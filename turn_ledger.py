import json
import os
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import config_manager

SCHEMA_VERSION = 1
MONEY_PICOS_PER_USD = 1_000_000_000_000
_LEDGER_LOCK = threading.RLock()
_LEDGER_FILE_OVERRIDE = None
_SEEN_LEDGER_PATH = None
_SEEN_TURN_IDS = None

TOKEN_FIELDS = (
    "input_tokens",
    "uncached_input_tokens",
    "cached_input_tokens",
    "cache_write_tokens",
    "output_tokens",
    "reasoning_tokens",
    "tool_input_tokens",
    "provider_reported_total_tokens",
    "reconstructed_total_tokens",
    "unclassified_tokens",
    "reconciliation_delta_tokens",
)
_TOKEN_BASES = {"observed", "derived", "unavailable"}
_MODALITIES = ("text", "image", "video", "audio")
_TOOL_COUNT_FIELDS = (
    "web_search_requests",
    "web_fetch_requests",
    "search_query_count",
    "maps_query_count",
)
_TOOL_BOOL_FIELDS = (
    "search_used",
    "maps_used",
)
_TOOL_BASIS_FIELDS = (
    "search_query_count_basis",
    "maps_query_count_basis",
)


class LedgerCorruptionError(ValueError):
    pass


def ledger_path():
    if _LEDGER_FILE_OVERRIDE is not None:
        return Path(_LEDGER_FILE_OVERRIDE)
    return Path(config_manager.APP_DIR) / "turns.jsonl"


def usd_to_picos(value):
    if value is None:
        return None
    amount = Decimal(str(value)) * Decimal(MONEY_PICOS_PER_USD)
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def picos_to_usd(value):
    if value is None:
        return None
    return float(Decimal(int(value)) / Decimal(MONEY_PICOS_PER_USD))


def _obj_get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _obj_has(obj, key):
    if obj is None:
        return False
    if isinstance(obj, dict):
        return key in obj and obj.get(key) is not None
    return getattr(obj, key, None) is not None


def _first_present(obj, *keys):
    for key in keys:
        if _obj_has(obj, key):
            return _obj_get(obj, key), key
    return None, None


def _as_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _iso_time(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _latency_ms(start_time, end_time):
    if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
        return None
    try:
        return max(0, int((end_time - start_time).total_seconds() * 1000))
    except Exception:
        return None


def _response_usage(response):
    native = _obj_get(response, "usageMetadata", None)
    if native is None:
        native = _obj_get(response, "usage_metadata", None)
    if native is not None:
        return native
    hidden = _obj_get(response, "_hidden_params", None)
    if hidden:
        native = _obj_get(hidden, "usageMetadata", None) or _obj_get(hidden, "usage_metadata", None)
        if native is not None:
            return native
    return _obj_get(response, "usage", None)


def _response_model(response):
    return (
        _obj_get(response, "modelVersion", None)
        or _obj_get(response, "model_version", None)
        or _obj_get(response, "model", None)
    )


def _details(usage, primary, secondary=None):
    value = _obj_get(usage, primary, None)
    if value is None and secondary:
        value = _obj_get(usage, secondary, None)
    return value


def _empty_tokens():
    return {name: None for name in TOKEN_FIELDS}, {name: "unavailable" for name in TOKEN_FIELDS}


def _set_token(tokens, basis, name, value, source_basis):
    value = _as_int(value)
    tokens[name] = value
    basis[name] = source_basis if value is not None else "unavailable"


def _sum_modalities(value):
    if not isinstance(value, dict):
        return None
    return sum(int(value.get(key, 0) or 0) for key in _MODALITIES)


def _standardize_openai(completion_response, provider_result):
    raw = _response_usage(completion_response)
    normalized = (provider_result or {}).get("usage") or {}
    tokens, basis = _empty_tokens()

    raw_input, _ = _first_present(raw, "input_tokens", "prompt_tokens")
    raw_output, _ = _first_present(raw, "output_tokens", "completion_tokens")
    _set_token(tokens, basis, "input_tokens", raw_input, "observed")
    _set_token(tokens, basis, "output_tokens", raw_output, "observed")

    input_details = _details(raw, "input_tokens_details", "prompt_tokens_details")
    output_details = _details(raw, "output_tokens_details", "completion_tokens_details")
    cached, _ = _first_present(input_details, "cached_tokens")
    cache_write, _ = _first_present(input_details, "cache_write_tokens")
    reasoning, _ = _first_present(output_details, "reasoning_tokens")
    _set_token(tokens, basis, "cached_input_tokens", cached, "observed")
    _set_token(tokens, basis, "cache_write_tokens", cache_write, "observed")
    _set_token(tokens, basis, "reasoning_tokens", reasoning, "observed")

    if tokens["input_tokens"] is not None and cached is not None and cache_write is not None:
        _set_token(
            tokens,
            basis,
            "uncached_input_tokens",
            max(0, tokens["input_tokens"] - int(cached) - int(cache_write)),
            "derived",
        )

    provider_total, _ = _first_present(raw, "total_tokens")
    _set_token(tokens, basis, "provider_reported_total_tokens", provider_total, "observed")
    if tokens["input_tokens"] is not None and tokens["output_tokens"] is not None:
        _set_token(
            tokens,
            basis,
            "reconstructed_total_tokens",
            tokens["input_tokens"] + tokens["output_tokens"],
            "derived",
        )
    if tokens["provider_reported_total_tokens"] is not None and tokens["reconstructed_total_tokens"] is not None:
        delta = tokens["provider_reported_total_tokens"] - tokens["reconstructed_total_tokens"]
        _set_token(tokens, basis, "reconciliation_delta_tokens", delta, "derived")
        _set_token(tokens, basis, "unclassified_tokens", max(0, delta), "derived")

    modalities = {}
    audio_in, _ = _first_present(input_details, "audio_tokens")
    audio_out, _ = _first_present(output_details, "audio_tokens")
    if audio_in is not None:
        modalities.setdefault("input", {})["audio"] = _as_int(audio_in)
    if audio_out is not None:
        modalities.setdefault("output", {})["audio"] = _as_int(audio_out)
    return tokens, basis, modalities, {}, normalized


def _standardize_anthropic(completion_response, provider_result):
    raw = _response_usage(completion_response)
    normalized = (provider_result or {}).get("usage") or {}
    tokens, basis = _empty_tokens()

    input_observed = _first_present(raw, "input_tokens", "prompt_tokens")[0] is not None
    output_observed = _first_present(raw, "output_tokens", "completion_tokens")[0] is not None
    input_basis_complete = bool(normalized.get("input_basis_complete"))

    if input_observed and input_basis_complete:
        _set_token(tokens, basis, "input_tokens", normalized.get("total_input_tokens"), "derived")
        _set_token(tokens, basis, "uncached_input_tokens", normalized.get("input_tokens"), "derived")
    if output_observed:
        _set_token(tokens, basis, "output_tokens", normalized.get("output_tokens"), "observed")

    prompt_details = _obj_get(raw, "prompt_tokens_details", None)
    cache_create_exposed = (
        _obj_has(raw, "cache_creation_input_tokens")
        or _obj_has(prompt_details, "cache_creation_tokens")
        or _obj_has(prompt_details, "cache_write_tokens")
    )
    cache_read_exposed = _obj_has(raw, "cache_read_input_tokens") or _obj_has(prompt_details, "cached_tokens")
    if cache_create_exposed:
        _set_token(tokens, basis, "cache_write_tokens", normalized.get("cache_creation_input_tokens"), "observed")
    if cache_read_exposed:
        _set_token(tokens, basis, "cached_input_tokens", normalized.get("cache_read_input_tokens"), "observed")

    output_details = _details(raw, "output_tokens_details", "completion_tokens_details")
    thinking, _ = _first_present(output_details, "thinking_tokens")
    _set_token(tokens, basis, "reasoning_tokens", thinking, "observed")

    provider_total, _ = _first_present(raw, "total_tokens")
    _set_token(tokens, basis, "provider_reported_total_tokens", provider_total, "observed")
    if tokens["input_tokens"] is not None and tokens["output_tokens"] is not None:
        _set_token(
            tokens,
            basis,
            "reconstructed_total_tokens",
            tokens["input_tokens"] + tokens["output_tokens"],
            "derived",
        )
    if tokens["provider_reported_total_tokens"] is not None and tokens["reconstructed_total_tokens"] is not None:
        delta = tokens["provider_reported_total_tokens"] - tokens["reconstructed_total_tokens"]
        _set_token(tokens, basis, "reconciliation_delta_tokens", delta, "derived")
        _set_token(tokens, basis, "unclassified_tokens", max(0, delta), "derived")

    server_tools = {}
    raw_tools = _obj_get(raw, "server_tool_use", None)
    for key in ("web_search_requests", "web_fetch_requests"):
        if _obj_has(raw_tools, key):
            server_tools[key] = int(_obj_get(raw_tools, key, 0) or 0)
    return tokens, basis, {}, server_tools, normalized


def _google_modality_details_present(raw, source_shape, kind):
    if source_shape == "google_raw":
        fields = {
            "uncached_input": ("promptTokensDetails", "prompt_tokens_details"),
            "cached_input": ("cacheTokensDetails", "cache_tokens_details"),
            "output": ("candidatesTokensDetails", "responseTokensDetails", "candidates_tokens_details", "response_tokens_details"),
            "tool_input": ("toolUsePromptTokensDetails", "tool_use_prompt_tokens_details"),
        }
    else:
        fields = {
            "uncached_input": ("prompt_tokens_details",),
            "cached_input": ("prompt_tokens_details",),
            "output": ("completion_tokens_details",),
            "tool_input": ("prompt_tokens_details",),
        }
    return any(_obj_has(raw, field) for field in fields.get(kind, ()))


def _standardize_google(completion_response, provider_result):
    raw = _response_usage(completion_response)
    normalized = (provider_result or {}).get("usage") or {}
    tokens, basis = _empty_tokens()
    source_shape = normalized.get("source_shape")

    if source_shape == "google_raw":
        input_explicit = _obj_has(raw, "promptTokenCount") or _obj_has(raw, "prompt_token_count")
        output_explicit = (
            _obj_has(raw, "candidatesTokenCount")
            or _obj_has(raw, "candidates_token_count")
            or _obj_has(raw, "responseTokenCount")
            or _obj_has(raw, "response_token_count")
        )
        cached_explicit = _obj_has(raw, "cachedContentTokenCount") or _obj_has(raw, "cached_content_token_count")
        tool_explicit = _obj_has(raw, "toolUsePromptTokenCount") or _obj_has(raw, "tool_use_prompt_token_count")
        reasoning_explicit = _obj_has(raw, "thoughtsTokenCount") or _obj_has(raw, "thoughts_token_count")
        total_explicit = _obj_has(raw, "totalTokenCount") or _obj_has(raw, "total_token_count")
    elif source_shape == "litellm_normalized":
        prompt_details = _obj_get(raw, "prompt_tokens_details", None)
        completion_details = _obj_get(raw, "completion_tokens_details", None)
        input_explicit = _obj_has(raw, "prompt_tokens")
        output_explicit = _obj_has(raw, "completion_tokens")
        cached_explicit = _obj_has(prompt_details, "cached_tokens") or _obj_has(raw, "cache_read_input_tokens")
        tool_explicit = _obj_has(prompt_details, "tool_use_tokens")
        reasoning_explicit = _obj_has(completion_details, "reasoning_tokens") or _obj_has(raw, "reasoning_tokens")
        total_explicit = _obj_has(raw, "total_tokens")
    else:
        input_explicit = output_explicit = cached_explicit = False
        tool_explicit = reasoning_explicit = total_explicit = False

    prompt = _as_int(normalized.get("prompt_total_tokens")) if input_explicit else None
    _set_token(tokens, basis, "input_tokens", prompt, "observed")
    if cached_explicit:
        cached = _as_int(normalized.get("cached_tokens"))
        _set_token(tokens, basis, "cached_input_tokens", cached, "observed")
        if prompt is not None and cached is not None:
            _set_token(tokens, basis, "uncached_input_tokens", max(0, prompt - cached), "derived")
    if tool_explicit:
        _set_token(tokens, basis, "tool_input_tokens", normalized.get("tool_use_prompt_tokens"), "observed")
    if reasoning_explicit:
        _set_token(tokens, basis, "reasoning_tokens", normalized.get("thinking_tokens"), "observed")

    if output_explicit:
        output_including_reasoning = _as_int(normalized.get("output_tokens_including_thinking"))
        output_excluding_reasoning = output_including_reasoning
        if source_shape == "litellm_normalized" and tokens["reasoning_tokens"] is not None:
            output_excluding_reasoning = max(0, output_including_reasoning - tokens["reasoning_tokens"])
        elif source_shape == "google_raw":
            candidate_sum = _sum_modalities(normalized.get("candidate_output_modalities") or {})
            if candidate_sum is not None:
                output_excluding_reasoning = candidate_sum
        _set_token(tokens, basis, "output_tokens", output_excluding_reasoning, "derived")

    if total_explicit:
        _set_token(tokens, basis, "provider_reported_total_tokens", normalized.get("total_tokens"), "observed")
        unattributed = _as_int(normalized.get("unattributed_tokens"))
        if unattributed is not None:
            _set_token(tokens, basis, "unclassified_tokens", unattributed, "derived")
            _set_token(
                tokens,
                basis,
                "reconstructed_total_tokens",
                max(0, tokens["provider_reported_total_tokens"] - unattributed),
                "derived",
            )
            _set_token(tokens, basis, "reconciliation_delta_tokens", unattributed, "derived")

    modalities = {}
    for bucket, normalized_name in (
        ("uncached_input", "uncached_input_modalities"),
        ("cached_input", "cached_input_modalities"),
        ("output", "candidate_output_modalities"),
        ("tool_input", "tool_use_prompt_modalities"),
    ):
        value = normalized.get(normalized_name)
        if not _google_modality_details_present(raw, source_shape, bucket) or not isinstance(value, dict):
            continue
        cleaned = {key: _as_int(value.get(key)) for key in _MODALITIES if value.get(key) is not None}
        if cleaned:
            modalities[bucket] = cleaned

    server_tools = {}
    grounding = normalized.get("grounding") or {}
    if grounding.get("grounding_metadata_observed"):
        server_tools["search_used"] = bool(grounding.get("search_used", False))
        server_tools["search_query_count"] = grounding.get("search_query_count")
        server_tools["search_query_count_basis"] = grounding.get("search_query_count_basis", "unavailable")
        server_tools["maps_used"] = bool(grounding.get("maps_used", False))
        server_tools["maps_query_count"] = grounding.get("maps_query_count")
        server_tools["maps_query_count_basis"] = grounding.get("maps_query_count_basis", "unavailable")
    return tokens, basis, modalities, server_tools, normalized


def _standardize_generic(completion_response):
    raw = _response_usage(completion_response)
    tokens, basis = _empty_tokens()
    input_value, _ = _first_present(raw, "input_tokens", "prompt_tokens")
    output_value, _ = _first_present(raw, "output_tokens", "completion_tokens")
    provider_total, _ = _first_present(raw, "total_tokens")
    _set_token(tokens, basis, "input_tokens", input_value, "observed")
    _set_token(tokens, basis, "output_tokens", output_value, "observed")
    _set_token(tokens, basis, "provider_reported_total_tokens", provider_total, "observed")

    input_details = _details(raw, "input_tokens_details", "prompt_tokens_details")
    output_details = _details(raw, "output_tokens_details", "completion_tokens_details")
    cached, _ = _first_present(input_details, "cached_tokens")
    reasoning, _ = _first_present(output_details, "reasoning_tokens", "thinking_tokens")
    _set_token(tokens, basis, "cached_input_tokens", cached, "observed")
    _set_token(tokens, basis, "reasoning_tokens", reasoning, "observed")
    if tokens["input_tokens"] is not None and cached is not None:
        _set_token(tokens, basis, "uncached_input_tokens", max(0, tokens["input_tokens"] - int(cached)), "derived")
    if tokens["input_tokens"] is not None and tokens["output_tokens"] is not None:
        _set_token(
            tokens,
            basis,
            "reconstructed_total_tokens",
            tokens["input_tokens"] + tokens["output_tokens"],
            "derived",
        )
    if tokens["provider_reported_total_tokens"] is not None and tokens["reconstructed_total_tokens"] is not None:
        delta = tokens["provider_reported_total_tokens"] - tokens["reconstructed_total_tokens"]
        _set_token(tokens, basis, "reconciliation_delta_tokens", delta, "derived")
        _set_token(tokens, basis, "unclassified_tokens", max(0, delta), "derived")
    return tokens, basis, {}, {}, {}


def standardize_tokens(provider, completion_response, provider_result=None):
    if provider == "openai":
        return _standardize_openai(completion_response, provider_result)
    if provider == "anthropic":
        return _standardize_anthropic(completion_response, provider_result)
    if provider == "google":
        return _standardize_google(completion_response, provider_result)
    return _standardize_generic(completion_response)


def infer_provider(requested_model_id, provider_result=None):
    if provider_result and provider_result.get("provider"):
        return str(provider_result["provider"])
    model = str(requested_model_id or "").lower()
    if model.startswith(("openai/", "gpt-", "o1", "o3", "o4")):
        return "openai"
    if model.startswith(("anthropic/", "claude-")):
        return "anthropic"
    if model.startswith(("google/", "gemini/", "vertex_ai/", "vertex-ai/", "gemini-")):
        return "google"
    if "/" in model:
        return model.split("/", 1)[0]
    return "unknown"


def build_turn_record(
    *,
    turn_id=None,
    thread_id="default",
    requested_model_id,
    completion_response,
    provider_result=None,
    estimated_cost_usd=None,
    cost_basis="unavailable",
    estimate_complete=False,
    start_time=None,
    end_time=None,
    requested_service_tier=None,
    state_after=None,
):
    provider = infer_provider(requested_model_id, provider_result)
    tokens, token_basis, modalities, server_tools, normalized_usage = standardize_tokens(
        provider, completion_response, provider_result
    )
    observed_model = (provider_result or {}).get("response_model_id") or _response_model(completion_response)
    canonical_model = (provider_result or {}).get("canonical_model_id")
    verified_at = (provider_result or {}).get("verified_at")

    observed_tier = None
    if provider == "openai" and (provider_result or {}).get("service_tier_source") == "response":
        observed_tier = (provider_result or {}).get("service_tier")
    elif provider in {"anthropic", "google"} and isinstance(normalized_usage, dict):
        observed_tier = normalized_usage.get("service_tier")

    state_after = state_after or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "turn_id": str(turn_id or uuid.uuid4().hex),
        "thread_id": str(thread_id or "default"),
        "started_at": _iso_time(start_time),
        "completed_at": _iso_time(end_time),
        "latency_ms": _latency_ms(start_time, end_time),
        "provider": provider,
        "requested_model_id": str(requested_model_id or ""),
        "canonical_model_id": str(canonical_model) if canonical_model is not None else None,
        "observed_model_id": str(observed_model) if observed_model is not None else None,
        "registry_verified_at": str(verified_at) if verified_at is not None else None,
        "requested_service_tier": str(requested_service_tier) if requested_service_tier is not None else None,
        "observed_service_tier": str(observed_tier) if observed_tier is not None else None,
        "tokens": tokens,
        "token_basis": token_basis,
        "modalities": modalities,
        "server_tools": server_tools,
        "estimated_cost_usd": float(estimated_cost_usd) if estimated_cost_usd is not None else None,
        "estimated_cost_picos": usd_to_picos(estimated_cost_usd),
        "pricing_components_usd": (provider_result or {}).get("components_usd") or {},
        "cost_basis": str(cost_basis or "unavailable"),
        "estimate_complete": bool(estimate_complete),
        "notes": [str(note) for note in ((provider_result or {}).get("notes") or [])],
        "cumulative_local_estimated_spend_usd": (
            float(state_after["current_spend_usd"])
            if state_after.get("current_spend_usd") is not None
            else None
        ),
        "cumulative_thread_estimated_spend_usd": (
            float(state_after["thread_spend_usd"])
            if state_after.get("thread_spend_usd") is not None
            else None
        ),
        "cumulative_completed_turns": (
            int(state_after["total_requests"])
            if state_after.get("total_requests") is not None
            else None
        ),
    }


def _numeric_tree(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, child in value.items():
            parsed = _numeric_tree(child)
            if parsed is not None:
                cleaned[str(key)] = parsed
        return cleaned
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    return None


def _sanitize_record(record):
    raw_tokens = record.get("tokens") if isinstance(record.get("tokens"), dict) else {}
    raw_basis = record.get("token_basis") if isinstance(record.get("token_basis"), dict) else {}
    tokens = {}
    basis = {}
    for name in TOKEN_FIELDS:
        value = _as_int(raw_tokens.get(name))
        tokens[name] = value
        status = raw_basis.get(name)
        basis[name] = status if status in _TOKEN_BASES else ("unavailable" if value is None else "derived")

    modalities = {}
    raw_modalities = record.get("modalities") if isinstance(record.get("modalities"), dict) else {}
    for bucket in ("input", "uncached_input", "cached_input", "output", "tool_input"):
        values = raw_modalities.get(bucket)
        if not isinstance(values, dict):
            continue
        cleaned = {key: _as_int(values.get(key)) for key in _MODALITIES if values.get(key) is not None}
        if cleaned:
            modalities[bucket] = cleaned

    server_tools = {}
    raw_tools = record.get("server_tools") if isinstance(record.get("server_tools"), dict) else {}
    for key in _TOOL_COUNT_FIELDS:
        if key in raw_tools:
            server_tools[key] = _as_int(raw_tools.get(key))
    for key in _TOOL_BOOL_FIELDS:
        if key in raw_tools:
            server_tools[key] = bool(raw_tools.get(key))
    for key in _TOOL_BASIS_FIELDS:
        if key in raw_tools:
            value = raw_tools.get(key)
            server_tools[key] = value if value in _TOKEN_BASES else "unavailable"

    notes = record.get("notes") if isinstance(record.get("notes"), list) else []
    cost = float(record["estimated_cost_usd"]) if record.get("estimated_cost_usd") is not None else None
    return {
        "schema_version": SCHEMA_VERSION,
        "turn_id": str(record.get("turn_id") or "").strip(),
        "thread_id": str(record.get("thread_id") or "default"),
        "started_at": record.get("started_at"),
        "completed_at": record.get("completed_at"),
        "latency_ms": _as_int(record.get("latency_ms")),
        "provider": str(record.get("provider") or "unknown"),
        "requested_model_id": str(record.get("requested_model_id") or ""),
        "canonical_model_id": record.get("canonical_model_id"),
        "observed_model_id": record.get("observed_model_id"),
        "registry_verified_at": record.get("registry_verified_at"),
        "requested_service_tier": record.get("requested_service_tier"),
        "observed_service_tier": record.get("observed_service_tier"),
        "tokens": tokens,
        "token_basis": basis,
        "modalities": modalities,
        "server_tools": server_tools,
        "estimated_cost_usd": cost,
        "estimated_cost_picos": usd_to_picos(cost),
        "pricing_components_usd": _numeric_tree(record.get("pricing_components_usd") or {}) or {},
        "cost_basis": str(record.get("cost_basis") or "unavailable"),
        "estimate_complete": bool(record.get("estimate_complete", False)),
        "notes": [str(note) for note in notes],
        "cumulative_local_estimated_spend_usd": (
            float(record["cumulative_local_estimated_spend_usd"])
            if record.get("cumulative_local_estimated_spend_usd") is not None
            else None
        ),
        "cumulative_thread_estimated_spend_usd": (
            float(record["cumulative_thread_estimated_spend_usd"])
            if record.get("cumulative_thread_estimated_spend_usd") is not None
            else None
        ),
        "cumulative_completed_turns": _as_int(record.get("cumulative_completed_turns")),
    }


def _read_lines_locked(path):
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LedgerCorruptionError(f"Invalid JSON in turn ledger line {line_no}: {exc}") from exc
            if not isinstance(record, dict) or not str(record.get("turn_id") or "").strip():
                raise LedgerCorruptionError(f"Invalid turn ledger record at line {line_no}")
            records.append(record)
    return records


def _ensure_seen_ids_locked(path):
    global _SEEN_LEDGER_PATH, _SEEN_TURN_IDS
    resolved = str(path.resolve())
    if _SEEN_TURN_IDS is None or _SEEN_LEDGER_PATH != resolved:
        _SEEN_TURN_IDS = {str(record["turn_id"]) for record in _read_lines_locked(path)}
        _SEEN_LEDGER_PATH = resolved


def append_turn(record):
    """Append one whitelisted telemetry record. Return False for duplicate turn IDs."""
    cleaned = _sanitize_record(record)
    if not cleaned["turn_id"]:
        raise ValueError("turn_id must be non-empty")
    path = ledger_path()
    with _LEDGER_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        _ensure_seen_ids_locked(path)
        if cleaned["turn_id"] in _SEEN_TURN_IDS:
            return False
        encoded = json.dumps(cleaned, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _SEEN_TURN_IDS.add(cleaned["turn_id"])
        return True


def read_turns(*, thread_id=None):
    path = ledger_path()
    with _LEDGER_LOCK:
        records = _read_lines_locked(path)
    if thread_id is None:
        return records
    key = str(thread_id)
    return [record for record in records if str(record.get("thread_id")) == key]


def _new_token_summary():
    return {name: {"sum": 0, "observed_turns": 0} for name in TOKEN_FIELDS}


def _add_record_to_summary(summary, record):
    summary["turn_count"] += 1
    tokens = record.get("tokens") or {}
    for name in TOKEN_FIELDS:
        value = tokens.get(name)
        if value is None:
            continue
        summary["tokens"][name]["sum"] += int(value)
        summary["tokens"][name]["observed_turns"] += 1
    picos = record.get("estimated_cost_picos")
    if picos is not None:
        summary["estimated_cost_picos"] += int(picos)
        summary["cost_observed_turns"] += 1


def summarize_thread(thread_id):
    records = read_turns(thread_id=thread_id)
    summary = {
        "thread_id": str(thread_id),
        "turn_count": 0,
        "tokens": _new_token_summary(),
        "estimated_cost_picos": 0,
        "estimated_cost_usd": 0.0,
        "cost_observed_turns": 0,
        "by_model": {},
    }
    for record in records:
        _add_record_to_summary(summary, record)
        model_key = (
            record.get("canonical_model_id")
            or record.get("observed_model_id")
            or record.get("requested_model_id")
            or "unknown"
        )
        model_summary = summary["by_model"].setdefault(
            str(model_key),
            {
                "provider": record.get("provider") or "unknown",
                "turn_count": 0,
                "tokens": _new_token_summary(),
                "estimated_cost_picos": 0,
                "estimated_cost_usd": 0.0,
                "cost_observed_turns": 0,
            },
        )
        _add_record_to_summary(model_summary, record)

    summary["estimated_cost_usd"] = picos_to_usd(summary["estimated_cost_picos"])
    for model_summary in summary["by_model"].values():
        model_summary["estimated_cost_usd"] = picos_to_usd(model_summary["estimated_cost_picos"])
    return summary
