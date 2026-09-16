import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

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
        with turn_ledger._LEDGER_LOCK:
            turn_ledger._SEEN_LEDGER_PATH = None
            turn_ledger._SEEN_TURN_IDS = None

    def tearDown(self):
        with turn_ledger._LEDGER_LOCK:
            turn_ledger._SEEN_LEDGER_PATH = None
            turn_ledger._SEEN_TURN_IDS = None

    def payload(self):
        return {
            "surface": "gemini_web",
            "provider": "google",
            "model_id": "gemini-2.5-flash",
            "external_thread_id": "https://gemini.google.com/app/example-thread",
            "external_turn_id": "model-response-17",
            "visible_user_text": "What is 17 multiplied by 24?",
            "visible_assistant_text": "408",
            "completed_at": "2026-09-16T19:30:00+00:00",
        }

    def test_visible_text_is_ephemeral_and_never_persisted(self):
        result = external_turn_ingest.settle_external_turn(self.payload())
        self.assertTrue(result["receipt_id"].startswith("gemini_web-turn-"))
        raw = self.ledger_path.read_text(encoding="utf-8")
        self.assertNotIn("What is 17 multiplied by 24?", raw)
        self.assertNotIn("408", raw)
        self.assertNotIn("gemini.google.com/app/example-thread", raw)

    def test_visible_text_tokens_are_derived_not_observed(self):
        result = external_turn_ingest.settle_external_turn(self.payload())
        turn = result["receipt"]["turn"]
        self.assertEqual(turn["tokens"]["input_tokens"]["basis"], "derived")
        self.assertEqual(turn["tokens"]["output_tokens"]["basis"], "derived")
        self.assertIsNone(turn["cost"]["estimated_usd"])
        self.assertEqual(turn["cost"]["basis"], "unavailable")

    def test_provider_observed_token_fields_preserve_basis(self):
        payload = self.payload()
        payload.pop("visible_user_text")
        payload.pop("visible_assistant_text")
        payload["tokens"] = {
            "input_tokens": {"value": 21, "basis": "observed"},
            "output_tokens": {"value": 7, "basis": "observed"},
            "provider_reported_total_tokens": {"value": 28, "basis": "observed"},
        }
        result = external_turn_ingest.settle_external_turn(payload)
        turn = result["receipt"]["turn"]
        self.assertEqual(turn["tokens"]["input_tokens"]["value"], 21)
        self.assertEqual(turn["tokens"]["input_tokens"]["basis"], "observed")
        self.assertEqual(turn["tokens"]["provider_reported_total_tokens"]["basis"], "observed")

    def test_duplicate_external_identity_does_not_duplicate_ledger(self):
        first = external_turn_ingest.settle_external_turn(self.payload())
        second = external_turn_ingest.settle_external_turn(self.payload())
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(len(turn_ledger.read_turns()), 1)

    def test_prompt_answer_storage_fields_are_rejected(self):
        payload = self.payload()
        payload["prompt"] = "do not persist me"
        with self.assertRaises(HTTPException):
            external_turn_ingest.settle_external_turn(payload)

    def test_thread_and_turn_external_ids_are_hashed(self):
        result = external_turn_ingest.settle_external_turn(self.payload())
        record = turn_ledger.read_turns()[0]
        self.assertNotEqual(record["thread_id"], "https://gemini.google.com/app/example-thread")
        self.assertNotEqual(record["turn_id"], "model-response-17")
        self.assertEqual(record["turn_id"], result["receipt_id"])


if __name__ == "__main__":
    unittest.main()
