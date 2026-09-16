"""Canonical machine-readable Turn Receipt presentation object.

A Turn Receipt is produced from the privacy-limited, normalized turn record that
TokenTotals already stores. This module does not recalculate provider usage or
pricing. It gives the existing per-turn presentation a stable object identity for
renderers, APIs, exports, and tests.
"""

import telemetry_view


TURN_RECEIPT_SCHEMA = "tokentotals.turn_receipt"
TURN_RECEIPT_SCHEMA_VERSION = 1
TURN_RECEIPT_KIND = "completed_turn_usage_estimate"


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
