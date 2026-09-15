from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_CLAIM_FILES = (
    ROOT / "README.md",
    ROOT / "TokenTotals_Security_Whitepaper.md",
    ROOT / "proxy_server.py",
)

FORBIDDEN_BLANKET_LIVE_AUDIT_PHRASES = (
    "audited live directly from provider documentation",
    "official vendor pricing is audited live",
    "official provider pricing audited live",
    "all provider pricing is audited live",
)


def _public_claim_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8").lower() for path in PUBLIC_CLAIM_FILES)


def test_blanket_live_provider_audit_claim_cannot_return():
    text = _public_claim_text()
    for phrase in FORBIDDEN_BLANKET_LIVE_AUDIT_PHRASES:
        assert phrase not in text, f"unsupported pricing claim returned: {phrase!r}"


def test_provider_sync_scope_remains_explicit():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    whitepaper = (ROOT / "TokenTotals_Security_Whitepaper.md").read_text(encoding="utf-8")
    dashboard_source = (ROOT / "proxy_server.py").read_text(encoding="utf-8")

    assert "Official-source OpenAI pricing checker" in readme
    assert "Anthropic and Google do not yet have the dynamic official-source synchronization path" in readme

    assert "OpenAI is the first provider with a dynamic official-source overlay" in whitepaper
    assert "Anthropic and Google remain on the dated checked-in verified catalog" in whitepaper

    assert "Pricing receipts" in dashboard_source
    assert "audited live" not in dashboard_source.lower()
