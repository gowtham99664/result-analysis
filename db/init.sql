CREATE DATABASE IF NOT EXISTS result_analysis;
USE result_analysis;

CREATE TABLE IF NOT EXISTS students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    roll_number VARCHAR(50) NOT NULL UNIQUE,
    branch ENUM('CSE', 'ECE', 'EEE', 'MECH') NOT NULL,
    section ENUM('A', 'B', 'C') NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Admin/Staff table with role-based access
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) DEFAULT '',
    role ENUM('super_admin', 'admin', 'staff') DEFAULT 'admin',
    permissions TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Results table: each row = one subject in one semester
CREATE TABLE IF NOT EXISTS results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    roll_number VARCHAR(50) NOT NULL,
    year INT NOT NULL COMMENT 'Year: 1=I, 2=II, 3=III, 4=IV',
    semester INT NOT NULL COMMENT 'Semester: 1=I, 2=II',
    subject_code VARCHAR(50) NOT NULL,
    subject_name VARCHAR(255) NOT NULL,
    internal_marks INT DEFAULT 0,
    external_marks INT DEFAULT 0,
    total_marks INT DEFAULT 0,
    max_marks INT NOT NULL DEFAULT 100,
    grade_points DECIMAL(4,2) DEFAULT 0,
    grade VARCHAR(5) DEFAULT '',
    status ENUM('PASS', 'FAIL', 'AB', 'MP') DEFAULT 'PASS' COMMENT 'AB=Absent, MP=Malpractice',
    academic_year VARCHAR(20) NOT NULL DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (roll_number) REFERENCES students(roll_number) ON DELETE CASCADE,
    UNIQUE KEY unique_result (roll_number, year, semester, subject_code)
);

-- Semester summary: stores SGPA per year-semester for each student
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
);

-- Correction requests from students
CREATE TABLE IF NOT EXISTS correction_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    roll_number VARCHAR(50) NOT NULL,
    result_id INT,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    attachment_path VARCHAR(500) DEFAULT NULL,
    status ENUM('PENDING', 'REVIEWED', 'RESOLVED', 'REJECTED') DEFAULT 'PENDING',
    admin_remarks TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (roll_number) REFERENCES students(roll_number) ON DELETE CASCADE,
    FOREIGN KEY (result_id) REFERENCES results(id) ON DELETE SET NULL
);

-- Upload history for tracking memo uploads
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
);

-- Insert default admin (password will be hashed by the backend on first run)
-- Placeholder: the backend init script will handle this
