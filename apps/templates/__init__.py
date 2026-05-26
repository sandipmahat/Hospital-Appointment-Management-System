import os
from flask import Flask, config, render_temlate, session, request, abort
from app.database import create_tables

def create_app():
    app=Flask(__name__)
    app.secret_key = config.SECRET_KEY
    
    #initiallize database tables
    with app.app_context():
        creat_tables()

    @app.before_request
    def csfr_protect():
        if "csfr_token" not in session:
            session["csrf_token"] = os.urandom(16).hex()

        #verify CSRF token for POST requests
        if request.method == "POST":
            token = request.form .get("csrf_token")
            form_token = request.form.get("csrf_token")

            if not token or not form_token or token != form_token:
                abort(403)