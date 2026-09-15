from fastapi.testclient import TestClient

import config_manager
import proxy_server


def _client(monkeypatch, tmp_path):
    app_dir = tmp_path / ".tokentotals"
    monkeypatch.setattr(config_manager, "APP_DIR", app_dir)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", app_dir / "config.json")
    monkeypatch.setattr(config_manager, "STATE_FILE", app_dir / "state.json")
    config_manager.init_files()
    return TestClient(proxy_server.app)


def test_boost_rejects_cross_origin_simple_text_plain_post(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    config_manager.set_locked(True)
    before_config = config_manager.get_config()
    before_state = config_manager.get_state()

    response = client.post(
        "/api/boost",
        content='{"acknowledgement":"BOOST $5"}',
        headers={
            "Content-Type": "text/plain",
            "Origin": "https://example.invalid",
        },
    )

    assert response.status_code == 415
    assert config_manager.get_config() == before_config
    assert config_manager.get_state() == before_state
    assert "access-control-allow-origin" not in response.headers


def test_boost_cors_preflight_is_not_granted(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    response = client.options(
        "/api/boost",
        headers={
            "Origin": "https://example.invalid",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 405
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-methods" not in response.headers


def test_boost_wrong_missing_or_nonobject_ack_preserves_budget_and_lock(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    config_manager.set_locked(True)
    before_config = config_manager.get_config()
    before_state = config_manager.get_state()

    attempts = [
        lambda: client.post("/api/boost"),
        lambda: client.post(
            "/api/boost",
            content="null",
            headers={"Content-Type": "application/json"},
        ),
        lambda: client.post("/api/boost", json={}),
        lambda: client.post("/api/boost", json={"acknowledgement": "YES"}),
        lambda: client.post("/api/boost", json={"acknowledgement": "BOOST $50"}),
    ]
    expected_status = [415, 400, 400, 400, 400]

    for attempt, status in zip(attempts, expected_status):
        response = attempt()
        assert response.status_code == status
        assert config_manager.get_config() == before_config
        assert config_manager.get_state() == before_state


def test_valid_boost_changes_only_budget_limit_and_lock(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    state = config_manager.get_state()
    state.update(
        {
            "current_spend_usd": 4.125,
            "potential_savings_usd": 0.375,
            "thread_spend_usd": 1.25,
            "active_thread_id": "thread-boost-proof",
            "is_locked": True,
            "total_requests": 9,
            "flagged_routine_calls": 3,
            "unreconciled_streams": 2,
        }
    )
    config_manager.save_state(state)
    before_state = config_manager.get_state()
    before_config = config_manager.get_config()

    response = client.post(
        "/api/boost",
        json={"acknowledgement": "BOOST $5"},
    )

    assert response.status_code == 200
    after_state = config_manager.get_state()
    after_config = config_manager.get_config()

    expected_state = dict(before_state)
    expected_state["is_locked"] = False
    expected_config = dict(before_config)
    expected_config["daily_budget_limit_usd"] = round(
        float(before_config["daily_budget_limit_usd"]) + 5.0, 2
    )

    assert after_state == expected_state
    assert after_config == expected_config
