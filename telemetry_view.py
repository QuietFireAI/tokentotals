import math
import statistics

import turn_ledger


def _coverage(observed_turns, total_turns):
    observed = int(observed_turns or 0)
    total = int(total_turns or 0)
    if observed <= 0:
        return "unavailable"
    if total > 0 and observed == total:
        return "complete"
    return "partial"


def _model_key(record):
    return str(
        record.get("canonical_model_id")
        or record.get("observed_model_id")
        or record.get("requested_model_id")
        or "unknown"
    )


def _selected_total_tokens(record):
    tokens = record.get("tokens") or {}
    provider_total = tokens.get("provider_reported_total_tokens")
    if provider_total is not None:
        return int(provider_total), "provider_reported"
    reconstructed = tokens.get("reconstructed_total_tokens")
    if reconstructed is not None:
        return int(reconstructed), "tokentotals_reconstructed"
    return None, "unavailable"


def _token_metric(record, field):
    tokens = record.get("tokens") or {}
    basis = record.get("token_basis") or {}
    value = tokens.get(field)
    return {
        "value": int(value) if value is not None else None,
        "basis": str(basis.get(field) or "unavailable"),
    }


def _summary_token_metrics(raw_summary):
    total_turns = int(raw_summary.get("turn_count", 0) or 0)
    metrics = {}
    for field in turn_ledger.TOKEN_FIELDS:
        raw = (raw_summary.get("tokens") or {}).get(field) or {}
        observed_turns = int(raw.get("observed_turns", 0) or 0)
        metrics[field] = {
            "sum": int(raw.get("sum", 0) or 0) if observed_turns else None,
            "observed_turns": observed_turns,
            "total_turns": total_turns,
            "coverage": _coverage(observed_turns, total_turns),
        }
    return metrics


def _cost_summary(raw_summary):
    total_turns = int(raw_summary.get("turn_count", 0) or 0)
    costed_turns = int(raw_summary.get("cost_observed_turns", 0) or 0)
    return {
        "estimated_cost_usd": (
            float(raw_summary.get("estimated_cost_usd", 0.0))
            if costed_turns
            else None
        ),
        "costed_turns": costed_turns,
        "total_turns": total_turns,
        "coverage": _coverage(costed_turns, total_turns),
    }


def _nearest_rank_percentile(values, percentile):
    if not values:
        return None
    ordered = sorted(int(value) for value in values)
    rank = max(1, int(math.ceil(float(percentile) * len(ordered))))
    return ordered[rank - 1]


def _turn_size_stats(records):
    values = []
    for record in records:
        value, _basis = _selected_total_tokens(record)
        if value is not None:
            values.append(value)
    if not values:
        return {
            "sampled_turns": 0,
            "total_turns": len(records),
            "coverage": "unavailable",
            "sum": None,
            "average": None,
            "median": None,
            "p95_nearest_rank": None,
            "max": None,
        }
    return {
        "sampled_turns": len(values),
        "total_turns": len(records),
        "coverage": _coverage(len(values), len(records)),
        "sum": sum(values),
        "average": sum(values) / len(values),
        "median": statistics.median(values),
        "p95_nearest_rank": _nearest_rank_percentile(values, 0.95),
        "max": max(values),
    }


def _model_summary(model_id, raw_summary, records):
    return {
        "model_id": str(model_id),
        "provider": raw_summary.get("provider") or "unknown",
        "turn_count": int(raw_summary.get("turn_count", 0) or 0),
        "tokens": _summary_token_metrics(raw_summary),
        "turn_token_stats": _turn_size_stats(records),
        "cost": _cost_summary(raw_summary),
    }


def latest_turn_view(record):
    if not record:
        return None
    total_value, total_basis = _selected_total_tokens(record)
    input_tokens = (record.get("tokens") or {}).get("input_tokens")
    cached_tokens = (record.get("tokens") or {}).get("cached_input_tokens")
    output_tokens = (record.get("tokens") or {}).get("output_tokens")
    latency_ms = record.get("latency_ms")

    cache_share = None
    if input_tokens is not None and cached_tokens is not None and int(input_tokens) > 0:
        cache_share = {
            "cached_tokens": int(cached_tokens),
            "input_tokens": int(input_tokens),
            "pct_of_input": round((int(cached_tokens) / int(input_tokens)) * 100.0, 2),
        }

    output_per_wall_second = None
    if output_tokens is not None and latency_ms is not None and int(latency_ms) > 0:
        output_per_wall_second = round(int(output_tokens) / (int(latency_ms) / 1000.0), 3)

    cost_value = record.get("estimated_cost_usd")
    return {
        "turn_id": record.get("turn_id"),
        "thread_id": record.get("thread_id"),
        "started_at": record.get("started_at"),
        "completed_at": record.get("completed_at"),
        "latency_ms": int(latency_ms) if latency_ms is not None else None,
        "provider": record.get("provider") or "unknown",
        "model": {
            "requested": record.get("requested_model_id"),
            "canonical": record.get("canonical_model_id"),
            "observed": record.get("observed_model_id"),
        },
        "service_tier": {
            "requested": record.get("requested_service_tier"),
            "observed": record.get("observed_service_tier"),
        },
        "tokens": {
            field: _token_metric(record, field)
            for field in turn_ledger.TOKEN_FIELDS
        },
        "turn_total_tokens": {
            "value": total_value,
            "basis": total_basis,
        },
        "cache_share": cache_share,
        "output_tokens_per_wall_second": output_per_wall_second,
        "output_rate_scope": (
            "observed output tokens divided by callback wall-clock elapsed time; not pure model generation throughput"
            if output_per_wall_second is not None
            else None
        ),
        "modalities": record.get("modalities") or {},
        "server_tools": record.get("server_tools") or {},
        "cost": {
            "estimated_usd": float(cost_value) if cost_value is not None else None,
            "basis": record.get("cost_basis") or "unavailable",
            "complete": bool(record.get("estimate_complete", False)),
            "components_usd": record.get("pricing_components_usd") or {},
            "registry_verified_at": record.get("registry_verified_at"),
        },
        "notes": [str(note) for note in (record.get("notes") or [])],
    }


def thread_view(thread_id):
    records = turn_ledger.read_turns(thread_id=thread_id)
    if not records:
        return None

    raw_summary = turn_ledger.summarize_thread(thread_id)
    by_model_records = {}
    for record in records:
        by_model_records.setdefault(_model_key(record), []).append(record)

    by_model = []
    for model_id, model_raw in (raw_summary.get("by_model") or {}).items():
        by_model.append(
            _model_summary(
                model_id,
                model_raw,
                by_model_records.get(str(model_id), []),
            )
        )
    by_model.sort(key=lambda item: (-item["turn_count"], item["model_id"]))

    return {
        "thread_id": str(thread_id),
        "turn_count": len(records),
        "latest_turn": latest_turn_view(records[-1]),
        "tokens": _summary_token_metrics(raw_summary),
        "turn_token_stats": _turn_size_stats(records),
        "cost": _cost_summary(raw_summary),
        "by_model": by_model,
        "context": {
            "status": "unavailable",
            "reason": "No defensible normalized current-context and model-limit source is implemented across supported providers.",
        },
    }
