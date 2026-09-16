import unittest

import turn_receipt_terminal


class TerminalReceiptTests(unittest.TestCase):
    def _receipt(self):
        return {
            "receipt_id": "hermes-abc",
            "turn": {
                "completed_at": "2026-09-16T20:00:00+00:00",
                "provider": "openai",
                "model": {"canonical": "gpt-5.6-sol", "observed": None, "requested": "gpt-5.6-sol"},
                "tokens": {
                    "input_tokens": {"value": 100, "basis": "observed"},
                    "uncached_input_tokens": {"value": 80, "basis": "derived"},
                    "cached_input_tokens": {"value": None, "basis": "unavailable"},
                    "cache_write_tokens": {"value": None, "basis": "unavailable"},
                    "output_tokens": {"value": 20, "basis": "observed"},
                    "reasoning_tokens": {"value": None, "basis": "unavailable"},
                    "provider_reported_total_tokens": {"value": 120, "basis": "observed"},
                },
                "cost": {
                    "estimated_usd": 0.0012,
                    "basis": "hermes_child_transaction_sum_complete",
                    "complete": True,
                    "indicator": {"label": "TokenTotals estimate"},
                },
            },
        }

    def test_standard_footer_is_only_turnreceipt(self):
        text = turn_receipt_terminal.render_text(self._receipt(), "standard")
        self.assertTrue(text.endswith("TurnReceipt.com"))
        self.assertIn("Cached input           Unavailable", text)
        self.assertNotIn("provider invoice", text.lower())

    def test_expanded_includes_child_count_without_content(self):
        evidence = {
            "api_calls": [{
                "provider": "openai",
                "model": "gpt-5.6-sol",
                "response_model": "gpt-5.6-sol",
                "usage": {"total_tokens": 120},
                "pricing": {"estimated_usd": 0.0012},
            }],
            "failed_api_attempts": [],
        }
        text = turn_receipt_terminal.render_text(self._receipt(), "expanded", evidence=evidence)
        self.assertIn("Hermes API calls       1", text)
        self.assertIn("Call 1", text)
        self.assertIn("Receipt ID", text)


if __name__ == "__main__":
    unittest.main()
