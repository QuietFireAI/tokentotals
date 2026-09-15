import json
import os
import threading
from pathlib import Path
from datetime import date

APP_DIR = Path.home() / ".tokentotals"
CONFIG_FILE = APP_DIR / "config.json"
STATE_FILE = APP_DIR / "state.json"
_LOCK = threading.RLock()

DEFAULT_CONFIG = {
    "daily_budget_limit_usd": 10.00,
    "port": 8080,
    "auto_economy_mode": False,
    "warning_threshold_pct": 75,
    "default_max_output_tokens": 4096,
}

DEFAULT_STATE = {
    "date": str(date.today()),
    "current_spend_usd": 0.00,
    "potential_savings_usd": 0.00,
    "thread_spend_usd": 0.00,
    "active_thread_id": "default",
    "is_locked": False,
    "total_requests": 0,
    "flagged_routine_calls": 0,
    "unreconciled_responses": 0,
    "unreconciled_streams": 0,
}


def _atomic_json_write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=4)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def init_files():
    with _LOCK:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            _atomic_json_write(CONFIG_FILE, dict(DEFAULT_CONFIG))
        if not STATE_FILE.exists():
            _atomic_json_write(STATE_FILE, dict(DEFAULT_STATE))


def _load_config_unlocked():
    init_files()
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        data = {}
    merged = dict(DEFAULT_CONFIG)
    if isinstance(data, dict):
        merged.update(data)
    return merged


def _load_state_unlocked():
    init_files()
    try:
        with STATE_FILE.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except Exception:
        state = {}
    merged = dict(DEFAULT_STATE)
    if isinstance(state, dict):
        merged.update(state)
    today_str = str(date.today())
    if merged.get("date") != today_str:
        merged.update(dict(DEFAULT_STATE))
        merged["date"] = today_str
        _atomic_json_write(STATE_FILE, merged)
    return merged


def get_config():
    with _LOCK:
        return _load_config_unlocked()


def save_config(config_dict):
    with _LOCK:
        merged = dict(DEFAULT_CONFIG)
        merged.update(config_dict or {})
        _atomic_json_write(CONFIG_FILE, merged)


def get_state():
    with _LOCK:
        return _load_state_unlocked()


def save_state(state_dict):
    with _LOCK:
        merged = dict(DEFAULT_STATE)
        merged.update(state_dict or {})
        _atomic_json_write(STATE_FILE, merged)


def _apply_thread_cost(state, delta, thread_id):
    if thread_id and thread_id != state.get("active_thread_id", "default"):
        state["active_thread_id"] = thread_id
        state["thread_spend_usd"] = max(0.0, round(delta, 6))
    else:
        state["thread_spend_usd"] = max(
            0.0, round(state.get("thread_spend_usd", 0.0) + delta, 6)
        )


def try_reserve_spend(cost_usd, thread_id=None, potential_saving=0.0, is_routine=False):
    """Atomically reserve worst-case request cost before upstream egress."""
    cost_usd = max(0.0, float(cost_usd or 0.0))
    with _LOCK:
        state = _load_state_unlocked()
        conf = _load_config_unlocked()
        limit = float(conf.get("daily_budget_limit_usd", 10.0))
        if state.get("is_locked"):
            return False, state
        projected = float(state.get("current_spend_usd", 0.0)) + cost_usd
        if projected > limit:
            state["is_locked"] = True
            _atomic_json_write(STATE_FILE, state)
            return False, state

        state["current_spend_usd"] = round(projected, 6)
        state["total_requests"] = int(state.get("total_requests", 0)) + 1
        if is_routine:
            state["flagged_routine_calls"] = int(state.get("flagged_routine_calls", 0)) + 1
            state["potential_savings_usd"] = round(
                float(state.get("potential_savings_usd", 0.0)) + max(0.0, float(potential_saving or 0.0)),
                6,
            )
        _apply_thread_cost(state, cost_usd, thread_id)
        _atomic_json_write(STATE_FILE, state)
        return True, state


def reconcile_reserved_spend(reserved_cost_usd, actual_cost_usd, thread_id=None):
    """Replace a pre-flight reservation with the post-response estimate."""
    reserved = max(0.0, float(reserved_cost_usd or 0.0))
    actual = max(0.0, float(actual_cost_usd or 0.0))
    delta = actual - reserved
    with _LOCK:
        state = _load_state_unlocked()
        state["current_spend_usd"] = max(
            0.0, round(float(state.get("current_spend_usd", 0.0)) + delta, 6)
        )
        if not thread_id or thread_id == state.get("active_thread_id"):
            state["thread_spend_usd"] = max(
                0.0, round(float(state.get("thread_spend_usd", 0.0)) + delta, 6)
            )
        conf = _load_config_unlocked()
        if state["current_spend_usd"] >= float(conf.get("daily_budget_limit_usd", 10.0)):
            state["is_locked"] = True
        _atomic_json_write(STATE_FILE, state)
        return state


def mark_unreconciled_response(delta=1, *, stream=False):
    """Record a completed response that lacked usable final usage telemetry.

    The conservative reservation remains unchanged. ``unreconciled_responses`` is
    the total across response modes; ``unreconciled_streams`` is retained as the
    backwards-compatible stream subset for existing state/readers.
    """
    with _LOCK:
        state = _load_state_unlocked()
        state["unreconciled_responses"] = max(
            0, int(state.get("unreconciled_responses", 0)) + int(delta)
        )
        if stream:
            state["unreconciled_streams"] = max(
                0, int(state.get("unreconciled_streams", 0)) + int(delta)
            )
        _atomic_json_write(STATE_FILE, state)
        return state


def mark_unreconciled_stream(delta=1):
    """Backward-compatible stream-specific wrapper."""
    return mark_unreconciled_response(delta, stream=True)


def update_spend(cost_usd, thread_id=None, potential_saving=0.0, is_routine=False):
    accepted, state = try_reserve_spend(
        cost_usd,
        thread_id=thread_id,
        potential_saving=potential_saving,
        is_routine=is_routine,
    )
    return state


def set_locked(locked=True):
    with _LOCK:
        state = _load_state_unlocked()
        state["is_locked"] = bool(locked)
        _atomic_json_write(STATE_FILE, state)


def quick_boost(boost_amount=5.00):
    with _LOCK:
        conf = _load_config_unlocked()
        conf["daily_budget_limit_usd"] = round(
            float(conf.get("daily_budget_limit_usd", 10.00)) + float(boost_amount), 2
        )
        _atomic_json_write(CONFIG_FILE, conf)
        state = _load_state_unlocked()
        state["is_locked"] = False
        _atomic_json_write(STATE_FILE, state)
        return conf["daily_budget_limit_usd"]


def unlock_circuit_breaker():
    with _LOCK:
        state = _load_state_unlocked()
        state["is_locked"] = False
        _atomic_json_write(STATE_FILE, state)
