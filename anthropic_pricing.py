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
    base_input = int(_obj_get(usage, "input_tokens", 0) or 0)
    cache_creation_total = int(_obj_get(usage, "cache_creation_input_tokens", 0) or 0)
    cache_read = int(_obj_get(usage, "cache_read_input_tokens", 0) or 0)
    output = int(_obj_get(usage, "output_tokens", 0) or 0)

    cache_creation = _obj_get(usage, "cache_creation", {}) or {}
    cache_5m = int(_obj_get(cache_creation, "ephemeral_5m_input_tokens", 0) or 0)
    cache_1h = int(_obj_get(cache_creation, "ephemeral_1h_input_tokens", 0) or 0)
    cache_breakdown = cache_5m + cache_1h
    cache_breakdown_complete = cache_breakdown == cache_creation_total

    notes = []
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
    complete = normalized["cache_breakdown_complete"]

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
