from pathlib import Path
import importlib
import sys
import types
import unittest

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


class PreflightPricingFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "litellm" not in sys.modules:
            sys.modules["litellm"] = types.SimpleNamespace(
                suppress_debug_info=True,
                success_callback=[],
                model_cost={},
                token_counter=lambda **kwargs: max(1, len(kwargs.get("text", "")) // 4),
            )
        cls.proxy = importlib.import_module("proxy_server")

    def setUp(self):
        self.original_model_cost = self.proxy.litellm.model_cost
        self.original_get_state = self.proxy.config_manager.get_state
        self.original_get_config = self.proxy.config_manager.get_config

    def tearDown(self):
        self.proxy.litellm.model_cost = self.original_model_cost
        self.proxy.config_manager.get_state = self.original_get_state
        self.proxy.config_manager.get_config = self.original_get_config

    def test_machine_specific_pricing_plugin_is_removed(self):
        source = (ROOT / "proxy_server.py").read_text(encoding="utf-8")
        self.assertNotIn("Command Center", source)
        self.assertNotIn("from pricing_engine", source)
        self.assertNotIn("legacy_input_estimate", source)
        self.assertNotIn("input_price_per_1m\": 2.50", source)

    def test_litellm_catalog_fallback_requires_exact_model_key(self):
        self.proxy.litellm.model_cost = {
            "other_provider/exact-model": {"input_cost_per_token": 0.000002}
        }
        self.assertAlmostEqual(
            self.proxy.litellm_catalog_input_estimate(
                "other_provider/exact-model", 1_000
            ),
            0.002,
        )
        self.assertIsNone(
            self.proxy.litellm_catalog_input_estimate("exact-model", 1_000)
        )

    def test_unknown_provider_can_use_pinned_catalog_as_secondary_estimate(self):
        self.proxy.litellm.model_cost = {
            "other_provider/exact-model": {"input_cost_per_token": 0.000002}
        }
        cost, source = self.proxy.preflight_input_estimate(
            "other_provider/exact-model", 1_000, {}
        )
        self.assertAlmostEqual(cost, 0.002)
        self.assertEqual(source, "litellm_catalog_fallback")

    def test_dedicated_provider_failure_does_not_fall_through_to_litellm(self):
        self.proxy.litellm.model_cost = {
            "gemini-future-99": {"input_cost_per_token": 0.000001}
        }
        cost, source = self.proxy.preflight_input_estimate(
            "gemini-future-99", 1_000, {}
        )
        self.assertIsNone(cost)
        self.assertEqual(source, "google_registry_unresolved")

    def test_negative_or_missing_catalog_rate_is_not_used(self):
        self.proxy.litellm.model_cost = {
            "other_provider/negative": {"input_cost_per_token": -1},
            "other_provider/missing": {},
        }
        self.assertIsNone(
            self.proxy.litellm_catalog_input_estimate(
                "other_provider/negative", 1_000
            )
        )
        self.assertIsNone(
            self.proxy.litellm_catalog_input_estimate(
                "other_provider/missing", 1_000
            )
        )

    def test_unpriced_model_is_blocked_before_upstream_call(self):
        self.proxy.litellm.model_cost = {}
        self.proxy.config_manager.get_state = lambda: {
            "is_locked": False,
            "current_spend_usd": 0.0,
        }
        self.proxy.config_manager.get_config = lambda: {
            "daily_budget_limit_usd": 10.0,
            "warning_threshold_pct": 75,
            "auto_economy_mode": False,
        }

        client = TestClient(self.proxy.app)
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "not-a-priced-provider/model",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("Pricing Unavailable", detail)
        self.assertIn("not sent upstream", detail)


if __name__ == "__main__":
    unittest.main()
