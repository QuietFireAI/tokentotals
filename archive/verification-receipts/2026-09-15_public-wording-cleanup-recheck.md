# Public Wording Cleanup Recheck Receipt

Date: 2026-09-15
Repository: `QuietFireAI/tokentotals`

## Status

Implementation complete; independent acceptance verification pending at the time of this receipt checkpoint.

## Diagnosis

Launch-facing wording had drifted behind the runtime/product boundary already established elsewhere in the repository. The stale language was concentrated in current public/runtime surfaces rather than historical evidence:

- `README.md` still used `zero-egress`, `In Budget`, `dollar headroom`, daily-budget/cap wording, and related financial-clearance phrasing;
- `proxy_server.py` still returned user-facing 403/429 messages such as `protect your card`, `daily budget`, `Outgoing calls locked`, and `available local headroom`;
- `generate_launch_calendar.py` and the generated `TokenTotals_30Day_Launch_Plan.ics` still advertised a `hard $5/day ceiling` and `Zero-egress` shorthand.

The GitHub repository description itself also still advertises `Zero-egress` and `budget alerts`. The connected GitHub integration available for this work exposes repository-content mutations but not repository-administration metadata updates, so that description remains a manual GitHub-admin cleanup surface unless changed separately.

Historical verification receipts were intentionally left unchanged. They preserve earlier wording and repairs as evidence and are not current launch copy.

## Implementation

- `52a38b05b6ccc54b690e227f65fb9e789a2d2c15` — reconciled `README.md` with the actual local-control-plane/upstream-egress boundary and local pacing/Turn Notice terminology.
- `c8186ca4ee359db85b3351fac753adb333b022b9` — removed stale hard-ceiling and zero-egress wording from the launch-calendar generator.
- `5f73801e73c3004f4ef3b3c8f12a47cee47fb0b3` — refreshed the generated `.ics` launch plan with the same truthful wording.
- `176262da6a7a848537e87974c03a340683e30d9b` — changed live proxy pacing messages so they describe only TokenTotals-routed requests and do not claim card/account protection or a provider balance.
- `3a199872a7238b6e82abbf7127cf346e465887ac` — added five regression guards covering the public network boundary, financial-clearance wording, live proxy messages, compatibility-only legacy API keys, and launch-calendar wording.

Backward-compatible JSON/config names such as `daily_budget_limit_usd` and `remaining_budget_usd` were deliberately not removed in this pass. Current presentation uses neutral aliases, and the live source marks the old `budget_*` status fields as compatibility fields rather than launch-facing semantics.

## Unfavorable / pending evidence

GitHub Actions run `35036909415`, job `104607947043`, successfully completed checkout, Python setup, dependency installation, source compilation, and live `proxy_server` import, but its regression-suite step remained in progress materially longer than the prior 161-test baseline at this checkpoint.

Two attempts to fetch that still-running job's decoded logs returned GitHub temporary-storage `BlobNotFound` responses, so no partial test output was available. This is recorded rather than treated as a pass or hidden.

An independent local clone was also attempted for diagnosis, but the local execution environment had no outbound DNS access to `github.com`; no repository content was changed by that failed diagnostic attempt.

A fresh acceptance run is being triggered from this receipt checkpoint rather than claiming the wedged/in-progress run succeeded.

## Required acceptance

The wording-cleanup item is not closed until a clean GitHub Actions runner completes install, compile, live proxy import, and the full regression suite, including the five new wording guards. The expected suite size from the 161-test baseline is **166 tests**.

After a clean acceptance result, this receipt must be updated with the exact run/job/count and the roadmap can mark Public Wording Cleanup complete. The stale GitHub repository description should remain disclosed as a manual admin item until it is actually changed.