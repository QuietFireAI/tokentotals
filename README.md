# TokenTotals

> **Turn Receipts for Hermes.**
>
> Use Hermes normally. When a completed answer settles, TokenTotals is designed to place an independent Turn Receipt directly beneath that answer.

**Launch target:** Hermes Agent on Windows  
**Status:** pre-release candidate pending user-zero live proof  
**Next integration after Hermes:** OpenClaw  
**Browser `/chat` and browser-extension work:** reference/testing only, not the launch product

- Product: https://tokentotals.com
- Receipt: https://turnreceipt.com
- Turn Receipt reference: https://turnreceipts.com

## What TokenTotals is

TokenTotals is a local accounting engine for AI turns. For the Hermes launch, a Hermes plugin observes Hermes' own turn/request lifecycle telemetry and sends privacy-limited usage evidence to the local TokenTotals engine. TokenTotals then performs deterministic accounting and renders the receipt.

The model does **not** calculate its own receipt. Receipt generation does not require a second LLM call.

```text
You use Hermes normally
        ↓
Hermes completes the turn
        ↓
Hermes observer telemetry
        ↓
TokenTotals local accounting engine
        ↓
TURN RECEIPT
        ↓
TurnReceipt.com
```

The intended user experience is equally simple:

```text
You:    normal Hermes prompt
Hermes: normal Hermes answer

TURN RECEIPT
...
TurnReceipt.com
```

The Hermes answer is rendered first and is not rewritten by TokenTotals.

## Current launch status

The Hermes integration candidate has automated evidence for:

- full TokenTotals regression coverage;
- Hermes-specific contract tests;
- successful loading by a pinned real Hermes installation through Hermes' own plugin doctor;
- Windows TokenTotals candidate build and packaged smoke tests; and
- standalone Hermes plugin packaging.

Those checks are necessary, but they are **not the final product proof**.

The launch gate is a real user-zero Hermes session showing:

> **normal Hermes answer → matching Turn Receipt directly underneath**

Until that live behavior is demonstrated and its telemetry reconciles, this branch remains a candidate.

## Why Hermes is the first launch surface

Hermes exposes a documented observer contract with stable turn and request identities plus normalized usage telemetry. TokenTotals can therefore bind accounting to explicit transaction identities rather than guessing from browser timing or DOM position.

The integration uses Hermes lifecycle hooks for:

- turn scope;
- each successful provider API request;
- failed/retried API attempts;
- final turn settlement; and
- session cleanup.

A single human Hermes turn may contain several provider calls because of tools, retries, or agent loops. TokenTotals treats those calls as child transactions, prices them individually when the required telemetry is available, and then produces one top-level Turn Receipt for the human turn.

## What a Turn Receipt shows

A receipt can include, when the underlying runtime/provider exposes the information:

- provider and model identity;
- input and output tokens;
- cache/reasoning categories where defensibly observable;
- provider-reported totals;
- reconciliation values;
- estimated cost;
- pricing basis and estimate completeness;
- receipt identity; and
- in Expanded mode, child API-call evidence and deeper turn/thread economics.

**Missing is not zero.** If a billing-relevant field cannot be established, TokenTotals leaves it unavailable rather than manufacturing a neat-looking `0`.

A Turn Receipt is an independent usage estimate, not a provider invoice. Provider account and invoice records remain authoritative.

## One human turn, several transactions

Hermes can perform more than one model transaction to satisfy one user instruction. The Hermes build keeps that topology explicit:

```text
Human turn
  ├─ API request 1
  ├─ API request 2
  └─ API request 3
        ↓
one top-level Turn Receipt
```

Each successful child request is accounted for independently before the turn-level total is produced. Failed attempts are preserved as failure evidence rather than silently converted into successful billed children.

## Privacy boundary

The Hermes plugin is designed to send TokenTotals accounting metadata, not conversation content.

The accounting payload excludes:

- prompt text;
- assistant answer text;
- conversation history;
- tool arguments/results;
- API keys;
- cookies;
- authorization headers; and
- hidden reasoning content.

The current CLI placement adapter uses an in-memory digest of the final answer only to bind the settled receipt to the exact response panel. The answer text is not sent to TokenTotals or written to the Turn Receipt evidence store by the plugin.

## Standard and Expanded receipts

**Standard** is the compact default. It is intended to sit immediately beneath the answer and show the essential turn economics.

**Expanded** uses the same canonical receipt object and exposes deeper telemetry, pricing provenance, child API-call count, failures, reconciliation, and thread information where available.

Changing Standard/Expanded changes presentation only. It does not create another calculator or another model call.

## Installation and user-zero testing

For the pre-release Hermes candidate, follow [`USER_GUIDE.md`](USER_GUIDE.md).

The normal test path is:

1. install/run Hermes normally;
2. run the TokenTotals Hermes Windows candidate;
3. install and enable the TurnReceipt Hermes plugin;
4. run `hermes plugins doctor`;
5. start normal `hermes chat`;
6. ask any ordinary prompt you choose; and
7. verify the Turn Receipt appears immediately beneath that exact answer.

The test prompt is not hard-wired. Any normal Hermes prompt should exercise the integration.

## Browser surfaces are not the launch claim

TokenTotals retains a built-in `/chat` page and experimental browser-integration work because they are useful engineering tools.

They are **not** the Hermes launch experience and they do not satisfy the Hermes product gate.

The built-in `/chat` surface is a controlled reference client used to test the TokenTotals engine, receipt renderer, settlement behavior, Standard/Expanded presentation, and provider plumbing.

The browser-extension track is experimental. Consumer websites do not necessarily expose API-grade same-turn telemetry, so browser work must be tested surface by surface and must never invent unavailable data.

See [`EXTERNAL_SURFACE_INTEGRATION.md`](EXTERNAL_SURFACE_INTEGRATION.md) for that experimental track.

## OpenClaw is next

After the Hermes launch gate is proven, the next planned first-class integration is OpenClaw. OpenClaw has different turn aggregation and tool-loop semantics, so it will receive its own adapter and evidence set rather than being treated as a cosmetic port of the Hermes plugin.

Hermes proof comes first. OpenClaw does not delay that gate.

## The TokenTotals engine

Hermes is the launch surface; TokenTotals remains the accounting machinery underneath it.

The engine provides:

- canonical per-turn receipt objects;
- versioned provider pricing registries;
- deterministic cost reconstruction;
- observed/derived/unavailable field semantics;
- exact receipt identities;
- append-only local turn telemetry;
- thread aggregation;
- Standard/Expanded renderers;
- CSV audit export;
- local pacing/notification support; and
- provider-specific accounting logic where defensible telemetry exists.

The accounting engine is intentionally separable from any single host so additional agent/work surfaces can use the same receipt object without creating parallel accounting systems.

## Verification and transparency

TokenTotals is evidence-driven. Failures are preserved rather than rewritten out of project history.

- [`HERMES_INTEGRATION.md`](HERMES_INTEGRATION.md) — Hermes architecture and acceptance tests
- [`USER_GUIDE.md`](USER_GUIDE.md) — literal Hermes user guide
- [`TURN_RECEIPTS.md`](TURN_RECEIPTS.md) — canonical Turn Receipt definition
- [`CALCULATION_TRANSPARENCY.md`](CALCULATION_TRANSPARENCY.md) — formulas and pricing/reconciliation rules
- [`ROADMAP.md`](ROADMAP.md) — Hermes-first launch sequence
- [`archive/verification-receipts/`](archive/verification-receipts/) — preserved verification history

## Boundaries

TokenTotals does not claim that:

- its estimates are provider invoices;
- every provider/runtime exposes every desired telemetry field;
- a green CI run proves the end-user receipt experience;
- the browser reference client is the launch product;
- an external browser adapter is complete because it can place HTML beneath an answer; or
- model capability/equivalence can be inferred from price alone.

The standard is narrower and testable:

> **A real AI transaction should be able to produce an inspectable receipt from the telemetry legitimately available to the application—without asking the AI to grade its own usage.**

## License

TokenTotals is licensed under GNU GPLv3.
