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
