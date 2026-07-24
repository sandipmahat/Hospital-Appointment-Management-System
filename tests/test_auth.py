import unittest
from unittest.mock import MagicMock, patch

import pymysql
from werkzeug.security import generate_password_hash

from apps import create_apps


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_apps(
            {
                "TESTING": True,
                "INIT_DB": False,
                "CSRF_ENABLED": False,
                "SECRET_KEY": "test-secret",
            }
        )
        self.client = self.app.test_client()

    def _connection_with_user(self, user):
        cursor = MagicMock()
        cursor.fetchone.return_value = user
        connection = MagicMock()
        connection.cursor.return_value = cursor
        return connection

    # ---- User tab: unknown email auto-creates an account ----
    def test_user_login_with_unknown_email_creates_account(self):
        connection = self._connection_with_user(None)
        with (
            patch(
                "apps.controllers.authController.get_connection",
                return_value=connection,
            ),
            patch("apps.controllers.authController.insert_row", return_value=99) as insert_row,
        ):
            response = self.client.post(
                "/login",
                data={
                    "login_as": "user",
                    "email": "NEWPATIENT@example.com",
                    "password": "Secure123",
                },
            )

        self.assertEqual(response.status_code, 302)
        inserted = insert_row.call_args.args[2]
        self.assertEqual(inserted["email"], "newpatient@example.com")
        self.assertEqual(inserted["role"], "user")
        self.assertNotEqual(inserted["password"], "Secure123")
        with self.client.session_transaction() as session:
            self.assertEqual(session["user_id"], 99)
            self.assertEqual(session["user_role"], "user")

    def test_user_login_auto_create_rejects_short_password(self):
        with patch(
            "apps.controllers.authController.get_connection",
            return_value=self._connection_with_user(None),
        ), patch("apps.controllers.authController.insert_row") as insert_row:
            response = self.client.post(
                "/login",
                data={"login_as": "user", "email": "shortpass@example.com", "password": "abc"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"at least 6 characters", response.data)
        insert_row.assert_not_called()

    # ---- User tab: existing account logs in / logs out normally ----
    def test_login_creates_session_and_logout_clears_it(self):
        user = {
            "id": 4,
            "name": "Alice",
            "email": "alice@example.com",
            "password": generate_password_hash("Secure123"),
            "role": "user",
        }
        with patch(
            "apps.controllers.authController.get_connection",
            return_value=self._connection_with_user(user),
        ):
            response = self.client.post(
                "/login",
                data={"login_as": "user", "email": "ALICE@example.com", "password": "Secure123"},
            )

        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertEqual(session["user_id"], 4)
            self.assertTrue(session.permanent)

        response = self.client.post("/logout")
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_user_login_wrong_password_does_not_create_session(self):
        user = {
            "id": 4,
            "name": "Alice",
            "email": "alice@example.com",
            "password": generate_password_hash("Secure123"),
            "role": "user",
        }
        with patch(
            "apps.controllers.authController.get_connection",
            return_value=self._connection_with_user(user),
        ):
            response = self.client.post(
                "/login",
                data={"login_as": "user", "email": "alice@example.com", "password": "wrongpass"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Wrong email or password.", response.data)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    # ---- Doctor tab: only pre-created accounts can log in ----
    def test_doctor_login_without_account_shows_access_denied(self):
        with patch(
            "apps.controllers.authController.get_connection",
            return_value=self._connection_with_user(None),
        ):
            response = self.client.post(
                "/login",
                data={"login_as": "doctor", "email": "notadoctor@example.com", "password": "whatever1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Access Denied", response.data)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_doctor_login_with_valid_account_succeeds(self):
        doctor = {
            "id": 7,
            "name": "Dr. Rajesh Sharma",
            "email": "rajesh.sharma@sandyhub.com.np",
            "password": generate_password_hash("Doctor@123"),
            "role": "doctor",
        }
        with patch(
            "apps.controllers.authController.get_connection",
            return_value=self._connection_with_user(doctor),
        ):
            response = self.client.post(
                "/login",
                data={"login_as": "doctor", "email": doctor["email"], "password": "Doctor@123"},
            )

        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertEqual(session["user_id"], 7)
            self.assertEqual(session["user_role"], "doctor")

    # ---- Admin tab: never auto-creates, only the seeded account works ----
    def test_admin_login_without_account_is_rejected(self):
        with patch(
            "apps.controllers.authController.get_connection",
            return_value=self._connection_with_user(None),
        ), patch("apps.controllers.authController.insert_row") as insert_row:
            response = self.client.post(
                "/login",
                data={"login_as": "admin", "email": "notanadmin@example.com", "password": "whatever1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid administrator credentials.", response.data)
        insert_row.assert_not_called()

    # ---- Cross-role protection: a doctor's email can't log in via the user tab ----
    def test_wrong_tab_for_existing_role_is_rejected(self):
        doctor = {
            "id": 7,
            "name": "Dr. Rajesh Sharma",
            "email": "rajesh.sharma@sandyhub.com.np",
            "password": generate_password_hash("Doctor@123"),
            "role": "doctor",
        }
        with patch(
            "apps.controllers.authController.get_connection",
            return_value=self._connection_with_user(doctor),
        ):
            response = self.client.post(
                "/login",
                data={"login_as": "user", "email": doctor["email"], "password": "Doctor@123"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"different type of account", response.data)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_login_handles_database_connection_failure(self):
        with patch(
            "apps.controllers.authController.get_connection",
            side_effect=pymysql.err.OperationalError(1045, "Access denied for user 'root'@'localhost' (using password: YES)"),
        ):
            response = self.client.post(
                "/login",
                data={"login_as": "user", "email": "alice@example.com", "password": "Secure123"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Database connection is unavailable.", response.data)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_protected_route_redirects_anonymous_user(self):
        response = self.client.get("/my-appointments")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_register_route_no_longer_exists(self):
        response = self.client.get("/register")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
