import os
import re
import time
import tempfile
import pymysql
import pymysql.cursors
from decimal import Decimal
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import timedelta, datetime
import pdfplumber
import pytesseract
from PIL import Image

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuration
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "spmvv-result-analysis-secret-key-2024"
)
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=24)

jwt = JWTManager(app)

# Database configuration
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "db"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "spmvv_root_2024"),
    "database": os.environ.get("DB_NAME", "result_analysis"),
}


def get_db_connection(use_dict=False):
    """Get a database connection with retry logic."""
    max_retries = 30
    retry_delay = 2
    for attempt in range(max_retries):
        try:
            cursorclass = (
                pymysql.cursors.DictCursor if use_dict else pymysql.cursors.Cursor
            )
            conn = pymysql.connect(**DB_CONFIG, cursorclass=cursorclass)
            return conn
        except pymysql.Error as err:
            if attempt < max_retries - 1:
                print(
                    f"DB connection attempt {attempt + 1} failed: {err}. Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
            else:
                raise err


def serialize_row(row):
    """Convert non-JSON-serializable types in a dict row."""
    if not row:
        return row
    for k, v in row.items():
        if isinstance(v, Decimal):
            row[k] = float(v)
        elif isinstance(v, datetime):
            row[k] = v.isoformat()
    return row


def serialize_rows(rows):
    """Serialize a list of dict rows."""
    return [serialize_row(r) for r in rows]


# ============================================================
# FILE UPLOAD CONFIG
# ============================================================

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================
# MARKS MEMO PARSER
# ============================================================

# Roman numeral mapping
ROMAN_TO_INT = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
}

# Word-to-number mapping for marks in word form
WORD_TO_NUM = {
    "ZERO": 0,
    "ONE": 1,
    "TWO": 2,
    "THREE": 3,
    "FOUR": 4,
    "FIVE": 5,
    "SIX": 6,
    "SEVEN": 7,
    "EIGHT": 8,
    "NINE": 9,
}


def words_to_number(word_str):
    """Convert marks in word form to a number. E.g., 'SIX NINE' -> 69, 'SEVEN THREE' -> 73."""
    words = word_str.strip().upper().split()
    digits = []
    for w in words:
        # Clean OCR artifacts
        w = re.sub(r"[^A-Z]", "", w)
        if w in WORD_TO_NUM:
            digits.append(str(WORD_TO_NUM[w]))
    if digits:
        return int("".join(digits))
    return None


def _resolve_roman_ocr(s):
    """Resolve a roman numeral string with common OCR errors."""
    s = s.strip().upper()
    # Direct map for clean values
    if s in ROMAN_TO_INT:
        return ROMAN_TO_INT[s]
    # Common OCR misreads for "II"
    if s in ("IT", "IL", "I1", "11", "LI", "TI"):
        return 2
    # "III" misreads
    if s in ("III", "IIT", "IIL", "II1", "I11", "1II"):
        return 3
    # "IV" misreads
    if s in ("1V", "LV"):
        return 4
    # Single digit
    if s == "1":
        return 1
    if s == "2":
        return 2
    if s == "3":
        return 3
    if s == "4":
        return 4
    return None


def calculate_grade_from_marks(total_marks, parsed_grade=""):
    """Calculate grade and grade_points from total marks using SPMVV grading scale.

    If total_marks <= 40 and parsed OCR grade is 'F' or 'AB', preserve it.
    Otherwise derive grade purely from marks:
      91-100 -> O (10), 81-90 -> A (9), 71-80 -> B (8), 61-70 -> C (7),
      51-60 -> D (6), 41-50 -> P (5), <=40 -> F (0).
    """
    try:
        marks = int(total_marks)
    except (TypeError, ValueError):
        marks = 0

    if marks >= 91:
        return "O", 10.0
    elif marks >= 81:
        return "A", 9.0
    elif marks >= 71:
        return "B", 8.0
    elif marks >= 61:
        return "C", 7.0
    elif marks >= 51:
        return "D", 6.0
    elif marks >= 41:
        return "P", 5.0
    else:
        # For marks <= 40: check parsed OCR grade for F vs AB distinction
        pg = (parsed_grade or "").strip().upper()
        if pg == "AB":
            return "AB", 0.0
        return "F", 0.0


def parse_year_semester_from_text(text):
    """Extract year and semester from memo text."""
    year = None
    semester = None

    # Pattern: "I Year II SEMESTER" or "II Year I SEMESTER"
    # Also handle OCR errors: "IT" for "II", "Il" for "II", "1" for "I", etc.
    # Very flexible: allow 1-4 roman/OCR chars for year, 1-3 for semester
    ys_match = re.search(
        r"(I{1,4}V?|IV|[1-4]|I[T1Ll]|II[T1Ll])\s+Year\s+(I{1,3}V?|IV|[1-4]|I[T1Ll]|II[T1Ll])\s+SEMESTER",
        text,
        re.IGNORECASE,
    )
    if ys_match:
        year = _resolve_roman_ocr(ys_match.group(1))
        semester = _resolve_roman_ocr(ys_match.group(2))
        if year and semester:
            return year, semester

    # Fallback: "Course:B.Tech....  II Year II SEMESTER" with flexible spacing
    course_ys = re.search(
        r"(I{1,4}V?|IV|[1-4]|I[T1Ll]|II[T1Ll])\s*Year\s*(I{1,3}V?|IV|[1-4]|I[T1Ll]|II[T1Ll])\s*SEMESTER",
        text,
        re.IGNORECASE,
    )
    if course_ys:
        year = _resolve_roman_ocr(course_ys.group(1))
        semester = _resolve_roman_ocr(course_ys.group(2))
        if year and semester:
            return year, semester

    # Fallback: "Year : I" style (separate patterns)
    year_match = re.search(r"Year\s*[:]\s*(I{1,4}V?|[1-4])", text, re.IGNORECASE)
    if year_match:
        year = _resolve_roman_ocr(year_match.group(1))

    sem_match = re.search(
        r"Sem(?:ester)?\s*[:]\s*(I{1,3}V?|[1-2])", text, re.IGNORECASE
    )
    if sem_match:
        semester = _resolve_roman_ocr(sem_match.group(1))

    return year, semester


def parse_student_info_from_text(text):
    """Extract student name and hall ticket number from memo text."""
    info = {}

    # Hall Ticket No
    ht_match = re.search(
        r"(?:Hall\s*Ticket\s*No\.?|H\.?T\.?\s*No\.?|Regd\.?\s*No\.?)\s*[:.]?\s*([A-Za-z0-9/]+)",
        text,
        re.IGNORECASE,
    )
    if ht_match:
        info["hall_ticket"] = ht_match.group(1).strip()

    # Name
    name_match = re.search(
        r"(?:Name\s*[:.]?\s*)([A-Z][A-Za-z\s.]+?)(?:\s*[-—]?\s*Hall|\s*Regd|\s*H\.?T|\n)",
        text,
        re.IGNORECASE,
    )
    if name_match:
        name = name_match.group(1).strip()
        # Clean up: remove trailing artifacts
        name = re.sub(r"\s+Tt$", "", name).strip()
        info["name"] = name

    return info


def parse_sgpa_from_text(text):
    """Extract SGPA from memo text."""
    # Try SGPA/GPA pattern - prioritize SGPA
    sgpa_match = re.search(
        r"(?:S\.?G\.?P\.?A\.?|Semester\s*Grade\s*Point\s*Average\s*\(SGPA\))\s*[:.]?\s*(\d+\.?\d*)",
        text,
        re.IGNORECASE,
    )
    if sgpa_match:
        return float(sgpa_match.group(1))
    # Fallback: "Grade Point Average (GPA): 7.96"
    gpa_match = re.search(
        r"(?:Grade\s*Point\s*Average\s*\((?:S?GPA)\)|G\.?P\.?A\.?)\s*[:.]?\s*(\d+\.?\d*)",
        text,
        re.IGNORECASE,
    )
    if gpa_match:
        return float(gpa_match.group(1))
    return None


def parse_total_marks_from_text(text):
    """Extract total marks from text like 'Total Marks : 590/ 800' or '690/1000'."""
    tm_match = re.search(
        r"Total\s*Marks?\s*[:.]?\s*(\d+)\s*/\s*(\d+)", text, re.IGNORECASE
    )
    if tm_match:
        return int(tm_match.group(1)), int(tm_match.group(2))
    return None, None


def clean_text_line(line):
    """Clean a text line, removing extra whitespace."""
    return re.sub(r"\s+", " ", line).strip()


def normalize_subject_code(raw_code):
    """Normalize an OCR-extracted subject code.
    SPMVV codes follow the pattern: 20 + dept(2-3 letters) + type(T/P/S/C) + number(1-2 digits)
    E.g., 20BST04, 20CSP02, 20ECP12, 20CSS01, 20MEP03
    OCR may confuse O↔0, S↔5, etc. in numeric positions.
    The type letter (T=Theory, P=Practical, S=Skill/Seminar, C=?) is always a letter.
    """
    code = raw_code.upper().strip()
    # Remove leading/trailing non-alphanumeric (OCR artifacts like ')
    code = re.sub(r"^[^A-Z0-9]+", "", code)
    code = re.sub(r"[^A-Z0-9]+$", "", code)
    # Replace O with 0 in position 0-1 (the "20" prefix)
    if len(code) >= 2:
        prefix = code[:2].replace("O", "0")
        code = prefix + code[2:]

    # SPMVV structure: 20 + dept(2-3 alpha) + type(T/P/S/C: 1 alpha) + number(1-2 digits)
    # Total length: 7-8 chars (20 + 2-3 dept + 1 type + 2 digits)
    # Try to match with known type letters to split correctly
    # Pattern: 20 + 2 letter dept + type + digits
    m = re.match(r"^(20[A-Z]{2})([TPSC])([A-Z0-9O]{1,3})$", code)
    if m:
        dept = m.group(1)  # e.g., "20BS", "20CS", "20EC", "20EE", "20ME"
        typ = m.group(2)  # T, P, S, or C
        num = (
            m.group(3).replace("O", "0").replace("S", "5")
        )  # Fix O→0, S→5 in number part
        # Fix 3-digit numbers from OCR artifacts (e.g., "005" → "05")
        if len(num) == 3 and num[0] == "0":
            num = num[1:]
        return dept + typ + num

    # Pattern: 20 + 3 letter dept + type + digits
    m = re.match(r"^(20[A-Z]{3})([TPSC])([A-Z0-9O]{1,3})$", code)
    if m:
        dept = m.group(1)
        typ = m.group(2)
        num = m.group(3).replace("O", "0").replace("S", "5")
        # Fix 3-digit numbers from OCR artifacts
        if len(num) == 3 and num[0] == "0":
            num = num[1:]
        return dept + typ + num

    # Fallback: just fix trailing O→0 after the alpha prefix
    m = re.match(r"^(20[A-Z]{2,4})(.+)$", code)
    if m:
        alpha_part = m.group(1)
        tail = m.group(2)
        fixed_tail = tail.replace("O", "0")
        code = alpha_part + fixed_tail

    return code


def parse_ocr_subjects(text):
    """
    Parse subjects from OCR text of SPMVV marks memo.
    Handles both word-form marks and numeric marks.
    Returns a list of subject dicts with internal_marks, external_marks,
    total_marks, grade_points, and grade.

    Key design:
    - Subject codes may be on their own line, with name and marks on subsequent lines
    - Blank lines between code/name/marks are common in OCR output
    - Looks ahead up to 5 raw lines (skipping blanks) to find name and marks
    - Marks are typically in WORD FORM (e.g., "SIX NINE" = 69)
    - Numeric columns (credits, internal, external) appear between name and word marks
    - Grade appears as a standalone letter (O, A+, A, B+, B, C, D, F, AB)
    - Grade points are computed from grade using SPMVV grading scale
    """
    subjects = []
    lines = text.split("\n")

    # Subject code pattern: starts with 2, then 0/O, then 2-4 letters, then 1-3 alphanumeric
    # Allow leading punctuation (OCR artifacts like ' or -)
    code_pattern = re.compile(
        r"['\"\-\s]*\b(2[0O][A-Z]{2,4}[A-Z0-9O][0-9O]{0,2})\b", re.IGNORECASE
    )

    # Skip keywords for first-pass (detecting code lines) — aggressive filtering
    skip_keywords = [
        "paper code",
        "paper title",
        "sri padmavati",
        "tirupati",
        "women",
        "memorandum",
        "hall ticket",
        "name:",
        "course:",
        "maximum marks",
        "minimum marks",
        "total marks",
        "grand total",
        "aggregate",
        "semester grade",
        "sgpa",
        "gpa",
        "written by",
        "compared by",
        "note :",
        "descre",
        "theory subjects",
        "practical subjects",
        "examination",
        "internal",
        "ext. exam",
        "in words",
        "in figures",
        "satisfactory",
        "tirup",
        "weighted average",
        "marks in words",
    ]

    # Content-stop keywords: only these stop content collection after a code
    # (more conservative — don't stop on "in words" / "in figures" which appear
    # in the memo footer near the last subject on each page)
    content_stop_keywords = [
        "paper code",
        "paper title",
        "sri padmavati",
        "memorandum",
        "hall ticket",
        "name:",
        "course:",
        "maximum marks",
        "minimum marks",
        "total marks",
        "totalmarks",
        "grand total",
        "aggregate",
        "semester grade",
        "sgpa",
        "gpa",
        "written by",
        "compared by",
        "note :",
        "descre",
        "theory subjects",
        "practical subjects",
        "satisfactory",
        "weighted average",
        "in figures",
    ]

    # Valid grades
    grade_set = {"O", "A", "B", "C", "D", "P", "F", "AB"}

    # SPMVV Grade-to-GradePoints mapping
    grade_to_gp = {
        "O": 10.0,
        "A": 9.0,
        "B": 8.0,
        "C": 7.0,
        "D": 6.0,
        "P": 5.0,
        "F": 0.0,
        "AB": 0.0,
    }

    # Word-form marks pattern (at least 2 number words)
    word_marks_pattern = re.compile(
        r"((?:ZERO|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE)"
        r"(?:\s+(?:ZERO|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE))+)",
        re.IGNORECASE,
    )

    def is_skip_line(line):
        ll = line.lower()
        return any(kw in ll for kw in skip_keywords)

    def is_content_stop(line):
        """Check if a line should stop content collection (more conservative)."""
        ll = line.lower()
        return any(kw in ll for kw in content_stop_keywords)

    # First pass: find all lines with subject codes and their positions
    code_lines = []
    for idx, raw_line in enumerate(lines):
        line = clean_text_line(raw_line)
        if not line or len(line) < 4:
            continue
        if is_skip_line(line):
            continue
        m = code_pattern.search(line)
        if m:
            code_lines.append((idx, m))

    # Second pass: for each code, collect text until the next code
    for ci, (code_idx, code_match) in enumerate(code_lines):
        raw_code = code_match.group(1)
        subject_code = normalize_subject_code(raw_code)

        # Validate: should start with "20" after normalization
        if not subject_code.startswith("20"):
            continue

        current_line = clean_text_line(lines[code_idx])
        after_code = current_line[code_match.end() :].strip()
        after_code = re.sub(r"^[\s|]+", "", after_code)

        # Determine the boundary: next code line or end
        if ci + 1 < len(code_lines):
            next_code_idx = code_lines[ci + 1][0]
        else:
            next_code_idx = len(lines)

        # Collect non-blank, non-skip lines between this code and the next
        collected_parts = [after_code] if after_code else []
        content_lines_seen = 0
        max_content_lines = 5  # increased from 4 to catch more content
        for li in range(code_idx + 1, min(next_code_idx, code_idx + 10)):
            raw = clean_text_line(lines[li])
            if not raw or len(raw) < 2:
                continue  # skip blanks — don't count
            if is_content_stop(raw):
                break
            collected_parts.append(raw)
            content_lines_seen += 1
            # Stop if we found word marks
            if word_marks_pattern.search(raw):
                break
            if content_lines_seen >= max_content_lines:
                break

        combined = " ".join(collected_parts)

        # OCR fuzzy correction for garbled number words
        # Common OCR misreads: stx→SIX, OUR→FOUR, BIGHT→EIGHT, HINE→NINE, etc.
        ocr_word_fixes = {
            r"\bstx\b": "SIX",
            r"\bslx\b": "SIX",
            r"\bs[1l]x\b": "SIX",
            r"\bOUR\b": "FOUR",  # context: standalone OUR near number words
            r"\bBIGHT\b": "EIGHT",
            r"\bEIGHI\b": "EIGHT",
            r"\bHINE\b": "NINE",
            r"\bNINB\b": "NINE",
            r"\bFIVB\b": "FIVE",
            r"\bTHREF\b": "THREE",
            r"\bSEVBN\b": "SEVEN",
            r"\bSBVEN\b": "SEVEN",
            r"\bZBRO\b": "ZERO",
            r"\bZER0\b": "ZERO",
            r"\bTW0\b": "TWO",
            r"\bF0UR\b": "FOUR",
        }
        fixed_combined = combined
        for pat, replacement in ocr_word_fixes.items():
            fixed_combined = re.sub(
                pat, replacement, fixed_combined, flags=re.IGNORECASE
            )

        # Extract marks in word form
        subject_name = ""
        grade = ""
        total_marks = None
        internal_marks = 0
        external_marks = 0
        grade_points = 0.0

        wm = word_marks_pattern.search(fixed_combined)
        if wm:
            candidate_marks = words_to_number(wm.group(1))
            # Sanity check: single subject marks should be 0-100
            # Values > 100 are likely page totals (e.g., 590/800)
            if candidate_marks is not None and 0 <= candidate_marks <= 100:
                total_marks = candidate_marks
                before_marks = fixed_combined[: wm.start()].strip()
                after_word_marks = fixed_combined[wm.end() :].strip()
            else:
                # Rejected word marks (too high) — still strip them from name
                before_marks = fixed_combined[: wm.start()].strip()
                after_word_marks = ""
        else:
            before_marks = combined
            after_word_marks = ""

        # Extract grade: only check for AB (absent) from OCR text
        # All other grades are calculated from total marks
        grade_search_text = before_marks + " " + after_word_marks
        ocr_grade = ""
        # Only look for AB — indicates absent
        ab_match = re.search(r"(?:^|\s|\|)\s*(AB)\s*(?:\s|\||$)", grade_search_text)
        if ab_match:
            ocr_grade = "AB"

        # Calculate grade and grade_points from total marks
        if total_marks is not None:
            grade, grade_points = calculate_grade_from_marks(total_marks, ocr_grade)
        elif ocr_grade == "AB":
            grade = "AB"
            grade_points = 0.0

        # Extract numeric internal/external marks from before_marks
        # After removing the subject name, look for sequences of 2-3 digit numbers
        # Pattern: ... subject_name [credits] [internal] [external] ... WORD_MARKS
        # The numbers typically appear as: 1-digit credits, then 2-digit internal, 2-digit external
        # Find all 1-3 digit numbers in before_marks
        all_nums_in_before = re.findall(r"\b(\d{1,3})\b", before_marks)
        all_nums = [int(n) for n in all_nums_in_before]

        # Filter for plausible marks (internal: 0-40, external: 0-70 for theory; 0-60 for practical)
        # Credits are typically 1-4
        # Strategy: find sequences of [credits, internal, external] or [internal, external]
        marks_candidates = []
        for n in all_nums:
            if 0 <= n <= 100:
                marks_candidates.append(n)

        # Try to identify internal and external from numeric candidates
        if len(marks_candidates) >= 3:
            # Likely: credits, internal, external (or some other combo)
            # Credits is typically 1-4, internal 0-40, external 0-70
            # Try to find a pattern where credits(1-6), internal(0-40), external(0-70)
            for i in range(len(marks_candidates) - 2):
                c, a, b = (
                    marks_candidates[i],
                    marks_candidates[i + 1],
                    marks_candidates[i + 2],
                )
                if 1 <= c <= 6 and 0 <= a <= 40 and 0 <= b <= 70:
                    # Validate: a + b should be close to total_marks if we have it
                    if total_marks is not None:
                        if abs((a + b) - total_marks) <= 2:  # allow small OCR error
                            internal_marks = a
                            external_marks = b
                            break
                    else:
                        internal_marks = a
                        external_marks = b
                        break
        elif len(marks_candidates) >= 2:
            # Might be just internal, external (no credits)
            for i in range(len(marks_candidates) - 1):
                a, b = marks_candidates[i], marks_candidates[i + 1]
                if 0 <= a <= 40 and 0 <= b <= 70:
                    if total_marks is not None:
                        if abs((a + b) - total_marks) <= 2:
                            internal_marks = a
                            external_marks = b
                            break
                    else:
                        internal_marks = a
                        external_marks = b
                        break

        # Extract subject name from before_marks
        name_part = before_marks

        # Remove pipe chars
        name_part = re.sub(r"\|", " ", name_part)
        # Remove "in Words" / "in Figures" that may have been collected
        name_part = re.sub(
            r"\s+in\s+(?:words|figures)\s*$", "", name_part, flags=re.IGNORECASE
        )
        name_part = re.sub(
            r"\s+in\s+(?:words|figures)\s+", " ", name_part, flags=re.IGNORECASE
        )
        # Remove trailing numbers (credits, internal/external marks)
        # Pattern: remove sequences of 1-2 digit numbers at the end
        name_part = re.sub(r"(\s+\d{1,3}){1,5}\s*$", "", name_part)
        # Remove trailing grade
        if grade:
            escaped_grade = re.escape(grade)
            name_part = re.sub(r"\s+" + escaped_grade + r"\s*$", "", name_part)
        # Remove trailing single-char grade-like letters
        name_part = re.sub(r"\s+[OABCDFP]\s*$", "", name_part, flags=re.IGNORECASE)
        # Remove trailing digits again
        name_part = re.sub(r"\s+\d{1,3}\s*$", "", name_part)
        # Clean artifacts
        name_part = re.sub(r"^[^A-Za-z]+", "", name_part).strip()
        # Remove trailing non-alpha junk (numbers, symbols, OCR artifacts)
        name_part = re.sub(r"[\s]+[^A-Za-z\s]{1,3}$", "", name_part).strip()
        name_part = re.sub(r"[^A-Za-z0-9)\s.&/-]+$", "", name_part).strip()
        # Remove trailing artifact patterns like "9 o 3 %] &" or "S, \" AN"
        name_part = re.sub(
            r"\s+\d+\s+[a-z]\s+\d+\s*[%\]}&;|]+.*$", "", name_part, flags=re.IGNORECASE
        ).strip()
        name_part = re.sub(
            r"\s+[A-Z],?\s*[\"\'\\]+\s*[A-Z]*\s*$", "", name_part
        ).strip()
        # Remove stray trailing chars
        name_part = re.sub(r"\s+[.:;,]+\s*$", "", name_part).strip()
        # Remove trailing OCR noise like "HX", "VEN", "b4" at the end
        name_part = re.sub(r"\s+[A-Z]{1,3}\s*$", "", name_part).strip()
        name_part = re.sub(r"\s+[a-z]\d\s*$", "", name_part).strip()
        # Remove footer/header text that leaked into name
        name_part = re.sub(
            r"\s*(?:TotalMarks|Total\s*Marks|in\s+Words|in\s+Figures|Semester\s+Grade).*$",
            "",
            name_part,
            flags=re.IGNORECASE,
        ).strip()
        # Remove OCR junk between split subject names (e.g., "3 18 49 VEN b4")
        # Pattern: sequences of short numeric/alpha tokens that aren't real words
        name_part = re.sub(
            r"\s+\d{1,2}\s+\d{1,2}\s+\d{1,2}\s+[A-Z]{1,4}\s+[a-z0-9]{1,3}\s+",
            " ",
            name_part,
        ).strip()
        # Remove trailing PR, N, and other single-char OCR artifacts
        name_part = re.sub(r"\s+[A-Z]{1,2}\s+[a-z]\s+\w+\s*$", "", name_part).strip()
        name_part = re.sub(r"\s+[A-Z]{1,2}\s*$", "", name_part).strip()

        if name_part:
            subject_name = name_part
        else:
            subject_name = subject_code

        # Try numeric marks if word marks not found
        if total_marks is None:
            nums = re.findall(r"\b(\d{2,3})\b", combined)
            bigger_nums = [int(n) for n in nums if 20 <= int(n) <= 100]
            if len(bigger_nums) >= 2:
                total_marks = bigger_nums[-1]
            elif len(bigger_nums) == 1:
                total_marks = bigger_nums[0]

        # If we have internal + external but no total, compute it
        if total_marks is None and internal_marks > 0 and external_marks > 0:
            total_marks = internal_marks + external_marks

        # Determine pass/fail
        status = "PASS"
        if grade.upper() in ("F", "AB"):
            status = "FAIL"
        elif total_marks is not None and total_marks < 40:
            status = "FAIL"

        # Always include the subject — even with total_marks=0
        # Student can manually fill in marks in the preview
        subjects.append(
            {
                "subject_code": subject_code,
                "subject_name": subject_name,
                "internal_marks": internal_marks,
                "external_marks": external_marks,
                "total_marks": total_marks if total_marks is not None else 0,
                "grade_points": grade_points,
                "grade": grade,
                "status": status,
            }
        )

    # Deduplicate: if same subject_code appears multiple times (across pages),
    # keep the entry with the most data (highest total_marks > 0, or has grade)
    seen = {}
    for s in subjects:
        code = s["subject_code"]
        if code not in seen:
            seen[code] = s
        else:
            existing = seen[code]

            # Score: prefer entry with marks, then grade, then better name
            def score(entry):
                sc = 0
                if entry["total_marks"] > 0:
                    sc += 100
                if entry["internal_marks"] > 0:
                    sc += 10
                if entry["grade"]:
                    sc += 5
                if entry["subject_name"] != entry["subject_code"]:
                    sc += 2
                return sc

            if score(s) > score(existing):
                # Merge: keep better entry but fill in missing fields from other
                if not s["subject_name"] or s["subject_name"] == s["subject_code"]:
                    s["subject_name"] = existing["subject_name"]
                if not s["grade"] and existing["grade"]:
                    s["grade"] = existing["grade"]
                    s["grade_points"] = existing["grade_points"]
                seen[code] = s
            else:
                # Keep existing but fill in missing fields from new
                if (
                    not existing["subject_name"]
                    or existing["subject_name"] == existing["subject_code"]
                ):
                    existing["subject_name"] = s["subject_name"]
                if not existing["grade"] and s["grade"]:
                    existing["grade"] = s["grade"]
                    existing["grade_points"] = s["grade_points"]

    return list(seen.values())


def ocr_pdf_to_text(filepath):
    """Convert a scanned PDF to text using pdftoppm + Tesseract OCR."""
    import subprocess

    pages_text = []
    tmp_prefix = os.path.join(tempfile.gettempdir(), f"memo_ocr_{int(time.time())}")

    try:
        # Convert PDF pages to images
        result = subprocess.run(
            ["pdftoppm", "-png", "-r", "300", filepath, tmp_prefix],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise ValueError(f"PDF to image conversion failed: {result.stderr}")

        # Find generated images
        tmp_dir = os.path.dirname(tmp_prefix)
        prefix_name = os.path.basename(tmp_prefix)
        page_files = sorted(
            [
                f
                for f in os.listdir(tmp_dir)
                if f.startswith(prefix_name) and f.endswith(".png")
            ]
        )

        for pf in page_files:
            img_path = os.path.join(tmp_dir, pf)
            try:
                img = Image.open(img_path).convert("L")
                # Enhance contrast for better OCR
                from PIL import ImageEnhance

                enhanced = ImageEnhance.Contrast(img).enhance(2.0)
                text = pytesseract.image_to_string(
                    enhanced, lang="eng", config="--psm 3 --oem 3"
                )
                pages_text.append(text)
            finally:
                try:
                    os.remove(img_path)
                except OSError:
                    pass

    except subprocess.TimeoutExpired:
        raise ValueError("PDF conversion timed out")

    return pages_text


def parse_pdf_memo(filepath):
    """
    Parse a marks memo PDF.
    First tries pdfplumber (for text-based PDFs).
    Falls back to OCR (for scanned/image-based PDFs).
    """
    all_semesters = []

    # Try pdfplumber first
    try:
        has_text = False
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if len(text.strip()) > 100:
                    has_text = True
                    break

        if has_text:
            # Text-based PDF - use pdfplumber
            with pdfplumber.open(filepath) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    if not text.strip():
                        continue
                    year, semester = parse_year_semester_from_text(text)
                    student_info = parse_student_info_from_text(text)
                    sgpa = parse_sgpa_from_text(text)
                    subjects = parse_ocr_subjects(text)
                    if subjects:
                        all_semesters.append(
                            {
                                "page": page_num + 1,
                                "year": year,
                                "semester": semester,
                                "student_info": student_info,
                                "sgpa": sgpa,
                                "subjects": subjects,
                            }
                        )
            if all_semesters:
                return all_semesters
    except Exception:
        pass

    # Scanned PDF - use OCR
    pages_text = ocr_pdf_to_text(filepath)

    for page_num, text in enumerate(pages_text):
        if not text.strip():
            continue

        year, semester = parse_year_semester_from_text(text)
        student_info = parse_student_info_from_text(text)
        sgpa = parse_sgpa_from_text(text)
        subjects = parse_ocr_subjects(text)

        if subjects:
            all_semesters.append(
                {
                    "page": page_num + 1,
                    "year": year,
                    "semester": semester,
                    "student_info": student_info,
                    "sgpa": sgpa,
                    "subjects": subjects,
                }
            )

    return all_semesters


def parse_image_memo(filepath):
    """
    Parse a marks memo image using Tesseract OCR.
    Returns a list of semester results (usually just one per image).
    """
    try:
        img = Image.open(filepath).convert("L")
        from PIL import ImageEnhance

        enhanced = ImageEnhance.Contrast(img).enhance(2.0)
        text = pytesseract.image_to_string(
            enhanced, lang="eng", config="--psm 3 --oem 3"
        )

        if not text.strip():
            raise ValueError("No text could be extracted from the image")

        year, semester = parse_year_semester_from_text(text)
        student_info = parse_student_info_from_text(text)
        sgpa = parse_sgpa_from_text(text)
        subjects = parse_ocr_subjects(text)

        if not subjects:
            raise ValueError(
                "Could not extract any subject data from the image. "
                "Please ensure the image is clear and contains a marks table."
            )

        return [
            {
                "page": 1,
                "year": year,
                "semester": semester,
                "student_info": student_info,
                "sgpa": sgpa,
                "subjects": subjects,
            }
        ]

    except pytesseract.TesseractNotFoundError:
        raise ValueError("OCR engine not available. Please upload a PDF instead.")
    except Exception as e:
        raise ValueError(f"Failed to parse image: {str(e)}")


def init_db():
    """Initialize database tables and default admin."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(255) NOT NULL,
            roll_number VARCHAR(50) NOT NULL UNIQUE,
            branch ENUM('CSE', 'ECE', 'EEE', 'MECH') NOT NULL,
            section ENUM('A', 'B', 'C') NOT NULL,
            password VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            full_name VARCHAR(255) DEFAULT '',
            role ENUM('super_admin', 'admin', 'staff') DEFAULT 'admin',
            permissions TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migrate existing admins table: add columns if missing
    try:
        cursor.execute(
            "ALTER TABLE admins ADD COLUMN full_name VARCHAR(255) DEFAULT '' AFTER password"
        )
    except Exception:
        pass
    try:
        cursor.execute(
            "ALTER TABLE admins ADD COLUMN role ENUM('super_admin', 'admin', 'staff') DEFAULT 'admin' AFTER full_name"
        )
    except Exception:
        pass
    try:
        cursor.execute(
            "ALTER TABLE admins ADD COLUMN permissions TEXT DEFAULT NULL AFTER role"
        )
    except Exception:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INT AUTO_INCREMENT PRIMARY KEY,
            roll_number VARCHAR(50) NOT NULL,
            year INT NOT NULL,
            semester INT NOT NULL,
            subject_code VARCHAR(50) NOT NULL,
            subject_name VARCHAR(255) NOT NULL,
            internal_marks INT DEFAULT 0,
            external_marks INT DEFAULT 0,
            total_marks INT DEFAULT 0,
            max_marks INT NOT NULL DEFAULT 100,
            grade_points DECIMAL(4,2) DEFAULT 0,
            grade VARCHAR(5) DEFAULT '',
            status ENUM('PASS', 'FAIL', 'AB', 'MP') DEFAULT 'PASS',
            academic_year VARCHAR(20) NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (roll_number) REFERENCES students(roll_number) ON DELETE CASCADE,
            UNIQUE KEY unique_result (roll_number, year, semester, subject_code)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS semester_summary (
            id INT AUTO_INCREMENT PRIMARY KEY,
            roll_number VARCHAR(50) NOT NULL,
            year INT NOT NULL,
            semester INT NOT NULL,
            sgpa DECIMAL(4,2) DEFAULT 0,
            total_marks INT DEFAULT 0,
            total_subjects INT DEFAULT 0,
            passed_subjects INT DEFAULT 0,
            failed_subjects INT DEFAULT 0,
            academic_year VARCHAR(20) NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (roll_number) REFERENCES students(roll_number) ON DELETE CASCADE,
            UNIQUE KEY unique_semester (roll_number, year, semester)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS correction_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            roll_number VARCHAR(50) NOT NULL,
            result_id INT,
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            attachment_path VARCHAR(500) DEFAULT NULL,
            status ENUM('PENDING', 'IN_PROGRESS', 'REVIEWED', 'RESOLVED', 'REJECTED') DEFAULT 'PENDING',
            admin_remarks TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (roll_number) REFERENCES students(roll_number) ON DELETE CASCADE,
            FOREIGN KEY (result_id) REFERENCES results(id) ON DELETE SET NULL
        )
    """)

    # Add student_read column if not exists
    try:
        cursor.execute(
            "ALTER TABLE correction_requests ADD COLUMN student_read TINYINT(1) DEFAULT 0"
        )
    except Exception:
        pass  # Column already exists

    # Add IN_PROGRESS to status enum if not already present
    try:
        cursor.execute(
            "ALTER TABLE correction_requests MODIFY COLUMN status ENUM('PENDING', 'IN_PROGRESS', 'REVIEWED', 'RESOLVED', 'REJECTED') DEFAULT 'PENDING'"
        )
    except Exception:
        pass

    # Add year and semester columns to correction_requests
    try:
        cursor.execute(
            "ALTER TABLE correction_requests ADD COLUMN year INT DEFAULT NULL AFTER result_id"
        )
    except Exception:
        pass
    try:
        cursor.execute(
            "ALTER TABLE correction_requests ADD COLUMN semester INT DEFAULT NULL AFTER year"
        )
    except Exception:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS upload_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            roll_number VARCHAR(50) NOT NULL,
            original_filename VARCHAR(255) NOT NULL DEFAULT '',
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            year_semester_data TEXT DEFAULT NULL,
            num_subjects INT DEFAULT 0,
            num_semesters INT DEFAULT 0,
            status ENUM('CONFIRMED', 'DELETED') DEFAULT 'CONFIRMED',
            FOREIGN KEY (roll_number) REFERENCES students(roll_number) ON DELETE CASCADE
        )
    """)

    # Insert default admin if not exists
    cursor.execute("SELECT COUNT(*) FROM admins WHERE username = 'admin'")
    count = cursor.fetchone()[0]
    if count == 0:
        hashed_password = generate_password_hash("admin123")
        cursor.execute(
            "INSERT INTO admins (username, password, full_name, role) VALUES (%s, %s, %s, %s)",
            ("admin", hashed_password, "Administrator", "super_admin"),
        )
        print("Default admin account created.")
    else:
        # Ensure existing admin has super_admin role
        cursor.execute(
            "UPDATE admins SET role = 'super_admin' WHERE username = 'admin' AND (role IS NULL OR role = 'admin')"
        )

    conn.commit()
    cursor.close()
    conn.close()
    print("Database initialized successfully.")


# ============================================================
# AUTH ROUTES
# ============================================================


@app.route("/api/auth/student/register", methods=["POST"])
def student_register():
    """Register a new student."""
    data = request.get_json()

    required_fields = [
        "full_name",
        "roll_number",
        "branch",
        "section",
        "password",
        "confirm_password",
    ]
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"{field} is required"}), 400

    if data["password"] != data["confirm_password"]:
        return jsonify({"error": "Passwords do not match"}), 400

    if data["branch"] not in ["CSE", "ECE", "EEE", "MECH"]:
        return jsonify({"error": "Invalid branch selected"}), 400

    if data["section"] not in ["A", "B", "C"]:
        return jsonify({"error": "Invalid section selected"}), 400

    if len(data["password"]) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM students WHERE roll_number = %s", (data["roll_number"],)
        )
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Roll number already registered"}), 409

        hashed_password = generate_password_hash(data["password"])
        cursor.execute(
            "INSERT INTO students (full_name, roll_number, branch, section, password) VALUES (%s, %s, %s, %s, %s)",
            (
                data["full_name"],
                data["roll_number"],
                data["branch"],
                data["section"],
                hashed_password,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Registration successful! You can now login."}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/auth/student/login", methods=["POST"])
def student_login():
    """Student login."""
    data = request.get_json()

    if not data.get("roll_number") or not data.get("password"):
        return jsonify({"error": "Roll number and password are required"}), 400

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM students WHERE roll_number = %s", (data["roll_number"],)
        )
        student = cursor.fetchone()
        cursor.close()
        conn.close()

        if not student or not check_password_hash(
            student["password"], data["password"]
        ):
            return jsonify({"error": "Invalid roll number or password"}), 401

        access_token = create_access_token(
            identity=student["roll_number"],
            additional_claims={
                "role": "student",
                "full_name": student["full_name"],
                "branch": student["branch"],
                "section": student["section"],
            },
        )

        return jsonify(
            {
                "message": "Login successful",
                "access_token": access_token,
                "user": {
                    "full_name": student["full_name"],
                    "roll_number": student["roll_number"],
                    "branch": student["branch"],
                    "section": student["section"],
                    "role": "student",
                },
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/auth/admin/login", methods=["POST"])
def admin_login():
    """Admin login."""
    data = request.get_json()

    if not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password are required"}), 400

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM admins WHERE username = %s", (data["username"],))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()

        if not admin or not check_password_hash(admin["password"], data["password"]):
            return jsonify({"error": "Invalid username or password"}), 401

        access_token = create_access_token(
            identity=admin["username"],
            additional_claims={
                "role": "admin",
                "admin_role": admin.get("role", "admin"),
                "permissions": admin.get("permissions", ""),
                "full_name": admin.get("full_name", ""),
            },
        )

        return jsonify(
            {
                "message": "Login successful",
                "access_token": access_token,
                "user": {
                    "username": admin["username"],
                    "role": "admin",
                    "admin_role": admin.get("role", "admin"),
                    "full_name": admin.get("full_name", ""),
                    "permissions": admin.get("permissions", ""),
                },
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# HELPER: compute CGPA and pending subjects
# ============================================================


def compute_cgpa_and_pending(roll_number, up_to_year=None, up_to_semester=None):
    """
    Compute CGPA (average of SGPAs) and pending (failed) subjects
    for a student, optionally filtered up to a given year/semester.
    """
    conn = get_db_connection(use_dict=True)
    cursor = conn.cursor()

    # Build filter for semester_summary
    query = "SELECT * FROM semester_summary WHERE roll_number = %s"
    params = [roll_number]
    if up_to_year and up_to_semester:
        query += " AND (year < %s OR (year = %s AND semester <= %s))"
        params.extend([int(up_to_year), int(up_to_year), int(up_to_semester)])
    elif up_to_year:
        query += " AND year <= %s"
        params.append(int(up_to_year))
    query += " ORDER BY year, semester"

    cursor.execute(query, params)
    summaries = serialize_rows(cursor.fetchall())

    # CGPA = average of all SGPAs
    sgpas = [s["sgpa"] for s in summaries if s["sgpa"] and s["sgpa"] > 0]
    cgpa = round(sum(sgpas) / len(sgpas), 2) if sgpas else 0

    # Get pending (failed) subjects
    query2 = "SELECT * FROM results WHERE roll_number = %s AND status = 'FAIL'"
    params2 = [roll_number]
    if up_to_year and up_to_semester:
        query2 += " AND (year < %s OR (year = %s AND semester <= %s))"
        params2.extend([int(up_to_year), int(up_to_year), int(up_to_semester)])
    elif up_to_year:
        query2 += " AND year <= %s"
        params2.append(int(up_to_year))
    query2 += " ORDER BY year, semester, subject_code"

    cursor.execute(query2, params2)
    pending_subjects = serialize_rows(cursor.fetchall())

    cursor.close()
    conn.close()

    return {
        "cgpa": cgpa,
        "sgpas": summaries,
        "pending_subjects": pending_subjects,
        "total_semesters": len(summaries),
    }


# ============================================================
# STUDENT ROUTES
# ============================================================


@app.route("/api/student/profile", methods=["GET"])
@jwt_required()
def get_student_profile():
    """Get student profile."""
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"error": "Access denied"}), 403

    identity = get_jwt_identity()
    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, full_name, roll_number, branch, section, created_at FROM students WHERE roll_number = %s",
            (identity,),
        )
        student = cursor.fetchone()
        cursor.close()
        conn.close()

        if not student:
            return jsonify({"error": "Student not found"}), 404

        student = serialize_row(student)
        return jsonify({"student": student}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/student/results", methods=["GET"])
@jwt_required()
def get_student_results():
    """Get results for the logged-in student with optional year/semester filter."""
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"error": "Access denied"}), 403

    identity = get_jwt_identity()
    year = request.args.get("year")
    semester = request.args.get("semester")

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()

        query = "SELECT * FROM results WHERE roll_number = %s"
        params = [identity]
        if year and semester:
            query += " AND (year < %s OR (year = %s AND semester <= %s))"
            params.extend([int(year), int(year), int(semester)])
        elif year:
            query += " AND year <= %s"
            params.append(int(year))
        query += " ORDER BY year, semester, subject_code"

        cursor.execute(query, params)
        results = serialize_rows(cursor.fetchall())

        # Get semester summaries
        sq = "SELECT * FROM semester_summary WHERE roll_number = %s"
        sp = [identity]
        if year and semester:
            sq += " AND (year < %s OR (year = %s AND semester <= %s))"
            sp.extend([int(year), int(year), int(semester)])
        elif year:
            sq += " AND year <= %s"
            sp.append(int(year))
        sq += " ORDER BY year, semester"

        cursor.execute(sq, sp)
        summaries = serialize_rows(cursor.fetchall())

        cursor.close()
        conn.close()

        # Compute CGPA and pending
        stats = compute_cgpa_and_pending(identity, year, semester)

        return jsonify(
            {
                "results": results,
                "semester_summaries": summaries,
                "cgpa": stats["cgpa"],
                "pending_subjects": stats["pending_subjects"],
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# STUDENT MEMO UPLOAD ROUTES
# ============================================================


@app.route("/api/student/upload-memo", methods=["POST"])
@jwt_required()
def upload_memo():
    """
    Upload a marks memo (PDF or image) and parse it.
    Returns extracted data for student review before saving.
    """
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"error": "Please login as a student to upload memos"}), 403

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify(
            {"error": "Invalid file type. Allowed: PDF, PNG, JPG, JPEG"}
        ), 400

    try:
        # Save file temporarily
        filename = secure_filename(file.filename)
        ext = filename.rsplit(".", 1)[1].lower()
        tmp_path = os.path.join(
            UPLOAD_FOLDER, f"memo_{get_jwt_identity()}_{int(time.time())}.{ext}"
        )
        file.save(tmp_path)

        # Parse based on file type
        if ext == "pdf":
            semesters = parse_pdf_memo(tmp_path)
        else:
            semesters = parse_image_memo(tmp_path)

        # Clean up temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass

        if not semesters:
            return jsonify(
                {
                    "error": "Could not extract any data from the uploaded file. "
                    "Please ensure it contains a valid marks memo with a readable table."
                }
            ), 422

        return jsonify(
            {
                "message": "File parsed successfully",
                "semesters": semesters,
                "total_semesters": len(semesters),
                "total_subjects": sum(len(s["subjects"]) for s in semesters),
            }
        ), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        return jsonify({"error": f"Failed to process file: {str(e)}"}), 500


@app.route("/api/student/confirm-memo", methods=["POST"])
@jwt_required()
def confirm_memo():
    """
    Save the parsed (and potentially student-edited) memo data to DB.
    Expects JSON with semesters array, each containing year, semester, sgpa, subjects.
    Student can edit: subject_code, subject_name, academic_year.
    Student CANNOT edit: marks, grade_points, grade, sgpa.
    """
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify(
            {"error": "Please login as a student to perform this action"}
        ), 403

    identity = get_jwt_identity()
    data = request.get_json()

    if not data or "semesters" not in data:
        return jsonify({"error": "No semester data provided"}), 400

    semesters = data["semesters"]
    if not semesters:
        return jsonify({"error": "Empty semester data"}), 400

    original_filename = data.get("filename", "unknown")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify student exists
        cursor.execute("SELECT id FROM students WHERE roll_number = %s", (identity,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Student not found"}), 404

        results_added = 0
        summaries_added = 0

        for sem in semesters:
            year = int(sem.get("year", 0))
            semester = int(sem.get("semester", 0))
            sgpa = float(sem.get("sgpa", 0)) if sem.get("sgpa") else 0
            academic_year = sem.get("academic_year", "")
            subjects = sem.get("subjects", [])

            if not year or not semester:
                continue

            for subj in subjects:
                subject_code = subj.get("subject_code", "").strip()
                subject_name = subj.get("subject_name", "").strip()
                internal = int(subj.get("internal_marks", 0))
                external = int(subj.get("external_marks", 0))
                total = int(subj.get("total_marks", internal + external))
                parsed_grade = subj.get("grade", "").strip()
                status = subj.get("status", "PASS").strip().upper()

                if not subject_code:
                    continue

                # Calculate grade and grade_points from total marks
                grade, grade_points = calculate_grade_from_marks(total, parsed_grade)

                if status not in ("PASS", "FAIL", "AB", "MP"):
                    status = "FAIL" if grade.upper() in ("F", "AB") else "PASS"

                cursor.execute(
                    """INSERT INTO results
                       (roll_number, year, semester, subject_code, subject_name,
                        internal_marks, external_marks, total_marks, max_marks,
                        grade_points, grade, status, academic_year)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE
                        subject_name=VALUES(subject_name),
                        internal_marks=VALUES(internal_marks),
                        external_marks=VALUES(external_marks),
                        total_marks=VALUES(total_marks),
                        grade_points=VALUES(grade_points),
                        grade=VALUES(grade),
                        status=VALUES(status),
                        academic_year=VALUES(academic_year)
                    """,
                    (
                        identity,
                        year,
                        semester,
                        subject_code,
                        subject_name,
                        internal,
                        external,
                        total,
                        100,
                        grade_points,
                        grade,
                        status,
                        academic_year,
                    ),
                )
                results_added += 1

            # Upsert semester summary
            # Calculate SGPA from grade points (average of all subject grade points)
            if subjects:
                computed_grade_points = []
                for subj in subjects:
                    total = int(subj.get("total_marks", 0))
                    pg = subj.get("grade", "")
                    g, gp = calculate_grade_from_marks(total, pg)
                    computed_grade_points.append(gp)

                if computed_grade_points:
                    sgpa = round(
                        sum(computed_grade_points) / len(computed_grade_points), 2
                    )

                total_subj = len(subjects)
                passed = len(
                    [s for s in subjects if s.get("status", "PASS").upper() == "PASS"]
                )
                failed = total_subj - passed
                total_marks_sum = sum(int(s.get("total_marks", 0)) for s in subjects)

                cursor.execute(
                    """INSERT INTO semester_summary
                       (roll_number, year, semester, sgpa, total_marks,
                        total_subjects, passed_subjects, failed_subjects, academic_year)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE
                        sgpa=VALUES(sgpa),
                        total_marks=VALUES(total_marks),
                        total_subjects=VALUES(total_subjects),
                        passed_subjects=VALUES(passed_subjects),
                        failed_subjects=VALUES(failed_subjects),
                        academic_year=VALUES(academic_year)
                    """,
                    (
                        identity,
                        year,
                        semester,
                        sgpa,
                        total_marks_sum,
                        total_subj,
                        passed,
                        failed,
                        academic_year,
                    ),
                )
                summaries_added += 1

        # Record upload history
        import json as json_lib

        year_sem_info = []
        for sem in semesters:
            y = int(sem.get("year", 0))
            s = int(sem.get("semester", 0))
            subj_codes = [
                sub.get("subject_code", "") for sub in sem.get("subjects", [])
            ]
            year_sem_info.append(
                {"year": y, "semester": s, "subject_codes": subj_codes}
            )

        cursor.execute(
            """INSERT INTO upload_history
               (roll_number, original_filename, year_semester_data, num_subjects, num_semesters)
               VALUES (%s, %s, %s, %s, %s)""",
            (
                identity,
                original_filename,
                json_lib.dumps(year_sem_info),
                results_added,
                len(semesters),
            ),
        )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify(
            {
                "message": f"Successfully saved {results_added} results and {summaries_added} semester summaries",
                "results_added": results_added,
                "summaries_added": summaries_added,
            }
        ), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# ADMIN ROUTES
# ============================================================


@app.route("/api/admin/overview-stats", methods=["GET"])
@jwt_required()
def admin_overview_stats():
    """Get comprehensive overview stats for admin dashboard.

    Returns:
    - branch_breakdown: per-branch, per-year (derived from roll prefix), per-section counts
    - batch_upload_stats: per-batch, per-year/semester upload counts vs total registered
    """
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()

        # 1. Get all students
        cursor.execute(
            "SELECT id, full_name, roll_number, branch, section FROM students ORDER BY roll_number"
        )
        all_students = cursor.fetchall()

        # 2. Build branch breakdown (branch -> { total, years: { year_prefix -> { total, sections: { section -> count } } } })
        branch_breakdown = {}
        batch_students = {}  # batch_prefix -> list of roll_numbers

        for s in all_students:
            branch = s["branch"] or "OTHER"
            section = s["section"] or "N/A"
            roll = s["roll_number"] or ""

            # Detect batch from first 2 digits of roll number
            batch_prefix = roll[:2] if len(roll) >= 2 and roll[:2].isdigit() else "XX"
            batch_year = f"20{batch_prefix}" if batch_prefix != "XX" else "Unknown"

            # Branch breakdown
            if branch not in branch_breakdown:
                branch_breakdown[branch] = {"total": 0, "batches": {}}
            branch_breakdown[branch]["total"] += 1

            if batch_year not in branch_breakdown[branch]["batches"]:
                branch_breakdown[branch]["batches"][batch_year] = {
                    "total": 0,
                    "sections": {},
                }
            branch_breakdown[branch]["batches"][batch_year]["total"] += 1

            sec_data = branch_breakdown[branch]["batches"][batch_year]["sections"]
            sec_data[section] = sec_data.get(section, 0) + 1

            # Track batch -> roll_numbers
            if batch_year not in batch_students:
                batch_students[batch_year] = []
            batch_students[batch_year].append(roll)

        # 3. Build batch upload stats
        # For each batch, find which students have uploaded results for each year/semester
        batch_upload_stats = {}

        for batch_year, roll_numbers in sorted(batch_students.items()):
            if not roll_numbers:
                continue

            # Find distinct year/semester combinations that have results for this batch
            placeholders = ",".join(["%s"] * len(roll_numbers))
            cursor.execute(
                f"""SELECT year, semester, COUNT(DISTINCT roll_number) as uploaded_count
                    FROM results
                    WHERE roll_number IN ({placeholders})
                    GROUP BY year, semester
                    ORDER BY year, semester""",
                roll_numbers,
            )
            upload_rows = cursor.fetchall()

            semesters = []
            for row in upload_rows:
                semesters.append(
                    {
                        "year": row["year"],
                        "semester": row["semester"],
                        "uploaded": row["uploaded_count"],
                        "total": len(roll_numbers),
                        "pending": len(roll_numbers) - row["uploaded_count"],
                    }
                )

            batch_prefix = batch_year[2:] if batch_year.startswith("20") else batch_year
            # Calculate end year (4-year program)
            try:
                end_year = int(batch_year) + 4
                batch_label = f"{batch_year}-{end_year}"
            except (ValueError, TypeError):
                batch_label = batch_year

            batch_upload_stats[batch_year] = {
                "batch_label": batch_label,
                "total_students": len(roll_numbers),
                "semesters": semesters,
            }

        cursor.close()
        conn.close()

        return (
            jsonify(
                {
                    "total_students": len(all_students),
                    "branch_breakdown": branch_breakdown,
                    "batch_upload_stats": batch_upload_stats,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/students", methods=["GET"])
@jwt_required()
def get_all_students():
    """Get all registered students (admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, full_name, roll_number, branch, section, created_at FROM students ORDER BY branch, section, roll_number"
        )
        students = serialize_rows(cursor.fetchall())
        cursor.close()
        conn.close()

        return jsonify({"students": students}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/search-student", methods=["GET"])
@jwt_required()
def search_student():
    """Search student by roll number (admin only). Supports partial match."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    roll_number = request.args.get("roll_number", "").strip()
    if not roll_number:
        return jsonify({"error": "Roll number is required"}), 400

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()

        # Try exact match first, then partial
        cursor.execute(
            "SELECT id, full_name, roll_number, branch, section, created_at FROM students WHERE roll_number = %s",
            (roll_number,),
        )
        student = cursor.fetchone()

        if not student:
            # Try partial match
            cursor.execute(
                "SELECT id, full_name, roll_number, branch, section, created_at FROM students WHERE roll_number LIKE %s ORDER BY roll_number LIMIT 10",
                (f"%{roll_number}%",),
            )
            students = serialize_rows(cursor.fetchall())
            cursor.close()
            conn.close()

            if not students:
                return jsonify({"error": "No student found with this roll number"}), 404

            return jsonify({"students": students, "exact": False}), 200

        student = serialize_row(student)
        cursor.close()
        conn.close()

        return jsonify({"student": student, "exact": True}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/student-results/<roll_number>", methods=["GET"])
@jwt_required()
def get_student_results_admin(roll_number):
    """Get results for a specific student with optional year/semester filter (admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    year = request.args.get("year")
    semester = request.args.get("semester")

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()

        # Get student info
        cursor.execute(
            "SELECT id, full_name, roll_number, branch, section FROM students WHERE roll_number = %s",
            (roll_number,),
        )
        student = cursor.fetchone()
        if not student:
            cursor.close()
            conn.close()
            return jsonify({"error": "Student not found"}), 404
        student = serialize_row(student)

        # Get results with filter
        query = "SELECT * FROM results WHERE roll_number = %s"
        params = [roll_number]
        if year and semester:
            query += " AND (year < %s OR (year = %s AND semester <= %s))"
            params.extend([int(year), int(year), int(semester)])
        elif year:
            query += " AND year <= %s"
            params.append(int(year))
        query += " ORDER BY year, semester, subject_code"

        cursor.execute(query, params)
        results = serialize_rows(cursor.fetchall())

        # Get semester summaries
        sq = "SELECT * FROM semester_summary WHERE roll_number = %s"
        sp = [roll_number]
        if year and semester:
            sq += " AND (year < %s OR (year = %s AND semester <= %s))"
            sp.extend([int(year), int(year), int(semester)])
        elif year:
            sq += " AND year <= %s"
            sp.append(int(year))
        sq += " ORDER BY year, semester"

        cursor.execute(sq, sp)
        summaries = serialize_rows(cursor.fetchall())

        cursor.close()
        conn.close()

        # CGPA and pending
        stats = compute_cgpa_and_pending(roll_number, year, semester)

        return jsonify(
            {
                "student": student,
                "results": results,
                "semester_summaries": summaries,
                "cgpa": stats["cgpa"],
                "pending_subjects": stats["pending_subjects"],
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/results", methods=["POST"])
@jwt_required()
def add_result():
    """Add a result for a student (admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json()
    required_fields = [
        "roll_number",
        "subject_name",
        "subject_code",
        "year",
        "semester",
    ]
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == "":
            return jsonify({"error": f"{field} is required"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify student exists
        cursor.execute(
            "SELECT id FROM students WHERE roll_number = %s", (data["roll_number"],)
        )
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Student not found with this roll number"}), 404

        internal = int(data.get("internal_marks", 0))
        external = int(data.get("external_marks", 0))
        total = int(data.get("total_marks", internal + external))
        max_marks = int(data.get("max_marks", 100))
        academic_year = data.get("academic_year", "")

        # Calculate grade and grade_points from total marks
        parsed_grade = data.get("grade", "")
        grade, grade_points = calculate_grade_from_marks(total, parsed_grade)

        # Determine pass/fail status
        status = data.get("status", "")
        if not status:
            status = "FAIL" if grade in ("F", "AB") else "PASS"

        cursor.execute(
            """INSERT INTO results
               (roll_number, year, semester, subject_code, subject_name,
                internal_marks, external_marks, total_marks, max_marks,
                grade_points, grade, status, academic_year)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE
                subject_name=VALUES(subject_name),
                internal_marks=VALUES(internal_marks),
                external_marks=VALUES(external_marks),
                total_marks=VALUES(total_marks),
                max_marks=VALUES(max_marks),
                grade_points=VALUES(grade_points),
                grade=VALUES(grade),
                status=VALUES(status),
                academic_year=VALUES(academic_year)
            """,
            (
                data["roll_number"],
                int(data["year"]),
                int(data["semester"]),
                data["subject_code"],
                data["subject_name"],
                internal,
                external,
                total,
                max_marks,
                grade_points,
                grade,
                status,
                academic_year,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify(
            {"message": "Result added successfully", "grade": grade, "status": status}
        ), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/results/<int:result_id>", methods=["PUT"])
@jwt_required()
def update_result(result_id):
    """Update a specific result (admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json()

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()

        # Check result exists
        cursor.execute("SELECT * FROM results WHERE id = %s", (result_id,))
        result = cursor.fetchone()
        if not result:
            cursor.close()
            conn.close()
            return jsonify({"error": "Result not found"}), 404

        # Build update query dynamically
        updatable = [
            "subject_code",
            "subject_name",
            "internal_marks",
            "external_marks",
            "total_marks",
            "max_marks",
            "grade_points",
            "grade",
            "status",
            "academic_year",
            "year",
            "semester",
        ]

        # If total_marks is being updated, recalculate grade/grade_points/status
        if "total_marks" in data:
            total = int(data["total_marks"])
            parsed_grade = data.get("grade", result.get("grade", ""))
            grade, grade_points = calculate_grade_from_marks(total, parsed_grade)
            data["grade"] = grade
            data["grade_points"] = grade_points
            # Also update status if not explicitly provided
            if "status" not in data:
                data["status"] = "FAIL" if grade in ("F", "AB") else "PASS"

        updates = []
        values = []
        for field in updatable:
            if field in data:
                updates.append(f"{field} = %s")
                values.append(data[field])

        if not updates:
            cursor.close()
            conn.close()
            return jsonify({"error": "No fields to update"}), 400

        values.append(result_id)
        cursor.execute(f"UPDATE results SET {', '.join(updates)} WHERE id = %s", values)
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Result updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/results/<int:result_id>", methods=["DELETE"])
@jwt_required()
def delete_result(result_id):
    """Delete a specific result (admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM results WHERE id = %s", (result_id,))
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({"error": "Result not found"}), 404
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Result deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/semester-summary", methods=["POST"])
@jwt_required()
def upsert_semester_summary():
    """Add/update semester summary (SGPA) for a student (admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json()
    required = ["roll_number", "year", "semester", "sgpa"]
    for field in required:
        if field not in data or data[field] is None or data[field] == "":
            return jsonify({"error": f"{field} is required"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify student exists
        cursor.execute(
            "SELECT id FROM students WHERE roll_number = %s", (data["roll_number"],)
        )
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Student not found"}), 404

        cursor.execute(
            """
            INSERT INTO semester_summary
            (roll_number, year, semester, sgpa, total_marks, total_subjects,
             passed_subjects, failed_subjects, academic_year)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                sgpa=VALUES(sgpa),
                total_marks=VALUES(total_marks),
                total_subjects=VALUES(total_subjects),
                passed_subjects=VALUES(passed_subjects),
                failed_subjects=VALUES(failed_subjects),
                academic_year=VALUES(academic_year)
        """,
            (
                data["roll_number"],
                int(data["year"]),
                int(data["semester"]),
                float(data["sgpa"]),
                int(data.get("total_marks", 0)),
                int(data.get("total_subjects", 0)),
                int(data.get("passed_subjects", 0)),
                int(data.get("failed_subjects", 0)),
                data.get("academic_year", ""),
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Semester summary saved successfully"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/results/<roll_number>", methods=["GET"])
@jwt_required()
def get_results_by_roll(roll_number):
    """Get results for a specific student (admin only) - legacy endpoint."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM results WHERE roll_number = %s ORDER BY year, semester, subject_code",
            (roll_number,),
        )
        results = serialize_rows(cursor.fetchall())
        cursor.close()
        conn.close()

        return jsonify({"results": results}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# CORRECTION REQUESTS
# ============================================================


@app.route("/api/student/correction-request", methods=["POST"])
@jwt_required()
def submit_correction_request():
    """Student submits a correction request with optional file attachment."""
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"error": "Access denied"}), 403

    identity = get_jwt_identity()

    # Support both JSON and multipart/form-data
    if request.content_type and "multipart" in request.content_type:
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        result_id = request.form.get("result_id")
        year = request.form.get("year")
        semester = request.form.get("semester")
        attachment = request.files.get("attachment")
    else:
        data = request.get_json() or {}
        title = data.get("title", "").strip()
        description = data.get("description", "").strip()
        result_id = data.get("result_id")
        year = data.get("year")
        semester = data.get("semester")
        attachment = None

    # Convert year/semester to int if provided
    try:
        year = int(year) if year else None
    except (ValueError, TypeError):
        year = None
    try:
        semester = int(semester) if semester else None
    except (ValueError, TypeError):
        semester = None

    if not title or not description:
        return jsonify({"error": "Title and description are required"}), 400

    attachment_path = None
    if attachment and attachment.filename:
        ext = (
            attachment.filename.rsplit(".", 1)[-1].lower()
            if "." in attachment.filename
            else "pdf"
        )
        safe_name = f"correction_{identity}_{int(time.time())}.{ext}"
        save_path = os.path.join(UPLOAD_FOLDER, safe_name)
        attachment.save(save_path)
        attachment_path = safe_name

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO correction_requests
               (roll_number, result_id, year, semester, title, description, attachment_path)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                identity,
                result_id if result_id else None,
                year,
                semester,
                title,
                description,
                attachment_path,
            ),
        )
        conn.commit()
        req_id = cursor.lastrowid
        cursor.close()
        conn.close()

        return jsonify({"message": "Correction request submitted", "id": req_id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/student/correction-requests", methods=["GET"])
@jwt_required()
def get_student_correction_requests():
    """Get correction requests for logged-in student."""
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"error": "Access denied"}), 403

    identity = get_jwt_identity()
    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM correction_requests WHERE roll_number = %s ORDER BY created_at DESC",
            (identity,),
        )
        requests_list = serialize_rows(cursor.fetchall())
        cursor.close()
        conn.close()

        return jsonify({"requests": requests_list}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/correction-requests", methods=["GET"])
@jwt_required()
def get_all_correction_requests():
    """Get all correction requests (admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cr.*, s.full_name
            FROM correction_requests cr
            JOIN students s ON cr.roll_number = s.roll_number
            ORDER BY
                CASE cr.status WHEN 'PENDING' THEN 0 WHEN 'IN_PROGRESS' THEN 1 ELSE 2 END,
                cr.created_at DESC
        """)
        requests_list = serialize_rows(cursor.fetchall())
        cursor.close()
        conn.close()

        return jsonify({"requests": requests_list}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/correction-requests/<int:req_id>", methods=["PUT"])
@jwt_required()
def update_correction_request(req_id):
    """Update correction request status (admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        updates = []
        values = []
        if "status" in data:
            updates.append("status = %s")
            values.append(data["status"])
        if "admin_remarks" in data:
            updates.append("admin_remarks = %s")
            values.append(data["admin_remarks"])

        if not updates:
            return jsonify({"error": "No fields to update"}), 400

        values.append(req_id)
        cursor.execute(
            f"UPDATE correction_requests SET {', '.join(updates)} WHERE id = %s", values
        )
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({"error": "Correction request not found"}), 404

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Correction request updated"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/correction-requests/count", methods=["GET"])
@jwt_required()
def get_correction_requests_count():
    """Get count of pending correction requests (admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM correction_requests WHERE status IN ('PENDING', 'IN_PROGRESS')"
        )
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        return jsonify({"pending_count": count}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/correction-requests/<int:req_id>/attachment", methods=["GET"])
@jwt_required()
def download_correction_attachment(req_id):
    """Download attachment for a correction request (admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT attachment_path FROM correction_requests WHERE id = %s", (req_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row or not row["attachment_path"]:
            return jsonify({"error": "No attachment found"}), 404

        file_path = os.path.join(UPLOAD_FOLDER, row["attachment_path"])
        if not os.path.exists(file_path):
            return jsonify({"error": "Attachment file not found on server"}), 404

        return send_file(
            file_path, as_attachment=True, download_name=row["attachment_path"]
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/student/notifications/mark-read", methods=["PUT"])
@jwt_required()
def mark_student_notifications_read():
    """Mark all resolved/rejected correction requests as read for the student."""
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"error": "Access denied"}), 403

    identity = get_jwt_identity()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE correction_requests SET student_read = 1 WHERE roll_number = %s AND status IN ('RESOLVED', 'REJECTED') AND student_read = 0",
            (identity,),
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Notifications marked as read"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/student/add-subject", methods=["POST"])
@jwt_required()
def student_add_subject():
    """Student adds a missing subject (code + name only, marks stay 0)."""
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"error": "Access denied"}), 403

    identity = get_jwt_identity()
    data = request.get_json() or {}

    subject_code = data.get("subject_code", "").strip()
    subject_name = data.get("subject_name", "").strip()
    year = data.get("year")
    semester = data.get("semester")

    if not subject_code or not subject_name or not year or not semester:
        return jsonify(
            {"error": "Subject code, subject name, year, and semester are required"}
        ), 400

    try:
        year = int(year)
        semester = int(semester)
    except (ValueError, TypeError):
        return jsonify({"error": "Year and semester must be numbers"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for duplicate
        cursor.execute(
            "SELECT id FROM results WHERE roll_number = %s AND year = %s AND semester = %s AND subject_code = %s",
            (identity, year, semester, subject_code),
        )
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify(
                {"error": "This subject already exists for this semester"}
            ), 409

        cursor.execute(
            """INSERT INTO results
               (roll_number, year, semester, subject_code, subject_name,
                internal_marks, external_marks, total_marks, max_marks,
                grade_points, grade, status, academic_year)
               VALUES (%s, %s, %s, %s, %s, 0, 0, 0, 100, 0, '', 'PASS', '')""",
            (identity, year, semester, subject_code, subject_name),
        )
        conn.commit()
        result_id = cursor.lastrowid
        cursor.close()
        conn.close()

        return jsonify({"message": "Subject added successfully", "id": result_id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# PHASE 3: UPLOAD TRACKING
# ============================================================


@app.route("/api/admin/uploads", methods=["GET"])
@jwt_required()
def get_all_uploads():
    """Get all upload history records (admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT uh.*, s.full_name, s.branch, s.section
            FROM upload_history uh
            JOIN students s ON uh.roll_number = s.roll_number
            WHERE uh.status = 'CONFIRMED'
            ORDER BY uh.upload_time DESC
        """)
        uploads = serialize_rows(cursor.fetchall())
        cursor.close()
        conn.close()

        return jsonify({"uploads": uploads}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/uploads/<int:upload_id>", methods=["DELETE"])
@jwt_required()
def delete_upload(upload_id):
    """Delete an upload and cascade-delete all results/summaries from it."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    try:
        import json as json_lib

        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()

        # Get upload record
        cursor.execute("SELECT * FROM upload_history WHERE id = %s", (upload_id,))
        upload = cursor.fetchone()
        if not upload:
            cursor.close()
            conn.close()
            return jsonify({"error": "Upload not found"}), 404

        roll_number = upload["roll_number"]
        year_sem_data = upload.get("year_semester_data", "[]")

        # Parse year_semester_data to find which results/summaries to delete
        try:
            sem_info = json_lib.loads(year_sem_data) if year_sem_data else []
        except (json_lib.JSONDecodeError, TypeError):
            sem_info = []

        results_deleted = 0
        summaries_deleted = 0

        for entry in sem_info:
            y = entry.get("year", 0)
            s = entry.get("semester", 0)
            subject_codes = entry.get("subject_codes", [])

            if y and s and subject_codes:
                # Delete specific results by subject code
                for code in subject_codes:
                    if code.strip():
                        cursor.execute(
                            "DELETE FROM results WHERE roll_number = %s AND year = %s AND semester = %s AND subject_code = %s",
                            (roll_number, y, s, code.strip()),
                        )
                        results_deleted += cursor.rowcount

                # Delete semester summary if no more results exist for this year/sem
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM results WHERE roll_number = %s AND year = %s AND semester = %s",
                    (roll_number, y, s),
                )
                remaining = cursor.fetchone()
                if remaining and remaining["cnt"] == 0:
                    cursor.execute(
                        "DELETE FROM semester_summary WHERE roll_number = %s AND year = %s AND semester = %s",
                        (roll_number, y, s),
                    )
                    summaries_deleted += cursor.rowcount

        # Mark upload as deleted
        cursor.execute(
            "UPDATE upload_history SET status = 'DELETED' WHERE id = %s", (upload_id,)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify(
            {
                "message": f"Upload deleted. Removed {results_deleted} results and {summaries_deleted} semester summaries.",
                "results_deleted": results_deleted,
                "summaries_deleted": summaries_deleted,
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# PHASE 3: STUDENT MANAGEMENT (FILTERS + DELETE)
# ============================================================


@app.route("/api/admin/students/filtered", methods=["GET"])
@jwt_required()
def get_filtered_students():
    """Get students with optional branch/section filters (admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    branch = request.args.get("branch", "").strip()
    section = request.args.get("section", "").strip()
    search = request.args.get("search", "").strip()

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()

        query = "SELECT id, full_name, roll_number, branch, section, created_at FROM students WHERE 1=1"
        params = []

        if branch:
            query += " AND branch = %s"
            params.append(branch)
        if section:
            query += " AND section = %s"
            params.append(section)
        if search:
            query += " AND (roll_number LIKE %s OR full_name LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY branch, section, roll_number"

        cursor.execute(query, params)
        students = serialize_rows(cursor.fetchall())
        cursor.close()
        conn.close()

        return jsonify({"students": students, "count": len(students)}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/students/<roll_number>", methods=["DELETE"])
@jwt_required()
def delete_student(roll_number):
    """Delete a single student account (admin only). Cascades to results/summaries."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM students WHERE roll_number = %s", (roll_number,))
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({"error": "Student not found"}), 404

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": f"Student {roll_number} deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/students/bulk-delete", methods=["POST"])
@jwt_required()
def bulk_delete_students():
    """Bulk delete student accounts (admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json()
    roll_numbers = data.get("roll_numbers", [])

    if not roll_numbers:
        return jsonify({"error": "No roll numbers provided"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        deleted = 0
        for rn in roll_numbers:
            cursor.execute("DELETE FROM students WHERE roll_number = %s", (rn,))
            deleted += cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify(
            {
                "message": f"Successfully deleted {deleted} student(s)",
                "deleted": deleted,
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# PHASE 3: STAFF/USER MANAGEMENT
# ============================================================


@app.route("/api/admin/users", methods=["GET"])
@jwt_required()
def get_admin_users():
    """Get all admin/staff users (super_admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, full_name, role, permissions, created_at FROM admins ORDER BY role, username"
        )
        users = serialize_rows(cursor.fetchall())
        cursor.close()
        conn.close()

        return jsonify({"users": users}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/create-user", methods=["POST"])
@jwt_required()
def create_admin_user():
    """Create a new staff/admin user (super_admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    # Only super_admin can create users
    if claims.get("admin_role") not in ("super_admin",):
        return jsonify({"error": "Only super admin can create user accounts"}), 403

    data = request.get_json()
    required = ["username", "password", "full_name", "role"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    if data["role"] not in ("admin", "staff"):
        return jsonify({"error": "Invalid role. Must be 'admin' or 'staff'"}), 400

    if len(data["password"]) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if username exists
        cursor.execute("SELECT id FROM admins WHERE username = %s", (data["username"],))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Username already exists"}), 409

        hashed_password = generate_password_hash(data["password"])
        permissions = data.get("permissions", "")

        cursor.execute(
            "INSERT INTO admins (username, password, full_name, role, permissions) VALUES (%s, %s, %s, %s, %s)",
            (
                data["username"],
                hashed_password,
                data["full_name"],
                data["role"],
                permissions,
            ),
        )
        conn.commit()
        user_id = cursor.lastrowid
        cursor.close()
        conn.close()

        return jsonify(
            {
                "message": f"User '{data['username']}' created successfully",
                "id": user_id,
            }
        ), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def delete_admin_user(user_id):
    """Delete an admin/staff user (super_admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    if claims.get("admin_role") not in ("super_admin",):
        return jsonify({"error": "Only super admin can delete user accounts"}), 403

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()

        # Prevent deleting the default admin
        cursor.execute("SELECT username, role FROM admins WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return jsonify({"error": "User not found"}), 404

        if user["username"] == "admin":
            cursor.close()
            conn.close()
            return jsonify({"error": "Cannot delete the default admin account"}), 403

        cursor.execute("DELETE FROM admins WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "User deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
@jwt_required()
def update_admin_user(user_id):
    """Update an admin/staff user's role/permissions (super_admin only)."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    if claims.get("admin_role") not in ("super_admin",):
        return jsonify({"error": "Only super admin can update user accounts"}), 403

    data = request.get_json()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        updates = []
        values = []
        if "full_name" in data:
            updates.append("full_name = %s")
            values.append(data["full_name"])
        if "role" in data and data["role"] in ("admin", "staff"):
            updates.append("role = %s")
            values.append(data["role"])
        if "permissions" in data:
            updates.append("permissions = %s")
            values.append(data["permissions"])

        if not updates:
            cursor.close()
            conn.close()
            return jsonify({"error": "No fields to update"}), 400

        values.append(user_id)
        cursor.execute(f"UPDATE admins SET {', '.join(updates)} WHERE id = %s", values)
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({"error": "User not found"}), 404

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "User updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# PHASE 3: PASSWORD MANAGEMENT
# ============================================================


@app.route("/api/admin/change-password", methods=["PUT"])
@jwt_required()
def admin_change_password():
    """Admin changes their own password."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    identity = get_jwt_identity()
    data = request.get_json()

    if not data.get("current_password") or not data.get("new_password"):
        return jsonify({"error": "Current password and new password are required"}), 400

    if len(data["new_password"]) < 6:
        return jsonify({"error": "New password must be at least 6 characters"}), 400

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM admins WHERE username = %s", (identity,))
        admin = cursor.fetchone()

        if not admin or not check_password_hash(
            admin["password"], data["current_password"]
        ):
            cursor.close()
            conn.close()
            return jsonify({"error": "Current password is incorrect"}), 401

        hashed = generate_password_hash(data["new_password"])
        cursor.execute(
            "UPDATE admins SET password = %s WHERE username = %s", (hashed, identity)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Password changed successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/student/change-password", methods=["PUT"])
@jwt_required()
def student_change_password():
    """Student changes their own password."""
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"error": "Access denied"}), 403

    identity = get_jwt_identity()
    data = request.get_json()

    if not data.get("current_password") or not data.get("new_password"):
        return jsonify({"error": "Current password and new password are required"}), 400

    if len(data["new_password"]) < 6:
        return jsonify({"error": "New password must be at least 6 characters"}), 400

    try:
        conn = get_db_connection(use_dict=True)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM students WHERE roll_number = %s", (identity,))
        student = cursor.fetchone()

        if not student or not check_password_hash(
            student["password"], data["current_password"]
        ):
            cursor.close()
            conn.close()
            return jsonify({"error": "Current password is incorrect"}), 401

        hashed = generate_password_hash(data["new_password"])
        cursor.execute(
            "UPDATE students SET password = %s WHERE roll_number = %s",
            (hashed, identity),
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Password changed successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/reset-student-password", methods=["PUT"])
@jwt_required()
def admin_reset_student_password():
    """Admin resets a student's password."""
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json()

    if not data.get("roll_number") or not data.get("new_password"):
        return jsonify({"error": "Roll number and new password are required"}), 400

    if len(data["new_password"]) < 6:
        return jsonify({"error": "New password must be at least 6 characters"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM students WHERE roll_number = %s", (data["roll_number"],)
        )
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Student not found"}), 404

        hashed = generate_password_hash(data["new_password"])
        cursor.execute(
            "UPDATE students SET password = %s WHERE roll_number = %s",
            (hashed, data["roll_number"]),
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify(
            {
                "message": f"Password for {data['roll_number']} has been reset successfully"
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "database": str(e)}), 503


if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Starting Flask application...")
    app.run(host="0.0.0.0", port=5000, debug=False)
