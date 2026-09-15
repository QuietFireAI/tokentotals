# IR-009 Request Context Isolation Proof

**Finding:** Shared request-scoped callback globals were unsafe under concurrent requests  
**Classification:** CONFIRMED CONCURRENCY DEFECT / REPAIRED AND REVALIDATED  
**Repair branch:** `sol/forensic-hardening`  
**Revalidation date:** 2026-09-15

## Baseline defect

The baseline proxy stored request-specific accounting data in module globals including `CURRENT_THREAD_ID`, `CURRENT_ROUTINE_FLAG`, and `CURRENT_POTENTIAL_SAVING`. A LiteLLM callback then read those shared globals later.

That design was unsafe under overlapping requests. Request A could set its values, request B could overwrite the same variables, and request A's later callback could observe request B's context.

**Impact:** spend, routine classification, and potential-savings accounting could be attributed using another in-flight request's identity or metadata.

## Repair

The hardened request path no longer uses those request-scoped globals or the old callback accounting path.

`thread_id`, `is_routine`, `potential_saving`, routed pricing, reservation amount, and reconciliation context remain local to each request and are passed explicitly into the state-management functions that need them.

The surviving module-level `LAST_LATENCY_MS` value is aggregate dashboard telemetry; it is not used for spend, thread, routine, or savings attribution and is outside this finding.

## Adversarial overlap revalidation

The 2026-09-15 IR-009 pass added two regression guards without changing production proxy logic.

The first fails if any of the baseline request-scoped globals or the old `track_cost_callback` symbol reappears in `proxy_server`.

The second creates two real overlapping HTTP requests with different request identities and different classification outcomes:

- `thread-routine` sends a short request that is classified as routine and produces a positive potential-savings estimate;
- `thread-nonroutine` sends a much larger request that is not routine and must carry zero potential-savings metadata.

A `threading.Barrier` inside the mocked upstream completion function prevents either response from completing until both requests have reached the upstream boundary. This recreates the overlap window that made the baseline shared globals unsafe.

The test instruments the explicit reservation and reconciliation calls and requires:

```text
thread-routine:
  is_routine == true
  potential_saving > 0

thread-nonroutine:
  is_routine == false
  potential_saving == 0

reconciliation thread IDs == {thread-routine, thread-nonroutine}
total_requests == 2
flagged_routine_calls == 1
```

The test passed. Each request retained its own accounting identity through reservation, upstream overlap, and reconciliation.

## Revalidation evidence

On the IR-009 overlap-test revision:

- clean regression suite: **38 passed / 0 failed**;
- CPython 3.12 compatibility check: **PASS**;
- constrained dependency install and `pip check`: **PASS**;
- request-scoped-global regression guard: **PASS**;
- simultaneous request-context isolation test: **PASS**.

No production proxy code was modified during this revalidation because the existing hardened request-local implementation satisfied the tested invariant.

## State display boundary

The state file still exposes one `active_thread_id` / `thread_spend_usd` display slot. Under overlapping requests that display slot can legitimately move to whichever thread most recently became active. This is not the old IR-009 defect and is not represented as a per-thread ledger.

IR-009 concerns whether one request's spend/routine/savings accounting can be processed using another request's request-local identity. The overlap test proves that the hardened explicit-argument path keeps those contexts separate.

## Verdict

**IR-009 — PASS: REPAIRED AND REVALIDATED.**

The baseline shared request-scoped globals are absent, and overlapping requests preserve their own accounting context through both reservation and reconciliation.
