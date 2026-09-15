import pytest

import matrix_source_check


def test_anthropic_base_rates_are_read_from_first_model_rows():
    catalog = {
        "models": {
            "claude-fable-5.1": {
                "provider": "Anthropic",
                "input_price_per_1m": 10.0,
                "output_price_per_1m": 50.0,
            },
            "claude-opus-5": {
                "provider": "Anthropic",
                "input_price_per_1m": 5.0,
                "output_price_per_1m": 25.0,
            },
        }
    }
    text = """
    Model pricing
    Claude Fable 5.1 $10 / MTok $12.50 / MTok $20 / MTok $0.25 / MTok $50 / MTok
    Claude Opus 5 $5 / MTok $6.25 / MTok $10 / MTok $0.50 / MTok $25 / MTok
    """
    result = matrix_source_check.validate_provider_text("Anthropic", text, catalog)
    assert [row["model"] for row in result] == ["claude-fable-5.1", "claude-opus-5"]


def test_google_validator_uses_first_standard_occurrence_not_later_priority_repeat():
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
    Standard
    Gemini 3.1 Pro Preview Input Global $2.00 $4.00 $0.20 $0.40 Text output Global $12.00 $18.00
    Gemini 3.5 Flash Input Global $1.50 $1.50 $0.15 $0.15 Text output Global $9.00 $9.00
    Priority
    Gemini 3.1 Pro Preview Input Global $3.60 $7.20 Text output Global $21.60 $32.40
    Gemini 3.5 Flash Input Global $2.70 $2.70 Text output Global $16.20 $16.20
    """
    result = matrix_source_check.validate_provider_text("Google", text, catalog)
    assert result[0]["input_price_per_1m"] == 2.0
    assert result[0]["output_price_per_1m"] == 12.0


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
    changed = "Gemini 3.5 Flash Input Global $2.00 Text output Global $10.00"
    with pytest.raises(ValueError, match="catalog input"):
        matrix_source_check.validate_provider_text("Google", changed, catalog)
