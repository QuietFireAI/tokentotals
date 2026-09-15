# IR-008 Concurrent Reservation Proof

**Finding:** Concurrent requests could race the budget gate  
**Classification:** CONFIRMED SAFETY DEFECT / REPAIRED AND REVALIDATED  
**Repair branch:** `sol/forensic-hardening`  
**Revalidation date:** 2026-09-15

## Baseline defect

The baseline request path performed budget read/check logic before upstream egress without an atomic reservation transaction. Two overlapping requests could therefore observe the same remaining budget and each independently decide that it was safe to proceed.

**Impact:** individually affordable requests could collectively cross the configured local budget because the budget decision and spend commitment were separate operations.

## Repair

`config_manager.try_reserve_spend()` now performs the budget decision and reservation while holding a process-local re-entrant lock.

Inside that critical section it:

1. reads current state and configuration;
2. rejects immediately if the breaker is already locked;
3. calculates projected spend as current reserved/reconciled spend plus the new reservation;
4. locks and rejects when the projection exceeds the configured budget; or
5. commits the accepted reservation and related request/thread accounting before releasing the lock.

State writes use a temporary file plus `os.replace()` while the same process lock is held.

The proxy calls this atomic reservation operation before `litellm.acompletion()` begins, so a request that cannot reserve its conservative amount does not reach upstream execution.

## Adversarial concurrency revalidation

The 2026-09-15 IR-008 pass added a true simultaneous-thread contention test rather than relying only on sequential calls.

The test configures a `$0.10` budget and starts two worker threads. Each attempts to reserve `$0.06`.

Each reservation is affordable by itself, but both cannot fit together. A `threading.Barrier` releases both workers at the same time so they contend for the same reservation gate.

The required invariant is:

```text
accepted_count == 1
rejected_count == 1
final_spend == $0.06
total_requests == 1
is_locked == true
```

The test passed. If the read/check/write sequence were not protected by one process-local critical section, both workers could observe `$0.00` and both could be accepted, producing `$0.12` of reservations against a `$0.10` budget.

The pre-existing sequential regression test also remains: after reserving `$0.08` against a `$0.10` budget, a later `$0.03` reservation is rejected without changing accepted spend.

## Revalidation evidence

On the IR-008 contention-test revision:

- focused regression suite: **36 passed / 0 failed**;
- CPython 3.12 compatibility check: **PASS**;
- constrained dependency install and `pip check`: **PASS**;
- the simultaneous reservation contention test: **PASS**.

No production locking code was modified during this IR-008 revalidation pass because the existing hardened `try_reserve_spend()` implementation satisfied the tested in-process atomicity invariant.

## Boundary

This proof is intentionally limited to concurrency **inside one TokenTotals Python process**.

`threading.RLock` does not coordinate independent operating-system processes. Running multiple TokenTotals proxy processes against the same state file is therefore outside the proven budget invariant and remains documented as unsupported until an inter-process lock or transactional shared state mechanism is implemented and tested.

The proof also does not claim distributed coordination across machines.

## Verdict

**IR-008 — PASS: REPAIRED AND REVALIDATED.**

Concurrent request handlers in a single TokenTotals process cannot both cross the same remaining-budget window: the budget check and reservation commit are serialized under the process-local lock before upstream egress.
