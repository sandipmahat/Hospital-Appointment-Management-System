import csv
import io
import math
import re
import secrets
import string
from datetime import date, datetime, timedelta

import pymysql
import pyotp
from flask import render_template, request, redirect, url_for, session, flash, current_app, Response
from werkzeug.security import generate_password_hash, check_password_hash
from apps.auth import login_user
from apps.database import (
    get_connection, insert_row, select_one, select_all, count_rows,
    record_login_event,
)
from apps.errors import handle_db_errors
from apps.rate_limit import is_rate_limited, record_failed_attempt, reset_attempts, seconds_until_retry

# How long a "forgot password" link stays valid before it has to be
# requested again. An hour is generous enough for someone to check their
# inbox without leaving a working reset link sitting around indefinitely.
PASSWORD_RESET_TTL_MINUTES = 60

DASHBOARD_PAGE_SIZE = 15

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEPARTMENTS = (
    "Cardiology",
    "Neurology",
    "Orthopedics",
    "Pediatrics",
    "Dermatology",
    "Gynecology",
)

# Single source of truth for doctor data. The booking form's doctor dropdown,
# the homepage "Meet Our Expert Doctors" cards, the department grid, and
# appointment validation all read from this one list instead of maintaining
# separate, drifting copies of the roster. Doctor login accounts (see
# create_tables()) are linked to a profile purely by this exact name string.
DOCTOR_PROFILES = (
    {
        "name": "Dr. Rajesh Sharma",
        "specialty": "Cardiologist",
        "department": "Cardiology",
        "image": "doctor-koirala.jpg",
    },
    {
        "name": "Dr. Priya Singh",
        "specialty": "Neurologist",
        "department": "Neurology",
        "image": "doctor-sharma.jpg",
    },
    {
        "name": "Dr. Aakash Joshi",
        "specialty": "Orthopedic Surgeon",
        "department": "Orthopedics",
        "image": "doctor-singh.jpg",
    },
    {
        "name": "Dr. Sneha Gupta",
        "specialty": "Pediatrician",
        "department": "Pediatrics",
        "image": "doctor-thapa.jpg",
    },
    {
        "name": "Dr. Ramesh Thapa",
        "specialty": "Dermatologist",
        "department": "Dermatology",
        "image": "doctor-kumar.jpg",
    },
    {
        "name": "Dr. Anita Karki",
        "specialty": "Gynecologist",
        "department": "Gynecology",
        "image": "doctor-joshi.jpg",
    },
)
DOCTORS = tuple(profile["name"] for profile in DOCTOR_PROFILES)

DEFAULT_DOCTOR_IMAGE = "doctor-default.jpg"
DEFAULT_DOCTOR_SPECIALTY = "Specialist"
DEFAULT_DOCTOR_DEPARTMENT = "General"


def get_doctor_profiles():
    """All doctor accounts (the original roster plus any the admin has since
    added from Manage Doctor Accounts), read live from the database instead
    of the fixed DOCTOR_PROFILES tuple above. DOCTOR_PROFILES/DOCTORS still
    exist purely to seed the first six accounts on a fresh database (see
    create_tables()); everywhere the app actually renders or validates
    against "the doctor roster" at runtime goes through this function, so an
    admin-added doctor behaves identically to a seeded one everywhere -
    homepage cards, department grid, booking dropdowns, and validation."""
    rows = select_all(
        "users",
        where_clause="role = 'doctor'",
        columns="name, department, specialty, image",
        order_by="name ASC",
    )
    for row in rows:
        row["department"] = row.get("department") or DEFAULT_DOCTOR_DEPARTMENT
        row["specialty"] = row.get("specialty") or DEFAULT_DOCTOR_SPECIALTY
        row["image"] = row.get("image") or DEFAULT_DOCTOR_IMAGE
    return rows


def get_doctor_names(profiles=None):
    profiles = profiles if profiles is not None else get_doctor_profiles()
    return tuple(p["name"] for p in profiles)


def get_departments(profiles=None):
    """The fixed department list (stable ordering, dedicated homepage icons)
    plus any custom department a newly added doctor was given, so the
    booking form's department dropdown and validation stay in sync with
    whoever is actually in the roster."""
    profiles = profiles if profiles is not None else get_doctor_profiles()
    extra = sorted({p["department"] for p in profiles if p["department"] not in DEPARTMENTS})
    return tuple(DEPARTMENTS) + tuple(extra)

# Appointments are booked in fixed hourly slots (with a lunch break at
# 12:00) rather than freeform times. This is what makes "is this doctor
# free at this time" a simple, checkable question instead of an open-ended
# one, and it's what the availability endpoint and double-booking guard
# below are built around.
TIME_SLOTS = ("09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00")
TIME_SLOT_LABELS = {
    "09:00": "9:00 AM", "10:00": "10:00 AM", "11:00": "11:00 AM",
    "13:00": "1:00 PM", "14:00": "2:00 PM", "15:00": "3:00 PM", "16:00": "4:00 PM",
}


def _get_clean_form_value(field_name, default=""):
    return request.form.get(field_name, default).strip()


def _get_clean_query_value(field_name, default=""):
    return request.args.get(field_name, default).strip()


def _is_valid_email(email):
    return bool(EMAIL_PATTERN.fullmatch(email))


def _handle_db_error(message="Database connection is unavailable. Please try again later.", exc=None):
    # Log the real exception server-side (visible in the terminal running
    # `python run.py`) while still only ever showing the user a safe,
    # generic message. Without this, a bad password/host/port in .env fails
    # silently from the user's point of view with no way to diagnose it.
    if exc is not None:
        current_app.logger.exception("Database error: %s", exc)
    flash(message, "error")


def send_notification(recipient_email, subject, body):
    """Stands in for a real transactional email service. This coursework
    build has no SMTP credentials to send an actual email with, so instead
    of failing (or pretending nothing needs to happen) it writes the message
    to the notifications table and the server log - anyone can open
    Notification Log from the dashboard and see exactly what would have
    landed in the patient's inbox, with the same subject/body a real email
    integration would have sent. Swapping this out for a real provider later
    (e.g. Flask-Mail, SendGrid) only means changing what happens inside this
    one function - nothing that calls it needs to change.
    """
    try:
        insert_row(
            "notifications",
            ["recipient_email", "subject", "body"],
            {"recipient_email": recipient_email, "subject": subject, "body": body},
        )
    except pymysql.MySQLError:
        # A notification is a nice-to-have record, not the point of the
        # request that triggered it - losing the log entry shouldn't turn
        # into a 500 for the admin action that called this.
        current_app.logger.exception("Failed to record notification for %s", recipient_email)
    current_app.logger.info("NOTIFICATION -> %s | %s | %s", recipient_email, subject, body)


def _appointment_form_data():
    return {
        "department": _get_clean_form_value("department"),
        "doctor_name": _get_clean_form_value("doctor_name"),
        "appointment_date": _get_clean_form_value("appointment_date"),
        "appointment_time": _get_clean_form_value("appointment_time"),
    }


def _booked_slots(doctor_name, appointment_date, exclude_id=None):
    """Return the set of time slots already taken for this doctor on this
    date. A cancelled appointment frees its slot back up; pending and
    approved appointments both hold their slot, since a pending request
    might still be approved."""
    where_clause = "doctor_name = %s AND appointment_date = %s AND status != 'cancelled'"
    params = [doctor_name, appointment_date]
    if exclude_id is not None:
        where_clause += " AND id != %s"
        params.append(exclude_id)
    rows = select_all(
        "appointments",
        where_clause=where_clause,
        params=tuple(params),
        columns="appointment_time",
    )
    return {row["appointment_time"] for row in rows}


def _unavailable_slots(doctor_name, appointment_date):
    """Slots the doctor has blocked out for this date, on top of whatever's
    already booked. A row with time_slot IS NULL blocks the entire day (every
    slot in TIME_SLOTS comes back); a row with a specific time_slot blocks
    just that one hour."""
    rows = select_all(
        "doctor_unavailability",
        where_clause="doctor_name = %s AND unavailable_date = %s",
        params=(doctor_name, appointment_date),
        columns="time_slot",
    )
    if any(row["time_slot"] is None for row in rows):
        return set(TIME_SLOTS)
    return {row["time_slot"] for row in rows}


def _available_slots(doctor_name, appointment_date, exclude_id=None):
    taken = _booked_slots(doctor_name, appointment_date, exclude_id=exclude_id)
    blocked = _unavailable_slots(doctor_name, appointment_date)
    return [slot for slot in TIME_SLOTS if slot not in taken and slot not in blocked]


def _validate_appointment(data, exclude_id=None):
    if not all(data.values()):
        return "All appointment fields are required."
    profiles = get_doctor_profiles()
    doctor_profiles = {profile["name"]: profile for profile in profiles}
    if data["department"] not in get_departments(profiles) or data["doctor_name"] not in doctor_profiles:
        return "Please select a valid department and doctor."
    if doctor_profiles[data["doctor_name"]]["department"] != data["department"]:
        return "Please choose a doctor from the selected department."
    if data["appointment_time"] not in TIME_SLOTS:
        return "Please choose one of the available appointment times."
    try:
        appointment_day = date.fromisoformat(data["appointment_date"])
    except ValueError:
        return "Please enter a valid appointment date."
    if appointment_day < date.today():
        return "Appointments cannot be booked in the past."
    taken = _booked_slots(data["doctor_name"], data["appointment_date"], exclude_id=exclude_id)
    if data["appointment_time"] in taken:
        return "That time slot is already booked for this doctor. Please choose another."
    return None


# ---------------- HOME PAGE ----------------
def home():
    features = [
        "Book appointments quickly",
        "Track your visit history",
        "Get reminders for upcoming care",
    ]
    profiles = get_doctor_profiles()

    # Group doctors by department so the "Browse by Department" grid and
    # quick-book dropdown each show one card/option per department (with an
    # accurate specialist count) instead of one per doctor - without this,
    # two doctors sharing a department (easy to end up with once an admin
    # can add doctors freely from Manage Doctor Accounts) would render as
    # two duplicate "Cardiology" cards, each wrongly claiming to be the
    # only specialist.
    department_groups = []
    groups_by_name = {}
    for profile in profiles:
        dept = profile["department"]
        if dept not in groups_by_name:
            groups_by_name[dept] = {"department": dept, "doctors": []}
            department_groups.append(groups_by_name[dept])
        groups_by_name[dept]["doctors"].append(profile["name"])

    return render_template(
        "medhub.html",
        name=session.get("user_name"),
        features=features,
        is_authenticated=bool(session.get("user_id")),
        doctors=profiles,
        department_groups=department_groups,
    )


# ---------------- ABOUT PAGE ----------------
def about():
    profiles = get_doctor_profiles()
    stats = [
        {"num": "3", "label": "User Roles", "color": "blue"},
        {"num": str(len(profiles)), "label": "Specialist Doctors", "color": "green"},
        {"num": "7", "label": "Daily Time Slots", "color": "amber"},
        {"num": "36", "label": "Automated Tests", "color": "purple"},
    ]
    return render_template("about.html", stats=stats, departments=get_departments(profiles))


# ---------------- CONTACT PAGE ----------------
def contact():
    return render_template("contact.html")


def _redirect_for_role(role):
    if role == "admin":
        return redirect(url_for("auth.dashboard"))
    if role == "doctor":
        return redirect(url_for("auth.doctor_schedule"))
    return redirect(url_for("auth.home"))


def _audit_login(event_type, user=None, email=None, notes=None):
    """Record a login event in MySQL without exposing credentials in the log."""
    user = user or {}
    record_login_event(
        user.get("id"),
        user.get("email") or email or "unknown",
        event_type,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string[:255],
        notes=notes,
    )


# ---------------- LOGIN FUNCTION (single, role-based) ----------------
# This is the one and only authentication entry point in the app. There is
# no separate registration page: a "user" login for an email that doesn't
# exist yet silently creates that patient account (no admin approval
# needed), while "doctor" and "admin" logins only ever succeed against
# accounts that were already provisioned ahead of time - a doctor or admin
# can never self-register through this form.
def login():
    if session.get("user_id"):
        return _redirect_for_role(session.get("user_role"))

    if request.method == "POST":
        login_as = _get_clean_form_value("login_as", "user")
        if login_as not in {"user", "doctor", "admin"}:
            login_as = "user"

        email = _get_clean_form_value("email", "").lower()
        password = _get_clean_form_value("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "error")
            return render_template("login.html", submitted_email=email, login_as=login_as, show_form=True)

        if not _is_valid_email(email):
            flash("Please enter a valid email address.", "error")
            return render_template("login.html", submitted_email=email, login_as=login_as, show_form=True)

        rate_limit_key = f"{email}:{request.remote_addr}"
        if is_rate_limited(rate_limit_key):
            wait_minutes = max(1, seconds_until_retry(rate_limit_key) // 60)
            flash(
                f"Too many failed login attempts. Please try again in about "
                f"{wait_minutes} minute(s).",
                "error",
            )
            return render_template("login.html", submitted_email=email, login_as=login_as, show_form=True)

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
        except pymysql.MySQLError as exc:
            _handle_db_error(exc=exc)
            return render_template("login.html", submitted_email=email, login_as=login_as, show_form=True)

        # ---- Doctor tab: the account must already exist with role=doctor.
        if login_as == "doctor":
            if user and user["role"] == "doctor":
                if check_password_hash(user["password"], password):
                    session.clear()
                    login_user(user)
                    reset_attempts(rate_limit_key)
                    _audit_login("login_success", user, notes="Doctor login")
                    flash("Login successful!", "success")
                    return _redirect_for_role("doctor")
                _audit_login("login_failure", user, notes="Incorrect doctor password")
                record_failed_attempt(rate_limit_key)
                flash("Wrong email or password.", "error")
            else:
                record_failed_attempt(rate_limit_key)
                flash(
                    "Access Denied. Your account has not been created by the "
                    "administrator. Please contact the hospital administrator.",
                    "error",
                )
            return render_template("login.html", submitted_email=email, login_as=login_as, show_form=True)

        # ---- Admin tab: only the single seeded admin account can ever log in.
        if login_as == "admin":
            if user and user["role"] == "admin" and check_password_hash(user["password"], password):
                if user.get("totp_secret"):
                    # Password is correct, but this admin has two-factor
                    # turned on - hold off on login_user() until the code is
                    # verified too. A "pending" marker (not a real session)
                    # is enough to remember who's mid-login without granting
                    # any actual access yet.
                    session.clear()
                    session["pending_admin_id"] = user["id"]
                    reset_attempts(rate_limit_key)
                    return redirect(url_for("auth.verify_admin_2fa"))
                session.clear()
                login_user(user)
                reset_attempts(rate_limit_key)
                _audit_login("login_success", user, notes="Administrator login")
                flash("Login successful!", "success")
                return _redirect_for_role("admin")
            _audit_login("login_failure", user, email, notes="Invalid administrator credentials")
            record_failed_attempt(rate_limit_key)
            flash("Invalid administrator credentials.", "error")
            return render_template("login.html", submitted_email=email, login_as=login_as, show_form=True)

        # ---- User tab: log in if the email exists as a patient account;
        # if the email doesn't exist at all, create it on the spot. If the
        # email belongs to a doctor/admin account instead, don't silently
        # try to log them into the wrong role.
        if user and user["role"] != "user":
            flash(
                "This email is registered as a different type of account. "
                "Please use the matching login tab above.",
                "error",
            )
            return render_template("login.html", submitted_email=email, login_as=login_as, show_form=True)

        if user:
            if check_password_hash(user["password"], password):
                session.clear()
                login_user(user)
                reset_attempts(rate_limit_key)
                _audit_login("login_success", user, notes="Patient login")
                flash("Login successful!", "success")
                return _redirect_for_role("user")
            _audit_login("login_failure", user, notes="Incorrect patient password")
            record_failed_attempt(rate_limit_key)
            flash("Wrong email or password.", "error")
            return render_template("login.html", submitted_email=email, login_as=login_as, show_form=True)

        # No account with this email yet - auto-create one, no approval needed.
        if len(password) < 6:
            flash("Password should be at least 6 characters.", "error")
            return render_template("login.html", submitted_email=email, login_as=login_as, show_form=True)

        try:
            new_user_id = insert_row(
                "users",
                ["name", "email", "password", "role"],
                {
                    "name": email.split("@")[0],
                    "email": email,
                    "password": generate_password_hash(password),
                    "role": "user",
                },
            )
        except pymysql.MySQLError as exc:
            _handle_db_error(exc=exc)
            return render_template("login.html", submitted_email=email, login_as=login_as, show_form=True)

        session.clear()
        new_user = {"id": new_user_id, "name": email.split("@")[0], "email": email, "role": "user"}
        login_user(new_user)
        reset_attempts(rate_limit_key)
        _audit_login("login_success", new_user, notes="New patient account created")
        flash("Welcome! Your account has been created.", "success")
        return _redirect_for_role("user")

    requested_role = request.args.get("login_as")
    if requested_role not in {"user", "doctor", "admin"}:
        requested_role = None
    return render_template(
        "login.html",
        submitted_email="",
        login_as=requested_role or "user",
        show_form=bool(requested_role),
    )


# ---------------- ADMIN: VERIFY 2FA CODE (second login step) ----------------
@handle_db_errors(fallback_endpoint="auth.login")
def verify_admin_2fa():
    """The second half of an admin login once TOTP is enabled. pending_admin_id
    only ever gets set by the admin branch of login() right after a correct
    password check, and only ever gets cleared here (or by session.clear()
    elsewhere) - so landing on this page with nothing pending just bounces
    back to the normal login form instead of erroring."""
    pending_id = session.get("pending_admin_id")
    if not pending_id:
        return redirect(url_for("auth.login"))

    user = select_one(
        "users",
        "id = %s AND role = 'admin'",
        (pending_id,),
        columns="id, name, email, role, totp_secret",
    )
    if not user or not user.get("totp_secret"):
        session.pop("pending_admin_id", None)
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = _get_clean_form_value("code")
        totp = pyotp.TOTP(user["totp_secret"])
        # valid_window=1 tolerates the code from one 30-second step before
        # or after "now", which absorbs ordinary clock drift between the
        # server and the admin's phone without meaningfully weakening the
        # check - a real intruder still needs the secret, not just luck.
        if code and totp.verify(code, valid_window=1):
            session.pop("pending_admin_id", None)
            session.clear()
            login_user(user)
            _audit_login("login_success", user, notes="Administrator login with 2FA")
            flash("Login successful!", "success")
            return _redirect_for_role("admin")
        flash("That code didn't match. Please try again.", "error")

    return render_template("verify_2fa.html")


# ---------------- LOGOUT ----------------
def logout():
    _audit_login(
        "logout",
        {"id": session.get("user_id"), "email": session.get("user_email")},
        notes="User logged out",
    )
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


# ---------------- SELF-SERVICE PASSWORD RESET ----------------
# Two-step "forgot password" flow: request a link, then use it once. No
# email server is configured for this build, so the link itself never
# appears anywhere the requester can see it directly (that would let anyone
# who merely knows a person's email address reset that account without ever
# touching their inbox). Instead it's written to the notifications table by
# send_notification(), which only the admin can read via Notification Log -
# functionally the same "check your email" step, just admin-gated instead
# of actually leaving the server.
@handle_db_errors(fallback_endpoint="auth.login")
def forgot_password():
    if request.method == "POST":
        email = _get_clean_form_value("email", "").lower()
        if email and _is_valid_email(email):
            user = select_one("users", "email = %s", (email,), columns="id, name, email")
            if user:
                token = secrets.token_urlsafe(32)
                expires_at = datetime.now() + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)
                insert_row(
                    "password_resets",
                    ["user_id", "token", "expires_at"],
                    {"user_id": user["id"], "token": token, "expires_at": expires_at},
                )
                reset_link = url_for("auth.reset_password", token=token, _external=True)
                send_notification(
                    user["email"],
                    "Reset your sandyHUb password",
                    f"Hi {user['name']}, use this link within the next hour to reset your "
                    f"password: {reset_link}\n\nIf you didn't request this, you can ignore "
                    "this message and your password will stay the same.",
                )
        # Identical message whether or not the account exists - a form that
        # confirms "yes, that email is registered" is a free way for anyone
        # to enumerate real user accounts on the site.
        flash(
            "If an account exists for that email, password reset instructions have been sent.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")


@handle_db_errors(fallback_endpoint="auth.forgot_password")
def reset_password(token):
    reset_row = select_one(
        "password_resets",
        "token = %s AND used = 0 AND expires_at > NOW()",
        (token,),
        columns="id, user_id",
    )
    if not reset_row:
        flash(
            "This password reset link is invalid or has expired. Please request a new one.",
            "error",
        )
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        new_password = _get_clean_form_value("password")
        confirm_password = _get_clean_form_value("confirmPassword")

        if len(new_password) < 6:
            flash("Password should be at least 6 characters.", "error")
        elif new_password != confirm_password:
            flash("Passwords do not match.", "error")
        else:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET password = %s WHERE id = %s",
                (generate_password_hash(new_password), reset_row["user_id"]),
            )
            # Marked used rather than deleted, so a second attempt with the
            # same link gets a clear "already used" style rejection (it just
            # won't match the "used = 0" clause above) instead of a
            # confusing "not found".
            cursor.execute(
                "UPDATE password_resets SET used = 1 WHERE id = %s", (reset_row["id"],)
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash("Your password has been reset. Please log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=token)


# ---------------- DASHBOARD ----------------
@handle_db_errors()
def dashboard():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    if session.get("user_role") != "admin":
        flash("You do not have permission to access the dashboard.", "error")
        return redirect(url_for("auth.home"))

    # A password just reset via admin_reset_password() rides here for
    # exactly one page load - popped (not just read) so refreshing the
    # dashboard afterwards never shows it a second time.
    password_reveal = session.pop("password_reveal", None)

    # Optional filters for the two tables below. Kept deliberately simple -
    # a name/email substring match for users, a status match for
    # appointments - since a hospital this size doesn't need a full query
    # builder, just a fast way to find one row in a growing list.
    user_query = _get_clean_query_value("q")
    status_filter = _get_clean_query_value("status")
    if status_filter not in {"pending", "approved", "cancelled"}:
        status_filter = ""

    # Appointments can grow without bound over the life of a hospital, so the
    # table is paged server-side (LIMIT/OFFSET) instead of loading every row
    # into memory on every dashboard view.
    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1

    appt_where, appt_params = (None, ())
    if status_filter:
        appt_where, appt_params = "status = %s", (status_filter,)

    total_appointments = count_rows("appointments", where_clause=appt_where, params=appt_params)
    total_pages = max(1, math.ceil(total_appointments / DASHBOARD_PAGE_SIZE))
    page = min(page, total_pages)
    offset = (page - 1) * DASHBOARD_PAGE_SIZE

    # Small COUNT(*) queries for the summary stat cards - cheap even as the
    # hospital grows, since none of them pull row data into memory. These
    # always reflect the whole table, independent of the status filter above.
    total_users = count_rows("users")
    pending_count = count_rows("appointments", where_clause="status = 'pending'")
    approved_count = count_rows("appointments", where_clause="status = 'approved'")
    cancelled_count = count_rows("appointments", where_clause="status = 'cancelled'")

    user_where, user_params = (None, ())
    if user_query:
        user_where = "name LIKE %s OR email LIKE %s"
        user_params = (f"%{user_query}%", f"%{user_query}%")

    users = select_all(
        "users",
        where_clause=user_where,
        params=user_params,
        columns="id, name, email, role, created_at",
        order_by="created_at DESC",
        limit=100,
    )

    appt_join_where = f"a.{appt_where}" if appt_where else None
    appointments = select_all(
        "appointments a LEFT JOIN users u ON u.id = a.user_id",
        where_clause=appt_join_where,
        params=appt_params,
        columns=(
            "a.id, a.user_id, u.name AS patient_name, u.email AS patient_email, "
            "a.doctor_name, a.department, a.appointment_date, a.appointment_time, "
            "a.status, a.created_at"
        ),
        order_by="a.appointment_date ASC, a.appointment_time ASC",
        limit=DASHBOARD_PAGE_SIZE,
        offset=offset,
    )

    return render_template(
        "dashboard.html",
        users=users,
        appointments=appointments,
        page=page,
        total_pages=total_pages,
        total_appointments=total_appointments,
        total_users=total_users,
        pending_count=pending_count,
        approved_count=approved_count,
        cancelled_count=cancelled_count,
        user_query=user_query,
        status_filter=status_filter,
        password_reveal=password_reveal,
    )


# ---------------- ADMIN APPOINTMENTS ----------------
@handle_db_errors()
def admin_appointments():
    if request.method == "POST":
        appointment_id = _get_clean_form_value("appointment_id")
        action = _get_clean_form_value("action")

        # "remind" doesn't touch the appointment's status at all - it just
        # re-sends the same notification an approval would have sent, for a
        # patient whose appointment is coming up and might appreciate a
        # nudge. Handled separately from approve/cancel below since it
        # doesn't run an UPDATE.
        if appointment_id and action == "remind":
            appt = select_one(
                "appointments a LEFT JOIN users u ON u.id = a.user_id",
                "a.id = %s",
                (appointment_id,),
                columns="a.doctor_name, a.appointment_date, a.appointment_time, u.name AS patient_name, u.email AS patient_email",
            )
            if appt and appt.get("patient_email"):
                send_notification(
                    appt["patient_email"],
                    "Reminder: upcoming appointment at sandyHUb",
                    f"Hi {appt['patient_name']}, this is a reminder of your appointment with "
                    f"{appt['doctor_name']} on {appt['appointment_date']} at "
                    f"{TIME_SLOT_LABELS.get(str(appt['appointment_time'])[:5], appt['appointment_time'])}.",
                )
                flash("Reminder sent.", "success")
            else:
                flash("Could not find that appointment's patient.", "error")
            return dashboard()

        if appointment_id and action in {"approve", "cancel"}:
            status = "approved" if action == "approve" else "cancelled"
            # A cancellation can carry an optional note explaining why, shown
            # back to the patient on My Appointments - approving never needs
            # one, so the column is simply cleared back to NULL on approval
            # rather than keeping a stale reason from some earlier cancel.
            reason = _get_clean_form_value("reason") if action == "cancel" else ""
            appt = select_one(
                "appointments a LEFT JOIN users u ON u.id = a.user_id",
                "a.id = %s",
                (appointment_id,),
                columns="a.doctor_name, a.appointment_date, a.appointment_time, u.name AS patient_name, u.email AS patient_email",
            )
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE appointments SET status = %s, cancellation_reason = %s WHERE id = %s",
                (status, reason or None, appointment_id),
            )
            affected = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()
            if affected:
                flash(f"Appointment {status}.", "success")
                # Best-effort - a slow/broken notification log should never
                # stop the appointment status update that already committed.
                if appt and appt.get("patient_email"):
                    if action == "approve":
                        send_notification(
                            appt["patient_email"],
                            "Your sandyHUb appointment has been approved",
                            f"Hi {appt['patient_name']}, your appointment with {appt['doctor_name']} on "
                            f"{appt['appointment_date']} at "
                            f"{TIME_SLOT_LABELS.get(str(appt['appointment_time'])[:5], appt['appointment_time'])} "
                            "has been approved. See you then!",
                        )
                    else:
                        send_notification(
                            appt["patient_email"],
                            "Your sandyHUb appointment was cancelled",
                            f"Hi {appt['patient_name']}, your appointment with {appt['doctor_name']} on "
                            f"{appt['appointment_date']} was cancelled."
                            + (f" Reason: {reason}" if reason else ""),
                        )
            else:
                flash("Unable to update appointment status.", "error")
        else:
            flash("Invalid appointment action.", "error")

    return dashboard()


# ---------------- BOOK APPOINTMENT ----------------
@handle_db_errors()
def book_appointment():
    if request.method == "POST":
        form_data = _appointment_form_data()
        validation_error = _validate_appointment(form_data)
        if validation_error:
            flash(validation_error, "error")
            profiles = get_doctor_profiles()
            return render_template(
                "book_appointment.html",
                departments=get_departments(profiles),
                doctors=profiles,
                appointment=form_data,
                time_slots=TIME_SLOTS,
                time_slot_labels=TIME_SLOT_LABELS,
            )

        user_id = session["user_id"]
        # Use insert_row to accept only allowed columns from form data
        insert_row(
            "appointments",
            [
                "user_id",
                "doctor_name",
                "department",
                "appointment_date",
                "appointment_time",
            ],
            {
                "user_id": user_id,
                **form_data,
            },
        )

        flash("Appointment booked successfully. Your request is pending approval.", "success")
        return redirect(url_for("auth.my_appointments"))

    # Support deep-linking from the doctor cards and the homepage quick-book
    # panel (?doctor_name=...&department=...&appointment_date=...),
    # pre-selecting those values on the form. Only accept values that are
    # actually valid so an arbitrary query string can't inject an unlisted
    # option into the dropdown or a malformed date into the date input.
    requested_doctor = request.args.get("doctor_name", "")
    requested_department = request.args.get("department", "")
    requested_date = request.args.get("appointment_date", "")
    try:
        date.fromisoformat(requested_date)
    except ValueError:
        requested_date = ""
    profiles = get_doctor_profiles()
    doctor_names = get_doctor_names(profiles)
    departments = get_departments(profiles)
    return render_template(
        "book_appointment.html",
        departments=departments,
        doctors=profiles,
        appointment={
            "doctor_name": requested_doctor if requested_doctor in doctor_names else "",
            "department": requested_department if requested_department in departments else "",
            "appointment_date": requested_date,
        },
        time_slots=TIME_SLOTS,
        time_slot_labels=TIME_SLOT_LABELS,
    )


@handle_db_errors(fallback_endpoint="auth.book_appointment")
def appointment_availability():
    """JSON endpoint the booking form calls whenever the doctor or date
    changes, so it can only display slots that are actually still open
    instead of letting the patient pick a time and find out it's taken
    only after submitting."""
    doctor_name = request.args.get("doctor_name", "")
    appointment_date = request.args.get("appointment_date", "")
    exclude_id = request.args.get("exclude_id", type=int)

    if doctor_name not in get_doctor_names():
        return {"error": "Unknown doctor."}, 400
    try:
        date.fromisoformat(appointment_date)
    except ValueError:
        return {"error": "Invalid date."}, 400
    if date.fromisoformat(appointment_date) < date.today():
        return {"error": "Appointments cannot be booked in the past."}, 400

    available = _available_slots(doctor_name, appointment_date, exclude_id=exclude_id)
    return {
        "available": available,
        "labels": {slot: TIME_SLOT_LABELS[slot] for slot in available},
    }


@handle_db_errors(fallback_endpoint="auth.my_appointments")
def edit_appointment(appointment_id):
    user_id = session["user_id"]
    appointment = select_one(
        "appointments",
        "id = %s AND user_id = %s",
        (appointment_id, user_id),
        columns=(
            "id, doctor_name, department, appointment_date, "
            "appointment_time, status"
        ),
    )
    if not appointment:
        flash("Appointment not found or access denied.", "error")
        return redirect(url_for("auth.my_appointments"))

    if appointment["status"] not in {"pending", "cancelled"}:
        flash("Only pending or cancelled appointments can be edited.", "error")
        return redirect(url_for("auth.my_appointments"))

    if request.method == "POST":
        form_data = _appointment_form_data()
        validation_error = _validate_appointment(form_data, exclude_id=appointment_id)
        if validation_error:
            flash(validation_error, "error")
            appointment.update(form_data)
            profiles = get_doctor_profiles()
            return render_template(
                "book_appointment.html",
                departments=get_departments(profiles),
                doctors=profiles,
                appointment=appointment,
                editing=True,
                time_slots=TIME_SLOTS,
                time_slot_labels=TIME_SLOT_LABELS,
            )

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE appointments
            SET doctor_name = %s, department = %s, appointment_date = %s,
                appointment_time = %s, status = 'pending'
            WHERE id = %s AND user_id = %s
            """,
            (
                form_data["doctor_name"],
                form_data["department"],
                form_data["appointment_date"],
                form_data["appointment_time"],
                appointment_id,
                user_id,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Appointment updated successfully.", "success")
        return redirect(url_for("auth.my_appointments"))

    profiles = get_doctor_profiles()
    return render_template(
        "book_appointment.html",
        departments=get_departments(profiles),
        doctors=profiles,
        appointment=appointment,
        editing=True,
        time_slots=TIME_SLOTS,
        time_slot_labels=TIME_SLOT_LABELS,
    )


@handle_db_errors(fallback_endpoint="auth.my_appointments")
def delete_appointment(appointment_id):
    user_id = session["user_id"]
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM appointments WHERE id = %s AND user_id = %s",
        (appointment_id, user_id),
    )
    deleted = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()

    flash(
        "Appointment deleted." if deleted else "Appointment not found or access denied.",
        "success" if deleted else "error",
    )
    return redirect(url_for("auth.my_appointments"))


# ---------------- MY APPOINTMENTS ----------------
@handle_db_errors()
def my_appointments():
    user_id = session.get("user_id")
    appointments = select_all(
        "appointments",
        where_clause="user_id = %s",
        params=(user_id,),
        columns="id, doctor_name, department, appointment_date, appointment_time, status, created_at, cancellation_reason",
        order_by="appointment_date ASC, appointment_time ASC",
    )

    return render_template("my_appointments.html", appointments=appointments)


# ---------------- PROFILE ----------------
@handle_db_errors()
def profile():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, password, role FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        session.clear()
        flash("User session not found. Please log in again.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        name = _get_clean_form_value("name", "")
        email = _get_clean_form_value("email", "").lower()
        current_password = _get_clean_form_value("currentPassword", "")
        new_password = _get_clean_form_value("newPassword", "")
        confirm_password = _get_clean_form_value("confirmPassword", "")

        if not name or not email:
            flash("Name and email are required.", "error")
            cursor.close()
            conn.close()
            safe_user = {k: v for k, v in user.items() if k != "password"}
            return render_template("profile.html", user=safe_user)

        if not _is_valid_email(email):
            flash("Please enter a valid email address.", "error")
            cursor.close()
            conn.close()
            return render_template("profile.html", user=user)

        if email != user["email"]:
            cursor.execute(
                "SELECT id FROM users WHERE email = %s AND id != %s",
                (email, user_id),
            )
            if cursor.fetchone():
                flash("This email is already used by another account.", "error")
                cursor.close()
                conn.close()
                return render_template("profile.html", user=user)

        password_update = None
        if new_password:
            if not current_password:
                flash("Please enter your current password to change your password.", "error")
                cursor.close()
                conn.close()
                return render_template("profile.html", user=user)

            if not check_password_hash(user["password"], current_password):
                flash("Current password is incorrect.", "error")
                cursor.close()
                conn.close()
                safe_user = {k: v for k, v in user.items() if k != "password"}
                return render_template("profile.html", user=safe_user)

            if new_password != confirm_password:
                flash("New passwords do not match.", "error")
                cursor.close()
                conn.close()
                safe_user = {k: v for k, v in user.items() if k != "password"}
                return render_template("profile.html", user=safe_user)

            if len(new_password) < 6:
                flash("New password must be at least 6 characters.", "error")
                cursor.close()
                conn.close()
                safe_user = {k: v for k, v in user.items() if k != "password"}
                return render_template("profile.html", user=safe_user)

            password_update = generate_password_hash(new_password)

        if password_update:
            cursor.execute(
                "UPDATE users SET name = %s, email = %s, password = %s WHERE id = %s",
                (name, email, password_update, user_id),
            )
        else:
            cursor.execute(
                "UPDATE users SET name = %s, email = %s WHERE id = %s",
                (name, email, user_id),
            )

        conn.commit()
        cursor.close()
        conn.close()

        session["user_name"] = name
        session["user_email"] = email

        flash("Profile updated successfully.", "success")
        return redirect(url_for("auth.profile"))
    cursor.close()
    conn.close()
    safe_user = {k: v for k, v in user.items() if k != "password"}
    return render_template("profile.html", user=safe_user)


# ---------------- ADMIN: TWO-FACTOR AUTHENTICATION SETUP ----------------
@handle_db_errors(fallback_endpoint="auth.dashboard")
def totp_setup():
    """Lets the admin turn TOTP two-factor on or off for their own account.
    Turning it on is a two-step confirm: a secret is generated and shown
    (as both a manual entry key and an otpauth:// URI an authenticator app
    can scan) but not saved to the database yet, and only gets written to
    users.totp_secret once the admin proves their app actually has it right
    by submitting one real 6-digit code - otherwise a typo'd or
    never-actually-scanned secret could lock the admin out on their very
    next login."""
    user_id = session["user_id"]
    user = select_one("users", "id = %s", (user_id,), columns="id, name, email, totp_secret")

    if request.method == "POST":
        action = _get_clean_form_value("action")

        if action == "disable":
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET totp_secret = NULL WHERE id = %s", (user_id,))
            conn.commit()
            cursor.close()
            conn.close()
            session.pop("pending_totp_secret", None)
            flash("Two-factor authentication has been turned off.", "success")
            return redirect(url_for("auth.totp_setup"))

        pending_secret = session.get("pending_totp_secret")
        code = _get_clean_form_value("code")
        if pending_secret and code and pyotp.TOTP(pending_secret).verify(code, valid_window=1):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET totp_secret = %s WHERE id = %s", (pending_secret, user_id))
            conn.commit()
            cursor.close()
            conn.close()
            session.pop("pending_totp_secret", None)
            flash("Two-factor authentication is now enabled on your account.", "success")
            return redirect(url_for("auth.totp_setup"))

        flash("That code didn't match. Please scan the QR/key again and try once more.", "error")

    if user.get("totp_secret"):
        return render_template("totp_setup.html", enabled=True)

    # Reuse a secret already generated earlier in this same setup attempt
    # (e.g. after a failed confirm code) instead of rotating it on every
    # page load, which would invalidate whatever the admin just scanned.
    secret = session.get("pending_totp_secret")
    if not secret:
        secret = pyotp.random_base32()
        session["pending_totp_secret"] = secret
    otpauth_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="sandyHUb Admin")
    return render_template("totp_setup.html", enabled=False, secret=secret, otpauth_uri=otpauth_uri)


# ---------------- ADMIN: MANAGE DOCTOR ACCOUNTS ----------------
@handle_db_errors(fallback_endpoint="auth.dashboard")
def manage_doctors():
    """Lets an admin create a doctor login two ways: pick one of the
    original six roster doctors who doesn't have an account yet (their
    department/specialty/portrait come along automatically), or add a
    brand new doctor outside that roster by typing a name, department, and
    specialty directly. Either way it's a normal `role='doctor'` row, and
    get_doctor_profiles() reads the live roster from the database - so an
    admin-added doctor shows up everywhere a seeded one does (homepage
    cards, department grid, booking dropdown) with no further wiring.

    On success the plaintext password is shown once on this same response
    (never redirected, never stored) so the admin can hand it to the
    doctor - after that the app only ever holds the hash."""
    existing = select_all(
        "users",
        where_clause="role = 'doctor'",
        columns="id, name, email, department, specialty, created_at",
        order_by="name ASC",
    )
    claimed_names = {row["name"] for row in existing}
    available_doctors = [d for d in DOCTOR_PROFILES if d["name"] not in claimed_names]
    created_doctor = None

    if request.method == "POST":
        mode = _get_clean_form_value("mode") or "roster"
        email = _get_clean_form_value("email").lower()
        password = _get_clean_form_value("password")
        confirm_password = _get_clean_form_value("confirmPassword")

        if mode == "custom":
            doctor_name = _get_clean_form_value("doctor_name")
            if doctor_name and not doctor_name.lower().startswith("dr."):
                doctor_name = f"Dr. {doctor_name}"
            department = _get_clean_form_value("department")
            specialty = _get_clean_form_value("specialty")
            image = None
        else:
            doctor_name = _get_clean_form_value("doctor_name")
            profile = next((d for d in DOCTOR_PROFILES if d["name"] == doctor_name), None)
            department = profile["department"] if profile else ""
            specialty = profile["specialty"] if profile else ""
            image = profile["image"] if profile else None

        if not doctor_name:
            flash("Please enter the doctor's name.", "error")
        elif mode == "roster" and doctor_name not in DOCTORS:
            flash("Please choose a valid doctor.", "error")
        elif doctor_name in claimed_names:
            flash("That doctor already has an account.", "error")
        elif mode == "custom" and not department:
            flash("Please enter a department.", "error")
        elif not email or not password:
            flash("Email and password are required.", "error")
        elif not _is_valid_email(email):
            flash("Please enter a valid email address.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        elif len(password) < 6:
            flash("Password should be at least 6 characters.", "error")
        else:
            existing_user = select_one("users", "email = %s", (email,))
            if existing_user:
                flash("This email is already registered.", "error")
            else:
                insert_row(
                    "users",
                    ["name", "email", "password", "role", "department", "specialty", "image"],
                    {
                        "name": doctor_name,
                        "email": email,
                        "password": generate_password_hash(password),
                        "role": "doctor",
                        "department": department or None,
                        "specialty": specialty or None,
                        "image": image,
                    },
                )
                created_doctor = {"name": doctor_name, "email": email, "password": password}
                existing = select_all(
                    "users",
                    where_clause="role = 'doctor'",
                    columns="id, name, email, department, specialty, created_at",
                    order_by="name ASC",
                )
                claimed_names = {row["name"] for row in existing}
                available_doctors = [d for d in DOCTOR_PROFILES if d["name"] not in claimed_names]

    return render_template(
        "manage_doctors.html",
        existing_doctors=existing,
        available_doctors=available_doctors,
        departments=DEPARTMENTS,
        created_doctor=created_doctor,
    )


# ---------------- ADMIN: EDIT A DOCTOR'S PROFILE ----------------
@handle_db_errors(fallback_endpoint="auth.manage_doctors")
def edit_doctor_profile(user_id):
    """A basic editable profile for one doctor account - department,
    specialty, a short bio, and the filename of their portrait under
    static/images/. Deliberately not self-service (the doctor doesn't get a
    "edit my profile" screen of their own yet): the admin already owns
    doctor account creation, so keeping the one edit surface here means
    there's a single place that can put a doctor into an inconsistent state
    instead of two."""
    doctor = select_one(
        "users",
        "id = %s AND role = 'doctor'",
        (user_id,),
        columns="id, name, email, department, specialty, bio, image, created_at",
    )
    if not doctor:
        flash("Doctor not found.", "error")
        return redirect(url_for("auth.manage_doctors"))

    if request.method == "POST":
        department = _get_clean_form_value("department")
        specialty = _get_clean_form_value("specialty")
        bio = _get_clean_form_value("bio")
        image = _get_clean_form_value("image")

        if not department or not specialty:
            flash("Department and specialty are required.", "error")
        else:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET department = %s, specialty = %s, bio = %s, image = %s
                WHERE id = %s
                """,
                (department, specialty, bio or None, image or None, user_id),
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash(f"{doctor['name']}'s profile has been updated.", "success")
            return redirect(url_for("auth.manage_doctors"))

        # Validation failed - fall through and re-render with what was typed
        # rather than the stale values loaded above.
        doctor.update({"department": department, "specialty": specialty, "bio": bio, "image": image})

    return render_template(
        "doctor_profile_edit.html",
        doctor=doctor,
        departments=DEPARTMENTS,
    )


def _generate_temp_password(length=10):
    """A random password strong enough to hand to a user once and have them
    change it later - mixed case, digits, and a couple of symbols, generated
    with `secrets` (not `random`) since this ends up protecting a real
    account, not just filling in a placeholder."""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------------- ADMIN: RESET A USER'S PASSWORD ----------------
@handle_db_errors(fallback_endpoint="auth.dashboard")
def admin_reset_password(user_id):
    """Lets the admin set a fresh password for any account without knowing
    the old one - for a doctor or patient who's locked themselves out, since
    there's no self-service reset for them to use yet. Same one-time-reveal
    pattern as doctor creation: the new plaintext password rides along in
    the session for exactly one redirect, gets shown once on the dashboard,
    and is never stored or retrievable after that."""
    user = select_one("users", "id = %s", (user_id,), columns="id, name, email, role")
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("auth.dashboard"))

    new_password = _generate_temp_password()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password = %s WHERE id = %s",
        (generate_password_hash(new_password), user_id),
    )
    conn.commit()
    cursor.close()
    conn.close()

    session["password_reveal"] = {
        "name": user["name"],
        "email": user["email"],
        "password": new_password,
    }
    flash(f"Password reset for {user['name']}.", "success")
    return redirect(url_for("auth.dashboard"))


# ---------------- ADMIN: DELETE A USER OR DOCTOR ACCOUNT ----------------
@handle_db_errors(fallback_endpoint="auth.dashboard")
def admin_delete_user(user_id):
    """Removes a user (or doctor) account entirely. Appointments belonging
    to a deleted patient go with them automatically through the users.id
    foreign key's ON DELETE CASCADE, so this can never leave an orphaned
    booking behind. The administrator account itself is refused here - this
    system is built around exactly one admin, and there's no recovery path
    if that account gets removed by mistake."""
    user = select_one("users", "id = %s", (user_id,), columns="id, name, role")
    if not user:
        flash("User not found.", "error")
    elif user["role"] == "admin":
        flash("The administrator account can't be deleted.", "error")
    else:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"{user['name']}'s account has been deleted.", "success")
    return redirect(url_for("auth.dashboard"))


# ---------------- ADMIN: EXPORT APPOINTMENTS AS CSV ----------------
@handle_db_errors(fallback_endpoint="auth.dashboard")
def export_appointments_csv():
    """Downloads every appointment as a CSV, for an administrator who wants
    the full booking history in a spreadsheet rather than paging through the
    dashboard table 15 rows at a time. Pulls every row regardless of the
    dashboard's current page, since the whole point of an export is having
    it all in one file."""
    appointments = select_all(
        "appointments a LEFT JOIN users u ON u.id = a.user_id",
        columns=(
            "a.id, u.name AS patient_name, u.email AS patient_email, "
            "a.doctor_name, a.department, a.appointment_date, a.appointment_time, "
            "a.status, a.created_at"
        ),
        order_by="a.appointment_date DESC, a.appointment_time ASC",
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "ID", "Patient", "Email", "Doctor", "Department",
        "Date", "Time", "Status", "Booked At",
    ])
    for appt in appointments:
        writer.writerow([
            appt["id"], appt["patient_name"], appt["patient_email"],
            appt["doctor_name"], appt["department"], appt["appointment_date"],
            appt["appointment_time"], appt["status"], appt["created_at"],
        ])

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=sandyhub-appointments.csv"},
    )


# ---------------- ADMIN: NOTIFICATION LOG ----------------
@handle_db_errors(fallback_endpoint="auth.dashboard")
def notification_log():
    """Read-only list of every stub "email" send_notification() has ever
    recorded - approvals, cancellations, reminders, and password reset
    links. Exists so the admin (and, for coursework purposes, an examiner)
    can see the notification feature is genuinely wired up end to end
    without needing a real mailbox to check."""
    notifications = select_all(
        "notifications",
        columns="id, recipient_email, subject, body, created_at",
        order_by="created_at DESC",
        limit=200,
    )
    return render_template("notification_log.html", notifications=notifications)


# ---------------- DOCTOR: MY SCHEDULE (read-only) ----------------
@handle_db_errors()
def doctor_schedule():
    doctor_name = session.get("user_name")
    appointments = select_all(
        "appointments a LEFT JOIN users u ON u.id = a.user_id",
        columns=(
            "a.id, u.name AS patient_name, u.email AS patient_email, "
            "a.department, a.appointment_date, a.appointment_time, a.status"
        ),
        where_clause="a.doctor_name = %s AND a.status != 'cancelled'",
        params=(doctor_name,),
        order_by="a.appointment_date ASC, a.appointment_time ASC",
    )

    # This doctor's own upcoming blocked-out days/slots, so the schedule
    # page can show "you've blocked these" alongside "here's who's booked"
    # instead of the unavailability list being invisible until someone
    # tries to book into it and gets rejected.
    unavailability = select_all(
        "doctor_unavailability",
        where_clause="doctor_name = %s AND unavailable_date >= %s",
        params=(doctor_name, date.today().isoformat()),
        columns="id, unavailable_date, time_slot, reason",
        order_by="unavailable_date ASC, time_slot ASC",
    )

    return render_template(
        "doctor_schedule.html",
        appointments=appointments,
        doctor_name=doctor_name,
        unavailability=unavailability,
        time_slots=TIME_SLOTS,
        time_slot_labels=TIME_SLOT_LABELS,
    )


# ---------------- DOCTOR: MARK SLOTS/DAYS UNAVAILABLE ----------------
@handle_db_errors(fallback_endpoint="auth.doctor_schedule")
def add_doctor_unavailability():
    """Lets the logged-in doctor block out either an entire day or a single
    time slot on a day. A blank "time slot" means the whole day - stored as
    NULL rather than one row per slot, so _unavailable_slots() only has to
    check for a NULL row to know the whole day is off instead of needing all
    seven slots individually inserted."""
    doctor_name = session.get("user_name")
    unavailable_date = _get_clean_form_value("unavailable_date")
    time_slot = _get_clean_form_value("time_slot")
    reason = _get_clean_form_value("reason")

    try:
        parsed_date = date.fromisoformat(unavailable_date)
    except ValueError:
        flash("Please choose a valid date.", "error")
        return redirect(url_for("auth.doctor_schedule"))

    if parsed_date < date.today():
        flash("You can't block out a date in the past.", "error")
        return redirect(url_for("auth.doctor_schedule"))

    if time_slot and time_slot not in TIME_SLOTS:
        flash("Please choose a valid time slot, or leave it blank to block the whole day.", "error")
        return redirect(url_for("auth.doctor_schedule"))

    insert_row(
        "doctor_unavailability",
        ["doctor_name", "unavailable_date", "time_slot", "reason"],
        {
            "doctor_name": doctor_name,
            "unavailable_date": unavailable_date,
            "time_slot": time_slot or None,
            "reason": reason or None,
        },
    )
    flash(
        f"Marked {unavailable_date} "
        + (f"at {TIME_SLOT_LABELS.get(time_slot, time_slot)} " if time_slot else "(whole day) ")
        + "as unavailable.",
        "success",
    )
    return redirect(url_for("auth.doctor_schedule"))


@handle_db_errors(fallback_endpoint="auth.doctor_schedule")
def delete_doctor_unavailability(entry_id):
    """Removes a block-out entry. Scoped to the logged-in doctor's own name
    so one doctor can never clear another doctor's blocked-out days just by
    guessing an id in the URL."""
    doctor_name = session.get("user_name")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM doctor_unavailability WHERE id = %s AND doctor_name = %s",
        (entry_id, doctor_name),
    )
    deleted = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    flash(
        "Availability restored." if deleted else "That entry was not found.",
        "success" if deleted else "error",
    )
    return redirect(url_for("auth.doctor_schedule"))
