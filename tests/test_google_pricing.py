import unittest
from types import SimpleNamespace

from google_pricing import (
    calculate_google_cost,
    calculate_google_response_cost,
    estimate_google_input_cost,
    resolve_google_model,
)


class GooglePricingTests(unittest.TestCase):
    def test_registry_resolves_provider_prefix(self):
        model = resolve_google_model("gemini/gemini-2.5-flash")
        self.assertIsNotNone(model)
        self.assertEqual(model["canonical_model_id"], "gemini-2.5-flash")

    def test_raw_standard_thinking_is_output_once(self):
        usage = {
            "promptTokenCount": 1_000,
            "candidatesTokenCount": 500,
            "thoughtsTokenCount": 250,
            "totalTokenCount": 1_750,
            "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 1_000}],
            "candidatesTokensDetails": [{"modality": "TEXT", "tokenCount": 500}],
            "serviceTier": "standard",
        }
        result = calculate_google_cost("gemini-2.5-flash", usage)
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.002175)
        self.assertEqual(result["usage"]["thinking_tokens"], 250)
        self.assertEqual(result["usage"]["output_tokens_including_thinking"], 750)

    def test_raw_cached_prompt_subtracts_cache(self):
        usage = {
            "promptTokenCount": 10_000,
            "cachedContentTokenCount": 8_000,
            "candidatesTokenCount": 1_000,
            "totalTokenCount": 11_000,
            "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 10_000}],
            "cacheTokensDetails": [{"modality": "TEXT", "tokenCount": 8_000}],
            "candidatesTokensDetails": [{"modality": "TEXT", "tokenCount": 1_000}],
            "serviceTier": "standard",
        }
        result = calculate_google_cost("gemini-2.5-flash", usage)
        self.assertTrue(result["complete"])
        self.assertEqual(result["usage"]["uncached_input_modalities"]["text"], 2_000)
        self.assertEqual(result["usage"]["cached_input_modalities"]["text"], 8_000)
        self.assertAlmostEqual(result["total_cost_usd"], 0.00334)

    def test_raw_tool_use_prompt_is_separate_billable_input(self):
        usage = {
            "promptTokenCount": 1_000,
            "toolUsePromptTokenCount": 400,
            "candidatesTokenCount": 500,
            "totalTokenCount": 1_900,
            "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 1_000}],
            "toolUsePromptTokensDetails": [{"modality": "TEXT", "tokenCount": 400}],
            "candidatesTokensDetails": [{"modality": "TEXT", "tokenCount": 500}],
            "serviceTier": "standard",
        }
        result = calculate_google_cost("gemini-2.5-flash", usage)
        self.assertTrue(result["complete"])
        self.assertEqual(result["usage"]["billable_tool_use_prompt_tokens"], 400)
        self.assertAlmostEqual(result["total_cost_usd"], 0.00167)

    def test_raw_missing_tool_use_field_is_detected_from_residual(self):
        usage = {
            "promptTokenCount": 1_000,
            "candidatesTokenCount": 500,
            "thoughtsTokenCount": 100,
            "totalTokenCount": 2_000,
            "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 1_000}],
            "candidatesTokensDetails": [{"modality": "TEXT", "tokenCount": 500}],
            "serviceTier": "standard",
        }
        result = calculate_google_cost("gemini-2.5-flash", usage)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])
        self.assertEqual(result["usage"]["unattributed_tokens"], 400)
        self.assertGreater(result["known_list_equivalent_usd"], 0)
        self.assertTrue(any("possible omitted tool-use" in n for n in result["notes"]))

    def test_litellm_normalized_tool_use_is_not_double_counted(self):
        usage = {
            "prompt_tokens": 1_400,
            "completion_tokens": 500,
            "total_tokens": 1_900,
            "prompt_tokens_details": {
                "text_tokens": 1_000,
                "tool_use_tokens": 400,
            },
            "completion_tokens_details": {"text_tokens": 500},
            "service_tier": "standard",
        }
        result = calculate_google_cost("gemini-2.5-flash", usage)
        self.assertTrue(result["complete"])
        self.assertEqual(result["usage"]["uncached_input_modalities"]["text"], 1_000)
        self.assertEqual(result["usage"]["billable_tool_use_prompt_tokens"], 400)
        self.assertAlmostEqual(result["total_cost_usd"], 0.00167)

    def test_litellm_residual_is_refused(self):
        usage = {
            "prompt_tokens": 1_000,
            "completion_tokens": 500,
            "total_tokens": 1_900,
            "prompt_tokens_details": {"text_tokens": 1_000},
            "completion_tokens_details": {"text_tokens": 500},
            "service_tier": "standard",
        }
        result = calculate_google_cost("gemini-2.5-flash", usage)
        self.assertFalse(result["complete"])
        self.assertEqual(result["usage"]["unattributed_tokens"], 400)
        self.assertTrue(any("dropped during normalization" in n for n in result["notes"]))

    def test_observed_standard_wins_over_requested_priority(self):
        response = SimpleNamespace(
            model="gemini-2.5-flash",
            usage=SimpleNamespace(
                prompt_tokens=1_000,
                completion_tokens=1_000,
                total_tokens=2_000,
                prompt_tokens_details=SimpleNamespace(text_tokens=1_000),
                completion_tokens_details=SimpleNamespace(text_tokens=1_000),
                service_tier="standard",
            ),
        )
        result = calculate_google_response_cost(
            "gemini-2.5-flash",
            response,
            request_service_tier="priority",
        )
        self.assertTrue(result["complete"])
        self.assertEqual(result["processing_mode"], "standard")
        self.assertAlmostEqual(result["total_cost_usd"], 0.0028)

    def test_priority_requested_without_observed_tier_is_incomplete(self):
        usage = {
            "prompt_tokens": 1_000,
            "completion_tokens": 1_000,
            "total_tokens": 2_000,
            "prompt_tokens_details": {"text_tokens": 1_000},
            "completion_tokens_details": {"text_tokens": 1_000},
        }
        result = calculate_google_cost(
            "gemini-2.5-flash",
            usage,
            request_service_tier="priority",
        )
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])
        self.assertTrue(any("graceful downgrade" in n for n in result["notes"]))

    def test_long_context_uses_higher_rate(self):
        usage = {
            "promptTokenCount": 250_000,
            "candidatesTokenCount": 1_000,
            "totalTokenCount": 251_000,
            "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 250_000}],
            "candidatesTokensDetails": [{"modality": "TEXT", "tokenCount": 1_000}],
            "serviceTier": "standard",
        }
        result = calculate_google_cost("gemini-2.5-pro", usage)
        self.assertTrue(result["complete"])
        self.assertTrue(result["long_context"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.64)

    def test_audio_input_uses_audio_rate(self):
        usage = {
            "promptTokenCount": 1_000,
            "candidatesTokenCount": 0,
            "totalTokenCount": 1_000,
            "promptTokensDetails": [{"modality": "AUDIO", "tokenCount": 1_000}],
            "serviceTier": "standard",
        }
        result = calculate_google_cost("gemini-2.5-flash", usage)
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.001)

    def test_search_grounding_is_list_equivalent_and_tool_input_not_double_billed(self):
        response = {
            "modelVersion": "gemini-3.5-flash",
            "usageMetadata": {
                "promptTokenCount": 1_000,
                "toolUsePromptTokenCount": 400,
                "candidatesTokenCount": 500,
                "totalTokenCount": 1_900,
                "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 1_000}],
                "toolUsePromptTokensDetails": [{"modality": "TEXT", "tokenCount": 400}],
                "candidatesTokensDetails": [{"modality": "TEXT", "tokenCount": 500}],
                "serviceTier": "standard",
            },
            "candidates": [{
                "groundingMetadata": {
                    "webSearchQueries": ["alpha", "alpha", "beta"]
                }
            }],
        }
        result = calculate_google_response_cost("gemini-3.5-flash", response)
        self.assertFalse(result["complete"])
        self.assertEqual(result["usage"]["grounding"]["search_query_count"], 2)
        self.assertEqual(result["usage"]["billable_tool_use_prompt_tokens"], 0)
        self.assertAlmostEqual(result["components_usd"]["search_grounding_list_equivalent"], 0.028)

    def test_search_requested_but_metadata_missing_is_incomplete(self):
        usage = {
            "prompt_tokens": 1_000,
            "completion_tokens": 500,
            "total_tokens": 1_500,
            "prompt_tokens_details": {"text_tokens": 1_000},
            "completion_tokens_details": {"text_tokens": 500},
            "service_tier": "standard",
        }
        result = calculate_google_cost(
            "gemini-3.5-flash",
            usage,
            request_feature_hints=["google_search"],
        )
        self.assertFalse(result["complete"])
        self.assertTrue(any("no grounding execution metadata" in n for n in result["notes"]))

    def test_vertex_platform_is_incomplete(self):
        usage = {
            "prompt_tokens": 1_000,
            "completion_tokens": 500,
            "total_tokens": 1_500,
            "prompt_tokens_details": {"text_tokens": 1_000},
            "completion_tokens_details": {"text_tokens": 500},
            "service_tier": "standard",
        }
        result = calculate_google_cost(
            "vertex_ai/gemini-2.5-flash",
            usage,
            platform="vertex_ai",
        )
        self.assertFalse(result["complete"])
        self.assertTrue(any("Vertex AI" in n for n in result["notes"]))

    def test_unknown_model_never_guesses(self):
        result = calculate_google_cost(
            "gemini-future-99",
            {"promptTokenCount": 1_000, "candidatesTokenCount": 1_000},
        )
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total_cost_usd"])
        self.assertIsNone(result["known_list_equivalent_usd"])

    def test_preflight_priority_uses_priority_rate(self):
        result = estimate_google_input_cost(
            "gemini-2.5-flash",
            1_000,
            service_tier="priority",
        )
        self.assertTrue(result["complete"])
        self.assertAlmostEqual(result["total_cost_usd"], 0.00054)


if __name__ == "__main__":
    unittest.main()
