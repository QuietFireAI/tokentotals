from datetime import date

import pytest

import matrix_source_check


def test_anthropic_base_and_guard_rates_are_read_from_model_pricing_not_navigation():
    catalog = {
        "models": {
            "claude-fable-5.1": {
                "provider": "Anthropic",
                "input_price_per_1m": 10.0,
                "output_price_per_1m": 50.0,
                "guard_input_price_per_1m": 20.0,
                "guard_output_price_per_1m": 50.0,
            },
            "claude-opus-5": {
                "provider": "Anthropic",
                "input_price_per_1m": 5.0,
                "output_price_per_1m": 25.0,
                "guard_input_price_per_1m": 10.0,
                "guard_output_price_per_1m": 25.0,
            },
        }
    }
    text = """
    Models
    Claude Fable 5.1
    Claude Opus 5
    Model pricing
    Claude Fable 5.1 $10 / MTok $12.50 / MTok $20 / MTok $0.25 / MTok $50 / MTok
    Claude Opus 5 $5 / MTok $6.25 / MTok $10 / MTok $0.50 / MTok $25 / MTok
    """
    result = matrix_source_check.validate_provider_text("Anthropic", text, catalog)
    assert [row["model"] for row in result] == ["claude-fable-5.1", "claude-opus-5"]
    assert result[0]["guard_input_price_per_1m"] == 20.0
    assert result[1]["guard_output_price_per_1m"] == 25.0


def test_google_validator_uses_standard_section_not_promo_or_priority_repeat():
    catalog = {
        "models": {
            "gemini-3.1-pro-preview": {
                "provider": "Google",
                "input_price_per_1m": 2.0,
                "output_price_per_1m": 12.0,
            },
            "gemini-3.5-flash": {
                "provider": "Google",
                "input_price_per_1m": 1.5,
                "output_price_per_1m": 9.0,
            },
        }
    }
    text = """
    Gemini 3.5 Flash promotional mention $99 $99
    Google models
    Gemini 3
    Standard Model Priority Flex/Batch
    Gemini 3.1 Pro Preview Input Global $2.00 $4.00 $0.20 $0.40 Text output Global $12.00 $18.00
    Gemini 3.5 Flash Input Global $1.50 $1.50 $0.15 $0.15 Text output Global $9.00 $9.00
    Priority
    Gemini 3.1 Pro Preview Input Global $3.60 $7.20 Text output Global $21.60 $32.40
    Gemini 3.5 Flash Input Global $2.70 $2.70 Text output Global $16.20 $16.20
    """
    result = matrix_source_check.validate_provider_text("Google", text, catalog)
    assert result[0]["input_price_per_1m"] == 2.0
    assert result[0]["output_price_per_1m"] == 12.0


def test_google_guard_rates_are_validated_against_priority_section():
    catalog = {
        "models": {
            "gemini-3.5-flash-lite": {
                "provider": "Google",
                "input_price_per_1m": 0.3,
                "output_price_per_1m": 2.5,
                "guard_input_price_per_1m": 0.594,
                "guard_output_price_per_1m": 4.95,
            }
        }
    }
    text = """
    Google models
    Standard
    Gemini 3.5 Flash-Lite Input Global $0.30 Non-global $0.33 Text output Global $2.50 Non-global $2.75
    Price (/1M tokens) <= 200K input tokens with Priority
    Gemini 3.5 Flash-Lite Input Global $0.54 Non-global $0.594 Text output Global $4.50 Non-global $4.95
    """
    result = matrix_source_check.validate_provider_text("Google", text, catalog)
    assert result[0]["guard_input_price_per_1m"] == 0.594
    assert result[0]["guard_output_price_per_1m"] == 4.95


def test_google_guard_rate_drift_fails_instead_of_accepting_lower_standard_value():
    catalog = {
        "models": {
            "gemini-3.5-flash-lite": {
                "provider": "Google",
                "input_price_per_1m": 0.3,
                "output_price_per_1m": 2.5,
                "guard_input_price_per_1m": 0.594,
                "guard_output_price_per_1m": 2.75,
            }
        }
    }
    text = """
    Google models
    Standard
    Gemini 3.5 Flash-Lite Input Global $0.30 Non-global $0.33 Text output Global $2.50 Non-global $2.75
    Price (/1M tokens) <= 200K input tokens with Priority
    Gemini 3.5 Flash-Lite Input Global $0.54 Non-global $0.594 Text output Global $4.50 Non-global $4.95
    """
    with pytest.raises(ValueError, match="guard output"):
        matrix_source_check.validate_provider_text("Google", text, catalog)


def test_live_source_drift_fails_instead_of_accepting_new_number_silently():
    catalog = {
        "models": {
            "gemini-3.5-flash": {
                "provider": "Google",
                "input_price_per_1m": 1.5,
                "output_price_per_1m": 9.0,
            }
        }
    }
    changed = """
    Google models
    Standard
    Gemini 3.5 Flash Input Global $2.00 Text output Global $10.00
    """
    with pytest.raises(ValueError, match="catalog input"):
        matrix_source_check.validate_provider_text("Google", changed, catalog)


def test_expired_catalog_rate_fails_even_if_old_number_remains_on_provider_page():
    catalog = {
        "models": {
            "gemini-3.8-flash": {
                "provider": "Google",
                "input_price_per_1m": 0.75,
                "output_price_per_1m": 3.75,
                "effective_until": "2026-12-31",
            }
        }
    }
    historical_and_new = """
    Google models
    Standard
    Gemini 3.8 Flash through December 31, 2026 Input Global $0.75 Text output Global $3.75
    Gemini 3.8 Flash Starting January 1, 2027 Input Global $1.50 Text output Global $7.50
    """
    with pytest.raises(ValueError, match="expired on 2026-12-31"):
        matrix_source_check.validate_provider_text(
            "Google",
            historical_and_new,
            catalog,
            today=date(2027, 1, 1),
        )
