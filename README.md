# Hospital Appointment Management System

A Flask and MySQL web application for patients to create accounts, sign in,
manage their profile, and create, view, edit, or delete hospital appointments.
Administrators can review users and approve or cancel appointment requests.

This project was developed for the ST5041CMD coursework and demonstrates a
complete client/server web application using HTML, CSS, JavaScript, Jinja2,
Flask, Python, MySQL, authentication, sessions, security controls, and tests.

## Features

- User registration with server-side validation and Werkzeug password hashing
- Login, logout, secure sessions, and protected routes
- Role-based administrator access
- Patient profile management and password changes
- Full appointment CRUD:
  - Create an appointment
  - View personal appointments
  - Edit an owned appointment
  - Delete an owned appointment
- Administrator appointment approval and cancellation
- Responsive Jinja2 templates and reusable static CSS/JavaScript
- Flash messages and custom 403, 404, and 500 pages
- CSRF protection for state-changing requests
- Parameterized SQL queries and ownership checks
- Automated authentication, authorization, CRUD, validation, and template tests

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

Never commit a real `.env` file or production credentials.

## Run the Application

```bash
python run.py
```

Then open `http://127.0.0.1:5000`.

The development database initializer creates an administrator account when one
does not exist. Change or remove this seeded account before production use.

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

## Screenshots

Add screenshots here before submission:

- Home page: `docs/screenshots/home.png`
- Login page: `docs/screenshots/login.png`
- Appointment management: `docs/screenshots/appointments.png`
- Administrator dashboard: `docs/screenshots/dashboard.png`

## Repository and Demo

- GitHub: https://github.com/sandipmahat/Hospital-Appointment-Management-System
- YouTube/Google Drive demo: `ADD_DEMO_VIDEO_LINK_HERE`

## Known Limitations

- Doctor and department records are currently maintained as controlled
  application lists rather than through a separate administration interface.
- Email delivery, SMS reminders, and real telemedicine are demonstration
  features only.
- The project uses direct PyMySQL queries instead of an ORM or migration tool.
- Production deployment and HTTPS configuration are outside the coursework
  development setup.

## Future Improvements

- Normalize doctors and departments into dedicated managed tables.
- Add appointment availability and double-booking prevention.
- Add password reset emails and account verification.
- Add pagination, search, and reporting to the administrator dashboard.
- Add database migrations and broader integration/browser tests.
- Deploy using a production WSGI server and HTTPS.
