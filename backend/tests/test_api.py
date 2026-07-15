from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


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

    @patch("app.main.AIClient.test_connection", new_callable=AsyncMock)
    def test_ai_can_be_configured_and_cleared_from_local_ui(self, test_connection: AsyncMock) -> None:
        test_connection.return_value = {
            "model": "deepseek-ai/DeepSeek-V4-Flash",
            "total_tokens": 23,
        }
        self.client.delete("/api/settings/ai")
        configured = self.client.post(
            "/api/settings/ai",
            json={
                "provider": "siliconflow",
                "api_key": "test-key-not-a-real-secret-123",
                "model": "deepseek-ai/DeepSeek-V4-Flash",
            },
        )
        self.assertEqual(configured.status_code, 200, configured.text)
        payload = configured.json()
        self.assertTrue(payload["configured"])
        self.assertEqual(payload["provider"], "siliconflow")
        self.assertEqual(payload["tested_model"], "deepseek-ai/DeepSeek-V4-Flash")
        self.assertNotIn("test-key-not-a-real-secret", configured.text)
        self.assertTrue(self.client.get("/api/health").json()["ai_configured"])

        cleared = self.client.delete("/api/settings/ai")
        self.assertEqual(cleared.status_code, 200)
        self.assertFalse(cleared.json()["configured"])
        self.assertFalse(self.client.get("/api/health").json()["ai_configured"])


if __name__ == "__main__":
    unittest.main()
