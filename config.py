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

    INIT_DB = os.getenv("INIT_DB", "true").lower() == "true"
    CSRF_ENABLED = os.getenv("CSRF_ENABLED", "true").lower() == "true"
    TESTING = False


# Backwards-compatible module constants used by the database helper.
SECRET_KEY = Config.SECRET_KEY
MYSQL_HOST = Config.MYSQL_HOST
MYSQL_PORT = Config.MYSQL_PORT
MYSQL_USER = Config.MYSQL_USER
MYSQL_PASSWORD = Config.MYSQL_PASSWORD
MYSQL_DATABASE = Config.MYSQL_DATABASE
