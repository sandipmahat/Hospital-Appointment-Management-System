from flask import render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from apps.database import get_connection


# ---------------- HOME PAGE ----------------
def home():
    return render_template("medhub.html", name=session.get("user_name"))


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
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please fill in all fields.", "error")
            return render_template("login.html")

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

    return render_template("login.html")


# ---------------- REGISTER FUNCTION ----------------
def register():
    if session.get("user_id"):
        if session.get("user_role") == "admin":
            return redirect(url_for("auth.dashboard"))
        return redirect(url_for("auth.home"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password should be at least 6 characters.", "error")
            return render_template("register.html")

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            cursor.close()
            conn.close()
            flash("This email is already registered.", "error")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (name, email, hashed_password),
        )
        conn.commit()
        cursor.close()
        conn.close()

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

    cursor.close()
    conn.close()

    return render_template("dashboard.html", users=users)


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
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        current_password = request.form.get("currentPassword", "")
        new_password = request.form.get("newPassword", "")
        confirm_password = request.form.get("confirmPassword", "")

        if not name or not email:
            flash("Name and email are required.", "error")
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
                return render_template("profile.html", user=user)

            if new_password != confirm_password:
                flash("New passwords do not match.", "error")
                cursor.close()
                conn.close()
                return render_template("profile.html", user=user)

            if len(new_password) < 6:
                flash("New password must be at least 6 characters.", "error")
                cursor.close()
                conn.close()
                return render_template("profile.html", user=user)

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
    return render_template("profile.html", user=user)
