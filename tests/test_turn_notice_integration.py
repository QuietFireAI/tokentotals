import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import config_manager
import proxy_server
import turn_notice


class _FakeResponse:
    def model_dump(self):
        return {"ok": True}


class TurnNoticeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        app_dir = Path(self.tempdir.name) / ".tokentotals"
        self.paths = patch.multiple(
            config_manager,
            APP_DIR=app_dir,
            CONFIG_FILE=app_dir / "config.json",
            STATE_FILE=app_dir / "state.json",
        )
        self.paths.start()
        self.addCleanup(self.paths.stop)
        with config_manager._DATA_LOCK:
            config_manager._INFLIGHT_RESERVATIONS.clear()
            config_manager._SETTLED_RESERVATION_IDS.clear()
        turn_notice.reset_runtime_notices()
        self.addCleanup(self._clear_runtime_state)
        config_manager.init_files()
        conf = config_manager.get_config()
        conf["daily_budget_limit_usd"] = 100.0
        conf["turn_notice_threshold_usd"] = 0.20
        config_manager.save_config(conf)
        self.client = TestClient(proxy_server.app)

    def _clear_runtime_state(self):
        with config_manager._DATA_LOCK:
            config_manager._INFLIGHT_RESERVATIONS.clear()
            config_manager._SETTLED_RESERVATION_IDS.clear()
        turn_notice.reset_runtime_notices()

    def _times(self):
        start = datetime.now()
        return start, start + timedelta(milliseconds=100)

    def _callback_kwargs(self, reservation_id, model="gpt-4o", thread_id="thread-live", response_cost=0.0):
        return {
            "model": model,
            "response_cost": response_cost,
            "litellm_params": {
                "litellm_metadata": {
                    proxy_server.THREAD_METADATA_KEY: thread_id,
                    proxy_server.RESERVATION_METADATA_KEY: reservation_id,
                }
            },
        }

    def test_accepted_preflight_publishes_notice_after_admission(self):
        async def fake_upstream(**kwargs):
            return _FakeResponse()

        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.25, "test_preflight")), \
             patch.object(proxy_server.litellm, "acompletion", side_effect=fake_upstream):
            response = self.client.post(
                "/v1/chat/completions",
                headers={"x-thread-id": "thread-a", "authorization": "Bearer test"},
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )

        self.assertEqual(response.status_code, 200)
        notice = turn_notice.latest_notice("thread-a")
        self.assertIsNotNone(notice)
        self.assertEqual(notice["stage"], "preflight")
        self.assertEqual(notice["model_id"], "gpt-4o")
        self.assertEqual(notice["cost_basis"], "test_preflight")
        self.assertEqual(notice["estimated_cost_usd"], 0.25)
        self.assertFalse(notice["estimate_complete"])

    def test_rejected_preflight_does_not_publish_notice(self):
        conf = config_manager.get_config()
        conf["daily_budget_limit_usd"] = 0.10
        conf["turn_notice_threshold_usd"] = 0.05
        config_manager.save_config(conf)

        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.25, "test_preflight")):
            response = self.client.post(
                "/v1/chat/completions",
                headers={"x-thread-id": "thread-blocked", "authorization": "Bearer test"},
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertIsNone(turn_notice.latest_notice("thread-blocked"))

    def test_completed_notice_survives_ledger_write_failure(self):
        reservation_id = "turn-completed"
        reserved = config_manager.reserve_preflight_budget(reservation_id, 0.01, thread_id="thread-live")
        self.assertTrue(reserved["accepted"])
        response = {
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }
        provider_result = {
            "provider": "openai",
            "canonical_model_id": "gpt-4o",
            "complete": True,
            "total_cost_usd": 0.25,
            "components_usd": {},
            "usage": {},
            "notes": [],
        }
        start, end = self._times()
        with patch.object(proxy_server, "calculate_openai_response_cost", return_value=provider_result), \
             patch.object(proxy_server.turn_ledger, "append_turn", side_effect=OSError("disk full")):
            proxy_server.track_cost_callback(
                self._callback_kwargs(reservation_id),
                response,
                start,
                end,
            )

        self.assertEqual(config_manager.get_state()["current_spend_usd"], 0.25)
        notice = turn_notice.latest_notice("thread-live")
        self.assertEqual(notice["stage"], "completed")
        self.assertEqual(notice["estimated_cost_usd"], 0.25)
        self.assertEqual(notice["cost_basis"], "provider_registry_complete")
        self.assertTrue(notice["estimate_complete"])

    def test_unavailable_completed_cost_does_not_publish_notice(self):
        reservation_id = "turn-unavailable"
        reserved = config_manager.reserve_preflight_budget(reservation_id, 0.01, thread_id="thread-live")
        self.assertTrue(reserved["accepted"])
        response = {
            "model": "other-provider/model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }
        start, end = self._times()
        proxy_server.track_cost_callback(
            self._callback_kwargs(reservation_id, model="other-provider/model", response_cost=0.0),
            response,
            start,
            end,
        )

        self.assertIsNone(turn_notice.latest_notice("thread-live"))

    def test_notice_api_reports_disabled_enabled_and_thread_scope(self):
        conf = config_manager.get_config()
        conf["turn_notice_threshold_usd"] = None
        config_manager.save_config(conf)
        disabled = self.client.get("/api/turn-notice")
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.json()["enabled"])
        self.assertIsNone(disabled.json()["reminder_threshold_usd"])
        self.assertIsNone(disabled.json()["notice"])

        conf["turn_notice_threshold_usd"] = 0.20
        config_manager.save_config(conf)
        turn_notice.evaluate_and_publish(
            stage="completed",
            estimated_cost_usd=0.25,
            threshold_usd=0.20,
            thread_id="thread-api",
            turn_id="turn-api",
            model_id="gpt-4o",
            cost_basis="provider_registry_complete",
            estimate_complete=True,
        )
        enabled = self.client.get("/api/turn-notice", params={"thread_id": "thread-api"})
        self.assertEqual(enabled.status_code, 200)
        payload = enabled.json()
        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["reminder_threshold_usd"], 0.20)
        self.assertEqual(payload["scope"], "thread")
        self.assertEqual(payload["thread_id"], "thread-api")
        self.assertEqual(payload["notice"]["event_id"], "turn-api:completed")

        blank = self.client.get("/api/turn-notice", params={"thread_id": "   "})
        self.assertEqual(blank.status_code, 400)


if __name__ == "__main__":
    unittest.main()
