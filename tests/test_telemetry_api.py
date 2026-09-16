import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import proxy_server
import turn_ledger


class TelemetryApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(proxy_server.app)

    def test_thread_telemetry_returns_presentation_object(self):
        expected = {
            "thread_id": "thread-1",
            "turn_count": 3,
            "latest_turn": {
                "turn_id": "turn-3",
                "model": {"canonical": "gemini-3.8-flash"},
            },
            "cost": {
                "estimated_cost_usd": 0.5,
                "costed_turns": 2,
                "total_turns": 3,
                "coverage": "partial",
            },
            "by_model": [
                {"model_id": "gemini-3.8-flash", "turn_count": 2},
                {"model_id": "claude-sonnet-5", "turn_count": 1},
            ],
        }
        with patch.object(proxy_server.telemetry_view, "thread_view", return_value=expected) as mocked:
            response = self.client.get("/api/telemetry/thread", params={"thread_id": "thread-1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        mocked.assert_called_once_with("thread-1")

    def test_missing_thread_id_is_rejected_by_fastapi(self):
        response = self.client.get("/api/telemetry/thread")
        self.assertEqual(response.status_code, 422)

    def test_blank_thread_id_is_rejected(self):
        with patch.object(proxy_server.telemetry_view, "thread_view") as mocked:
            response = self.client.get("/api/telemetry/thread", params={"thread_id": "   "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "thread_id must be non-empty")
        mocked.assert_not_called()

    def test_unknown_thread_returns_404(self):
        with patch.object(proxy_server.telemetry_view, "thread_view", return_value=None):
            response = self.client.get("/api/telemetry/thread", params={"thread_id": "missing"})

        self.assertEqual(response.status_code, 404)
        self.assertIn("No TokenTotals turn telemetry exists", response.json()["detail"])

    def test_corrupt_ledger_is_visible_not_silently_skipped(self):
        with patch.object(
            proxy_server.telemetry_view,
            "thread_view",
            side_effect=turn_ledger.LedgerCorruptionError("bad line 2"),
        ):
            response = self.client.get("/api/telemetry/thread", params={"thread_id": "thread-1"})

        self.assertEqual(response.status_code, 500)
        self.assertIn("turn ledger is corrupt", response.json()["detail"])
        self.assertIn("bad line 2", response.json()["detail"])


    def test_turn_receipt_endpoint_returns_canonical_receipt(self):
        expected = {
            "schema": "tokentotals.turn_receipt",
            "schema_version": 1,
            "receipt_id": "turn-3",
            "thread": {"thread_id": "thread-1", "turn_count": 3},
        }
        with patch.object(proxy_server.turn_receipt, "for_thread", return_value=expected) as mocked:
            response = self.client.get("/api/turn-receipt", params={"thread_id": "thread-1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        mocked.assert_called_once_with("thread-1")

    def test_turn_receipt_endpoint_rejects_blank_thread_id(self):
        with patch.object(proxy_server.turn_receipt, "for_thread") as mocked:
            response = self.client.get("/api/turn-receipt", params={"thread_id": "   "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "thread_id must be non-empty")
        mocked.assert_not_called()

    def test_turn_receipt_endpoint_returns_404_for_unknown_thread(self):
        with patch.object(proxy_server.turn_receipt, "for_thread", return_value=None):
            response = self.client.get("/api/turn-receipt", params={"thread_id": "missing"})

        self.assertEqual(response.status_code, 404)
        self.assertIn("No TokenTotals Turn Receipt exists", response.json()["detail"])

    def test_turn_receipt_endpoint_surfaces_ledger_corruption(self):
        with patch.object(
            proxy_server.turn_receipt,
            "for_thread",
            side_effect=turn_ledger.LedgerCorruptionError("bad line 9"),
        ):
            response = self.client.get("/api/turn-receipt", params={"thread_id": "thread-1"})

        self.assertEqual(response.status_code, 500)
        self.assertIn("turn ledger is corrupt", response.json()["detail"])
        self.assertIn("bad line 9", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
