import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parent / "pricing" / "anthropic_registry.json"
_PROVIDER_PREFIXES = ("anthropic/",)
KNOWN_SERVER_TOOL_FIELDS = {"web_search_requests", "web_fetch_requests"}


def _obj_get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _obj_items(obj):
    if obj is None:
        return []
    if isinstance(obj, dict):
        return list(obj.items())
    data = getattr(obj, "__dict__", None)
    if isinstance(data, dict):
        return list(data.items())
    return []


def _clean_model_id(model_id):
    model_id = (model_id or "").strip()
    for prefix in _PROVIDER_PREFIXES:
        if model_id.startswith(prefix):
            return model_id[len(prefix):]
    return model_id


def looks_like_anthropic_model(model_id):
    return _clean_model_id(model_id).lower().startswith("claude-")


def load_registry():
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_anthropic_model(model_id):
    clean = _clean_model_id(model_id)
    registry = load_registry()
    for canonical, record in registry["models"].items():
        if clean == canonical or clean in record.get("aliases", []):
            result = dict(record)
            result["canonical_model_id"] = canonical
            result["requested_model_id"] = model_id
            result["verified_at"] = registry.get("verified_at")
            return result
    return None


def normalize_usage(usage, cache_ttl_hint=None):
    notes = []
    input_basis_complete = True

    raw_input = _obj_get(usage, "input_tokens", None)
    normalized_prompt = _obj_get(usage, "prompt_tokens", None)
    prompt_details = _obj_get(usage, "prompt_tokens_details", {}) or {}

    top_cache_creation = _obj_get(usage, "cache_creation_input_tokens", None)
    top_cache_read = _obj_get(usage, "cache_read_input_tokens", None)

    detail_cache_read = _obj_get(prompt_details, "cached_tokens", None)
    detail_cache_creation = _obj_get(prompt_details, "cache_creation_tokens", None)
    if detail_cache_creation is None:
        detail_cache_creation = _obj_get(prompt_details, "cache_write_tokens", None)

    cache_creation_total = int(
        (top_cache_creation if top_cache_creation is not None else detail_cache_creation) or 0
    )
    cache_read = int((top_cache_read if top_cache_read is not None else detail_cache_read) or 0)

    if raw_input is not None:
        # Anthropic-native semantics: input_tokens is the uncached remainder only.
        base_input = int(raw_input or 0)
        input_basis = "anthropic_raw"
    elif normalized_prompt is not None:
        prompt_total = int(normalized_prompt or 0)
        text_tokens = _obj_get(prompt_details, "text_tokens", None)
        if text_tokens is not None:
            base_input = int(text_tokens or 0)
            input_basis = "litellm_text_tokens"
        elif detail_cache_read is not None or detail_cache_creation is not None:
            # OpenAI-compatible normalized semantics normally include cache categories
            # inside prompt_tokens. Subtract only categories actually represented in
            # prompt_tokens_details; top-level Anthropic cache-create fields are not
            # assumed to be included in prompt_tokens.
            included_cache_read = int(detail_cache_read or 0)
            included_cache_creation = int(detail_cache_creation or 0)
            if included_cache_read > prompt_total or included_cache_creation > prompt_total:
                input_basis_complete = False
                notes.append("Normalized cache detail exceeds prompt_tokens; input-token basis is inconsistent.")
            base_input = max(0, prompt_total - included_cache_read - included_cache_creation)
            input_basis = "litellm_prompt_includes_cache_details"

            if top_cache_read is not None and int(top_cache_read or 0) != included_cache_read:
                input_basis_complete = False
                notes.append("Top-level and nested cache-read token counts disagree.")
            if (
                top_cache_creation is not None
                and detail_cache_creation is not None
                and int(top_cache_creation or 0) != included_cache_creation
            ):
                input_basis_complete = False
                notes.append("Top-level and nested cache-write token counts disagree.")
        elif cache_read:
            # LiteLLM versions have differed on whether normalized prompt_tokens
            # includes Anthropic cache reads. Without a nested cached-token field or
            # raw input_tokens, choosing either basis could silently over/under-count.
            base_input = prompt_total
            input_basis_complete = False
            input_basis = "litellm_ambiguous_cache_basis"
            notes.append(
                "Normalized prompt_tokens included a top-level cache-read count without enough detail to determine whether cached tokens are already included."
            )
        else:
            # Cache-creation-only Anthropic LiteLLM responses historically expose
            # prompt_tokens as the uncached remainder and cache_creation separately.
            base_input = prompt_total
            input_basis = "litellm_prompt_uncached_or_no_cache"
    else:
        base_input = 0
        input_basis = "missing_input_counter"
        input_basis_complete = False
        notes.append("Neither input_tokens nor prompt_tokens was available; input usage cannot be reconstructed safely.")

    raw_output = _obj_get(usage, "output_tokens", None)
    normalized_completion = _obj_get(usage, "completion_tokens", None)
    if raw_output is not None:
        output = int(raw_output or 0)
    elif normalized_completion is not None:
        output = int(normalized_completion or 0)
    else:
        output = 0
        notes.append("Neither output_tokens nor completion_tokens was available.")
        input_basis_complete = False

    cache_creation = _obj_get(usage, "cache_creation", {}) or {}
    cache_5m = int(_obj_get(cache_creation, "ephemeral_5m_input_tokens", 0) or 0)
    cache_1h = int(_obj_get(cache_creation, "ephemeral_1h_input_tokens", 0) or 0)
    cache_breakdown = cache_5m + cache_1h
    cache_breakdown_complete = cache_breakdown == cache_creation_total

    if cache_breakdown > cache_creation_total:
        cache_breakdown_complete = False
        notes.append("Cache TTL breakdown exceeds cache_creation_input_tokens.")
    elif cache_breakdown < cache_creation_total:
        remainder = cache_creation_total - cache_breakdown
        if cache_ttl_hint == "5m":
            cache_5m += remainder
            cache_breakdown_complete = True
        elif cache_ttl_hint == "1h":
            cache_1h += remainder
            cache_breakdown_complete = True
        elif remainder:
            cache_breakdown_complete = False
            notes.append("Cache creation tokens were reported without a complete 5m/1h TTL breakdown.")

    output_details = _obj_get(usage, "output_tokens_details", {}) or {}
    if not output_details:
        output_details = _obj_get(usage, "completion_tokens_details", {}) or {}
    thinking = int(_obj_get(output_details, "thinking_tokens", 0) or 0)

    server_tools = _obj_get(usage, "server_tool_use", {}) or {}
    web_search = int(_obj_get(server_tools, "web_search_requests", 0) or 0)
    web_fetch = int(_obj_get(server_tools, "web_fetch_requests", 0) or 0)
    unknown_server_tools = {}
    for key, value in _obj_items(server_tools):
        if key in KNOWN_SERVER_TOOL_FIELDS or key.startswith("_"):
            continue
        try:
            numeric = int(value or 0)
        except Exception:
            numeric = 0
        if numeric:
            unknown_server_tools[key] = numeric

    return {
        "input_tokens": base_input,
        "input_basis": input_basis,
        "input_basis_complete": input_basis_complete,
        "cache_creation_input_tokens": cache_creation_total,
        "cache_write_5m_tokens": cache_5m,
        "cache_write_1h_tokens": cache_1h,
        "cache_read_input_tokens": cache_read,
        "total_input_tokens": base_input + cache_creation_total + cache_read,
        "output_tokens": output,
        "thinking_tokens": thinking,
        "inference_geo": _obj_get(usage, "inference_geo", None),
        "service_tier": _obj_get(usage, "service_tier", None),
        "speed": _obj_get(usage, "speed", None),
        "web_search_requests": web_search,
        "web_fetch_requests": web_fetch,
        "unknown_server_tools": unknown_server_tools,
        "cache_breakdown_complete": cache_breakdown_complete,
        "normalization_notes": notes,
    }


def calculate_anthropic_cost(
    model_id,
    usage,
    *,
    processing_mode="standard",
    cache_ttl_hint=None,
    inference_geo_hint=None,
    service_tier_hint=None,
    speed_hint=None,
    platform="claude_api",
):
    registry = load_registry()
    record = resolve_anthropic_model(model_id)
    normalized = normalize_usage(usage, cache_ttl_hint=cache_ttl_hint)

    if record is None:
        return {
            "provider": "anthropic",
            "requested_model_id": model_id,
            "canonical_model_id": None,
            "total_cost_usd": None,
            "known_list_equivalent_usd": None,
            "complete": False,
            "notes": ["Unknown Anthropic model: no price was guessed."],
            "usage": normalized,
        }

    notes = list(normalized["normalization_notes"])
    complete = normalized["cache_breakdown_complete"] and normalized["input_basis_complete"]

    if platform != "claude_api":
        complete = False
        notes.append(
            "This registry covers first-party Claude API public list pricing; partner/marketplace invoice pricing was not inferred."
        )

    actual_tier = normalized["service_tier"]
    requested_tier = service_tier_hint
    if actual_tier and str(actual_tier).lower() == "priority":
        complete = False
        notes.append(
            "Priority Tier is commitment/contract based; public list rates are only a list-equivalent reference."
        )
    elif not actual_tier and requested_tier and str(requested_tier).lower() == "auto":
        complete = False
        notes.append(
            "Requested service_tier=auto but response usage did not reveal whether Priority or Standard capacity was used."
        )

    observed_speed = normalized["speed"]
    if observed_speed:
        speed = str(observed_speed).lower()
    elif speed_hint and str(speed_hint).lower() == "fast":
        speed = "fast-unresolved"
        complete = False
        notes.append(
            "Fast speed was requested but usage.speed was not returned, so the applied speed/rate cannot be inferred safely."
        )
    else:
        speed = "standard"

    if speed == "fast":
        rates = record.get("fast_rates")
        if not rates:
            complete = False
            notes.append("Response reports fast mode for a model without verified fast-mode rates.")
            rates = record["rates"]
    else:
        rates = record["rates"]

    geo = normalized["inference_geo"] or inference_geo_hint
    geo_multiplier = 1.0
    if record.get("supports_inference_geo"):
        if geo is None:
            complete = False
            notes.append(
                "Inference geography was not resolved. Workspace defaults can affect whether the 1.1x US-only multiplier applies."
            )
        else:
            geo_name = str(geo).lower()
            if geo_name == "us":
                geo_multiplier = float(record.get("inference_geo_us_multiplier") or 1.1)
            elif geo_name == "global":
                geo_multiplier = 1.0
            else:
                complete = False
                notes.append(f"Unrecognized inference geography: {geo}.")
    elif geo and str(geo).lower() == "us":
        complete = False
        notes.append("US-only inference was reported for a model whose first-party geo pricing is not registered.")

    mode = (processing_mode or "standard").lower()
    if mode == "batch":
        if speed == "fast":
            complete = False
            notes.append("Fast mode and Batch are not a supported pricing combination.")
        mode_multiplier = float(record.get("batch_multiplier", 0.5))
    elif mode == "standard":
        mode_multiplier = 1.0
    else:
        complete = False
        notes.append(f"Unsupported processing mode: {processing_mode}.")
        mode_multiplier = 1.0

    categories = (
        ("base_input", "input_tokens"),
        ("cache_write_5m", "cache_write_5m_tokens"),
        ("cache_write_1h", "cache_write_1h_tokens"),
        ("cache_read", "cache_read_input_tokens"),
        ("output", "output_tokens"),
    )
    components = {}
    subtotal = 0.0
    for rate_key, usage_key in categories:
        tokens = normalized[usage_key]
        rate = rates.get(rate_key)
        if tokens and rate is None:
            complete = False
            notes.append(f"{rate_key} usage was reported but no verified rate is registered.")
            components[rate_key] = None
            continue
        cost = (tokens / 1_000_000.0) * float(rate or 0.0) * geo_multiplier * mode_multiplier
        components[rate_key] = round(cost, 12)
        subtotal += cost

    tool_rates = registry.get("tool_rates", {})
    web_search_cost = normalized["web_search_requests"] * float(tool_rates.get("web_search_request_usd", 0.0))
    web_fetch_cost = normalized["web_fetch_requests"] * float(tool_rates.get("web_fetch_request_usd", 0.0))
    components["web_search"] = round(web_search_cost, 12)
    components["web_fetch"] = round(web_fetch_cost, 12)
    subtotal += web_search_cost + web_fetch_cost

    if normalized["unknown_server_tools"]:
        complete = False
        notes.append(
            "Unpriced Anthropic server-tool activity was reported: "
            + ", ".join(sorted(normalized["unknown_server_tools"].keys()))
            + "."
        )

    known_total = round(subtotal, 12)

    return {
        "provider": "anthropic",
        "requested_model_id": model_id,
        "canonical_model_id": record["canonical_model_id"],
        "verified_at": record.get("verified_at"),
        "platform": platform,
        "processing_mode": mode,
        "service_tier": actual_tier or requested_tier or "unspecified",
        "speed": speed,
        "inference_geo": geo,
        "geo_multiplier": geo_multiplier,
        "processing_multiplier": mode_multiplier,
        "components_usd": components,
        "known_list_equivalent_usd": known_total,
        "total_cost_usd": known_total if complete else None,
        "complete": complete,
        "notes": notes,
        "usage": normalized,
    }


def calculate_anthropic_response_cost(
    request_model_id,
    completion_response,
    *,
    processing_mode="standard",
    cache_ttl_hint=None,
    inference_geo_hint=None,
    service_tier_hint=None,
    speed_hint=None,
    platform="claude_api",
):
    usage = _obj_get(completion_response, "usage", None)
    response_model = _obj_get(completion_response, "model", None) or request_model_id
    if usage is None:
        return {
            "provider": "anthropic",
            "requested_model_id": request_model_id,
            "canonical_model_id": None,
            "total_cost_usd": None,
            "known_list_equivalent_usd": None,
            "complete": False,
            "notes": ["No Anthropic response usage telemetry was available; no price was guessed."],
            "usage": normalize_usage({}),
        }

    result = calculate_anthropic_cost(
        response_model,
        usage,
        processing_mode=processing_mode,
        cache_ttl_hint=cache_ttl_hint,
        inference_geo_hint=inference_geo_hint,
        service_tier_hint=service_tier_hint,
        speed_hint=speed_hint,
        platform=platform,
    )
    result["response_model_id"] = response_model
    return result
