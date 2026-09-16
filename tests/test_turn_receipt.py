import unittest

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

    def test_receipt_rejects_missing_turn_identity(self):
        record = self._record()
        record["turn_id"] = ""
        with self.assertRaisesRegex(ValueError, "non-empty turn_id"):
            turn_receipt.from_record(record)

    def test_empty_record_has_no_receipt(self):
        self.assertIsNone(turn_receipt.from_record(None))
        self.assertIsNone(turn_receipt.from_record({}))


if __name__ == "__main__":
    unittest.main()
