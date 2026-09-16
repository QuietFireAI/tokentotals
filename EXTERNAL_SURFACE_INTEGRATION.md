# External Surface Integration

This work exists to restore the original Turn Receipt product requirement:

> Use the AI where you already use it. When the answer finishes, the Turn Receipt appears directly beneath that answer.

`/chat` is a controlled reference client and test harness. It is not sufficient evidence that the external-surface product requirement is complete.

## Acceptance gate

The product is not launch-ready until a surface TokenTotals does not own demonstrates all of the following in one real transaction:

1. user sends one normal prompt in the existing AI/agent interface;
2. provider/agent answer remains unchanged;
3. one Turn Receipt appears directly beneath that exact answer;
4. no second LLM generation call is made to create the receipt;
5. receipt identity correlates to the same external turn, not a timing guess;
6. telemetry fields are only marked observed when actually supplied by the surface;
7. missing telemetry remains unavailable, never fake zero;
8. deterministic TokenTotals pricing/accounting produces the receipt;
9. receipt ID, ledger record, thread aggregate, dashboard and export reconcile;
10. reload, duplicate event, multiple tabs and new-thread cases do not cross-bind receipts;
11. disabling the extension leaves the provider UI working normally;
12. the path survives a clean Windows restart/install test.

## Architecture

Existing provider/agent surface -> privacy-limited telemetry probe -> exact external turn correlation -> localhost `POST /api/external-turn` -> canonical TokenTotals ledger record -> existing receipt renderer -> receipt inserted after the exact answer element.

The extension is responsible for observation, correlation and placement. TokenTotals remains responsible for pricing, provenance, missing-data semantics, ledgering and rendering.

## Privacy boundary

The external ingest contract intentionally excludes prompt text, answer text, API keys, cookies, authorization headers and hidden reasoning. The browser probe whitelists usage/model/correlation fields and discards ordinary response content.

## Current hard boundary

Chrome/Edge MV3 can inject scripts into supported pages and communicate with localhost. DOM placement is therefore technically feasible.

A provider-owned consumer chat page does not necessarily expose API-grade token/cost telemetry. The implementation must inspect each surface separately. When same-turn usage fields are absent, TokenTotals must not invent them. A visually inserted receipt with unavailable fields is truthful; a complete cost receipt is only possible when sufficient telemetry is actually observable or the provider/host supplies it.

The extension does not use timing proximity alone to claim exact-turn identity. If a stable response/message/turn ID cannot be correlated between DOM and observed telemetry, it refuses settlement until a stronger adapter exists.

## Adapter order

1. telemetry-rich external/agent surfaces first for a full accounting proof;
2. Gemini web telemetry/DOM probe;
3. ChatGPT web telemetry/DOM probe;
4. Claude web telemetry/DOM probe;
5. additional IDE/agent adapters.

A selector or endpoint is not considered stable because another project once used it. Every adapter requires live evidence before release.
