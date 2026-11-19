import unittest
from types import SimpleNamespace

import openai_pricing as pricing


class OpenAIPricingTests(unittest.TestCase):
    def test_standard_sol_response(self):
        usage = {
            "input_tokens": 10_000,
            "input_tokens_details": {"cached_tokens": 4_000, "cache_write_tokens": 0},
            "output_tokens": 2_000,
            "output_tokens_details": {"reasoning_tokens": 500},
        }
        result = pricing.calculate_openai_cost("gpt-5.6-sol", usage, "default")
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.0656)
        self.assertEqual(result["usage"]["reasoning_tokens"], 500)

    def test_astra_cache_write(self):
        usage = {
            "input_tokens": 10_000,
            "input_tokens_details": {"cached_tokens": 2_000, "cache_write_tokens": 3_000},
            "output_tokens": 1_000,
        }
        result = pricing.calculate_openai_cost("gpt-6-astra", usage, "default")
        self.assertAlmostEqual(result["total_cost_usd"], 0.1395)

    def test_long_context_multiplier(self):
        usage = {"input_tokens": 300_000, "output_tokens": 10_000}
        result = pricing.calculate_openai_cost("gpt-5.6-sol", usage, "default")
        self.assertTrue(result["long_context_applied"])
        self.assertAlmostEqual(result["total_cost_usd"], 2.7)

    def test_fast_multiplier(self):
        # openai.com/api-fast-mode (read 2026-11-18): Sol Fast is $10 input,
        # $1 cached input, $60 output per 1M tokens (2.5x / 2.5x / 3x).
        usage = {"input_tokens": 1_000, "output_tokens": 1_000}
        result = pricing.calculate_openai_cost("gpt-5.6-sol", usage, "fast")
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.07)
        self.assertEqual(
            result["service_tier_multiplier"],
            {"input": 2.5, "cached_input": 2.5, "cache_write": None, "output": 3.0},
        )

    def test_sol_fast_cached_input_rate(self):
        usage = {
            "input_tokens": 100_000,
            "input_tokens_details": {"cached_tokens": 100_000, "cache_write_tokens": 0},
            "output_tokens": 0,
        }
        result = pricing.calculate_openai_cost("gpt-5.6-sol", usage, "priority")
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.1)

    def test_terra_and_luna_fast_stay_2x(self):
        # Under the 272K long-context threshold: 100K input, 100K output.
        usage = {"input_tokens": 100_000, "output_tokens": 100_000}
        terra = pricing.calculate_openai_cost("gpt-5.6-terra", usage, "fast")
        luna = pricing.calculate_openai_cost("gpt-5.6-luna", usage, "fast")
        self.assertAlmostEqual(terra["total_cost_usd"], (4.0 + 24.0) / 10)
        self.assertAlmostEqual(luna["total_cost_usd"], (0.4 + 2.4) / 10)

    def test_fast_cache_write_has_no_published_rate(self):
        usage = {
            "input_tokens": 10_000,
            "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 5_000},
            "output_tokens": 100,
        }
        result = pricing.calculate_openai_cost("gpt-5.6-sol", usage, "fast")
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])
        self.assertIsNone(result["components_usd"]["cache_write"])

    def test_fast_long_context_is_not_guessed(self):
        usage = {"input_tokens": 300_000, "output_tokens": 1_000}
        for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
            result = pricing.calculate_openai_cost(model, usage, "fast")
            self.assertFalse(result["complete"], model)
            self.assertIsNone(result["total_cost_usd"], model)
            self.assertTrue(any("exclude long context" in n for n in result["notes"]), model)

    def test_astra_fast_long_context_stays_priced(self):
        # Astra's model page states Fast mode is 2x the applicable rates.
        usage = {"input_tokens": 300_000, "output_tokens": 1_000}
        result = pricing.calculate_openai_cost("gpt-6-astra", usage, "fast")
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.3 * 10 * 2 * 2 + 0.001 * 50 * 1.5 * 2)
        self.assertEqual(result["service_tier_multiplier"], 2.0)

    def test_sol_promotional_window_date(self):
        record = pricing.resolve_openai_model("gpt-5.6-sol")
        self.assertEqual(record["pricing_window"]["valid_through_at_least"], "2026-11-30")

    def test_ultrafast_is_recognized_as_unpriced_not_mapped_to_fast_or_standard(self):
        usage = {"input_tokens": 1_000, "output_tokens": 1_000}
        result = pricing.calculate_openai_cost("gpt-5.6-sol", usage, "ultrafast")
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])
        self.assertEqual(result["service_tier"], "ultrafast")
        self.assertTrue(any("Unsupported or unverified service tier: ultrafast" in n for n in result["notes"]))

    def test_auto_tier_is_not_fixed_multiplier(self):
        result = pricing.calculate_openai_cost(
            "gpt-5.6-sol", {"input_tokens": 1_000, "output_tokens": 1_000}, "auto"
        )
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])

    def test_unknown_model_never_guesses(self):
        result = pricing.calculate_openai_cost(
            "gpt-99-future", {"input_tokens": 1_000, "output_tokens": 1_000}
        )
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])

    def test_chat_completions_shape(self):
        usage = SimpleNamespace(
            prompt_tokens=2_000,
            prompt_tokens_details=SimpleNamespace(cached_tokens=1_000, cache_write_tokens=0),
            completion_tokens=1_000,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=700),
        )
        result = pricing.calculate_openai_cost("o3-mini", usage, "default")
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.00605)
        self.assertEqual(result["usage"]["reasoning_tokens"], 700)

    def test_unverified_service_tier_refuses_total(self):
        result = pricing.calculate_openai_cost(
            "o1", {"input_tokens": 1_000, "output_tokens": 1_000}, "fast"
        )
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])

    def test_audio_usage_marks_incomplete(self):
        usage = {
            "input_tokens": 1_000,
            "input_tokens_details": {"audio_tokens": 100},
            "output_tokens": 1_000,
        }
        result = pricing.calculate_openai_cost("gpt-5.6-sol", usage, "default")
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])

    def test_auto_tier_without_resolved_response_tier_refuses_total(self):
        response = SimpleNamespace(
            model="gpt-5.6-sol",
            usage=SimpleNamespace(input_tokens=1_000, output_tokens=1_000),
            service_tier=None,
        )
        result = pricing.calculate_openai_response_cost(
            "gpt-5.6-sol", response, request_service_tier="auto"
        )
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])

    def test_explicit_default_tier_can_price_without_response_tier(self):
        response = SimpleNamespace(
            model="gpt-5.6-sol",
            usage=SimpleNamespace(input_tokens=1_000, output_tokens=1_000),
            service_tier=None,
        )
        result = pricing.calculate_openai_response_cost(
            "gpt-5.6-sol", response, request_service_tier="default"
        )
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.024)

    def test_hosted_tool_activity_refuses_token_only_total(self):
        response = SimpleNamespace(
            model="gpt-6-astra",
            service_tier="default",
            usage=SimpleNamespace(input_tokens=1_000, output_tokens=1_000),
            output=[SimpleNamespace(type="web_search_call")],
        )
        result = pricing.calculate_openai_response_cost("gpt-6-astra", response)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])
        self.assertEqual(result["hosted_tool_activity"], ["web_search_call"])

    def test_request_feature_hint_refuses_all_in_total(self):
        response = SimpleNamespace(
            model="gpt-6-astra",
            service_tier="default",
            usage=SimpleNamespace(input_tokens=1_000, output_tokens=1_000),
            output=[],
        )
        result = pricing.calculate_openai_response_cost(
            "gpt-6-astra", response, request_feature_hints=["file_search"]
        )
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])
        self.assertEqual(result["hosted_tool_activity"], ["file_search"])


if __name__ == "__main__":
    unittest.main()
