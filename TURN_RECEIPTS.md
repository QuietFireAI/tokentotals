# Turn Receipts for AI

**Project term:** Turn Receipt  
**Reference implementation:** TokenTotals by QuietFireAI  
**First launch surface:** Hermes Agent  
**Next planned surface:** OpenClaw  
**Individual receipt:** https://turnreceipt.com  
**Turn Receipt reference:** https://turnreceipts.com  
**Product:** https://tokentotals.com

## Definition

A **Turn Receipt** is an inspectable record of one completed AI turn that separates observed telemetry from derived calculations, preserves unavailable information as unavailable, records the pricing/accounting basis used, and makes the resulting arithmetic checkable.

This document formalizes the term **Turn Receipt** for the TokenTotals project and its integrations. The term refers to the receipt object and evidence contract described here; it does not imply ownership of ordinary uses of the words “turn” or “receipt.” TokenTotals does **not** claim that no person or project ever used those ordinary words or similar phrases before this project.

For the Hermes launch, the intended experience is:

> **use Hermes normally → Hermes answer → Turn Receipt directly beneath that answer**

The receipt is calculated independently from the model answer. The model is not asked to report or calculate its own usage or cost, and receipt generation does not require a second LLM call.

## Public receipt contract

The public receipt behavior is intentionally narrow and testable:

- **Observed is not derived.** Runtime/provider telemetry remains distinguishable from TokenTotals calculations.
- **Missing is not zero.** If a field cannot be established, it remains unavailable.
- **Show the math.** Derived values should be reproducible from recorded inputs and pricing/accounting rules.
- Provider account and final invoice remain authoritative for provider billing.
- **Standard** is the default inline presentation beneath the completed answer.
- **Expanded** renders the same Turn Receipt with deeper telemetry, provenance, child-transaction detail, and the current thread aggregate at render time where available.
- `X-TokenTotals-Receipt-ID` is the server-owned response binding used by supported TokenTotals proxy surfaces to identify the settled receipt for that turn.
- A fallback estimate remains explicitly labeled as a fallback estimate; it is not silently presented as provider-native billing telemetry.

Standard and Expanded are two views of one canonical receipt object. Expanded thread context is contextual information loaded at render time; it does not rewrite the historical turn record.

## Launch-surface history

The first TokenTotals test concept used frontier-model/browser workflows. That work helped establish the receipt object, accounting engine, renderer, settlement behavior and in-conversation presentation model.

Continuing to validate that path across frontier-model/browser surfaces at the required evidence standard became **too cost-intensive for the project on our end**. TokenTotals therefore moved the first launch integration to Hermes rather than weakening the proof standard or keeping the browser path as a mandatory launch dependency.

That earlier browser/frontier work remains a testing/reference track and may continue. Hermes is the first launch surface because its documented lifecycle and telemetry provide a cleaner environment for proving the receipt as a real transaction artifact. OpenClaw is planned next.

## Core principles

TokenTotals follows these rules:

1. **Observed is not derived.** Runtime/provider telemetry remains distinguishable from TokenTotals calculations.
2. **Missing is not zero.** If a field cannot be established, it remains unavailable.
3. **Show the math.** Derived values should be reproducible from recorded inputs and pricing/accounting rules.
4. **Bind the receipt to the real turn.** Correlation must use stable transaction identity, not timing proximity.
5. **Preserve multi-call structure.** One human turn may contain several provider transactions; those child transactions should remain inspectable.
6. **Do not modify the model answer to make the receipt exist.** The answer and accounting object remain separate.
7. **Do not ask the model to grade itself.** Receipt accounting is out-of-band from model generation.
8. **Do not turn an estimate into an invoice claim.** Provider account and final invoice remain authoritative.
9. **Minimize retained content.** Accounting does not require storing prompt text, answer text, credentials, or hidden reasoning.

## Hermes receipt topology

Hermes is the first launch surface because it exposes stable turn/request identities and normalized observer telemetry.

A simple turn can look like:

```text
Hermes turn
  └─ provider API request
        ↓
Turn Receipt
```

A tool/agent turn can look like:

```text
Hermes turn
  ├─ provider API request 1
  ├─ provider API request 2
  └─ provider API request 3
        ↓
one top-level Turn Receipt
```

TokenTotals accounts for each successful child request independently when sufficient telemetry exists, then rolls those children into the top-level human-turn receipt.

A failed/retried API attempt remains failure evidence. It is not silently rewritten as a successful billed child.

## What a Turn Receipt can contain

Depending on the telemetry exposed for that transaction, a Turn Receipt can contain:

- receipt, session/thread and turn identity;
- provider and model identity;
- input and output tokens;
- cached-input/cache-write categories;
- reasoning/thinking categories when defensibly observable;
- provider-reported token totals;
- reconstructed totals and reconciliation deltas;
- observed / derived / unavailable basis labels;
- estimated child and turn-level cost;
- pricing basis and completeness;
- timing information; and
- in Expanded mode, child transaction evidence and deeper thread economics.

No receipt is required to contain every field. Provider/runtime telemetry varies. Absence is represented as absence.

## Standard and Expanded presentation

TokenTotals uses one canonical receipt object with two presentation depths.

**Standard** is the default inline presentation intended to sit directly beneath the completed answer.

**Expanded** renders the same Turn Receipt and exposes deeper telemetry, provenance, reconciliation, child API-call information and the current thread aggregate at render time where available.

Changing presentation does not change the accounting object and does not trigger another model call.

The ordinary compact footer is simply:

```text
TurnReceipt.com
```

Receipt identity remains available in the underlying object/export and Expanded detail.

## Answer integrity

The model answer remains the model answer.

For Hermes, the normal Hermes response is rendered first. The TurnReceipt integration then renders the receipt underneath it from the separately settled TokenTotals accounting object.

TokenTotals does not append receipt text into raw provider response bytes.

## Same-turn binding

A receipt only means something if it belongs to the exact transaction shown above it.

The Hermes integration therefore relies on Hermes' stable lifecycle identifiers rather than a “most recent response” guess. The integration can preserve:

- Hermes session identity;
- Hermes turn identity;
- provider API-request identity; and
- API-call ordering/count information.

The top-level TokenTotals receipt identity is derived from the stable Hermes turn identity. On supported TokenTotals proxy surfaces, the `X-TokenTotals-Receipt-ID` binding exposes that server-owned receipt identity without modifying the model answer.

## Cost semantics

A Turn Receipt can report a cost estimate only when TokenTotals has a defensible basis for doing so.

A top-level Hermes turn can be classified as:

- complete child-transaction sum when all successful child requests are defensibly priced;
- partial child-transaction sum when only part of the cost can be reconstructed; or
- unavailable when no defensible cost can be established.

Unavailable cost is not displayed as `$0.00`.

When provider-specific reconstruction is incomplete and a defensible secondary basis exists, TokenTotals may show a clearly labeled fallback estimate. A fallback estimate is not relabeled as observed provider billing.

Every Turn Receipt remains an independent estimate, not a provider invoice. Provider account and final invoice remain authoritative.

## Privacy boundary

The Hermes accounting payload is designed around usage metadata, not conversation content.

It excludes:

- prompt text;
- answer text;
- conversation history;
- tool arguments/results;
- API keys;
- cookies;
- authorization headers; and
- hidden reasoning content.

The current CLI placement adapter may use an in-memory hash of the answer only to bind a settled receipt to the exact response panel. The answer text itself is not sent to TokenTotals or stored in the Hermes evidence record by this integration.

## Hermes launch gate

The Hermes build is not promoted to a finished launch merely because code exists or CI is green.

The live gate is:

1. user sends a normal prompt in normal Hermes;
2. Hermes produces its normal answer;
3. that answer is unchanged;
4. the matching Turn Receipt appears directly beneath it;
5. no second LLM call creates the receipt;
6. the receipt is tied to the same Hermes turn/request evidence;
7. missing telemetry remains unavailable;
8. a multi-call/tool turn produces one top-level receipt with inspectable child accounting; and
9. disabling TokenTotals/TurnReceipt leaves Hermes usable normally.

Until that live user-zero behavior is demonstrated, the Hermes build remains a candidate.

## Browser/reference surfaces

TokenTotals also contains a built-in `/chat` client and experimental browser-integration work.

Those surfaces are useful for engineering tests, but they are **not the Hermes launch claim**.

The built-in `/chat` surface is a controlled reference harness for exercising the TokenTotals engine and renderer.

The browser/frontier-model path was the project's initial test concept. It remains useful work, but sustained validation became too cost-intensive for the project's current resources to keep it as the first-launch dependency. Work may continue there after the Hermes/OpenClaw path is established.

## OpenClaw next

After Hermes is proven, OpenClaw is the next planned first-class integration. Its adapter will use the same canonical TokenTotals receipt principles, but OpenClaw-specific lifecycle and aggregation behavior must be tested independently.

## Short form

> **A Turn Receipt is an independently calculated, inspectable record of one completed AI turn that shows what was observed, what was derived, what remains unavailable, and how the turn's usage and estimated cost were accounted for.**
