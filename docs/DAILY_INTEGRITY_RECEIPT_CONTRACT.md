# TokenTotals Daily Integrity Receipt Contract

**Status:** Normative hardening contract  
**Revision:** 2026-09-15

## Rule

Every scheduled or manually dispatched daily pricing-integrity attempt must leave an immutable repository receipt under `docs/pricing_archive/YYYY/MM/`, whether the attempt passes or fails.

A failed check is evidence. Failure must block promotion of current/public pricing surfaces, but it must not erase the fact that the check occurred or the reason it failed.

## Successful attempt

When all required gates pass:

1. official-source refresh succeeds;
2. the last successful pricing receipt passes the 24-hour freshness gate;
3. telemetry-honesty gates pass;
4. the complete forensic regression suite passes;
5. the refresh writes only the permitted generated surfaces;
6. an immutable workflow receipt ending in `-PASS.md` is written;
7. the generated `docs/PRICING_DAILY_STATUS.md` is also preserved as an exact timestamped archive copy;
8. the generated pricing surfaces and archive receipts are published together.

A PASS workflow receipt contains the daily list used by that run.

## Failed attempt

When any required gate fails:

1. the attempt is stamped with its UTC time, GitHub run ID, run attempt, starting SHA, and gate outcomes;
2. an immutable workflow receipt ending in `-FAIL.md` is written;
3. where available, the receipt includes the tail of the refresh/source-check log so the failure reason remains reviewable;
4. generated current/public pricing surfaces are restored to the branch state that existed at checkout;
5. only `docs/pricing_archive/` evidence is staged for publication;
6. the failure receipt is committed to the repository;
7. the workflow then remains red/failing.

A failed attempt must never be converted into a fresh/current pricing publication merely so the workflow can finish green.

## Immutability

Receipt paths include UTC timestamp plus GitHub run and attempt identity. A receipt writer must refuse to overwrite an existing receipt at the same path.

The archive is append-only evidence. Corrections occur through a later receipt, not by rewriting an earlier one.

## Separation of evidence and promotion

The repository therefore preserves two different facts:

- **What happened during every daily attempt** — PASS or FAIL receipts in `docs/pricing_archive/`.
- **What pricing state is currently promoted** — the catalog, matrix, README pricing block, whitepaper pricing receipt, and `docs/PRICING_DAILY_STATUS.md`, which advance only after all gates pass.

This separation is deliberate. A bad day remains visible without contaminating the last verified public/current pricing state.

## Regression proof

`tests/test_daily_integrity_archive.py` enforces that:

- the successful daily status archive is byte-for-byte identical to the generated daily status;
- archived receipts cannot be overwritten;
- a failed workflow produces an immutable `-FAIL.md` receipt containing the failure state and available log evidence;
- a successful workflow produces a `-PASS.md` receipt containing the daily list;
- the GitHub workflow restores current/public pricing files on failure and stages only `docs/pricing_archive/` before recording the failed attempt.

The daily workflow regression in `tests/test_matrix_freshness.py` also requires the PASS/FAIL receipt and failure-archive publication stages to remain present.

## Deployment boundary

The scheduled GitHub Actions job becomes unattended on the repository default branch when this workflow is merged there. The archive contract itself does not depend on SMTP configuration. Email delivery remains a separate successful-run notification path.
