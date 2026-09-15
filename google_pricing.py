import json
from datetime import date
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parent / "pricing" / "google_registry.json"
_PROVIDER_PREFIXES = ("gemini/", "google/", "vertex_ai/", "vertex-ai/")
_MODALITY_MAP = {
    "TEXT": "text",
    "DOCUMENT": "text",
    "IMAGE": "image",
    "VIDEO": "video",
    "AUDIO": "audio",
}


def _obj_get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _clean_model_id(model_id):
    model_id = (model_id or "").strip()
    lower = model_id.lower()
    for prefix in _PROVIDER_PREFIXES:
        if lower.startswith(prefix):
            return model_id[len(prefix):]
    if lower.startswith("models/"):
        return model_id[7:]
    return model_id


def looks_like_google_model(model_id):
    return _clean_model_id(model_id).lower().startswith("gemini-")


def infer_google_platform(model_id):
    lower = (model_id or "").lower()
    if lower.startswith(("vertex_ai/", "vertex-ai/")):
        return "vertex_ai"
    return "gemini_developer_api"


def load_registry():
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _merge_inherited(registry, canonical, seen=None):
    seen = set(seen or ())
    if canonical in seen:
        raise ValueError(f"Circular Google pricing registry inheritance at {canonical}")
    seen.add(canonical)
    record = dict(registry["models"][canonical])
    parent = record.pop("inherits", None)
    if parent:
        base = _merge_inherited(registry, parent, seen)
        base.update(record)
        record = base
    return record


def resolve_google_model(model_id):
    clean = _clean_model_id(model_id)
    registry = load_registry()
    for canonical, raw in registry["models"].items():
        if clean == canonical or clean in raw.get("aliases", []):
            record = _merge_inherited(registry, canonical)
            record["canonical_model_id"] = canonical
            record["requested_model_id"] = model_id
            record["verified_at"] = registry.get("verified_at")
            return record
    return None


def _parse_date(value):
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _active_modes(record, as_of=None):
    as_of = _parse_date(as_of) or date.today()
    if "pricing_periods" not in record:
        return record.get("modes", {}), None
    for period in record.get("pricing_periods", []):
        start = _parse_date(period.get("valid_from"))
        end = _parse_date(period.get("valid_through"))
        if start and as_of < start:
            continue
        if end and as_of > end:
            continue
        return period.get("modes", {}), {
            "valid_from": period.get("valid_from"),
            "valid_through": period.get("valid_through"),
        }
    return {}, None


def _detail_tokens(details):
    out = {"text": 0, "image": 0, "video": 0, "audio": 0}
    found = False
    for detail in details or []:
        modality = str(_obj_get(detail, "modality", "")).upper()
        key = _MODALITY_MAP.get(modality)
        if not key:
            continue
        count = _obj_get(detail, "tokenCount", None)
        if count is None:
            count = _obj_get(detail, "token_count", 0)
        try:
            value = int(count or 0)
        except Exception:
            value = 0
        out[key] += value
        found = True
    return out, found


def _normalized_detail_tokens(details):
    return {
        "text": int(_obj_get(details, "text_tokens", 0) or 0),
        "image": int(_obj_get(details, "image_tokens", 0) or 0),
        "video": int(_obj_get(details, "video_tokens", 0) or 0),
        "audio": int(_obj_get(details, "audio_tokens", 0) or 0),
    }


def _sum_modalities(modalities):
    return sum(int(v or 0) for v in modalities.values())


def _find_grounding_metadata(response):
    candidates = _obj_get(response, "candidates", None)
    if candidates is None:
        candidates = _obj_get(response, "choices", None)
    found = []
    for candidate in candidates or []:
        metadata = _obj_get(candidate, "groundingMetadata", None)
        if metadata is None:
            metadata = _obj_get(candidate, "grounding_metadata", None)
        if metadata is None:
            message = _obj_get(candidate, "message", None)
            provider = _obj_get(message, "provider_specific_fields", None)
            metadata = _obj_get(provider, "grounding_metadata", None) or _obj_get(provider, "groundingMetadata", None)
        if metadata:
            found.append(metadata)
    provider_fields = _obj_get(response, "provider_specific_fields", None)
    if provider_fields:
        metadata = _obj_get(provider_fields, "grounding_metadata", None) or _obj_get(provider_fields, "groundingMetadata", None)
        if metadata:
            found.append(metadata)
    return found


def _grounding_activity(response):
    web_queries = []
    image_queries = []
    maps = False
    for metadata in _find_grounding_metadata(response):
        web_queries.extend(_obj_get(metadata, "webSearchQueries", None) or _obj_get(metadata, "web_search_queries", None) or [])
        image_queries.extend(_obj_get(metadata, "imageSearchQueries", None) or _obj_get(metadata, "image_search_queries", None) or [])
        if _obj_get(metadata, "googleMapsWidgetContextToken", None) or _obj_get(metadata, "google_maps_widget_context_token", None):
            maps = True
        for chunk in _obj_get(metadata, "groundingChunks", None) or _obj_get(metadata, "grounding_chunks", None) or []:
            if _obj_get(chunk, "maps", None):
                maps = True
    unique_search_queries = {str(q).strip() for q in [*web_queries, *image_queries] if str(q).strip()}
    return {
        "search_query_count": len(unique_search_queries),
        "maps_used": maps,
        "grounding_metadata_observed": bool(web_queries or image_queries or maps),
    }


def _raw_usage_from_response(response):
    direct = _obj_get(response, "usageMetadata", None)
    if direct is None:
        direct = _obj_get(response, "usage_metadata", None)
    if direct is not None:
        return direct
    hidden = _obj_get(response, "_hidden_params", None)
    if hidden:
        raw = _obj_get(hidden, "usageMetadata", None) or _obj_get(hidden, "usage_metadata", None)
        if raw is not None:
            return raw
    return None


def _rate_for_modality(rate_map, modality):
    if rate_map is None:
        return None
    if modality in rate_map:
        return rate_map[modality]
    return rate_map.get("default")


def _has_modality_specific_rates(rate_map):
    return bool(rate_map and any(k != "default" for k in rate_map))


def normalize_google_usage(usage, *, response=None):
    notes = []
    complete = True
    raw = usage
    raw_shape = any(_obj_get(raw, k, None) is not None for k in (
        "promptTokenCount", "cachedContentTokenCount", "candidatesTokenCount",
        "toolUsePromptTokenCount", "thoughtsTokenCount", "totalTokenCount"
    ))
    grounding = _grounding_activity(response) if response is not None else {
        "search_query_count": 0, "maps_used": False, "grounding_metadata_observed": False
    }

    if raw_shape:
        prompt_total = int(_obj_get(raw, "promptTokenCount", 0) or 0)
        cached_total = int(_obj_get(raw, "cachedContentTokenCount", 0) or 0)
        candidate = int(_obj_get(raw, "candidatesTokenCount", 0) or 0)
        response_tokens = int(_obj_get(raw, "responseTokenCount", 0) or 0)
        if response_tokens and not candidate:
            candidate = response_tokens
        thoughts = int(_obj_get(raw, "thoughtsTokenCount", 0) or 0)
        tool_use = _obj_get(raw, "toolUsePromptTokenCount", None)
        tool_use = int(tool_use or 0) if tool_use is not None else None
        total = int(_obj_get(raw, "totalTokenCount", 0) or 0)
        service_tier = _obj_get(raw, "serviceTier", None) or _obj_get(raw, "service_tier", None)

        prompt_mod, have_prompt_mod = _detail_tokens(_obj_get(raw, "promptTokensDetails", None) or [])
        cache_mod, have_cache_mod = _detail_tokens(_obj_get(raw, "cacheTokensDetails", None) or [])
        output_mod, have_output_mod = _detail_tokens(
            _obj_get(raw, "candidatesTokensDetails", None) or _obj_get(raw, "responseTokensDetails", None) or []
        )
        tool_mod, have_tool_mod = _detail_tokens(_obj_get(raw, "toolUsePromptTokensDetails", None) or [])

        if cached_total > prompt_total:
            complete = False
            notes.append("cachedContentTokenCount exceeds promptTokenCount; Google input basis is inconsistent.")
        if have_prompt_mod and _sum_modalities(prompt_mod) != prompt_total:
            complete = False
            notes.append("promptTokensDetails does not reconcile to promptTokenCount.")
        if have_cache_mod and _sum_modalities(cache_mod) != cached_total:
            complete = False
            notes.append("cacheTokensDetails does not reconcile to cachedContentTokenCount.")

        if have_prompt_mod:
            uncached_mod = dict(prompt_mod)
            if have_cache_mod:
                for key in uncached_mod:
                    uncached_mod[key] = max(0, uncached_mod[key] - cache_mod[key])
            elif cached_total:
                nonzero = [k for k, v in prompt_mod.items() if v]
                if nonzero == ["text"]:
                    cache_mod = {"text": cached_total, "image": 0, "video": 0, "audio": 0}
                    uncached_mod["text"] = max(0, uncached_mod["text"] - cached_total)
                    have_cache_mod = True
                else:
                    complete = False
                    notes.append("Cached tokens were reported without a modality breakdown for a multimodal prompt.")
        else:
            uncached_mod = {"text": max(0, prompt_total - cached_total), "image": 0, "video": 0, "audio": 0}
            cache_mod = {"text": cached_total, "image": 0, "video": 0, "audio": 0}

        if not have_output_mod:
            output_mod = {"text": candidate, "image": 0, "video": 0, "audio": 0}

        if tool_use is None:
            expected = prompt_total + candidate + thoughts
            residual = max(0, total - expected) if total else 0
            unattributed = residual
            if residual:
                complete = False
                notes.append("totalTokenCount contains tokens not attributed to prompt/candidates/thoughts; possible omitted tool-use prompt tokens.")
            tool_use = 0
        else:
            unattributed = max(0, total - (prompt_total + candidate + thoughts + tool_use)) if total else 0
            if unattributed:
                complete = False
                notes.append("totalTokenCount contains unattributed tokens beyond the documented Google usage buckets.")

        search_grounded = grounding["search_query_count"] > 0
        billable_tool_use = 0 if search_grounded else tool_use
        if have_tool_mod and _sum_modalities(tool_mod) != tool_use:
            complete = False
            notes.append("toolUsePromptTokensDetails does not reconcile to toolUsePromptTokenCount.")

        return {
            "source_shape": "google_raw",
            "prompt_total_tokens": prompt_total,
            "uncached_input_modalities": uncached_mod,
            "cached_input_modalities": cache_mod,
            "candidate_output_modalities": output_mod,
            "cached_tokens": cached_total,
            "tool_use_prompt_tokens": tool_use,
            "tool_use_prompt_modalities": tool_mod if have_tool_mod else None,
            "billable_tool_use_prompt_tokens": billable_tool_use,
            "tool_use_separate_for_billing": True,
            "thinking_tokens": thoughts,
            "output_tokens_including_thinking": candidate + thoughts,
            "total_tokens": total,
            "unattributed_tokens": unattributed,
            "service_tier": service_tier,
            "grounding": grounding,
            "normalization_complete": complete,
            "normalization_notes": notes,
        }

    prompt = _obj_get(raw, "prompt_tokens", None)
    completion = _obj_get(raw, "completion_tokens", None)
    total = _obj_get(raw, "total_tokens", None)
    if prompt is None and completion is None:
        return {
            "source_shape": "missing",
            "prompt_total_tokens": 0,
            "uncached_input_modalities": {"text": 0, "image": 0, "video": 0, "audio": 0},
            "cached_input_modalities": {"text": 0, "image": 0, "video": 0, "audio": 0},
            "candidate_output_modalities": {"text": 0, "image": 0, "video": 0, "audio": 0},
            "cached_tokens": 0,
            "tool_use_prompt_tokens": 0,
            "tool_use_prompt_modalities": None,
            "billable_tool_use_prompt_tokens": 0,
            "tool_use_separate_for_billing": False,
            "thinking_tokens": 0,
            "output_tokens_including_thinking": 0,
            "total_tokens": 0,
            "unattributed_tokens": 0,
            "service_tier": None,
            "grounding": grounding,
            "normalization_complete": False,
            "normalization_notes": ["No recognizable Google or LiteLLM usage telemetry was available."],
        }

    prompt = int(prompt or 0)
    completion = int(completion or 0)
    total = int(total or 0)
    prompt_details = _obj_get(raw, "prompt_tokens_details", {}) or {}
    completion_details = _obj_get(raw, "completion_tokens_details", {}) or {}
    cached = int(_obj_get(prompt_details, "cached_tokens", None) or _obj_get(raw, "cache_read_input_tokens", 0) or 0)
    tool_use = int(_obj_get(prompt_details, "tool_use_tokens", 0) or 0)
    prompt_mod = _normalized_detail_tokens(prompt_details)
    output_mod = _normalized_detail_tokens(completion_details)
    reasoning = int(_obj_get(completion_details, "reasoning_tokens", None) or _obj_get(raw, "reasoning_tokens", 0) or 0)

    detail_uncached = _sum_modalities(prompt_mod)
    if detail_uncached:
        uncached_mod = prompt_mod
        tool_use_separate_for_billing = bool(tool_use)
        reconstructed = detail_uncached + cached + tool_use
        if prompt != reconstructed:
            delta = prompt - reconstructed
            if delta > 0:
                complete = False
                notes.append("LiteLLM prompt token total contains tokens not represented in prompt token details.")
            elif delta < 0:
                complete = False
                notes.append("LiteLLM prompt token details exceed prompt_tokens.")
    else:
        base_uncached = max(0, prompt - cached)
        uncached_mod = {"text": base_uncached, "image": 0, "video": 0, "audio": 0}
        tool_use_separate_for_billing = False

    cache_mod = {"text": cached, "image": 0, "video": 0, "audio": 0}
    if _sum_modalities(output_mod) == 0:
        output_mod = {"text": completion, "image": 0, "video": 0, "audio": 0}

    residual = max(0, total - (prompt + completion)) if total else 0
    if residual:
        complete = False
        notes.append("LiteLLM total_tokens exceeds prompt_tokens + completion_tokens; possible provider token category was dropped during normalization.")

    service_tier = _obj_get(raw, "service_tier", None)
    return {
        "source_shape": "litellm_normalized",
        "prompt_total_tokens": prompt,
        "uncached_input_modalities": uncached_mod,
        "cached_input_modalities": cache_mod,
        "candidate_output_modalities": output_mod,
        "cached_tokens": cached,
        "tool_use_prompt_tokens": tool_use,
        "tool_use_prompt_modalities": None,
        "billable_tool_use_prompt_tokens": tool_use,
        "tool_use_separate_for_billing": tool_use_separate_for_billing,
        "thinking_tokens": reasoning,
        "output_tokens_including_thinking": completion,
        "total_tokens": total,
        "unattributed_tokens": residual,
        "service_tier": service_tier,
        "grounding": grounding,
        "normalization_complete": complete,
        "normalization_notes": notes,
    }


def _mode_name(observed_tier=None, requested_tier=None, processing_mode="standard"):
    if (processing_mode or "standard").lower() == "batch":
        return "batch", True, None
    observed = str(observed_tier or "").lower()
    requested = str(requested_tier or "").lower()
    if observed in {"standard", "flex", "priority"}:
        return observed, True, None
    if observed:
        return "standard", False, f"Unrecognized observed Google service tier: {observed_tier}."
    if requested == "priority":
        return "priority", False, "Priority was requested but the response did not expose the applied tier; graceful downgrade to Standard is possible."
    if requested in {"flex", "standard", "default"}:
        return "standard" if requested in {"standard", "default"} else "flex", True, None
    if requested:
        return "standard", False, f"Unrecognized requested Google service tier: {requested_tier}."
    return "standard", True, None


def _selected_rates(record, mode, prompt_threshold_tokens, as_of=None):
    modes, period = _active_modes(record, as_of=as_of)
    mode_rates = modes.get(mode)
    if not mode_rates:
        return None, period, False
    threshold = record.get("long_context_threshold_tokens")
    long_context = bool(threshold and prompt_threshold_tokens > int(threshold))
    if long_context and mode_rates.get("long_context"):
        merged = dict(mode_rates)
        merged.update(mode_rates["long_context"])
        return merged, period, True
    return mode_rates, period, long_context


def _modality_cost(tokens_by_modality, rate_map, notes, complete_ref, label):
    total = 0.0
    components = {}
    for modality, tokens in tokens_by_modality.items():
        tokens = int(tokens or 0)
        if not tokens:
            continue
        rate = _rate_for_modality(rate_map, modality)
        if rate is None:
            complete_ref[0] = False
            notes.append(f"{label} {modality} tokens were observed but no verified rate is registered.")
            components[modality] = None
            continue
        cost = tokens / 1_000_000.0 * float(rate)
        components[modality] = round(cost, 12)
        total += cost
    return total, components


def calculate_google_cost(model_id, usage, *, response=None, request_service_tier=None, processing_mode="standard", platform=None, request_feature_hints=None, as_of=None):
    registry = load_registry()
    record = resolve_google_model(model_id)
    normalized = normalize_google_usage(usage, response=response)
    platform = platform or infer_google_platform(model_id)

    if record is None:
        return {"provider": "google", "requested_model_id": model_id, "canonical_model_id": None, "total_cost_usd": None, "known_list_equivalent_usd": None, "complete": False, "notes": ["Unknown Google/Gemini model: no price was guessed."], "usage": normalized}

    notes = list(normalized["normalization_notes"])
    complete_ref = [bool(normalized["normalization_complete"])]
    if platform != "gemini_developer_api":
        complete_ref[0] = False
        notes.append("The Google registry covers Gemini Developer API public paid-tier pricing; Vertex AI, provisioned throughput, marketplace, or contract pricing was not inferred.")

    mode, tier_complete, tier_note = _mode_name(normalized.get("service_tier"), request_service_tier, processing_mode)
    if not tier_complete:
        complete_ref[0] = False
        notes.append(tier_note)

    prompt_threshold_tokens = normalized["prompt_total_tokens"]
    if normalized["tool_use_prompt_tokens"] and record.get("long_context_threshold_tokens"):
        complete_ref[0] = False
        notes.append("Long-context pricing is model-call dependent, but aggregate tool-use prompt tokens do not reveal each internal prompt's threshold basis.")

    rates, period, long_context = _selected_rates(record, mode, prompt_threshold_tokens, as_of=as_of)
    if rates is None:
        return {"provider": "google", "requested_model_id": model_id, "canonical_model_id": record["canonical_model_id"], "verified_at": record.get("verified_at"), "platform": platform, "processing_mode": mode, "total_cost_usd": None, "known_list_equivalent_usd": None, "complete": False, "notes": notes + ["No verified Google rate period/mode applies to this calculation date."], "usage": normalized}

    if normalized["source_shape"] == "google_raw" and normalized["cached_tokens"] and _has_modality_specific_rates(rates.get("cached_input")):
        if _sum_modalities(normalized["cached_input_modalities"]) != normalized["cached_tokens"]:
            complete_ref[0] = False
            notes.append("Cached-token modalities are required because this model has modality-specific cache rates.")

    subtotal = 0.0
    components = {}
    value, parts = _modality_cost(normalized["uncached_input_modalities"], rates.get("input"), notes, complete_ref, "Input")
    subtotal += value
    components["uncached_input"] = parts
    value, parts = _modality_cost(normalized["cached_input_modalities"], rates.get("cached_input"), notes, complete_ref, "Cached input")
    subtotal += value
    components["cached_input"] = parts

    if normalized["billable_tool_use_prompt_tokens"] and normalized.get("tool_use_separate_for_billing", False):
        tool_modalities = normalized.get("tool_use_prompt_modalities")
        if tool_modalities:
            value, parts = _modality_cost(tool_modalities, rates.get("input"), notes, complete_ref, "Tool-use input")
        else:
            rate = _rate_for_modality(rates.get("input"), "text")
            if rate is None:
                complete_ref[0] = False
                notes.append("Tool-use prompt tokens were observed but no default input rate is registered.")
                value, parts = 0.0, {"text": None}
            else:
                value = normalized["billable_tool_use_prompt_tokens"] / 1_000_000.0 * float(rate)
                parts = {"text": round(value, 12)}
        subtotal += value
        components["tool_use_input"] = parts

    output_tokens = normalized["output_tokens_including_thinking"]
    output_mod = dict(normalized["candidate_output_modalities"])
    candidate_sum = _sum_modalities(output_mod)
    if normalized["source_shape"] == "google_raw" and normalized["thinking_tokens"]:
        output_mod["text"] = output_mod.get("text", 0) + normalized["thinking_tokens"]
    elif normalized["source_shape"] == "litellm_normalized" and candidate_sum != output_tokens:
        if candidate_sum < output_tokens:
            output_mod["text"] = output_mod.get("text", 0) + (output_tokens - candidate_sum)
        elif candidate_sum > output_tokens:
            complete_ref[0] = False
            notes.append("Completion token modality details exceed completion_tokens.")

    value, parts = _modality_cost(output_mod, rates.get("output"), notes, complete_ref, "Output")
    subtotal += value
    components["output_including_thinking"] = parts

    if normalized["unattributed_tokens"]:
        fallback_rate = _rate_for_modality(rates.get("input"), "text")
        if fallback_rate is not None:
            unattributed_cost = normalized["unattributed_tokens"] / 1_000_000.0 * float(fallback_rate)
            components["unattributed_input_equivalent"] = round(unattributed_cost, 12)
            subtotal += unattributed_cost
        complete_ref[0] = False

    grounding = normalized["grounding"]
    tool_rates = registry.get("tool_pricing", {})
    search_count = grounding["search_query_count"]
    if search_count:
        if float(record.get("generation", 0)) >= 3:
            search_equivalent = search_count * float(tool_rates["gemini_3_search_request_usd"])
        else:
            search_equivalent = float(tool_rates["gemini_2_5_search_grounded_prompt_usd"])
        components["search_grounding_list_equivalent"] = round(search_equivalent, 12)
        subtotal += search_equivalent
        complete_ref[0] = False
        notes.append("Google Search grounding was observed. The public paid overage rate is represented, but project-level free allowance remaining is not observable from the response.")

    if grounding["maps_used"]:
        maps_equivalent = float(tool_rates["maps_grounded_prompt_usd"])
        components["maps_grounding_list_equivalent"] = round(maps_equivalent, 12)
        subtotal += maps_equivalent
        complete_ref[0] = False
        notes.append("Google Maps grounding was observed. The public paid overage rate is represented, but project-level free allowance remaining is not observable from the response.")

    hints = {str(x).lower() for x in (request_feature_hints or [])}
    if hints & {"file_search", "filesearch"}:
        complete_ref[0] = False
        notes.append("File Search can add embedding charges that are not reconstructable from ordinary response token telemetry.")
    if hints & {"google_search", "googlesearch", "google_search_retrieval"} and not grounding["grounding_metadata_observed"]:
        complete_ref[0] = False
        notes.append("Google Search was enabled/requested but no grounding execution metadata survived into the response.")
    if hints & {"google_maps", "googlemaps"} and not grounding["maps_used"]:
        complete_ref[0] = False
        notes.append("Google Maps was enabled/requested but no billable execution counter was observable.")
    if hints & {"url_context", "urlcontext"} and not normalized["tool_use_prompt_tokens"]:
        complete_ref[0] = False
        notes.append("URL context was enabled/requested but tool-use input tokens were not observable.")

    known_total = round(subtotal, 12)
    return {
        "provider": "google",
        "requested_model_id": model_id,
        "canonical_model_id": record["canonical_model_id"],
        "verified_at": record.get("verified_at"),
        "platform": platform,
        "processing_mode": mode,
        "price_period": period,
        "long_context": long_context,
        "components_usd": components,
        "known_list_equivalent_usd": known_total,
        "total_cost_usd": known_total if complete_ref[0] else None,
        "complete": complete_ref[0],
        "notes": notes,
        "usage": normalized,
    }


def calculate_google_response_cost(request_model_id, completion_response, *, request_service_tier=None, processing_mode="standard", platform=None, request_feature_hints=None, as_of=None):
    raw_usage = _raw_usage_from_response(completion_response)
    usage = raw_usage if raw_usage is not None else _obj_get(completion_response, "usage", None)
    response_model = _obj_get(completion_response, "modelVersion", None) or _obj_get(completion_response, "model", None) or request_model_id
    if usage is None:
        return {"provider": "google", "requested_model_id": request_model_id, "canonical_model_id": None, "total_cost_usd": None, "known_list_equivalent_usd": None, "complete": False, "notes": ["No Google/Gemini response usage telemetry was available; no price was guessed."], "usage": normalize_google_usage({}, response=completion_response)}
    return calculate_google_cost(response_model, usage, response=completion_response, request_service_tier=request_service_tier, processing_mode=processing_mode, platform=platform or infer_google_platform(request_model_id), request_feature_hints=request_feature_hints, as_of=as_of)


def estimate_google_input_cost(model_id, estimated_tokens, *, service_tier=None, processing_mode="standard", modality="text", as_of=None):
    record = resolve_google_model(model_id)
    if record is None:
        return {"provider": "google", "requested_model_id": model_id, "total_cost_usd": None, "complete": False, "notes": ["Unknown Google/Gemini model: no preflight price was guessed."]}
    requested = str(service_tier or "standard").lower()
    if processing_mode == "batch":
        mode = "batch"
    elif requested in {"standard", "default", ""}:
        mode = "standard"
    elif requested in {"flex", "priority"}:
        mode = requested
    else:
        return {"provider": "google", "requested_model_id": model_id, "total_cost_usd": None, "complete": False, "notes": [f"Unsupported Google service tier for preflight: {service_tier}."]}
    rates, period, long_context = _selected_rates(record, mode, int(estimated_tokens or 0), as_of=as_of)
    if rates is None:
        return {"provider": "google", "requested_model_id": model_id, "total_cost_usd": None, "complete": False, "notes": ["No verified Google rate period/mode applies to this preflight date."]}
    rate = _rate_for_modality(rates.get("input"), modality)
    if rate is None:
        return {"provider": "google", "requested_model_id": model_id, "total_cost_usd": None, "complete": False, "notes": [f"No verified Google {modality} input rate is registered for preflight."]}
    cost = max(0, int(estimated_tokens or 0)) / 1_000_000.0 * float(rate)
    return {
        "provider": "google",
        "requested_model_id": model_id,
        "canonical_model_id": record["canonical_model_id"],
        "verified_at": record.get("verified_at"),
        "processing_mode": mode,
        "price_period": period,
        "long_context": long_context,
        "total_cost_usd": round(cost, 12),
        "complete": True,
        "notes": ["Preflight input-only estimate; output, cache outcomes, grounding/tool charges, and account adjustments are not yet known."],
    }
