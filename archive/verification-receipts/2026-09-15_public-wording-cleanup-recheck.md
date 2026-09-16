# Public Wording Cleanup Recheck Receipt

Date: 2026-09-15
Repository: `QuietFireAI/tokentotals`

## Status

Complete and verified.

## Diagnosis

Launch-facing wording had drifted behind the runtime/product boundary already established elsewhere in the repository. The stale language was concentrated in current public/runtime surfaces rather than historical evidence:

- `README.md` still used `zero-egress`, `In Budget`, `dollar headroom`, daily-budget/cap wording, and related financial-clearance phrasing;
- `proxy_server.py` still returned user-facing 403/429 messages such as `protect your card`, `daily budget`, `Outgoing calls locked`, and `available local headroom`;
- `generate_launch_calendar.py` and the generated `TokenTotals_30Day_Launch_Plan.ics` still advertised a `hard $5/day ceiling` and `Zero-egress` shorthand;
- the README platform badge claimed Windows/macOS/Linux even though the current desktop tray application is Windows-specific (`winsound`, `os.startfile`, and Windows executable Quickstart);
- the README duplicated the dashboard as a separate Key Features sales block even though the dashboard was already documented and wired;
- the public documentation did not yet provide one place where users could inspect the arithmetic behind TokenTotals-derived metrics.

The GitHub repository description itself still advertises `Zero-egress` and `budget alerts`. The connected GitHub integration available for this work exposes repository-content mutations but not repository-administration metadata updates, so that description remains a manual GitHub-admin cleanup surface unless changed separately.

Historical verification receipts were intentionally left unchanged. They preserve earlier wording and repairs as evidence and are not current launch copy.

## Implementation

- `52a38b05b6ccc54b690e227f65fb9e789a2d2c15` — reconciled `README.md` with the actual local-control-plane/upstream-egress boundary and local pacing/Turn Notice terminology.
- `c8186ca4ee359db85b3351fac753adb333b022b9` — removed stale hard-ceiling and zero-egress wording from the launch-calendar generator.
- `5f73801e73c3004f4ef3b3c8f12a47cee47fb0b3` — refreshed the generated `.ics` launch plan with the same truthful wording.
- `176262da6a7a848537e87974c03a340683e30d9b` — changed live proxy pacing messages so they describe only TokenTotals-routed requests and do not claim card/account protection or a provider balance.
- `3a199872a7238b6e82abbf7127cf346e465887ac` — added five regression guards covering the public network boundary, financial-clearance wording, live proxy messages, compatibility-only legacy API keys, and launch-calendar wording.
- `e479c6d5350597cb46d5328ff0aaac3fd266d355` — added unbuffered CI test output and a 90-second regression watchdog so a deadlocked test cannot remain opaque indefinitely.
- `32377c9ded39edae8fddb4f688cfef2cddf1e4e5` — added `CALCULATION_TRANSPARENCY.md`, documenting the arithmetic behind current derived metrics.
- `03e73d8ec4afd1fb6190ad8d2e903222acfc32e6` — reconciled README platform support, Quickstart, dashboard wording, append-only telemetry positioning, calculation-transparency link, and support contact. The current desktop badge is Windows-only, the Quickstart documents the 8080-8089 port fallback, and the duplicate Key Features dashboard block was removed while the real dashboard remains documented.
- `faf022bf1e4a5ca9e3ac803665926c174fb7b959` — replaced the flaky cross-thread dual-`TestClient` reservation endpoint test with a deterministic single-event-loop `httpx.AsyncClient` + `ASGITransport` concurrency test, preserving the same admission-control invariant.
- `5feeeb6080da04b88048b1f3e3c5b5b346bc14a9` — tightened regression guards around Windows-only desktop claims, dashboard documentation, Quickstart port behavior, calculation transparency, and current support contact.
- `c73712e5cd1389ba31f724d72d998ffded974cc7` — added `CONTRIBUTING.md` with an evidence-based math/metric review path: identify the metric, observed inputs, current result, expected arithmetic, provider/rule basis, reproduction, and expected regression.

Backward-compatible JSON/config names such as `daily_budget_limit_usd` and `remaining_budget_usd` were deliberately not removed in this pass. Current presentation uses neutral aliases, and the live source marks the old `budget_*` status fields as compatibility fields rather than launch-facing semantics.

## Dashboard verification

The dashboard is a real runtime surface, not illustrative documentation. The proxy serves the local dashboard routes and the Windows tray opens the configured loopback dashboard URL. The README therefore keeps the dashboard in the primary presentation/Quickstart material while avoiding a duplicate sales block under Key Features.

## Telemetry positioning

The README now leans into the core TokenTotals distinction without claiming proprietary access to hidden provider data: many LLM providers already expose useful usage ingredients such as token counts, cache detail, model identity, and related metadata through supported responses/APIs. TokenTotals' value is to normalize those legitimate fields, preserve them turn-by-turn, apply documented pricing mechanics, expose coverage/residuals, and create a locally inspectable receipt-like history that provider interfaces often do not present in this form.

The documentation phrase is intentionally pointed but defensible: `The data is often there. The usable receipt usually isn't. TokenTotals makes one.`

## Calculation transparency

`CALCULATION_TRANSPARENCY.md` documents the current arithmetic for:

- preflight token/cost estimates;
- post-response cost components;
- cache share and uncached-input reconstruction;
- reconstructed totals and reconciliation residuals;
- wall-clock output token rate;
- average/median/P95/max turn-size statistics;
- token and cost coverage;
- posted/in-flight/combined local estimates;
- local threshold percentages and admission checks; and
- Turn Notice comparisons.

`CONTRIBUTING.md` turns community math feedback into a reproducible review process tied back to those formulas, provider rules, regression tests, and verification receipts.

## Unfavorable evidence preserved

### Initial opaque run

GitHub Actions run `35036909415`, job `104607947043`, successfully completed checkout, Python setup, dependency installation, source compilation, and live `proxy_server` import, but its regression-suite step remained in progress materially longer than the prior 161-test baseline.

Two attempts to fetch that still-running job's decoded logs returned GitHub temporary-storage `BlobNotFound` responses, so no partial test output was available at that time. This was recorded rather than treated as a pass or hidden.

An independent local clone was also attempted for diagnosis, but the execution environment had no outbound DNS access to `github.com`; no repository content was changed by that failed diagnostic attempt.

### Reproduced hang and watchdog diagnosis

A fresh run reproduced the long-running regression behavior, showing it was not safe to dismiss as a one-off runner anomaly. The workflow was then hardened with unbuffered output and a 90-second watchdog.

On GitHub Actions run `35037379647`, job `104609414510`, the watchdog terminated the suite with exit code `124` while executing:

`test_second_endpoint_request_is_stopped_before_upstream_while_first_is_inflight`

The hang was in the test harness: the test opened one FastAPI/Starlette `TestClient` in a worker thread while simultaneously opening another `TestClient` in the main thread. That cross-thread client pattern became unreliable under the installed Starlette/httpx stack. The production reservation algorithm itself was not changed to make the test pass.

The test was rewritten to run both concurrent ASGI requests inside one asyncio event loop using `httpx.AsyncClient` with `ASGITransport`. The invariant remained the same: while the first admitted request holds a $0.30 reservation under a $0.50 local threshold, the second $0.30 request must return `429` before any second upstream call occurs; after release/settlement, the first request completes and no reservation remains stranded.

## Final acceptance

GitHub Actions run `35037727736`, job `104610494205`, on commit `5feeeb6080da04b88048b1f3e3c5b5b346bc14a9` completed:

- clean checkout and Python setup;
- dependency installation;
- source compilation;
- live `proxy_server` smoke import; and
- **166/166 regression tests passed** in 0.759 seconds.

The previously hanging concurrency test completed successfully inside the normal suite.

The CI watchdog and unbuffered output remain in the workflow as a permanent test-harness hardening measure.

## Remaining external/manual item

The GitHub repository description is still stale (`Zero-egress` / `budget alerts`) because the connected GitHub application available here does not expose repository-administration metadata mutation. That does not alter runtime behavior or repository files, but it should be manually updated before public drop.
