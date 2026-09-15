import threading
import types

from fastapi.testclient import TestClient

import config_manager
import proxy_server


class FakeResponse:
    def __init__(self, prompt_tokens=12, completion_tokens=7):
        self.usage = types.SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def model_dump(self):
        return {
            "id": "fake",
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
            },
        }


def _isolate(monkeypatch, tmp_path):
    app_dir = tmp_path / ".tokentotals"
    monkeypatch.setattr(config_manager, "APP_DIR", app_dir)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", app_dir / "config.json")
    monkeypatch.setattr(config_manager, "STATE_FILE", app_dir / "state.json")
    config_manager.init_files()
    conf = config_manager.get_config()
    conf["daily_budget_limit_usd"] = 10.0
    conf["default_max_output_tokens"] = 64
    conf["auto_economy_mode"] = False
    config_manager.save_config(conf)


def test_request_scoped_accounting_globals_do_not_return():
    for name in (
        "CURRENT_THREAD_ID",
        "CURRENT_ROUTINE_FLAG",
        "CURRENT_POTENTIAL_SAVING",
        "track_cost_callback",
    ):
        assert not hasattr(proxy_server, name)


def test_overlapping_requests_keep_accounting_context_isolated(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    original_try_reserve = config_manager.try_reserve_spend
    original_reconcile = config_manager.reconcile_reserved_spend
    observed_reservations = []
    observed_reconciliations = []
    observations_lock = threading.Lock()

    def record_reservation(
        cost_usd,
        thread_id=None,
        potential_saving=0.0,
        is_routine=False,
    ):
        with observations_lock:
            observed_reservations.append(
                {
                    "thread_id": thread_id,
                    "potential_saving": float(potential_saving or 0.0),
                    "is_routine": bool(is_routine),
                }
            )
        return original_try_reserve(
            cost_usd,
            thread_id=thread_id,
            potential_saving=potential_saving,
            is_routine=is_routine,
        )

    def record_reconciliation(reserved_cost_usd, actual_cost_usd, thread_id=None):
        with observations_lock:
            observed_reconciliations.append(thread_id)
        return original_reconcile(
            reserved_cost_usd,
            actual_cost_usd,
            thread_id=thread_id,
        )

    monkeypatch.setattr(config_manager, "try_reserve_spend", record_reservation)
    monkeypatch.setattr(config_manager, "reconcile_reserved_spend", record_reconciliation)

    upstream_barrier = threading.Barrier(2)

    async def overlapping_completion(**kwargs):
        # Both requests must reach the upstream boundary before either response is
        # released. This creates the overlap that made the baseline globals unsafe.
        upstream_barrier.wait(timeout=10)
        return FakeResponse()

    monkeypatch.setattr(proxy_server.litellm, "acompletion", overlapping_completion)

    responses = {}
    failures = []

    def worker(label, thread_id, content):
        try:
            with TestClient(proxy_server.app) as client:
                responses[label] = client.post(
                    "/v1/chat/completions",
                    headers={
                        "Authorization": "Bearer test",
                        "x-thread-id": thread_id,
                    },
                    json={
                        "model": "gpt-6-astra",
                        "messages": [{"role": "user", "content": content}],
                        "max_tokens": 16,
                    },
                )
        except Exception as exc:  # pragma: no cover - surfaced by assertion below
            failures.append(exc)

    routine = threading.Thread(
        target=worker,
        args=("routine", "thread-routine", "ROUTINE hello"),
    )
    nonroutine = threading.Thread(
        target=worker,
        args=(
            "nonroutine",
            "thread-nonroutine",
            "NONROUTINE " + ("substantial context " * 400),
        ),
    )

    routine.start()
    nonroutine.start()
    routine.join(timeout=20)
    nonroutine.join(timeout=20)

    assert not routine.is_alive()
    assert not nonroutine.is_alive()
    assert failures == []
    assert responses["routine"].status_code == 200
    assert responses["nonroutine"].status_code == 200

    by_thread = {item["thread_id"]: item for item in observed_reservations}
    assert set(by_thread) == {"thread-routine", "thread-nonroutine"}

    assert by_thread["thread-routine"]["is_routine"] is True
    assert by_thread["thread-routine"]["potential_saving"] > 0.0

    assert by_thread["thread-nonroutine"]["is_routine"] is False
    assert by_thread["thread-nonroutine"]["potential_saving"] == 0.0

    assert sorted(observed_reconciliations) == [
        "thread-nonroutine",
        "thread-routine",
    ]

    state = config_manager.get_state()
    assert state["total_requests"] == 2
    assert state["flagged_routine_calls"] == 1
    assert state["potential_savings_usd"] > 0.0
