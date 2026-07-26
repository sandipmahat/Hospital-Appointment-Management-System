import unittest
from apps import create_apps


class TemplateRenderingTests(unittest.TestCase):
    def setUp(self):
        self.app = create_apps(
            {
                "TESTING": True,
                "INIT_DB": False,
                "CSRF_ENABLED": False,
                "SECRET_KEY": "test-secret",
            }
        )

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

    def test_home_page_is_public_and_links_to_login(self):
        with self.app.test_client() as client:
            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('href="/login"', body)
        self.assertIn("Create an account to manage appointments.", body)

    def test_about_page_contains_responsive_design_lesson(self):
        with self.app.test_client() as client:
            response = client.get("/about")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Responsive design matters", body)
        self.assertIn("Viewport meta tag", body)
        self.assertIn("Mobile-first approach", body)

    def test_static_assets_are_served_from_static_folder(self):
        # The real homepage is medhub.html (rendered by GET /); there used to
        # be an unreachable index.html left over from an earlier design that
        # this test rendered directly instead of exercising the live route.
        # It's been removed, along with the placeholder images it referenced.
        with self.app.test_client() as client:
            response = client.get("/")
            rendered_template = response.get_data(as_text=True)

        expected_paths = [
            "/static/css/style.css",
            "/static/css/medhub.css",
            "/static/js/events-alerts.js",
            "/static/js/form-validation.js",
            "/static/images/hospital-photo.jpg",
            "/static/images/doctor-sharma.jpg",
        ]

        for asset_path in expected_paths:
            self.assertIn(asset_path, rendered_template)

        with self.app.test_client() as client:
            for asset_path in expected_paths:
                static_response = client.get(asset_path)
                try:
                    self.assertEqual(static_response.status_code, 200, msg=f"{asset_path} should be served")
                finally:
                    static_response.close()

    def test_login_page_rejects_invalid_email_and_shows_flash_message(self):
        with self.app.test_client() as client:
            response = client.post(
                "/login",
                data={"login_as": "user", "email": "not-an-email", "password": "123456"},
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Please enter a valid email address.", body)


if __name__ == "__main__":
    unittest.main()
