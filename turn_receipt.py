"""Canonical machine-readable Turn Receipt presentation object.

A Turn Receipt is produced from the privacy-limited, normalized turn record that
TokenTotals already stores. This module does not recalculate provider usage or
pricing. It gives the existing per-turn presentation a stable object identity for
renderers, APIs, exports, and tests.
"""

import receipt_pricing
import telemetry_view
import turn_ledger


TURN_RECEIPT_SCHEMA = "tokentotals.turn_receipt"
TURN_RECEIPT_SCHEMA_VERSION = 1
TURN_RECEIPT_KIND = "completed_turn_usage_estimate"
_COMPONENT_ALIGNED_COST_BASES = {
    "provider_registry_complete",
    "known_list_equivalent",
}


def _estimate_indicator(cost):
    basis = str(cost.get("basis") or "unavailable")
    complete = bool(cost.get("complete", False))
    amount = cost.get("estimated_usd")

    if basis == "provider_registry_complete" and complete:
        return {
            "status": "provider_reconstruction",
            "level": "normal",
            "label": "TokenTotals estimate",
            "message": (
                "Calculated from the provider telemetry and TokenTotals pricing basis available for this turn. "
                "This is still an independent estimate, not the provider invoice."
            ),
        }

    if basis == "litellm_response_cost_fallback" and amount is not None:
        return {
            "status": "fallback",
            "level": "warning",
            "label": "Fallback estimate",
            "message": (
                "Provider telemetry was not sufficient for TokenTotals' normal reconstruction. "
                "This amount uses LiteLLM response_cost as a secondary source and may be higher or lower than the provider invoice."
            ),
        }

    if basis == "known_list_equivalent" and amount is not None:
        return {
            "status": "list_equivalent",
            "level": "warning",
            "label": "List-equivalent estimate",
            "message": (
                "This amount reflects the known public list-equivalent portion TokenTotals could reconstruct. "
                "Unobservable or account-specific adjustments may make the provider invoice higher or lower."
            ),
        }

    if amount is None or basis == "unavailable":
        return {
            "status": "unavailable",
            "level": "warning",
            "label": "Cost unavailable",
            "message": (
                "TokenTotals does not have a defensible cost estimate for this turn. Missing cost information is not treated as zero."
            ),
        }

    return {
        "status": "incomplete",
        "level": "warning",
        "label": "Incomplete estimate",
        "message": (
            "TokenTotals recorded an estimate, but at least one pricing or telemetry dimension is unresolved. "
            "The provider invoice remains authoritative."
        ),
    }


def from_record(record):
    """Return the canonical Turn Receipt object for one completed ledger record."""
    if not record:
        return None

    turn = telemetry_view.latest_turn_view(record)
    if turn is None:
        return None

    receipt_id = str(turn.get("turn_id") or "").strip()
    if not receipt_id:
        raise ValueError("Turn Receipt requires a non-empty turn_id")

    # Provider calculator components are only presented as the arithmetic behind
    # the receipt total when that total came from the same provider reconstruction.
    # A LiteLLM response_cost fallback can be useful, but its internal rate/component
    # basis is not exposed here, so provider components must not masquerade as the
    # math that produced that fallback total.
    cost = turn.get("cost") or {}
    if cost.get("basis") in _COMPONENT_ALIGNED_COST_BASES:
        cost["components_basis"] = "same_as_estimate"
    else:
        cost["components_usd"] = {}
        cost["components_basis"] = "unavailable_for_estimate_basis"

    # Derive only effective rates reproducible from the recorded component dollars
    # and recorded billed units. This intentionally does not consult today's price
    # registry, so an old receipt's math cannot drift when provider docs change.
    cost["rate_provenance"] = receipt_pricing.from_turn(turn)
    cost["indicator"] = _estimate_indicator(cost)

    return {
        "schema": TURN_RECEIPT_SCHEMA,
        "schema_version": TURN_RECEIPT_SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "kind": TURN_RECEIPT_KIND,
        "generated_by": "TokenTotals",
        "authority": {
            "scope": "independent_usage_estimate",
            "provider_invoice": False,
        },
        "turn": turn,
    }


def for_thread(thread_id):
    """Return the latest Turn Receipt plus a truthful current thread aggregate.

    The compact inline receipt stays turn-scoped. This deeper object preserves the
    thread-level total, count, and cost coverage for expanded/detail surfaces.
    The ledger's cumulative_completed_turns field is process-global, so it must not
    be presented as a per-thread count.
    """
    key = str(thread_id or "").strip()
    if not key:
        raise ValueError("thread_id must be non-empty")

    records = turn_ledger.read_turns(thread_id=key)
    if not records:
        return None

    receipt = from_record(records[-1])
    summary = turn_ledger.summarize_thread(key)
    total_turns = int(summary.get("turn_count") or 0)
    costed_turns = int(summary.get("cost_observed_turns") or 0)

    if costed_turns == 0:
        estimated_cost_usd = None
        coverage = "unavailable"
    else:
        estimated_cost_usd = summary.get("estimated_cost_usd")
        coverage = "complete" if costed_turns == total_turns else "partial"

    receipt["thread"] = {
        "thread_id": key,
        "turn_count": total_turns,
        "estimated_cost_usd": estimated_cost_usd,
        "costed_turns": costed_turns,
        "cost_coverage": coverage,
    }
    return receipt


def standard_view(receipt):
    """Return the compact, turn-scoped fields for the inline receipt."""
    if not receipt:
        return None

    turn = receipt.get("turn") or {}
    model = turn.get("model") or {}
    tokens = turn.get("tokens") or {}
    cost = turn.get("cost") or {}

    def token_value(name):
        metric = tokens.get(name) or {}
        return metric.get("value")

    return {
        "receipt_id": receipt.get("receipt_id"),
        "completed_at": turn.get("completed_at"),
        "provider": turn.get("provider"),
        "model": model.get("canonical") or model.get("observed") or model.get("requested"),
        "input_tokens": token_value("input_tokens"),
        "cached_input_tokens": token_value("cached_input_tokens"),
        "output_tokens": token_value("output_tokens"),
        "turn_estimate_usd": cost.get("estimated_usd"),
        "estimate_indicator": cost.get("indicator"),
        "pricing_basis": cost.get("basis"),
        "pricing_registry_verified_at": cost.get("registry_verified_at"),
        "disclaimer": "Independent usage estimate by TokenTotals — not a provider invoice.",
        "website": "TurnReceipt.com",
    }
