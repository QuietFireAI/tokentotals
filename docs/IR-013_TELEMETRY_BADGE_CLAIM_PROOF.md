# IR-013 Turn-by-Turn Telemetry Badge Claim Proof

**Finding:** public documentation claimed a turn-by-turn in-context telemetry badge that the implementation did not provide  
**Classification:** UNSUPPORTED CLAIM / REPAIRED AND REVALIDATED  
**Repair branch:** `sol/forensic-hardening`  
**Revalidation date:** 2026-09-15

## Baseline claim

The baseline README contained a section titled:

```text
The Hook (Turn-by-Turn Chat Telemetry Badge)
```

and stated that every developer turn or agent interaction rendered a live telemetry badge directly in the working context.

## What the implementation actually did

The reviewed implementation provided:

- a localhost FastAPI proxy;
- a separate browser dashboard;
- a Windows tray/modal UI;
- request accounting and budget controls around `/v1/chat/completions`.

It did not contain an IDE/chat integration adapter that injected TokenTotals telemetry into every assistant turn.

The non-stream proxy path returns the upstream response object (`model_dump()` when available) after accounting reconciliation. The streaming path forwards provider chunks as SSE. No TokenTotals badge-decoration step was identified in that lifecycle.

**Impact:** the baseline README described a user-visible integration surface that was not implemented. A user could reasonably expect TokenTotals telemetry to appear inside their IDE/chat conversation when the repository only supplied the separate dashboard/tray surfaces.

## Repair

The unsupported implemented-feature claim was removed. The current README explicitly states:

```text
It does not inject a telemetry badge into every IDE/chat turn.
```

TokenTotals can later add such an adapter, but it must be implemented and tested before the public documentation may describe it as an available feature.

No production proxy feature was added merely to preserve the old claim.

## Regression proof

IR-013 adds two independent guards.

### 1. Public-claim guard

`tests/test_public_claim_integrity.py` rejects the baseline claim language, including the turn-by-turn badge heading and statements that every developer turn renders a badge. It also requires the current README to retain the explicit non-implementation statement.

This means the unsupported feature cannot quietly return through marketing/documentation alone.

### 2. Response pass-through guard

`tests/test_proxy_guardrails.py` mocks an upstream non-stream response containing known assistant text and sends it through the real FastAPI endpoint. The test requires the returned assistant content to remain exactly the provider text and requires that no `TokenTotals` decoration appear in the returned payload.

This does not prohibit a future explicit integration adapter. It records the behavior of the current proxy: accounting/control occurs around the transaction, not by silently rewriting assistant content.

## Validation evidence

The IR-013-specific revision passed **48/48** tests. The later pricing stop-line revision retained both IR-013 guards and passed the broader **51/51** suite.

Final revalidation evidence includes:

- clean regression suite: **51 passed / 0 failed**;
- CPython 3.12 compatibility check: **PASS**;
- constrained dependency install and `pip check`: **PASS**;
- unsupported badge public-claim guard: **PASS**;
- non-stream response pass-through test: **PASS**;
- Linux runtime smoke: **PASS**;
- Windows runtime smoke: **PASS**;
- Windows constrained build-tool smoke: **PASS**.

No production proxy change was required for IR-013.

## Boundary

This finding does not say an in-context telemetry adapter is a bad feature. It says TokenTotals must not claim that integration until an actual host/IDE/chat adapter exists and has tests proving how and where it renders telemetry.

## Verdict

**IR-013 — PASS: REPAIRED AND REVALIDATED.**
