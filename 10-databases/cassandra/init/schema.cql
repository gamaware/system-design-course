-- Create keyspace with replication factor 3
CREATE KEYSPACE IF NOT EXISTS university
    WITH replication = {'class': 'NetworkTopologyStrategy', 'dc1': 3};

USE university;

-- Students table (partition by major for efficient queries)
CREATE TABLE IF NOT EXISTS students (
    major text,
    student_id uuid,
    name text,
    email text,
    PRIMARY KEY (major, student_id)
);

-- Courses table (partition by code)
CREATE TABLE IF NOT EXISTS courses (
    code text PRIMARY KEY,
    title text,
    capacity int,
    enrolled int
);

-- Enrollments by student (good partition key)
CREATE TABLE IF NOT EXISTS enrollments_by_student (
    student_id uuid,
    course_code text,
    course_title text,
    enrolled_at timestamp,
    PRIMARY KEY (student_id, course_code)
);

-- Access log with BAD partition key (all data in one partition)
CREATE TABLE IF NOT EXISTS access_log_bad (
    log_type text,
    accessed_at timestamp,
    student_name text,
    resource text,
    PRIMARY KEY (log_type, accessed_at)
);

-- Access log with GOOD partition key (distributed by date)
CREATE TABLE IF NOT EXISTS access_log_good (
    day text,
    accessed_at timestamp,
    student_name text,
    resource text,
    PRIMARY KEY (day, accessed_at)
);

-- Seed students
INSERT INTO students (major, student_id, name, email)
    VALUES ('Computer Science', uuid(), 'Alice Johnson', 'alice@university.edu');
INSERT INTO students (major, student_id, name, email)
    VALUES ('Mathematics', uuid(), 'Bob Smith', 'bob@university.edu');
INSERT INTO students (major, student_id, name, email)
    VALUES ('Computer Science', uuid(), 'Carol Davis', 'carol@university.edu');
INSERT INTO students (major, student_id, name, email)
    VALUES ('Physics', uuid(), 'David Lee', 'david@university.edu');
INSERT INTO students (major, student_id, name, email)
    VALUES ('Computer Science', uuid(), 'Eva Martinez', 'eva@university.edu');
INSERT INTO students (major, student_id, name, email)
    VALUES ('Mathematics', uuid(), 'Frank Wilson', 'frank@university.edu');
INSERT INTO students (major, student_id, name, email)
    VALUES ('Biology', uuid(), 'Grace Kim', 'grace@university.edu');
INSERT INTO students (major, student_id, name, email)
    VALUES ('Computer Science', uuid(), 'Henry Brown', 'henry@university.edu');
INSERT INTO students (major, student_id, name, email)
    VALUES ('Physics', uuid(), 'Iris Chen', 'iris@university.edu');
INSERT INTO students (major, student_id, name, email)
    VALUES ('Mathematics', uuid(), 'Jack Taylor', 'jack@university.edu');

-- Seed courses
INSERT INTO courses (code, title, capacity, enrolled)
    VALUES ('CS101', 'Intro to Programming', 30, 4);
INSERT INTO courses (code, title, capacity, enrolled)
    VALUES ('CS201', 'Data Structures', 25, 2);
INSERT INTO courses (code, title, capacity, enrolled)
    VALUES ('MATH101', 'Calculus I', 35, 2);
INSERT INTO courses (code, title, capacity, enrolled)
    VALUES ('PHYS101', 'Physics I', 30, 2);
