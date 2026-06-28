import re
import unittest
from pathlib import Path

from flask import Response

from apps import create_apps


class CsrfProtectionTests(unittest.TestCase):
    def setUp(self):
        self.app = create_apps(
            {
                "TESTING": True,
                "INIT_DB": False,
                "CSRF_ENABLED": True,
                "SECRET_KEY": "test-secret",
            }
        )
        self.app.add_url_rule(
            "/csrf-test",
            "csrf_test",
            lambda: Response(status=204),
            methods=["POST"],
        )
        self.client = self.app.test_client()

    def _csrf_token(self):
        self.client.get("/login")
        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def test_get_generates_token_and_form_contains_it(self):
        response = self.client.get("/login")
        with self.client.session_transaction() as session:
            token = session["csrf_token"]

        self.assertIn(
            f'name="csrf_token" value="{token}"',
            response.get_data(as_text=True),
        )

    def test_valid_form_token_allows_request(self):
        response = self.client.post(
            "/csrf-test",
            data={"csrf_token": self._csrf_token()},
        )

        self.assertEqual(response.status_code, 204)

    def test_missing_token_returns_403(self):
        response = self.client.post("/csrf-test")

        self.assertEqual(response.status_code, 403)
        self.assertIn(b"security token is missing or invalid", response.data)

    def test_invalid_token_returns_403(self):
        response = self.client.post(
            "/csrf-test",
            data={"csrf_token": "attacker-controlled-token"},
        )

        self.assertEqual(response.status_code, 403)

    def test_header_token_allows_non_form_request(self):
        response = self.client.post(
            "/csrf-test",
            headers={"X-CSRF-Token": self._csrf_token()},
        )

        self.assertEqual(response.status_code, 204)

    def test_logout_cannot_be_triggered_with_get(self):
        response = self.client.get("/logout")

        self.assertEqual(response.status_code, 405)

    def test_every_html_form_has_hidden_csrf_input(self):
        templates_dir = Path(self.app.root_path, self.app.template_folder)
        form_pattern = re.compile(r"<form\b.*?</form>", re.IGNORECASE | re.DOTALL)
        csrf_pattern = re.compile(
            r'<input\b(?=[^>]*\btype=["\']hidden["\'])'
            r'(?=[^>]*\bname=["\']csrf_token["\'])[^>]*>',
            re.IGNORECASE,
        )

        forms_checked = 0
        for template in templates_dir.rglob("*.html"):
            content = template.read_text(encoding="utf-8")
            for form in form_pattern.findall(content):
                forms_checked += 1
                self.assertRegex(
                    form,
                    csrf_pattern,
                    msg=f"Missing CSRF field in {template}",
                )

        self.assertGreater(forms_checked, 0)


if __name__ == "__main__":
    unittest.main()
