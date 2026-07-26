# Hospital Appointment Management System (sandyHUb)

![Python](https://img.shields.io/badge/Python-3-blue)
![Flask](https://img.shields.io/badge/Flask-web%20framework-black)
![MySQL](https://img.shields.io/badge/MySQL-database-orange)
![Tests](https://img.shields.io/badge/tests-unittest-green)
![License](https://img.shields.io/badge/license-unspecified-lightgrey)

A Flask and MySQL web application for patients to sign in, manage their
profile, and create, view, edit, or delete hospital appointments. Doctors
can view their own schedule, and a single administrator can review users,
approve or cancel appointments, and provision doctor accounts.

This project was developed for the ST5041CMD coursework and demonstrates a
complete client/server web application using HTML, CSS, JavaScript, Jinja2,
Flask, Python, MySQL, authentication, sessions, security controls, and tests.

## Contents

- [Implemented Features](#implemented-features)
- [Technologies](#technologies)
- [Project Structure](#project-structure)
- [Database Design](#database-design)
- [Setup](#setup)
- [Environment Variables](#environment-variables)
- [Run the Application](#run-the-application)
- [Run Tests](#run-tests)
- [Security Controls](#security-controls)
- [Screenshots](#screenshots)
- [Repository and Demo](#repository-and-demo)
- [Known Limitations](#known-limitations)
- [Future Improvements](#future-improvements)

## Implemented Features

1. Role-based login for patients, doctors, and the administrator.
2. Automatic patient-account creation for a new email address.
3. Secure password hashing; plaintext passwords are never stored.
4. Login rate limiting after repeated failed attempts.
5. Pre-seeded specialist doctors across six departments.
6. Administrator-created doctor accounts, including custom doctors and departments.
7. Admin user search with account name, email, role, and creation date.
8. Safe admin password resets: a temporary password is shown once and then only its hash is stored.
9. Admin account deletion for non-administrator users.
10. Patient appointment booking with fixed daily time slots.
11. Live availability checks that hide booked time slots.
12. Doctor-and-department matching enforced in the browser and on the server.
13. Patient appointment view, edit, and delete controls with ownership checks.
14. Administrator appointment approval, cancellation, pagination, search, and CSV export.
15. Doctor-only read-only schedules showing that doctor’s active appointments.
16. Profile updates with current-password verification before a password change.
17. CSRF protection, parameterized SQL queries, role checks, and custom error pages.
18. Responsive templates with a mobile navigation menu and accessible form feedback.
19. Token-based "forgot password" flow: a one-time link is generated and delivered through an admin-visible Notification Log (no real mail server needed), and the confirmation message never reveals whether the email is registered.
20. Optional TOTP-based two-factor authentication for the administrator account, with QR-code enrollment and verification before it's enabled.
21. Homepage stats bar highlighting key numbers (patients served, specialist doctors, on-time rate, emergency support, experience, and clinic locations).

## Technologies

- Python 3
- Flask
- Jinja2
- Werkzeug security utilities
- MySQL
- PyMySQL
- HTML5
- CSS3
- JavaScript
- Python `unittest`
- Git and GitHub

## Project Structure

```text
Hospital-Appointment-Management-System/
├── apps/
│   ├── controllers/
│   │   └── authController.py
│   ├── routes/
│   │   └── authRoutes.py
│   ├── static/
│   │   ├── css/
│   │   ├── images/
│   │   └── js/
│   ├── templates/
│   │   ├── errors/
│   │   └── *.html
│   ├── auth.py
│   ├── database.py
│   └── __init__.py
├── tests/
├── .env.example
├── config.py
├── hospital_workbench_database.sql
├── requirements.txt
└── run.py
```

## Database Design

### `users`

- `id` — primary key
- `name`
- `email` — unique, indexed by the unique constraint
- `password` — Werkzeug password hash
- `role`
- `created_at`

### `appointments`

- `id` — primary key
- `user_id` — foreign key to `users.id` with `ON DELETE CASCADE`
- `doctor_name`
- `department`
- `appointment_date`
- `appointment_time`
- `status`
- `created_at`
- `updated_at`

Additional indexes support user lookups, status filtering, scheduling, role
filtering, and chronological sorting.

## Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/sandipmahat/Hospital-Appointment-Management-System.git
   cd Hospital-Appointment-Management-System
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and set secure local values. Environment
   variables can also be configured directly in the terminal or IDE.

5. Create a MySQL user with permission to create and use the configured
   database. The application creates the database and required tables when
   `INIT_DB=true`.

6. Confirm the configured MySQL service is running before starting the Flask
   app. If you only need to preview static pages, set `INIT_DB=false` while
   developing locally.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Flask session signing key |
| `MYSQL_HOST` | MySQL server hostname |
| `MYSQL_PORT` | MySQL server port |
| `MYSQL_USER` | MySQL username |
| `MYSQL_PASSWORD` | MySQL password |
| `MYSQL_DATABASE` | Application database name |
| `SESSION_COOKIE_SECURE` | Set `true` when using HTTPS |
| `SESSION_LIFETIME_MINUTES` | Login session duration |
| `INIT_DB` | Automatically create/update tables |
| `CSRF_ENABLED` | Enable CSRF validation |
| `ADMIN_EMAIL` | Email for the single seeded administrator account |
| `ADMIN_PASSWORD` | Initial password for the seeded administrator account (stored as a hash) |
| `DOCTOR_SEED_PASSWORD` | Initial password for all six seeded doctor accounts (stored as a hash) |

Never commit a real `.env` file or production credentials.

## Run the Application

```bash
python run.py
```

Then open `http://127.0.0.1:5000`.

With `INIT_DB=true`, first startup seeds one administrator account (using
`ADMIN_EMAIL`/`ADMIN_PASSWORD`) and six doctor accounts (using
`DOCTOR_SEED_PASSWORD`, one per doctor in `DOCTOR_PROFILES`) if they don't
already exist. Change these seeded credentials before any real deployment.

## Run Tests

```bash
python -m unittest discover -s tests -v
```

The tests disable live database initialization and use mocks, so they do not
modify a developer's MySQL data.

## Security Controls

- Passwords are hashed and checked with Werkzeug.
- Session cookies are HTTP-only and use `SameSite=Lax`.
- Secure cookies can be enabled in HTTPS environments.
- CSRF tokens protect POST, PUT, PATCH, and DELETE operations.
- SQL values are passed as parameters.
- Appointment edit/delete queries include the authenticated user's ID.
- Administrator routes use role-based access decorators.
- Jinja autoescaping protects rendered user data.
- Secrets and database credentials are loaded from environment variables.
- Optional TOTP two-factor authentication for the administrator account (`pyotp`), with a verification step before it can be enabled or disabled.
- Password reset tokens expire after a configurable TTL and are single-use, and the request flow gives an identical response regardless of whether the email exists, preventing account enumeration.

## Screenshots

Add screenshots here before submission:

- Home page: `docs/screenshots/home.png`
- Login page: `docs/screenshots/login.png`
- Appointment management: `docs/screenshots/appointments.png`
- Administrator dashboard: `docs/screenshots/dashboard.png`

## Repository and Demo

- GitHub: https://github.com/sandipmahat/Hospital-Appointment-Management-System
- YouTube demo: https://youtu.be/slcRqAq52u4

## Known Limitations

- The doctor and department roster is a controlled application list
  (`DOCTOR_PROFILES` in `authController.py`) rather than a fully managed
  database table with its own CRUD screens; the admin panel can only create
  login accounts for the six doctors already in that list.
- Email delivery, SMS reminders, and real telemedicine are demonstration
  features only.
- No real mail server is configured, so password reset links are delivered
  through the internal Notification Log (admin-visible) rather than an
  actual inbox.
- The project uses direct PyMySQL queries instead of an ORM or migration tool.
- Production deployment and HTTPS configuration are outside the coursework
  development setup.

## Future Improvements

- Normalize doctors and departments into dedicated managed database tables.
- Add password reset emails and account verification.
- Add search and reporting to the administrator dashboard.
- Add database migrations and broader integration/browser tests.
- Deploy using a production WSGI server and HTTPS.
