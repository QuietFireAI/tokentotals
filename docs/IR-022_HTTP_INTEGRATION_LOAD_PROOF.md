# IR-022 — Loopback HTTP integration/load validation proof

**Classification:** EVIDENCE GAP / REVALIDATED  
**Branch:** `sol/forensic-hardening`  
**Proof revision:** `16cd9b02d73e434716768354bba310eda0caa832`  
**GitHub Actions proof run:** `34984018982`

## Why this item existed

The hardened TokenTotals suite already had strong route, state, pricing, and concurrency regression coverage, but most HTTP-path tests used FastAPI/Starlette `TestClient`. That is valuable application-level coverage, but it does not prove the production FastAPI app behaves the same way when reached through a real loopback TCP socket and a running Uvicorn server.

This was therefore an **evidence gap**, not a confirmed implementation defect.

## Test method

`tests/test_http_integration_load.py` starts the production `proxy_server.app` behind a real Uvicorn listener on an ephemeral `127.0.0.1` port. Requests are sent with `httpx` across the actual loopback HTTP/TCP boundary. Test state/config files are isolated in a temporary TokenTotals directory.

The upstream provider call remains deliberately mocked. This proves TokenTotals' local HTTP, reservation, reconciliation, and state behavior without spending provider money or confusing provider-network behavior with the local proxy invariant.

## Proof 1 — Real loopback round trip

A real HTTP POST is sent to `/v1/chat/completions` through Uvicorn. The test requires all of the following:

- HTTP 200 from the real loopback listener;
- provider assistant content passes through unchanged;
- the mocked upstream receives the expected routed model/output bound;
- `/api/status` is reachable over the same real listener;
- exactly one request is recorded;
- no unreconciled stream is created; and
- the conservative reservation is reconciled to the expected provider-usage estimate.

## Proof 2 — Concurrent loopback burst

The second test releases **24 client threads at the same time** against the real Uvicorn listener. The mocked asynchronous upstream call deliberately sleeps briefly so requests overlap rather than completing as a serial happy path.

The test requires:

- all 24 HTTP requests return 200;
- the upstream call count is exactly 24;
- `total_requests` is exactly 24;
- `current_spend_usd` equals the sum of the 24 reconciled estimates;
- no spend update is lost;
- no unreconciled stream is created; and
- the circuit breaker remains unlocked under the deliberately ample test budget.

## Result

No production-code change was required. The existing hardened single-process reservation/reconciliation implementation satisfied both real-loopback tests.

GitHub Actions run `34984018982` completed with:

- **55 passed / 0 failed** on Ubuntu / CPython 3.12;
- Linux constrained runtime smoke: PASS;
- Windows constrained runtime smoke: PASS;
- Windows constrained PyInstaller toolchain smoke: PASS; and
- `pip check`: PASS in the constrained environments.

The two IR-022 tests account for tests 54 and 55 in the current suite. Tests 52 and 53 are the 24-hour pricing-receipt freshness invariants added immediately before this item.

## Boundary

This closes the prior claim that TokenTotals had no real local integration/load validation. It does **not** prove unlimited production load, multi-process safety, provider-network reliability, or invoice parity. The burst is a controlled single-process local concurrency test with mocked provider egress. A live paid-provider canary and sustained soak/stress testing remain separate evidence items.
