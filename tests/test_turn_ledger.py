import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import turn_ledger


class TurnLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.ledger_path = Path(self.tempdir.name) / "turns.jsonl"
        self.override = patch.object(turn_ledger, "_LEDGER_FILE_OVERRIDE", self.ledger_path)
        self.override.start()
        self.addCleanup(self.override.stop)

    def _base_record(self, turn_id, model, provider="openai", tokens=None, cost=0.001):
        return {
            "turn_id": turn_id,
            "thread_id": "thread-mixed",
            "provider": provider,
            "requested_model_id": model,
            "canonical_model_id": model,
            "observed_model_id": model,
            "tokens": tokens or {},
            "token_basis": {
                key: "observed"
                for key, value in (tokens or {}).items()
                if value is not None
            },
            "estimated_cost_usd": cost,
            "cost_basis": "provider_registry_complete",
            "estimate_complete": True,
        }

    def test_openai_token_anatomy_does_not_double_count_reasoning(self):
        response = {
            "model": "gpt-4o",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_tokens_details": {
                    "cached_tokens": 40,
                    "cache_write_tokens": 10,
                },
                "completion_tokens_details": {"reasoning_tokens": 5},
            },
        }
        provider_result = {
            "provider": "openai",
            "canonical_model_id": "gpt-4o",
            "verified_at": "2026-09-15",
            "usage": {},
            "components_usd": {"input": 0.001, "output": 0.002},
            "notes": [],
        }
        record = turn_ledger.build_turn_record(
            turn_id="openai-1",
            thread_id="T",
            requested_model_id="gpt-4o",
            completion_response=response,
            provider_result=provider_result,
            estimated_cost_usd=0.003,
            cost_basis="provider_registry_complete",
            estimate_complete=True,
        )
        tokens = record["tokens"]
        self.assertEqual(tokens["input_tokens"], 100)
        self.assertEqual(tokens["cached_input_tokens"], 40)
        self.assertEqual(tokens["cache_write_tokens"], 10)
        self.assertEqual(tokens["uncached_input_tokens"], 50)
        self.assertEqual(tokens["output_tokens"], 20)
        self.assertEqual(tokens["reasoning_tokens"], 5)
        self.assertEqual(tokens["provider_reported_total_tokens"], 120)
        self.assertEqual(tokens["reconstructed_total_tokens"], 120)
        self.assertEqual(tokens["unclassified_tokens"], 0)

    def test_anthropic_cache_and_thinking_categories_are_preserved(self):
        response = {
            "model": "claude-sonnet-5",
            "usage": {
                "input_tokens": 80,
                "cache_creation_input_tokens": 10,
                "cache_read_input_tokens": 30,
                "output_tokens": 20,
                "output_tokens_details": {"thinking_tokens": 5},
                "server_tool_use": {"web_search_requests": 1},
            },
        }
        provider_result = {
            "provider": "anthropic",
            "canonical_model_id": "claude-sonnet-5",
            "verified_at": "2026-09-15",
            "usage": {
                "input_basis_complete": True,
                "input_tokens": 80,
                "total_input_tokens": 120,
                "cache_creation_input_tokens": 10,
                "cache_read_input_tokens": 30,
                "output_tokens": 20,
                "thinking_tokens": 5,
                "web_search_requests": 1,
                "web_fetch_requests": 0,
            },
            "notes": [],
        }
        record = turn_ledger.build_turn_record(
            turn_id="anthropic-1",
            thread_id="T",
            requested_model_id="claude-sonnet-5",
            completion_response=response,
            provider_result=provider_result,
        )
        tokens = record["tokens"]
        self.assertEqual(tokens["input_tokens"], 120)
        self.assertEqual(tokens["uncached_input_tokens"], 80)
        self.assertEqual(tokens["cache_write_tokens"], 10)
        self.assertEqual(tokens["cached_input_tokens"], 30)
        self.assertEqual(tokens["output_tokens"], 20)
        self.assertEqual(tokens["reasoning_tokens"], 5)
        self.assertEqual(tokens["reconstructed_total_tokens"], 140)
        self.assertIsNone(tokens["provider_reported_total_tokens"])
        self.assertEqual(record["server_tools"], {"web_search_requests": 1})

    def test_google_residual_tokens_are_explicit(self):
        response = {
            "modelVersion": "gemini-3.8-flash",
            "usageMetadata": {
                "promptTokenCount": 100,
                "cachedContentTokenCount": 20,
                "candidatesTokenCount": 30,
                "thoughtsTokenCount": 10,
                "toolUsePromptTokenCount": 5,
                "totalTokenCount": 150,
                "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 100}],
                "cacheTokensDetails": [{"modality": "TEXT", "tokenCount": 20}],
                "candidatesTokensDetails": [{"modality": "TEXT", "tokenCount": 30}],
                "toolUsePromptTokensDetails": [{"modality": "TEXT", "tokenCount": 5}],
            },
        }
        provider_result = {
            "provider": "google",
            "canonical_model_id": "gemini-3.8-flash",
            "verified_at": "2026-09-15",
            "usage": {
                "source_shape": "google_raw",
                "prompt_total_tokens": 100,
                "cached_tokens": 20,
                "tool_use_prompt_tokens": 5,
                "thinking_tokens": 10,
                "output_tokens_including_thinking": 40,
                "total_tokens": 150,
                "unattributed_tokens": 5,
                "uncached_input_modalities": {"text": 80, "image": 0, "video": 0, "audio": 0},
                "cached_input_modalities": {"text": 20, "image": 0, "video": 0, "audio": 0},
                "candidate_output_modalities": {"text": 30, "image": 0, "video": 0, "audio": 0},
                "tool_use_prompt_modalities": {"text": 5, "image": 0, "video": 0, "audio": 0},
                "grounding": {"grounding_metadata_observed": False},
            },
            "notes": ["totalTokenCount contains unattributed tokens."],
        }
        record = turn_ledger.build_turn_record(
            turn_id="google-1",
            thread_id="T",
            requested_model_id="gemini-3.8-flash",
            completion_response=response,
            provider_result=provider_result,
        )
        tokens = record["tokens"]
        self.assertEqual(tokens["input_tokens"], 100)
        self.assertEqual(tokens["cached_input_tokens"], 20)
        self.assertEqual(tokens["uncached_input_tokens"], 80)
        self.assertEqual(tokens["tool_input_tokens"], 5)
        self.assertEqual(tokens["output_tokens"], 30)
        self.assertEqual(tokens["reasoning_tokens"], 10)
        self.assertEqual(tokens["provider_reported_total_tokens"], 150)
        self.assertEqual(tokens["reconstructed_total_tokens"], 145)
        self.assertEqual(tokens["unclassified_tokens"], 5)
        self.assertEqual(tokens["reconciliation_delta_tokens"], 5)
        self.assertEqual(record["modalities"]["output"]["text"], 30)

    def test_google_maps_unknown_query_count_survives_append_as_null(self):
        response = {
            "modelVersion": "gemini-3.8-flash",
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 20,
                "totalTokenCount": 120,
                "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 100}],
                "candidatesTokensDetails": [{"modality": "TEXT", "tokenCount": 20}],
            },
        }
        provider_result = {
            "provider": "google",
            "canonical_model_id": "gemini-3.8-flash",
            "verified_at": "2026-09-15",
            "usage": {
                "source_shape": "google_raw",
                "prompt_total_tokens": 100,
                "cached_tokens": 0,
                "tool_use_prompt_tokens": 0,
                "thinking_tokens": 0,
                "output_tokens_including_thinking": 20,
                "total_tokens": 120,
                "unattributed_tokens": 0,
                "uncached_input_modalities": {"text": 100, "image": 0, "video": 0, "audio": 0},
                "cached_input_modalities": {"text": 0, "image": 0, "video": 0, "audio": 0},
                "candidate_output_modalities": {"text": 20, "image": 0, "video": 0, "audio": 0},
                "tool_use_prompt_modalities": None,
                "grounding": {
                    "grounding_metadata_observed": True,
                    "search_used": False,
                    "search_query_count": 0,
                    "search_query_count_basis": "derived",
                    "maps_used": True,
                    "maps_query_count": None,
                    "maps_query_count_basis": "unavailable",
                },
            },
            "notes": ["Exact Gemini 3 Maps search-query count unavailable."],
        }
        record = turn_ledger.build_turn_record(
            turn_id="google-maps-unknown",
            thread_id="T",
            requested_model_id="gemini-3.8-flash",
            completion_response=response,
            provider_result=provider_result,
        )
        self.assertTrue(record["server_tools"]["maps_used"])
        self.assertIsNone(record["server_tools"]["maps_query_count"])
        self.assertEqual(record["server_tools"]["maps_query_count_basis"], "unavailable")
        self.assertEqual(record["server_tools"]["search_query_count"], 0)

        self.assertTrue(turn_ledger.append_turn(record))
        stored = turn_ledger.read_turns(thread_id="T")[0]
        self.assertTrue(stored["server_tools"]["maps_used"])
        self.assertIsNone(stored["server_tools"]["maps_query_count"])
        self.assertEqual(stored["server_tools"]["maps_query_count_basis"], "unavailable")
        self.assertEqual(stored["server_tools"]["search_query_count"], 0)

    def test_missing_optional_telemetry_is_not_silently_zero(self):
        response = {
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        }
        record = turn_ledger.build_turn_record(
            turn_id="missing-1",
            thread_id="T",
            requested_model_id="gpt-4o",
            completion_response=response,
            provider_result={"provider": "openai", "canonical_model_id": "gpt-4o", "usage": {}},
        )
        tokens = record["tokens"]
        self.assertEqual(tokens["input_tokens"], 10)
        self.assertEqual(tokens["output_tokens"], 2)
        self.assertIsNone(tokens["cached_input_tokens"])
        self.assertIsNone(tokens["cache_write_tokens"])
        self.assertIsNone(tokens["uncached_input_tokens"])
        self.assertIsNone(tokens["reasoning_tokens"])
        self.assertIsNone(tokens["provider_reported_total_tokens"])
        self.assertEqual(tokens["reconstructed_total_tokens"], 12)
        self.assertEqual(record["token_basis"]["cached_input_tokens"], "unavailable")

    def test_explicit_zero_remains_observed_zero(self):
        response = {
            "model": "gpt-4o",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                "completion_tokens_details": {"reasoning_tokens": 0},
            },
        }
        record = turn_ledger.build_turn_record(
            turn_id="zero-1",
            thread_id="T",
            requested_model_id="gpt-4o",
            completion_response=response,
            provider_result={"provider": "openai", "canonical_model_id": "gpt-4o", "usage": {}},
        )
        self.assertEqual(record["tokens"]["cached_input_tokens"], 0)
        self.assertEqual(record["tokens"]["cache_write_tokens"], 0)
        self.assertEqual(record["tokens"]["reasoning_tokens"], 0)
        self.assertEqual(record["tokens"]["uncached_input_tokens"], 10)
        self.assertEqual(record["token_basis"]["reasoning_tokens"], "observed")

    def test_append_is_append_only_idempotent_and_strips_non_schema_content(self):
        first = self._base_record("turn-1", "gpt-4o", tokens={"input_tokens": 10})
        first["messages"] = [{"role": "user", "content": "SECRET PROMPT TEXT"}]
        first["response_text"] = "SECRET RESPONSE TEXT"
        first["api_key"] = "SECRET-KEY"
        second = self._base_record("turn-2", "gpt-4o", tokens={"input_tokens": 20})

        self.assertTrue(turn_ledger.append_turn(first))
        self.assertFalse(turn_ledger.append_turn(first))
        self.assertTrue(turn_ledger.append_turn(second))

        lines = self.ledger_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        raw_file = self.ledger_path.read_text(encoding="utf-8")
        self.assertNotIn("SECRET PROMPT TEXT", raw_file)
        self.assertNotIn("SECRET RESPONSE TEXT", raw_file)
        self.assertNotIn("SECRET-KEY", raw_file)
        records = turn_ledger.read_turns()
        self.assertEqual([r["turn_id"] for r in records], ["turn-1", "turn-2"])

    def test_corruption_is_reported_not_silently_skipped(self):
        self.ledger_path.write_text('{"turn_id":"good"}\nnot-json\n', encoding="utf-8")
        with self.assertRaises(turn_ledger.LedgerCorruptionError):
            turn_ledger.read_turns()

    def test_picodollar_cost_sum_preserves_pricing_component_precision(self):
        first = self._base_record("pico-1", "gpt-4o", tokens={"input_tokens": 1}, cost=0.000000000001)
        second = self._base_record("pico-2", "gpt-4o", tokens={"input_tokens": 1}, cost=0.000000000002)
        turn_ledger.append_turn(first)
        turn_ledger.append_turn(second)
        summary = turn_ledger.summarize_thread("thread-mixed")
        self.assertEqual(summary["estimated_cost_picos"], 3)
        self.assertEqual(summary["estimated_cost_usd"], 0.000000000003)

    def test_same_thread_preserves_separate_model_totals(self):
        records = [
            self._base_record(
                "mix-1",
                "gemini-3.8-flash",
                provider="google",
                tokens={"input_tokens": 100, "output_tokens": 10, "reasoning_tokens": None},
                cost=0.10,
            ),
            self._base_record(
                "mix-2",
                "claude-sonnet-5",
                provider="anthropic",
                tokens={"input_tokens": 200, "output_tokens": 20, "reasoning_tokens": 5},
                cost=0.20,
            ),
            self._base_record(
                "mix-3",
                "gpt-5.6-sol",
                provider="openai",
                tokens={"input_tokens": 300, "output_tokens": 30, "reasoning_tokens": 7},
                cost=0.30,
            ),
            self._base_record(
                "mix-4",
                "gemini-3.8-flash",
                provider="google",
                tokens={"input_tokens": 400, "output_tokens": 40, "reasoning_tokens": None},
                cost=0.40,
            ),
        ]
        for record in records:
            turn_ledger.append_turn(record)

        summary = turn_ledger.summarize_thread("thread-mixed")
        self.assertEqual(summary["turn_count"], 4)
        self.assertEqual(summary["tokens"]["input_tokens"]["sum"], 1000)
        self.assertEqual(summary["tokens"]["input_tokens"]["observed_turns"], 4)
        self.assertEqual(summary["tokens"]["reasoning_tokens"]["sum"], 12)
        self.assertEqual(summary["tokens"]["reasoning_tokens"]["observed_turns"], 2)
        self.assertAlmostEqual(summary["estimated_cost_usd"], 1.0, places=12)

        self.assertEqual(summary["by_model"]["gemini-3.8-flash"]["turn_count"], 2)
        self.assertEqual(
            summary["by_model"]["gemini-3.8-flash"]["tokens"]["input_tokens"]["sum"],
            500,
        )
        self.assertEqual(summary["by_model"]["claude-sonnet-5"]["turn_count"], 1)
        self.assertEqual(summary["by_model"]["gpt-5.6-sol"]["turn_count"], 1)
        self.assertEqual(
            summary["by_model"]["gemini-3.8-flash"]["tokens"]["reasoning_tokens"]["observed_turns"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
