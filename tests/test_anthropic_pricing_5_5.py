import unittest

import anthropic_pricing as ap

USAGE = {
    "input_tokens": 2,
    "cache_creation_input_tokens": 139313,
    "cache_read_input_tokens": 76446,
    "output_tokens": 908,
    "cache_creation": {"ephemeral_1h_input_tokens": 139313, "ephemeral_5m_input_tokens": 0},
    "service_tier": "standard",
    "inference_geo": "global",
}


def expected(rates, usage=USAGE, mult=1.0):
    return mult * (
        usage["input_tokens"] * rates[0]
        + usage["cache_creation"]["ephemeral_5m_input_tokens"] * rates[1]
        + usage["cache_creation"]["ephemeral_1h_input_tokens"] * rates[2]
        + usage["cache_read_input_tokens"] * rates[3]
        + usage["output_tokens"] * rates[4]
    ) / 1_000_000


class Claude55PricingTests(unittest.TestCase):
    """Rates from https://platform.claude.com/docs/en/about-claude/pricing read 2026-11-13."""

    def test_current_models_resolve_with_their_own_verification_date(self):
        for model in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-2"):
            record = ap.resolve_anthropic_model(model)
            self.assertIsNotNone(record, model)
            self.assertEqual(record["verified_at"], "2026-11-13")

    def test_older_models_keep_registry_level_date(self):
        self.assertEqual(ap.resolve_anthropic_model("claude-opus-5")["verified_at"], "2026-09-15")

    def test_opus_5_5(self):
        r = ap.calculate_anthropic_cost("claude-opus-5-5", USAGE)
        self.assertTrue(r["complete"])
        self.assertAlmostEqual(r["total_cost_usd"], expected((4, 5, 8, 0.2, 20)), places=9)

    def test_sonnet_5_5(self):
        r = ap.calculate_anthropic_cost("claude-sonnet-5-5", USAGE)
        self.assertAlmostEqual(r["total_cost_usd"], expected((2, 2.5, 4, 0.1, 10)), places=9)

    def test_fable_5_2(self):
        r = ap.calculate_anthropic_cost("claude-fable-5-2", USAGE)
        self.assertAlmostEqual(r["total_cost_usd"], expected((8, 10, 16, 0.2, 40)), places=9)

    def test_us_geo_multiplier(self):
        usage = dict(USAGE, inference_geo="us")
        r = ap.calculate_anthropic_cost("claude-opus-5-5", usage)
        self.assertAlmostEqual(r["total_cost_usd"], expected((4, 5, 8, 0.2, 20), mult=1.1), places=9)

    def test_haiku_5_5_short_prompt_uses_base_rates(self):
        usage = {"input_tokens": 50000, "output_tokens": 1000, "service_tier": "standard", "inference_geo": "global"}
        r = ap.calculate_anthropic_cost("claude-haiku-5-5", usage)
        self.assertFalse(r["long_context_applied"])
        self.assertAlmostEqual(r["total_cost_usd"], (50000 * 0.10 + 1000 * 0.50) / 1e6, places=12)

    def test_haiku_5_5_long_prompt_uses_long_context_rates(self):
        r = ap.calculate_anthropic_cost("claude-haiku-5-5", USAGE)
        self.assertTrue(r["long_context_applied"])
        self.assertAlmostEqual(r["total_cost_usd"], expected((0.5, 0.625, 1.0, 0.05, 2.5)), places=9)

    def test_fast_mode_cache_activity_is_incomplete_not_guessed(self):
        usage = dict(USAGE, speed="fast")
        r = ap.calculate_anthropic_cost("claude-opus-5-5", usage)
        self.assertFalse(r["complete"])
        self.assertIsNone(r["total_cost_usd"])


if __name__ == "__main__":
    unittest.main()
