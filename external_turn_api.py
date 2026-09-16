"""External chat-surface ingest for TurnReceipt.

This module accepts evidence observed by a user-authorized surface adapter, derives
only what can be derived locally, writes the canonical TokenTotals ledger record,
and deliberately does not persist prompt/answer text.
"""

import hashlib
from datetime import datetime, timezone

import litellm
from fastapi import HTTPException, Request

import turn_ledger
import turn_receipt

_ALLOWED_SURFACES = {"gemini_web", "claude_web", "chatgpt_web", "hermes", "openclaw", "lobster"}


def _clean_text(value):
    return str(value or "")


def _clean_id(value, name):
    value = str(value or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail=f"{name} must be non-empty")
    if len(value) > 256:
        raise HTTPException(status_code=400, detail=f"{name} is too long")
    return value


def _stable_id(surface, external_turn_id):
    digest = hashlib.sha256(f"{surface}\n{external_turn_id}".encode("utf-8")).hexdigest()[:32]
    return f"ext-{surface}-{digest}"


def _estimate_tokens(text, model_id):
    if not text:
        return None, "unavailable"
    try:
        value = int(litellm.token_counter(model=model_id or None, text=text))
        return max(1, value), "derived"
    except Exception:
        # Explicit heuristic fallback, never presented as provider-observed usage.
        return max(1, len(text) // 4), "derived"


def _empty_token_maps():
    tokens = {name: None for name in turn_ledger.TOKEN_FIELDS}
    basis = {name: "unavailable" for name in turn_ledger.TOKEN_FIELDS}
    return tokens, basis


def build_external_record(payload):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON object required")

    surface = str(payload.get("surface") or "").strip().lower()
    if surface not in _ALLOWED_SURFACES:
        raise HTTPException(status_code=400, detail="unsupported external surface")

    external_turn_id = _clean_id(payload.get("external_turn_id"), "external_turn_id")
    external_thread_id = _clean_id(payload.get("external_thread_id"), "external_thread_id")
    model_id = str(payload.get("model_id") or "").strip()
    if len(model_id) > 160:
        raise HTTPException(status_code=400, detail="model_id is too long")

    input_text = _clean_text(payload.get("visible_input_text"))
    output_text = _clean_text(payload.get("visible_output_text"))
    if len(input_text) > 2_000_000 or len(output_text) > 4_000_000:
        raise HTTPException(status_code=413, detail="visible turn text is too large")

    observed = payload.get("observed_usage")
    if observed is not None and not isinstance(observed, dict):
        raise HTTPException(status_code=400, detail="observed_usage must be an object when supplied")

    tokens, basis = _empty_token_maps()

    # Prefer explicitly observed telemetry. Missing values remain unavailable.
    if observed:
        mapping = {
            "input_tokens": "input_tokens",
            "output_tokens": "output_tokens",
            "cached_input_tokens": "cached_input_tokens",
            "reasoning_tokens": "reasoning_tokens",
            "provider_reported_total_tokens": "provider_reported_total_tokens",
        }
        for source_name, target_name in mapping.items():
            if source_name not in observed or observed.get(source_name) is None:
                continue
            value = observed.get(source_name)
            if isinstance(value, bool):
                raise HTTPException(status_code=400, detail=f"{source_name} must be an integer")
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{source_name} must be an integer")
            if value < 0:
                raise HTTPException(status_code=400, detail=f"{source_name} must be non-negative")
            tokens[target_name] = value
            basis[target_name] = "observed"

    # If provider usage is absent, derive visible-text counts locally. This is an
    # explicit partial estimate: hidden system/context/tool tokens are unavailable.
    if tokens["input_tokens"] is None:
        tokens["input_tokens"], basis["input_tokens"] = _estimate_tokens(input_text, model_id)
    if tokens["output_tokens"] is None:
        tokens["output_tokens"], basis["output_tokens"] = _estimate_tokens(output_text, model_id)

    if tokens["input_tokens"] is not None and tokens["output_tokens"] is not None:
        tokens["reconstructed_total_tokens"] = tokens["input_tokens"] + tokens["output_tokens"]
        basis["reconstructed_total_tokens"] = "derived"

    if tokens["provider_reported_total_tokens"] is not None and tokens["reconstructed_total_tokens"] is not None:
        delta = tokens["provider_reported_total_tokens"] - tokens["reconstructed_total_tokens"]
        tokens["reconciliation_delta_tokens"] = delta
        basis["reconciliation_delta_tokens"] = "derived"
        tokens["unclassified_tokens"] = max(0, delta)
        basis["unclassified_tokens"] = "derived"

    now = datetime.now(timezone.utc).isoformat()
    turn_id = _stable_id(surface, external_turn_id)
    thread_id = f"ext-{surface}-{hashlib.sha256(external_thread_id.encode('utf-8')).hexdigest()[:24]}"

    notes = [
        f"source_surface={surface}",
        "external_surface_evidence",
        "prompt_and_answer_text_not_persisted",
    ]
    if not observed:
        notes.append("visible_text_token_estimate_only")
        notes.append("hidden_context_and_provider_internal_usage_unavailable")
    else:
        notes.append("provider_surface_usage_fields_observed_by_adapter")

    provider = turn_ledger.infer_provider(model_id)
    return {
        "schema_version": turn_ledger.SCHEMA_VERSION,
        "turn_id": turn_id,
        "thread_id": thread_id,
        "started_at": None,
        "completed_at": now,
        "latency_ms": None,
        "provider": provider,
        "requested_model_id": model_id,
        "canonical_model_id": None,
        "observed_model_id": model_id or None,
        "registry_verified_at": None,
        "requested_service_tier": None,
        "observed_service_tier": None,
        "tokens": tokens,
        "token_basis": basis,
        "modalities": {},
        "server_tools": {},
        # Consumer web surfaces do not imply token-billed API charges. Do not
        # manufacture a dollar value from visible text alone.
        "estimated_cost_usd": None,
        "estimated_cost_picos": None,
        "pricing_components_usd": {},
        "cost_basis": "unavailable_external_surface",
        "estimate_complete": False,
        "notes": notes,
        "cumulative_local_estimated_spend_usd": None,
        "cumulative_thread_estimated_spend_usd": None,
        "cumulative_completed_turns": None,
    }


def register_external_turn_routes(app):
    @app.post("/api/external-turn")
    async def ingest_external_turn(request: Request):
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        record = build_external_record(payload)
        try:
            created = turn_ledger.append_turn(record)
            receipt = turn_receipt.by_id(record["turn_id"])
        except turn_ledger.LedgerCorruptionError as exc:
            raise HTTPException(status_code=500, detail=f"TokenTotals turn ledger is corrupt: {exc}")

        if receipt is None:
            raise HTTPException(status_code=500, detail="External turn settled but receipt could not be loaded")

        return {
            "created": bool(created),
            "receipt_id": record["turn_id"],
            "thread_id": record["thread_id"],
            "render_standard": f"/api/turn-receipt/{record['turn_id']}/render?mode=standard",
            "render_expanded": f"/api/turn-receipt/{record['turn_id']}/render?mode=expanded",
        }
