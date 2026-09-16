from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, found {count}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Normal receipts stay visually quiet. Warning messages remain visible because
# they materially qualify the displayed accounting result.
replace_once(
    "turn_receipt_renderer.py",
    '    detail = f\'<div class="tt-receipt-indicator-message">{_e(message)}</div>\' if message else ""\n',
    '    detail = (\n'
    '        f\'<div class="tt-receipt-indicator-message">{_e(message)}</div>\'\n'
    '        if message and css_level == "warning"\n'
    '        else ""\n'
    '    )\n',
)

# Keep receipt ID available in Expanded detail for auditability.
replace_once(
    "turn_receipt_renderer.py",
    '        + _row("Requested model", _display(model.get("requested")))\n',
    '        + _row("Receipt ID", _display(turn.get("turn_id")))\n'
    '        + _row("Requested model", _display(model.get("requested")))\n',
)

# Remove the ordinary disclaimer subline from the visual receipt header.
replace_once(
    "turn_receipt_renderer.py",
    '        + \'<header class="tt-receipt-head"><div>\'\n'
    '        + \'<div class="tt-receipt-title">Turn Receipt</div>\'\n'
    '        + f\'<div class="tt-receipt-subtitle">{_e(view.get("disclaimer"))}</div>\'\n'
    '        + \'</div><div class="tt-receipt-value">\'\n',
    '        + \'<header class="tt-receipt-head"><div>\'\n'
    '        + \'<div class="tt-receipt-title">Turn Receipt</div>\'\n'
    '        + \'</div><div class="tt-receipt-value">\'\n',
)

# Footer is intentionally only the product URL.
replace_once(
    "turn_receipt_renderer.py",
    '        + \'<footer class="tt-receipt-footer"><span>Receipt ID: \'\n'
    '        + _display(view.get("receipt_id"))\n'
    '        + \'</span><a href="https://turnreceipt.com/" rel="noopener">TURNRECEIPT.COM</a></footer>\'\n',
    '        + \'<footer class="tt-receipt-footer"><a href="https://turnreceipt.com/" rel="noopener">TurnReceipt.com</a></footer>\'\n',
)

# Lock the visual rule in tests.
replace_once(
    "tests/test_turn_receipt_renderer.py",
    '        self.assertIn("TURNRECEIPT.COM", html)\n        self.assertIn("not a provider invoice", html)\n',
    '        self.assertIn(">TurnReceipt.com</a>", html)\n'
    '        self.assertNotIn("not a provider invoice", html)\n'
    '        self.assertNotIn("Receipt ID:", html)\n',
)
replace_once(
    "tests/test_turn_receipt_renderer.py",
    '        self.assertIn("Token anatomy", html)\n',
    '        self.assertIn("Receipt ID", html)\n'
    '        self.assertIn("turn-abc123", html)\n'
    '        self.assertIn("Token anatomy", html)\n',
)

print("receipt visual rule applied")
