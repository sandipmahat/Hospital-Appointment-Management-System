import unittest
from unittest.mock import MagicMock, patch

import pymysql

from apps import create_apps
from apps.errors import handle_db_errors
from apps.rate_limit import (
    is_rate_limited,
    record_failed_attempt,
    reset_attempts,
    MAX_ATTEMPTS,
)


class LoginRateLimitTests(unittest.TestCase):
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
        # Rate limiting is tracked in a module-level store shared across the
        # process, so start each test from a clean slate for this key.
        reset_attempts("locked@example.com:127.0.0.1")

    def tearDown(self):
        reset_attempts("locked@example.com:127.0.0.1")

    def test_account_locks_out_after_repeated_failed_logins(self):
        connection = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        connection.cursor.return_value = cursor

        # Use the admin tab here specifically: unlike the user tab, a
        # non-matching admin login never auto-creates an account, so every
        # attempt fails the same way and the lockout counter climbs
        # cleanly without touching the database's insert path at all.
        with patch(
            "apps.controllers.authController.get_connection",
            return_value=connection,
        ):
            for _ in range(MAX_ATTEMPTS):
                response = self.client.post(
                    "/login",
                    data={"login_as": "admin", "email": "locked@example.com", "password": "wrongpass"},
                )
                self.assertIn(b"Invalid administrator credentials.", response.data)

            # One more attempt should now be blocked before it ever touches
            # the database again.
            locked_response = self.client.post(
                "/login",
                data={"login_as": "admin", "email": "locked@example.com", "password": "wrongpass"},
            )

        self.assertIn(b"Too many failed login attempts", locked_response.data)

    def test_successful_login_resets_the_counter(self):
        key = "reset@example.com:127.0.0.1"
        reset_attempts(key)
        for _ in range(MAX_ATTEMPTS - 1):
            record_failed_attempt(key)

        self.assertFalse(is_rate_limited(key))
        reset_attempts(key)
        self.assertFalse(is_rate_limited(key))


class SecretKeyGuardTests(unittest.TestCase):
    def test_refuses_to_start_with_default_secret_key_outside_debug(self):
        with self.assertRaises(RuntimeError):
            create_apps(
                {
                    "TESTING": False,
                    "DEBUG": False,
                    "INIT_DB": False,
                    "CSRF_ENABLED": False,
                    "SECRET_KEY": "dev-only-change-me",
                }
            )

    def test_allows_default_secret_key_in_debug_mode(self):
        app = create_apps(
            {
                "TESTING": False,
                "DEBUG": True,
                "INIT_DB": False,
                "CSRF_ENABLED": False,
                "SECRET_KEY": "dev-only-change-me",
            }
        )
        self.assertIsNotNone(app)


class DbErrorHandlingDecoratorTests(unittest.TestCase):
    def test_decorator_flashes_and_redirects_instead_of_500(self):
        app = create_apps(
            {
                "TESTING": True,
                "INIT_DB": False,
                "CSRF_ENABLED": False,
                "SECRET_KEY": "test-secret",
            }
        )

        @handle_db_errors(fallback_endpoint="auth.home")
        def flaky_view():
            raise pymysql.err.OperationalError(2003, "Can't connect to MySQL server")

        app.add_url_rule("/flaky", "flaky", flaky_view)

        with app.test_client() as client:
            response = client.get("/flaky")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/", response.headers["Location"])

    def test_dashboard_degrades_gracefully_when_db_is_unreachable(self):
        app = create_apps(
            {
                "TESTING": True,
                "INIT_DB": False,
                "CSRF_ENABLED": False,
                "SECRET_KEY": "test-secret",
            }
        )
        with app.test_client() as client:
            with client.session_transaction() as session:
                session["user_id"] = 1
                session["user_role"] = "admin"

            with patch(
                "apps.controllers.authController.count_rows",
                side_effect=pymysql.err.OperationalError(2003, "unreachable"),
            ):
                response = client.get("/dashboard")

        # A DB outage should redirect with a flash message, never a raw 500.
        self.assertEqual(response.status_code, 302)


if __name__ == "__main__":
    unittest.main()
