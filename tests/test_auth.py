import unittest
from unittest.mock import MagicMock, patch

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

    def test_registration_hashes_password_and_uses_user_role(self):
        connection = self._connection_with_user(None)
        with (
            patch(
                "apps.controllers.authController.get_connection",
                return_value=connection,
            ),
            patch("apps.controllers.authController.insert_row") as insert_row,
        ):
            response = self.client.post(
                "/register",
                data={
                    "name": "Alice Patient",
                    "email": "ALICE@example.com",
                    "password": "Secure123",
                    "confirmPassword": "Secure123",
                },
            )

        self.assertEqual(response.status_code, 302)
        inserted = insert_row.call_args.args[2]
        self.assertEqual(inserted["email"], "alice@example.com")
        self.assertEqual(inserted["role"], "user")
        self.assertNotEqual(inserted["password"], "Secure123")

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
                data={"email": "ALICE@example.com", "password": "Secure123"},
            )

        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertEqual(session["user_id"], 4)
            self.assertTrue(session.permanent)

        response = self.client.get("/logout")
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_invalid_login_does_not_create_session(self):
        with patch(
            "apps.controllers.authController.get_connection",
            return_value=self._connection_with_user(None),
        ):
            response = self.client.post(
                "/login",
                data={"email": "missing@example.com", "password": "wrongpass"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Wrong email or password.", response.data)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_protected_route_redirects_anonymous_user(self):
        response = self.client.get("/my-appointments")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()
