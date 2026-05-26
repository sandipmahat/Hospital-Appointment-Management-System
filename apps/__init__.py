from flask import Flask
from apps.routes import authRoutes   

def create_apps():
    apps = Flask(__name__)
    apps.register_blueprint(authRoutes.register())
    return apps;