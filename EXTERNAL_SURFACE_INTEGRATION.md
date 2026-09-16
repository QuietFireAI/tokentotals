# External Surface Integration — Testing Track

This document records TokenTotals' **initial browser/frontier-model testing concept** and the conditions under which that work may continue.

It is **not the current launch path**.

## Why this track moved out of the launch path

The original product requirement remains straightforward:

> Use the AI where you already use it. When the answer finishes, the Turn Receipt appears directly beneath that answer.

The first implementation experiments attacked that problem through frontier-model/browser surfaces. Those experiments were useful because they exercised receipt placement, settlement, canonical receipt rendering, pricing/accounting, and the requirement that a receipt remain separate from the model's answer.

However, continuing to validate closed consumer browser surfaces across frontier models at the required evidence standard became **too cost-intensive for the project on our end**. The project therefore chose not to keep burning resources against that surface merely to preserve the original test sequence.

The launch focus pivoted to **Hermes Agent**, where documented observer hooks and stable transaction identities provide a stronger, less expensive environment for proving the actual receipt behavior. OpenClaw is planned next.

Browser/frontier work remains legitimate engineering work and may continue later. It is no longer a prerequisite for launch.

## What the browser work is for now

The browser path is retained for:

- controlled receipt-rendering experiments;
- external-surface placement research;
- testing provider-site correlation strategies;
- validating privacy boundaries;
- exploring what telemetry each browser surface legitimately exposes; and
- eventually adding browser adapters when the telemetry/evidence path is strong enough to justify them.

The built-in TokenTotals `/chat` page remains a reference/test harness for the accounting engine and renderer. It is not the launch destination.

## Browser acceptance gate

If browser work resumes as a first-class integration, it does not pass merely because HTML can be placed beneath an answer. A surface TokenTotals does not own must demonstrate in one real transaction:

1. user sends a normal prompt in the existing AI interface;
2. the provider/agent answer remains unchanged;
3. one Turn Receipt appears directly beneath that exact answer;
4. no second LLM generation call is made to create the receipt;
5. receipt identity correlates to the same external turn, not a timing guess;
6. telemetry fields are only marked observed when actually supplied by the surface;
7. missing telemetry remains unavailable, never fake zero;
8. deterministic TokenTotals pricing/accounting produces the receipt;
9. receipt ID, ledger record, thread aggregate and export reconcile; and
10. reload/duplicate/multiple-tab/new-thread cases do not cross-bind receipts.

Until those conditions are met on a browser surface, browser integration remains testing/research.

## Architecture under study

```text
Existing provider/agent surface
        ↓
privacy-limited telemetry observation
        ↓
exact external-turn correlation
        ↓
localhost TokenTotals accounting
        ↓
canonical Turn Receipt
        ↓
receipt placed after the exact answer
```

TokenTotals remains responsible for pricing, provenance, missing-data semantics, ledgering and rendering. A browser adapter would be responsible for observation, correlation and placement.

## Privacy boundary

The external ingest contract excludes prompt text, answer text, API keys, cookies, authorization headers and hidden reasoning. Browser probes must whitelist usage/model/correlation fields and discard ordinary response content.

## Current technical boundary

Chrome/Edge extension technology can place UI into permitted pages and communicate with localhost. That makes placement technically feasible.

The harder question is whether a given consumer website exposes enough same-turn transaction telemetry to support a defensible receipt. That must be established per surface. TokenTotals will not substitute a visually convincing receipt for missing accounting evidence.

## Current priority order

1. **Hermes launch integration** — active launch path.
2. **OpenClaw integration** — next planned first-class surface.
3. Browser/frontier surfaces — continue when resources and telemetry evidence justify renewed work.

The earlier browser work is preserved because it is useful history and may become useful product work later. It is simply no longer being allowed to consume the launch budget before the receipt is proven in a telemetry-rich host.
