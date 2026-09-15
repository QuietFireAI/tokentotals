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


def test_unlock_rejects_missing_malformed_nonobject_and_wrong_ack_without_unlocking(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    attempts = [
        lambda: client.post("/api/unlock"),
        lambda: client.post(
            "/api/unlock",
            content="{not-json",
            headers={"Content-Type": "application/json"},
        ),
        lambda: client.post("/api/unlock", json=None),
        lambda: client.post("/api/unlock", json={}),
        lambda: client.post("/api/unlock", json={"acknowledgement": "YES"}),
        lambda: client.post("/api/unlock", json={"acknowledgement": "I UNDERSTAND THIS"}),
        lambda: client.post(
            "/api/unlock",
            content='{"acknowledgement":"I UNDERSTAND"}',
            headers={"Content-Type": "text/plain", "Origin": "https://example.invalid"},
        ),
    ]
    expected_status = [415, 400, 400, 400, 400, 400, 415]

    for attempt, status in zip(attempts, expected_status):
        config_manager.set_locked(True)
        response = attempt()
        assert response.status_code == status
        assert config_manager.get_state()["is_locked"] is True


def test_unlock_acknowledgement_normalization_is_intentional(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    config_manager.set_locked(True)

    response = client.post(
        "/api/unlock",
        json={"acknowledgement": "  i understand  "},
    )

    assert response.status_code == 200
    assert config_manager.get_state()["is_locked"] is False
    assert "verified user acknowledgment" in response.json()["message"]


def test_unlock_changes_only_lock_state_not_accounting_or_budget(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    conf = config_manager.get_config()
    conf["daily_budget_limit_usd"] = 17.25
    config_manager.save_config(conf)

    state = config_manager.get_state()
    state.update(
        {
            "current_spend_usd": 4.125,
            "potential_savings_usd": 0.375,
            "thread_spend_usd": 1.25,
            "active_thread_id": "thread-proof",
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
        "/api/unlock",
        json={"acknowledgement": "I UNDERSTAND"},
    )

    assert response.status_code == 200
    after_state = config_manager.get_state()
    after_config = config_manager.get_config()

    expected_state = dict(before_state)
    expected_state["is_locked"] = False
    assert after_state == expected_state
    assert after_config == before_config
