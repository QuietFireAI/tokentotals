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

# Preflight reservations are deliberately process-local and ephemeral. They exist
# only while requests are in flight and are never persisted to state.json, so a
# daemon restart cannot strand phantom reserved dollars on disk.
_INFLIGHT_RESERVATIONS = {}
_SETTLED_RESERVATION_IDS = set()

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


def _inflight_reserved_usd_unlocked():
    total = 0.0
    for reservation in _INFLIGHT_RESERVATIONS.values():
        try:
            total += float(reservation.get("estimated_cost_usd", 0.0) or 0.0)
        except (AttributeError, TypeError, ValueError):
            continue
    return round(total, 10)


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


def get_inflight_reserved_usd():
    with _DATA_LOCK:
        return _inflight_reserved_usd_unlocked()


def get_pacing_snapshot():
    """Return actual spend plus ephemeral in-flight pacing commitments."""
    with _DATA_LOCK:
        state = get_state()
        conf = get_config()
        current = float(state.get('current_spend_usd', 0.0) or 0.0)
        reserved = _inflight_reserved_usd_unlocked()
        limit = float(conf.get('daily_budget_limit_usd', 10.00) or 0.0)
        committed = current + reserved
        return {
            'current_spend_usd': round(current, 4),
            'inflight_reserved_usd': round(reserved, 10),
            'committed_spend_usd': round(committed, 10),
            'available_budget_usd': round(max(0.0, limit - committed), 10),
            'daily_budget_limit_usd': limit,
            'is_locked': bool(state.get('is_locked', False)),
            'reservation_count': len(_INFLIGHT_RESERVATIONS),
        }


def reserve_preflight_budget(reservation_id, estimated_cost_usd, thread_id=None):
    """Atomically admit and reserve preflight-estimated headroom for one request.

    The reservation covers only the defensible preflight estimate available before
    execution (currently input-side pricing). It is not a guarantee of the final
    full-turn cost, which can still exceed the reservation after output/tools/etc.
    are known.
    """
    reservation_key = str(reservation_id or '').strip()
    if not reservation_key:
        raise ValueError('reservation_id must be a non-empty string')
    try:
        estimated_cost = float(estimated_cost_usd)
    except (TypeError, ValueError) as exc:
        raise ValueError('estimated_cost_usd must be numeric') from exc
    if estimated_cost < 0:
        raise ValueError('estimated_cost_usd cannot be negative')

    with _DATA_LOCK:
        if reservation_key in _INFLIGHT_RESERVATIONS:
            raise ValueError('reservation_id is already active')

        state = get_state()
        conf = get_config()
        current = float(state.get('current_spend_usd', 0.0) or 0.0)
        reserved_before = _inflight_reserved_usd_unlocked()
        limit = float(conf.get('daily_budget_limit_usd', 10.00) or 0.0)

        if state.get('is_locked', False):
            return {
                'accepted': False,
                'reason': 'locked',
                'current_spend_usd': round(current, 4),
                'inflight_reserved_usd': round(reserved_before, 10),
                'daily_budget_limit_usd': limit,
            }

        # A request that exceeds the threshold even without other in-flight work
        # is a true local budget breach and preserves the existing lock behavior.
        if current + estimated_cost > limit:
            state['is_locked'] = True
            save_state(state)
            return {
                'accepted': False,
                'reason': 'budget_limit',
                'current_spend_usd': round(current, 4),
                'inflight_reserved_usd': round(reserved_before, 10),
                'daily_budget_limit_usd': limit,
            }

        # If only concurrent reservations consume the remaining headroom, reject
        # this request without permanently locking the daemon. Headroom may become
        # available again as those requests settle or fail.
        if current + reserved_before + estimated_cost > limit:
            return {
                'accepted': False,
                'reason': 'inflight_headroom',
                'current_spend_usd': round(current, 4),
                'inflight_reserved_usd': round(reserved_before, 10),
                'daily_budget_limit_usd': limit,
            }

        _INFLIGHT_RESERVATIONS[reservation_key] = {
            'estimated_cost_usd': estimated_cost,
            'thread_id': str(thread_id or 'default'),
        }
        reserved_after = _inflight_reserved_usd_unlocked()
        return {
            'accepted': True,
            'reason': 'reserved',
            'reservation_id': reservation_key,
            'estimated_cost_usd': estimated_cost,
            'current_spend_usd': round(current, 4),
            'inflight_reserved_usd': round(reserved_after, 10),
            'daily_budget_limit_usd': limit,
        }


def release_preflight_reservation(reservation_id):
    """Release a reservation when a request never produces a billable callback."""
    reservation_key = str(reservation_id or '').strip()
    if not reservation_key:
        return None
    with _DATA_LOCK:
        return _INFLIGHT_RESERVATIONS.pop(reservation_key, None)


def update_spend(cost_usd, thread_id=None, reservation_id=None):
    with _DATA_LOCK:
        reservation_key = str(reservation_id or '').strip()
        if reservation_key and reservation_key in _SETTLED_RESERVATION_IDS:
            # A duplicated success callback must not double-charge local state.
            return get_state()

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

        # Persist the actual cost before releasing its reservation. Because both
        # operations occur under the same process-local lock, no other request can
        # observe a gap where neither actual spend nor reserved headroom is counted.
        save_state(state)
        if reservation_key:
            _INFLIGHT_RESERVATIONS.pop(reservation_key, None)
            _SETTLED_RESERVATION_IDS.add(reservation_key)
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