import asyncio
import socket
import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
import uvicorn

import config_manager
import proxy_server


class ProviderResponse:
    def __init__(self, *, prompt_tokens=10, completion_tokens=5, content="ok"):
        self.usage = types.SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        self._content = content

    def model_dump(self):
        return {
            "id": "integration-response",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": self._content,
                    }
                }
            ],
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
            },
        }


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def live_server(monkeypatch, tmp_path):
    """Run the production FastAPI app behind a real Uvicorn loopback listener."""
    app_dir = tmp_path / ".tokentotals"
    monkeypatch.setattr(config_manager, "APP_DIR", app_dir)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", app_dir / "config.json")
    monkeypatch.setattr(config_manager, "STATE_FILE", app_dir / "state.json")
    config_manager.init_files()

    port = _free_loopback_port()
    conf = config_manager.get_config()
    conf["daily_budget_limit_usd"] = 10.0
    conf["default_max_output_tokens"] = 64
    conf["port"] = port
    config_manager.save_config(conf)

    server = uvicorn.Server(
        uvicorn.Config(
            proxy_server.app,
            host="127.0.0.1",
            port=port,
            log_level="critical",
            access_log=False,
            lifespan="off",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 5.0
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=2.0)
        pytest.fail("Uvicorn loopback integration server did not start")

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5.0)
        if thread.is_alive():
            pytest.fail("Uvicorn loopback integration server did not stop cleanly")


def test_real_loopback_http_round_trip_reconciles_state(live_server, monkeypatch):
    async def fake_completion(**kwargs):
        assert kwargs["model"] == "gpt-5.6-luna"
        assert kwargs["max_tokens"] == 20
        return ProviderResponse(content="provider response over real loopback HTTP")

    monkeypatch.setattr(proxy_server.litellm, "acompletion", fake_completion)

    with httpx.Client(base_url=live_server, timeout=10.0, trust_env=False) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer integration-test", "X-Thread-ID": "tcp-one"},
            json={
                "model": "gpt-5.6-luna",
                "messages": [{"role": "user", "content": "hello over tcp"}],
                "max_tokens": 20,
            },
        )
        status = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "provider response over real loopback HTTP"
    assert status.status_code == 200

    pricing = proxy_server.resolve_model("gpt-5.6-luna")
    expected_actual = proxy_server.calculate_cost(
        pricing, 10, 5, conservative=False
    )["total_cost_usd"]
    state = config_manager.get_state()
    assert state["total_requests"] == 1
    assert state["unreconciled_streams"] == 0
    assert state["current_spend_usd"] == pytest.approx(round(expected_actual, 6), abs=1e-9)
    assert status.json()["current_spend_usd"] == pytest.approx(round(expected_actual, 6), abs=1e-9)


def test_concurrent_loopback_http_burst_has_no_lost_spend_updates(live_server, monkeypatch):
    request_count = 24
    upstream_calls = []

    async def delayed_completion(**kwargs):
        upstream_calls.append(kwargs["model"])
        # Keep requests overlapped long enough for the real server to exercise
        # concurrent reservation/reconciliation rather than a serial happy path.
        await asyncio.sleep(0.075)
        return ProviderResponse(prompt_tokens=10, completion_tokens=5)

    monkeypatch.setattr(proxy_server.litellm, "acompletion", delayed_completion)
    start_barrier = threading.Barrier(request_count)

    def send_one(index: int):
        start_barrier.wait(timeout=10.0)
        with httpx.Client(base_url=live_server, timeout=15.0, trust_env=False) as client:
            return client.post(
                "/v1/chat/completions",
                headers={
                    "Authorization": "Bearer integration-test",
                    "X-Thread-ID": f"tcp-load-{index}",
                },
                json={
                    "model": "gpt-5.6-luna",
                    "messages": [{"role": "user", "content": f"load request {index}"}],
                    "max_tokens": 20,
                },
            ).status_code

    with ThreadPoolExecutor(max_workers=request_count) as pool:
        statuses = list(pool.map(send_one, range(request_count)))

    assert statuses == [200] * request_count
    assert len(upstream_calls) == request_count

    pricing = proxy_server.resolve_model("gpt-5.6-luna")
    per_request_actual = proxy_server.calculate_cost(
        pricing, 10, 5, conservative=False
    )["total_cost_usd"]
    expected_total = round(per_request_actual * request_count, 6)
    state = config_manager.get_state()

    assert state["total_requests"] == request_count
    assert state["unreconciled_streams"] == 0
    assert state["is_locked"] is False
    assert state["current_spend_usd"] == pytest.approx(expected_total, abs=1e-9)


def test_repeated_concurrent_loopback_soak_preserves_exact_accounting(live_server, monkeypatch):
    """Exercise cumulative state integrity across repeated real-TCP concurrency bursts.

    This is a bounded local soak, not a throughput benchmark: eight rounds of 32
    simultaneous requests (256 total). State is checked after every round so a
    transient lost update cannot be hidden by a correct-looking final value.
    """
    concurrency = 32
    rounds = 8
    upstream_calls = 0
    upstream_lock = threading.Lock()

    async def delayed_completion(**kwargs):
        nonlocal upstream_calls
        with upstream_lock:
            upstream_calls += 1
        await asyncio.sleep(0.025)
        return ProviderResponse(prompt_tokens=10, completion_tokens=5)

    monkeypatch.setattr(proxy_server.litellm, "acompletion", delayed_completion)

    pricing = proxy_server.resolve_model("gpt-5.6-luna")
    per_request_actual = proxy_server.calculate_cost(
        pricing, 10, 5, conservative=False
    )["total_cost_usd"]

    for round_index in range(rounds):
        start_barrier = threading.Barrier(concurrency)

        def send_one(index: int):
            start_barrier.wait(timeout=15.0)
            with httpx.Client(base_url=live_server, timeout=20.0, trust_env=False) as client:
                response = client.post(
                    "/v1/chat/completions",
                    headers={
                        "Authorization": "Bearer soak-test",
                        "X-Thread-ID": f"soak-{round_index}-{index}",
                    },
                    json={
                        "model": "gpt-5.6-luna",
                        "messages": [
                            {
                                "role": "user",
                                "content": f"soak round {round_index} request {index}",
                            }
                        ],
                        "max_tokens": 20,
                    },
                )
                return response.status_code

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            statuses = list(pool.map(send_one, range(concurrency)))

        assert statuses == [200] * concurrency

        expected_requests = (round_index + 1) * concurrency
        expected_spend = round(per_request_actual * expected_requests, 6)
        state = config_manager.get_state()

        assert upstream_calls == expected_requests
        assert state["total_requests"] == expected_requests
        assert state["unreconciled_streams"] == 0
        assert state["is_locked"] is False
        assert state["current_spend_usd"] == pytest.approx(expected_spend, abs=1e-9)

        with httpx.Client(base_url=live_server, timeout=10.0, trust_env=False) as client:
            status = client.get("/api/status")
        assert status.status_code == 200
        assert status.json()["total_requests"] == expected_requests
        assert status.json()["current_spend_usd"] == pytest.approx(expected_spend, abs=1e-9)
