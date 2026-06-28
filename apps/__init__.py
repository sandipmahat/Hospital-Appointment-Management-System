import secrets

from flask import Flask, abort, render_template, request, session
from apps.routes import authRoutes
from apps.database import create_tables
from config import Config


CSRF_SESSION_KEY = "csrf_token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def generate_csrf_token():
    """Return the current session's token, creating a cryptographically random one."""
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def create_apps(test_config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    app.jinja_env.autoescape = True

    if app.config["INIT_DB"]:
        create_tables()

    app.register_blueprint(authRoutes.register())

    @app.before_request
    def csrf_protect():
        if not app.config["CSRF_ENABLED"]:
            return None

        expected_token = generate_csrf_token()

        if request.method in UNSAFE_METHODS:
            submitted_token = request.form.get("csrf_token") or request.headers.get(
                "X-CSRF-Token"
            )
            if not submitted_token or not secrets.compare_digest(
                submitted_token, expected_token
            ):
                abort(
                    403,
                    description=(
                        "Your security token is missing or invalid. "
                        "Refresh the page and try again."
                    ),
                )

    app.jinja_env.globals["csrf_token"] = generate_csrf_token

    # Custom error pages
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html", error=e), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("errors/500.html"), 500

    return app
