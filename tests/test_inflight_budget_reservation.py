import asyncio
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import config_manager
import proxy_server


class _FakeResponse:
    def model_dump(self):
        return {"ok": True}


class InflightBudgetReservationTests(unittest.TestCase):
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
        self.addCleanup(self._clear_ephemeral_state)
        config_manager.init_files()
        conf = config_manager.get_config()
        conf["daily_budget_limit_usd"] = 1.00
        config_manager.save_config(conf)

    def _clear_ephemeral_state(self):
        with config_manager._DATA_LOCK:
            config_manager._INFLIGHT_RESERVATIONS.clear()
            config_manager._SETTLED_RESERVATION_IDS.clear()

    def test_parallel_reservations_cannot_spend_the_same_headroom(self):
        config_manager.update_spend(0.60, thread_id="seed")
        barrier = threading.Barrier(2)

        def reserve(index):
            barrier.wait()
            return config_manager.reserve_preflight_budget(
                f"reservation-{index}",
                0.30,
                thread_id=f"thread-{index}",
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, (1, 2)))

        accepted = [result for result in results if result["accepted"]]
        rejected = [result for result in results if not result["accepted"]]
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["reason"], "inflight_headroom")
        self.assertFalse(config_manager.get_state()["is_locked"])
        self.assertEqual(config_manager.get_inflight_reserved_usd(), 0.30)

    def test_contention_rejection_is_temporary_not_a_persistent_lock(self):
        config_manager.update_spend(0.60, thread_id="seed")
        first = config_manager.reserve_preflight_budget("first", 0.30, thread_id="A")
        blocked = config_manager.reserve_preflight_budget("blocked", 0.20, thread_id="B")

        self.assertTrue(first["accepted"])
        self.assertFalse(blocked["accepted"])
        self.assertEqual(blocked["reason"], "inflight_headroom")
        self.assertFalse(config_manager.get_state()["is_locked"])

        config_manager.release_preflight_reservation("first")
        retry = config_manager.reserve_preflight_budget("retry", 0.20, thread_id="B")
        self.assertTrue(retry["accepted"])

    def test_true_preflight_budget_breach_still_locks(self):
        config_manager.update_spend(0.80, thread_id="seed")
        result = config_manager.reserve_preflight_budget("too-large", 0.30, thread_id="A")

        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "budget_limit")
        self.assertTrue(config_manager.get_state()["is_locked"])
        self.assertEqual(config_manager.get_inflight_reserved_usd(), 0.0)

    def test_settlement_replaces_reservation_with_actual_cost_once(self):
        reserved = config_manager.reserve_preflight_budget("settle-me", 0.20, thread_id="A")
        self.assertTrue(reserved["accepted"])
        self.assertEqual(config_manager.get_inflight_reserved_usd(), 0.20)

        state = config_manager.update_spend(
            0.35,
            thread_id="A",
            reservation_id="settle-me",
        )
        self.assertEqual(state["current_spend_usd"], 0.35)
        self.assertEqual(state["total_requests"], 1)
        self.assertEqual(config_manager.get_inflight_reserved_usd(), 0.0)

        duplicate = config_manager.update_spend(
            0.35,
            thread_id="A",
            reservation_id="settle-me",
        )
        self.assertEqual(duplicate["current_spend_usd"], 0.35)
        self.assertEqual(duplicate["total_requests"], 1)

    def test_actual_cost_can_exceed_preflight_reservation_and_lock_after_settlement(self):
        config_manager.update_spend(0.70, thread_id="seed")
        reserved = config_manager.reserve_preflight_budget("underestimated", 0.20, thread_id="A")
        self.assertTrue(reserved["accepted"])

        state = config_manager.update_spend(
            0.40,
            thread_id="A",
            reservation_id="underestimated",
        )
        self.assertEqual(state["current_spend_usd"], 1.10)
        self.assertTrue(state["is_locked"])
        self.assertEqual(config_manager.get_inflight_reserved_usd(), 0.0)

    def test_upstream_failure_releases_reserved_headroom(self):
        async def fail_upstream(**kwargs):
            raise RuntimeError("provider unavailable")

        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.25, "test")), \
             patch.object(proxy_server.litellm, "acompletion", side_effect=fail_upstream):
            response = TestClient(proxy_server.app).post(
                "/v1/chat/completions",
                headers={"authorization": "Bearer test"},
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(config_manager.get_inflight_reserved_usd(), 0.0)
        self.assertEqual(config_manager.get_state()["current_spend_usd"], 0.0)

    def test_second_endpoint_request_is_stopped_before_upstream_while_first_is_inflight(self):
        started = threading.Event()
        release = threading.Event()
        upstream_calls = []

        async def held_upstream(**kwargs):
            upstream_calls.append(kwargs)
            started.set()
            while not release.is_set():
                await asyncio.sleep(0.01)
            metadata = kwargs["litellm_metadata"]
            config_manager.update_spend(
                0.20,
                thread_id=metadata[proxy_server.THREAD_METADATA_KEY],
                reservation_id=metadata[proxy_server.RESERVATION_METADATA_KEY],
            )
            return _FakeResponse()

        def send_first():
            return TestClient(proxy_server.app).post(
                "/v1/chat/completions",
                headers={"x-thread-id": "first", "authorization": "Bearer test"},
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "first"}],
                },
            )

        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.30, "test")), \
             patch.object(proxy_server.litellm, "acompletion", side_effect=held_upstream):
            with ThreadPoolExecutor(max_workers=1) as pool:
                first_future = pool.submit(send_first)
                self.assertTrue(started.wait(timeout=2.0))

                second = TestClient(proxy_server.app).post(
                    "/v1/chat/completions",
                    headers={"x-thread-id": "second", "authorization": "Bearer test"},
                    json={
                        "model": "gpt-4o",
                        "messages": [{"role": "user", "content": "second"}],
                    },
                )
                self.assertEqual(second.status_code, 429)
                self.assertIn("temporarily reserved", second.json()["detail"])
                self.assertEqual(len(upstream_calls), 1)
                self.assertFalse(config_manager.get_state()["is_locked"])

                release.set()
                first = first_future.result(timeout=2.0)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(len(upstream_calls), 1)
        self.assertEqual(config_manager.get_inflight_reserved_usd(), 0.0)
        self.assertEqual(config_manager.get_state()["current_spend_usd"], 0.20)

    def test_status_reports_actual_spend_inflight_commitment_and_available_headroom(self):
        config_manager.update_spend(0.20, thread_id="seed")
        reservation = config_manager.reserve_preflight_budget("status", 0.25, thread_id="A")
        self.assertTrue(reservation["accepted"])

        payload = TestClient(proxy_server.app).get("/api/status").json()
        self.assertEqual(payload["current_spend_usd"], 0.20)
        self.assertEqual(payload["inflight_reserved_usd"], 0.25)
        self.assertEqual(payload["committed_spend_usd"], 0.45)
        self.assertEqual(payload["remaining_budget_usd"], 0.55)
        self.assertEqual(payload["budget_used_pct"], 20.0)
        self.assertEqual(payload["budget_committed_pct"], 45.0)
        self.assertIn("Available headroom", proxy_server.DASHBOARD_HTML)
        self.assertIn("in-flight", proxy_server.DASHBOARD_HTML)


if __name__ == "__main__":
    unittest.main()
