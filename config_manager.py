import os
import json
from pathlib import Path
from datetime import date

APP_DIR = Path.home() / ".tokentotals"
CONFIG_FILE = APP_DIR / "config.json"
STATE_FILE = APP_DIR / "state.json"

DEFAULT_CONFIG = {
    "daily_budget_limit_usd": 10.00,
    "port": 8080,
    "warning_threshold_pct": 75
}

DEFAULT_STATE = {
    "date": str(date.today()),
    "current_spend_usd": 0.00,
    "thread_spend_usd": 0.00,
    "active_thread_id": "default",
    "is_locked": False,
    "total_requests": 0
}

def init_files():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
    if not STATE_FILE.exists():
        with open(STATE_FILE, 'w') as f:
            json.dump(DEFAULT_STATE, f, indent=4)

def get_config():
    init_files()
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception:
        return DEFAULT_CONFIG

def save_config(config_dict):
    init_files()
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_dict, f, indent=4)

def get_state():
    init_files()
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            today_str = str(date.today())
            if state.get("date") != today_str:
                state["date"] = today_str
                state["current_spend_usd"] = 0.00
                state["thread_spend_usd"] = 0.00
                state["is_locked"] = False
                state["total_requests"] = 0
                save_state(state)
            return state
    except Exception:
        return DEFAULT_STATE

def save_state(state_dict):
    init_files()
    with open(STATE_FILE, 'w') as f:
        json.dump(state_dict, f, indent=4)

def update_spend(cost_usd, thread_id=None):
    state = get_state()
    state['current_spend_usd'] = round(state.get('current_spend_usd', 0.0) + cost_usd, 4)
    state['total_requests'] = state.get('total_requests', 0) + 1

    current_thread = state.get('active_thread_id', 'default')
    if thread_id and thread_id != current_thread:
        state['active_thread_id'] = thread_id
        state['thread_spend_usd'] = round(cost_usd, 4)
    else:
        state['thread_spend_usd'] = round(state.get('thread_spend_usd', 0.0) + cost_usd, 4)

    conf = get_config()
    if state['current_spend_usd'] >= conf.get("daily_budget_limit_usd", 10.00):
        state['is_locked'] = True

    save_state(state)
    return state

def set_locked(locked=True):
    state = get_state()
    state['is_locked'] = locked
    save_state(state)

def quick_boost(boost_amount=5.00):
    conf = get_config()
    conf['daily_budget_limit_usd'] = round(conf.get('daily_budget_limit_usd', 10.00) + boost_amount, 2)
    save_config(conf)

    state = get_state()
    state['is_locked'] = False
    save_state(state)
    return conf['daily_budget_limit_usd']

def unlock_circuit_breaker():
    state = get_state()
    state['is_locked'] = False
    save_state(state)