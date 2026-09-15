# TokenTotals Daily Pricing Refresh Contract

**Status:** governing integrity contract  
**Schedule:** 12:05 AM America/New_York, every day  
**Branch deployment note:** GitHub scheduled workflows become unattended/operational only when this workflow exists on the repository default branch.

## Core rule

TokenTotals pricing maintenance is **schedule-driven, not change-triggered**.

Every day, TokenTotals performs a fresh integrity cycle whether or not any provider price appears to have changed. Provider drift/change detection is an output of that cycle for audit and review; it is not what causes the cycle to run.

The operating model is:

```text
scheduled daily refresh
        ↓
fetch current official provider sources
        ↓
validate represented models, rates, rules, and effective dates
        ↓
record drift/change evidence versus the prior verified view
        ↓
rebuild the verified pricing view where automatic promotion is explicitly safe
        ↓
regenerate calculations + MODEL_COMPARISON_MATRIX.md + README pricing block
        + whitepaper pricing receipt + daily pricing status
        ↓
run telemetry-honesty gates + complete regression/integration suite
        ↓
all gates pass?
   no             yes
   ↓               ↓
publish nothing    publish one atomic daily integrity commit
```

## Scheduler role

`.github/workflows/daily-integrity-refresh.yml` is the primary mechanism.

It is scheduled for **00:05 Eastern Time** every day. Because GitHub cron schedules are expressed in UTC, the workflow declares both UTC equivalents (04:05 and 05:05 UTC) and uses the `America/New_York` UTC offset to select the active EDT/EST schedule. Manual `workflow_dispatch` is retained as an explicit override.

The workflow does **not** use repository price/file changes as the normal refresh trigger. A day changing is sufficient reason to verify pricing again.

## Validator/watchdog role

`scripts/check_pricing_freshness.py` does **not** trigger or perform a refresh.

Its role is to validate the last successfully published verified daily receipt. The receipt must:

- have overall status `verified`;
- include verified OpenAI, Anthropic, and Google provider statuses;
- contain a valid timezone-aware `source_checked_at` timestamp;
- be no more than 24 hours old;
- not be future-dated.

A receipt exactly 24 hours old remains current. At 24 hours plus one second, the validator fails closed with `STALE DAILY PRICING REFRESH`.

The validator therefore acts as a watchdog for scheduled-operation failure: if the daily workflow does not run, cannot fetch a provider source, cannot parse/validate represented pricing, fails an integrity test, or cannot publish, the prior receipt does not advance and eventually becomes stale.

## Atomic publication rule

The daily receipt is only published to the repository after the complete workflow passes its provider checks, generated-surface checks, telemetry-honesty gates, full regression/integration suite, and unexpected-file/diff checks.

The atomic publication set is:

- `pricing_catalog.json`
- `MODEL_COMPARISON_MATRIX.md`
- `README.md` generated pricing block
- `TokenTotals_Security_Whitepaper.md` generated pricing receipt
- `docs/PRICING_DAILY_STATUS.md`

A failed run must not stamp yesterday's pricing as current and must not partially publish a subset of those surfaces.

## Drift/change role

Price/model/source drift remains important evidence, but it is subordinate to the scheduled cycle.

The daily refresh compares the newly observed official-source evidence with the prior verified view so TokenTotals can record recognized changes, quarantine suspicious changes, or stop for manual review when a change cannot be safely interpreted. That comparison is an audit/control mechanism, not a scheduler.

## Integrity principle

**Verify → calculate → publish → expire → repeat.**

TokenTotals should prefer a visible failed/stale refresh over a green status backed by unverified or silently old pricing.
