# In-Flight Preflight Reservation Recheck Receipt

Date: 2026-09-15
Repository: `QuietFireAI/tokentotals`

## Scope

This receipt records the diagnosis, implementation, failed acceptance attempts, correction, and final verification for TokenTotals' in-flight preflight reservation work.

The defect was narrow but important: even after post-response accounting had been serialized, two concurrent requests could still inspect the same posted local spend before either response callback settled. Both could therefore pass preflight against the same known local pacing headroom.

This item does **not** claim that TokenTotals can know a request's final full-turn cost before execution. The reservation covers the defensible preflight estimate available at admission time, currently input-side pricing. Output, reasoning/thinking, hosted tools, cache behavior, applied service tier, and other response-dependent dimensions can cause final settled cost to exceed the reservation.

## Runtime changes

### Process-local atomic reservation state

Commit `96280f2bb2fb01a20ce08b74cdaa1b432b6ef7a8` (`fix: reserve in-flight pacing headroom atomically`) added process-local ephemeral reservation tracking in `config_manager.py`.

Key invariants:

- admission check and reservation insertion occur under the same `_DATA_LOCK` used for local accounting state;
- the decision considers posted spend plus all active reservations plus the new request estimate;
- reservations are deliberately **not persisted** to `state.json`, so a daemon restart cannot strand phantom reserved dollars;
- a request that independently exceeds the configured local threshold retains the existing persistent lock behavior;
- a request blocked only by other active reservations is rejected temporarily without permanently locking the daemon;
- successful settlement persists the actual reconstructed cost before removing its reservation under the same lock;
- duplicate settlement for the same server reservation ID is ignored inside the running daemon to avoid local double-counting.

### Request-local reconciliation wiring

Commit `ad5f0ea81f53c5aa747e48d022ab77ea629bf23a` (`fix: reserve preflight headroom across concurrent requests`) wired reservations through `proxy_server.py`.

Each admitted request receives a server-generated reservation ID carried with the existing thread ID in server-owned LiteLLM request-local metadata. Client-supplied `litellm_metadata` is removed before those accounting values are injected.

Behavior:

- temporary contention returns HTTP `429` before the second request reaches LiteLLM;
- a true posted-spend/preflight threshold breach returns HTTP `403` and preserves the local lock behavior;
- upstream failure releases the reservation;
- successful cost callback reconciles the reservation with the actual post-response estimate;
- streaming cleanup releases any still-active reservation if a stream terminates before normal settlement;
- `/api/status` can distinguish posted estimated spend from active preflight commitments.

Commit `3a119b78f7ed1c86485c9fb38894665647957e81` adapted existing concurrency metadata tests so the server-owned reservation ID is tested alongside the server-owned thread ID and cannot be spoofed by client metadata.

## New regression coverage

Commit `999060cc077cb633d9afc1c2aaace727d6c9cf9a` added `tests/test_inflight_budget_reservation.py` with eight focused regressions covering:

1. two parallel reservations cannot consume the same remaining known headroom;
2. contention caused only by another active reservation is temporary and does not persistently lock TokenTotals;
3. a genuine posted-spend plus preflight-estimate threshold breach still locks;
4. settlement replaces a reservation with actual estimated cost once, without duplicate accounting;
5. actual settled cost may exceed the preflight reservation and can lock afterward;
6. upstream failure releases reserved headroom;
7. at the real endpoint, a second concurrent request is stopped before LiteLLM while the first request holds the remaining reservation capacity; and
8. status telemetry distinguishes posted spend, active reservation commitment, and the derived combined amount.

## Public documentation

Commits `65454c267106a5ef5db5ae01ecce5318892173f8` and `116f903ca978ac633f38814f0c48d698176d063d` updated the README and Technical & Security Whitepaper. The whitepaper was advanced to version `2.7-DEFENSIVE-SPEC` and documents the admission equation, reservation lifecycle, single-daemon boundary, and the distinction between preflight reservation and unknown final full-turn cost.

## Failed / unfavorable evidence preserved

### First held-request acceptance attempt hung

The first full acceptance attempt used an endpoint concurrency test with a `$1.00` local threshold and two `$0.30` requests. Both requests correctly fit under that threshold, so the second request legitimately reached the intentionally held fake upstream. The test then waited for a release event that it only intended to set after receiving the second response, creating a test deadlock.

This was a test-design error, not a runtime admission failure. Commit `e6c410aec644179098178d43f267159f3feba786` corrected the endpoint test to use a `$0.50` threshold so two `$0.30` requests cannot both be admitted.

### Corrected acceptance run: 106/107

GitHub Actions run `35029664949` reached the full regression suite after clean dependency installation, compilation, and proxy import. The new reservation tests themselves passed, including the real held-request endpoint test.

The run failed one stale optimizer-retirement assertion:

`test_default_state_and_config_do_not_expose_retired_optimizer`

That test had hard-coded the complete `update_spend` signature as exactly `cost_usd, thread_id`. The legitimate new `reservation_id` reconciliation parameter caused the failure. The assertion was updated by commit `680064d091f640dc4121bdcfb835ee0f1f81785b` to preserve its real invariant: spend accounting must not reintroduce optimizer/savings inputs.

No runtime reservation behavior was weakened to satisfy the old test.

## Final acceptance evidence

Final acceptance commit: `680064d091f640dc4121bdcfb835ee0f1f81785b`

GitHub Actions run: `35029757839`
Job: `104585236650`
Conclusion: **success**

Acceptance gate results:

- clean Python 3.12 dependency installation: passed;
- Python compileall: passed;
- live `proxy_server` import: passed;
- regression suite: **107 tests run, 107 passed**;
- runtime duration reported by unittest: `0.388s`.

## Explicit boundaries

This receipt proves the repair only within the normal single local TokenTotals daemon process. `_DATA_LOCK` and in-flight reservations are process-local; this is not represented as a cross-process or distributed transaction system.

The reservation is also not a financial guarantee, provider-account balance, credit limit, or prediction of the maximum cost of the next turn. It prevents concurrent requests from reusing the same **known preflight estimate capacity**. Final post-response cost can be higher when billing-relevant dimensions become observable only after execution.

Historical failures and the test-design correction above are intentionally retained as part of the verification record.