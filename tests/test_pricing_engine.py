import pytest

from pricing_engine import UnknownModelPrice, calculate_cost, resolve_model


def test_verified_price_math_includes_input_and_output():
    pricing = resolve_model("gpt-5.6-sol")
    result = calculate_cost(pricing, 10_000, 2_000)
    assert result["input_cost_usd"] == pytest.approx(0.04)
    assert result["output_cost_usd"] == pytest.approx(0.04)
    assert result["total_cost_usd"] == pytest.approx(0.08)


def test_guard_rate_is_conservative():
    pricing = resolve_model("gpt-5.6-sol")
    normal = calculate_cost(pricing, 10_000, 2_000)["total_cost_usd"]
    guard = calculate_cost(pricing, 10_000, 2_000, conservative=True)["total_cost_usd"]
    assert guard >= normal


def test_alias_resolution_is_exact_not_fuzzy():
    assert resolve_model("openai/gpt-6-astra")["canonical_model"] == "gpt-6-astra"
    with pytest.raises(UnknownModelPrice):
        resolve_model("gpt-6-astra-ish")


def test_unknown_models_fail_closed():
    with pytest.raises(UnknownModelPrice):
        resolve_model("definitely-not-a-real-model")
