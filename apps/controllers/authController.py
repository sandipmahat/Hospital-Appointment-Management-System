import re

from flask import render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from apps.database import get_connection, insert_row, select_one, select_all

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _get_clean_form_value(field_name, default=""):
    return request.form.get(field_name, default).strip()


def _is_valid_email(email):
    return bool(EMAIL_PATTERN.fullmatch(email))


# ---------------- HOME PAGE ----------------
def home():
    features = [
        "Book appointments quickly",
        "Track your visit history",
        "Get reminders for upcoming care",
    ]
    return render_template(
        "medhub.html",
        name=session.get("user_name"),
        features=features,
        is_authenticated=bool(session.get("user_id")),
    )


# ---------------- ABOUT PAGE ----------------
def about():
    aboutcompany = [
        {"name": "softwarica", "address": "Lalitpur, Nepal"},
        {"name": "another company", "address": "Kathmandu, Nepal"},
    ]
    return render_template("about.html", aboutcompany=aboutcompany)


# ---------------- CONTACT PAGE ----------------
def contact():
    return render_template("contact.html")


# ---------------- LOGIN FUNCTION ----------------
def login():
    if session.get("user_id"):
        if session.get("user_role") == "admin":
            return redirect(url_for("auth.dashboard"))
        return redirect(url_for("auth.home"))

    if request.method == "POST":
        email = _get_clean_form_value("email", "").lower()
        password = _get_clean_form_value("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "error")
            return render_template("login.html", submitted_email=email)

        if not _is_valid_email(email):
            flash("Please enter a valid email address.", "error")
            return render_template("login.html", submitted_email=email)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            session["user_role"] = user.get("role", "user")

            flash("Login successful!", "success")
            if session["user_role"] == "admin":
                return redirect(url_for("auth.dashboard"))

            return redirect(url_for("auth.home"))

        flash("Wrong email or password.", "error")

    return render_template(
        "login.html",
        submitted_email=_get_clean_form_value("email", "").lower(),
    )


# ---------------- REGISTER FUNCTION ----------------
def register():
    if session.get("user_id"):
        if session.get("user_role") == "admin":
            return redirect(url_for("auth.dashboard"))
        return redirect(url_for("auth.home"))

    if request.method == "POST":
        name = _get_clean_form_value("name", "")
        email = _get_clean_form_value("email", "").lower()
        password = _get_clean_form_value("password", "")
        confirm_password = _get_clean_form_value("confirmPassword", "")

        if not name or not email or not password or not confirm_password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if not _is_valid_email(email):
            flash("Please enter a valid email address.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password should be at least 6 characters.", "error")
            return render_template("register.html")

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            cursor.close()
            conn.close()
            flash("This email is already registered.", "error")
            return render_template("register.html")

        cursor.close()
        conn.close()

        hashed_password = generate_password_hash(password)
        # Use insert_row to avoid mass-assignment
        insert_row(
            "users",
            ["name", "email", "password", "role"],
            {"name": name, "email": email, "password": hashed_password, "role": "user"},
        )

        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


# ---------------- LOGOUT ----------------
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


# ---------------- DASHBOARD ----------------
def dashboard():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    if session.get("user_role") != "admin":
        flash("You do not have permission to access the dashboard.", "error")
        return redirect(url_for("auth.home"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, name, email, role, created_at FROM users ORDER BY created_at DESC"
    )
    users = cursor.fetchall()

    cursor.execute(
        "SELECT a.id, a.user_id, u.name AS patient_name, u.email AS patient_email, a.doctor_name, a.department, a.appointment_date, a.appointment_time, a.status, a.created_at "
        "FROM appointments a "
        "LEFT JOIN users u ON u.id = a.user_id "
        "ORDER BY a.appointment_date ASC, a.appointment_time ASC"
    )
    appointments = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("dashboard.html", users=users, appointments=appointments)


# ---------------- ADMIN APPOINTMENTS ----------------
def admin_appointments():
    if request.method == "POST":
        appointment_id = _get_clean_form_value("appointment_id")
        action = _get_clean_form_value("action")
        if appointment_id and action in {"approve", "cancel"}:
            status = "approved" if action == "approve" else "cancelled"
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE appointments SET status = %s WHERE id = %s",
                (status, appointment_id),
            )
            affected = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()
            if affected:
                flash(f"Appointment {status}.", "success")
            else:
                flash("Unable to update appointment status.", "error")
        else:
            flash("Invalid appointment action.", "error")

    return dashboard()


# ---------------- BOOK APPOINTMENT ----------------
def book_appointment():
    departments = [
        "Cardiology",
        "Neurology",
        "Pediatrics",
        "Orthopedics",
        "Dermatology",
        "General Medicine",
    ]
    doctors = [
        "Dr. Sharma",
        "Dr. Koirala",
        "Dr. Singh",
        "Dr. Thapa",
        "Dr. Kumar",
        "Dr. Joshi",
    ]

    if request.method == "POST":
        department = _get_clean_form_value("department", "")
        doctor_name = _get_clean_form_value("doctor_name", "")
        appointment_date = _get_clean_form_value("appointment_date", "")
        appointment_time = _get_clean_form_value("appointment_time", "")

        if not department or not doctor_name or not appointment_date or not appointment_time:
            flash("All appointment fields are required.", "error")
            return render_template(
                "book_appointment.html",
                departments=departments,
                doctors=doctors,
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
                "doctor_name": doctor_name,
                "department": department,
                "appointment_date": appointment_date,
                "appointment_time": appointment_time,
            },
        )

        flash("Appointment booked successfully. Your request is pending approval.", "success")
        return redirect(url_for("auth.my_appointments"))

    return render_template(
        "book_appointment.html",
        departments=departments,
        doctors=doctors,
    )


# ---------------- MY APPOINTMENTS ----------------
def my_appointments():
    user_id = session.get("user_id")
    appointments = select_all(
        "appointments",
        where_clause="user_id = %s",
        params=(user_id,),
        columns="id, doctor_name, department, appointment_date, appointment_time, status, created_at",
        order_by="appointment_date ASC, appointment_time ASC",
    )

    return render_template("my_appointments.html", appointments=appointments)


# ---------------- PROFILE ----------------
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
