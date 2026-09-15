# TokenTotals Concurrent Accounting Recheck Receipt

Date: 2026-09-15

## Scope

This receipt closes the post-response concurrent accounting item identified after dashboard telemetry truthfulness was completed.

The concern had three linked failure paths inside the normal single TokenTotals daemon process:

1. one process-global thread ID could be overwritten by a second in-flight request before the first request's cost callback completed;
2. state updates used an unlocked read-modify-write cycle against `state.json`, allowing simultaneous callbacks to overwrite one another; and
3. a single `thread_spend_usd` accumulator could not preserve per-thread totals when callbacks completed in an interleaved order such as `A -> B -> A`.

## Diagnosis

The old request path assigned every request to shared `CURRENT_THREAD_ID`. The success callback later read that same process-global value. Overlapping requests could therefore attribute a completed request's cost to whichever thread most recently changed the global.

Separately, `config_manager.update_spend()` loaded state, incremented spend/request counters, and wrote state back without serializing the transaction. Concurrent callbacks could read the same prior state and one later write could erase the other's increment.

Finally, the state schema stored only the currently active thread's displayed total. Switching from A to B reset the active accumulator; switching back to A could not recover A's earlier same-day spend.

## Decision

Keep the current single-process local-daemon architecture and make that architecture internally concurrency-safe rather than introducing a database or cross-process locking subsystem.

The repair therefore:

- carries a server-owned TokenTotals thread identifier through LiteLLM request-local metadata;
- reads that identifier from the callback's own metadata instead of shared process state;
- strips client-supplied `litellm_metadata` before injecting TokenTotals' callback metadata so the accounting identifier cannot be replaced by request input;
- serializes local config/state transactions with a process-local re-entrant lock; and
- stores daily spend by thread ID while retaining `thread_spend_usd` as the active-thread compatibility/display field.

Existing installations with a legacy active-thread total are migrated on first spend update so the already-recorded same-day active-thread amount is not discarded.

## Implementation commits

- `5c7b4711f2aa60e334f12522d05e4e648867503c` — serialized config/state transactions and introduced daily per-thread spend accounting with legacy active-thread migration.
- `2aa189b3b23109ec32b977ec65720654216d5345` — removed process-global thread attribution and carried the server-owned thread ID through LiteLLM request-local callback metadata.
- `c6157844f80e2d767ba3ce04cc559bde15aabe32` — added the initial concurrent accounting regression suite.
- `0aa50c8d06408a46de05c0a099fb6ae7adcdee82` — added explicit legacy thread-spend migration coverage and established the initial acceptance gate for this item.
- `7c3b713eb671a20742df43774e5cc2eff855250f` — documented the post-response concurrency guarantee and in-flight reservation limitation in `README.md`.
- `93372071472eb023a17e1a9826942f436eb58339` — updated the technical/security whitepaper to version `2.6-DEFENSIVE-SPEC` with explicit concurrency and pacing-boundary sections.
- `067fd8fd08b70b0ce789a070ae635123dfa55b5a` — added a regression that requires the public docs to preserve both the request-local concurrency guarantee and the current in-flight reservation limitation.

## Regression invariants

`tests/test_concurrent_accounting.py` enforces that:

1. interleaved `A -> B -> A` updates preserve A and B independently and restore A's accumulated same-day total when A becomes active again;
2. 100 parallel spend updates across multiple thread IDs do not lose current-spend increments, per-thread increments, or request-count increments;
3. callbacks use the thread identifier carried by their own request-local LiteLLM metadata, including out-of-order completion sequences;
4. client-provided `litellm_metadata` cannot replace TokenTotals' server-owned thread attribution;
5. a legacy state file's active-thread spend survives first migration into the new per-thread map; and
6. the public README and technical/security whitepaper state both the request-local concurrency protection and the fact that simultaneous preflight headroom is not yet reserved.

## Clean-machine evidence

### Runtime/accounting acceptance gate

GitHub Actions run: `35024972035`
Job: `104569695600`
Commit: `0aa50c8d06408a46de05c0a099fb6ae7adcdee82`
Result: **SUCCESS**

Clean runner stages:

- dependency install: success
- Python compile: success
- live `proxy_server` import: success
- regression suite: **98/98 passed**

Concurrency-specific tests passing:

- `test_callbacks_use_their_own_request_local_thread_metadata`
- `test_client_metadata_cannot_spoof_server_thread_attribution`
- `test_interleaved_a_b_a_preserves_each_thread_total`
- `test_legacy_active_thread_total_is_preserved_on_first_update`
- `test_parallel_updates_do_not_lose_spend_or_request_counts`

### Public-documentation follow-up gate

GitHub Actions run: `35025792967`
Job: `104572376153`
Commit: `067fd8fd08b70b0ce789a070ae635123dfa55b5a`
Result: **SUCCESS**

Clean runner stages:

- dependency install: success
- Python compile: success
- live `proxy_server` import: success
- regression suite: **99/99 passed**

Documentation/concurrency guard passing:

- `test_public_docs_state_concurrency_guarantee_and_inflight_boundary`

All existing provider-pricing, proxy-integration, legacy-removal, model-catalog, optimizer-retirement, dashboard-truthfulness, preflight-fallback, and pricing-document reconciliation regressions remained green.

## Result

**COMPLETE for post-response accounting concurrency in the current single TokenTotals daemon process, including public documentation alignment.**

Costs are no longer attributed through one shared request-global thread identifier, simultaneous callback state updates are serialized, interleaved thread activity retains independent same-day totals, and the current public documentation states both the guarantee and its limit.

## Explicitly not claimed

This receipt does not claim cross-process or distributed transactional safety. The state lock is intentionally process-local because the current product runs one local TokenTotals daemon process.

This receipt also does not claim that preflight budget headroom is reserved across multiple simultaneously in-flight requests. Two requests can still perform their preflight checks before either has posted its eventual response cost. In-flight budget reservation is a separate pacing concern and is not closed by this receipt.
