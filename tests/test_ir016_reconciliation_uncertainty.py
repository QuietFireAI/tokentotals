import types

import pytest
from fastapi.testclient import TestClient

import config_manager
import proxy_server


class ResponseWithoutUsage:
    def model_dump(self):
        return {
            "id": "no-usage-response",
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
        }


class StreamWithoutUsage:
    def __init__(self):
        self.sent = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.sent:
            raise StopAsyncIteration
        self.sent = True
        return {"id": "chunk-no-usage", "choices": [{"delta": {"content": "ok"}}]}


@pytest.fixture
def client(monkeypatch, tmp_path):
    app_dir = tmp_path / ".tokentotals"
    monkeypatch.setattr(config_manager, "APP_DIR", app_dir)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", app_dir / "config.json")
    monkeypatch.setattr(config_manager, "STATE_FILE", app_dir / "state.json")
    config_manager.init_files()
    conf = config_manager.get_config()
    conf["daily_budget_limit_usd"] = 10.0
    conf["default_max_output_tokens"] = 64
    config_manager.save_config(conf)
    return TestClient(proxy_server.app)


def test_non_stream_missing_usage_retains_reservation_and_is_marked_unreconciled(client, monkeypatch):
    observed = {}

    async def fake_completion(**kwargs):
        observed["reserved"] = config_manager.get_state()["current_spend_usd"]
        return ResponseWithoutUsage()

    monkeypatch.setattr(proxy_server.litellm, "acompletion", fake_completion)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test"},
        json={
            "model": "gpt-5.6-luna",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 32,
        },
    )

    assert response.status_code == 200
    state = config_manager.get_state()
    assert observed["reserved"] > 0
    assert state["current_spend_usd"] == pytest.approx(observed["reserved"], abs=1e-9)
    assert state.get("unreconciled_responses", 0) == 1
    assert state.get("unreconciled_streams", 0) == 0


def test_stream_missing_usage_retains_reservation_and_counts_total_plus_stream_subset(client, monkeypatch):
    observed = {}

    async def fake_completion(**kwargs):
        observed["reserved"] = config_manager.get_state()["current_spend_usd"]
        return StreamWithoutUsage()

    monkeypatch.setattr(proxy_server.litellm, "acompletion", fake_completion)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test"},
        json={
            "model": "gpt-5.6-luna",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 32,
            "stream": True,
        },
    )

    assert response.status_code == 200
    state = config_manager.get_state()
    assert state["current_spend_usd"] == pytest.approx(observed["reserved"], abs=1e-9)
    assert state.get("unreconciled_responses", 0) == 1
    assert state.get("unreconciled_streams", 0) == 1


def test_usable_non_stream_usage_reconciles_and_does_not_increment_uncertainty(client, monkeypatch):
    class ResponseWithUsage:
        def __init__(self):
            self.usage = types.SimpleNamespace(prompt_tokens=7, completion_tokens=3)

        def model_dump(self):
            return {
                "id": "usage-response",
                "usage": {"prompt_tokens": 7, "completion_tokens": 3},
            }

    async def fake_completion(**kwargs):
        return ResponseWithUsage()

    monkeypatch.setattr(proxy_server.litellm, "acompletion", fake_completion)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test"},
        json={
            "model": "gpt-5.6-luna",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 32,
        },
    )

    assert response.status_code == 200
    state = config_manager.get_state()
    assert state.get("unreconciled_responses", 0) == 0
    assert state.get("unreconciled_streams", 0) == 0
