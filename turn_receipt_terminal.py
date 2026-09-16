"""Terminal renderer for canonical Turn Receipt objects.

The renderer consumes the same canonical receipt object used by HTML/API surfaces.
It does not recalculate tokens or cost.
"""

from __future__ import annotations


def _value(value):
    return "Unavailable" if value is None else str(value)


def _money(value):
    if value is None:
        return "Unavailable"
    return f"${float(value):.8f}".rstrip("0").rstrip(".")


def _row(label, value, width=22):
    return f"{label:<{width}} {value}"


def render_text(receipt, mode="standard", *, evidence=None):
    if not receipt:
        raise ValueError("receipt is required")
    mode = str(mode or "standard").strip().lower()
    if mode not in {"standard", "expanded"}:
        raise ValueError("mode must be standard or expanded")

    turn = receipt.get("turn") or {}
    model = turn.get("model") or {}
    tokens = turn.get("tokens") or {}
    cost = turn.get("cost") or {}
    indicator = cost.get("indicator") or {}

    def token(name):
        metric = tokens.get(name) or {}
        return metric.get("value")

    lines = [
        "TURN RECEIPT",
        "----------------------------------------",
        _row("Provider", _value(turn.get("provider"))),
        _row("Model", _value(model.get("canonical") or model.get("observed") or model.get("requested"))),
        _row("Input tokens", _value(token("input_tokens"))),
        _row("Cached input", _value(token("cached_input_tokens"))),
        _row("Output tokens", _value(token("output_tokens"))),
        _row("Turn estimate", _money(cost.get("estimated_usd"))),
    ]
    if indicator.get("label"):
        lines.append(_row("Estimate status", indicator.get("label")))

    if mode == "expanded":
        lines.extend(
            [
                "----------------------------------------",
                _row("Receipt ID", _value(receipt.get("receipt_id"))),
                _row("Completed", _value(turn.get("completed_at"))),
                _row("Pricing basis", _value(cost.get("basis"))),
                _row("Cost complete", "yes" if cost.get("complete") else "no"),
                _row("Uncached input", _value(token("uncached_input_tokens"))),
                _row("Cache write", _value(token("cache_write_tokens"))),
                _row("Reasoning tokens", _value(token("reasoning_tokens"))),
                _row("Provider total", _value(token("provider_reported_total_tokens"))),
            ]
        )
        if evidence:
            calls = evidence.get("api_calls") or []
            failures = evidence.get("failed_api_attempts") or []
            lines.extend(
                [
                    _row("Hermes API calls", len(calls)),
                    _row("Failed attempts", len(failures)),
                ]
            )
            for index, call in enumerate(calls, start=1):
                usage = call.get("usage") or {}
                pricing = call.get("pricing") or {}
                label = f"Call {index}"
                detail = (
                    f"{call.get('provider') or 'unknown'} · "
                    f"{call.get('response_model') or call.get('model') or 'unknown'} · "
                    f"{_value(usage.get('total_tokens'))} tok · "
                    f"{_money(pricing.get('estimated_usd'))}"
                )
                lines.append(_row(label, detail))

    lines.extend(["----------------------------------------", "TurnReceipt.com"])
    return "\n".join(lines)
