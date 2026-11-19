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


class CurrentAnthropicModelRateTests(unittest.TestCase):
    """Rates read from platform.claude.com/docs/en/about-claude/pricing on 2026-11-18."""

    GLOBAL_STANDARD = {"inference_geo": "global", "service_tier": "standard", "speed": "standard"}

    def _cost(self, model, usage, **kwargs):
        merged = dict(self.GLOBAL_STANDARD)
        merged.update(usage)
        return pricing.calculate_anthropic_cost(model, merged, **kwargs)

    def _per_million(self, model):
        # 100,000 tokens per category (at, not over, Haiku 5.5's 100K threshold),
        # scaled back to a per-1M rate.
        n = 100_000
        out = {}
        for key in ("input_tokens", "cache_read_input_tokens", "output_tokens"):
            usage = {"input_tokens": 0, "output_tokens": 0}
            usage[key] = n
            result = self._cost(model, usage)
            self.assertTrue(result["complete"], (model, key, result["notes"]))
            out[key] = round(result["total_cost_usd"] * 1_000_000 / n, 9)
        for ttl, key in (("5m", "ephemeral_5m_input_tokens"), ("1h", "ephemeral_1h_input_tokens")):
            usage = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_creation_input_tokens": n,
                "cache_creation": {key: n},
            }
            result = self._cost(model, usage)
            self.assertTrue(result["complete"], (model, ttl, result["notes"]))
            out["write_" + ttl] = round(result["total_cost_usd"] * 1_000_000 / n, 9)
        return out

    def test_standard_rates(self):
        expected = {
            "claude-fable-5-2": (8.0, 10.0, 16.0, 0.20, 40.0),
            "claude-mythos-5-2": (8.0, 10.0, 16.0, 0.20, 40.0),
            "claude-opus-5-5": (4.0, 5.0, 8.0, 0.20, 20.0),
            "claude-sonnet-5-5": (2.0, 2.50, 4.0, 0.10, 10.0),
            "claude-haiku-5-5": (0.10, 0.125, 0.20, 0.01, 0.50),
        }
        for model, (inp, w5, w1, read, out) in expected.items():
            self.assertEqual(
                self._per_million(model),
                {"input_tokens": inp, "cache_read_input_tokens": read, "output_tokens": out,
                 "write_5m": w5, "write_1h": w1},
                model,
            )

    def test_batch_is_half(self):
        result = self._cost(
            "claude-opus-5-5", {"input_tokens": 1_000_000, "output_tokens": 1_000_000},
            processing_mode="batch",
        )
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 2.0 + 10.0)

    def test_fast_mode_rates(self):
        usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000, "speed": "fast"}
        for model, total in (("claude-fable-5-2", 96.0), ("claude-mythos-5-2", 96.0), ("claude-opus-5-5", 48.0)):
            result = self._cost(model, usage)
            self.assertTrue(result["complete"], model)
            self.assertAlmostEqual(result["total_cost_usd"], total)

    def test_fast_mode_cache_read_uses_cache_multiplier_on_fast_price(self):
        usage = {"input_tokens": 0, "cache_read_input_tokens": 1_000_000, "output_tokens": 0, "speed": "fast"}
        self.assertAlmostEqual(self._cost("claude-fable-5-2", usage)["total_cost_usd"], 0.40)
        self.assertAlmostEqual(self._cost("claude-opus-5-5", usage)["total_cost_usd"], 0.40)

    def test_no_fast_rates_for_sonnet_and_haiku_55(self):
        usage = {"input_tokens": 1_000, "output_tokens": 1_000, "speed": "fast"}
        for model in ("claude-sonnet-5-5", "claude-haiku-5-5"):
            self.assertFalse(self._cost(model, usage)["complete"], model)

    def test_us_geo_multiplier_applies(self):
        usage = {"input_tokens": 1_000_000, "output_tokens": 0, "inference_geo": "us"}
        self.assertAlmostEqual(self._cost("claude-sonnet-5-5", usage)["total_cost_usd"], 2.2)

    def test_haiku_55_at_threshold_uses_lower_rates(self):
        result = self._cost("claude-haiku-5-5", {"input_tokens": 100_000, "output_tokens": 1_000_000})
        self.assertFalse(result["long_context_applied"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.01 + 0.50)

    def test_haiku_55_over_threshold_uses_higher_rates_for_every_category(self):
        result = self._cost("claude-haiku-5-5", {"input_tokens": 100_001, "output_tokens": 1_000_000})
        self.assertTrue(result["long_context_applied"])
        self.assertAlmostEqual(result["total_cost_usd"], 100_001 / 1e6 * 0.50 + 2.50)

    def test_haiku_55_prompt_length_counts_cache_reads_and_writes(self):
        usage = {
            "input_tokens": 1_000,
            "cache_read_input_tokens": 90_000,
            "cache_creation_input_tokens": 10_000,
            "cache_creation": {"ephemeral_5m_input_tokens": 10_000},
            "output_tokens": 0,
        }
        result = self._cost("claude-haiku-5-5", usage)
        self.assertTrue(result["complete"], result["notes"])
        self.assertTrue(result["long_context_applied"])
        expected = 1_000 / 1e6 * 0.50 + 90_000 / 1e6 * 0.05 + 10_000 / 1e6 * 0.625
        self.assertAlmostEqual(result["total_cost_usd"], expected)

    def test_haiku_55_long_context_with_batch_and_us_geo(self):
        result = self._cost(
            "claude-haiku-5-5",
            {"input_tokens": 200_000, "output_tokens": 0, "inference_geo": "us"},
            processing_mode="batch",
        )
        self.assertAlmostEqual(result["total_cost_usd"], 0.2 * 0.50 * 0.5 * 1.1)

    def test_haiku_55_preflight_uses_higher_rate_over_threshold(self):
        import proxy_server

        estimate = proxy_server.anthropic_preflight_input_estimate
        self.assertAlmostEqual(estimate("claude-haiku-5-5", 100_000, {"inference_geo": "global"}), 0.01)
        self.assertAlmostEqual(estimate("claude-haiku-5-5", 200_000, {"inference_geo": "global"}), 0.1)

    def test_mythos_52_is_marked_limited_availability(self):
        self.assertTrue(pricing.resolve_anthropic_model("claude-mythos-5-2")["limited_availability"])


if __name__ == "__main__":
    unittest.main()
