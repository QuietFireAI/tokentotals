"""Send the successfully published TokenTotals daily integrity receipt by SMTP.

This script intentionally uses only Python's standard library. It is called only after the
daily provider verification, pricing-surface regeneration, integrity tests, and atomic
publish have succeeded.

Required environment variables:
- TOKENTOTALS_SMTP_HOST
- TOKENTOTALS_SMTP_USERNAME
- TOKENTOTALS_SMTP_PASSWORD

Optional environment variables:
- TOKENTOTALS_SMTP_PORT (default: 465)
- TOKENTOTALS_SMTP_SECURITY (ssl or starttls; default: ssl)
- TOKENTOTALS_REPORT_FROM (default: SMTP username)
- TOKENTOTALS_REPORT_TO (default: dailyreport@firelandsai.com)
- GITHUB_SHA / GITHUB_RUN_ID / GITHUB_REPOSITORY / GITHUB_SERVER_URL
"""
from __future__ import annotations

import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "docs" / "PRICING_DAILY_STATUS.md"
DEFAULT_TO = "dailyreport@firelandsai.com"


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"required email setting {name} is missing")
    return value


def build_message() -> EmailMessage:
    host = _required("TOKENTOTALS_SMTP_HOST")
    username = _required("TOKENTOTALS_SMTP_USERNAME")
    _required("TOKENTOTALS_SMTP_PASSWORD")

    report_to = os.environ.get("TOKENTOTALS_REPORT_TO", DEFAULT_TO).strip() or DEFAULT_TO
    report_from = os.environ.get("TOKENTOTALS_REPORT_FROM", username).strip() or username
    sha = os.environ.get("GITHUB_SHA", "unknown")
    repo = os.environ.get("GITHUB_REPOSITORY", "QuietFireAI/tokentotals")
    run_id = os.environ.get("GITHUB_RUN_ID", "unknown")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    if not STATUS_PATH.exists():
        raise RuntimeError(f"daily pricing status file is missing: {STATUS_PATH}")
    status = STATUS_PATH.read_text(encoding="utf-8")

    msg = EmailMessage()
    msg["Subject"] = f"TokenTotals daily integrity report — {now[:10]}"
    msg["From"] = report_from
    msg["To"] = report_to
    msg.set_content(
        "\n".join(
            [
                "TokenTotals daily pricing integrity refresh completed successfully.",
                "",
                f"Report generated: {now}",
                f"Repository: {repo}",
                f"Published/workflow SHA: {sha}",
                f"Workflow run: {server}/{repo}/actions/runs/{run_id}",
                f"SMTP host used: {host}",
                "",
                "The report below is the same generated pricing/status surface used by the repository.",
                "If provider verification, freshness validation, telemetry-integrity tests, the full regression suite, file-integrity checks, or publication had failed, this success email step would not have been reached.",
                "",
                status,
            ]
        )
    )
    return msg


def send() -> None:
    host = _required("TOKENTOTALS_SMTP_HOST")
    username = _required("TOKENTOTALS_SMTP_USERNAME")
    password = _required("TOKENTOTALS_SMTP_PASSWORD")
    port = int(os.environ.get("TOKENTOTALS_SMTP_PORT", "465"))
    security = os.environ.get("TOKENTOTALS_SMTP_SECURITY", "ssl").strip().lower()
    msg = build_message()
    context = ssl.create_default_context()

    if security == "ssl":
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as smtp:
            smtp.login(username, password)
            smtp.send_message(msg)
    elif security == "starttls":
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(username, password)
            smtp.send_message(msg)
    else:
        raise RuntimeError("TOKENTOTALS_SMTP_SECURITY must be 'ssl' or 'starttls'")

    print(f"Daily integrity report sent to {msg['To']}")


def main() -> int:
    send()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
