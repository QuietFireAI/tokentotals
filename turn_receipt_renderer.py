"""Safe HTML rendering for canonical TokenTotals Turn Receipts.

The renderer is presentation-only. It does not recalculate usage or pricing.
Standard mode stays turn-scoped. Expanded mode may receive the current thread
telemetry view as a separate aggregate surface.
"""

from html import escape

import turn_receipt


RECEIPT_FONT_STACK = '"Courier New", Courier, "Liberation Mono", ui-monospace, monospace'
VALID_MODES = {"standard", "expanded"}

_TOKEN_LABELS = {
    "input_tokens": "Input tokens",
    "uncached_input_tokens": "Uncached input",
    "cached_input_tokens": "Cached input",
    "cache_write_tokens": "Cache write/create",
    "output_tokens": "Output tokens",
    "reasoning_tokens": "Reasoning / thinking",
    "tool_input_tokens": "Tool input",
    "provider_reported_total_tokens": "Provider total",
    "reconstructed_total_tokens": "Reconstructed total",
    "unclassified_tokens": "Residual / unclassified",
    "reconciliation_delta_tokens": "Reconciliation delta",
}


def _e(value):
    return escape(str(value), quote=True)


def _display(value):
    if value is None or value == "":
        return "Unavailable"
    return _e(value)


def _int(value):
    if value is None:
        return "Unavailable"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return _e(value)


def _usd(value):
    if value is None:
        return "Unavailable"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _e(value)
    if number == 0.0:
        return "$0.0000"
    digits = 8 if abs(number) < 0.0001 else 6 if abs(number) < 1 else 4
    return f"${number:.{digits}f}"


def _row(label, value, *, value_class=""):
    cls = f"tt-receipt-value {value_class}".strip()
    return (
        '<div class="tt-receipt-row">'
        f'<span class="tt-receipt-label">{_e(label)}</span>'
        f'<span class="{cls}">{value}</span>'
        "</div>"
    )


def _metric(metric):
    metric = metric or {}
    value = metric.get("value")
    basis = metric.get("basis") or "unavailable"
    if value is None:
        return 'Unavailable <span class="tt-receipt-basis">unavailable</span>'
    return f'{_int(value)} <span class="tt-receipt-basis">{_e(basis)}</span>'


def _coverage(value):
    return _display(value or "unavailable")


def _indicator_markup(cost):
    indicator = (cost or {}).get("indicator") or {}
    label = indicator.get("label") or "Estimate status unavailable"
    level = indicator.get("level") or "warning"
    message = indicator.get("message") or ""
    css_level = "normal" if level == "normal" else "warning"
    detail = (
        f'<div class="tt-receipt-indicator-message">{_e(message)}</div>'
        if message and css_level == "warning"
        else ""
    )
    return (
        f'<div class="tt-receipt-indicator tt-{css_level}">'
        f'<strong>{_e(label)}</strong>{detail}</div>'
    )


def _css():
    return f"""
<style>
.tt-receipt {{
  --tt-ink:#202124; --tt-muted:#6b7280; --tt-line:#c9cdd3;
  --tt-warn:#92400e; --tt-warn-bg:#fffbeb; --tt-ok:#166534;
  max-width:720px; background:#fff; color:var(--tt-ink);
  border:1px solid #d6d8dc; border-radius:3px; overflow:hidden;
  font-family:{RECEIPT_FONT_STACK}; letter-spacing:.01em;
  box-shadow:0 2px 8px rgba(0,0,0,.055);
}}
.tt-receipt * {{ box-sizing:border-box; }}
.tt-receipt-head {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; padding:14px 16px; border-bottom:1px dashed var(--tt-line); }}
.tt-receipt-title {{ font-size:16px; font-weight:800; letter-spacing:.075em; text-transform:uppercase; }}
.tt-receipt-subtitle {{ color:var(--tt-muted); font-size:10px; margin-top:5px; line-height:1.4; }}
.tt-receipt-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:0 26px; padding:7px 16px; }}
.tt-receipt-row {{ display:flex; justify-content:space-between; gap:16px; padding:7px 0; border-bottom:1px dashed #e1e3e6; font-size:12px; }}
.tt-receipt-label {{ color:#555b63; text-transform:uppercase; font-size:10px; letter-spacing:.025em; }}
.tt-receipt-value {{ text-align:right; font-weight:700; overflow-wrap:anywhere; }}
.tt-receipt-basis {{ font-weight:400; color:var(--tt-muted); font-size:9px; text-transform:uppercase; white-space:nowrap; }}
.tt-receipt-indicator {{ margin:10px 16px 0; padding:8px 10px; border:1px dashed var(--tt-line); font-size:11px; }}
.tt-receipt-indicator.tt-normal {{ color:var(--tt-ok); }}
.tt-receipt-indicator.tt-warning {{ color:var(--tt-warn); background:var(--tt-warn-bg); }}
.tt-receipt-indicator-message {{ margin-top:4px; line-height:1.45; font-weight:400; }}
.tt-receipt-footer {{ display:flex; justify-content:space-between; gap:16px; align-items:center; padding:11px 16px; border-top:1px dashed var(--tt-line); font-size:10px; color:var(--tt-muted); }}
.tt-receipt-footer a {{ color:#30343a; text-decoration:none; font-weight:800; }}
.tt-receipt-section {{ border-top:1px dashed var(--tt-line); padding:12px 16px; }}
.tt-receipt-section h4 {{ margin:0 0 8px; font-size:11px; text-transform:uppercase; letter-spacing:.04em; }}
.tt-receipt-section-note {{ color:var(--tt-muted); font-size:10px; line-height:1.45; margin-bottom:8px; }}
.tt-receipt-mini-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:0 24px; }}
.tt-receipt-table {{ width:100%; border-collapse:collapse; font-size:10px; }}
.tt-receipt-table th,.tt-receipt-table td {{ padding:5px 4px; border-bottom:1px dashed #e1e3e6; text-align:left; vertical-align:top; }}
.tt-receipt-table th {{ color:#555b63; text-transform:uppercase; font-size:9px; }}
.tt-receipt-notes {{ margin:0; padding-left:18px; font-size:10px; line-height:1.5; }}
@media(max-width:680px) {{ .tt-receipt-grid,.tt-receipt-mini-grid {{ grid-template-columns:1fr; }} .tt-receipt-head,.tt-receipt-footer {{ flex-direction:column; }} }}
</style>
"""


def _standard_body(receipt):
    view = turn_receipt.standard_view(receipt)
    if not view:
        raise ValueError("receipt is required")
    turn = receipt.get("turn") or {}
    cost = turn.get("cost") or {}

    left = [
        _row("Model", _display(view.get("model"))),
        _row("Provider", _display(view.get("provider"))),
        _row("Turn estimate", _usd(view.get("turn_estimate_usd"))),
        _row("Pricing basis", _display(view.get("pricing_basis"))),
    ]
    right = [
        _row("Input", _int(view.get("input_tokens"))),
        _row("Cached input", _int(view.get("cached_input_tokens"))),
        _row("Output", _int(view.get("output_tokens"))),
        _row("Registry verified", _display(view.get("pricing_registry_verified_at"))),
    ]

    return (
        '<div class="tt-receipt-grid"><div>' + "".join(left) + '</div><div>' + "".join(right) + "</div></div>"
        + _indicator_markup(cost)
    )


def _token_section(turn):
    tokens = turn.get("tokens") or {}
    rows = []
    for field, label in _TOKEN_LABELS.items():
        rows.append(_row(label, _metric(tokens.get(field))))
    return (
        '<section class="tt-receipt-section"><h4>Token anatomy</h4>'
        '<div class="tt-receipt-mini-grid"><div>'
        + "".join(rows[:6])
        + '</div><div>'
        + "".join(rows[6:])
        + "</div></div></section>"
    )


def _pricing_section(turn):
    cost = turn.get("cost") or {}
    components = cost.get("components_usd") or {}
    provenance = cost.get("rate_provenance") or {}
    rates = provenance.get("effective_rates") or []
    unresolved = provenance.get("unresolved_components") or []

    component_rows = "".join(
        f"<tr><td>{_e(name)}</td><td>{_usd(value)}</td></tr>"
        for name, value in sorted(components.items())
        if not isinstance(value, dict)
    )
    for name, value in sorted(components.items()):
        if isinstance(value, dict):
            for subname, subvalue in sorted(value.items()):
                component_rows += f"<tr><td>{_e(name)}.{_e(subname)}</td><td>{_usd(subvalue)}</td></tr>"
    if not component_rows:
        component_rows = '<tr><td colspan="2">Unavailable for this estimate basis</td></tr>'

    rate_rows = "".join(
        "<tr>"
        f"<td>{_display(item.get('component'))}</td>"
        f"<td>{_display(item.get('unit_basis'))}</td>"
        f"<td>{_int(item.get('quantity'))}</td>"
        f"<td>{_usd(item.get('effective_rate_usd'))}</td>"
        "</tr>"
        for item in rates
    )
    if not rate_rows:
        rate_rows = '<tr><td colspan="4">No reproducible effective rates available for this estimate basis.</td></tr>'

    unresolved_markup = ""
    if unresolved:
        unresolved_markup = (
            '<div class="tt-receipt-section-note">Unresolved pricing components: '
            + ", ".join(_e(item) for item in unresolved)
            + "</div>"
        )

    return (
        '<section class="tt-receipt-section"><h4>Pricing math</h4>'
        f'<div class="tt-receipt-section-note">Component basis: {_display(cost.get("components_basis"))}. '
        'Effective rates are derived only from the recorded component dollars and recorded billed units for this turn.</div>'
        '<table class="tt-receipt-table"><thead><tr><th>Component</th><th>Recorded cost</th></tr></thead><tbody>'
        + component_rows
        + "</tbody></table>"
        '<div class="tt-receipt-section-note" style="margin-top:10px;">Effective rates</div>'
        '<table class="tt-receipt-table"><thead><tr><th>Component</th><th>Unit</th><th>Quantity</th><th>Rate</th></tr></thead><tbody>'
        + rate_rows
        + "</tbody></table>"
        + unresolved_markup
        + "</section>"
    )


def _identity_section(turn):
    model = turn.get("model") or {}
    tier = turn.get("service_tier") or {}
    cache = turn.get("cache_share") or {}
    rate = turn.get("output_tokens_per_wall_second")
    return (
        '<section class="tt-receipt-section"><h4>Turn detail</h4><div class="tt-receipt-mini-grid"><div>'
        + _row("Receipt ID", _display(turn.get("turn_id")))
        + _row("Requested model", _display(model.get("requested")))
        + _row("Canonical model", _display(model.get("canonical")))
        + _row("Observed model", _display(model.get("observed")))
        + _row("Requested tier", _display(tier.get("requested")))
        + _row("Observed tier", _display(tier.get("observed")))
        + '</div><div>'
        + _row("Latency", _display(f"{turn.get('latency_ms')} ms" if turn.get("latency_ms") is not None else None))
        + _row("Cached share", _display(f"{cache.get('pct_of_input')}%" if cache.get("pct_of_input") is not None else None))
        + _row("Output / wall sec", _display(rate))
        + _row("Started", _display(turn.get("started_at")))
        + _row("Completed", _display(turn.get("completed_at")))
        + "</div></div></section>"
    )


def _thread_section(thread_view):
    if not thread_view:
        return (
            '<section class="tt-receipt-section"><h4>Current thread aggregate</h4>'
            '<div class="tt-receipt-section-note">Thread aggregate is unavailable for this rendering.</div></section>'
        )
    cost = thread_view.get("cost") or {}
    models = thread_view.get("by_model") or []
    model_rows = "".join(
        "<tr>"
        f"<td>{_display(item.get('model_id'))}</td>"
        f"<td>{_display(item.get('provider'))}</td>"
        f"<td>{_int(item.get('turn_count'))}</td>"
        f"<td>{_usd((item.get('cost') or {}).get('estimated_cost_usd'))}</td>"
        f"<td>{_coverage((item.get('cost') or {}).get('coverage'))}</td>"
        "</tr>"
        for item in models
    )
    if not model_rows:
        model_rows = '<tr><td colspan="5">No model breakdown available.</td></tr>'
    return (
        '<section class="tt-receipt-section"><h4>Current thread aggregate</h4>'
        '<div class="tt-receipt-section-note">This is the thread aggregate at render time; it is not represented as the historical state of an older turn.</div>'
        '<div class="tt-receipt-mini-grid"><div>'
        + _row("Turns", _int(thread_view.get("turn_count")))
        + _row("Thread estimate", _usd(cost.get("estimated_cost_usd")))
        + '</div><div>'
        + _row("Costed turns", _int(cost.get("costed_turns")))
        + _row("Cost coverage", _coverage(cost.get("coverage")))
        + "</div></div>"
        '<table class="tt-receipt-table"><thead><tr><th>Model</th><th>Provider</th><th>Turns</th><th>Estimate</th><th>Coverage</th></tr></thead><tbody>'
        + model_rows
        + "</tbody></table></section>"
    )


def _notes_section(turn):
    notes = [str(note) for note in (turn.get("notes") or []) if str(note).strip()]
    if not notes:
        return ""
    return (
        '<section class="tt-receipt-section"><h4>Notes</h4><ul class="tt-receipt-notes">'
        + "".join(f"<li>{_e(note)}</li>" for note in notes)
        + "</ul></section>"
    )


def render_html(receipt, mode="standard", thread_view=None):
    """Render a canonical Turn Receipt as a safe HTML fragment.

    Standard mode is strictly turn-scoped. Expanded mode adds deeper turn detail
    and may include a separately supplied current thread aggregate.
    """
    selected = str(mode or "standard").strip().lower()
    if selected not in VALID_MODES:
        raise ValueError("mode must be 'standard' or 'expanded'")
    if not receipt:
        raise ValueError("receipt is required")

    view = turn_receipt.standard_view(receipt)
    if not view:
        raise ValueError("receipt is required")
    turn = receipt.get("turn") or {}

    body = _standard_body(receipt)
    if selected == "expanded":
        body += _identity_section(turn)
        body += _token_section(turn)
        body += _pricing_section(turn)
        body += _thread_section(thread_view)
        body += _notes_section(turn)

    return (
        _css()
        + f'<article class="tt-receipt" data-receipt-id="{_e(view.get("receipt_id"))}" data-mode="{_e(selected)}">'
        + '<header class="tt-receipt-head"><div>'
        + '<div class="tt-receipt-title">Turn Receipt</div>'
        + '</div><div class="tt-receipt-value">'
        + _display(view.get("completed_at"))
        + "</div></header>"
        + body
        + '<footer class="tt-receipt-footer"><a href="https://turnreceipt.com/" rel="noopener">TurnReceipt.com</a></footer>'
        + "</article>"
    )
