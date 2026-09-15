import importlib
import inspect
from pathlib import Path
import unittest
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import config_manager


ROOT = Path(__file__).resolve().parents[1]


class _FakeResponse:
    def model_dump(self):
        return {"ok": True}


class OptimizerRetirementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proxy = importlib.import_module("proxy_server")

    def test_runtime_optimizer_symbols_are_removed(self):
        proxy_source = (ROOT / "proxy_server.py").read_text(encoding="utf-8")
        config_source = (ROOT / "config_manager.py").read_text(encoding="utf-8-sig")
        gui_source = (ROOT / "app_gui.py").read_text(encoding="utf-8")

        for retired in (
            "CURRENT_ROUTINE_FLAG",
            "CURRENT_POTENTIAL_SAVING",
            "econ_model",
            "is_premium_model",
            "is_lightweight",
        ):
            self.assertNotIn(retired, proxy_source)

        self.assertNotIn("auto_economy_mode", proxy_source)
        self.assertNotIn("auto_economy_mode", config_source)
        self.assertNotIn("potential_savings_usd", config_source)
        self.assertNotIn("flagged_routine_calls", config_source)
        self.assertNotIn("get_savings_text", gui_source)

    def test_default_state_and_config_do_not_expose_retired_optimizer(self):
        self.assertNotIn("auto_economy_mode", config_manager.DEFAULT_CONFIG)
        self.assertNotIn("potential_savings_usd", config_manager.DEFAULT_STATE)
        self.assertNotIn("flagged_routine_calls", config_manager.DEFAULT_STATE)

        params = inspect.signature(config_manager.update_spend).parameters
        self.assertEqual(list(params), ["cost_usd", "thread_id"])

    def test_status_endpoint_omits_retired_optimizer_metrics(self):
        original_get_state = self.proxy.config_manager.get_state
        original_get_config = self.proxy.config_manager.get_config
        self.proxy.config_manager.get_state = lambda: {
            "current_spend_usd": 1.0,
            "thread_spend_usd": 0.2,
            "is_locked": False,
            "potential_savings_usd": 999.0,
            "flagged_routine_calls": 99,
        }
        self.proxy.config_manager.get_config = lambda: {
            "daily_budget_limit_usd": 10.0,
            "warning_threshold_pct": 75,
            "port": 8080,
            "auto_economy_mode": True,
        }
        try:
            payload = TestClient(self.proxy.app).get("/api/status").json()
        finally:
            self.proxy.config_manager.get_state = original_get_state
            self.proxy.config_manager.get_config = original_get_config

        self.assertNotIn("potential_savings_usd", payload)
        self.assertNotIn("flagged_routine_calls", payload)
        self.assertNotIn("auto_economy_mode", payload)

    def test_legacy_auto_economy_true_cannot_remap_requested_model(self):
        proxy = self.proxy
        originals = {
            "litellm": proxy.litellm,
            "get_state": proxy.config_manager.get_state,
            "get_config": proxy.config_manager.get_config,
            "set_locked": proxy.config_manager.set_locked,
            "estimate_text_tokens": proxy.estimate_text_tokens,
            "preflight_input_estimate": proxy.preflight_input_estimate,
        }

        class _LiteLLMStub:
            pass

        stub = _LiteLLMStub()
        stub.acompletion = AsyncMock(return_value=_FakeResponse())

        proxy.litellm = stub
        proxy.config_manager.get_state = lambda: {
            "current_spend_usd": 0.0,
            "thread_spend_usd": 0.0,
            "is_locked": False,
        }
        proxy.config_manager.get_config = lambda: {
            "daily_budget_limit_usd": 10.0,
            "warning_threshold_pct": 75,
            "auto_economy_mode": True,
        }
        proxy.config_manager.set_locked = lambda *_args, **_kwargs: None
        proxy.estimate_text_tokens = lambda *_args, **_kwargs: 10
        proxy.preflight_input_estimate = lambda *_args, **_kwargs: (0.001, "test")

        try:
            response = TestClient(proxy.app).post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "format this"}],
                },
            )
        finally:
            proxy.litellm = originals["litellm"]
            proxy.config_manager.get_state = originals["get_state"]
            proxy.config_manager.get_config = originals["get_config"]
            proxy.config_manager.set_locked = originals["set_locked"]
            proxy.estimate_text_tokens = originals["estimate_text_tokens"]
            proxy.preflight_input_estimate = originals["preflight_input_estimate"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(stub.acompletion.await_count, 1)
        self.assertEqual(stub.acompletion.await_args.kwargs["model"], "gpt-4o")

    def test_dashboard_and_current_docs_do_not_claim_active_auto_downgrade(self):
        proxy_source = (ROOT / "proxy_server.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        whitepaper = (ROOT / "TokenTotals_Security_Whitepaper.md").read_text(encoding="utf-8-sig")

        self.assertNotIn("Potential Savings Opportunity", proxy_source)
        self.assertNotIn("routine calls flagged", proxy_source)
        self.assertNotIn("estimated potential savings of up to ~90%", proxy_source)
        self.assertNotIn("automatically remaps routine/simple prompts", readme)
        self.assertIn("does **not** silently replace the model or provider", readme)
        self.assertNotIn("## 5. Counterfactual Model Optimization & Advisory", whitepaper)
        self.assertIn("## 5. Model-Integrity Boundary", whitepaper)


if __name__ == "__main__":
    unittest.main()
