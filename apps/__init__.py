import secrets

from flask import Flask, abort, render_template, request, session
from apps.routes import authRoutes
from apps.database import create_tables
from config import Config


CSRF_SESSION_KEY = "csrf_token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
INSECURE_DEFAULT_SECRET_KEY = "dev-only-change-me"


def _check_secret_key(app):
    """Guard against running with the insecure placeholder SECRET_KEY.

    Always warn loudly so it's impossible to miss in the logs. Only hard-fail
    when the app is being run in a non-debug, non-testing configuration
    (i.e. something closer to a real deployment), so the default coursework
    `python run.py` (debug=True) workflow keeps working without extra setup.
    """
    if app.config.get("SECRET_KEY") != INSECURE_DEFAULT_SECRET_KEY:
        return

    app.logger.warning(
        "SECRET_KEY is using the insecure placeholder value. Set a unique, "
        "random SECRET_KEY in your .env file before deploying this app."
    )

    if not app.config.get("TESTING") and not app.debug:
        raise RuntimeError(
            "Refusing to start: SECRET_KEY is still the insecure default "
            "('dev-only-change-me'). Set a real SECRET_KEY environment "
            "variable (e.g. via `python -c \"import secrets; "
            "print(secrets.token_hex(32))\"`) before running outside debug "
            "mode."
        )


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

    _check_secret_key(app)

    app.jinja_env.autoescape = True

    if app.config["INIT_DB"]:
        try:
            create_tables()
        except Exception as exc:
            app.logger.warning(
                "Database initialization failed during startup; continuing without DB setup: %s",
                exc,
            )

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
