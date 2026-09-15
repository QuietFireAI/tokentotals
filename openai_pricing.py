import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parent / "pricing" / "openai_registry.json"
_PROVIDER_PREFIXES = ("openai/",)


def _obj_get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _clean_model_id(model_id):
    model_id = (model_id or "").strip()
    for prefix in _PROVIDER_PREFIXES:
        if model_id.startswith(prefix):
            return model_id[len(prefix):]
    return model_id


def looks_like_openai_model(model_id):
    clean = _clean_model_id(model_id).lower()
    return clean.startswith(("gpt-", "o1", "o3", "o4", "chatgpt-", "computer-use-"))


def load_registry():
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_openai_model(model_id):
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


def normalize_usage(usage):
    input_total = _obj_get(usage, "input_tokens")
    if input_total is None:
        input_total = _obj_get(usage, "prompt_tokens", 0)

    output_total = _obj_get(usage, "output_tokens")
    if output_total is None:
        output_total = _obj_get(usage, "completion_tokens", 0)

    input_details = _obj_get(usage, "input_tokens_details")
    if input_details is None:
        input_details = _obj_get(usage, "prompt_tokens_details", {})

    output_details = _obj_get(usage, "output_tokens_details")
    if output_details is None:
        output_details = _obj_get(usage, "completion_tokens_details", {})

    cached = int(_obj_get(input_details, "cached_tokens", 0) or 0)
    cache_write = int(_obj_get(input_details, "cache_write_tokens", 0) or 0)
    input_total = int(input_total or 0)
    output_total = int(output_total or 0)
    reasoning = int(_obj_get(output_details, "reasoning_tokens", 0) or 0)
    audio_in = int(_obj_get(input_details, "audio_tokens", 0) or 0)
    audio_out = int(_obj_get(output_details, "audio_tokens", 0) or 0)

    overlap = cached + cache_write > input_total
    uncached = max(0, input_total - cached - cache_write)

    return {
        "input_tokens": input_total,
        "uncached_input_tokens": uncached,
        "cached_input_tokens": cached,
        "cache_write_tokens": cache_write,
        "output_tokens": output_total,
        "reasoning_tokens": reasoning,
        "audio_input_tokens": audio_in,
        "audio_output_tokens": audio_out,
        "usage_breakdown_overlap": overlap,
    }


def _tier_multiplier(record, service_tier):
    tier = (service_tier or "default").lower()
    tiers = record.get("service_tiers", {})
    if tier not in tiers:
        return None, tier
    return float(tiers[tier]), tier


def calculate_openai_cost(model_id, usage, service_tier=None):
    record = resolve_openai_model(model_id)
    normalized = normalize_usage(usage)

    if record is None:
        return {
            "provider": "openai",
            "requested_model_id": model_id,
            "canonical_model_id": None,
            "total_cost_usd": None,
            "complete": False,
            "notes": ["Unknown OpenAI model: no price was guessed."],
            "usage": normalized,
        }

    notes = []
    complete = True
    tier_multiplier, tier = _tier_multiplier(record, service_tier)
    if tier_multiplier is None:
        complete = False
        notes.append(f"Unsupported or unverified service tier: {tier}.")
        tier_multiplier = 1.0

    if normalized["usage_breakdown_overlap"]:
        complete = False
        notes.append(
            "Cached + cache-write tokens exceed total input tokens; usage categories overlap unexpectedly."
        )

    if normalized["audio_input_tokens"] or normalized["audio_output_tokens"]:
        complete = False
        notes.append("Audio-token pricing is not represented by this text-model registry.")

    rates = record["rates"]
    long_rules = record.get("long_context")
    input_mult = cached_mult = write_mult = output_mult = 1.0
    long_context_applied = False

    if long_rules and normalized["input_tokens"] > int(long_rules["threshold_input_tokens"]):
        long_context_applied = True
        input_mult = float(long_rules.get("input_multiplier", 1.0))
        cached_mult = float(long_rules.get("cached_input_multiplier", input_mult))
        write_mult = float(long_rules.get("cache_write_multiplier", input_mult))
        output_mult = float(long_rules.get("output_multiplier", 1.0))

    components = {}
    categories = (
        ("input", "uncached_input_tokens", input_mult),
        ("cached_input", "cached_input_tokens", cached_mult),
        ("cache_write", "cache_write_tokens", write_mult),
        ("output", "output_tokens", output_mult),
    )

    subtotal = 0.0
    for rate_key, token_key, category_mult in categories:
        tokens = normalized[token_key]
        rate = rates.get(rate_key)

        if tokens and rate is None:
            complete = False
            notes.append(f"{rate_key} tokens were reported but no verified rate is registered.")
            components[rate_key] = None
            continue

        cost = (
            (tokens / 1_000_000.0)
            * float(rate or 0.0)
            * category_mult
            * tier_multiplier
        )
        components[rate_key] = round(cost, 12)
        subtotal += cost

    total = round(subtotal, 12) if complete else None

    return {
        "provider": "openai",
        "requested_model_id": model_id,
        "canonical_model_id": record["canonical_model_id"],
        "verified_at": record.get("verified_at"),
        "service_tier": tier,
        "service_tier_multiplier": tier_multiplier,
        "long_context_applied": long_context_applied,
        "components_usd": components,
        "total_cost_usd": total,
        "complete": complete,
        "notes": notes,
        "usage": normalized,
    }


def calculate_openai_response_cost(request_model_id, completion_response, request_service_tier=None):
    response_model = _obj_get(completion_response, "model", None) or request_model_id
    usage = _obj_get(completion_response, "usage", None)
    actual_service_tier = _obj_get(completion_response, "service_tier", None)

    if usage is None:
        return {
            "provider": "openai",
            "requested_model_id": request_model_id,
            "canonical_model_id": None,
            "total_cost_usd": None,
            "complete": False,
            "notes": ["No response usage telemetry was available; no price was guessed."],
            "usage": normalize_usage({}),
        }

    tier = actual_service_tier or request_service_tier
    result = calculate_openai_cost(response_model, usage, service_tier=tier)
    result["response_model_id"] = response_model
    result["service_tier_source"] = "response" if actual_service_tier else "request_or_default"

    if actual_service_tier is None and (request_service_tier is None or request_service_tier == "auto"):
        result["notes"] = list(result.get("notes", [])) + [
            "Resolved service tier was not returned; default pricing is assumed unless project settings route auto elsewhere."
        ]

    return result


def estimate_openai_input_cost(model_id, estimated_input_tokens, service_tier=None):
    usage = {
        "input_tokens": int(max(0, estimated_input_tokens or 0)),
        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
        "output_tokens": 0,
        "output_tokens_details": {"reasoning_tokens": 0},
    }
    result = calculate_openai_cost(model_id, usage, service_tier=service_tier)
    result["estimate_only"] = True
    result["notes"] = list(result.get("notes", [])) + [
        "Pre-flight estimate assumes all input is uncached and excludes output/tool charges."
    ]
    return result
