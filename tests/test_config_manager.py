import config_manager


def _isolate(monkeypatch, tmp_path, budget=1.0):
    app_dir = tmp_path / ".tokentotals"
    monkeypatch.setattr(config_manager, "APP_DIR", app_dir)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", app_dir / "config.json")
    monkeypatch.setattr(config_manager, "STATE_FILE", app_dir / "state.json")
    config_manager.init_files()
    conf = config_manager.get_config()
    conf["daily_budget_limit_usd"] = budget
    config_manager.save_config(conf)


def test_reservation_is_atomic_and_fails_closed(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path, budget=0.10)
    ok, _ = config_manager.try_reserve_spend(0.08, thread_id="a")
    assert ok is True
    ok, state = config_manager.try_reserve_spend(0.03, thread_id="b")
    assert ok is False
    assert state["is_locked"] is True
    assert config_manager.get_state()["current_spend_usd"] == 0.08


def test_reconcile_releases_unused_reservation(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path, budget=1.0)
    ok, _ = config_manager.try_reserve_spend(0.50, thread_id="a")
    assert ok
    state = config_manager.reconcile_reserved_spend(0.50, 0.12, thread_id="a")
    assert state["current_spend_usd"] == 0.12
