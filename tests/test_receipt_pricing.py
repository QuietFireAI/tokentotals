import unittest

import receipt_pricing


def metric(value, basis="observed"):
    return {"value": value, "basis": basis if value is not None else "unavailable"}


class ReceiptPricingTests(unittest.TestCase):
    def _turn(self, provider, components, tokens=None, modalities=None, server_tools=None, basis="provider_registry_complete"):
        return {
            "provider": provider,
            "tokens": tokens or {},
            "modalities": modalities or {},
            "server_tools": server_tools or {},
            "cost": {
                "basis": basis,
                "components_usd": components,
                "registry_verified_at": "2026-09-16",
            },
        }

    def test_openai_effective_rates_reproduce_recorded_component_math(self):
        turn = self._turn(
            "openai",
            {
                "input": 0.000625,
                "cached_input": 0.000125,
                "output": 0.004,
            },
            tokens={
                "uncached_input_tokens": metric(250, "derived"),
                "cached_input_tokens": metric(1000),
                "output_tokens": metric(400),
            },
        )

        provenance = receipt_pricing.from_turn(turn)
        rates = {item["component"]: item for item in provenance["effective_rates"]}
        self.assertEqual(provenance["status"], "complete_for_recorded_components")
        self.assertEqual(rates["input"]["effective_rate_usd"], 2.5)
        self.assertEqual(rates["cached_input"]["effective_rate_usd"], 0.125)
        self.assertEqual(rates["output"]["effective_rate_usd"], 10.0)
        self.assertEqual(rates["input"]["unit_basis"], "per_1m_tokens")

    def test_anthropic_cache_write_is_preserved_as_weighted_effective_rate(self):
        turn = self._turn(
            "anthropic",
            {
                "base_input": 0.0003,
                "cache_write_5m": 0.0001,
                "cache_write_1h": 0.0003,
                "cache_read": 0.0002,
                "output": 0.00075,
                "web_search": 0.02,
            },
            tokens={
                "uncached_input_tokens": metric(100, "derived"),
                "cache_write_tokens": metric(100),
                "cached_input_tokens": metric(200),
                "output_tokens": metric(50),
            },
            server_tools={"web_search_requests": 2},
        )

        provenance = receipt_pricing.from_turn(turn)
        rates = {item["component"]: item for item in provenance["effective_rates"]}
        self.assertEqual(rates["base_input"]["effective_rate_usd"], 3.0)
        self.assertEqual(rates["cache_write_effective"]["effective_rate_usd"], 4.0)
        self.assertEqual(rates["cache_read"]["effective_rate_usd"], 1.0)
        self.assertEqual(rates["output"]["effective_rate_usd"], 15.0)
        self.assertEqual(rates["web_search"]["effective_rate_usd"], 0.01)
        self.assertEqual(rates["web_search"]["unit_basis"], "per_request")

    def test_google_output_rate_includes_recorded_reasoning_tokens(self):
        turn = self._turn(
            "google",
            {
                "uncached_input": {"text": 0.0002},
                "output_including_thinking": {"text": 0.001},
            },
            tokens={
                "uncached_input_tokens": metric(200, "derived"),
                "output_tokens": metric(90, "derived"),
                "reasoning_tokens": metric(10),
            },
            modalities={
                "uncached_input": {"text": 200},
                "output": {"text": 90},
            },
        )

        provenance = receipt_pricing.from_turn(turn)
        rates = {item["component"]: item for item in provenance["effective_rates"]}
        self.assertEqual(rates["uncached_input.text"]["effective_rate_usd"], 1.0)
        self.assertEqual(rates["output_including_thinking.text"]["quantity"], 100)
        self.assertEqual(rates["output_including_thinking.text"]["effective_rate_usd"], 10.0)

    def test_google_grounding_rate_stays_unresolved_when_billing_unit_is_not_persisted(self):
        turn = self._turn(
            "google",
            {
                "uncached_input": {"text": 0.0002},
                "search_grounding_list_equivalent": 0.035,
            },
            tokens={"uncached_input_tokens": metric(200, "derived")},
            modalities={"uncached_input": {"text": 200}},
            server_tools={"search_query_count": 7},
        )

        provenance = receipt_pricing.from_turn(turn)
        self.assertEqual(provenance["status"], "partial")
        self.assertIn("search_grounding_list_equivalent", provenance["unresolved_components"])

    def test_fallback_total_does_not_invent_effective_rates(self):
        turn = self._turn(
            "openai",
            {"input": 0.123},
            tokens={"uncached_input_tokens": metric(100)},
            basis="litellm_response_cost_fallback",
        )

        provenance = receipt_pricing.from_turn(turn)
        self.assertEqual(provenance["status"], "unavailable_for_estimate_basis")
        self.assertEqual(provenance["effective_rates"], [])


if __name__ == "__main__":
    unittest.main()
