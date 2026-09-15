from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def _base_view(monkeypatch):
    import pricing_engine

    monkeypatch.setattr(pricing_engine, "_load_verified_openai_overlay", lambda: None)
    pricing_engine.clear_catalog_cache()
    return pricing_engine


def test_committed_matrix_matches_base_verified_view(monkeypatch):
    """The public matrix must be regenerated whenever its base pricing view changes.

    Dynamic provider snapshots are intentionally disabled here because the committed
    repository matrix is the portable base snapshot. At runtime, the generator still
    consumes promoted provider overlays through pricing_engine when present.
    """
    import generate_model_matrix

    pricing_engine = _base_view(monkeypatch)
    try:
        expected = generate_model_matrix.render().strip()
        actual = Path("MODEL_COMPARISON_MATRIX.md").read_text(encoding="utf-8").strip()
        assert actual == expected
    finally:
        pricing_engine.clear_catalog_cache()


def test_readme_pricing_snapshot_matches_generator_and_has_no_stale_era_rows(monkeypatch):
    """README's below-the-fold comparison must share the same generated pricing truth."""
    import generate_model_matrix

    pricing_engine = _base_view(monkeypatch)
    try:
        readme = Path("README.md").read_text(encoding="utf-8")
        start = generate_model_matrix.README_START
        end = generate_model_matrix.README_END
        assert readme.count(start) == 1
        assert readme.count(end) == 1

        actual = start + readme.split(start, 1)[1].split(end, 1)[0] + end
        expected = generate_model_matrix.render_readme_pricing_section()
        assert actual.strip() == expected.strip()

        public_pricing = (
            Path("MODEL_COMPARISON_MATRIX.md").read_text(encoding="utf-8")
            + "\n"
            + actual
        ).lower()
        for stale_model in (
            "gpt-4o",
            "o1 |",
            "o3-mini",
            "claude 3.7 sonnet",
            "claude 3.5 sonnet",
            "claude 3.5 haiku",
            "gemini 2.5 pro",
            "gemini 2.0 flash",
            "gemini 2.0 flash-lite",
        ):
            assert stale_model not in public_pricing, f"stale comparison row returned: {stale_model}"
    finally:
        pricing_engine.clear_catalog_cache()


def _freshness_catalog(checked_at: datetime) -> dict:
    return {
        "daily_integrity_refresh": {
            "status": "verified",
            "source_checked_at": checked_at.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "providers": {
                "OpenAI": {"status": "verified"},
                "Anthropic": {"status": "verified"},
                "Google": {"status": "verified"},
            },
        }
    }


def test_pricing_receipt_is_current_through_exactly_24_hours():
    from scripts.check_pricing_freshness import check_freshness

    now = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    result = check_freshness(_freshness_catalog(now - timedelta(hours=24)), now=now)
    assert result["status"] == "CURRENT"
    assert result["age_seconds"] == 24 * 60 * 60


def test_pricing_receipt_fails_closed_after_24_hours():
    from scripts.check_pricing_freshness import check_freshness

    now = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    stale = _freshness_catalog(now - timedelta(hours=24, seconds=1))
    with pytest.raises(RuntimeError, match="STALE PRICING RECEIPT"):
        check_freshness(stale, now=now)
