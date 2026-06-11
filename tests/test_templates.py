import unittest
from unittest.mock import patch

from apps import create_apps


class TemplateRenderingTests(unittest.TestCase):
    def setUp(self):
        with patch("apps.create_tables", return_value=None):
            self.app = create_apps()
        self.app.testing = True

    def test_home_page_renders_dynamic_jinja_content_and_escapes_user_input(self):
        with self.app.test_client() as client:
            with client.session_transaction() as session:
                session["user_id"] = 1
                session["user_name"] = "<script>alert('x')</script>"
                session["user_role"] = "user"

            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Welcome back", body)
        self.assertIn("Book appointments quickly", body)
        self.assertIn("&lt;script&gt;", body)
        self.assertNotIn("<script>alert('x')</script>", body)

    def test_about_page_contains_responsive_design_lesson(self):
        with self.app.test_client() as client:
            response = client.get("/about")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Responsive design matters", body)
        self.assertIn("Viewport meta tag", body)
        self.assertIn("Mobile-first approach", body)


if __name__ == "__main__":
    unittest.main()
