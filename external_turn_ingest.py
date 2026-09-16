"""Privacy-limited ingest for turns completed in provider-owned chat surfaces.

This module accepts only same-turn evidence supplied by a local browser/host
adapter. Prompt/answer text may be supplied transiently for local token estimation,
but is never written to the ledger. Missing provider telemetry stays unavailable.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import litellm
from fastapi import APIRouter, HTTPException

import turn_ledger
import turn_receipt
import turn_receipt_renderer


router = APIRouter()

_ALLOWED_BASIS = {"observed", "derived", "unavailable"}
_BROWSER_SURFACES = {"gemini_web", "chatgpt_web", "claude_web"}
_FORBIDDEN_PERSIST_KEYS = {
    "prompt",
    "answer",
    "messages",
    "conversation",
    "api_key",
    "authorization",
    "cookie",
    "cookies",
    "hidden_reasoning",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_int(value: Any):
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _opaque_id(prefix: str, value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return f"{prefix}-{uuid.uuid4().hex}"
    digest = hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:32]
    return f"{prefix}-{digest}"


def _estimate_text_tokens(text: Any, model_id: str):
    value = str(text or "")
    if not value:
        return None
    try:
        count = int(litellm.token_counter(model=model_id or None, text=value))
        return max(1, count)
    except Exception:
        # Explicitly a derived fallback. It is never presented as observed usage.
        return max(1, len(value) // 4)


def _metric(raw: Any):
    if isinstance(raw, dict):
        value = _as_int(raw.get("value"))
        basis = str(raw.get("basis") or "unavailable").strip().lower()
        if basis not in _ALLOWED_BASIS:
            basis = "unavailable"
        if value is None:
            basis = "unavailable"
        return value, basis
    value = _as_int(raw)
    return value, "observed" if value is not None else "unavailable"


def _validate_payload(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="External turn payload must be a JSON object")

    for key in payload:
        if str(key).lower() in _FORBIDDEN_PERSIST_KEYS:
            raise HTTPException(status_code=400, detail=f"Unsupported external-turn field: {key}")

    surface = str(payload.get("surface") or "").strip().lower()
    if not surface:
        raise HTTPException(status_code=400, detail="surface is required")

    model_id = str(payload.get("model_id") or "").strip()
    provider = str(payload.get("provider") or "unknown").strip().lower() or "unknown"
    if surface == "gemini_web" and provider == "unknown":
        provider = "google"
    elif surface == "chatgpt_web" and provider == "unknown":
        provider = "openai"
    elif surface == "claude_web" and provider == "unknown":
        provider = "anthropic"

    return {
        **payload,
        "surface": surface,
        "provider": provider,
        "model_id": model_id,
    }


def settle_external_turn(payload: dict) -> dict:
    payload = _validate_payload(payload)
    surface = payload["surface"]
    provider = payload["provider"]
    model_id = payload["model_id"]

    raw_tokens = payload.get("tokens") if isinstance(payload.get("tokens"), dict) else {}
    tokens = {name: None for name in turn_ledger.TOKEN_FIELDS}
    token_basis = {name: "unavailable" for name in turn_ledger.TOKEN_FIELDS}

    for name in turn_ledger.TOKEN_FIELDS:
        value, basis = _metric(raw_tokens.get(name))
        tokens[name] = value
        token_basis[name] = basis

    # Browser surfaces often do not expose provider-native token telemetry. The
    # adapter may send the visible current-turn text transiently so TokenTotals can
    # derive an explicitly incomplete local estimate. These strings are discarded
    # here and are never inserted into the ledger record.
    visible_user_text = payload.get("visible_user_text")
    visible_assistant_text = payload.get("visible_assistant_text")
    if tokens["input_tokens"] is None and visible_user_text:
        tokens["input_tokens"] = _estimate_text_tokens(visible_user_text, model_id)
        token_basis["input_tokens"] = "derived" if tokens["input_tokens"] is not None else "unavailable"
    if tokens["output_tokens"] is None and visible_assistant_text:
        tokens["output_tokens"] = _estimate_text_tokens(visible_assistant_text, model_id)
        token_basis["output_tokens"] = "derived" if tokens["output_tokens"] is not None else "unavailable"

    if tokens["input_tokens"] is not None and tokens["output_tokens"] is not None:
        tokens["reconstructed_total_tokens"] = tokens["input_tokens"] + tokens["output_tokens"]
        token_basis["reconstructed_total_tokens"] = "derived"

    provider_total = tokens.get("provider_reported_total_tokens")
    reconstructed = tokens.get("reconstructed_total_tokens")
    if provider_total is not None and reconstructed is not None:
        delta = provider_total - reconstructed
        tokens["reconciliation_delta_tokens"] = delta
        token_basis["reconciliation_delta_tokens"] = "derived"
        tokens["unclassified_tokens"] = max(0, delta)
        token_basis["unclassified_tokens"] = "derived"

    external_thread = payload.get("external_thread_id") or payload.get("thread_id")
    external_turn = payload.get("external_turn_id") or payload.get("turn_id")
    thread_id = _opaque_id(f"{surface}-thread", external_thread)
    turn_id = _opaque_id(f"{surface}-turn", external_turn)

    started_at = payload.get("started_at")
    completed_at = payload.get("completed_at") or _now_iso()
    latency_ms = _as_int(payload.get("latency_ms"))

    notes = [f"External surface: {surface}."]
    if surface in _BROWSER_SURFACES:
        notes.append(
            "Provider-owned consumer chat surface; provider billing semantics are not inferred from API pricing."
        )
    if any(token_basis.get(name) == "derived" for name in ("input_tokens", "output_tokens")):
        notes.append(
            "At least one token count is derived from visible current-turn text; hidden system/context usage may be unavailable."
        )

    # Browser consumer surfaces do not automatically share the same billing basis
    # as provider APIs. Until account/provider-native cost telemetry is observed,
    # cost remains unavailable rather than pretending that API list price is the
    # user's charge.
    estimated_cost_usd = None
    cost_basis = "unavailable"
    estimate_complete = False

    record = {
        "schema_version": turn_ledger.SCHEMA_VERSION,
        "turn_id": turn_id,
        "thread_id": thread_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "latency_ms": latency_ms,
        "provider": provider,
        "requested_model_id": model_id,
        "canonical_model_id": None,
        "observed_model_id": model_id or None,
        "registry_verified_at": None,
        "requested_service_tier": None,
        "observed_service_tier": None,
        "tokens": tokens,
        "token_basis": token_basis,
        "modalities": {},
        "server_tools": {},
        "estimated_cost_usd": estimated_cost_usd,
        "estimated_cost_picos": None,
        "pricing_components_usd": {},
        "cost_basis": cost_basis,
        "estimate_complete": estimate_complete,
        "notes": notes,
        "cumulative_local_estimated_spend_usd": None,
        "cumulative_thread_estimated_spend_usd": None,
        "cumulative_completed_turns": None,
    }

    appended = turn_ledger.append_turn(record)
    receipt = turn_receipt.by_id(turn_id)
    if receipt is None:
        raise RuntimeError("External turn settled but canonical Turn Receipt could not be loaded")
    return {
        "receipt_id": turn_id,
        "thread_id": thread_id,
        "duplicate": not appended,
        "receipt": receipt,
    }


@router.post("/api/external-turns/settle")
async def external_turn_settle(payload: dict):
    return settle_external_turn(payload)


@router.post("/api/external-turns/settle/render")
async def external_turn_settle_and_render(payload: dict):
    mode = str(payload.pop("receipt_mode", "standard") or "standard").strip().lower()
    if mode not in {"standard", "expanded"}:
        raise HTTPException(status_code=400, detail="receipt_mode must be standard or expanded")
    result = settle_external_turn(payload)
    html = turn_receipt_renderer.render_html(result["receipt"], mode=mode)
    return {
        "receipt_id": result["receipt_id"],
        "thread_id": result["thread_id"],
        "duplicate": result["duplicate"],
        "html": html,
    }
