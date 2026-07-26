-- Hospital Appointment Management System: unified MySQL Workbench setup
--
-- Run this script while connected as a user that can alter `flask_crud`.
-- It NEVER drops tables or deletes existing hospital records.
-- Existing users, doctors, administrators and appointments remain in place.

CREATE DATABASE IF NOT EXISTS flask_crud
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE flask_crud;

-- Extra contact data belongs only to patients.  Login credentials remain in
-- `users`; passwords are intentionally not selected by the reporting views.
CREATE TABLE IF NOT EXISTS patient_profiles (
    patient_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    phone VARCHAR(30) NULL,
    date_of_birth DATE NULL,
    gender VARCHAR(30) NULL,
    address VARCHAR(255) NULL,
    emergency_contact_name VARCHAR(100) NULL,
    emergency_contact_phone VARCHAR(30) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_patient_profiles_user UNIQUE (user_id),
    CONSTRAINT fk_patient_profiles_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- One record per authentication action.  The Flask app must INSERT here when
-- a login, logout, failed attempt, reset or lockout occurs.
CREATE TABLE IF NOT EXISTS login_events (
    event_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    username VARCHAR(100) NOT NULL,
    event_type ENUM('login_success', 'login_failure', 'logout',
                    'password_reset', 'account_locked') NOT NULL,
    ip_address VARCHAR(45) NULL,
    user_agent VARCHAR(255) NULL,
    device_type VARCHAR(50) NULL,
    location VARCHAR(100) NULL,
    event_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes VARCHAR(255) NULL,
    KEY idx_login_events_user_time (user_id, event_time),
    KEY idx_login_events_type_time (event_type, event_time),
    CONSTRAINT fk_login_events_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS account_lockouts (
    lockout_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    username VARCHAR(100) NOT NULL,
    locked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    unlock_at TIMESTAMP NOT NULL,
    reason VARCHAR(255) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    KEY idx_account_lockouts_user_active (user_id, is_active),
    CONSTRAINT fk_account_lockouts_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create a profile placeholder for every patient already registered.
INSERT INTO patient_profiles (user_id)
SELECT u.id
FROM users AS u
LEFT JOIN patient_profiles AS p ON p.user_id = u.id
WHERE u.role = 'user' AND p.user_id IS NULL;

-- Optional one-time import of your previous standalone login log.  This is
-- safe to run only once; remove this block if you do not want its sample rows.
-- INSERT INTO login_events
--     (user_id, username, event_type, ip_address, user_agent, device_type,
--      location, event_time, notes)
-- SELECT u.id, e.username, e.event_type, e.ip_address, e.user_agent,
--        e.device_type, e.location, e.event_time, e.notes
-- FROM login_events_db.login_events AS e
-- LEFT JOIN users AS u ON u.id = e.user_id OR u.email = e.username;

-- Workbench-friendly reporting views.  They intentionally omit password and
-- TOTP-secret fields, so browsing the database cannot expose credentials.
CREATE OR REPLACE VIEW vw_all_accounts AS
SELECT id, name, email, role, department, specialty, bio, created_at
FROM users;

CREATE OR REPLACE VIEW vw_patients AS
SELECT u.id AS patient_user_id, u.name AS patient_name, u.email,
       p.phone, p.date_of_birth, p.gender, p.address,
       p.emergency_contact_name, p.emergency_contact_phone,
       COUNT(a.id) AS total_appointments,
       MAX(a.appointment_date) AS latest_appointment_date,
       u.created_at AS registered_at
FROM users AS u
LEFT JOIN patient_profiles AS p ON p.user_id = u.id
LEFT JOIN appointments AS a ON a.user_id = u.id
WHERE u.role = 'user'
GROUP BY u.id, u.name, u.email, p.phone, p.date_of_birth, p.gender, p.address,
         p.emergency_contact_name, p.emergency_contact_phone, u.created_at;

CREATE OR REPLACE VIEW vw_doctors AS
SELECT id AS doctor_user_id, name AS doctor_name, email, department,
       specialty, bio, created_at
FROM users
WHERE role = 'doctor';

CREATE OR REPLACE VIEW vw_administrators AS
SELECT id AS admin_user_id, name AS admin_name, email, created_at
FROM users
WHERE role = 'admin';

CREATE OR REPLACE VIEW vw_login_history AS
SELECT e.event_id, e.event_time, e.event_type, e.username,
       u.name AS account_name, u.email, u.role,
       e.ip_address, e.device_type, e.location, e.notes
FROM login_events AS e
LEFT JOIN users AS u ON u.id = e.user_id
ORDER BY e.event_time DESC;

CREATE OR REPLACE VIEW vw_patient_appointments AS
SELECT a.id AS appointment_id, u.name AS patient_name, u.email AS patient_email,
       a.doctor_name, a.department, a.appointment_date, a.appointment_time,
       a.status, a.cancellation_reason, a.created_at
FROM appointments AS a
JOIN users AS u ON u.id = a.user_id
ORDER BY a.appointment_date DESC, a.appointment_time DESC;

-- Run these in Workbench after executing the script:
-- SELECT * FROM vw_all_accounts;
-- SELECT * FROM vw_patients;
-- SELECT * FROM vw_doctors;
-- SELECT * FROM vw_administrators;
-- SELECT * FROM vw_login_history;
-- SELECT * FROM vw_patient_appointments;
