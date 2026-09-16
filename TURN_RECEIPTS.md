# Turn Receipts for AI

**Project term:** Turn Receipt  
**Reference implementation:** TokenTotals by QuietFireAI  
**Definition established in this repository:** 2026-09-15  
**Individual receipt:** https://turnreceipt.com  
**Concept site:** https://turnreceipts.com  
**Product site:** https://tokentotals.com

## Definition

TokenTotals formalizes the term **Turn Receipt** for an inspectable record of a completed AI turn that separates what was observed from what was derived, preserves what remains unavailable, reconciles the available telemetry, records the pricing basis used for an estimate, and makes the resulting arithmetic checkable.

A Turn Receipt is intended to answer a narrow set of questions about one AI turn:

> **What happened on this turn, what did the provider actually expose, what did the application derive from it, what could not be established, and can the arithmetic be checked?**

TokenTotals is the open-source reference implementation of this definition in this repository.

## Core principles

A TokenTotals Turn Receipt follows these principles:

1. **Observed is not derived.** Provider/client/runtime telemetry is preserved separately from values calculated by TokenTotals.
2. **Missing is not zero.** A value that cannot be defensibly established remains unavailable rather than being manufactured as `0`.
3. **Show the math.** Derived values should have an inspectable formula, input basis, and—when cost is involved—the pricing rule used.
4. **Reconcile instead of hiding disagreement.** Provider-reported totals and TokenTotals-reconstructed totals can coexist, with residual or unclassified usage preserved when they do not reconcile.
5. **Keep model and provider identity explicit.** Requested, canonical, and provider-observed identities remain distinguishable when the telemetry supports them.
6. **Preserve the turn as evidence.** The local ledger keeps a durable per-turn telemetry record rather than relying only on a transient display value.
7. **Do not turn an estimate into an invoice claim.** TokenTotals can reconstruct a best-effort cost estimate from exposed telemetry and documented rules; the provider account and final invoice remain authoritative.
8. **Minimize retained content.** The TokenTotals ledger is telemetry-focused and does not intentionally persist prompt text, response text, API keys, or hidden reasoning content.

## What a Turn Receipt can contain

Depending on provider/model telemetry and the completeness of the applicable pricing rules, a Turn Receipt can preserve or derive:

- turn and thread identifiers and timestamp;
- requested, canonical, and provider-observed model identity;
- provider identity and pricing-registry verification date;
- input, uncached input, cached input, cache-write/create, output, reasoning/thinking, tool-input, modality, and supported server-tool usage;
- provider-reported total tokens;
- TokenTotals reconstructed total tokens;
- reconciliation delta and residual/unclassified tokens;
- observed/derived/unavailable basis labels;
- estimated cost components and reproducible effective rates where the persisted units and component dollars support them;
- total estimated turn cost;
- estimate completeness and explicit cost basis;
- a visible estimate-status indicator when TokenTotals uses a fallback, known-list-equivalent, or unavailable cost basis;
- latency or wall-clock timing where exposed or measured; and
- thread-level aggregate telemetry when a deeper presentation requests it.

No Turn Receipt is required to contain every field. Provider telemetry differs by provider, model, API surface, tier, and time. Absence is represented as absence.

## Standard and Expanded presentation

TokenTotals uses one canonical Turn Receipt object and can render it at different levels of detail. The presentation mode does not create a second accounting path and does not recalculate the model response.

**Standard** is the default inline presentation. It is deliberately compact and turn-scoped: receipt identity, provider/model identity, the key token counts available for that turn, estimated turn cost, estimate status/basis, and pricing-registry verification date.

**Expanded** renders the same Turn Receipt with deeper turn telemetry and pricing detail, including observed/derived/unavailable basis labels, reconciliation fields, pricing components and reproducible effective rates where available. It can also include the **current thread aggregate at render time**—turn count, cumulative estimated cost with coverage, and per-model breakdown. That thread aggregate is a current summary, not a claim that it was frozen into the historical turn when the receipt was first created.

A user can choose Standard or Expanded as the default display. Changing the display mode changes presentation only; it does not change the canonical receipt or the underlying ledger record.

## In-conversation rendering and receipt binding

TokenTotals includes a local chat surface where the interaction is presented as:

> **question → answer → Turn Receipt → repeat**

The model's normal response body is not silently modified to contain TokenTotals telemetry. Instead, TokenTotals assigns the request a server-owned turn identifier, returns that identifier as `X-TokenTotals-Receipt-ID`, settles the turn into the ledger, and lets the presentation layer retrieve the exact canonical receipt for that identifier. This prevents overlapping turns in the same thread from being matched by a fragile “latest receipt” guess.

The receipt can then be rendered directly beneath the answer in a compatible TokenTotals-powered conversation surface. No popup or separate dashboard is required for that flow. The dashboard remains available as a separate diagnostic and aggregate telemetry surface.

The local receipt APIs are:

```text
GET /api/turn-receipt?thread_id=<id>
GET /api/turn-receipt/<turn_id>
GET /api/turn-receipt/<turn_id>/render?mode=standard
GET /api/turn-receipt/<turn_id>/render?mode=expanded
```

The local Turn Receipt chat surface is available at `/chat` on the configured TokenTotals port.

## Estimate-status disclosure

A Turn Receipt must not make uncertainty look like normal precision.

- A complete provider-registry reconstruction can be labeled **TokenTotals estimate**.
- A secondary LiteLLM cost source is labeled **Fallback estimate** and explains that the result may be higher or lower than the provider invoice.
- A known list-equivalent estimate is visibly identified as incomplete/list-equivalent.
- If no defensible cost can be established, the receipt reports cost as unavailable rather than `$0`.

## Turn Receipt versus observability

A Turn Receipt is deliberately narrower than a full tracing, evals, routing, or enterprise-observability system. Those systems can answer broader questions about application behavior, chains, tools, quality, or infrastructure.

The Turn Receipt focuses on the completed AI turn as an inspectable evidence object. It can coexist with those systems and be consumed by them.

## Turn Receipt versus provider billing

A Turn Receipt is **not** a provider invoice, account balance, credit line, or statement of authoritative funds remaining.

TokenTotals combines legitimately exposed telemetry with versioned public pricing references and known provider-specific rules. When a billing-relevant dimension is unavailable or unresolved, the receipt should disclose that limitation rather than imply invoice-exact precision.

For the current calculation rules and formulas, see [`CALCULATION_TRANSPARENCY.md`](CALCULATION_TRANSPARENCY.md).

## Terminology and provenance

This repository deliberately uses and formalizes **Turn Receipt** as the name for the per-turn evidence construct described above. The project does **not** claim that no person or project ever used the ordinary English words “turn receipt” before this definition.

The provenance claim is narrower and checkable: TokenTotals publicly defines this specific construct, implements it, documents its boundaries, tests the behavior behind it, and preserves the repository history showing when the definition entered the project.

That distinction is intentional. The value of the term should come from a useful definition and working implementation, not from an unverifiable first-use claim.

## Canonical project surfaces

- **Individual Turn Receipt:** https://turnreceipt.com
- **Turn Receipt concept:** https://turnreceipts.com
- **TokenTotals product:** https://tokentotals.com
- **Source code and verification history:** https://github.com/QuietFireAI/TokenTotals
- **Turn Receipt / documentation contact:** support@turnreceipts.com
- **TokenTotals product support:** support@tokentotals.com
- **QuietFireAI general contact:** support@quietfireAI.com

## Short form

When a compact definition is needed:

> **A Turn Receipt is an inspectable per-turn record that separates observed telemetry, derived calculations, unavailable information, reconciliation results, pricing basis, and estimated cost so an AI turn can show its work.**