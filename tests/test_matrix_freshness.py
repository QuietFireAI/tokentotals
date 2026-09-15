from pathlib import Path


def test_committed_matrix_matches_base_verified_view(monkeypatch):
    """The public matrix must be regenerated whenever its base pricing view changes.

    Dynamic provider snapshots are intentionally disabled here because the committed
    repository matrix is the portable base snapshot. At runtime, the generator still
    consumes promoted provider overlays through pricing_engine when present.
    """
    import generate_model_matrix
    import pricing_engine

    monkeypatch.setattr(pricing_engine, "_load_verified_openai_overlay", lambda: None)
    pricing_engine.clear_catalog_cache()
    try:
        expected = generate_model_matrix.render().strip()
        actual = Path("MODEL_COMPARISON_MATRIX.md").read_text(encoding="utf-8").strip()
        assert actual == expected
    finally:
        pricing_engine.clear_catalog_cache()
