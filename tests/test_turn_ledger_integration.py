import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import config_manager
import proxy_server
import turn_ledger


class TurnLedgerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        app_dir = Path(self.tempdir.name) / ".tokentotals"
        self.ledger_file = app_dir / "turns.jsonl"
        self.paths = patch.multiple(
            config_manager,
            APP_DIR=app_dir,
            CONFIG_FILE=app_dir / "config.json",
            STATE_FILE=app_dir / "state.json",
        )
        self.paths.start()
        self.addCleanup(self.paths.stop)
        self.ledger_override = patch.object(turn_ledger, "_LEDGER_FILE_OVERRIDE", self.ledger_file)
        self.ledger_override.start()
        self.addCleanup(self.ledger_override.stop)
        with config_manager._DATA_LOCK:
            config_manager._INFLIGHT_RESERVATIONS.clear()
            config_manager._SETTLED_RESERVATION_IDS.clear()
        with turn_ledger._LEDGER_LOCK:
            turn_ledger._SEEN_LEDGER_PATH = None
            turn_ledger._SEEN_TURN_IDS = None
        self.addCleanup(self._clear_ephemeral_state)
        config_manager.init_files()
        conf = config_manager.get_config()
        conf["daily_budget_limit_usd"] = 100.0
        config_manager.save_config(conf)

    def _clear_ephemeral_state(self):
        with config_manager._DATA_LOCK:
            config_manager._INFLIGHT_RESERVATIONS.clear()
            config_manager._SETTLED_RESERVATION_IDS.clear()
        with turn_ledger._LEDGER_LOCK:
            turn_ledger._SEEN_LEDGER_PATH = None
            turn_ledger._SEEN_TURN_IDS = None

    def _times(self):
        start = datetime.now()
        return start, start + timedelta(milliseconds=125)

    def _kwargs(self, model, reservation_id, thread_id="thread-live", response_cost=0.0, **extra):
        kwargs = {
            "model": model,
            "response_cost": response_cost,
            "litellm_params": {
                "litellm_metadata": {
                    proxy_server.THREAD_METADATA_KEY: thread_id,
                    proxy_server.RESERVATION_METADATA_KEY: reservation_id,
                }
            },
        }
        kwargs.update(extra)
        return kwargs

    def _reserve(self, reservation_id, thread_id="thread-live", amount=0.01):
        result = config_manager.reserve_preflight_budget(
            reservation_id,
            amount,
            thread_id=thread_id,
        )
        self.assertTrue(result["accepted"])

    def test_complete_provider_callback_settles_and_appends_turn(self):
        reservation_id = "turn-complete"
        self._reserve(reservation_id)
        response = {
            "model": "gpt-4o",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_tokens_details": {"cached_tokens": 40, "cache_write_tokens": 0},
                "completion_tokens_details": {"reasoning_tokens": 5},
            },
        }
        provider_result = {
            "provider": "openai",
            "canonical_model_id": "gpt-4o",
            "response_model_id": "gpt-4o",
            "verified_at": "2026-09-15",
            "complete": True,
            "total_cost_usd": 0.0123456789,
            "components_usd": {"input": 0.002, "output": 0.0103456789},
            "usage": {},
            "notes": [],
        }
        start, end = self._times()
        with patch.object(proxy_server, "calculate_openai_response_cost", return_value=provider_result):
            proxy_server.track_cost_callback(
                self._kwargs("gpt-4o", reservation_id),
                response,
                start,
                end,
            )

        state = config_manager.get_state()
        self.assertEqual(state["current_spend_usd"], 0.0123456789)
        self.assertEqual(state["total_requests"], 1)
        self.assertEqual(config_manager.get_inflight_reserved_usd(), 0.0)

        records = turn_ledger.read_turns(thread_id="thread-live")
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["turn_id"], reservation_id)
        self.assertEqual(record["requested_model_id"], "gpt-4o")
        self.assertEqual(record["canonical_model_id"], "gpt-4o")
        self.assertEqual(record["cost_basis"], "provider_registry_complete")
        self.assertTrue(record["estimate_complete"])
        self.assertEqual(record["estimated_cost_usd"], 0.0123456789)
        self.assertEqual(record["tokens"]["input_tokens"], 100)
        self.assertEqual(record["tokens"]["cached_input_tokens"], 40)
        self.assertEqual(record["tokens"]["output_tokens"], 20)
        self.assertEqual(record["latency_ms"], 125)

    def test_incomplete_provider_uses_litellm_cost_with_explicit_fallback_basis(self):
        reservation_id = "turn-litellm-fallback"
        self._reserve(reservation_id)
        response = {
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }
        provider_result = {
            "provider": "openai",
            "canonical_model_id": "gpt-4o",
            "complete": False,
            "total_cost_usd": None,
            "usage": {},
            "notes": ["test unresolved dimension"],
        }
        start, end = self._times()
        with patch.object(proxy_server, "calculate_openai_response_cost", return_value=provider_result):
            proxy_server.track_cost_callback(
                self._kwargs("gpt-4o", reservation_id, response_cost=0.031),
                response,
                start,
                end,
            )

        record = turn_ledger.read_turns()[0]
        self.assertEqual(record["estimated_cost_usd"], 0.031)
        self.assertEqual(record["cost_basis"], "litellm_response_cost_fallback")
        self.assertFalse(record["estimate_complete"])
        self.assertEqual(config_manager.get_state()["current_spend_usd"], 0.031)

    def test_known_list_equivalent_is_labeled_incomplete(self):
        reservation_id = "turn-known-equivalent"
        self._reserve(reservation_id)
        response = {
            "model": "claude-sonnet-5",
            "usage": {"input_tokens": 10, "output_tokens": 2},
        }
        provider_result = {
            "provider": "anthropic",
            "canonical_model_id": "claude-sonnet-5",
            "complete": False,
            "total_cost_usd": None,
            "known_list_equivalent_usd": 0.044,
            "usage": {
                "input_basis_complete": True,
                "input_tokens": 10,
                "total_input_tokens": 10,
                "output_tokens": 2,
            },
            "notes": ["account-specific dimension unresolved"],
        }
        start, end = self._times()
        with patch.object(proxy_server, "calculate_anthropic_response_cost", return_value=provider_result):
            proxy_server.track_cost_callback(
                self._kwargs("claude-sonnet-5", reservation_id, response_cost=0.0),
                response,
                start,
                end,
            )

        record = turn_ledger.read_turns()[0]
        self.assertEqual(record["estimated_cost_usd"], 0.044)
        self.assertEqual(record["cost_basis"], "known_list_equivalent")
        self.assertFalse(record["estimate_complete"])
        self.assertEqual(config_manager.get_state()["current_spend_usd"], 0.044)

    def test_no_defensible_post_response_cost_is_unknown_not_fake_zero(self):
        reservation_id = "turn-cost-unknown"
        self._reserve(reservation_id)
        response = {
            "model": "other-provider/model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }
        start, end = self._times()
        proxy_server.track_cost_callback(
            self._kwargs("other-provider/model", reservation_id, response_cost=0.0),
            response,
            start,
            end,
        )

        state = config_manager.get_state()
        self.assertEqual(state["current_spend_usd"], 0.0)
        self.assertEqual(state["total_requests"], 1)
        record = turn_ledger.read_turns()[0]
        self.assertIsNone(record["estimated_cost_usd"])
        self.assertIsNone(record["estimated_cost_picos"])
        self.assertEqual(record["cost_basis"], "unavailable")
        self.assertFalse(record["estimate_complete"])
        self.assertEqual(record["tokens"]["provider_reported_total_tokens"], 12)

    def test_duplicate_callback_same_server_turn_id_does_not_double_count(self):
        reservation_id = "turn-duplicate"
        self._reserve(reservation_id)
        response = {
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }
        provider_result = {
            "provider": "openai",
            "canonical_model_id": "gpt-4o",
            "complete": True,
            "total_cost_usd": 0.02,
            "components_usd": {},
            "usage": {},
            "notes": [],
        }
        start, end = self._times()
        with patch.object(proxy_server, "calculate_openai_response_cost", return_value=provider_result):
            kwargs = self._kwargs("gpt-4o", reservation_id)
            proxy_server.track_cost_callback(kwargs, response, start, end)
            proxy_server.track_cost_callback(kwargs, response, start, end)

        state = config_manager.get_state()
        self.assertEqual(state["current_spend_usd"], 0.02)
        self.assertEqual(state["total_requests"], 1)
        self.assertEqual(len(turn_ledger.read_turns()), 1)

    def test_ledger_io_failure_does_not_undo_accounting_settlement(self):
        reservation_id = "turn-ledger-failure"
        self._reserve(reservation_id)
        response = {
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }
        provider_result = {
            "provider": "openai",
            "canonical_model_id": "gpt-4o",
            "complete": True,
            "total_cost_usd": 0.025,
            "components_usd": {},
            "usage": {},
            "notes": [],
        }
        start, end = self._times()
        with patch.object(proxy_server, "calculate_openai_response_cost", return_value=provider_result), \
             patch.object(proxy_server.turn_ledger, "append_turn", side_effect=OSError("disk full")):
            proxy_server.track_cost_callback(
                self._kwargs("gpt-4o", reservation_id),
                response,
                start,
                end,
            )

        state = config_manager.get_state()
        self.assertEqual(state["current_spend_usd"], 0.025)
        self.assertEqual(state["total_requests"], 1)
        self.assertEqual(config_manager.get_inflight_reserved_usd(), 0.0)

    def test_callback_secrets_are_not_written_to_ledger(self):
        reservation_id = "turn-private"
        self._reserve(reservation_id)
        response = {
            "model": "other-provider/model",
            "usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5},
        }
        start, end = self._times()
        kwargs = self._kwargs(
            "other-provider/model",
            reservation_id,
            response_cost=0.01,
            messages=[{"role": "user", "content": "SECRET CALLBACK PROMPT"}],
            api_key="SECRET CALLBACK KEY",
        )
        proxy_server.track_cost_callback(kwargs, response, start, end)

        raw = self.ledger_file.read_text(encoding="utf-8")
        self.assertNotIn("SECRET CALLBACK PROMPT", raw)
        self.assertNotIn("SECRET CALLBACK KEY", raw)
        record = turn_ledger.read_turns()[0]
        self.assertEqual(record["cost_basis"], "litellm_response_cost_fallback")


if __name__ == "__main__":
    unittest.main()
