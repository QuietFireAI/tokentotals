import types

import litellm
import pytest
from fastapi.testclient import TestClient

import config_manager
import proxy_server


class FakeResponse:
    def __init__(self, prompt_tokens=100, completion_tokens=50):
        self.usage = types.SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)

    def model_dump(self):
        return {"id":"fake","usage":{"prompt_tokens":self.usage.prompt_tokens,"completion_tokens":self.usage.completion_tokens}}


@pytest.fixture
def client(monkeypatch, tmp_path):
    app_dir = tmp_path / ".tokentotals"
    monkeypatch.setattr(config_manager, "APP_DIR", app_dir)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", app_dir / "config.json")
    monkeypatch.setattr(config_manager, "STATE_FILE", app_dir / "state.json")
    config_manager.init_files()
    conf = config_manager.get_config()
    conf["daily_budget_limit_usd"] = 10.0
    conf["default_max_output_tokens"] = 128
    config_manager.save_config(conf)
    return TestClient(proxy_server.app)


def test_proxy_uses_installed_litellm_dependency():
    assert proxy_server.litellm is litellm
    assert callable(litellm.acompletion)
    assert getattr(litellm, "__file__", None)


def test_unlock_requires_real_acknowledgement(client):
    config_manager.set_locked(True)
    assert client.post("/api/unlock", json={}).status_code == 400
    assert config_manager.get_state()["is_locked"] is True
    response = client.post("/api/unlock", json={"acknowledgement": "I UNDERSTAND"})
    assert response.status_code == 200
    assert config_manager.get_state()["is_locked"] is False


def test_boost_requires_explicit_acknowledgement(client):
    before = config_manager.get_config()["daily_budget_limit_usd"]
    assert client.post("/api/boost", json={}).status_code == 400
    assert config_manager.get_config()["daily_budget_limit_usd"] == before
    assert client.post("/api/boost", json={"acknowledgement": "BOOST $5"}).status_code == 200
    assert config_manager.get_config()["daily_budget_limit_usd"] == before + 5.0


def test_unknown_price_never_reaches_upstream(client, monkeypatch):
    called = False
    async def fail_if_called(**kwargs):
        nonlocal called
        called = True
        return FakeResponse()
    monkeypatch.setattr(proxy_server.litellm, "acompletion", fail_if_called)
    response = client.post("/v1/chat/completions", json={"model":"made-up-model","messages":[{"role":"user","content":"hi"}]})
    assert response.status_code == 422
    assert called is False


def test_output_reservation_can_block_before_upstream(client, monkeypatch):
    conf = config_manager.get_config()
    conf["daily_budget_limit_usd"] = 0.00001
    config_manager.save_config(conf)
    called = False
    async def fail_if_called(**kwargs):
        nonlocal called
        called = True
        return FakeResponse()
    monkeypatch.setattr(proxy_server.litellm, "acompletion", fail_if_called)
    response = client.post("/v1/chat/completions", json={"model":"gpt-6-astra","messages":[{"role":"user","content":"hello"}],"max_tokens":1000})
    assert response.status_code == 403
    assert called is False


def test_conflicting_output_bounds_reserve_largest_before_upstream(client, monkeypatch):
    conf = config_manager.get_config()
    conf["daily_budget_limit_usd"] = 0.005
    config_manager.save_config(conf)
    called = False

    async def fail_if_called(**kwargs):
        nonlocal called
        called = True
        return FakeResponse()

    monkeypatch.setattr(proxy_server.litellm, "acompletion", fail_if_called)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-6-astra",
            "messages": [{"role": "user", "content": "hello"}],
            "max_completion_tokens": 1,
            "max_tokens": 1000,
        },
    )
    assert response.status_code == 403
    assert called is False


def test_auto_economy_reserves_for_model_actually_routed(client, monkeypatch):
    conf = config_manager.get_config()
    conf["daily_budget_limit_usd"] = 0.005
    conf["auto_economy_mode"] = True
    config_manager.save_config(conf)
    called = False

    async def fail_if_called(**kwargs):
        nonlocal called
        called = True
        return FakeResponse()

    # Force a deliberately more-expensive "economy" route to prove the reservation
    # follows the model actually sent rather than the originally requested model.
    monkeypatch.setattr(proxy_server, "_economy_model_for", lambda provider: "gpt-6-astra")
    monkeypatch.setattr(proxy_server.litellm, "acompletion", fail_if_called)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-5.6-luna",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 1000,
        },
    )
    assert response.status_code == 403
    assert called is False


def test_missing_max_tokens_gets_bounded_and_reconciled(client, monkeypatch):
    captured = {}
    async def fake_completion(**kwargs):
        captured.update(kwargs)
        return FakeResponse(prompt_tokens=10, completion_tokens=5)
    monkeypatch.setattr(proxy_server.litellm, "acompletion", fake_completion)
    response = client.post("/v1/chat/completions", headers={"Authorization":"Bearer test"}, json={"model":"gpt-5.6-luna","messages":[{"role":"user","content":"hello"}]})
    assert response.status_code == 200
    assert 1 <= captured["max_tokens"] <= 128
    state = config_manager.get_state()
    assert state["current_spend_usd"] > 0
    assert state["current_spend_usd"] < 0.001


def test_dashboard_has_no_fabricated_static_telemetry(client):
    html = client.get("/dashboard").text
    assert "199k" not in html
    assert "14.5M" not in html
    assert "85%" not in html
    assert "Unreconciled Streams" in html
