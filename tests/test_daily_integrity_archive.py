from pathlib import Path

import pytest


def test_daily_status_is_archived_byte_for_byte_with_timestamped_path(monkeypatch, tmp_path):
    from scripts import daily_integrity_refresh as refresh

    status = tmp_path / "PRICING_DAILY_STATUS.md"
    archive_root = tmp_path / "pricing_archive"
    content = "# TokenTotals Daily Pricing Integrity Status\n\nverified receipt\n"
    status.write_text(content, encoding="utf-8")

    monkeypatch.setattr(refresh, "DAILY_STATUS_PATH", Path(status))
    monkeypatch.setattr(refresh, "ARCHIVE_ROOT", Path(archive_root))

    archived = refresh._archive_daily_status("2026-09-15T15:42:31Z")

    assert archived == archive_root / "2026" / "09" / "2026-09-15T154231Z.md"
    assert archived.read_text(encoding="utf-8") == content


def test_daily_archive_receipt_cannot_be_overwritten(monkeypatch, tmp_path):
    from scripts import daily_integrity_refresh as refresh

    status = tmp_path / "PRICING_DAILY_STATUS.md"
    archive_root = tmp_path / "pricing_archive"
    status.write_text("first verified receipt\n", encoding="utf-8")

    monkeypatch.setattr(refresh, "DAILY_STATUS_PATH", Path(status))
    monkeypatch.setattr(refresh, "ARCHIVE_ROOT", Path(archive_root))

    refresh._archive_daily_status("2026-09-15T15:42:31Z")
    status.write_text("attempted replacement\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already exists"):
        refresh._archive_daily_status("2026-09-15T15:42:31Z")

    archived = archive_root / "2026" / "09" / "2026-09-15T154231Z.md"
    assert archived.read_text(encoding="utf-8") == "first verified receipt\n"


def test_failed_daily_workflow_writes_immutable_repository_receipt(monkeypatch, tmp_path):
    from scripts import write_daily_integrity_workflow_receipt as receipt

    archive_root = tmp_path / "pricing_archive"
    monkeypatch.setattr(receipt, "ARCHIVE_ROOT", archive_root)
    monkeypatch.setattr(receipt, "DAILY_STATUS_PATH", tmp_path / "missing-status.md")

    outcomes = {
        "refresh": "failure",
        "freshness": "skipped",
        "telemetry": "skipped",
        "regression": "skipped",
        "writes": "skipped",
    }
    archived = receipt.write_receipt(
        checked_at="2026-09-15T16:10:00Z",
        run_id="12345",
        run_attempt="1",
        head_sha="abc123",
        outcomes=outcomes,
        refresh_log="provider parser failed\nmanual review required\n",
    )

    assert archived.parent == archive_root / "2026" / "09"
    assert archived.name.endswith("-FAIL.md")
    text = archived.read_text(encoding="utf-8")
    assert "**Result:** FAIL" in text
    assert "**refresh:** failure" in text
    assert "manual review required" in text
    assert "Public pricing surfaces must not be promoted" in text

    with pytest.raises(RuntimeError, match="already exists"):
        receipt.write_receipt(
            checked_at="2026-09-15T16:10:00Z",
            run_id="12345",
            run_attempt="1",
            head_sha="abc123",
            outcomes=outcomes,
            refresh_log="replacement attempt",
        )


def test_green_daily_workflow_receipt_contains_daily_list_copy(monkeypatch, tmp_path):
    from scripts import write_daily_integrity_workflow_receipt as receipt

    archive_root = tmp_path / "pricing_archive"
    daily_status = tmp_path / "PRICING_DAILY_STATUS.md"
    daily_status.write_text("# Daily list\n\nall providers verified\n", encoding="utf-8")
    monkeypatch.setattr(receipt, "ARCHIVE_ROOT", archive_root)
    monkeypatch.setattr(receipt, "DAILY_STATUS_PATH", daily_status)

    outcomes = {stage: "success" for stage in receipt.REQUIRED_STAGES}
    archived = receipt.write_receipt(
        checked_at="2026-09-15T16:11:00Z",
        run_id="12346",
        run_attempt="1",
        head_sha="def456",
        outcomes=outcomes,
    )

    text = archived.read_text(encoding="utf-8")
    assert archived.name.endswith("-PASS.md")
    assert "**Result:** PASS" in text
    assert "# Daily list" in text
    assert "all providers verified" in text
