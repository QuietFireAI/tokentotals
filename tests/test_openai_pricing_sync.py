import importlib
import json

SOL_MD = """
# GPT-5.6 Sol
Pricing
Input

$4.00
Cached input

$0.40
Output

$20.00
Prompts with >272K input tokens are priced at 2x input and 1.5x output for the full request.
Cache writes are billed at 1.25x the uncached input token rate.
"""

ASTRA_MD = """
# GPT-6 Astra
Pricing
Input

$10.00
Cached input

$1.00
Cache writes

$12.50
Output

$50.00
Prompts with more than 272K input tokens are priced at 2x input and cache rates and 1.5x output for the full request.
Cache writes are billed at 1.25x the uncached input token rate.
Batch and Flex are priced at 50% of Standard rates. Fast mode is priced at 2x the applicable rates.
"""

TERRA_MD = SOL_MD.replace("GPT-5.6 Sol", "GPT-5.6 Terra").replace("$4.00", "$2.00").replace("$0.40", "$0.20").replace("$20.00", "$12.00")
LUNA_MD = SOL_MD.replace("GPT-5.6 Sol", "GPT-5.6 Luna").replace("$4.00", "$0.20").replace("$0.40", "$0.02").replace("$20.00", "$1.20")


def _fixture_fetch(url):
    if "gpt-6-astra" in url:
        return ASTRA_MD
    if "gpt-5.6-sol" in url:
        return SOL_MD
    if "gpt-5.6-terra" in url:
        return TERRA_MD
    if "gpt-5.6-luna" in url:
        return LUNA_MD
    raise AssertionError(url)


def test_parse_sol_derives_cache_write_and_long_context():
    from openai_pricing_sync import MODEL_SPECS, parse_model_markdown
    record = parse_model_markdown("gpt-5.6-sol", SOL_MD, MODEL_SPECS["gpt-5.6-sol"]["url"])
    assert record["input_price_per_1m"] == 4.0
    assert record["cached_input_price_per_1m"] == 0.40
    assert record["cache_write_price_per_1m"] == 5.0
    assert record["output_price_per_1m"] == 20.0
    assert record["guard_input_price_per_1m"] == 8.0
    assert record["guard_output_price_per_1m"] == 30.0
    assert record["pricing_rules"]["long_context"]["threshold_input_tokens"] == 272000


def test_parse_astra_captures_service_relationships():
    from openai_pricing_sync import MODEL_SPECS, parse_model_markdown
    record = parse_model_markdown("gpt-6-astra", ASTRA_MD, MODEL_SPECS["gpt-6-astra"]["url"])
    assert record["cache_write_price_per_1m"] == 12.5
    assert record["pricing_rules"]["service_tier_multipliers"] == {
        "batch": 0.5,
        "flex": 0.5,
        "fast": 2.0,
    }
    assert record["guard_input_price_per_1m"] == 40.0
    assert record["guard_output_price_per_1m"] == 150.0


def test_incomplete_source_set_preserves_verified_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKENTOTALS_PRICING_DIR", str(tmp_path))
    import openai_pricing_sync
    importlib.reload(openai_pricing_sync)

    prior = {"provider": "OpenAI", "status": "verified", "models": {"keep": {"provider": "OpenAI"}}}
    openai_pricing_sync._atomic_json(openai_pricing_sync.VERIFIED_PATH, prior)

    def broken(url):
        if "terra" in url:
            raise RuntimeError("network/parser failure")
        return _fixture_fetch(url)

    result = openai_pricing_sync.sync_openai_pricing(broken)
    assert result["result"] == "failed"
    assert json.loads(openai_pricing_sync.VERIFIED_PATH.read_text()) == prior


def test_valid_sync_promotes_and_runtime_reads_same_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKENTOTALS_PRICING_DIR", str(tmp_path))
    import openai_pricing_sync
    import pricing_engine
    importlib.reload(openai_pricing_sync)

    result = openai_pricing_sync.sync_openai_pricing(_fixture_fetch)
    assert result["result"] == "promoted"
    assert openai_pricing_sync.VERIFIED_PATH.exists()

    pricing_engine.clear_catalog_cache()
    sol = pricing_engine.resolve_model("gpt-5.6")
    assert sol["input_price_per_1m"] == 4.0
    assert sol["cached_input_price_per_1m"] == 0.4
    assert sol["cache_write_price_per_1m"] == 5.0
    assert sol["source_url"].endswith("/gpt-5.6-sol")


def test_suspicious_jump_is_quarantined_and_previous_runtime_survives(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKENTOTALS_PRICING_DIR", str(tmp_path))
    import openai_pricing_sync
    import pricing_engine
    importlib.reload(openai_pricing_sync)

    assert openai_pricing_sync.sync_openai_pricing(_fixture_fetch)["result"] == "promoted"
    previous = json.loads(openai_pricing_sync.VERIFIED_PATH.read_text())

    def wild(url):
        text = _fixture_fetch(url)
        if "gpt-5.6-sol" in url:
            text = text.replace("$4.00", "$400.00", 1)
        return text

    result = openai_pricing_sync.sync_openai_pricing(wild)
    assert result["result"] == "candidate_only"
    current = json.loads(openai_pricing_sync.VERIFIED_PATH.read_text())
    assert current["models"]["gpt-5.6-sol"]["input_price_per_1m"] == previous["models"]["gpt-5.6-sol"]["input_price_per_1m"]

    pricing_engine.clear_catalog_cache()
    assert pricing_engine.resolve_model("gpt-5.6-sol")["input_price_per_1m"] == 4.0


def test_failed_check_retries_same_day(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKENTOTALS_PRICING_DIR", str(tmp_path))
    import openai_pricing_sync
    importlib.reload(openai_pricing_sync)
    openai_pricing_sync._atomic_json(
        openai_pricing_sync.STATUS_PATH,
        {"checked_at": openai_pricing_sync._utcnow(), "result": "failed"},
    )
    assert openai_pricing_sync.check_due_today() is True


def test_source_only_change_requires_review(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKENTOTALS_PRICING_DIR", str(tmp_path))
    import openai_pricing_sync
    importlib.reload(openai_pricing_sync)

    assert openai_pricing_sync.sync_openai_pricing(_fixture_fetch)["result"] == "promoted"

    def editorial_change(url):
        return _fixture_fetch(url) + "\nEditorial note with no pricing change.\n"

    result = openai_pricing_sync.sync_openai_pricing(editorial_change)
    assert result["result"] == "candidate_only"
    assert "source content changed" in result["message"].lower()
