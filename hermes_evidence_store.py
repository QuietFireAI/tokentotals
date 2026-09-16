"""Privacy-limited child-transaction evidence for Hermes Turn Receipts.

This store persists only correlation IDs, provider/model/runtime metadata, numeric
usage buckets, pricing results, and error classification. It never persists the
user prompt, assistant answer, tool arguments/results, API keys, cookies,
authorization headers, or hidden reasoning content.
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
    return Path(config_manager.APP_DIR) / "hermes-turn-evidence.jsonl"


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
    allowed = (
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
        "prompt_tokens",
        "total_tokens",
        "request_count",
    )
    return {key: _as_int(value.get(key)) for key in allowed if value.get(key) is not None}


def _clean_child(child):
    child = child if isinstance(child, dict) else {}
    pricing = child.get("pricing") if isinstance(child.get("pricing"), dict) else {}
    components = pricing.get("components_usd") if isinstance(pricing.get("components_usd"), dict) else {}
    return {
        "api_request_id": str(child.get("api_request_id") or "")[:256],
        "api_call_count": _as_int(child.get("api_call_count")),
        "provider": str(child.get("provider") or "unknown")[:128],
        "model": str(child.get("model") or "")[:256],
        "response_model": str(child.get("response_model") or "")[:256] or None,
        "platform": str(child.get("platform") or "")[:128] or None,
        "api_mode": str(child.get("api_mode") or "")[:128] or None,
        "started_at": _as_float(child.get("started_at")),
        "ended_at": _as_float(child.get("ended_at")),
        "api_duration": _as_float(child.get("api_duration")),
        "usage": _clean_usage(child.get("usage")),
        "pricing": {
            "estimated_usd": _as_float(pricing.get("estimated_usd")),
            "basis": str(pricing.get("basis") or "unavailable")[:128],
            "complete": bool(pricing.get("complete", False)),
            "registry_verified_at": (
                str(pricing.get("registry_verified_at"))[:128]
                if pricing.get("registry_verified_at") is not None
                else None
            ),
            "components_usd": {
                str(key)[:128]: float(amount)
                for key, amount in components.items()
                if isinstance(amount, (int, float)) and not isinstance(amount, bool)
            },
        },
    }


def _clean_failure(failure):
    failure = failure if isinstance(failure, dict) else {}
    return {
        "api_request_id": str(failure.get("api_request_id") or "")[:256],
        "api_call_count": _as_int(failure.get("api_call_count")),
        "provider": str(failure.get("provider") or "unknown")[:128],
        "model": str(failure.get("model") or "")[:256],
        "status_code": _as_int(failure.get("status_code")),
        "retry_count": _as_int(failure.get("retry_count")),
        "max_retries": _as_int(failure.get("max_retries")),
        "retryable": bool(failure.get("retryable")) if failure.get("retryable") is not None else None,
        "error_type": str(failure.get("error_type") or "")[:128] or None,
    }


def _clean_record(record):
    record = record if isinstance(record, dict) else {}
    receipt_id = str(record.get("receipt_id") or "").strip()
    if not receipt_id:
        raise ValueError("receipt_id is required")
    return {
        "schema": "tokentotals.hermes_evidence",
        "schema_version": 1,
        "receipt_id": receipt_id,
        "source_session_id": str(record.get("source_session_id") or "")[:512],
        "source_turn_id": str(record.get("source_turn_id") or "")[:512],
        "source_task_id": str(record.get("source_task_id") or "")[:512] or None,
        "telemetry_schema_version": str(record.get("telemetry_schema_version") or "")[:128] or None,
        "api_calls": [_clean_child(item) for item in (record.get("api_calls") or [])],
        "failed_api_attempts": [_clean_failure(item) for item in (record.get("failed_api_attempts") or [])],
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
