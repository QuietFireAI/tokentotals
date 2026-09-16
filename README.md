# TokenTotals

> **Turn Receipts for Hermes.**
>
> Use Hermes normally. When a completed answer settles, TokenTotals is designed to place an independent Turn Receipt directly beneath that answer.

**Launch target:** Hermes Agent on Windows  
**Status:** pre-release candidate pending user-zero live proof  
**Next integration after Hermes:** OpenClaw  
**TokenTotals `/chat` and browser-extension work:** reference/testing tracks, not the launch product

- Product: https://tokentotals.com
- Receipt: https://turnreceipt.com
- Turn Receipt reference: https://turnreceipts.com
- TokenTotals support: support@tokentotals.com
- Turn Receipt support: support@turnreceipts.com
- Project support: support@quietfireai.com

## Project evolution

TokenTotals' **initial testing concept** used frontier-model/browser workflows to prove the Turn Receipt idea end to end. That work was useful: it exercised the accounting engine, canonical receipt object, pricing logic, ledger, renderer, settlement behavior, and an initial browser/reference presentation path.

The limiting factor was practical, not conceptual: **continuing to validate the browser/frontier-model path at the evidence standard required by TokenTotals became too cost-intensive for this project on our end.** Rather than lower the proof standard, rely on brittle assumptions, or keep spending against an expensive test surface, the launch path was deliberately pivoted to **Hermes Agent**.

Hermes gives TokenTotals a much cleaner integration environment: stable turn/request identities, documented observer hooks, normalized usage telemetry, and room to test simple turns, retries, tools, and multi-call agent behavior without depending on a closed consumer web UI.

The browser/frontier work is **not abandoned and is not being rewritten as a failure**. It remains an initial testing/reference concept and can continue as resources and defensible telemetry paths allow. It is simply no longer the launch dependency.

The current sequence is therefore:

```text
Initial browser/frontier testing
        ↓
accounting + receipt machinery proven in controlled surfaces
        ↓
resource/cost boundary reached for rigorous frontier testing
        ↓
Hermes-first launch integration
        ↓
OpenClaw integration next
        ↓
browser/frontier work may continue as a later adapter track
```

This is a resource-allocation and evidence-quality decision, not a claim that browser integrations are impossible.

## What TokenTotals is

TokenTotals is a local accounting engine for AI turns. For the Hermes launch, a Hermes plugin observes Hermes' own turn/request lifecycle telemetry and sends privacy-limited usage evidence to the local TokenTotals engine. TokenTotals then performs deterministic accounting and renders the receipt.

The model does **not** calculate its own receipt. Receipt generation does not require a second LLM call.

**The data is often there. The usable receipt usually isn't. TokenTotals makes one.**

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

The Hermes integration candidate currently has automated evidence for:

- Hermes-specific contract tests;
- successful loading by a pinned real Hermes installation through Hermes' own plugin doctor;
- Windows TokenTotals candidate build and packaged smoke tests; and
- standalone Hermes plugin packaging.

The complete TokenTotals regression suite remains a required release gate. A Hermes-first documentation rewrite exposed documentation-contract failures in that suite; those failures are preserved and reconciled before the branch can be called green.

Those automated checks are necessary, but they are **not the final product proof**.

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

A Turn Receipt is an independent usage estimate, not a provider invoice. Provider account and final invoice records remain authoritative.

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

One thread can contain multiple models. TokenTotals preserves independent per-model/child evidence rather than pretending a mixed-model thread came from one model.

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

The local turn ledger does not persist prompt text, response text, API keys, cookies, authorization headers, or hidden reasoning content. The current CLI placement adapter uses an in-memory digest of the final answer only to bind the settled receipt to the exact response panel. The answer text is not sent to TokenTotals or written to the Turn Receipt evidence store by the plugin.

## Local ledger and evidence semantics

Completed turn telemetry is stored locally in `~/.tokentotals/turns.jsonl`. Runtime writes are append-only and idempotent by turn identity, but the file is **not represented as immutable or tamper-evident**. It is a local operational ledger, not a cryptographic notarization system.

Observed, derived, fallback, and unavailable values remain distinguishable. Missing is not zero, and an explicit observed zero is not interchangeable with missing telemetry.

## Request-local concurrency and in-flight accounting

TokenTotals keeps server-owned accounting attribution **request-local** so concurrent turns do not borrow another request's thread or reservation metadata.

Before an admitted provider request leaves the machine, TokenTotals can reserve an **in-flight** preflight estimate based on the input known at admission time. That reservation protects the same local pacing capacity from being spent simultaneously by concurrent requests. When the turn settles, the reservation is released and replaced with the defensible full-turn cost, including output and other billable components that become known only after the provider response.

A local pacing threshold is a local control on requests routed through TokenTotals. It is **not provider-account clearance**, does not represent an external account balance, and does not guarantee what a provider will ultimately invoice.

TokenTotals does **not** silently replace the model or provider requested by the caller. Model selection remains explicit; retired optimizer behavior is not part of the active runtime.

## Upstream network boundary

**Upstream egress exists.** TokenTotals itself keeps its accounting state local, but permitted requests still leave the local machine when the selected provider or remote runtime must be contacted. “Local” describes the TokenTotals control/accounting plane; it does not mean the chosen AI provider runs locally.

A genuinely self-hosted model can of course avoid a per-token provider request, but that is a property of the selected runtime/model path, not a blanket TokenTotals network guarantee.

## Versioned Provider Rules, Not a Second Billing Portal

TokenTotals uses versioned provider-specific accounting rules and only produces dollar estimates when the required basis is defensible. The repository-contained pricing registries are:

- `pricing/openai_registry.json`
- `pricing/anthropic_registry.json`
- `pricing/google_registry.json`

Those files are runtime accounting inputs, not claims that a README table is a provider's current invoice schedule. Any static price shown in screenshots, examples, or descriptive UI material is **illustrative UI copy, not a live pricing snapshot**.

Provider-native/account telemetry remains attributed to its source. TokenTotals does not silently average conflicting numbers or turn an unavailable billing dimension into a guessed zero. See [`CALCULATION_TRANSPARENCY.md`](CALCULATION_TRANSPARENCY.md) for the formulas, component treatment, fallback rules, and limitations.

## Standard and Expanded receipts

**Standard Receipt** is the compact default. It is intended to sit immediately beneath the answer and show the essential turn economics.

**Expanded Receipt** uses the same canonical receipt object and exposes deeper telemetry, pricing provenance, child API-call count, failures, reconciliation, and current thread information where available.

Changing Standard/Expanded changes presentation only. It does not create another calculator or another model call.

The formal receipt definition is in [`TURN_RECEIPTS.md`](TURN_RECEIPTS.md).

## Local reference client and API

The Hermes experience is the launch target, but the built-in local `/chat` page remains a useful controlled reference client for the same engine and renderer.

`TokenTotals.exe` binds to an available loopback port from `8080` through `8089`. When the first port is available, the reference chat surface is:

`http://127.0.0.1:8080/chat`

Relevant receipt/telemetry surfaces include:

- `/api/turn-receipt/<turn_id>`
- `/api/turn-receipt/<turn_id>/render?mode=standard`
- `/api/turn-receipt/<turn_id>/render?mode=expanded`
- `/api/telemetry/thread?thread_id=<id>`

Successful proxy responses use the server-owned `X-TokenTotals-Receipt-ID` binding where applicable. The receipt is rendered separately; provider/model response content is not modified to append receipt text.

## Desktop support boundary

The validated desktop packaging target for this pre-release line is **desktop-windows**. TokenTotals does not currently claim a validated macOS or Linux desktop release. Python/source use on other systems is a separate support question and must not be confused with a tested packaged desktop release.

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

## Browser surfaces are testing/reference work

TokenTotals retains a built-in `/chat` page and experimental browser-integration work because they are useful engineering tools and may become future integrations.

They are **not** the Hermes launch experience and they do not satisfy the Hermes product gate.

The built-in `/chat` surface is a controlled reference client used to test the TokenTotals engine, receipt renderer, settlement behavior, Standard/Expanded presentation, and provider plumbing. It is not the intended user destination.

The browser/frontier track is best understood as the project's **initial test concept**. It helped prove the underlying receipt machinery, but sustained frontier-model validation became too cost-intensive for the project to keep using as the primary launch path. Work on that track can continue later; it is no longer the thing that has to succeed before TokenTotals can launch.

See [`EXTERNAL_SURFACE_INTEGRATION.md`](EXTERNAL_SURFACE_INTEGRATION.md) for that testing/research track.

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
- [`MODEL_COMPARISON_MATRIX.md`](MODEL_COMPARISON_MATRIX.md) — provider mechanics and registry-source map
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

GNU GPLv3.