# TokenTotals Reconciliation Telemetry Contract

**Status:** Normative hardening contract  
**Revision:** 2026-09-15

## Governing rule

TokenTotals must never assume that every provider response contains complete usage or billing telemetry.

For every accepted chat-completion request, exactly one of these accounting outcomes applies:

1. **Usable provider usage is observed.** TokenTotals reconciles the conservative pre-flight reservation to the supported post-response estimate derived from that observed usage and the applicable verified pricing rules.
2. **Usable provider usage is unavailable.** TokenTotals keeps the conservative pre-flight reservation on the books and marks the completed response as unreconciled.

Missing usage must not be converted to zero cost, an invented token count, a guessed final cost, or an apparently reconciled transaction.

## Response modes

The rule applies to both non-stream and streamed responses.

- `unreconciled_responses` is the total count of completed responses that lacked usable final usage telemetry.
- `unreconciled_streams` is retained as a backward-compatible subset identifying how many of those unreconciled responses were streamed.

A stream without final usage therefore increments both counters. A non-stream response without usage increments only the total response counter.

## Reservation behavior

An unreconciled response retains the conservative pre-flight reservation that was committed before upstream execution. The absence of final usage does not release budget headroom.

## Claim boundary

TokenTotals must not claim that:

- every API response contains all information required to calculate spend;
- every response contains usage telemetry;
- every accepted response can be reconciled to exact spend;
- observed token usage alone establishes provider invoice parity.

The strongest allowed language is limited to what the transaction actually supports: observed usage is used when usable; otherwise the transaction remains explicitly unreconciled and conservative.

## Regression requirements

Tests must cover at least:

- a non-stream response with no usage retaining its reservation and incrementing `unreconciled_responses`;
- a stream with no final usage retaining its reservation and incrementing both `unreconciled_responses` and `unreconciled_streams`;
- a response with usable input/output usage reconciling normally without incrementing either uncertainty counter;
- public claim surfaces rejecting the baseline every-response / exact-spend wording.

## Billing boundary

Even a response with usable token counts may lack other billable particulars such as cache tiers, service modes, regional modifiers, modalities, hosted tools, storage/runtime charges, promotions, retries, or account-specific terms. Reconciliation therefore means the best supported TokenTotals estimate from the represented telemetry and pricing rules, not a guarantee of invoice identity.
