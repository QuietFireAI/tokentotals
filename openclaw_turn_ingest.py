"""Deterministic OpenClaw turn ingestion for TokenTotals.

OpenClaw exposes a stable per-turn ``runId`` plus a normalized turn-level usage
snapshot on ``reply_payload_sending``. TokenTotals uses that exact run identity
for the receipt and never correlates by timing proximity.

Cost policy:
- when OpenClaw proves the turn contained exactly one completed model call and
  TokenTotals recognizes the provider/model, TokenTotals performs its own
  provider-registry reconstruction from the normalized usage buckets;
- otherwise an OpenClaw ``turnUsd`` value may be preserved as an explicitly
  labeled runtime-reported amount;
- if neither basis is defensible, cost remains unavailable.

No prompt text, answer text, tool arguments/results, credentials, cookies,
authorization headers, or hidden reasoning content are accepted or persisted.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import config_manager
import openclaw_evidence_store
import turn_ledger
from anthropic_pricing import calculate_anthropic_response_cost
from google_pricing import calculate_google_response_cost, infer_google_platform
from openai_pricing import calculate_openai_response_cost

_PRICED_PROVIDERS = {"openai", "anthropic", "google"}
_USAGE_FIELDS = ("input", "output", "cache_read", "cache_write", "total")


def _clean_text(value, *, limit=512):
    return str(value or "").strip()[:limit]


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


def _stable_id(prefix, *parts):
    raw = "\x1f".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}-{digest}"


def _clean_usage(raw):
    if not isinstance(raw, dict):
        return {}
    return {key: _as_int(raw.get(key)) for key in _USAGE_FIELDS if raw.get(key) is not None}


def _normalize_provider(provider, resolved_ref=None):
    name = _clean_text(provider, limit=128).lower()
    if name:
        if name in {"claude", "anthropic-api"}:
            return "anthropic"
        if name in {"gemini", "google-ai", "googleai"}:
            return "google"
        return name
    resolved = _clean_text(resolved_ref, limit=512)
    if "/" in resolved:
        return _normalize_provider(resolved.split("/", 1)[0])
    return "unknown"


def _model_from_payload(model, resolved_ref=None):
    raw = _clean_text(model, limit=256)
    if raw:
        return raw
    resolved = _clean_text(resolved_ref, limit=512)
    if "/" in resolved:
        return resolved.split("/", 1)[1][:256]
    return resolved[:256]


def _provider_response(provider, model, usage):
    """Translate OpenClaw normalized usage into existing provider calculator input."""
    uncached = _as_int(usage.get("input"))
    output = _as_int(usage.get("output"))
    cache_read = _as_int(usage.get("cache_read"))
    cache_write = _as_int(usage.get("cache_write"))
    total = _as_int(usage.get("total"))

    prompt_parts = [value for value in (uncached, cache_read, cache_write) if value is not None]
    prompt_total = sum(prompt_parts) if prompt_parts else None
    if total is None and prompt_total is not None and output is not None:
        total = prompt_total + output

    if provider == "openai":
        response = {"model": model, "usage": {}}
        raw = response["usage"]
        if prompt_total is not None:
            raw["prompt_tokens"] = prompt_total
        if output is not None:
            raw["completion_tokens"] = output
        if total is not None:
            raw["total_tokens"] = total
        details = {}
        if cache_read is not None:
            details["cached_tokens"] = cache_read
        if cache_write is not None:
            details["cache_write_tokens"] = cache_write
        if details:
            raw["prompt_tokens_details"] = details
        return response

    if provider == "anthropic":
        response = {"model": model, "usage": {}}
        raw = response["usage"]
        if uncached is not None:
            raw["input_tokens"] = uncached
        if output is not None:
            raw["output_tokens"] = output
        if cache_read is not None:
            raw["cache_read_input_tokens"] = cache_read
        if cache_write is not None:
            raw["cache_creation_input_tokens"] = cache_write
        if total is not None:
            raw["total_tokens"] = total
        return response

    if provider == "google":
        response = {"model": model, "modelVersion": model, "usageMetadata": {}}
        raw = response["usageMetadata"]
        if prompt_total is not None:
            raw["promptTokenCount"] = prompt_total
        if output is not None:
            raw["candidatesTokenCount"] = output
        if cache_read is not None:
            raw["cachedContentTokenCount"] = cache_read
        if total is not None:
            raw["totalTokenCount"] = total
        return response

    return None


def _price_single_call(provider, model, usage):
    if provider not in _PRICED_PROVIDERS or not model or not usage:
        return None
    response = _provider_response(provider, model, usage)
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
    if not result:
        return None
    if result.get("complete") and result.get("total_cost_usd") is not None:
        return {
            "amount": float(result["total_cost_usd"]),
            "basis": "provider_registry_complete",
            "complete": True,
            "components": result.get("components_usd") or {},
            "verified_at": result.get("verified_at"),
        }
    if result.get("known_list_equivalent_usd") is not None:
        return {
            "amount": float(result["known_list_equivalent_usd"]),
            "basis": "known_list_equivalent",
            "complete": False,
            "components": result.get("components_usd") or {},
            "verified_at": result.get("verified_at"),
        }
    return None


def _clean_model_call(item):
    item = item if isinstance(item, dict) else {}
    outcome = _clean_text(item.get("outcome"), limit=64).lower() or None
    return {
        "call_id": _clean_text(item.get("call_id"), limit=256),
        "provider": _normalize_provider(item.get("provider")),
        "model": _clean_text(item.get("model"), limit=256),
        "api": _clean_text(item.get("api"), limit=128) or None,
        "transport": _clean_text(item.get("transport"), limit=128) or None,
        "duration_ms": _as_int(item.get("duration_ms")),
        "outcome": outcome,
        "error_category": _clean_text(item.get("error_category"), limit=128) or None,
        "failure_kind": _clean_text(item.get("failure_kind"), limit=128) or None,
        "upstream_request_id_hash": _clean_text(item.get("upstream_request_id_hash"), limit=256) or None,
    }


def _ledger_tokens(usage):
    tokens = {name: None for name in turn_ledger.TOKEN_FIELDS}
    basis = {name: "unavailable" for name in turn_ledger.TOKEN_FIELDS}

    uncached = _as_int(usage.get("input"))
    output = _as_int(usage.get("output"))
    cache_read = _as_int(usage.get("cache_read"))
    cache_write = _as_int(usage.get("cache_write"))
    provider_total = _as_int(usage.get("total"))

    prompt_parts = [value for value in (uncached, cache_read, cache_write) if value is not None]
    prompt_total = sum(prompt_parts) if prompt_parts else None

    def set_metric(name, value, source="observed"):
        if value is None:
            return
        tokens[name] = int(value)
        basis[name] = source

    set_metric("uncached_input_tokens", uncached)
    set_metric("cached_input_tokens", cache_read)
    set_metric("cache_write_tokens", cache_write)
    set_metric("input_tokens", prompt_total, "derived" if prompt_total is not None else "unavailable")
    set_metric("output_tokens", output)
    set_metric("provider_reported_total_tokens", provider_total)

    if prompt_total is not None and output is not None:
        reconstructed = prompt_total + output
        set_metric("reconstructed_total_tokens", reconstructed, "derived")
        if provider_total is not None:
            delta = provider_total - reconstructed
            set_metric("reconciliation_delta_tokens", delta, "derived")
            set_metric("unclassified_tokens", max(0, delta), "derived")
    return tokens, basis


def ingest_openclaw_turn(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    run_id = _clean_text(payload.get("run_id"))
    session_key = _clean_text(payload.get("session_key"), limit=1024)
    if not run_id:
        raise ValueError("run_id is required")
    if not session_key:
        raise ValueError("session_key is required")

    provider = _normalize_provider(payload.get("provider"), payload.get("resolved_ref"))
    model = _model_from_payload(payload.get("model"), payload.get("resolved_ref"))
    usage = _clean_usage(payload.get("usage"))
    last_usage = _clean_usage(payload.get("last_usage"))
    runtime_turn_usd = _as_float(payload.get("runtime_turn_usd"))
    if runtime_turn_usd is not None and runtime_turn_usd < 0:
        runtime_turn_usd = None

    model_calls = []
    seen = set()
    for raw in payload.get("model_calls") or []:
        if not isinstance(raw, dict):
            continue
        call = _clean_model_call(raw)
        key = call.get("call_id") or (
            call.get("provider"), call.get("model"), call.get("duration_ms"), call.get("outcome")
        )
        if key in seen:
            continue
        seen.add(key)
        model_calls.append(call)

    completed_calls = [call for call in model_calls if call.get("outcome") == "completed"]
    failed_calls = [call for call in model_calls if call.get("outcome") == "error"]

    receipt_id = _stable_id("openclaw", session_key, run_id)
    thread_id = _stable_id("openclaw-thread", session_key)

    pricing = None
    # Aggregate normalized usage can be safely interpreted as one pricing request
    # only when OpenClaw's lifecycle evidence proves exactly one completed call.
    if len(completed_calls) == 1:
        call_provider = completed_calls[0].get("provider") or provider
        call_model = completed_calls[0].get("model") or model
        pricing = _price_single_call(call_provider, call_model, usage)

    if pricing is not None:
        cost = pricing["amount"]
        cost_basis = pricing["basis"]
        estimate_complete = bool(pricing["complete"])
        pricing_components = pricing["components"]
        registry_verified_at = pricing["verified_at"]
    elif runtime_turn_usd is not None:
        # OpenClaw's own turn amount is useful evidence, especially for multi-call,
        # local, routed, or provider-plugin models TokenTotals does not yet price.
        # Keep provenance explicit rather than calling it an independent TT rebuild.
        cost = runtime_turn_usd
        cost_basis = "openclaw_runtime_reported"
        estimate_complete = True
        pricing_components = {}
        registry_verified_at = None
    else:
        cost = None
        cost_basis = "unavailable"
        estimate_complete = False
        pricing_components = {}
        registry_verified_at = None

    if cost is not None:
        state_after = config_manager.update_spend(
            cost_usd=float(cost),
            thread_id=thread_id,
            reservation_id=receipt_id,
        )
    else:
        state_after = config_manager.get_state()

    tokens, token_basis = _ledger_tokens(usage)
    duration_ms = _as_int(payload.get("duration_ms"))
    completed_at = datetime.now(timezone.utc).isoformat()
    notes = [
        "external_surface:openclaw",
        "external_same_turn_evidence",
        f"openclaw_run_id:{_stable_id('run', run_id)}",
        f"openclaw_model_calls:{len(model_calls)}",
        f"openclaw_completed_calls:{len(completed_calls)}",
        f"openclaw_failed_calls:{len(failed_calls)}",
    ]
    if payload.get("context_token_budget") is not None:
        notes.append("openclaw_context_budget_observed")
    if payload.get("context_used_tokens") is not None:
        notes.append("openclaw_context_used_observed")

    record = {
        "schema_version": turn_ledger.SCHEMA_VERSION,
        "turn_id": receipt_id,
        "thread_id": thread_id,
        "started_at": None,
        "completed_at": completed_at,
        "latency_ms": duration_ms,
        "provider": provider,
        "requested_model_id": _clean_text(payload.get("requested"), limit=512) or model,
        "canonical_model_id": model or None,
        "observed_model_id": model or None,
        "registry_verified_at": registry_verified_at,
        "requested_service_tier": None,
        "observed_service_tier": None,
        "tokens": tokens,
        "token_basis": token_basis,
        "modalities": {},
        "server_tools": {},
        "estimated_cost_usd": cost,
        "estimated_cost_picos": turn_ledger.usd_to_picos(cost),
        "pricing_components_usd": pricing_components,
        "cost_basis": cost_basis,
        "estimate_complete": estimate_complete,
        "notes": notes,
        "cumulative_local_estimated_spend_usd": state_after.get("current_spend_usd"),
        "cumulative_thread_estimated_spend_usd": state_after.get("thread_spend_usd"),
        "cumulative_completed_turns": state_after.get("total_requests"),
    }

    appended = turn_ledger.append_turn(record)
    openclaw_evidence_store.append(
        {
            "receipt_id": receipt_id,
            "source_run_id": run_id,
            "source_session_key": session_key,
            "source_session_id": _clean_text(payload.get("session_id")) or None,
            "provider": provider,
            "model": model,
            "resolved_ref": _clean_text(payload.get("resolved_ref")) or None,
            "requested": _clean_text(payload.get("requested")) or None,
            "usage": usage,
            "last_usage": last_usage,
            "runtime_turn_usd": runtime_turn_usd,
            "duration_ms": duration_ms,
            "context_token_budget": _as_int(payload.get("context_token_budget")),
            "context_used_tokens": _as_int(payload.get("context_used_tokens")),
            "reasoning_effort": _clean_text(payload.get("reasoning_effort"), limit=64) or None,
            "fast_mode": payload.get("fast_mode") if isinstance(payload.get("fast_mode"), bool) else None,
            "fallback_used": payload.get("fallback_used") if isinstance(payload.get("fallback_used"), bool) else None,
            "auth_mode": _clean_text(payload.get("auth_mode"), limit=64) or None,
            "override_source": _clean_text(payload.get("override_source"), limit=128) or None,
            "model_calls": model_calls,
        }
    )

    return {
        "turn_id": receipt_id,
        "thread_id": thread_id,
        "created": bool(appended),
        "source_run_id": run_id,
        "model_call_count": len(model_calls),
        "completed_call_count": len(completed_calls),
        "failed_call_count": len(failed_calls),
        "cost_basis": cost_basis,
        "estimate_complete": estimate_complete,
    }
