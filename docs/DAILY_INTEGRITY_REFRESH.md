# TokenTotals Daily Integrity Refresh

## Purpose

TokenTotals treats pricing freshness as a scheduled integrity obligation, not as an event that runs only when a provider price appears to change.

The primary mechanism is one daily workflow. Price/model drift is something discovered and recorded during that run; it is not the trigger for the run.

## Schedule

`.github/workflows/daily-integrity-refresh.yml` runs:

- once every day at **05:05 UTC** (`5 5 * * *`), which is 00:05 EST / 01:05 EDT and therefore safely after the Eastern calendar-day boundary; and
- on explicit `workflow_dispatch` for an extra/manual verification run.

GitHub scheduled workflows execute from the repository default branch. During the forensic hardening review the workflow is proven on `sol/forensic-hardening`, but the unattended daily cron does not become operational until the workflow reaches the default branch.

## Daily transaction

A successful daily run performs this sequence:

1. create a clean constrained CPython 3.12 environment;
2. verify the dependency graph;
3. fetch and validate the represented official provider pricing sources;
4. refresh the verified pricing receipt/catalog where the adapter can safely do so;
5. regenerate `MODEL_COMPARISON_MATRIX.md`;
6. regenerate the marked README pricing block;
7. regenerate the whitepaper pricing receipt;
8. regenerate `docs/PRICING_DAILY_STATUS.md` and all displayed calculation examples;
9. create an immutable timestamped archive copy of that generated daily status under `docs/pricing_archive/YYYY/MM/`;
10. run the 24-hour completion validator;
11. run the two telemetry-honesty stop-line tests explicitly;
12. run the complete forensic regression/integration suite;
13. reject any unexpected file modifications and require `git diff --check` to pass;
14. publish the allowed pricing/documentation surfaces **and the archive receipt** in one atomic daily commit; and
15. email the generated daily integrity report to `dailyreport@firelandsai.com`.

If any provider verification, regeneration, freshness, telemetry, regression, or file-integrity step fails, the workflow does not publish a new daily pricing receipt and does not send a success email.

The email step intentionally occurs **after** the atomic pricing publish. If SMTP delivery fails, the correctly verified pricing commit and archive receipt remain published, but the workflow is red and no successful-delivery claim is made.

## Immutable daily archive

Every successful refresh copies the complete generated `docs/PRICING_DAILY_STATUS.md` into a timestamped repository receipt such as:

`docs/pricing_archive/2026/09/2026-09-15T154231Z.md`

The archive filename uses UTC and is Windows-safe. A manual verification run on the same date receives its own timestamped receipt rather than replacing the scheduled receipt.

Archive receipts are intentionally append-only at creation time: if a receipt already exists for the same timestamp, the refresh raises an error instead of overwriting it. Regression tests verify that the archived file is byte-for-byte identical to the generated daily status and that an existing archive receipt cannot be replaced.

Because the archive file is staged in the same Git commit as the catalog, matrix, README pricing block, whitepaper receipt, and current status file, the historical receipt and the public pricing surfaces share one auditable publication boundary.

## Freshness validator

`scripts/check_pricing_freshness.py` is a watchdog, not a refresh trigger.

Its job is to prove that the most recently published daily refresh completed successfully and is still current. It requires:

- the daily receipt status to be `verified`;
- OpenAI, Anthropic, and Google provider statuses to all be `verified`;
- a valid timezone-aware `source_checked_at` timestamp; and
- receipt age of at most 24 hours.

A receipt at exactly 24:00:00 remains current. At 24:00:01 it fails closed as stale.

## Daily email receipt

`scripts/send_daily_integrity_email.py` uses Python's standard-library SMTP client; no third-party email GitHub Action is added to the integrity chain.

The email contains:

- successful-refresh statement;
- UTC report timestamp;
- repository and exact published commit SHA;
- GitHub Actions run link; and
- the complete generated `docs/PRICING_DAILY_STATUS.md`, including provider verification status, current represented models/rates, base calculation examples, and conservative reservation examples.

The recipient is fixed by the workflow to:

`dailyreport@firelandsai.com`

### Required GitHub Actions secrets

- `TOKENTOTALS_SMTP_HOST`
- `TOKENTOTALS_SMTP_USERNAME`
- `TOKENTOTALS_SMTP_PASSWORD`

### Optional GitHub Actions secrets

- `TOKENTOTALS_SMTP_PORT` — defaults to `465`
- `TOKENTOTALS_SMTP_SECURITY` — `ssl` (default) or `starttls`
- `TOKENTOTALS_REPORT_FROM` — defaults to the SMTP username

The repository never stores the SMTP password or other mail credentials in source.

## Integrity rule

The daily workflow follows this model:

```text
verify -> calculate -> regenerate -> archive -> test -> publish -> email receipt -> expire -> repeat
```

A changed price is an audit finding inside that cycle. A lack of price changes does not cancel the daily verification obligation.
