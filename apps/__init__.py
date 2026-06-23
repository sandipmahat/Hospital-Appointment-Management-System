import secrets

from flask import Flask, abort, render_template, request, session
from apps.routes import authRoutes
from apps.database import create_tables
from config import Config


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

        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)

        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            submitted_token = request.form.get("csrf_token") or request.headers.get(
                "X-CSRF-Token"
            )
            if not submitted_token or not secrets.compare_digest(
                submitted_token, session["csrf_token"]
            ):
                abort(403)

    app.jinja_env.globals["csrf_token"] = lambda: session.get("csrf_token", "")

    # Custom error pages
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    return app
