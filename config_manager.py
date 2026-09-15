import json
import threading
from pathlib import Path
from datetime import date

APP_DIR = Path.home() / ".tokentotals"
CONFIG_FILE = APP_DIR / "config.json"
STATE_FILE = APP_DIR / "state.json"

# TokenTotals currently runs one local daemon process. This re-entrant lock makes
# read-modify-write operations atomic across callbacks/threads inside that process.
# It is deliberately not represented as a cross-process file/database lock.
_DATA_LOCK = threading.RLock()

DEFAULT_CONFIG = {
    "daily_budget_limit_usd": 10.00,
    "port": 8080,
    "warning_threshold_pct": 75
}

DEFAULT_STATE = {
    "date": str(date.today()),
    "current_spend_usd": 0.00,
    "thread_spend_usd": 0.00,
    "thread_spend_by_id": {},
    "active_thread_id": "default",
    "is_locked": False,
    "total_requests": 0
}


def _fresh_default_state():
    state = dict(DEFAULT_STATE)
    state["thread_spend_by_id"] = {}
    return state


def init_files():
    with _DATA_LOCK:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
        if not STATE_FILE.exists():
            with open(STATE_FILE, 'w') as f:
                json.dump(_fresh_default_state(), f, indent=4)


def get_config():
    with _DATA_LOCK:
        init_files()
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            return dict(DEFAULT_CONFIG)


def save_config(config_dict):
    with _DATA_LOCK:
        init_files()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_dict, f, indent=4)


def get_state():
    with _DATA_LOCK:
        init_files()
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)

            today_str = str(date.today())
            if state.get("date") != today_str:
                state["date"] = today_str
                state["current_spend_usd"] = 0.00
                state["thread_spend_usd"] = 0.00
                state["thread_spend_by_id"] = {}
                state["active_thread_id"] = "default"
                state["is_locked"] = False
                state["total_requests"] = 0
                save_state(state)
            elif not isinstance(state.get("thread_spend_by_id"), dict):
                state["thread_spend_by_id"] = {}

            return state
        except Exception:
            return _fresh_default_state()


def save_state(state_dict):
    with _DATA_LOCK:
        init_files()
        with open(STATE_FILE, 'w') as f:
            json.dump(state_dict, f, indent=4)


def update_spend(cost_usd, thread_id=None):
    with _DATA_LOCK:
        state = get_state()
        state['current_spend_usd'] = round(state.get('current_spend_usd', 0.0) + cost_usd, 4)
        state['total_requests'] = state.get('total_requests', 0) + 1

        current_thread = str(state.get('active_thread_id') or 'default')
        thread_key = str(thread_id or current_thread or 'default')
        thread_totals = state.get('thread_spend_by_id')
        if not isinstance(thread_totals, dict):
            thread_totals = {}

        # Migrate the currently tracked legacy thread total the first time an old
        # state file is updated, so upgrading does not discard today's displayed
        # thread spend.
        if not thread_totals:
            legacy_thread_spend = state.get('thread_spend_usd', 0.0) or 0.0
            if legacy_thread_spend:
                thread_totals[current_thread] = round(float(legacy_thread_spend), 4)

        thread_totals[thread_key] = round(
            float(thread_totals.get(thread_key, 0.0) or 0.0) + cost_usd,
            4,
        )
        state['thread_spend_by_id'] = thread_totals
        state['active_thread_id'] = thread_key
        state['thread_spend_usd'] = thread_totals[thread_key]

        conf = get_config()
        if state['current_spend_usd'] >= conf.get("daily_budget_limit_usd", 10.00):
            state['is_locked'] = True

        save_state(state)
        return state


def set_locked(locked=True):
    with _DATA_LOCK:
        state = get_state()
        state['is_locked'] = locked
        save_state(state)


def quick_boost(boost_amount=5.00):
    with _DATA_LOCK:
        conf = get_config()
        conf['daily_budget_limit_usd'] = round(conf.get('daily_budget_limit_usd', 10.00) + boost_amount, 2)
        save_config(conf)

        state = get_state()
        state['is_locked'] = False
        save_state(state)
        return conf['daily_budget_limit_usd']


def unlock_circuit_breaker():
    with _DATA_LOCK:
        state = get_state()
        state['is_locked'] = False
        save_state(state)