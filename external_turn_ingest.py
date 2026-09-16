"""External same-turn telemetry ingestion for Turn Receipt surfaces.

This module intentionally accepts only usage/pricing evidence and correlation metadata.
It does not accept prompt text, answer text, API keys, cookies, hidden reasoning, or
provider credentials. Missing telemetry remains unavailable.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import config_manager
import turn_ledger
from anthropic_pricing import calculate_anthropic_response_cost
from google_pricing import calculate_google_response_cost, infer_google_platform
from openai_pricing import calculate_openai_response_cost

SUPPORTED_PROVIDERS = {"openai", "anthropic", "google"}


def _now():
    return datetime.now(timezone.utc)


def _clean_id(value, fallback=None):
    value = str(value or "").strip()
    return value or fallback


def _response_from_payload(provider, model, raw_usage, response_metadata):
    meta = dict(response_metadata or {})
    response = {"model": meta.get("model") or model}
    if provider == "google":
        response["usageMetadata"] = dict(raw_usage or {})
        if meta.get("modelVersion"):
            response["modelVersion"] = meta["modelVersion"]
    else:
        response["usage"] = dict(raw_usage or {})
        if meta.get("service_tier") is not None:
            response["service_tier"] = meta["service_tier"]
    return response


def _price(provider, model, response, *, service_tier=None, feature_hints=None):
    if provider == "openai":
        return calculate_openai_response_cost(
            model,
            response,
            request_service_tier=service_tier,
        )
    if provider == "anthropic":
        return calculate_anthropic_response_cost(
            model,
            response,
            processing_mode="standard",
            service_tier_hint=service_tier,
            platform="claude_api",
        )
    if provider == "google":
        return calculate_google_response_cost(
            model,
            response,
            request_service_tier=service_tier,
            processing_mode="standard",
            platform=infer_google_platform(model),
            request_feature_hints=list(feature_hints or []),
        )
    return None


def ingest_external_turn(payload):
    """Create exactly one canonical ledger turn from externally observed evidence.

    The caller must supply a stable source_turn_id from the external surface. The
    TokenTotals turn ID is namespaced from that identity, making retries idempotent.
    No receipt is created when the source identity is absent.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    provider = str(payload.get("provider") or "").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError("unsupported provider")

    model = _clean_id(payload.get("model"))
    if not model:
        raise ValueError("model is required")

    source_turn_id = _clean_id(payload.get("source_turn_id"))
    if not source_turn_id:
        raise ValueError("source_turn_id is required for exact-turn correlation")

    source_thread_id = _clean_id(payload.get("source_thread_id"), "default")
    surface = _clean_id(payload.get("surface"), "external")
    turn_id = f"ext-{provider}-{source_turn_id}"
    thread_id = f"ext-{provider}-{source_thread_id}"

    raw_usage = payload.get("usage")
    if raw_usage is not None and not isinstance(raw_usage, dict):
        raise ValueError("usage must be an object when supplied")

    response_metadata = payload.get("response_metadata")
    if response_metadata is not None and not isinstance(response_metadata, dict):
        raise ValueError("response_metadata must be an object when supplied")

    response = _response_from_payload(provider, model, raw_usage or {}, response_metadata or {})
    service_tier = (response_metadata or {}).get("service_tier")
    provider_result = None
    ledger_cost = None
    cost_basis = "unavailable"
    estimate_complete = False

    # Pricing is attempted only when usage evidence exists. Empty/missing usage
    # must never turn into an invented zero-cost receipt.
    if raw_usage:
        provider_result = _price(
            provider,
            model,
            response,
            service_tier=service_tier,
            feature_hints=payload.get("feature_hints"),
        )
        if provider_result and provider_result.get("complete") and provider_result.get("total_cost_usd") is not None:
            ledger_cost = provider_result["total_cost_usd"]
            cost_basis = "provider_registry_complete"
            estimate_complete = True
        elif provider_result and provider_result.get("known_list_equivalent_usd") is not None:
            ledger_cost = provider_result["known_list_equivalent_usd"]
            cost_basis = "known_list_equivalent"

    state_after = config_manager.update_spend(
        cost_usd=float(ledger_cost or 0.0),
        thread_id=thread_id,
        reservation_id=turn_id,
    )

    completed_at = payload.get("completed_at")
    if isinstance(completed_at, datetime):
        end_time = completed_at
    else:
        end_time = _now()

    record = turn_ledger.build_turn_record(
        turn_id=turn_id,
        thread_id=thread_id,
        requested_model_id=model,
        completion_response=response,
        provider_result=provider_result,
        estimated_cost_usd=ledger_cost,
        cost_basis=cost_basis,
        estimate_complete=estimate_complete,
        start_time=None,
        end_time=end_time,
        requested_service_tier=service_tier,
        state_after=state_after,
    )
    notes = list(record.get("notes") or [])
    notes.append(f"external_surface:{surface}")
    notes.append("external_same_turn_evidence")
    record["notes"] = notes

    appended = turn_ledger.append_turn(record)
    return {
        "turn_id": turn_id,
        "thread_id": thread_id,
        "created": bool(appended),
        "provider": provider,
        "model": model,
        "cost_basis": cost_basis,
        "estimate_complete": estimate_complete,
    }
