# IR-023 — Sustained concurrency / soak envelope

**Classification:** EVIDENCE GAP / REVALIDATED  
**Date:** 2026-09-15  
**Branch:** `sol/forensic-hardening`

## Finding

IR-022 proved one real Uvicorn loopback round trip and one 24-request overlapping burst, but it did not characterize whether repeated concurrent traffic would accumulate accounting drift over time. That was an evidence gap, not a confirmed defect.

The specific risk was cumulative state corruption: a system can survive one burst yet still lose a request count, lose or double-apply a reconciliation delta, create an unreconciled stream, or trip the breaker incorrectly after repeated reservation/reconciliation cycles.

## Test applied

`tests/test_http_integration_load.py` now contains a bounded sustained-concurrency test that runs the production FastAPI app behind a real Uvicorn listener on an ephemeral `127.0.0.1` port.

The provider call is mocked so the test isolates TokenTotals' local HTTP, reservation, reconciliation, and persistent state behavior without spending provider money.

The soak envelope is:

- 8 successive rounds;
- 32 simultaneous client requests per round;
- 256 total real loopback HTTP requests;
- one TokenTotals process;
- one ephemeral Uvicorn listener;
- fixed provider usage telemetry of 10 prompt tokens + 5 completion tokens per request;
- exact accounting assertions after every round, not only at the end.

Each round uses a barrier to release all 32 clients together. The mocked upstream call delays briefly so the requests remain overlapped rather than degenerating into a serial happy path.

## Invariants enforced after every round

After rounds 1 through 8, the test requires all of the following to be true:

1. every HTTP request returned 200;
2. the mocked upstream call count equals the exact cumulative request count;
3. `total_requests` equals the exact cumulative request count;
4. `current_spend_usd` equals the exact sum of all reconciled per-request estimates;
5. `unreconciled_streams == 0`;
6. `is_locked == False`;
7. `/api/status` reports the same cumulative request count and spend as persisted state.

This matters because a defect in an early round cannot be hidden by a correct-looking final state.

## Result

No production-code change was required.

GitHub Actions run `34985140692` on commit `0c37ea2533e63788d085c427b3d1bae4739a7941` passed the complete regression/integration suite with:

- **56 passed / 0 failed**;
- CPython 3.12.14;
- `pip check`: PASS;
- Linux runtime smoke: PASS;
- Windows runtime smoke: PASS;
- Windows constrained PyInstaller/build-tool smoke: PASS.

The 256-request soak preserved exact request and spend accounting at every checkpoint.

## What this proves

Within the tested single-process envelope, repeated concurrent real-loopback HTTP traffic did not produce cumulative accounting drift, lost updates, accidental lock state, or unreconciled-stream leakage.

## What this does not prove

This is a bounded integrity soak, not a production-capacity benchmark. It does **not** establish:

- unlimited throughput or a maximum requests-per-second rating;
- behavior above 32 simultaneous requests;
- behavior beyond 256 total requests in one run;
- multi-process safety;
- long-duration hours/days soak behavior;
- provider-network behavior or paid-provider reliability;
- invoice parity.

The process-local locking boundary remains unchanged: multiple independent TokenTotals processes against the same state file are outside the proven invariant.
