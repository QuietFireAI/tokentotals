"""Deterministic Hermes turn ingestion for TokenTotals.

Hermes supplies stable turn/request correlation IDs and normalized usage through its
documented observer-hook contract. TokenTotals prices each successful provider request
individually, then creates one top-level Turn Receipt for the human Hermes turn.

No prompt text, assistant text, tool arguments/results, credentials, cookies, auth
headers, or hidden-reasoning content are accepted by this module.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import config_manager
import hermes_evidence_store
import turn_ledger
from anthropic_pricing import calculate_anthropic_response_cost
from google_pricing import calculate_google_response_cost, infer_google_platform
from openai_pricing import calculate_openai_response_cost

_PRICED_PROVIDERS = {"openai", "anthropic", "google"}
_USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
    "prompt_tokens",
    "total_tokens",
    "request_count",
)


def _clean_text(value, *, limit=512):
    text = str(value or "").strip()
    return text[:limit]


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


def _iso_from_epoch(value):
    numeric = _as_float(value)
    if numeric is None:
        return None
    return datetime.fromtimestamp(numeric, tz=timezone.utc).isoformat()


def _stable_id(prefix, *parts):
    raw = "\x1f".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}-{digest}"


def _clean_usage(raw):
    if not isinstance(raw, dict):
        return {}
    return {key: _as_int(raw.get(key)) for key in _USAGE_FIELDS if raw.get(key) is not None}


def _provider_response(provider, model, usage, response_model=None):
    """Translate Hermes canonical buckets into calculator input without changing the
    canonical ledger buckets. This adapter exists only so the already-tested provider
    pricing engines can price one request at a time.
    """
    input_uncached = _as_int(usage.get("input_tokens"))
    output = _as_int(usage.get("output_tokens"))
    cache_read = _as_int(usage.get("cache_read_tokens"))
    cache_write = _as_int(usage.get("cache_write_tokens"))
    reasoning = _as_int(usage.get("reasoning_tokens"))
    prompt_total = _as_int(usage.get("prompt_tokens"))
    total = _as_int(usage.get("total_tokens"))

    if prompt_total is None:
        parts = [value for value in (input_uncached, cache_read, cache_write) if value is not None]
        prompt_total = sum(parts) if parts else None
    if total is None and prompt_total is not None and output is not None:
        total = prompt_total + output

    actual_model = response_model or model

    if provider == "openai":
        response = {"model": actual_model, "usage": {}}
        raw = response["usage"]
        if prompt_total is not None:
            raw["prompt_tokens"] = prompt_total
        if output is not None:
            raw["completion_tokens"] = output
        if total is not None:
            raw["total_tokens"] = total
        details = {}
        if cache_read:
            details["cached_tokens"] = cache_read
        if cache_write:
            details["cache_write_tokens"] = cache_write
        if details:
            raw["prompt_tokens_details"] = details
        if reasoning:
            raw["completion_tokens_details"] = {"reasoning_tokens": reasoning}
        return response

    if provider == "anthropic":
        response = {"model": actual_model, "usage": {}}
        raw = response["usage"]
        if input_uncached is not None:
            raw["input_tokens"] = input_uncached
        if output is not None:
            raw["output_tokens"] = output
        if cache_read:
            raw["cache_read_input_tokens"] = cache_read
        if cache_write:
            raw["cache_creation_input_tokens"] = cache_write
        if total is not None:
            raw["total_tokens"] = total
        return response

    if provider == "google":
        response = {"model": actual_model, "modelVersion": actual_model, "usageMetadata": {}}
        raw = response["usageMetadata"]
        if prompt_total is not None:
            raw["promptTokenCount"] = prompt_total
        if output is not None:
            raw["candidatesTokenCount"] = output
        if cache_read:
            raw["cachedContentTokenCount"] = cache_read
        if reasoning:
            raw["thoughtsTokenCount"] = reasoning
        if total is not None:
            raw["totalTokenCount"] = total
        return response

    return None


def _price_call(call):
    provider = _clean_text(call.get("provider"), limit=128).lower() or "unknown"
    model = _clean_text(call.get("model"), limit=256)
    response_model = _clean_text(call.get("response_model"), limit=256) or None
    usage = _clean_usage(call.get("usage"))
    if provider not in _PRICED_PROVIDERS or not model or not usage:
        return None, {
            "estimated_usd": None,
            "basis": "unavailable",
            "complete": False,
            "registry_verified_at": None,
            "components_usd": {},
        }

    response = _provider_response(provider, model, usage, response_model=response_model)
    if provider == "openai":
        result = calculate_openai_response_cost(model, response)
    elif provider == "anthropic":
        result = calculate_anthropic_response_cost(
            model,
            response,
            processing_mode="standard",
            platform="claude_api",
        )
    else:
        result = calculate_google_response_cost(
            model,
            response,
            processing_mode="standard",
            platform=infer_google_platform(model),
        )

    amount = None
    basis = "unavailable"
    complete = False
    if result and result.get("complete") and result.get("total_cost_usd") is not None:
        amount = float(result["total_cost_usd"])
        basis = "provider_registry_complete"
        complete = True
    elif result and result.get("known_list_equivalent_usd") is not None:
        amount = float(result["known_list_equivalent_usd"])
        basis = "known_list_equivalent"

    pricing = {
        "estimated_usd": amount,
        "basis": basis,
        "complete": complete,
        "registry_verified_at": (result or {}).get("verified_at"),
        "components_usd": (result or {}).get("components_usd") or {},
    }
    return result, pricing


def _aggregate_tokens(calls):
    def values(field):
        return [
            int((call.get("usage") or {}).get(field))
            for call in calls
            if (call.get("usage") or {}).get(field) is not None
        ]

    prompt_values = values("prompt_tokens")
    output_values = values("output_tokens")
    total_values = values("total_tokens")
    uncached_values = values("input_tokens")
    cache_read_values = values("cache_read_tokens")
    cache_write_values = values("cache_write_tokens")
    reasoning_values = values("reasoning_tokens")

    tokens = {name: None for name in turn_ledger.TOKEN_FIELDS}
    basis = {name: "unavailable" for name in turn_ledger.TOKEN_FIELDS}

    def set_metric(name, value, source="observed"):
        if value is None:
            return
        tokens[name] = int(value)
        basis[name] = source

    if prompt_values:
        set_metric("input_tokens", sum(prompt_values), "observed")
    if output_values:
        set_metric("output_tokens", sum(output_values), "observed")
    if total_values:
        set_metric("provider_reported_total_tokens", sum(total_values), "observed")
    if uncached_values:
        set_metric("uncached_input_tokens", sum(uncached_values), "derived")

    # Hermes CanonicalUsage uses integer zero for an optional bucket that may be
    # absent upstream. Preserve TokenTotals' missing != zero rule: positive values
    # are observable evidence; all-zero optional buckets stay unavailable.
    if any(value > 0 for value in cache_read_values):
        set_metric("cached_input_tokens", sum(cache_read_values), "observed")
    if any(value > 0 for value in cache_write_values):
        set_metric("cache_write_tokens", sum(cache_write_values), "observed")
    if any(value > 0 for value in reasoning_values):
        set_metric("reasoning_tokens", sum(reasoning_values), "observed")

    if tokens["input_tokens"] is not None and tokens["output_tokens"] is not None:
        reconstructed = tokens["input_tokens"] + tokens["output_tokens"]
        set_metric("reconstructed_total_tokens", reconstructed, "derived")
        if tokens["provider_reported_total_tokens"] is not None:
            delta = tokens["provider_reported_total_tokens"] - reconstructed
            set_metric("reconciliation_delta_tokens", delta, "derived")
            set_metric("unclassified_tokens", max(0, delta), "derived")
    return tokens, basis


def _clean_failure(item):
    item = item if isinstance(item, dict) else {}
    error = item.get("error") if isinstance(item.get("error"), dict) else {}
    return {
        "api_request_id": _clean_text(item.get("api_request_id"), limit=256),
        "api_call_count": _as_int(item.get("api_call_count")),
        "provider": _clean_text(item.get("provider"), limit=128).lower() or "unknown",
        "model": _clean_text(item.get("model"), limit=256),
        "status_code": _as_int(item.get("status_code")),
        "retry_count": _as_int(item.get("retry_count")),
        "max_retries": _as_int(item.get("max_retries")),
        "retryable": item.get("retryable") if isinstance(item.get("retryable"), bool) else None,
        "error_type": _clean_text(error.get("type") or item.get("error_type"), limit=128) or None,
    }


def ingest_hermes_turn(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    session_id = _clean_text(payload.get("session_id"))
    source_turn_id = _clean_text(payload.get("turn_id"))
    task_id = _clean_text(payload.get("task_id")) or None
    if not session_id:
        raise ValueError("session_id is required")
    if not source_turn_id:
        raise ValueError("turn_id is required")

    raw_calls = payload.get("api_calls")
    if not isinstance(raw_calls, list):
        raise ValueError("api_calls must be a list")

    receipt_id = _stable_id("hermes", session_id, source_turn_id)
    thread_id = _stable_id("hermes-thread", session_id)

    calls = []
    seen_request_ids = set()
    for raw_call in raw_calls:
        if not isinstance(raw_call, dict):
            continue
        request_id = _clean_text(raw_call.get("api_request_id"), limit=256)
        if not request_id or request_id in seen_request_ids:
            continue
        seen_request_ids.add(request_id)
        call = {
            "api_request_id": request_id,
            "api_call_count": _as_int(raw_call.get("api_call_count")),
            "provider": _clean_text(raw_call.get("provider"), limit=128).lower() or "unknown",
            "model": _clean_text(raw_call.get("model"), limit=256),
            "response_model": _clean_text(raw_call.get("response_model"), limit=256) or None,
            "platform": _clean_text(raw_call.get("platform"), limit=128) or None,
            "api_mode": _clean_text(raw_call.get("api_mode"), limit=128) or None,
            "started_at": _as_float(raw_call.get("started_at")),
            "ended_at": _as_float(raw_call.get("ended_at")),
            "api_duration": _as_float(raw_call.get("api_duration")),
            "usage": _clean_usage(raw_call.get("usage")),
        }
        _result, pricing = _price_call(call)
        call["pricing"] = pricing
        calls.append(call)

    failures = [_clean_failure(item) for item in (payload.get("failed_api_attempts") or []) if isinstance(item, dict)]

    tokens, token_basis = _aggregate_tokens(calls)
    providers = sorted({call["provider"] for call in calls if call.get("provider")})
    models = sorted(
        {
            call.get("response_model") or call.get("model")
            for call in calls
            if call.get("response_model") or call.get("model")
        }
    )
    provider_label = providers[0] if len(providers) == 1 else ("multiple" if providers else "unknown")
    model_label = models[0] if len(models) == 1 else ("multiple" if models else _clean_text(payload.get("model"), limit=256))

    priced = [call for call in calls if (call.get("pricing") or {}).get("estimated_usd") is not None]
    complete_priced = [call for call in priced if (call.get("pricing") or {}).get("complete")]
    total_cost = sum(float(call["pricing"]["estimated_usd"]) for call in priced) if priced else None

    successful_calls = len(calls)
    if successful_calls and len(complete_priced) == successful_calls:
        cost_basis = "hermes_child_transaction_sum_complete"
        estimate_complete = True
    elif total_cost is not None:
        cost_basis = "hermes_child_transaction_sum_partial"
        estimate_complete = False
    else:
        cost_basis = "unavailable"
        estimate_complete = False

    if total_cost is not None:
        state_after = config_manager.update_spend(
            cost_usd=total_cost,
            thread_id=thread_id,
            reservation_id=receipt_id,
        )
    else:
        state_after = config_manager.get_state()

    start_candidates = [call["started_at"] for call in calls if call.get("started_at") is not None]
    end_candidates = [call["ended_at"] for call in calls if call.get("ended_at") is not None]
    started_at = min(start_candidates) if start_candidates else None
    ended_at = max(end_candidates) if end_candidates else None
    if ended_at is None:
        ended_at = datetime.now(timezone.utc).timestamp()

    latency_ms = None
    if started_at is not None and ended_at is not None and ended_at >= started_at:
        latency_ms = int((ended_at - started_at) * 1000)

    record = {
        "schema_version": turn_ledger.SCHEMA_VERSION,
        "turn_id": receipt_id,
        "thread_id": thread_id,
        "started_at": _iso_from_epoch(started_at),
        "completed_at": _iso_from_epoch(ended_at),
        "latency_ms": latency_ms,
        "provider": provider_label,
        "requested_model_id": model_label or "",
        "canonical_model_id": models[0] if len(models) == 1 else None,
        "observed_model_id": models[0] if len(models) == 1 else None,
        "registry_verified_at": None,
        "requested_service_tier": None,
        "observed_service_tier": None,
        "tokens": tokens,
        "token_basis": token_basis,
        "modalities": {},
        "server_tools": {},
        "estimated_cost_usd": total_cost,
        "estimated_cost_picos": turn_ledger.usd_to_picos(total_cost),
        "pricing_components_usd": {},
        "cost_basis": cost_basis,
        "estimate_complete": estimate_complete,
        "notes": [
            "external_surface:hermes",
            "external_same_turn_evidence",
            f"hermes_api_calls:{successful_calls}",
            f"hermes_priced_calls:{len(priced)}",
            f"hermes_failed_attempts:{len(failures)}",
        ],
        "cumulative_local_estimated_spend_usd": state_after.get("current_spend_usd"),
        "cumulative_thread_estimated_spend_usd": state_after.get("thread_spend_usd"),
        "cumulative_completed_turns": state_after.get("total_requests"),
    }

    appended = turn_ledger.append_turn(record)
    hermes_evidence_store.append(
        {
            "receipt_id": receipt_id,
            "source_session_id": session_id,
            "source_turn_id": source_turn_id,
            "source_task_id": task_id,
            "telemetry_schema_version": payload.get("telemetry_schema_version"),
            "api_calls": calls,
            "failed_api_attempts": failures,
        }
    )

    return {
        "turn_id": receipt_id,
        "thread_id": thread_id,
        "created": bool(appended),
        "source_session_id": session_id,
        "source_turn_id": source_turn_id,
        "api_call_count": successful_calls,
        "priced_call_count": len(priced),
        "failed_attempt_count": len(failures),
        "cost_basis": cost_basis,
        "estimate_complete": estimate_complete,
    }
