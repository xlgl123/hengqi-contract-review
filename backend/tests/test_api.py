from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


TEST_DIR = Path(tempfile.mkdtemp(prefix="contract-mvp-test-"))
os.environ["DATABASE_PATH"] = str(TEST_DIR / "test.db")
os.environ.pop("AI_API_KEY", None)
os.environ.pop("DEEPSEEK_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_health_is_honest_about_ai_mode(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ai_configured"])

    def test_sample_contract_runs_complete_flow(self) -> None:
        sample = self.client.get("/api/sample").json()
        response = self.client.post(
            "/api/reviews",
            data={"text": sample["text"], "party_role": "service_provider"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["engine_mode"], "rules_demo")
        self.assertGreater(payload["risk_bill"]["total_risks"], 0)
        self.assertGreater(payload["risk_bill"]["high"], 0)
        self.assertIn("未配置AI_API_KEY", payload["warnings"][0])

        stored = self.client.get(f"/api/reviews/{payload['review_id']}")
        self.assertEqual(stored.status_code, 200)
        self.assertEqual(stored.json()["review_id"], payload["review_id"])

        recent = self.client.get("/api/reviews?limit=5")
        self.assertEqual(recent.status_code, 200)
        self.assertTrue(any(item["review_id"] == payload["review_id"] for item in recent.json()))
        summary = next(item for item in recent.json() if item["review_id"] == payload["review_id"])
        self.assertEqual(summary["total_risks"], payload["risk_bill"]["total_risks"])

    def test_short_text_is_rejected(self) -> None:
        response = self.client.post(
            "/api/reviews",
            data={"text": "太短", "party_role": "service_provider"},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
