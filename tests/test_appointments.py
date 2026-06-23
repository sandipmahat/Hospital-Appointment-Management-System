import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from apps import create_apps


class AppointmentCrudTests(unittest.TestCase):
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
        with self.client.session_transaction() as session:
            session["user_id"] = 12
            session["user_name"] = "Patient"
            session["user_role"] = "user"

    def test_create_appointment_uses_authenticated_user(self):
        future_date = (date.today() + timedelta(days=7)).isoformat()
        with patch("apps.controllers.authController.insert_row") as insert_row:
            response = self.client.post(
                "/book-appointment",
                data={
                    "department": "Cardiology",
                    "doctor_name": "Dr. Sharma",
                    "appointment_date": future_date,
                    "appointment_time": "10:30",
                },
            )

        self.assertEqual(response.status_code, 302)
        record = insert_row.call_args.args[2]
        self.assertEqual(record["user_id"], 12)
        self.assertEqual(record["department"], "Cardiology")

    def test_past_appointment_is_rejected(self):
        past_date = (date.today() - timedelta(days=1)).isoformat()
        with patch("apps.controllers.authController.insert_row") as insert_row:
            response = self.client.post(
                "/book-appointment",
                data={
                    "department": "Cardiology",
                    "doctor_name": "Dr. Sharma",
                    "appointment_date": past_date,
                    "appointment_time": "10:30",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Appointments cannot be booked in the past.", response.data)
        insert_row.assert_not_called()

    def test_edit_denies_access_to_another_users_appointment(self):
        with patch(
            "apps.controllers.authController.select_one", return_value=None
        ) as select_one:
            response = self.client.get("/appointments/99/edit")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(select_one.call_args.args[2], (99, 12))

    def test_delete_scopes_query_to_authenticated_user(self):
        cursor = MagicMock()
        cursor.rowcount = 1
        connection = MagicMock()
        connection.cursor.return_value = cursor

        with patch(
            "apps.controllers.authController.get_connection",
            return_value=connection,
        ):
            response = self.client.post("/appointments/8/delete")

        self.assertEqual(response.status_code, 302)
        query_params = cursor.execute.call_args.args[1]
        self.assertEqual(query_params, (8, 12))
        connection.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
