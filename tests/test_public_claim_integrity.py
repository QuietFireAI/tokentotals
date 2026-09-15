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

FORBIDDEN_IMPLEMENTED_BADGE_CLAIMS = (
    "turn-by-turn chat telemetry badge",
    "every single developer turn or agent interaction renders",
    "renders a clean, live telemetry badge directly in your working context",
)

FORBIDDEN_PREFLIGHT_TOKEN_PRECISION_CLAIMS = (
    "cryptographic/bpe token counts",
    "derived from bpe token frequency",
    "tokens}_{\\text{in}} = \\text{bpe}",
    "deterministic bpe token count",
    "exact bpe token count",
    "provider-accurate pre-flight token count",
)

FORBIDDEN_IMPLEMENTED_WEBSOCKET_CLAIMS = (
    "http/websocket loopback proxy daemon",
    "http/websocket proxy daemon",
    "supports http and websocket proxying",
    "websocket proxy support is implemented",
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


def test_turn_by_turn_badge_cannot_be_claimed_as_implemented():
    text = _public_claim_text()
    for phrase in FORBIDDEN_IMPLEMENTED_BADGE_CLAIMS:
        assert phrase not in text, f"unsupported telemetry-badge claim returned: {phrase!r}"

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "It does not inject a telemetry badge into every IDE/chat turn." in readme


def test_preflight_token_estimator_cannot_be_claimed_as_bpe_or_exact():
    text = _public_claim_text()
    for phrase in FORBIDDEN_PREFLIGHT_TOKEN_PRECISION_CLAIMS:
        assert phrase not in text, f"unsupported pre-flight token precision claim returned: {phrase!r}"

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    whitepaper = (ROOT / "TokenTotals_Security_Whitepaper.md").read_text(encoding="utf-8")

    assert "Pre-flight token counts are **not represented as provider/model BPE counts**." in readme
    assert "The current pre-flight estimator is a conservative local UTF-8-length heuristic." in whitepaper
    assert "It is **not represented as a provider/model BPE tokenizer**." in whitepaper


def test_websocket_proxy_cannot_be_claimed_as_implemented():
    text = _public_claim_text()
    for phrase in FORBIDDEN_IMPLEMENTED_WEBSOCKET_CLAIMS:
        assert phrase not in text, f"unsupported WebSocket implementation claim returned: {phrase!r}"

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    whitepaper = (ROOT / "TokenTotals_Security_Whitepaper.md").read_text(encoding="utf-8")

    assert "It does not provide a TokenTotals WebSocket proxy endpoint." in readme
    assert "This revision does **not** claim a TokenTotals WebSocket proxy endpoint." in whitepaper
    assert "supports HTTP `/v1/chat/completions` and SSE-style streamed responses" in whitepaper
