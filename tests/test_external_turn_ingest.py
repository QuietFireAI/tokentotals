import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import external_turn_ingest
import turn_ledger


class ExternalTurnIngestTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.ledger_path = Path(self.tempdir.name) / "turns.jsonl"
        self.override = patch.object(turn_ledger, "_LEDGER_FILE_OVERRIDE", self.ledger_path)
        self.override.start()
        self.addCleanup(self.override.stop)
        turn_ledger._SEEN_LEDGER_PATH = None
        turn_ledger._SEEN_TURN_IDS = None

    def test_requires_stable_external_turn_identity(self):
        with self.assertRaises(ValueError):
            external_turn_ingest.ingest_external_turn({
                "provider": "google",
                "model": "gemini-2.5-flash",
                "usage": {"promptTokenCount": 3, "candidatesTokenCount": 4, "totalTokenCount": 7},
            })

    @patch("external_turn_ingest.config_manager.update_spend", return_value={"current_spend_usd": 0.0, "thread_spend_usd": 0.0, "total_requests": 1})
    def test_missing_usage_remains_unavailable_not_zero(self, _update):
        result = external_turn_ingest.ingest_external_turn({
            "provider": "google",
            "model": "gemini-2.5-flash",
            "source_turn_id": "provider-turn-12345678",
            "source_thread_id": "provider-thread-1",
            "surface": "gemini.google.com",
        })
        self.assertEqual(result["cost_basis"], "unavailable")
        self.assertFalse(result["estimate_complete"])
        records = turn_ledger.read_turns()
        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0]["estimated_cost_usd"])
        self.assertTrue(all(value is None for value in records[0]["tokens"].values()))

    @patch("external_turn_ingest.config_manager.update_spend", return_value={"current_spend_usd": 0.001, "thread_spend_usd": 0.001, "total_requests": 1})
    @patch("external_turn_ingest._price")
    def test_retry_is_idempotent(self, price, _update):
        price.return_value = {
            "provider": "google",
            "canonical_model_id": "gemini-2.5-flash",
            "response_model_id": "gemini-2.5-flash",
            "verified_at": "2026-09-16",
            "usage": {"source_shape": "google_raw", "prompt_total_tokens": 3, "output_tokens_including_thinking": 4, "total_tokens": 7},
            "total_cost_usd": 0.001,
            "known_list_equivalent_usd": 0.001,
            "complete": True,
            "components_usd": {},
            "notes": [],
        }
        payload = {
            "provider": "google",
            "model": "gemini-2.5-flash",
            "source_turn_id": "provider-turn-abcdef12",
            "source_thread_id": "provider-thread-1",
            "surface": "gemini.google.com",
            "usage": {"promptTokenCount": 3, "candidatesTokenCount": 4, "totalTokenCount": 7},
        }
        first = external_turn_ingest.ingest_external_turn(payload)
        second = external_turn_ingest.ingest_external_turn(payload)
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(len(turn_ledger.read_turns()), 1)


if __name__ == "__main__":
    unittest.main()
