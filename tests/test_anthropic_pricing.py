import unittest

import anthropic_pricing as pricing


class AnthropicPricingTests(unittest.TestCase):
    def test_mixed_cache_ttls(self):
        usage = {
            "input_tokens": 1_000,
            "cache_creation_input_tokens": 5_000,
            "cache_creation": {
                "ephemeral_5m_input_tokens": 2_000,
                "ephemeral_1h_input_tokens": 3_000,
            },
            "cache_read_input_tokens": 4_000,
            "output_tokens": 1_000,
            "inference_geo": "global",
            "service_tier": "standard",
            "speed": "standard",
        }
        result = pricing.calculate_anthropic_cost("claude-sonnet-5", usage)
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.0298)

    def test_thinking_is_not_double_charged(self):
        usage = {
            "input_tokens": 1_000,
            "output_tokens": 1_000,
            "output_tokens_details": {"thinking_tokens": 700},
            "inference_geo": "global",
            "service_tier": "standard",
            "speed": "standard",
        }
        result = pricing.calculate_anthropic_cost("claude-sonnet-5", usage)
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.012)
        self.assertEqual(result["usage"]["thinking_tokens"], 700)

    def test_us_inference_multiplier(self):
        usage = {
            "input_tokens": 1_000,
            "output_tokens": 1_000,
            "inference_geo": "us",
            "service_tier": "standard",
            "speed": "standard",
        }
        result = pricing.calculate_anthropic_cost("claude-opus-5", usage)
        self.assertAlmostEqual(result["total_cost_usd"], 0.033)

    def test_missing_geo_on_geo_sensitive_model_refuses_total(self):
        usage = {
            "input_tokens": 1_000,
            "output_tokens": 1_000,
            "service_tier": "standard",
            "speed": "standard",
        }
        result = pricing.calculate_anthropic_cost("claude-opus-5", usage)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])

    def test_haiku_45_does_not_require_inference_geo(self):
        usage = {
            "input_tokens": 1_000,
            "output_tokens": 1_000,
            "service_tier": "standard",
            "speed": "standard",
        }
        result = pricing.calculate_anthropic_cost("claude-haiku-4-5", usage)
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.006)

    def test_fast_mode_opus5(self):
        usage = {
            "input_tokens": 1_000,
            "output_tokens": 1_000,
            "inference_geo": "global",
            "service_tier": "standard",
            "speed": "fast",
        }
        result = pricing.calculate_anthropic_cost("claude-opus-5", usage)
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.06)

    def test_fast_request_without_observed_speed_refuses_total(self):
        usage = {
            "input_tokens": 1_000,
            "output_tokens": 1_000,
            "inference_geo": "global",
            "service_tier": "standard",
        }
        result = pricing.calculate_anthropic_cost(
            "claude-opus-5", usage, speed_hint="fast"
        )
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])

    def test_cache_write_without_ttl_breakdown_refuses_total(self):
        usage = {
            "input_tokens": 1_000,
            "cache_creation_input_tokens": 1_000,
            "output_tokens": 1_000,
            "inference_geo": "global",
            "service_tier": "standard",
            "speed": "standard",
        }
        result = pricing.calculate_anthropic_cost("claude-sonnet-5", usage)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])

    def test_explicit_cache_ttl_hint_can_resolve_missing_breakdown(self):
        usage = {
            "input_tokens": 1_000,
            "cache_creation_input_tokens": 1_000,
            "output_tokens": 1_000,
            "inference_geo": "global",
            "service_tier": "standard",
            "speed": "standard",
        }
        result = pricing.calculate_anthropic_cost(
            "claude-sonnet-5", usage, cache_ttl_hint="5m"
        )
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.0145)

    def test_web_search_adds_per_request_charge(self):
        usage = {
            "input_tokens": 1_000,
            "output_tokens": 1_000,
            "inference_geo": "global",
            "service_tier": "standard",
            "speed": "standard",
            "server_tool_use": {"web_search_requests": 2},
        }
        result = pricing.calculate_anthropic_cost("claude-sonnet-5", usage)
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.032)

    def test_web_fetch_has_no_separate_charge(self):
        usage = {
            "input_tokens": 1_000,
            "output_tokens": 1_000,
            "inference_geo": "global",
            "service_tier": "standard",
            "speed": "standard",
            "server_tool_use": {"web_fetch_requests": 3},
        }
        result = pricing.calculate_anthropic_cost("claude-sonnet-5", usage)
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.012)

    def test_priority_tier_is_list_equivalent_only(self):
        usage = {
            "input_tokens": 1_000,
            "output_tokens": 1_000,
            "inference_geo": "global",
            "service_tier": "priority",
            "speed": "standard",
        }
        result = pricing.calculate_anthropic_cost("claude-sonnet-5", usage)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])
        self.assertAlmostEqual(result["known_list_equivalent_usd"], 0.012)

    def test_auto_tier_without_observed_tier_refuses_total(self):
        usage = {
            "input_tokens": 1_000,
            "output_tokens": 1_000,
            "inference_geo": "global",
            "speed": "standard",
        }
        result = pricing.calculate_anthropic_cost(
            "claude-sonnet-5", usage, service_tier_hint="auto"
        )
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])

    def test_batch_discount(self):
        usage = {
            "input_tokens": 1_000,
            "output_tokens": 1_000,
            "inference_geo": "global",
            "service_tier": "standard",
            "speed": "standard",
        }
        result = pricing.calculate_anthropic_cost(
            "claude-sonnet-5", usage, processing_mode="batch"
        )
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.006)

    def test_unknown_model_never_guesses(self):
        result = pricing.calculate_anthropic_cost(
            "claude-future-99", {"input_tokens": 1, "output_tokens": 1}
        )
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])

    def test_fable_51_special_cache_read_rate(self):
        usage = {
            "input_tokens": 0,
            "cache_read_input_tokens": 1_000_000,
            "output_tokens": 0,
            "inference_geo": "global",
            "service_tier": "standard",
            "speed": "standard",
        }
        result = pricing.calculate_anthropic_cost("claude-fable-5-1", usage)
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.25)

    def test_unknown_server_tool_refuses_all_in_total(self):
        usage = {
            "input_tokens": 1_000,
            "output_tokens": 1_000,
            "inference_geo": "global",
            "service_tier": "standard",
            "speed": "standard",
            "server_tool_use": {"mystery_requests": 1},
        }
        result = pricing.calculate_anthropic_cost("claude-sonnet-5", usage)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])

    def test_litellm_cache_hit_with_nested_cached_tokens(self):
        usage = {
            "prompt_tokens": 7_296,
            "completion_tokens": 1_000,
            "prompt_tokens_details": {"cached_tokens": 7_277},
            "cache_read_input_tokens": 7_277,
            "inference_geo": "global",
            "service_tier": "standard",
            "speed": "standard",
        }
        result = pricing.calculate_anthropic_cost("claude-sonnet-5", usage)
        self.assertTrue(result["complete"])
        self.assertEqual(result["usage"]["input_tokens"], 19)
        expected = (19 * 2 + 7_277 * 0.2 + 1_000 * 10) / 1_000_000
        self.assertAlmostEqual(result["total_cost_usd"], expected)

    def test_litellm_cache_write_keeps_top_level_creation_separate(self):
        usage = {
            "prompt_tokens": 19,
            "completion_tokens": 1_000,
            "prompt_tokens_details": {"cached_tokens": 0},
            "cache_creation_input_tokens": 7_277,
            "cache_read_input_tokens": 0,
            "inference_geo": "global",
            "service_tier": "standard",
            "speed": "standard",
        }
        result = pricing.calculate_anthropic_cost(
            "claude-sonnet-5", usage, cache_ttl_hint="5m"
        )
        self.assertTrue(result["complete"])
        self.assertEqual(result["usage"]["input_tokens"], 19)
        expected = (19 * 2 + 7_277 * 2.5 + 1_000 * 10) / 1_000_000
        self.assertAlmostEqual(result["total_cost_usd"], expected)

    def test_litellm_top_level_cache_read_without_basis_is_refused(self):
        usage = {
            "prompt_tokens": 7_296,
            "completion_tokens": 1_000,
            "cache_read_input_tokens": 7_277,
            "inference_geo": "global",
            "service_tier": "standard",
            "speed": "standard",
        }
        result = pricing.calculate_anthropic_cost("claude-sonnet-5", usage)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])
        self.assertEqual(result["usage"]["input_basis"], "litellm_ambiguous_cache_basis")


if __name__ == "__main__":
    unittest.main()
