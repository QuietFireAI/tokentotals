# TokenTotals Dashboard Telemetry Truthfulness Recheck Receipt

Date: 2026-09-15

## Scope

This receipt closes the dashboard truthfulness item identified immediately after the public pricing-document reconciliation.

The concern was that the embedded dashboard displayed values that looked like live operational telemetry even though the runtime did not collect or expose them through `/api/status`.

## Diagnosis

The dashboard contained three unsupported live-looking metrics:

- `~199k tok/turn`
- `14.5M tokens processed`
- `~85% Hit` prompt-cache savings

Those values were static HTML and were never refreshed from `/api/status`. The dashboard therefore visually implied measured runtime telemetry that TokenTotals did not actually maintain.

The same card group also described the proxy as `100% Local Zero-Egress Loopback`. That phrasing conflicted with the documented architecture: TokenTotals' control plane is local, but requests allowed through the pacing gate still egress to the selected upstream model provider.

## Decision

Unsupported telemetry was removed rather than replaced with invented calculations.

The dashboard retains only fields currently backed by runtime state/status data:

- local estimated current spend;
- configured local pacing threshold;
- remaining local threshold headroom;
- threshold percentage;
- active tracked thread estimated spend;
- proxy port; and
- last observed callback latency.

The dashboard now states the network boundary explicitly: local loopback control plane, with permitted upstream provider egress.

## Implementation commits

- `10d16b59edc15d00e1aaeca5a74cae3d50b024c4` — removed static token-velocity/session-total and cache-hit cards, changed budget language to local estimated spend/pacing threshold, and replaced the absolute zero-egress label with the actual loopback/upstream boundary.
- `6299130f078143ee45b47d2d4c237d4d572de8c1` — added dashboard telemetry truthfulness regressions.

## Regression invariants

`tests/test_dashboard_truthfulness.py` enforces that:

1. the dashboard does not contain the removed static token-velocity, total-token, or cache-hit values/labels;
2. the dashboard states the local control-plane/upstream-egress boundary and no longer says `100% Local Zero-Egress Loopback`;
3. the remaining live dashboard field IDs correspond to values actually returned by `/api/status` under controlled runtime state.

## Clean-machine evidence

GitHub Actions run: `35024288277`
Job: `104567424683`
Commit: `6299130f078143ee45b47d2d4c237d4d572de8c1`
Result: **SUCCESS**

Clean runner stages:

- dependency install: success
- Python compile: success
- live `proxy_server` import: success
- regression suite: **93/93 passed**

Dashboard-specific tests passing:

- `test_dashboard_live_fields_are_backed_by_status_endpoint`
- `test_dashboard_omits_uncollected_live_metrics`
- `test_dashboard_states_actual_local_and_upstream_boundary`

All existing provider-pricing, proxy-integration, legacy-removal, model-catalog, optimizer-retirement, preflight-fallback, and pricing-document reconciliation regressions remained green.

## Result

**COMPLETE for this item.**

The dashboard no longer presents static demonstration values as if they were live telemetry, and its network wording now matches the actual runtime boundary.

## Explicitly not claimed

This receipt does not claim TokenTotals cannot support token velocity, cumulative-token, or cache-efficiency telemetry in the future. It records only that those metrics were not backed by the current runtime and therefore were removed instead of fabricated.
