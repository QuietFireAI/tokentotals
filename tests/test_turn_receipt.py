import unittest
from unittest.mock import patch

import turn_receipt
import turn_ledger


class TurnReceiptTests(unittest.TestCase):
    def _record(self):
        tokens = {name: None for name in turn_ledger.TOKEN_FIELDS}
        basis = {name: "unavailable" for name in turn_ledger.TOKEN_FIELDS}

        tokens.update({
            "input_tokens": 1250,
            "cached_input_tokens": 1000,
            "uncached_input_tokens": 250,
            "output_tokens": 400,
            "provider_reported_total_tokens": 1650,
            "reconstructed_total_tokens": 1650,
            "unclassified_tokens": 0,
            "reconciliation_delta_tokens": 0,
        })
        basis.update({
            "input_tokens": "observed",
            "cached_input_tokens": "observed",
            "uncached_input_tokens": "derived",
            "output_tokens": "observed",
            "provider_reported_total_tokens": "observed",
            "reconstructed_total_tokens": "derived",
            "unclassified_tokens": "derived",
            "reconciliation_delta_tokens": "derived",
        })

        return {
            "turn_id": "turn-abc123",
            "thread_id": "thread-7",
            "started_at": "2026-09-16T12:00:00+00:00",
            "completed_at": "2026-09-16T12:00:01+00:00",
            "latency_ms": 1000,
            "provider": "openai",
            "requested_model_id": "gpt-example",
            "canonical_model_id": "gpt-example",
            "observed_model_id": "gpt-example",
            "requested_service_tier": None,
            "observed_service_tier": "standard",
            "tokens": tokens,
            "token_basis": basis,
            "modalities": {},
            "server_tools": {},
            "estimated_cost_usd": 0.012345,
            "pricing_components_usd": {
                "input": 0.002345,
                "output": 0.010000,
            },
            "cost_basis": "provider_registry_complete",
            "estimate_complete": True,
            "registry_verified_at": "2026-09-16",
            "notes": [],
        }

    def test_receipt_has_stable_schema_identity_and_turn_identity(self):
        receipt = turn_receipt.from_record(self._record())

        self.assertEqual(receipt["schema"], "tokentotals.turn_receipt")
        self.assertEqual(receipt["schema_version"], 1)
        self.assertEqual(receipt["receipt_id"], "turn-abc123")
        self.assertEqual(receipt["kind"], "completed_turn_usage_estimate")
        self.assertEqual(receipt["generated_by"], "TokenTotals")
        self.assertEqual(receipt["turn"]["turn_id"], receipt["receipt_id"])
        self.assertEqual(receipt["turn"]["thread_id"], "thread-7")

    def test_receipt_marks_tokentotals_estimate_as_not_provider_invoice(self):
        receipt = turn_receipt.from_record(self._record())

        self.assertEqual(receipt["authority"]["scope"], "independent_usage_estimate")
        self.assertIs(receipt["authority"]["provider_invoice"], False)
        self.assertTrue(receipt["turn"]["cost"]["complete"])
        self.assertEqual(receipt["turn"]["cost"]["basis"], "provider_registry_complete")
        self.assertEqual(receipt["turn"]["cost"]["components_usd"]["output"], 0.01)
        self.assertEqual(receipt["turn"]["cost"]["components_basis"], "same_as_estimate")
        self.assertEqual(receipt["turn"]["cost"]["indicator"]["level"], "normal")

    def test_receipt_hides_provider_components_when_total_uses_litellm_fallback(self):
        record = self._record()
        record["estimated_cost_usd"] = 0.031
        record["cost_basis"] = "litellm_response_cost_fallback"
        record["estimate_complete"] = False
        record["pricing_components_usd"] = {
            "input": 0.002345,
            "output": 0.010000,
        }

        receipt = turn_receipt.from_record(record)
        cost = receipt["turn"]["cost"]
        self.assertEqual(cost["estimated_usd"], 0.031)
        self.assertEqual(cost["basis"], "litellm_response_cost_fallback")
        self.assertEqual(cost["components_usd"], {})
        self.assertEqual(cost["components_basis"], "unavailable_for_estimate_basis")

    def test_fallback_estimate_is_explicitly_flagged_for_user(self):
        record = self._record()
        record["estimated_cost_usd"] = 0.031
        record["cost_basis"] = "litellm_response_cost_fallback"
        record["estimate_complete"] = False

        indicator = turn_receipt.from_record(record)["turn"]["cost"]["indicator"]
        self.assertEqual(indicator["status"], "fallback")
        self.assertEqual(indicator["level"], "warning")
        self.assertEqual(indicator["label"], "Fallback estimate")
        self.assertIn("may be higher or lower", indicator["message"])
        self.assertIn("provider invoice", indicator["message"])

    def test_known_list_equivalent_keeps_matching_components_but_stays_incomplete(self):
        record = self._record()
        record["cost_basis"] = "known_list_equivalent"
        record["estimate_complete"] = False

        receipt = turn_receipt.from_record(record)
        cost = receipt["turn"]["cost"]
        self.assertEqual(cost["components_basis"], "same_as_estimate")
        self.assertEqual(cost["components_usd"]["input"], 0.002345)
        self.assertFalse(cost["complete"])
        self.assertEqual(cost["indicator"]["status"], "list_equivalent")
        self.assertEqual(cost["indicator"]["level"], "warning")

    def test_unavailable_cost_is_not_presented_as_zero(self):
        record = self._record()
        record["estimated_cost_usd"] = None
        record["cost_basis"] = "unavailable"
        record["estimate_complete"] = False
        record["pricing_components_usd"] = {}

        cost = turn_receipt.from_record(record)["turn"]["cost"]
        self.assertIsNone(cost["estimated_usd"])
        self.assertEqual(cost["indicator"]["status"], "unavailable")
        self.assertIn("not treated as zero", cost["indicator"]["message"])

    def test_receipt_preserves_missing_and_explicit_zero_semantics(self):
        receipt = turn_receipt.from_record(self._record())
        tokens = receipt["turn"]["tokens"]

        self.assertEqual(tokens["reasoning_tokens"], {
            "value": None,
            "basis": "unavailable",
        })
        self.assertEqual(tokens["unclassified_tokens"], {
            "value": 0,
            "basis": "derived",
        })
        self.assertEqual(receipt["turn"]["turn_total_tokens"], {
            "value": 1650,
            "basis": "provider_reported",
        })

    def test_for_thread_uses_ledger_summary_not_global_completed_turn_count(self):
        record = self._record()
        record["cumulative_completed_turns"] = 999
        summary = {
            "thread_id": "thread-7",
            "turn_count": 4,
            "cost_observed_turns": 3,
            "estimated_cost_usd": 0.041,
        }

        with patch.object(turn_receipt.turn_ledger, "read_turns", return_value=[record]), \
             patch.object(turn_receipt.turn_ledger, "summarize_thread", return_value=summary):
            receipt = turn_receipt.for_thread("thread-7")

        self.assertEqual(receipt["thread"]["turn_count"], 4)
        self.assertEqual(receipt["thread"]["costed_turns"], 3)
        self.assertEqual(receipt["thread"]["cost_coverage"], "partial")
        self.assertEqual(receipt["thread"]["estimated_cost_usd"], 0.041)
        self.assertNotEqual(receipt["thread"]["turn_count"], 999)

    def test_for_thread_does_not_turn_no_cost_history_into_zero(self):
        record = self._record()
        summary = {
            "thread_id": "thread-7",
            "turn_count": 2,
            "cost_observed_turns": 0,
            "estimated_cost_usd": 0.0,
        }

        with patch.object(turn_receipt.turn_ledger, "read_turns", return_value=[record]), \
             patch.object(turn_receipt.turn_ledger, "summarize_thread", return_value=summary):
            receipt = turn_receipt.for_thread("thread-7")

        self.assertIsNone(receipt["thread"]["estimated_cost_usd"])
        self.assertEqual(receipt["thread"]["cost_coverage"], "unavailable")

    def test_standard_view_is_turn_scoped_and_omits_thread_aggregate(self):
        receipt = turn_receipt.from_record(self._record())
        receipt["thread"] = {
            "thread_id": "thread-7",
            "turn_count": 4,
            "estimated_cost_usd": 0.041,
            "costed_turns": 4,
            "cost_coverage": "complete",
        }

        view = turn_receipt.standard_view(receipt)

        self.assertEqual(view["receipt_id"], "turn-abc123")
        self.assertEqual(view["provider"], "openai")
        self.assertEqual(view["model"], "gpt-example")
        self.assertEqual(view["input_tokens"], 1250)
        self.assertEqual(view["cached_input_tokens"], 1000)
        self.assertEqual(view["output_tokens"], 400)
        self.assertEqual(view["turn_estimate_usd"], 0.012345)
        self.assertEqual(view["pricing_basis"], "provider_registry_complete")
        self.assertEqual(view["website"], "TurnReceipt.com")
        self.assertIn("not a provider invoice", view["disclaimer"])
        self.assertNotIn("thread_estimate_usd", view)
        self.assertNotIn("thread_turn_count", view)

    def test_by_id_returns_exact_turn_scoped_receipt(self):
        first = self._record()
        first["turn_id"] = "turn-first"
        second = self._record()
        second["turn_id"] = "turn-second"

        with patch.object(turn_receipt.turn_ledger, "read_turns", return_value=[first, second]):
            receipt = turn_receipt.by_id("turn-first")

        self.assertEqual(receipt["receipt_id"], "turn-first")
        self.assertEqual(receipt["turn"]["turn_id"], "turn-first")
        self.assertNotIn("thread", receipt)

    def test_by_id_rejects_blank_and_returns_none_for_unknown_turn(self):
        with self.assertRaisesRegex(ValueError, "turn_id must be non-empty"):
            turn_receipt.by_id("   ")

        with patch.object(turn_receipt.turn_ledger, "read_turns", return_value=[self._record()]):
            self.assertIsNone(turn_receipt.by_id("missing"))

    def test_for_thread_rejects_blank_and_returns_none_for_unknown_thread(self):
        with self.assertRaisesRegex(ValueError, "thread_id must be non-empty"):
            turn_receipt.for_thread("   ")

        with patch.object(turn_receipt.turn_ledger, "read_turns", return_value=[]):
            self.assertIsNone(turn_receipt.for_thread("missing"))

    def test_receipt_rejects_missing_turn_identity(self):
        record = self._record()
        record["turn_id"] = ""
        with self.assertRaisesRegex(ValueError, "non-empty turn_id"):
            turn_receipt.from_record(record)

    def test_empty_record_has_no_receipt(self):
        self.assertIsNone(turn_receipt.from_record(None))
        self.assertIsNone(turn_receipt.from_record({}))
        self.assertIsNone(turn_receipt.standard_view(None))


if __name__ == "__main__":
    unittest.main()
