import threading
from copy import deepcopy

_NOTICE_LOCK = threading.RLock()
_LATEST_NOTICE = None
_LATEST_BY_THREAD = {}
_SEEN_EVENT_IDS = set()


def normalize_threshold(value):
    """Return a positive local reminder threshold or None when disabled/invalid."""
    if value is None:
        return None
    try:
        threshold = float(value)
    except (TypeError, ValueError):
        return None
    if threshold <= 0:
        return None
    return threshold


def evaluate_notice(
    *,
    stage,
    estimated_cost_usd,
    threshold_usd,
    thread_id,
    turn_id,
    model_id=None,
    cost_basis=None,
    estimate_complete=False,
):
    """Build a factual Turn Notice event when a local turn estimate meets threshold."""
    threshold = normalize_threshold(threshold_usd)
    if threshold is None or estimated_cost_usd is None:
        return None
    try:
        estimate = float(estimated_cost_usd)
    except (TypeError, ValueError):
        return None
    if estimate < threshold:
        return None

    stage_name = str(stage or "").strip().lower()
    if stage_name not in {"preflight", "completed"}:
        raise ValueError("stage must be 'preflight' or 'completed'")

    turn_key = str(turn_id or "").strip()
    if not turn_key:
        raise ValueError("turn_id must be non-empty")
    thread_key = str(thread_id or "default").strip() or "default"

    if stage_name == "preflight":
        message = (
            f"Preflight input-side estimate ${estimate:.4f} met the local Turn Notice "
            f"reminder threshold of ${threshold:.4f}. Final turn cost can differ."
        )
    else:
        message = (
            f"Completed-turn local estimate ${estimate:.4f} met the local Turn Notice "
            f"reminder threshold of ${threshold:.4f}. Provider account records remain authoritative."
        )

    return {
        "event": "turn_notice",
        "event_id": f"{turn_key}:{stage_name}",
        "stage": stage_name,
        "turn_id": turn_key,
        "thread_id": thread_key,
        "model_id": str(model_id).strip() if model_id is not None else None,
        "estimated_cost_usd": estimate,
        "reminder_threshold_usd": threshold,
        "cost_basis": str(cost_basis or "unavailable"),
        "estimate_complete": bool(estimate_complete),
        "message": message,
    }


def publish_notice(event):
    """Publish one process-local notice. Duplicate event IDs are ignored."""
    if event is None:
        return False
    event_id = str(event.get("event_id") or "").strip()
    if not event_id:
        raise ValueError("Turn Notice event_id must be non-empty")
    thread_id = str(event.get("thread_id") or "default").strip() or "default"

    global _LATEST_NOTICE
    with _NOTICE_LOCK:
        if event_id in _SEEN_EVENT_IDS:
            return False
        cleaned = deepcopy(event)
        _SEEN_EVENT_IDS.add(event_id)
        _LATEST_NOTICE = cleaned
        _LATEST_BY_THREAD[thread_id] = cleaned
        return True


def evaluate_and_publish(**kwargs):
    event = evaluate_notice(**kwargs)
    if event is None:
        return None
    publish_notice(event)
    return deepcopy(event)


def latest_notice(thread_id=None):
    with _NOTICE_LOCK:
        if thread_id is None:
            return deepcopy(_LATEST_NOTICE)
        key = str(thread_id).strip() or "default"
        return deepcopy(_LATEST_BY_THREAD.get(key))


def reset_runtime_notices():
    """Test/runtime helper. Turn Notices are intentionally not persistent accounting."""
    global _LATEST_NOTICE
    with _NOTICE_LOCK:
        _LATEST_NOTICE = None
        _LATEST_BY_THREAD.clear()
        _SEEN_EVENT_IDS.clear()
