from flask import Flask
from apps.routes import authRoutes
import config

def create_apps():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = config.SECRET_KEY
    app.register_blueprint(authRoutes.register())
    return app
