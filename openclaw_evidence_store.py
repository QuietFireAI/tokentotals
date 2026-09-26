"""Privacy-limited OpenClaw turn evidence for TokenTotals.

Stores only stable correlation IDs, model/runtime metadata, normalized usage,
model-call lifecycle metadata, and cost provenance. It does not persist prompt
text, answer text, tool arguments/results, credentials, cookies, auth headers,
or hidden reasoning content.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import config_manager

_LOCK = threading.RLock()
_FILE_OVERRIDE = None


def evidence_path() -> Path:
    if _FILE_OVERRIDE is not None:
        return Path(_FILE_OVERRIDE)
    return Path(config_manager.APP_DIR) / "openclaw-turn-evidence.jsonl"


def _as_int(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _as_float(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_usage(value):
    if not isinstance(value, dict):
        return {}
    allowed = ("input", "output", "cache_read", "cache_write", "total")
    return {key: _as_int(value.get(key)) for key in allowed if value.get(key) is not None}


def _clean_call(item):
    item = item if isinstance(item, dict) else {}
    return {
        "call_id": str(item.get("call_id") or "")[:256],
        "provider": str(item.get("provider") or "unknown")[:128],
        "model": str(item.get("model") or "")[:256],
        "api": str(item.get("api") or "")[:128] or None,
        "transport": str(item.get("transport") or "")[:128] or None,
        "duration_ms": _as_int(item.get("duration_ms")),
        "outcome": str(item.get("outcome") or "")[:64] or None,
        "error_category": str(item.get("error_category") or "")[:128] or None,
        "failure_kind": str(item.get("failure_kind") or "")[:128] or None,
        "upstream_request_id_hash": str(item.get("upstream_request_id_hash") or "")[:256] or None,
    }


def _clean_record(record):
    record = record if isinstance(record, dict) else {}
    receipt_id = str(record.get("receipt_id") or "").strip()
    if not receipt_id:
        raise ValueError("receipt_id is required")
    return {
        "schema": "tokentotals.openclaw_evidence",
        "schema_version": 1,
        "receipt_id": receipt_id,
        "source_run_id": str(record.get("source_run_id") or "")[:512],
        "source_session_key": str(record.get("source_session_key") or "")[:1024],
        "source_session_id": str(record.get("source_session_id") or "")[:512] or None,
        "provider": str(record.get("provider") or "unknown")[:128],
        "model": str(record.get("model") or "")[:256],
        "resolved_ref": str(record.get("resolved_ref") or "")[:512] or None,
        "requested": str(record.get("requested") or "")[:512] or None,
        "usage": _clean_usage(record.get("usage")),
        "last_usage": _clean_usage(record.get("last_usage")),
        "runtime_turn_usd": _as_float(record.get("runtime_turn_usd")),
        "duration_ms": _as_int(record.get("duration_ms")),
        "context_token_budget": _as_int(record.get("context_token_budget")),
        "context_used_tokens": _as_int(record.get("context_used_tokens")),
        "reasoning_effort": str(record.get("reasoning_effort") or "")[:64] or None,
        "fast_mode": record.get("fast_mode") if isinstance(record.get("fast_mode"), bool) else None,
        "fallback_used": record.get("fallback_used") if isinstance(record.get("fallback_used"), bool) else None,
        "auth_mode": str(record.get("auth_mode") or "")[:64] or None,
        "override_source": str(record.get("override_source") or "")[:128] or None,
        "model_calls": [_clean_call(item) for item in (record.get("model_calls") or [])],
    }


def read(receipt_id):
    key = str(receipt_id or "").strip()
    if not key:
        return None
    path = evidence_path()
    with _LOCK:
        if not path.exists():
            return None
        latest = None
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(record.get("receipt_id") or "") == key:
                    latest = record
        return latest


def append(record):
    cleaned = _clean_record(record)
    if read(cleaned["receipt_id"]) is not None:
        return False
    path = evidence_path()
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(cleaned, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
    return True
