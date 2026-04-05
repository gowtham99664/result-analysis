import os
import time
import pymysql
from werkzeug.security import generate_password_hash

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "db"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "spmvv_root_2024"),
    "database": os.environ.get("DB_NAME", "result_analysis"),
}


def wait_for_db():
    """Wait for database to be ready."""
    max_retries = 60
    for attempt in range(max_retries):
        try:
            conn = pymysql.connect(**DB_CONFIG)
            conn.close()
            print("Database is ready!")
            return True
        except pymysql.Error:
            print(f"Waiting for database... attempt {attempt + 1}/{max_retries}")
            time.sleep(2)
    print("Could not connect to database!")
    return False


def init_db():
    """Initialize database with tables and default admin."""
    if not wait_for_db():
        return

    conn = pymysql.connect(**DB_CONFIG)
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
            credits INT DEFAULT 3,
            internal_marks INT DEFAULT 0,
            external_marks INT DEFAULT 0,
            total_marks INT DEFAULT 0,
            max_marks INT NOT NULL DEFAULT 100,
            grade_points DECIMAL(4,2) DEFAULT 0,
            grade VARCHAR(5) DEFAULT '',
            status ENUM('PASS', 'FAIL', 'AB', 'MP') DEFAULT 'PASS',
            attempts INT DEFAULT 1,
            display_order INT DEFAULT 0,
            academic_year VARCHAR(20) NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (roll_number) REFERENCES students(roll_number) ON DELETE CASCADE,
            UNIQUE KEY unique_result (roll_number, year, semester, subject_code)
        )
    """)

    # Migration for existing results tables: add credits and attempts columns
    try:
        cursor.execute(
            "ALTER TABLE results ADD COLUMN credits INT DEFAULT 3 AFTER subject_name"
        )
    except Exception:
        pass
    try:
        cursor.execute(
            "ALTER TABLE results ADD COLUMN attempts INT DEFAULT 1 AFTER status"
        )
    except Exception:
        pass
    try:
        cursor.execute(
            "ALTER TABLE results ADD COLUMN display_order INT DEFAULT 0 AFTER attempts"
        )
    except Exception:
        pass

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
            year INT DEFAULT NULL,
            semester INT DEFAULT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            attachment_path VARCHAR(500) DEFAULT NULL,
            status ENUM('PENDING', 'IN_PROGRESS', 'REVIEWED', 'RESOLVED', 'REJECTED') DEFAULT 'PENDING',
            admin_remarks TEXT DEFAULT NULL,
            student_read TINYINT(1) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (roll_number) REFERENCES students(roll_number) ON DELETE CASCADE,
            FOREIGN KEY (result_id) REFERENCES results(id) ON DELETE SET NULL
        )
    """)

    # Migration for existing correction_requests tables
    try:
        cursor.execute(
            "ALTER TABLE correction_requests ADD COLUMN student_read TINYINT(1) DEFAULT 0"
        )
    except Exception:
        pass
    try:
        cursor.execute(
            "ALTER TABLE correction_requests MODIFY COLUMN status ENUM('PENDING', 'IN_PROGRESS', 'REVIEWED', 'RESOLVED', 'REJECTED') DEFAULT 'PENDING'"
        )
    except Exception:
        pass
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
        print("Default admin account created (username: admin, password: admin123)")
    else:
        # Ensure existing admin has super_admin role
        cursor.execute(
            "UPDATE admins SET role = 'super_admin' WHERE username = 'admin' AND (role IS NULL OR role = 'admin')"
        )

    conn.commit()
    cursor.close()
    conn.close()
    print("Database initialization complete!")


if __name__ == "__main__":
    init_db()
