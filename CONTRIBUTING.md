# Contributing to TokenTotals

TokenTotals is built around inspectable telemetry, explicit arithmetic, and preserved evidence. Contributions are welcome, especially corrections that make a calculation, provider rule, telemetry interpretation, or failure boundary more accurate.

## Math and metric review

Start with `CALCULATION_TRANSPARENCY.md`. It documents the formulas currently used for derived metrics, including cost components, token reconstruction, cache share, residual tokens, coverage, turn statistics, pacing calculations, and Turn Notice comparisons.

If you think a calculation should change, please make the review reproducible. A strong math/metric report includes:

1. **Metric or formula** — name the exact TokenTotals field or documented calculation being challenged.
2. **Observed inputs** — show the provider/client telemetry fields used. Do not include secrets, prompt text, or private account data that is not necessary to reproduce the issue.
3. **Current TokenTotals result** — include the current derived value and, when relevant, its `observed`, `derived`, or `unavailable` basis.
4. **Expected result** — show the arithmetic you believe should replace or correct the current result.
5. **Pricing/rule basis** — link or identify the provider-published rule, registry entry, SDK/API behavior, or other supported evidence behind the proposed change.
6. **Reproduction** — provide the smallest reproducible example that demonstrates the delta.
7. **Test expectation** — describe the regression test that would fail before the correction and pass after it.

A useful report can be as simple as:

```text
Metric: cached_input_share_pct
Observed input_tokens: 34,521
Observed cached_input_tokens: 32,768
Current formula: cached / input × 100
Current result: 94.92%
Proposed result: ...
Why: ...
Provider/source: ...
Expected regression: ...
```

## Evidence standard

TokenTotals separates three things deliberately:

- **Observed** — supplied by legitimate provider/client/runtime telemetry.
- **Derived** — TokenTotals arithmetic over observed facts and versioned rules.
- **Unavailable** — not defensibly reconstructable from the available data.

A proposal should not convert an unavailable value into a confident zero, infer a provider-account balance, or turn a pricing assumption into an invoice-exact claim.

Provider invoices and authoritative account records remain the final billing authority. TokenTotals aims to make its own reconstruction as checkable as possible, not to hide uncertainty.

## Where to look

Calculation documentation:

- `CALCULATION_TRANSPARENCY.md`

Provider pricing rules:

- `pricing/openai_registry.json`
- `pricing/anthropic_registry.json`
- `pricing/google_registry.json`

Provider calculators:

- `openai_pricing.py`
- `anthropic_pricing.py`
- `google_pricing.py`

Telemetry/presentation math:

- `turn_ledger.py`
- `telemetry_view.py`
- `config_manager.py`
- `proxy_server.py`

Verification history:

- `archive/verification-receipts/`

Receipts intentionally preserve failed tests, stale assumptions, and repaired defects. Unfavorable evidence is useful evidence.

## Pull requests

Keep changes narrow when possible. For a calculation change, update the implementation, its regression test, and the relevant documentation together. Do not rewrite historical verification receipts to make an earlier result look better; add a new receipt or follow-up evidence instead.
