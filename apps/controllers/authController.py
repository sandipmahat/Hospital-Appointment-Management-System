from flask import render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from apps.database import get_connection


# ---------------- HOME PAGE ----------------
def home():
    return render_template("home.html")


# ---------------- CONTACT PAGE ----------------
def contact():
    return render_template("contact.html")


# ---------------- LOGIN FUNCTION ----------------
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # basic check
        if not email or not password:
            flash("Please fill in all the fields", "error")
            return render_template("login.html")

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        # check user and password
        if user and check_password_hash(user[3], password):
            session["user_id"] = user[0]
            session["user_name"] = user[1]

            flash("Login successful!", "success")
            return redirect(url_for("auth.dashboard"))
        else:
            flash("Wrong email or password", "error")

    return render_template("login.html")


# ---------------- REGISTER FUNCTION ----------------
def register():
    # if already logged in, go to dashboard
    if session.get("user_id"):
        return redirect(url_for("auth.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # simple validation
        if not name or not email or not password:
            flash("All fields are required", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password should be at least 6 characters", "error")
            return render_template("register.html")

        conn = get_connection()
        cursor = conn.cursor()

        # check if email already exists
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("This email is already registered", "error")
            return render_template("register.html")

        # hash password before saving
        hashed_password = generate_password_hash(password)

        # insert user into database
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


# ---------------- DASHBOARD ----------------
def dashboard():
    # check login
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    return render_template("dashboard.html")