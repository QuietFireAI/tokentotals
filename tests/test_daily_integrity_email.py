from pathlib import Path

import pytest


def _seed_env(monkeypatch):
    monkeypatch.setenv("TOKENTOTALS_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("TOKENTOTALS_SMTP_USERNAME", "reports@example.test")
    monkeypatch.setenv("TOKENTOTALS_SMTP_PASSWORD", "test-only-password")
    monkeypatch.setenv("TOKENTOTALS_PUBLISHED_SHA", "abc123published")
    monkeypatch.setenv("GITHUB_REPOSITORY", "QuietFireAI/tokentotals")
    monkeypatch.setenv("GITHUB_RUN_ID", "123456")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")


def test_daily_integrity_email_uses_generated_status_and_fixed_recipient(monkeypatch, tmp_path):
    from scripts import send_daily_integrity_email as sender

    _seed_env(monkeypatch)
    status = tmp_path / "PRICING_DAILY_STATUS.md"
    status.write_text(
        "# TokenTotals Daily Pricing Integrity Status\n\n"
        "OpenAI verified\nAnthropic verified\nGoogle verified\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sender, "STATUS_PATH", Path(status))

    msg = sender.build_message()
    body = msg.get_content()

    assert msg["To"] == "dailyreport@firelandsai.com"
    assert "TokenTotals daily integrity report" in msg["Subject"]
    assert "Published commit: abc123published" in body
    assert "OpenAI verified" in body
    assert "Anthropic verified" in body
    assert "Google verified" in body
    assert "actions/runs/123456" in body


def test_daily_integrity_email_fails_when_required_smtp_secret_is_missing(monkeypatch):
    from scripts import send_daily_integrity_email as sender

    monkeypatch.delenv("TOKENTOTALS_SMTP_HOST", raising=False)
    monkeypatch.setenv("TOKENTOTALS_SMTP_USERNAME", "reports@example.test")
    monkeypatch.setenv("TOKENTOTALS_SMTP_PASSWORD", "test-only-password")

    with pytest.raises(RuntimeError, match="TOKENTOTALS_SMTP_HOST"):
        sender.build_message()
