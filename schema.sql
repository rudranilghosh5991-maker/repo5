CREATE DATABASE IF NOT EXISTS college_portal
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE college_portal;

CREATE TABLE IF NOT EXISTS students (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  emp_id VARCHAR(50) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  student_name VARCHAR(120) NOT NULL,
  department VARCHAR(120) NOT NULL DEFAULT '',
  program VARCHAR(120) NOT NULL DEFAULT '',
  academic_year VARCHAR(30) NOT NULL DEFAULT '',
  email VARCHAR(254) NOT NULL DEFAULT '',
  phone VARCHAR(30) NOT NULL DEFAULT '',
  address VARCHAR(500) NOT NULL DEFAULT '',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_students_emp_id (emp_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS results (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  student_id BIGINT UNSIGNED NOT NULL,
  course_code VARCHAR(30) NOT NULL,
  course_name VARCHAR(160) NOT NULL,
  semester VARCHAR(50) NOT NULL,
  academic_year VARCHAR(30) NOT NULL DEFAULT '',
  grade VARCHAR(20) NOT NULL,
  published_at DATE NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_results_student_published (student_id, published_at),
  CONSTRAINT fk_results_student
    FOREIGN KEY (student_id) REFERENCES students (id)
    ON DELETE CASCADE
) ENGINE=InnoDB;
