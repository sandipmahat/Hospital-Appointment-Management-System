from flask import Blueprint
from apps.controllers import authController
from apps.auth import login_required, admin_required, doctor_required

bp = Blueprint("auth", __name__)

bp.route("/")(authController.home)
bp.route("/login", methods=["GET", "POST"])(authController.login)
bp.route("/login/verify-2fa", methods=["GET", "POST"])(authController.verify_admin_2fa)
bp.route("/forgot-password", methods=["GET", "POST"])(authController.forgot_password)
bp.route("/reset-password/<token>", methods=["GET", "POST"])(authController.reset_password)
bp.route("/contact")(authController.contact)
bp.route("/about")(authController.about)
bp.route("/dashboard")(admin_required(authController.dashboard))
bp.route("/admin/appointments", methods=["GET", "POST"])(admin_required(authController.admin_appointments))
bp.route("/admin/doctors", methods=["GET", "POST"])(admin_required(authController.manage_doctors))
bp.route("/admin/doctors/<int:user_id>/edit", methods=["GET", "POST"])(
    admin_required(authController.edit_doctor_profile)
)
bp.route("/admin/users/<int:user_id>/reset-password", methods=["POST"])(
    admin_required(authController.admin_reset_password)
)
bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])(
    admin_required(authController.admin_delete_user)
)
bp.route("/admin/appointments/export.csv")(admin_required(authController.export_appointments_csv))
bp.route("/admin/notifications")(admin_required(authController.notification_log))
bp.route("/admin/security/2fa", methods=["GET", "POST"])(admin_required(authController.totp_setup))
bp.route("/doctor/schedule")(doctor_required(authController.doctor_schedule))
bp.route("/doctor/unavailability", methods=["POST"])(doctor_required(authController.add_doctor_unavailability))
bp.route("/doctor/unavailability/<int:entry_id>/delete", methods=["POST"])(
    doctor_required(authController.delete_doctor_unavailability)
)
bp.route("/book-appointment", methods=["GET", "POST"])(login_required(authController.book_appointment))
bp.route("/book-appointment/availability")(login_required(authController.appointment_availability))
bp.route("/my-appointments")(login_required(authController.my_appointments))
bp.route("/appointments/<int:appointment_id>/edit", methods=["GET", "POST"])(
    login_required(authController.edit_appointment)
)
bp.route("/appointments/<int:appointment_id>/delete", methods=["POST"])(
    login_required(authController.delete_appointment)
)
bp.route("/logout", methods=["POST"])(login_required(authController.logout))
bp.route("/profile", methods=["GET", "POST"])(login_required(authController.profile))


def register():
    return bp
