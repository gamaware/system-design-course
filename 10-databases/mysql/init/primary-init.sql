-- University enrollment schema and seed data
CREATE DATABASE IF NOT EXISTS university;
USE university;

CREATE TABLE students (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    major VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE courses (
    course_id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(10) NOT NULL UNIQUE,
    title VARCHAR(100) NOT NULL,
    capacity INT NOT NULL DEFAULT 30,
    enrolled INT NOT NULL DEFAULT 0
);

CREATE TABLE enrollments (
    enrollment_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    course_id INT NOT NULL,
    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id),
    UNIQUE KEY unique_enrollment (student_id, course_id)
);

-- Seed students
INSERT INTO students (name, email, major) VALUES
('Alice Johnson', 'alice@university.edu', 'Computer Science'),
('Bob Smith', 'bob@university.edu', 'Mathematics'),
('Carol Davis', 'carol@university.edu', 'Computer Science'),
('David Lee', 'david@university.edu', 'Physics'),
('Eva Martinez', 'eva@university.edu', 'Computer Science'),
('Frank Wilson', 'frank@university.edu', 'Mathematics'),
('Grace Kim', 'grace@university.edu', 'Biology'),
('Henry Brown', 'henry@university.edu', 'Computer Science'),
('Iris Chen', 'iris@university.edu', 'Physics'),
('Jack Taylor', 'jack@university.edu', 'Mathematics');

-- Seed courses
INSERT INTO courses (code, title, capacity, enrolled) VALUES
('CS101', 'Intro to Programming', 30, 4),
('CS201', 'Data Structures', 25, 2),
('MATH101', 'Calculus I', 35, 2),
('PHYS101', 'Physics I', 30, 2);

-- Seed enrollments
INSERT INTO enrollments (student_id, course_id) VALUES
(1, 1), (3, 1), (5, 1), (8, 1),
(1, 2), (3, 2),
(2, 3), (6, 3),
(4, 4), (9, 4);

-- Create a large table for indexing exercise (no index on purpose)
CREATE TABLE access_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    resource VARCHAR(100) NOT NULL,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert 10,000 rows for indexing demo
DELIMITER //
CREATE PROCEDURE seed_access_log()
BEGIN
    DECLARE i INT DEFAULT 0;
    WHILE i < 10000 DO
        INSERT INTO access_log (student_id, resource, accessed_at)
        VALUES (
            FLOOR(1 + RAND() * 10),
            CONCAT('resource-', FLOOR(1 + RAND() * 50)),
            DATE_SUB(NOW(), INTERVAL FLOOR(RAND() * 365) DAY)
        );
        SET i = i + 1;
    END WHILE;
END //
DELIMITER ;

CALL seed_access_log();
DROP PROCEDURE seed_access_log;
