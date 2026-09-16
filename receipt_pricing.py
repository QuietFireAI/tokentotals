"""Derive durable effective-rate provenance from recorded Turn Receipt math.

This module deliberately does not look up today's pricing registries. It derives
only the effective unit rates that can be reproduced from the turn's persisted
usage units and persisted component costs. That lets an old receipt retain the
math that was actually recorded even after public pricing tables change.
"""

from decimal import Decimal


_COMPONENT_ALIGNED_COST_BASES = {
    "provider_registry_complete",
    "known_list_equivalent",
}
_TOKEN_SCALE = Decimal(1_000_000)


def _metric_value(turn, field):
    metric = (turn.get("tokens") or {}).get(field) or {}
    value = metric.get("value")
    return int(value) if value is not None else None


def _request_count(turn, field):
    value = (turn.get("server_tools") or {}).get(field)
    return int(value) if value is not None else None


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _append_effective_rate(rates, unresolved, *, component, quantity, cost_usd, unit_basis):
    cost = _number(cost_usd)
    if cost is None:
        return
    if cost < 0:
        unresolved.append(component)
        return
    if quantity is None or int(quantity) <= 0:
        if cost != 0.0:
            unresolved.append(component)
        return

    quantity = int(quantity)
    scale = _TOKEN_SCALE if unit_basis == "per_1m_tokens" else Decimal(1)
    effective = (Decimal(str(cost)) * scale) / Decimal(quantity)
    rates.append({
        "component": component,
        "unit_basis": unit_basis,
        "quantity": quantity,
        "component_cost_usd": cost,
        "effective_rate_usd": float(round(effective, 12)),
    })


def _openai_rates(turn, components, rates, unresolved):
    mapping = (
        ("input", "uncached_input_tokens"),
        ("cached_input", "cached_input_tokens"),
        ("cache_write", "cache_write_tokens"),
        ("output", "output_tokens"),
    )
    for component, token_field in mapping:
        if component not in components:
            continue
        _append_effective_rate(
            rates,
            unresolved,
            component=component,
            quantity=_metric_value(turn, token_field),
            cost_usd=components.get(component),
            unit_basis="per_1m_tokens",
        )


def _anthropic_rates(turn, components, rates, unresolved):
    for component, token_field in (
        ("base_input", "uncached_input_tokens"),
        ("cache_read", "cached_input_tokens"),
        ("output", "output_tokens"),
    ):
        if component not in components:
            continue
        _append_effective_rate(
            rates,
            unresolved,
            component=component,
            quantity=_metric_value(turn, token_field),
            cost_usd=components.get(component),
            unit_basis="per_1m_tokens",
        )

    cache_keys = ("cache_write_5m", "cache_write_1h")
    cache_costs = [_number(components.get(key)) for key in cache_keys if key in components]
    if cache_costs:
        _append_effective_rate(
            rates,
            unresolved,
            component="cache_write_effective",
            quantity=_metric_value(turn, "cache_write_tokens"),
            cost_usd=sum(cache_costs),
            unit_basis="per_1m_tokens",
        )

    for component, count_field in (
        ("web_search", "web_search_requests"),
        ("web_fetch", "web_fetch_requests"),
    ):
        if component not in components:
            continue
        _append_effective_rate(
            rates,
            unresolved,
            component=component,
            quantity=_request_count(turn, count_field),
            cost_usd=components.get(component),
            unit_basis="per_request",
        )


def _google_component_quantities(turn, bucket, fallback_token_field, *, include_reasoning=False):
    raw = (turn.get("modalities") or {}).get(bucket)
    quantities = {
        str(key): int(value)
        for key, value in (raw or {}).items()
        if value is not None
    }
    if include_reasoning:
        reasoning = _metric_value(turn, "reasoning_tokens")
        if reasoning is None:
            return quantities, False
        if reasoning:
            quantities["text"] = int(quantities.get("text", 0)) + reasoning

    if quantities:
        return quantities, True

    fallback = _metric_value(turn, fallback_token_field)
    if fallback is None:
        return {}, False
    if include_reasoning:
        reasoning = _metric_value(turn, "reasoning_tokens")
        if reasoning is None:
            return {}, False
        fallback += reasoning
    return {"text": fallback}, True


def _google_nested_rates(turn, components, rates, unresolved):
    definitions = (
        ("uncached_input", "uncached_input", "uncached_input_tokens", False),
        ("cached_input", "cached_input", "cached_input_tokens", False),
        ("tool_use_input", "tool_input", "tool_input_tokens", False),
        ("output_including_thinking", "output", "output_tokens", True),
    )
    for component, bucket, token_field, include_reasoning in definitions:
        costs = components.get(component)
        if not isinstance(costs, dict):
            continue
        quantities, quantity_complete = _google_component_quantities(
            turn,
            bucket,
            token_field,
            include_reasoning=include_reasoning,
        )
        populated_cost_modalities = [
            str(modality)
            for modality, value in costs.items()
            if _number(value) not in (None, 0.0)
        ]
        if not quantity_complete and populated_cost_modalities:
            unresolved.extend(f"{component}.{modality}" for modality in populated_cost_modalities)
            continue
        for modality, cost in costs.items():
            _append_effective_rate(
                rates,
                unresolved,
                component=f"{component}.{modality}",
                quantity=quantities.get(str(modality)),
                cost_usd=cost,
                unit_basis="per_1m_tokens",
            )

    if "unattributed_input_equivalent" in components:
        _append_effective_rate(
            rates,
            unresolved,
            component="unattributed_input_equivalent",
            quantity=_metric_value(turn, "unclassified_tokens"),
            cost_usd=components.get("unattributed_input_equivalent"),
            unit_basis="per_1m_tokens",
        )

    # Google 2.5 and Gemini 3 grounding components have different public billing
    # units. The ledger intentionally does not infer that unit from a model name.
    # Preserve the component dollars, but do not manufacture an effective rate.
    for grounding_component in (
        "search_grounding_list_equivalent",
        "maps_grounding_list_equivalent",
    ):
        value = _number(components.get(grounding_component))
        if value not in (None, 0.0):
            unresolved.append(grounding_component)


def from_turn(turn):
    """Return effective-rate provenance that can be reproduced from this turn."""
    cost = turn.get("cost") or {}
    basis = str(cost.get("basis") or "unavailable")
    verified_at = cost.get("registry_verified_at")
    components = cost.get("components_usd") or {}

    base = {
        "estimate_basis": basis,
        "registry_verified_at": verified_at,
        "method": "recorded component cost divided by recorded billed units",
        "scope": "effective rates for this recorded turn only; not a provider price table",
        "effective_rates": [],
        "unresolved_components": [],
    }

    if basis not in _COMPONENT_ALIGNED_COST_BASES:
        base["status"] = "unavailable_for_estimate_basis"
        return base

    rates = base["effective_rates"]
    unresolved = base["unresolved_components"]
    provider = str(turn.get("provider") or "unknown").lower()

    if provider == "openai":
        _openai_rates(turn, components, rates, unresolved)
    elif provider == "anthropic":
        _anthropic_rates(turn, components, rates, unresolved)
    elif provider == "google":
        _google_nested_rates(turn, components, rates, unresolved)
    elif components:
        unresolved.extend(sorted(str(key) for key in components))

    # Keep deterministic ordering and avoid duplicate unresolved labels.
    unresolved[:] = sorted(set(unresolved))
    rates.sort(key=lambda item: item["component"])

    if rates and unresolved:
        base["status"] = "partial"
    elif rates:
        base["status"] = "complete_for_recorded_components"
    elif unresolved:
        base["status"] = "unavailable_for_recorded_components"
    else:
        base["status"] = "no_nonzero_component_rate_data"
    return base
