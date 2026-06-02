from flask import Blueprint
from apps.controllers import authController

bp = Blueprint("auth", __name__)

bp.route("/")(authController.home)
bp.route("/login", methods=["GET", "POST"])(authController.login)
bp.route("/register", methods=["GET", "POST"])(authController.register)
bp.route("/contact")(authController.contact)
bp.route("/dashboard")(authController.dashboard)
bp.route("/logout")(authController.logout)
bp.route("/profile", methods=["GET", "POST"])(authController.profile)


def register():
    return bp
