import json
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


class FakeStreamWithoutUsage:
    def __init__(self):
        self._sent = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._sent:
            raise StopAsyncIteration
        self._sent = True
        return {"id": "fake-chunk", "choices": [{"delta": {"content": "ok"}}]}


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


def test_preflight_commits_input_and_output_reservation_before_upstream(client, monkeypatch):
    model = "gpt-5.6-luna"
    messages = [{"role": "user", "content": "hello"}]
    max_output = 100
    prompt_text = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
    pricing = proxy_server.resolve_model(model)
    estimated_input = proxy_server.estimate_text_tokens(prompt_text, model)
    input_only = proxy_server.calculate_cost(
        pricing, estimated_input, 0, conservative=True
    )["total_cost_usd"]
    expected_reservation = proxy_server.calculate_cost(
        pricing, estimated_input, max_output, conservative=True
    )["total_cost_usd"]
    observed = {}

    async def inspect_reservation_before_upstream(**kwargs):
        observed["spend_before_upstream"] = config_manager.get_state()["current_spend_usd"]
        observed["max_tokens"] = kwargs.get("max_tokens")
        return FakeResponse(prompt_tokens=10, completion_tokens=5)

    monkeypatch.setattr(proxy_server.litellm, "acompletion", inspect_reservation_before_upstream)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test"},
        json={"model": model, "messages": messages, "max_tokens": max_output},
    )

    assert response.status_code == 200
    assert observed["max_tokens"] == max_output
    assert observed["spend_before_upstream"] == pytest.approx(round(expected_reservation, 6), abs=1e-9)
    assert observed["spend_before_upstream"] > input_only


def test_stream_without_final_usage_keeps_full_reservation(client, monkeypatch):
    observed = {}

    async def fake_stream_completion(**kwargs):
        observed["spend_before_upstream"] = config_manager.get_state()["current_spend_usd"]
        return FakeStreamWithoutUsage()

    monkeypatch.setattr(proxy_server.litellm, "acompletion", fake_stream_completion)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test"},
        json={
            "model": "gpt-5.6-luna",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 100,
            "stream": True,
        },
    )

    assert response.status_code == 200
    state = config_manager.get_state()
    assert observed["spend_before_upstream"] > 0
    assert state["current_spend_usd"] == pytest.approx(observed["spend_before_upstream"], abs=1e-9)
    assert state["unreconciled_responses"] == 1
    assert state["unreconciled_streams"] == 1


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


def test_non_stream_response_content_is_not_decorated_with_tokentotals_badge(client, monkeypatch):
    class ProviderContentResponse:
        def __init__(self):
            self.usage = types.SimpleNamespace(prompt_tokens=10, completion_tokens=5)

        def model_dump(self):
            return {
                "id": "provider-response",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "provider answer stays untouched",
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

    async def fake_completion(**kwargs):
        return ProviderContentResponse()

    monkeypatch.setattr(proxy_server.litellm, "acompletion", fake_completion)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test"},
        json={
            "model": "gpt-5.6-luna",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 20,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["choices"][0]["message"]["content"] == "provider answer stays untouched"
    assert "TokenTotals" not in json.dumps(payload)


def test_dashboard_has_no_fabricated_static_telemetry(client):
    html = client.get("/dashboard").text

    # Ban both the exact baseline placeholder values and the unsupported metric
    # surfaces they occupied. If these metrics are implemented later, this test
    # must be deliberately changed alongside real runtime telemetry support.
    forbidden = (
        "199k",
        "14.5M",
        "85%",
        "tok/turn",
        "tokens processed",
        "Prompt Cache Savings",
        "Prompt caching discount active",
        "velocityVal",
        "cumulTokVal",
        "cacheVal",
    )
    for marker in forbidden:
        assert marker not in html

    assert "Unreconciled Responses" in html


def test_dashboard_dynamic_metrics_are_backed_by_status_fields(client):
    state = config_manager.get_state()
    state.update(
        {
            "current_spend_usd": 1.234567,
            "thread_spend_usd": 0.345678,
            "potential_savings_usd": 0.456789,
            "total_requests": 7,
            "unreconciled_responses": 3,
            "unreconciled_streams": 2,
        }
    )
    config_manager.save_state(state)

    status = client.get("/api/status")
    assert status.status_code == 200
    payload = status.json()
    assert payload["current_spend_usd"] == pytest.approx(1.234567)
    assert payload["thread_spend_usd"] == pytest.approx(0.345678)
    assert payload["potential_savings_usd"] == pytest.approx(0.456789)
    assert payload["total_requests"] == 7
    assert payload["unreconciled_responses"] == 3
    assert payload["unreconciled_streams"] == 2

    html = client.get("/dashboard").text
    assert "fetch('/api/status')" in html
    for field in (
        "current_spend_usd",
        "daily_budget_limit_usd",
        "remaining_budget_usd",
        "thread_spend_usd",
        "total_requests",
        "potential_savings_usd",
        "pricing_verified_at",
        "unreconciled_responses",
        "port",
        "last_latency_ms",
        "is_locked",
        "traffic_light",
    ):
        assert f"d.{field}" in html
