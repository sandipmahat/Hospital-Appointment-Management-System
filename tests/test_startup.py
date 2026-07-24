import unittest
from unittest.mock import patch

from apps import create_apps


class StartupConfigurationTests(unittest.TestCase):
    @patch("apps.create_tables", side_effect=RuntimeError("database unavailable"))
    def test_create_apps_continues_when_db_init_fails(self, mock_create_tables):
        app = create_apps(
            {
                "TESTING": True,
                "INIT_DB": True,
                "CSRF_ENABLED": False,
                "SECRET_KEY": "test-secret",
            }
        )

        self.assertIsNotNone(app)
        mock_create_tables.assert_called_once()


if __name__ == "__main__":
    unittest.main()
