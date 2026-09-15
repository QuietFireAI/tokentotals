# IR-012 Dashboard Telemetry Integrity Proof

**Finding:** dashboard presented hard-coded values as live-looking operational telemetry  
**Classification:** FABRICATED / PLACEHOLDER TELEMETRY — REPAIRED AND REVALIDATED  
**Repair branch:** `sol/forensic-hardening`  
**Revalidation date:** 2026-09-15

## Baseline defect

The baseline dashboard embedded fixed values directly in its HTML:

```text
~199k tok/turn
14.5M tokens processed
~85% Hit
Prompt caching discount active
```

Those values appeared inside metric cards styled alongside actual operational state. The dashboard refresh path did not populate those fields from `/api/status` or another measured runtime telemetry source.

The baseline source also named the unsupported surfaces as token velocity/session total and prompt-cache savings, including element IDs such as `velocityVal`, `cumulTokVal`, and `cacheVal`.

**Impact:** a user could reasonably interpret fixed demonstration/placeholder values as measured session telemetry. The problem was not merely that the particular numbers were stale; the implementation had no runtime basis for presenting those metrics as live values at all.

## Repair

The hardened dashboard removes the unsupported token-velocity, cumulative-token, cache-hit, and prompt-caching-status cards instead of replacing them with different plausible values.

The remaining dashboard metrics are populated from the runtime `/api/status` response, including:

- current estimated/reserved spend;
- configured daily budget;
- remaining budget;
- active-thread spend;
- request count;
- potential-savings estimate;
- pricing receipt date;
- unreconciled-stream count;
- proxy port / last latency;
- lock and traffic-light state.

Where TokenTotals does not have measured telemetry, the dashboard does not invent a substitute value.

## Revalidation improvement

The earlier regression guard checked only that `199k`, `14.5M`, and `85%` were absent. That was useful but too narrow: the same integrity failure could return under different numbers while the test still passed.

The 2026-09-15 IR-012 pass strengthened the guard in two ways.

### 1. Unsupported metric surfaces are banned, not just old numbers

The dashboard regression now rejects the baseline values **and** the unsupported semantic/UI markers:

```text
tok/turn
tokens processed
Prompt Cache Savings
Prompt caching discount active
velocityVal
cumulTokVal
cacheVal
```

If TokenTotals later implements real token-velocity or cache telemetry, this guard must be deliberately changed alongside the runtime telemetry implementation and its tests. Merely substituting new hard-coded values cannot satisfy the current test.

### 2. Displayed dynamic metrics are tied to status fields

A second regression test seeds non-default runtime state, reads `/api/status`, and verifies that the expected spend, thread, savings, request, and unreconciled values are actually returned from state.

It then verifies that the dashboard refresh code reads the corresponding `/api/status` fields for the metrics it displays. This creates a positive integrity check in addition to the negative placeholder ban: the dashboard is not only forbidden from showing the old fake metrics; its surviving dynamic fields are expected to have an identified runtime source.

## Validation evidence

On the IR-012 adversarial-test revision:

- clean regression suite: **46 passed / 0 failed**;
- CPython 3.12 compatibility check: **PASS**;
- constrained dependency install and `pip check`: **PASS**;
- baseline fabricated values absent: **PASS**;
- unsupported token-velocity/cache placeholder surfaces absent: **PASS**;
- surviving dashboard dynamic fields mapped to `/api/status`: **PASS**.

No production proxy change was required during this revalidation pass because the earlier hardening had already removed the fabricated cards. The new work strengthens the evidence and makes regression harder.

## Integrity rule

The governing UI rule is:

> A value may be presented as live/runtime telemetry only when TokenTotals has an implemented runtime source for it. Unknown or unavailable telemetry remains unknown; it is not replaced with a plausible-looking demonstration value.

This rule does not prohibit examples in clearly labeled documentation or test fixtures. It prohibits presenting unsupported constants as if they describe the user's current running session.

## Verdict

**IR-012 — PASS: REPAIRED AND REVALIDATED.**

The baseline dashboard contained fabricated/placeholder telemetry. Those unsupported surfaces are removed, the current dashboard is tied to runtime status fields, and the regression suite now guards the telemetry-integrity principle rather than only the original three numbers.
