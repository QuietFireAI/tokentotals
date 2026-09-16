import unittest

import turn_receipt_renderer


class TurnReceiptRendererTests(unittest.TestCase):
    def _receipt(self):
        def metric(value, basis):
            return {"value": value, "basis": basis}

        return {
            "schema": "tokentotals.turn_receipt",
            "schema_version": 1,
            "receipt_id": "turn-abc123",
            "kind": "completed_turn_usage_estimate",
            "generated_by": "TokenTotals",
            "authority": {"scope": "independent_usage_estimate", "provider_invoice": False},
            "turn": {
                "turn_id": "turn-abc123",
                "thread_id": "thread-7",
                "started_at": "2026-09-16T12:00:00+00:00",
                "completed_at": "2026-09-16T12:00:01+00:00",
                "latency_ms": 1000,
                "provider": "openai",
                "model": {
                    "requested": "gpt-example",
                    "canonical": "gpt-example",
                    "observed": "gpt-example",
                },
                "service_tier": {"requested": None, "observed": "standard"},
                "tokens": {
                    "input_tokens": metric(1250, "observed"),
                    "uncached_input_tokens": metric(250, "derived"),
                    "cached_input_tokens": metric(1000, "observed"),
                    "cache_write_tokens": metric(None, "unavailable"),
                    "output_tokens": metric(400, "observed"),
                    "reasoning_tokens": metric(None, "unavailable"),
                    "tool_input_tokens": metric(None, "unavailable"),
                    "provider_reported_total_tokens": metric(1650, "observed"),
                    "reconstructed_total_tokens": metric(1650, "derived"),
                    "unclassified_tokens": metric(0, "derived"),
                    "reconciliation_delta_tokens": metric(0, "derived"),
                },
                "turn_total_tokens": {"value": 1650, "basis": "provider_reported"},
                "cache_share": {"cached_tokens": 1000, "input_tokens": 1250, "pct_of_input": 80.0},
                "output_tokens_per_wall_second": 400.0,
                "output_rate_scope": "observed output tokens divided by callback wall-clock elapsed time; not pure model generation throughput",
                "modalities": {},
                "server_tools": {},
                "cost": {
                    "estimated_usd": 0.012345,
                    "basis": "provider_registry_complete",
                    "complete": True,
                    "components_usd": {"input": 0.002345, "output": 0.010000},
                    "components_basis": "same_as_estimate",
                    "registry_verified_at": "2026-09-16",
                    "indicator": {
                        "status": "provider_reconstruction",
                        "level": "normal",
                        "label": "TokenTotals estimate",
                        "message": "Calculated from available provider telemetry; not a provider invoice.",
                    },
                    "rate_provenance": {
                        "status": "complete_for_recorded_components",
                        "effective_rates": [
                            {
                                "component": "input",
                                "unit_basis": "per_1m_tokens",
                                "quantity": 250,
                                "component_cost_usd": 0.002345,
                                "effective_rate_usd": 9.38,
                            }
                        ],
                        "unresolved_components": [],
                    },
                },
                "notes": [],
            },
        }

    def _thread_view(self):
        return {
            "thread_id": "thread-7",
            "turn_count": 4,
            "cost": {
                "estimated_cost_usd": 0.041,
                "costed_turns": 3,
                "total_turns": 4,
                "coverage": "partial",
            },
            "by_model": [
                {
                    "model_id": "gpt-example",
                    "provider": "openai",
                    "turn_count": 3,
                    "cost": {"estimated_cost_usd": 0.031, "coverage": "complete"},
                },
                {
                    "model_id": "other-example",
                    "provider": "anthropic",
                    "turn_count": 1,
                    "cost": {"estimated_cost_usd": 0.010, "coverage": "complete"},
                },
            ],
        }

    def test_standard_is_turn_scoped_receipt_with_typewriter_visual_cue(self):
        html = turn_receipt_renderer.render_html(
            self._receipt(),
            mode="standard",
            thread_view=self._thread_view(),
        )

        self.assertIn("Turn Receipt", html)
        self.assertIn('"Courier New", Courier, "Liberation Mono", ui-monospace, monospace', html)
        self.assertIn("gpt-example", html)
        self.assertIn("$0.012345", html)
        self.assertIn(">TurnReceipt.com</a>", html)
        self.assertNotIn("not a provider invoice", html)
        self.assertNotIn("Receipt ID:", html)
        self.assertNotIn("Current thread aggregate", html)
        self.assertNotIn("other-example", html)

    def test_expanded_adds_deep_turn_detail_and_current_thread_aggregate(self):
        html = turn_receipt_renderer.render_html(
            self._receipt(),
            mode="expanded",
            thread_view=self._thread_view(),
        )

        self.assertIn("Receipt ID", html)
        self.assertIn("turn-abc123", html)
        self.assertIn("Token anatomy", html)
        self.assertIn("Pricing math", html)
        self.assertIn("Effective rates", html)
        self.assertIn("Current thread aggregate", html)
        self.assertIn("thread aggregate at render time", html)
        self.assertIn("other-example", html)
        self.assertIn("partial", html)
        self.assertNotIn("Context window", html)

    def test_missing_stays_unavailable_while_explicit_zero_stays_zero(self):
        receipt = self._receipt()
        receipt["turn"]["tokens"]["input_tokens"] = {"value": None, "basis": "unavailable"}
        receipt["turn"]["tokens"]["cached_input_tokens"] = {"value": 0, "basis": "observed"}

        html = turn_receipt_renderer.render_html(receipt, mode="expanded")

        self.assertIn("Unavailable", html)
        self.assertIn('0 <span class="tt-receipt-basis">observed</span>', html)

    def test_fallback_warning_is_visible_not_presented_as_normal_precision(self):
        receipt = self._receipt()
        receipt["turn"]["cost"]["basis"] = "litellm_response_cost_fallback"
        receipt["turn"]["cost"]["complete"] = False
        receipt["turn"]["cost"]["components_usd"] = {}
        receipt["turn"]["cost"]["components_basis"] = "unavailable_for_estimate_basis"
        receipt["turn"]["cost"]["indicator"] = {
            "status": "fallback",
            "level": "warning",
            "label": "Fallback estimate",
            "message": "Secondary source; may be higher or lower than the provider invoice.",
        }

        html = turn_receipt_renderer.render_html(receipt, mode="standard")

        self.assertIn("Fallback estimate", html)
        self.assertIn("higher or lower", html)
        self.assertIn("tt-warning", html)

    def test_renderer_escapes_provider_data_and_notes(self):
        receipt = self._receipt()
        receipt["turn"]["model"]["canonical"] = '<script>alert("x")</script>'
        receipt["turn"]["notes"] = ['<img src=x onerror=alert(1)>']

        html = turn_receipt_renderer.render_html(receipt, mode="expanded")

        self.assertNotIn('<script>alert("x")</script>', html)
        self.assertNotIn('<img src=x onerror=alert(1)>', html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img", html)

    def test_expanded_without_thread_data_says_unavailable_not_zero(self):
        html = turn_receipt_renderer.render_html(self._receipt(), mode="expanded")
        self.assertIn("Thread aggregate is unavailable", html)
        self.assertNotIn("Thread estimate</span><span class=\"tt-receipt-value\">$0.0000", html)

    def test_invalid_mode_and_missing_receipt_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "standard.*expanded"):
            turn_receipt_renderer.render_html(self._receipt(), mode="giant")
        with self.assertRaisesRegex(ValueError, "receipt is required"):
            turn_receipt_renderer.render_html(None)


if __name__ == "__main__":
    unittest.main()
