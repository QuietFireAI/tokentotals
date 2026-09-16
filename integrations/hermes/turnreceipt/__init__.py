"""TurnReceipt for Hermes.

Accounting uses Hermes' documented observer-hook contract. The CLI placement adapter
is deliberately separate: it wraps the current Hermes response-panel method at runtime
so the provider/model answer is rendered first and the independently calculated receipt
is printed immediately afterward. The wrapper never changes the assistant response.

If Hermes changes that internal display method, accounting remains fail-open and inline
placement disables itself rather than guessing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import urllib.error
import urllib.request
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

_LOCK = threading.RLock()
_TURNS = {}
_PENDING_DISPLAY = defaultdict(deque)
_ENGINE_BASE = None
_DISPLAY_PATCHED = False
_ORIGINAL_PRINT_RESPONSE_PANEL = None

_ALLOWED_USAGE = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
    "prompt_tokens",
    "total_tokens",
    "request_count",
)


def _clean(value, limit=512):
    return str(value or "").strip()[:limit]


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value):
    numeric = _number(value)
    return None if numeric is None else max(0, int(numeric))


def _usage(value):
    if not isinstance(value, dict):
        return {}
    return {key: _integer(value.get(key)) for key in _ALLOWED_USAGE if value.get(key) is not None}


def _turn_key(session_id, turn_id):
    return (_clean(session_id), _clean(turn_id))


def _response_digest(response):
    if response is None:
        text = ""
    elif isinstance(response, str):
        text = response
    else:
        text = str(response)
    return hashlib.sha256(text.encode("utf-8", errors="surrogatepass")).hexdigest()


def _candidate_engine_bases():
    configured = _clean(os.environ.get("HERMES_TURNRECEIPT_URL"), 1024).rstrip("/")
    if configured:
        yield configured
        return
    for port in range(8080, 8090):
        yield f"http://127.0.0.1:{port}"


def _post_json(path, payload):
    global _ENGINE_BASE
    bases = [_ENGINE_BASE] if _ENGINE_BASE else list(_candidate_engine_bases())
    last_error = None
    for base in bases:
        if not base:
            continue
        request = urllib.request.Request(
            f"{base}{path}",
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=1.5) as response:
                body = response.read().decode("utf-8")
            _ENGINE_BASE = base
            return json.loads(body)
        except Exception as exc:
            last_error = exc
            if _ENGINE_BASE:
                _ENGINE_BASE = None
                return _post_json(path, payload)
    raise RuntimeError(f"TokenTotals engine unavailable: {last_error}")


def on_pre_llm_call(**kwargs):
    session_id = _clean(kwargs.get("session_id"))
    turn_id = _clean(kwargs.get("turn_id"))
    if not session_id or not turn_id:
        return
    with _LOCK:
        _TURNS[_turn_key(session_id, turn_id)] = {
            "session_id": session_id,
            "turn_id": turn_id,
            "task_id": _clean(kwargs.get("task_id")) or None,
            "model": _clean(kwargs.get("model"), 256) or None,
            "platform": _clean(kwargs.get("platform"), 128) or None,
            "telemetry_schema_version": _clean(kwargs.get("telemetry_schema_version"), 128) or None,
            "api_calls": [],
            "failed_api_attempts": [],
        }


def _state_for(kwargs):
    session_id = _clean(kwargs.get("session_id"))
    turn_id = _clean(kwargs.get("turn_id"))
    if not session_id or not turn_id:
        return None
    key = _turn_key(session_id, turn_id)
    with _LOCK:
        state = _TURNS.get(key)
        if state is None:
            state = {
                "session_id": session_id,
                "turn_id": turn_id,
                "task_id": _clean(kwargs.get("task_id")) or None,
                "model": _clean(kwargs.get("model"), 256) or None,
                "platform": _clean(kwargs.get("platform"), 128) or None,
                "telemetry_schema_version": _clean(kwargs.get("telemetry_schema_version"), 128) or None,
                "api_calls": [],
                "failed_api_attempts": [],
            }
            _TURNS[key] = state
        return state


def on_post_api_request(**kwargs):
    state = _state_for(kwargs)
    if state is None:
        return
    request_id = _clean(kwargs.get("api_request_id"), 256)
    if not request_id:
        return
    call = {
        "api_request_id": request_id,
        "api_call_count": _integer(kwargs.get("api_call_count")),
        "provider": _clean(kwargs.get("provider"), 128).lower() or "unknown",
        "model": _clean(kwargs.get("model"), 256),
        "response_model": _clean(kwargs.get("response_model"), 256) or None,
        "platform": _clean(kwargs.get("platform"), 128) or None,
        "api_mode": _clean(kwargs.get("api_mode"), 128) or None,
        "started_at": _number(kwargs.get("started_at")),
        "ended_at": _number(kwargs.get("ended_at")),
        "api_duration": _number(kwargs.get("api_duration")),
        "usage": _usage(kwargs.get("usage")),
    }
    with _LOCK:
        if not any(item.get("api_request_id") == request_id for item in state["api_calls"]):
            state["api_calls"].append(call)


def on_api_request_error(**kwargs):
    state = _state_for(kwargs)
    if state is None:
        return
    error = kwargs.get("error") if isinstance(kwargs.get("error"), dict) else {}
    failure = {
        "api_request_id": _clean(kwargs.get("api_request_id"), 256),
        "api_call_count": _integer(kwargs.get("api_call_count")),
        "provider": _clean(kwargs.get("provider"), 128).lower() or "unknown",
        "model": _clean(kwargs.get("model"), 256),
        "status_code": _integer(kwargs.get("status_code")),
        "retry_count": _integer(kwargs.get("retry_count")),
        "max_retries": _integer(kwargs.get("max_retries")),
        "retryable": kwargs.get("retryable") if isinstance(kwargs.get("retryable"), bool) else None,
        "error_type": _clean(error.get("type"), 128) or None,
    }
    with _LOCK:
        state["failed_api_attempts"].append(failure)


def _queue_display(session_id, turn_id, assistant_response, receipt_text):
    if not receipt_text:
        return
    item = {
        "turn_id": turn_id,
        "response_digest": _response_digest(assistant_response),
        "receipt_text": str(receipt_text),
    }
    with _LOCK:
        queue = _PENDING_DISPLAY[_clean(session_id)]
        queue.append(item)
        while len(queue) > 16:
            queue.popleft()


def on_post_llm_call(**kwargs):
    session_id = _clean(kwargs.get("session_id"))
    turn_id = _clean(kwargs.get("turn_id"))
    if not session_id or not turn_id:
        return
    key = _turn_key(session_id, turn_id)
    with _LOCK:
        state = _TURNS.pop(key, None)
    if state is None:
        state = {
            "session_id": session_id,
            "turn_id": turn_id,
            "task_id": _clean(kwargs.get("task_id")) or None,
            "model": _clean(kwargs.get("model"), 256) or None,
            "platform": _clean(kwargs.get("platform"), 128) or None,
            "telemetry_schema_version": _clean(kwargs.get("telemetry_schema_version"), 128) or None,
            "api_calls": [],
            "failed_api_attempts": [],
        }

    # The payload is metadata/usage only. assistant_response is used solely for an
    # in-memory digest that binds the later CLI render; its text never crosses to
    # TokenTotals and is never persisted by this plugin.
    try:
        settled = _post_json("/api/hermes/turn", state)
    except Exception as exc:
        logger.warning("TurnReceipt: could not settle Hermes turn %s: %s", turn_id, exc)
        return

    mode = _clean(os.environ.get("HERMES_TURNRECEIPT_MODE"), 32).lower()
    field = "receipt_text_expanded" if mode == "expanded" else "receipt_text_standard"
    _queue_display(
        session_id,
        turn_id,
        kwargs.get("assistant_response"),
        settled.get(field),
    )


def _pop_matching_receipt(session_id, response):
    digest = _response_digest(response)
    key = _clean(session_id)
    with _LOCK:
        queue = _PENDING_DISPLAY.get(key)
        if not queue:
            return None
        for index, item in enumerate(queue):
            if item.get("response_digest") == digest:
                selected = item
                del queue[index]
                if not queue:
                    _PENDING_DISPLAY.pop(key, None)
                return selected
    return None


def _install_cli_display_adapter():
    """Guarded display-only wrapper.

    Hermes currently exposes no documented post-response-render plugin hook. The
    observer/accounting path is fully documented; this wrapper is the one compatibility
    shim. It never changes `response`, and it self-disables when the expected method
    is absent instead of guessing a new internal path.
    """
    global _DISPLAY_PATCHED, _ORIGINAL_PRINT_RESPONSE_PANEL
    if _DISPLAY_PATCHED:
        return True
    try:
        from hermes_cli.cli_chat_turn_mixin import CLIChatTurnMixin
    except Exception as exc:
        logger.warning("TurnReceipt: Hermes CLI display adapter unavailable: %s", exc)
        return False

    original = getattr(CLIChatTurnMixin, "_chat_print_response_panel", None)
    if not callable(original):
        logger.warning("TurnReceipt: Hermes response-panel seam is unavailable; inline display disabled")
        return False

    def wrapped(self, turn, response):
        result = original(self, turn, response)
        try:
            pending = _pop_matching_receipt(getattr(self, "session_id", ""), response)
            if pending and pending.get("receipt_text"):
                print()
                print(pending["receipt_text"], flush=True)
        except Exception as exc:
            logger.warning("TurnReceipt: receipt display failed: %s", exc)
        return result

    wrapped.__name__ = getattr(original, "__name__", "_chat_print_response_panel")
    wrapped.__doc__ = getattr(original, "__doc__", None)
    wrapped.__turnreceipt_wrapped__ = True
    CLIChatTurnMixin._chat_print_response_panel = wrapped
    _ORIGINAL_PRINT_RESPONSE_PANEL = original
    _DISPLAY_PATCHED = True
    return True


def on_session_finalize(**kwargs):
    session_id = _clean(kwargs.get("session_id"))
    if not session_id:
        return
    with _LOCK:
        for key in [key for key in _TURNS if key[0] == session_id]:
            _TURNS.pop(key, None)
        _PENDING_DISPLAY.pop(session_id, None)


def register(ctx):
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("post_api_request", on_post_api_request)
    ctx.register_hook("api_request_error", on_api_request_error)
    ctx.register_hook("post_llm_call", on_post_llm_call)
    ctx.register_hook("on_session_finalize", on_session_finalize)
    _install_cli_display_adapter()
