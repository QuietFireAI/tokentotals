from pathlib import Path

import pricing_engine
import proxy_server


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_and_build_have_no_developer_machine_pricing_path():
    """The baseline private Antigravity/Gemini pricing path must never return."""
    runtime = (ROOT / "proxy_server.py").read_text(encoding="utf-8")
    build = (ROOT / "build.ps1").read_text(encoding="utf-8-sig")
    combined = (runtime + "\n" + build).lower()

    forbidden = (
        r"c:\users\command center",
        ".gemini\\config\\plugins\\token-cost-estimator",
        ".gemini/config/plugins/token-cost-estimator",
        "token-cost-estimator\\scripts",
        "token-cost-estimator/scripts",
    )
    for marker in forbidden:
        assert marker not in combined, f"developer-machine pricing dependency returned: {marker!r}"

    # The old packaging path used PyInstaller --paths to reach outside the repo.
    assert "--paths" not in build.lower()


def test_pricing_catalog_is_repository_local_and_is_the_runtime_view():
    expected = (ROOT / "pricing_catalog.json").resolve()
    assert pricing_engine.CATALOG_PATH.resolve() == expected
    assert pricing_engine.CATALOG_PATH.exists()

    catalog = pricing_engine.load_catalog()
    assert isinstance(catalog.get("models"), dict)
    assert catalog["models"]

    # The production proxy imports and uses the same repository pricing engine.
    assert proxy_server.resolve_model is pricing_engine.resolve_model
    assert proxy_server.calculate_cost is pricing_engine.calculate_cost
    assert proxy_server.estimate_text_tokens is pricing_engine.estimate_text_tokens


def test_windows_build_bundles_repository_pricing_catalog_without_external_path():
    build = (ROOT / "build.ps1").read_text(encoding="utf-8-sig")
    assert '--add-data "pricing_catalog.json;."' in build
    assert "pricing_engine.py" not in build or "--paths" not in build.lower()
