import os
import unittest
from unittest.mock import patch

import bcrypt


os.environ["SECRET_KEY"] = "unit-test-secret-key-that-is-long-enough"
os.environ["FLASK_DEBUG"] = "1"
with patch("mysql.connector.pooling.MySQLConnectionPool", return_value=object()):
    import app as portal


class StudentPortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = bcrypt.hashpw(b"correct-password", bcrypt.gensalt()).decode("utf-8")

    def setUp(self):
        self.client = portal.app.test_client()
        self.client.get("/api/student/me")
        self.csrf_token = self.client.get_cookie("XSRF-TOKEN").value

    def csrf_headers(self):
        return {"X-XSRF-TOKEN": self.csrf_token}

    def sign_in(self, run_query):
        run_query.return_value = [{"id": 41, "password_hash": self.password_hash}]
        return self.client.post(
            "/api/auth/login",
            json={"empId": "EMP-41", "password": "correct-password"},
            headers=self.csrf_headers(),
        )

    def test_login_rejects_missing_csrf_token(self):
        response = self.client.post(
            "/api/auth/login",
            json={"empId": "EMP-41", "password": "correct-password"},
        )
        self.assertEqual(response.status_code, 403)

    def test_login_rejects_non_object_json(self):
        response = self.client.post(
            "/api/auth/login",
            json=["not", "an", "object"],
            headers=self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 400)

    def test_student_results_are_scoped_to_signed_in_student(self):
        result = {
            "courseCode": "CS101",
            "courseName": "Introduction to Computing",
            "semester": "Semester 1",
            "academicYear": "2026",
            "grade": "A",
            "publishedAt": None,
        }
        with patch.object(portal, "run_query", side_effect=[
            [{"id": 41, "password_hash": self.password_hash}],
            [result],
        ]) as run_query:
            login_response = self.sign_in(run_query)
            results_response = self.client.get("/api/student/results")

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(results_response.status_code, 200)
        self.assertEqual(results_response.json["results"], [result])
        self.assertEqual(run_query.call_args_list[1].args[1], (41,))

    def test_profile_update_requires_authentication(self):
        response = self.client.put(
            "/api/student/profile",
            json={"email": "student@example.edu", "phone": "", "address": ""},
            headers=self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
