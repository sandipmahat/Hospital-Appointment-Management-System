from functools import wraps
from flask import session, redirect, url_for, flash


def login_user(user):
    """
    Set session values for an authenticated user.
    Expects a dict-like `user` with keys: id, name, email, and optional role.
    """
    session["user_id"] = user["id"]
    session["user_name"] = user.get("name")
    session["user_email"] = user.get("email")
    session["user_role"] = user.get("role", "user")
    session.permanent = True


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))

        if session.get("user_role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("auth.home"))

        return view(*args, **kwargs)

    return wrapped
