from flask import Flask

def create_app():
    app = Flask(__name__)

    # required for session and flash messages
    app.secret_key = "your_secret_key"

    # import and register routes
    from apps.routes.auth_routes import bp as auth_bp
    app.register_blueprint(auth_bp)

    return app