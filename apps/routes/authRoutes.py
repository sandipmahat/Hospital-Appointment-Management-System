from flask import Blueprint
from apps.controllers import authController
from apps.auth import login_required, admin_required

bp = Blueprint("auth", __name__)

bp.route("/")(login_required(authController.home))
bp.route("/login", methods=["GET", "POST"])(authController.login)
bp.route("/register", methods=["GET", "POST"])(authController.register)
bp.route("/contact")(authController.contact)
bp.route("/about")(authController.about)
bp.route("/dashboard")(admin_required(authController.dashboard))
bp.route("/logout")(login_required(authController.logout))
bp.route("/profile", methods=["GET", "POST"])(login_required(authController.profile))


def register():
    return bp
