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

# Keep substantially more precision internally than the four-decimal human-facing
# display. Repeated sub-cent turns must not disappear through per-turn display
# rounding before they are accumulated.
INTERNAL_MONEY_DECIMALS = 10

# Preflight reservations are deliberately process-local and ephemeral. They exist
# only while requests are in flight and are never persisted to state.json, so a
# daemon restart cannot strand phantom reserved dollars on disk.
_INFLIGHT_RESERVATIONS = {}
_SETTLED_RESERVATION_IDS = set()

DEFAULT_CONFIG = {
    "daily_budget_limit_usd": 10.00,
    "port": 8080,
    "warning_threshold_pct": 75,
    # Optional per-turn reminder. None means Turn Notice is disabled until the
    # user chooses a positive dollar value. This is not a provider account limit.
    "turn_notice_threshold_usd": None,
}

DEFAULT_STATE = {
    "date": str(date.today()),
    "current_spend_usd": 0.00,
    "thread_spend_usd": 0.00,
    "thread_spend_by_id": {},
    "active_thread_id": "default",
    "is_locked": False,
    "total_requests": 0,
    # Same-day headroom granted by typing "I UNDERSTAND" (see
    # unlock_circuit_breaker). Added on top of the configured threshold; the saved
    # threshold in config.json is never changed by an acknowledgment.
    "acknowledged_headroom_usd": 0.00,
    "acknowledgment_count": 0,
    # Turns whose post-response cost could not be priced. Their preflight input
    # estimate is posted to spend so the pacing threshold still sees them, and is
    # tracked here so the posted figure is never presented as a full price.
    "unpriced_turn_count": 0,
    "unpriced_preflight_estimate_usd": 0.00,
}

# Fields reset at the start of each local day.
_DAILY_RESET_FIELDS = (
    "current_spend_usd",
    "thread_spend_usd",
    "thread_spend_by_id",
    "active_thread_id",
    "is_locked",
    "total_requests",
    "acknowledged_headroom_usd",
    "acknowledgment_count",
    "unpriced_turn_count",
    "unpriced_preflight_estimate_usd",
)


def _fresh_default_state():
    state = dict(DEFAULT_STATE)
    state["thread_spend_by_id"] = {}
    return state


def _money(value):
    return round(float(value or 0.0), INTERNAL_MONEY_DECIMALS)


def _configured_limit(conf):
    return float(conf.get('daily_budget_limit_usd', 10.00) or 0.0)


def _effective_limit(conf, state):
    """Configured threshold plus any same-day "I UNDERSTAND" headroom."""
    headroom = float(state.get('acknowledged_headroom_usd', 0.0) or 0.0)
    return _money(_configured_limit(conf) + max(0.0, headroom))


def get_effective_limit():
    with _DATA_LOCK:
        return _effective_limit(get_config(), get_state())


def _inflight_reserved_usd_unlocked():
    total = 0.0
    for reservation in _INFLIGHT_RESERVATIONS.values():
        try:
            total += float(reservation.get("estimated_cost_usd", 0.0) or 0.0)
        except (AttributeError, TypeError, ValueError):
            continue
    return _money(total)


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
                fresh = _fresh_default_state()
                for key in _DAILY_RESET_FIELDS:
                    state[key] = fresh[key]
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
    """Return posted spend plus ephemeral in-flight pacing commitments."""
    with _DATA_LOCK:
        state = get_state()
        conf = get_config()
        current = float(state.get('current_spend_usd', 0.0) or 0.0)
        reserved = _inflight_reserved_usd_unlocked()
        limit = _effective_limit(conf, state)
        committed = current + reserved
        return {
            'current_spend_usd': _money(current),
            'inflight_reserved_usd': _money(reserved),
            'committed_spend_usd': _money(committed),
            'available_budget_usd': _money(max(0.0, limit - committed)),
            'daily_budget_limit_usd': limit,
            'configured_limit_usd': _configured_limit(conf),
            'acknowledged_headroom_usd': _money(state.get('acknowledged_headroom_usd', 0.0)),
            'is_locked': bool(state.get('is_locked', False)),
            'reservation_count': len(_INFLIGHT_RESERVATIONS),
        }


def reserve_preflight_budget(reservation_id, estimated_cost_usd, thread_id=None):
    """Atomically admit and reserve preflight-estimated threshold capacity.

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
        limit = _effective_limit(conf, state)

        if state.get('is_locked', False):
            return {
                'accepted': False,
                'reason': 'locked',
                'current_spend_usd': _money(current),
                'inflight_reserved_usd': _money(reserved_before),
                'daily_budget_limit_usd': limit,
            }

        # A request that crosses the configured local threshold even without other
        # in-flight work preserves the existing lock behavior.
        if current + estimated_cost > limit:
            state['is_locked'] = True
            save_state(state)
            return {
                'accepted': False,
                'reason': 'budget_limit',
                'current_spend_usd': _money(current),
                'inflight_reserved_usd': _money(reserved_before),
                'daily_budget_limit_usd': limit,
            }

        # If only concurrent reservations consume the remaining threshold capacity,
        # reject this request without permanently locking the daemon. Capacity may
        # become available again as those requests settle or fail.
        if current + reserved_before + estimated_cost > limit:
            return {
                'accepted': False,
                'reason': 'inflight_headroom',
                'current_spend_usd': _money(current),
                'inflight_reserved_usd': _money(reserved_before),
                'daily_budget_limit_usd': limit,
            }

        _INFLIGHT_RESERVATIONS[reservation_key] = {
            'estimated_cost_usd': _money(estimated_cost),
            'thread_id': str(thread_id or 'default'),
        }
        reserved_after = _inflight_reserved_usd_unlocked()
        return {
            'accepted': True,
            'reason': 'reserved',
            'reservation_id': reservation_key,
            'estimated_cost_usd': _money(estimated_cost),
            'current_spend_usd': _money(current),
            'inflight_reserved_usd': _money(reserved_after),
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
    """Post one settled turn.

    cost_usd=None means the turn could not be priced after the response. It is
    NOT posted as $0: the turn's preflight input estimate (the only defensible
    figure TokenTotals has for it) is posted so the pacing threshold still counts
    it, and the turn is counted in unpriced_turn_count /
    unpriced_preflight_estimate_usd so the posted spend is shown as incomplete.
    """
    with _DATA_LOCK:
        reservation_key = str(reservation_id or '').strip()
        if reservation_key and reservation_key in _SETTLED_RESERVATION_IDS:
            # A duplicated success callback must not double-charge local state.
            return get_state()

        state = get_state()
        if cost_usd is None:
            reservation = _INFLIGHT_RESERVATIONS.get(reservation_key) if reservation_key else None
            try:
                cost = _money((reservation or {}).get('estimated_cost_usd', 0.0))
            except (TypeError, ValueError):
                cost = 0.0
            state['unpriced_turn_count'] = int(state.get('unpriced_turn_count', 0) or 0) + 1
            state['unpriced_preflight_estimate_usd'] = _money(
                float(state.get('unpriced_preflight_estimate_usd', 0.0) or 0.0) + cost
            )
        else:
            cost = _money(cost_usd)
        state['current_spend_usd'] = _money(
            float(state.get('current_spend_usd', 0.0) or 0.0) + cost
        )
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
                thread_totals[current_thread] = _money(legacy_thread_spend)

        thread_totals[thread_key] = _money(
            float(thread_totals.get(thread_key, 0.0) or 0.0) + cost
        )
        state['thread_spend_by_id'] = thread_totals
        state['active_thread_id'] = thread_key
        state['thread_spend_usd'] = thread_totals[thread_key]

        conf = get_config()
        if state['current_spend_usd'] >= _effective_limit(conf, state):
            state['is_locked'] = True

        # Persist the actual cost before releasing its reservation. Because both
        # operations occur under the same process-local lock, no other request can
        # observe a gap where neither actual spend nor reserved threshold capacity
        # is counted.
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
    """The "I UNDERSTAND" acknowledgment.

    Clearing is_locked alone did nothing: the next request was re-checked against
    the same threshold and locked again. The acknowledgment now grants one more
    configured threshold of headroom for the rest of today, measured from the
    spend posted so far:

        effective threshold = spend posted at acknowledgment + configured threshold

    The saved threshold in config.json is unchanged (that is what +$5 boost is
    for), the headroom resets at the daily reset, and the lock re-engages if spend
    reaches the new effective threshold. Each further acknowledgment re-applies
    the rule from the spend posted at that time.
    """
    with _DATA_LOCK:
        state = get_state()
        conf = get_config()
        current = float(state.get('current_spend_usd', 0.0) or 0.0)
        configured = _configured_limit(conf)
        # effective = current + configured, so the headroom over configured is the
        # spend posted so far.
        headroom = max(0.0, current)
        state['acknowledged_headroom_usd'] = _money(
            max(float(state.get('acknowledged_headroom_usd', 0.0) or 0.0), headroom)
        )
        state['acknowledgment_count'] = int(state.get('acknowledgment_count', 0) or 0) + 1
        state['is_locked'] = False
        save_state(state)
        return {
            'configured_limit_usd': configured,
            'acknowledged_headroom_usd': state['acknowledged_headroom_usd'],
            'effective_limit_usd': _effective_limit(conf, state),
        }