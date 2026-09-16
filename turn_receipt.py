"""Canonical machine-readable Turn Receipt presentation object.

A Turn Receipt is produced from the privacy-limited, normalized turn record that
TokenTotals already stores. This module does not recalculate provider usage or
pricing. It gives the existing per-turn presentation a stable object identity for
renderers, APIs, exports, and tests.
"""

import receipt_pricing
import telemetry_view


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
