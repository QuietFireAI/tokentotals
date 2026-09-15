import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import config_manager
import proxy_server


class _FakeResponse:
    def model_dump(self):
        return {"ok": True}


class ConcurrentAccountingTests(unittest.TestCase):
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
        self.addCleanup(self._clear_ephemeral_reservations)
        config_manager.init_files()

    def _clear_ephemeral_reservations(self):
        with config_manager._DATA_LOCK:
            config_manager._INFLIGHT_RESERVATIONS.clear()
            config_manager._SETTLED_RESERVATION_IDS.clear()

    def test_interleaved_a_b_a_preserves_each_thread_total(self):
        config_manager.update_spend(0.10, thread_id="A")
        config_manager.update_spend(0.20, thread_id="B")
        state = config_manager.update_spend(0.30, thread_id="A")

        self.assertEqual(state["current_spend_usd"], 0.60)
        self.assertEqual(state["total_requests"], 3)
        self.assertEqual(state["thread_spend_by_id"]["A"], 0.40)
        self.assertEqual(state["thread_spend_by_id"]["B"], 0.20)
        self.assertEqual(state["active_thread_id"], "A")
        self.assertEqual(state["thread_spend_usd"], 0.40)

    def test_parallel_updates_do_not_lose_spend_or_request_counts(self):
        workers = 16
        updates = 100

        def add_one(index):
            config_manager.update_spend(0.01, thread_id=f"thread-{index % 4}")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(add_one, range(updates)))

        state = config_manager.get_state()
        self.assertEqual(state["current_spend_usd"], 1.00)
        self.assertEqual(state["total_requests"], updates)
        self.assertEqual(sum(state["thread_spend_by_id"].values()), 1.00)
        for thread_id in range(4):
            self.assertEqual(state["thread_spend_by_id"][f"thread-{thread_id}"], 0.25)

    def test_legacy_active_thread_total_is_preserved_on_first_update(self):
        legacy_state = {
            "date": str(config_manager.date.today()),
            "current_spend_usd": 1.25,
            "thread_spend_usd": 0.75,
            "active_thread_id": "legacy-thread",
            "is_locked": False,
            "total_requests": 5,
        }
        with open(config_manager.STATE_FILE, "w") as handle:
            json.dump(legacy_state, handle)

        state = config_manager.update_spend(0.25, thread_id="new-thread")

        self.assertEqual(state["current_spend_usd"], 1.50)
        self.assertEqual(state["thread_spend_by_id"]["legacy-thread"], 0.75)
        self.assertEqual(state["thread_spend_by_id"]["new-thread"], 0.25)
        self.assertEqual(state["active_thread_id"], "new-thread")
        self.assertEqual(state["thread_spend_usd"], 0.25)
        self.assertEqual(state["total_requests"], 6)

    def test_callbacks_use_their_own_request_local_thread_metadata(self):
        recorded = []

        def record_spend(cost_usd, thread_id=None, reservation_id=None):
            recorded.append((cost_usd, thread_id, reservation_id))

        start = datetime.now()
        with patch.object(proxy_server.config_manager, "update_spend", side_effect=record_spend):
            proxy_server.track_cost_callback(
                {
                    "model": "other-provider/model-a",
                    "response_cost": 0.11,
                    "litellm_params": {
                        "litellm_metadata": {proxy_server.THREAD_METADATA_KEY: "thread-A"}
                    },
                },
                None,
                start,
                start,
            )
            proxy_server.track_cost_callback(
                {
                    "model": "other-provider/model-b",
                    "response_cost": 0.22,
                    "litellm_params": {
                        "litellm_metadata": {proxy_server.THREAD_METADATA_KEY: "thread-B"}
                    },
                },
                None,
                start,
                start,
            )
            # Complete A after B to model out-of-order concurrent completions.
            proxy_server.track_cost_callback(
                {
                    "model": "other-provider/model-a",
                    "response_cost": 0.33,
                    "litellm_params": {
                        "litellm_metadata": {proxy_server.THREAD_METADATA_KEY: "thread-A"}
                    },
                },
                None,
                start,
                start,
            )

        self.assertEqual(
            recorded,
            [
                (0.11, "thread-A", None),
                (0.22, "thread-B", None),
                (0.33, "thread-A", None),
            ],
        )

    def test_client_metadata_cannot_spoof_server_thread_attribution(self):
        captured = {}

        async def fake_acompletion(**kwargs):
            captured.update(kwargs)
            return _FakeResponse()

        with patch.object(proxy_server, "preflight_input_estimate", return_value=(0.0, "test")), \
             patch.object(proxy_server.litellm, "acompletion", side_effect=fake_acompletion):
            client = TestClient(proxy_server.app)
            response = client.post(
                "/v1/chat/completions",
                headers={"x-thread-id": "trusted-thread", "authorization": "Bearer test"},
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "hello"}],
                    "litellm_metadata": {
                        proxy_server.THREAD_METADATA_KEY: "spoofed-thread",
                        proxy_server.RESERVATION_METADATA_KEY: "spoofed-reservation",
                        "other": "client-data",
                    },
                },
            )

        self.assertEqual(response.status_code, 200)
        metadata = captured["litellm_metadata"]
        self.assertEqual(metadata[proxy_server.THREAD_METADATA_KEY], "trusted-thread")
        self.assertTrue(metadata[proxy_server.RESERVATION_METADATA_KEY])
        self.assertNotEqual(metadata[proxy_server.THREAD_METADATA_KEY], "spoofed-thread")
        self.assertNotEqual(
            metadata[proxy_server.RESERVATION_METADATA_KEY],
            "spoofed-reservation",
        )
        self.assertNotIn("other", metadata)
        config_manager.release_preflight_reservation(
            metadata[proxy_server.RESERVATION_METADATA_KEY]
        )

    def test_public_docs_state_concurrency_guarantee_and_inflight_boundary(self):
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        whitepaper = (root / "TokenTotals_Security_Whitepaper.md").read_text(encoding="utf-8-sig")

        for document in (readme, whitepaper):
            lower = document.lower()
            self.assertIn("request-local", lower)
            self.assertIn("in-flight", lower)
            self.assertIn("reserve", lower)
            self.assertIn("input", lower)
            self.assertTrue(
                "output" in lower or "full-turn" in lower,
                "public docs must distinguish preflight input reservation from final turn cost",
            )


if __name__ == "__main__":
    unittest.main()
