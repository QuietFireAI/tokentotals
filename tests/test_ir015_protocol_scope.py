from starlette.routing import WebSocketRoute
from fastapi.testclient import TestClient

import config_manager
import proxy_server


class FakeSSEStream:
    def __init__(self):
        self.sent = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.sent:
            raise StopAsyncIteration
        self.sent = True
        return {"id": "chunk-1", "choices": [{"delta": {"content": "ok"}}]}


def test_tokentotals_exposes_no_websocket_route():
    """The current FastAPI application must not silently grow a WebSocket surface."""
    websocket_routes = [
        route for route in proxy_server.app.routes if isinstance(route, WebSocketRoute)
    ]
    assert websocket_routes == []


def test_streaming_chat_path_is_real_http_sse(monkeypatch, tmp_path):
    """A real streamed chat request uses HTTP text/event-stream, not WebSocket."""
    app_dir = tmp_path / ".tokentotals"
    monkeypatch.setattr(config_manager, "APP_DIR", app_dir)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", app_dir / "config.json")
    monkeypatch.setattr(config_manager, "STATE_FILE", app_dir / "state.json")
    config_manager.init_files()

    conf = config_manager.get_config()
    conf["daily_budget_limit_usd"] = 10.0
    conf["default_max_output_tokens"] = 32
    config_manager.save_config(conf)

    async def fake_completion(**kwargs):
        assert kwargs["stream"] is True
        return FakeSSEStream()

    monkeypatch.setattr(proxy_server.litellm, "acompletion", fake_completion)
    client = TestClient(proxy_server.app)
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test"},
        json={
            "model": "gpt-5.6-luna",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 8,
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data:" in response.text
    assert "[DONE]" in response.text
