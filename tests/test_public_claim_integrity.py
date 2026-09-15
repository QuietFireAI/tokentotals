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

FORBIDDEN_EVERY_RESPONSE_RECONCILIATION_CLAIMS = (
    "every single api response from openai, anthropic, and google already contains everything you need to calculate your exact spend in real time",
    "what the api already returns in every response",
    "every response contains everything needed to calculate exact spend",
    "every response contains everything you need to calculate exact spend",
)

FORBIDDEN_COMPLIANCE_CLAIMS = (
    "sails through compliance review",
    "fedramp & fisma compliance:",
    "fedramp and fisma compliant",
    "fedramp compliant by design",
    "fisma compliant by design",
    "automatically fedramp compliant",
    "automatically fisma compliant",
)

FORBIDDEN_CROSS_PLATFORM_GUI_CLAIMS = (
    "platform-windows%20%7c%20macos%20%7c%20linux",
    "platform: windows | macos | linux",
    "gui supports windows, macos, and linux",
    "desktop app supports windows, macos, and linux",
    "cross-platform gui for windows, macos, and linux",
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


def test_every_response_exact_spend_claim_cannot_return():
    text = _public_claim_text()
    for phrase in FORBIDDEN_EVERY_RESPONSE_RECONCILIATION_CLAIMS:
        assert phrase not in text, f"unsupported every-response reconciliation claim returned: {phrase!r}"

    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    whitepaper = (ROOT / "TokenTotals_Security_Whitepaper.md").read_text(encoding="utf-8").lower()
    assert "missing telemetry" in readme
    assert "usage is unavailable" in whitepaper


def test_fedramp_fisma_compliance_cannot_be_inferred_from_local_architecture():
    text = _public_claim_text()
    for phrase in FORBIDDEN_COMPLIANCE_CLAIMS:
        assert phrase not in text, f"unsupported compliance claim returned: {phrase!r}"

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    whitepaper = (ROOT / "TokenTotals_Security_Whitepaper.md").read_text(encoding="utf-8")

    assert "It is not a FedRAMP/FISMA authorization and does not make an environment compliant by itself." in readme
    assert "They do not by themselves establish FedRAMP authorization, FISMA compliance" in whitepaper
    assert "Those determinations belong to the relevant organization and security/compliance authority." in whitepaper


def test_gui_platform_claim_matches_current_windows_oriented_implementation():
    text = _public_claim_text()
    for phrase in FORBIDDEN_CROSS_PLATFORM_GUI_CLAIMS:
        assert phrase not in text, f"unsupported cross-platform GUI claim returned: {phrase!r}"

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    gui_source = (ROOT / "app_gui.py").read_text(encoding="utf-8")
    build_script = (ROOT / "build.ps1").read_text(encoding="utf-8")

    assert "The packaged GUI/build path in this repository is currently Windows-oriented." in readme
    assert "The Python proxy may be portable, but macOS/Linux GUI packaging is not release-tested here." in readme

    # These are implementation evidence for the current documentation boundary.
    # A future cross-platform GUI should deliberately replace this test together
    # with real platform-specific packaging and CI evidence.
    assert "import winsound" in gui_source
    assert "os.startfile" in gui_source
    assert "PyInstaller" in build_script
