# IR-016 Response Reconciliation Proof

**Finding:** IR-016 — “Every response contains everything needed to calculate spend”  
**Verdict:** UNSUPPORTED / OVERBROAD CLAIM + RECONCILIATION-EVIDENCE GAP / REPAIRED AND REVALIDATED  
**Proof revision:** 2026-09-15

## What was wrong

The baseline README stated:

> Every single API response from OpenAI, Anthropic, and Google already contains everything you need to calculate your exact spend in real time.

It then introduced the sample usage object as what the API returns in “EVERY response.”

That statement exceeded both provider variability and the implementation boundary. Usage telemetry can be absent or incomplete, especially around streaming and provider-specific response shapes. Even when token usage is present, other billable particulars can still affect provider billing.

Sequential revalidation also found a concrete runtime evidence gap. The hardened non-stream path already behaved conservatively when usage was absent: it retained the pre-flight reservation. However, unlike the streamed path, it did not record that the response remained unreconciled. The dollar reservation was safe, but the state/UI could not distinguish that completed response from one that had usable final usage telemetry.

## Why it mattered

A retained conservative reservation protects the budget, but missing reconciliation evidence can make accounting state look more settled than it actually is. TokenTotals' integrity rule is that unknown telemetry must remain visibly unknown, not merely be handled conservatively behind the scenes.

The correct invariant is therefore:

- usable provider usage → reconcile the reservation to the supported post-response estimate;
- missing/unusable provider usage → retain the conservative reservation and explicitly mark the response unreconciled.

This applies to both streamed and non-streamed responses.

## Adversarial test before repair

`tests/test_ir016_reconciliation_uncertainty.py` was added before the production repair.

It exercised three cases through the real FastAPI request path with provider egress mocked:

1. non-stream response with no usage;
2. streamed response with no final usage;
3. non-stream response with usable 7-input / 3-output token usage.

The first two tests required the conservative reservation to remain and a new total `unreconciled_responses` counter to expose the missing final telemetry. The streamed case additionally required the existing `unreconciled_streams` counter to remain as a stream-specific subset.

GitHub Actions run `34997237474` on commit `582d0fde30ded9f65c227fbeb3bb963fd5054632` failed exactly where expected:

- **2 failed / 71 passed**;
- the non-stream missing-usage response retained its reservation but had no total unreconciled marker;
- the streamed missing-usage response retained its reservation and had the old stream marker, but no total response-level marker;
- Linux runtime, Windows runtime, and Windows build-tool jobs passed.

That red run isolated the evidence gap rather than a dependency, transport, or pricing failure.

## Actual repair

### State contract

`config_manager.DEFAULT_STATE` now includes:

```text
unreconciled_responses
unreconciled_streams
```

`unreconciled_responses` is the total number of completed responses without usable final usage telemetry. `unreconciled_streams` remains the backward-compatible streamed subset.

`mark_unreconciled_response(..., stream=False)` increments the total. When `stream=True`, it also increments the stream subset. `mark_unreconciled_stream()` remains as a compatibility wrapper.

### Non-stream path

When `_usage_from_response()` returns no usable token pair, TokenTotals now:

- leaves the conservative reservation unchanged;
- increments `unreconciled_responses`;
- returns the provider response without inventing token or cost data.

### Stream path

A stream with no usable final usage still retains its reservation. It now increments both:

- `unreconciled_responses`;
- `unreconciled_streams`.

### Visibility

`/api/status` exposes both counters. The dashboard now displays **Unreconciled Responses** and explains that the conservative reservation is retained whenever usable final usage is unavailable.

### Public-claim guard

`tests/test_public_claim_integrity.py` permanently rejects the baseline “every single API response” / “EVERY response” exact-spend language and requires the current documentation to preserve the missing-telemetry boundary.

The normative rule is documented in `docs/RECONCILIATION_TELEMETRY_CONTRACT.md`.

## Revalidation result

GitHub Actions run `34997599965` on exact branch head `bf946d3e59766b078503f257c7cd2b59530d43d2` passed:

- **74/74** regression/integration tests on Ubuntu / CPython 3.12.14;
- constrained Linux runtime smoke;
- constrained Windows runtime smoke;
- constrained Windows PyInstaller/build-tool smoke;
- `pip check` in the validated environments.

The repaired tests prove:

- non-stream missing usage retains the full reservation and increments the total unreconciled counter;
- stream missing usage retains the full reservation and increments both the total and stream-subset counters;
- usable response usage reconciles normally and increments neither uncertainty counter;
- the baseline every-response/exact-spend claim cannot return unnoticed.

## Remaining boundary

Usable input/output token counts do not by themselves establish provider invoice parity. Depending on provider and transaction, billing can also depend on cache telemetry, context bands, service tier, region, modality, hosted tools, storage/runtime meters, promotions/effective dates, retries/partial responses, or account-specific terms.

IR-016 proves honest treatment of missing final usage telemetry. It does not claim that every billing dimension is implemented merely because a response contains token usage.
