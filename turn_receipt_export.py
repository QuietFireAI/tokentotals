"""Spreadsheet-safe thread export built from canonical Turn Receipts.

The export is intentionally accounting/telemetry-only. It does not include prompt
text, model answer text, API keys, or hidden reasoning. Missing cost information
remains blank rather than being converted to zero.
"""

import csv
import io
from decimal import Decimal

import turn_ledger
import turn_receipt


CSV_COLUMNS = (
    "receipt_id",
    "thread_id",
    "turn_number",
    "completed_at",
    "provider",
    "model",
    "requested_model",
    "observed_model",
    "requested_service_tier",
    "observed_service_tier",
    "input_tokens",
    "input_tokens_basis",
    "cached_input_tokens",
    "cached_input_tokens_basis",
    "uncached_input_tokens",
    "uncached_input_tokens_basis",
    "cache_write_tokens",
    "cache_write_tokens_basis",
    "output_tokens",
    "output_tokens_basis",
    "reasoning_tokens",
    "reasoning_tokens_basis",
    "tool_input_tokens",
    "tool_input_tokens_basis",
    "turn_total_tokens",
    "turn_total_tokens_basis",
    "turn_estimate_usd",
    "estimate_status",
    "estimate_basis",
    "estimate_complete",
    "registry_verified_at",
    "running_thread_estimate_usd",
    "costed_turns_to_date",
    "thread_cost_coverage_to_date",
    "latency_ms",
)

_DANGEROUS_SPREADSHEET_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def _safe_text(value):
    """Prevent spreadsheet formula execution while preserving the visible value."""
    if value is None:
        return ""
    text = str(value)
    stripped = text.lstrip(" ")
    if text.startswith(("\t", "\r", "\n")) or (
        stripped and stripped.startswith(_DANGEROUS_SPREADSHEET_PREFIXES[:4])
    ):
        return "'" + text
    return text


def _metric(turn, name):
    metric = (turn.get("tokens") or {}).get(name) or {}
    return metric.get("value"), metric.get("basis") or "unavailable"


def _decimal_text(value):
    if value is None:
        return ""
    amount = Decimal(str(value))
    text = format(amount, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def thread_rows(thread_id):
    """Return audit rows for completed turns in one thread, in ledger order."""
    key = str(thread_id or "").strip()
    if not key:
        raise ValueError("thread_id must be non-empty")

    records = turn_ledger.read_turns(thread_id=key)
    if not records:
        return []

    rows = []
    running_cost = Decimal("0")
    costed_turns = 0

    for turn_number, record in enumerate(records, start=1):
        receipt = turn_receipt.from_record(record)
        if not receipt:
            continue
        turn = receipt.get("turn") or {}
        cost = turn.get("cost") or {}
        model = turn.get("model") or {}
        service_tier = turn.get("service_tier") or {}
        indicator = cost.get("indicator") or {}
        turn_total = turn.get("turn_total_tokens") or {}

        amount = cost.get("estimated_usd")
        if amount is not None:
            running_cost += Decimal(str(amount))
            costed_turns += 1

        if costed_turns == 0:
            coverage = "unavailable"
            running_cost_text = ""
        else:
            coverage = "complete" if costed_turns == turn_number else "partial"
            running_cost_text = _decimal_text(running_cost)

        input_value, input_basis = _metric(turn, "input_tokens")
        cached_value, cached_basis = _metric(turn, "cached_input_tokens")
        uncached_value, uncached_basis = _metric(turn, "uncached_input_tokens")
        cache_write_value, cache_write_basis = _metric(turn, "cache_write_tokens")
        output_value, output_basis = _metric(turn, "output_tokens")
        reasoning_value, reasoning_basis = _metric(turn, "reasoning_tokens")
        tool_value, tool_basis = _metric(turn, "tool_input_tokens")

        selected_model = model.get("canonical") or model.get("observed") or model.get("requested")
        rows.append({
            "receipt_id": _safe_text(receipt.get("receipt_id")),
            "thread_id": _safe_text(turn.get("thread_id") or key),
            "turn_number": turn_number,
            "completed_at": _safe_text(turn.get("completed_at")),
            "provider": _safe_text(turn.get("provider")),
            "model": _safe_text(selected_model),
            "requested_model": _safe_text(model.get("requested")),
            "observed_model": _safe_text(model.get("observed")),
            "requested_service_tier": _safe_text(service_tier.get("requested")),
            "observed_service_tier": _safe_text(service_tier.get("observed")),
            "input_tokens": "" if input_value is None else input_value,
            "input_tokens_basis": _safe_text(input_basis),
            "cached_input_tokens": "" if cached_value is None else cached_value,
            "cached_input_tokens_basis": _safe_text(cached_basis),
            "uncached_input_tokens": "" if uncached_value is None else uncached_value,
            "uncached_input_tokens_basis": _safe_text(uncached_basis),
            "cache_write_tokens": "" if cache_write_value is None else cache_write_value,
            "cache_write_tokens_basis": _safe_text(cache_write_basis),
            "output_tokens": "" if output_value is None else output_value,
            "output_tokens_basis": _safe_text(output_basis),
            "reasoning_tokens": "" if reasoning_value is None else reasoning_value,
            "reasoning_tokens_basis": _safe_text(reasoning_basis),
            "tool_input_tokens": "" if tool_value is None else tool_value,
            "tool_input_tokens_basis": _safe_text(tool_basis),
            "turn_total_tokens": "" if turn_total.get("value") is None else turn_total.get("value"),
            "turn_total_tokens_basis": _safe_text(turn_total.get("basis") or "unavailable"),
            "turn_estimate_usd": _decimal_text(amount),
            "estimate_status": _safe_text(indicator.get("status") or "unavailable"),
            "estimate_basis": _safe_text(cost.get("basis") or "unavailable"),
            "estimate_complete": "true" if bool(cost.get("complete")) else "false",
            "registry_verified_at": _safe_text(cost.get("registry_verified_at")),
            "running_thread_estimate_usd": running_cost_text,
            "costed_turns_to_date": costed_turns,
            "thread_cost_coverage_to_date": coverage,
            "latency_ms": "" if turn.get("latency_ms") is None else turn.get("latency_ms"),
        })

    return rows


def thread_csv(thread_id):
    """Return UTF-8 CSV text with an Excel-friendly BOM, or None if no turns exist."""
    rows = thread_rows(thread_id)
    if not rows:
        return None

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return "\ufeff" + output.getvalue()
