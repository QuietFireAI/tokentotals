# IR-010 Unlock Acknowledgment Integrity Proof

**Finding:** `/api/unlock` claimed acknowledgment it never verified  
**Classification:** CONFIRMED INTEGRITY DEFECT / REPAIRED AND REVALIDATED  
**Repair branch:** `sol/forensic-hardening`  
**Revalidation date:** 2026-09-15

## Baseline defect

The baseline HTTP endpoint was unconditional:

```python
@app.post("/api/unlock")
async def api_unlock():
    config_manager.unlock_circuit_breaker()
    return {"message": "Circuit breaker unlocked by user acknowledgment.", "is_locked": False}
```

The important point is not that a particular bad value could trick the endpoint. The endpoint did not read or require request-supplied acknowledgment data at all. Once a POST reached `/api/unlock`, request input was irrelevant to the decision: the handler immediately cleared the lock and then described the result as a user-acknowledged unlock.

The Windows Tk lock dialog did separately require the phrase `I UNDERSTAND`, so the acknowledgment protection existed in the native UI but not in the HTTP unlock path.

**Impact:** an HTTP caller could clear the budget lock without demonstrating the acknowledgment that the endpoint's response claimed had occurred.

## Repair

The hardened endpoint now parses the request body before any unlock state transition and passes the `acknowledgement` field through `_require_ack()`.

The accepted phrase is:

```text
I UNDERSTAND
```

The validator intentionally trims surrounding whitespace and compares letter case insensitively. For example, `"  i understand  "` is accepted. Different wording such as `YES`, `I AGREE`, or `I UNDERSTAND THIS` is rejected.

This normalization is deliberate usability behavior; the safety invariant is that the caller must submit the acknowledgment phrase before the HTTP path can clear the lock.

Only after validation succeeds does the endpoint call `config_manager.unlock_circuit_breaker()`.

The native Tk dialog independently requires the same phrase before invoking the same unlock state transition.

## What unlock does and does not do

`unlock_circuit_breaker()` changes only `is_locked` to `False` and atomically rewrites the state file under the process-local lock.

It does **not**:

- reset `current_spend_usd`;
- erase request counts or savings telemetry;
- clear unreconciled-stream accounting;
- change active-thread accounting;
- raise or otherwise change the configured daily budget.

Therefore acknowledgment releases the lock; it is not an accounting reset or budget increase. Subsequent requests remain subject to the same recorded spend and configured budget gate.

## Adversarial revalidation

The 2026-09-15 IR-010 pass added three focused regression tests.

### 1. Invalid/missing acknowledgment remains locked

The test explicitly re-locks state before each attempt and submits:

- a POST with no body;
- malformed JSON;
- an empty JSON object;
- `{"acknowledgement": "YES"}`;
- `{"acknowledgement": "I UNDERSTAND THIS"}`.

Every attempt must return HTTP 400 and `is_locked` must remain `True`.

### 2. Normalization is intentional

The test submits:

```json
{"acknowledgement": "  i understand  "}
```

and requires HTTP 200 plus an unlocked state. This records that whitespace trimming and case-insensitive comparison are intended behavior rather than an accidental bypass.

### 3. Unlock changes only lock state

Before unlock, the test seeds non-default values for:

- daily budget;
- current spend;
- potential savings;
- active-thread spend and identity;
- total request count;
- routine-call count;
- unreconciled stream count;
- lock state.

After a valid acknowledgment, the complete post-state must equal the pre-state except for `is_locked: False`, and the configuration must be byte-for-byte equivalent as parsed data.

## Revalidation evidence

On the IR-010 adversarial-test revision:

- clean regression suite: **41 passed / 0 failed**;
- CPython 3.12 compatibility check: **PASS**;
- constrained dependency install and `pip check`: **PASS**;
- missing/malformed/wrong acknowledgment rejection: **PASS**;
- intentional phrase normalization: **PASS**;
- unlock-only state mutation invariant: **PASS**.

## Verdict

**IR-010 — PASS: REPAIRED AND REVALIDATED.**

The baseline HTTP unlock was unconditional despite claiming user acknowledgment. The hardened endpoint now requires request-supplied acknowledgment before the state transition, and regression tests prove invalid input cannot unlock and valid acknowledgment does not reset accounting or change the budget.
