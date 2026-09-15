"""Write an immutable repository receipt for every daily integrity workflow result.

The pricing refresh itself already writes an exact timestamped copy of a successful
PRICING_DAILY_STATUS.md. This companion receipt closes the other half of the audit
trail: the workflow outcome (PASS or FAIL) is recorded even when a source check or
later validation gate fails and public pricing surfaces are not promoted.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = ROOT / "docs" / "pricing_archive"
DAILY_STATUS_PATH = ROOT / "docs" / "PRICING_DAILY_STATUS.md"

REQUIRED_STAGES = (
    "refresh",
    "freshness",
    "telemetry",
    "regression",
    "writes",
)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def write_receipt(
    *,
    checked_at: str,
    run_id: str,
    run_attempt: str,
    head_sha: str,
    outcomes: dict[str, str],
    refresh_log: str = "",
) -> Path:
    """Write one append-only PASS/FAIL receipt for the workflow attempt."""
    missing = [stage for stage in REQUIRED_STAGES if stage not in outcomes]
    if missing:
        raise ValueError(f"missing workflow outcomes: {missing}")

    parsed = _parse_utc(checked_at)
    archive_dir = ARCHIVE_ROOT / f"{parsed.year:04d}" / f"{parsed.month:02d}"
    archive_dir.mkdir(parents=True, exist_ok=True)

    passed = all(outcomes[stage] == "success" for stage in REQUIRED_STAGES)
    result = "PASS" if passed else "FAIL"
    stamp = parsed.strftime("%Y-%m-%dT%H%M%SZ")
    safe_run = "".join(ch for ch in str(run_id) if ch.isalnum() or ch in "-_") or "unknown"
    safe_attempt = "".join(ch for ch in str(run_attempt) if ch.isalnum() or ch in "-_") or "unknown"
    path = archive_dir / f"{stamp}-run-{safe_run}-attempt-{safe_attempt}-{result}.md"
    if path.exists():
        raise RuntimeError(f"daily integrity workflow receipt already exists: {path}")

    lines = [
        "# TokenTotals Daily Integrity Workflow Receipt",
        "",
        f"- **Result:** {result}",
        f"- **Recorded at (UTC):** {checked_at}",
        f"- **GitHub run:** {run_id}",
        f"- **Run attempt:** {run_attempt}",
        f"- **Starting SHA:** `{head_sha}`",
        "",
        "## Gate outcomes",
        "",
    ]
    for stage in REQUIRED_STAGES:
        lines.append(f"- **{stage}:** {outcomes[stage]}")

    if passed:
        lines.extend(
            [
                "",
                "## Receipt meaning",
                "",
                "All required daily integrity gates passed. The successful refresh also creates an exact timestamped copy of `docs/PRICING_DAILY_STATUS.md` in this archive tree before publication.",
            ]
        )
        if DAILY_STATUS_PATH.exists():
            lines.extend(
                [
                    "",
                    "## Daily list captured by this run",
                    "",
                    DAILY_STATUS_PATH.read_text(encoding="utf-8").rstrip(),
                ]
            )
    else:
        lines.extend(
            [
                "",
                "## Receipt meaning",
                "",
                "One or more daily integrity gates failed. Public pricing surfaces must not be promoted from this failed attempt. This failure receipt is still committed so the failed check remains part of the repository audit trail.",
            ]
        )
        if refresh_log.strip():
            # Keep the receipt useful without allowing an unbounded workflow log to
            # balloon the repository. The source-check failure is normally at the end.
            tail = "\n".join(refresh_log.splitlines()[-120:])
            lines.extend(["", "## Refresh log tail", "", "```text", tail, "```"])

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def main() -> int:
    outcomes = {
        stage: os.environ.get(f"TOKENTOTALS_{stage.upper()}_OUTCOME", "unknown")
        for stage in REQUIRED_STAGES
    }
    log_path = os.environ.get("TOKENTOTALS_REFRESH_LOG", "")
    refresh_log = ""
    if log_path and Path(log_path).exists():
        refresh_log = Path(log_path).read_text(encoding="utf-8", errors="replace")

    path = write_receipt(
        checked_at=os.environ["TOKENTOTALS_RECEIPT_TIMESTAMP"],
        run_id=os.environ.get("GITHUB_RUN_ID", "unknown"),
        run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT", "unknown"),
        head_sha=os.environ.get("GITHUB_SHA", "unknown"),
        outcomes=outcomes,
        refresh_log=refresh_log,
    )
    print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
