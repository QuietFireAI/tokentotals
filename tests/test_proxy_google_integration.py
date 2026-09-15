import importlib
import sys
import types
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace


class ProxyGoogleIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        start = datetime(2026, 9, 15, 16, 0, 0)
        return start, start + timedelta(milliseconds=20)

    def test_complete_google_telemetry_uses_local_provider_engine(self):
        response = SimpleNamespace(
            model="gemini-2.5-flash",
            usage=SimpleNamespace(
                prompt_tokens=1_000,
                completion_tokens=1_000,
                total_tokens=2_000,
                prompt_tokens_details=SimpleNamespace(text_tokens=1_000),
                completion_tokens_details=SimpleNamespace(text_tokens=1_000),
                service_tier="standard",
            ),
        )
        start, end = self._times()
        self.proxy.track_cost_callback(
            {"model": "gemini-2.5-flash", "response_cost": 999.0},
            response,
            start,
            end,
        )
        self.assertEqual(len(self.recorded), 1)
        self.assertAlmostEqual(self.recorded[0]["cost_usd"], 0.0028)

    def test_incomplete_google_telemetry_falls_back_to_litellm_cost(self):
        response = SimpleNamespace(
            model="gemini-2.5-flash",
            usage=SimpleNamespace(
                prompt_tokens=1_000,
                completion_tokens=500,
                total_tokens=1_900,
                prompt_tokens_details=SimpleNamespace(text_tokens=1_000),
                completion_tokens_details=SimpleNamespace(text_tokens=500),
                service_tier="standard",
            ),
        )
        start, end = self._times()
        self.proxy.track_cost_callback(
            {"model": "gemini-2.5-flash", "response_cost": 0.031},
            response,
            start,
            end,
        )
        self.assertEqual(len(self.recorded), 1)
        self.assertAlmostEqual(self.recorded[0]["cost_usd"], 0.031)

    def test_missing_litellm_cost_uses_google_known_equivalent_not_zero(self):
        response = SimpleNamespace(
            model="gemini-2.5-flash",
            usage=SimpleNamespace(
                prompt_tokens=1_000,
                completion_tokens=500,
                total_tokens=1_900,
                prompt_tokens_details=SimpleNamespace(text_tokens=1_000),
                completion_tokens_details=SimpleNamespace(text_tokens=500),
                service_tier="standard",
            ),
        )
        start, end = self._times()
        self.proxy.track_cost_callback(
            {"model": "gemini-2.5-flash", "response_cost": 0.0},
            response,
            start,
            end,
        )
        self.assertEqual(len(self.recorded), 1)
        self.assertAlmostEqual(self.recorded[0]["cost_usd"], 0.00167)
        self.assertGreater(self.recorded[0]["cost_usd"], 0.0)

    def test_google_preflight_uses_registry_rate(self):
        result = self.proxy.estimate_google_input_cost(
            "gemini-2.5-flash",
            1_000,
            service_tier="standard",
        )
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.0003)

    def test_google_priority_preflight_uses_priority_rate(self):
        result = self.proxy.estimate_google_input_cost(
            "gemini-2.5-flash",
            1_000,
            service_tier="priority",
        )
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.00054)

    def test_callback_feature_hints_read_nested_google_tools(self):
        hints = self.proxy.google_request_feature_hints_from_callback({
            "litellm_params": {
                "tools": [
                    {"googleSearch": {}},
                    {"url_context": {}},
                    {"file_search": {}},
                    {"function_declarations": []},
                ]
            }
        })
        self.assertEqual(hints, ["file_search", "google_search", "url_context"])

    def test_web_search_options_becomes_google_search_hint(self):
        hints = self.proxy.google_request_feature_hints_from_callback({
            "optional_params": {"web_search_options": {}}
        })
        self.assertEqual(hints, ["google_search"])

    def test_google_prefix_is_recognized_in_live_path(self):
        result = self.proxy.estimate_google_input_cost(
            "gemini/gemini-2.5-flash-lite",
            1_000,
        )
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.0001)


if __name__ == "__main__":
    unittest.main()
