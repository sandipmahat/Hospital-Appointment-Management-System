import os
from datetime import timedelta

from dotenv import load_dotenv


load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "hospital_appointments")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.getenv("SESSION_LIFETIME_MINUTES", "60"))
    )

    INIT_DB = os.getenv("INIT_DB", "false").lower() == "true"
    CSRF_ENABLED = os.getenv("CSRF_ENABLED", "true").lower() == "true"
    TESTING = False

    # The single administrator account, seeded once at first startup
    # (create_tables()). The plaintext value only ever lives here in .env -
    # what actually lands in the database is a Werkzeug password hash, never
    # this raw string.
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "sandipmahat1357@gmail.com")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Arunabc@0123")

    # Starter password for the six pre-seeded doctor accounts. Doctors are
    # expected to change this after their first login (via Profile).
    DOCTOR_SEED_PASSWORD = os.getenv("DOCTOR_SEED_PASSWORD", "Doctor@123")


# Backwards-compatible module constants used by the database helper.
SECRET_KEY = Config.SECRET_KEY
MYSQL_HOST = Config.MYSQL_HOST
MYSQL_PORT = Config.MYSQL_PORT
MYSQL_USER = Config.MYSQL_USER
MYSQL_PASSWORD = Config.MYSQL_PASSWORD
MYSQL_DATABASE = Config.MYSQL_DATABASE
ADMIN_EMAIL = Config.ADMIN_EMAIL
ADMIN_PASSWORD = Config.ADMIN_PASSWORD
DOCTOR_SEED_PASSWORD = Config.DOCTOR_SEED_PASSWORD
