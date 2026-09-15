import types

import pytest
from fastapi.testclient import TestClient

import config_manager
import proxy_server


def test_provider_reported_usage_supersedes_preflight_token_heuristic(monkeypatch, tmp_path):
    """Pre-flight estimation paces the request; provider usage drives final reconciliation."""
    app_dir = tmp_path / ".tokentotals"
    monkeypatch.setattr(config_manager, "APP_DIR", app_dir)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", app_dir / "config.json")
    monkeypatch.setattr(config_manager, "STATE_FILE", app_dir / "state.json")
    config_manager.init_files()

    conf = config_manager.get_config()
    conf["daily_budget_limit_usd"] = 10.0
    conf["default_max_output_tokens"] = 50
    config_manager.save_config(conf)

    # Force an intentionally large local estimate so the pre-flight reservation is
    # observably different from the provider-reported usage used after the response.
    monkeypatch.setattr(proxy_server, "estimate_text_tokens", lambda text, model=None: 10_000)

    class ProviderResponse:
        usage = types.SimpleNamespace(prompt_tokens=7, completion_tokens=3)

        def model_dump(self):
            return {
                "id": "provider-usage-proof",
                "usage": {"prompt_tokens": 7, "completion_tokens": 3},
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            }

    observed = {}

    async def fake_completion(**kwargs):
        observed["preflight_spend"] = config_manager.get_state()["current_spend_usd"]
        return ProviderResponse()

    monkeypatch.setattr(proxy_server.litellm, "acompletion", fake_completion)
    client = TestClient(proxy_server.app)

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test"},
        json={
            "model": "gpt-5.6-luna",
            "messages": [{"role": "user", "content": "tiny prompt"}],
            "max_tokens": 50,
        },
    )

    assert response.status_code == 200

    pricing = proxy_server.resolve_model("gpt-5.6-luna")
    expected_final = proxy_server.calculate_cost(
        pricing, 7, 3, conservative=False
    )["total_cost_usd"]
    final_spend = config_manager.get_state()["current_spend_usd"]

    assert observed["preflight_spend"] > expected_final
    assert final_spend == pytest.approx(round(expected_final, 6), abs=1e-9)
    assert final_spend < observed["preflight_spend"]
