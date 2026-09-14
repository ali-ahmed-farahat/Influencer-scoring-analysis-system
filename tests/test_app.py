import unittest
import os

os.environ["GEMINI_API_KEY"] = ""
os.environ["QWEN_LOCAL_ENABLED"] = "false"

from app import app


class AppRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True)
        cls.client = app.test_client()

    def test_home_route(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Influencer scoring", response.data)

    def test_health_route(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})

    def test_analysis_route(self):
        response = self.client.get("/analyze/HQ-110-HIGH-CONVERSION")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Analysis result", response.data)

    def test_unknown_candidate_route(self):
        response = self.client.get("/analyze/unknown")
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"Unknown account_id", response.data)
