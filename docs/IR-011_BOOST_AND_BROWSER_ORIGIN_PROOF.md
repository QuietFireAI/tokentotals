# IR-011 Boost Confirmation and Browser-Origin Proof

**Finding:** HTTP budget boost could be invoked without confirmation and the first hardening pass still accepted a browser-style simple POST  
**Classification:** CONFIRMED CONTROL DEFECT / REPAIRED AND REVALIDATED  
**Repair branch:** `sol/forensic-hardening`  
**Revalidation date:** 2026-09-15

## Baseline defect

The baseline `/api/boost` handler accepted a POST with no request-supplied confirmation, immediately increased the daily budget by $5, cleared the lock, and returned success. The same baseline application also installed permissive CORS middleware allowing arbitrary origins, methods, and headers.

**Impact:** the HTTP control path did not require evidence of an intentional boost action before changing the configured spending ceiling and lock state.

## First hardening pass

The initial hardening removed the permissive CORS middleware and required the `BOOST $5` acknowledgement phrase before calling `quick_boost(5.00)`.

That was an improvement, but the IR-011 revalidation did not assume it was sufficient.

## Adversarial finding during revalidation

A new regression test simulated a browser-style cross-origin "simple" POST:

```text
POST /api/boost
Origin: https://example.invalid
Content-Type: text/plain

{"acknowledgement":"BOOST $5"}
```

The test expected the state-changing request to be rejected. Instead, the first run returned **HTTP 200** and performed the boost.

The cause was concrete: the handler called `request.json()`, which parsed the JSON-formatted body even though the request declared `Content-Type: text/plain`. A browser can send certain `text/plain` POSTs without a CORS preflight, so removing permissive CORS alone did not close this state-changing path.

This failing adversarial run is retained as evidence that the initial repair was incomplete rather than being treated as a test nuisance.

## Final repair

A shared `_read_state_action_json()` gate now sits in front of both HTTP state-changing control endpoints:

- `/api/boost`
- `/api/unlock`

The gate requires:

1. `Content-Type: application/json`;
2. syntactically valid JSON;
3. a JSON object rather than `null`, a scalar, or an array.

Only after that transport/payload gate succeeds does the endpoint evaluate its acknowledgement phrase.

For boost, the phrase is:

```text
BOOST $5
```

The API acknowledgement validator trims surrounding whitespace and compares letter case insensitively. Different wording is rejected. The phrase is an intent/confirmation gate, not a password or authentication secret.

The browser dashboard already sends `application/json`. A cross-origin browser request using `application/json` requires a CORS preflight; TokenTotals does not install permissive CORS middleware or grant the tested foreign origin. A browser-style `text/plain` simple POST is now rejected with HTTP 415 before JSON parsing or state mutation.

Native Windows tray/popup boost actions remain explicit local UI actions and call the local state manager directly; they do not rely on the HTTP endpoint.

## State-change invariant

A successful HTTP boost is intentionally narrow:

- `daily_budget_limit_usd` increases by exactly `$5.00`;
- `is_locked` becomes `False`.

It does not reset or rewrite the already-recorded:

- current spend;
- potential savings;
- active-thread identity/spend;
- total request count;
- routine-call count;
- unreconciled-stream count.

## Adversarial validation

The final IR-011 tests prove:

- cross-origin `text/plain` with the correct phrase receives HTTP 415 and cannot change state;
- an OPTIONS/CORS preflight receives no `Access-Control-Allow-Origin` or `Access-Control-Allow-Methods` grant;
- no body is rejected before mutation;
- explicit JSON `null` with `Content-Type: application/json` is rejected as a non-object payload;
- an empty JSON object, `YES`, and `BOOST $50` are rejected and preserve both config and state;
- a valid JSON `BOOST $5` request raises only the daily limit by $5 and clears only the lock flag while preserving accounting.

The same JSON-only state-action gate was applied to `/api/unlock`, and the IR-010 regression tests were extended to prove explicit JSON `null` and browser-style `text/plain` cannot unlock.

## Validation history

The evidence chain deliberately records the failures:

1. **Initial IR-011 adversarial run:** the browser-style `text/plain` request returned HTTP 200. Result: **1 failed / 43 passed**. This exposed the incomplete first repair.
2. **First post-repair run:** production rejected the unsafe transport, but two test cases used `TestClient(json=None)`, which did not actually send an `application/json` null body and therefore received HTTP 415 rather than the test's expected 400. Result: **2 failed / 43 passed**. This was a test-harness ambiguity, not a state-mutation failure.
3. The tests were corrected to send a true JSON `null` explicitly as body `null` with `Content-Type: application/json`.
4. **Corrected repair run:** **45 passed / 0 failed**; `pip check` also reported no broken requirements.

## Boundary

This repair protects the intended localhost HTTP control semantics and closes the tested browser-simple-POST route. It is **not authentication against a malicious process already running with local user access**. A deliberate local program can still call the loopback endpoint with valid JSON and the published acknowledgement phrase.

## Verdict

**IR-011 — PASS: REPAIRED AND REVALIDATED.**

The HTTP boost now requires both an appropriate JSON state-control request and explicit acknowledgement before the budget/lock transition. The browser-style simple POST that defeated the first repair is now rejected before state mutation.
