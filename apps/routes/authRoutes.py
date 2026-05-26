from flask import Blueprint
from apps.controllers import authController

bp = Blueprint("auth", __name__)

def register():
    bp.route("/login", methods=["GET", "POST"])(authController.login)
    bp.route("/register", methods=["GET", "POST"])(authController.register)
    bp.route("/home")(authController.home)
    bp.route("/contact")(authController.contact)
    return bp