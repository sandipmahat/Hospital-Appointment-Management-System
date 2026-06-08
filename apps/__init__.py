from flask import Flask, render_template
from apps.routes import authRoutes
import config

from apps.database import create_tables

def create_apps():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = config.SECRET_KEY

    # Ensure database and tables exist before registering routes
    try:
        create_tables()
    except Exception as e:
        # Print useful message and re-raise so startup fails loudly during development
        print("Failed to prepare database:", e)
        raise

    app.register_blueprint(authRoutes.register())

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
