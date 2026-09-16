import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_manager
import hermes_evidence_store
import hermes_turn_ingest
import turn_ledger
import turn_receipt


class HermesTurnIngestTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        root = Path(self.tempdir.name)
        self.ledger = root / "turns.jsonl"
        self.evidence = root / "hermes.jsonl"
        self.ledger_patch = patch.object(turn_ledger, "_LEDGER_FILE_OVERRIDE", self.ledger)
        self.evidence_patch = patch.object(hermes_evidence_store, "_FILE_OVERRIDE", self.evidence)
        self.ledger_patch.start()
        self.evidence_patch.start()
        self.addCleanup(self.ledger_patch.stop)
        self.addCleanup(self.evidence_patch.stop)
        turn_ledger._SEEN_LEDGER_PATH = None
        turn_ledger._SEEN_TURN_IDS = None

        self.state_patch = patch.object(
            config_manager,
            "get_state",
            return_value={"current_spend_usd": 0.0, "thread_spend_usd": 0.0, "total_requests": 0},
        )
        self.update_patch = patch.object(
            config_manager,
            "update_spend",
            side_effect=lambda cost_usd, thread_id=None, reservation_id=None: {
                "current_spend_usd": float(cost_usd),
                "thread_spend_usd": float(cost_usd),
                "total_requests": 1,
            },
        )
        self.state_patch.start()
        self.update_patch.start()
        self.addCleanup(self.state_patch.stop)
        self.addCleanup(self.update_patch.stop)

    def _payload(self):
        return {
            "session_id": "session-1",
            "turn_id": "turn-1",
            "task_id": "task-1",
            "telemetry_schema_version": "hermes.observer.v1",
            "api_calls": [
                {
                    "api_request_id": "api-1",
                    "api_call_count": 1,
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "response_model": "gpt-4o-mini",
                    "platform": "cli",
                    "api_mode": "chat_completions",
                    "started_at": 1000.0,
                    "ended_at": 1000.5,
                    "api_duration": 0.5,
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "cache_read_tokens": 0,
                        "cache_write_tokens": 0,
                        "reasoning_tokens": 0,
                        "prompt_tokens": 100,
                        "total_tokens": 120,
                        "request_count": 1,
                    },
                }
            ],
            "failed_api_attempts": [],
        }

    def test_one_hermes_turn_creates_one_canonical_receipt(self):
        fake_pricing = {
            "provider": "openai",
            "complete": True,
            "total_cost_usd": 0.001,
            "components_usd": {"input": 0.0005, "output": 0.0005},
            "verified_at": "2026-09-16",
        }
        with patch.object(hermes_turn_ingest, "calculate_openai_response_cost", return_value=fake_pricing):
            result = hermes_turn_ingest.ingest_hermes_turn(self._payload())

        self.assertTrue(result["created"])
        receipt = turn_receipt.by_id(result["turn_id"])
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["turn"]["tokens"]["input_tokens"]["value"], 100)
        self.assertEqual(receipt["turn"]["tokens"]["output_tokens"]["value"], 20)
        self.assertIsNone(receipt["turn"]["tokens"]["cached_input_tokens"]["value"])
        self.assertEqual(receipt["turn"]["cost"]["estimated_usd"], 0.001)
        self.assertEqual(receipt["turn"]["cost"]["basis"], "hermes_child_transaction_sum_complete")
        self.assertEqual(receipt["turn"]["cost"]["indicator"]["label"], "TokenTotals estimate")

    def test_multiple_calls_are_priced_individually_then_summed(self):
        payload = self._payload()
        second = dict(payload["api_calls"][0])
        second["api_request_id"] = "api-2"
        second["api_call_count"] = 2
        second["usage"] = dict(second["usage"], prompt_tokens=50, input_tokens=50, output_tokens=10, total_tokens=60)
        payload["api_calls"].append(second)

        prices = [
            {"provider": "openai", "complete": True, "total_cost_usd": 0.001, "components_usd": {}},
            {"provider": "openai", "complete": True, "total_cost_usd": 0.002, "components_usd": {}},
        ]
        with patch.object(hermes_turn_ingest, "calculate_openai_response_cost", side_effect=prices) as pricing:
            result = hermes_turn_ingest.ingest_hermes_turn(payload)

        self.assertEqual(pricing.call_count, 2)
        receipt = turn_receipt.by_id(result["turn_id"])
        self.assertAlmostEqual(receipt["turn"]["cost"]["estimated_usd"], 0.003)
        self.assertEqual(receipt["turn"]["tokens"]["provider_reported_total_tokens"]["value"], 180)
        evidence = hermes_evidence_store.read(result["turn_id"])
        self.assertEqual(len(evidence["api_calls"]), 2)

    def test_duplicate_ingest_is_idempotent(self):
        fake_pricing = {"provider": "openai", "complete": True, "total_cost_usd": 0.001, "components_usd": {}}
        with patch.object(hermes_turn_ingest, "calculate_openai_response_cost", return_value=fake_pricing):
            first = hermes_turn_ingest.ingest_hermes_turn(self._payload())
            second = hermes_turn_ingest.ingest_hermes_turn(self._payload())
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(len(turn_ledger.read_turns()), 1)

    def test_missing_usage_does_not_become_zero_cost(self):
        payload = self._payload()
        payload["api_calls"][0]["usage"] = {}
        result = hermes_turn_ingest.ingest_hermes_turn(payload)
        receipt = turn_receipt.by_id(result["turn_id"])
        self.assertIsNone(receipt["turn"]["cost"]["estimated_usd"])
        self.assertEqual(receipt["turn"]["cost"]["basis"], "unavailable")
        self.assertEqual(receipt["turn"]["cost"]["indicator"]["label"], "Cost unavailable")
        self.assertFalse(config_manager.update_spend.called)

    def test_evidence_store_does_not_accept_conversation_content_fields(self):
        payload = self._payload()
        payload["prompt"] = "SECRET PROMPT"
        payload["answer"] = "SECRET ANSWER"
        payload["api_calls"][0]["request"] = {"authorization": "SECRET"}
        fake_pricing = {"provider": "openai", "complete": True, "total_cost_usd": 0.001, "components_usd": {}}
        with patch.object(hermes_turn_ingest, "calculate_openai_response_cost", return_value=fake_pricing):
            result = hermes_turn_ingest.ingest_hermes_turn(payload)
        raw = self.evidence.read_text(encoding="utf-8")
        self.assertNotIn("SECRET PROMPT", raw)
        self.assertNotIn("SECRET ANSWER", raw)
        self.assertNotIn("authorization", raw)


if __name__ == "__main__":
    unittest.main()
