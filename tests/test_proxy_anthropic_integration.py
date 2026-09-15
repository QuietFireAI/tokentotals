import importlib
import sys
import types
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace


class ProxyAnthropicIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Keep this test deterministic even when LiteLLM is not installed in the
        # test runner. proxy_server only needs these callback attributes at import.
        if "litellm" not in sys.modules:
            sys.modules["litellm"] = types.SimpleNamespace(
                suppress_debug_info=True,
                success_callback=[],
            )

        cls.proxy = importlib.import_module("proxy_server")

    def setUp(self):
        self.recorded = []
        self.original_update_spend = self.proxy.config_manager.update_spend
        self.proxy.config_manager.update_spend = lambda **kwargs: self.recorded.append(kwargs)

    def tearDown(self):
        self.proxy.config_manager.update_spend = self.original_update_spend

    def _times(self):
        start = datetime(2026, 9, 15, 12, 0, 0)
        return start, start + timedelta(milliseconds=25)

    def test_complete_anthropic_telemetry_uses_local_provider_engine(self):
        response = SimpleNamespace(
            model="claude-sonnet-5",
            usage=SimpleNamespace(
                input_tokens=1_000,
                output_tokens=1_000,
                inference_geo="global",
                service_tier="standard",
                speed="standard",
            ),
        )
        start, end = self._times()

        self.proxy.track_cost_callback(
            {"model": "claude-sonnet-5", "response_cost": 999.0},
            response,
            start,
            end,
        )

        self.assertEqual(len(self.recorded), 1)
        self.assertAlmostEqual(self.recorded[0]["cost_usd"], 0.012)

    def test_incomplete_anthropic_telemetry_falls_back_to_litellm_cost(self):
        response = SimpleNamespace(
            model="claude-opus-5",
            usage=SimpleNamespace(
                input_tokens=1_000,
                output_tokens=1_000,
                service_tier="standard",
                speed="standard",
            ),
        )
        start, end = self._times()

        self.proxy.track_cost_callback(
            {"model": "claude-opus-5", "response_cost": 0.031},
            response,
            start,
            end,
        )

        self.assertEqual(len(self.recorded), 1)
        self.assertAlmostEqual(self.recorded[0]["cost_usd"], 0.031)

    def test_missing_litellm_cost_uses_known_list_equivalent_not_zero(self):
        response = SimpleNamespace(
            model="claude-opus-5",
            usage=SimpleNamespace(
                input_tokens=1_000,
                output_tokens=1_000,
                service_tier="standard",
                speed="standard",
            ),
        )
        start, end = self._times()

        self.proxy.track_cost_callback(
            {"model": "claude-opus-5"},
            response,
            start,
            end,
        )

        self.assertEqual(len(self.recorded), 1)
        self.assertAlmostEqual(self.recorded[0]["cost_usd"], 0.03)
        self.assertGreater(self.recorded[0]["cost_usd"], 0.0)

    def test_anthropic_preflight_uses_registry_rate(self):
        estimate = self.proxy.anthropic_preflight_input_estimate(
            "claude-sonnet-5",
            1_000,
            {"inference_geo": "global", "speed": "standard"},
        )
        self.assertAlmostEqual(estimate, 0.002)

    def test_anthropic_preflight_unresolved_geo_is_conservative(self):
        estimate = self.proxy.anthropic_preflight_input_estimate(
            "claude-sonnet-5",
            1_000,
            {"speed": "standard"},
        )
        self.assertAlmostEqual(estimate, 0.0022)

    def test_anthropic_fast_preflight_uses_fast_rate_when_verified(self):
        estimate = self.proxy.anthropic_preflight_input_estimate(
            "claude-opus-5",
            1_000,
            {"inference_geo": "global", "speed": "fast"},
        )
        self.assertAlmostEqual(estimate, 0.01)

    def test_unknown_anthropic_model_returns_no_local_preflight_price(self):
        estimate = self.proxy.anthropic_preflight_input_estimate(
            "claude-future-99",
            1_000,
            {"inference_geo": "global", "speed": "standard"},
        )
        self.assertIsNone(estimate)

    def test_callback_param_reads_litellm_nested_params(self):
        self.assertEqual(
            self.proxy.callback_param(
                {"litellm_params": {"inference_geo": "us"}},
                "inference_geo",
            ),
            "us",
        )


if __name__ == "__main__":
    unittest.main()
