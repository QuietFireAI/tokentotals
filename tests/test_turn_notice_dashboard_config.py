import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import config_manager
import proxy_server
import turn_notice


class TurnNoticeDashboardConfigTests(unittest.TestCase):
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
        config_manager.init_files()
        turn_notice.reset_runtime_notices()
        self.addCleanup(turn_notice.reset_runtime_notices)
        self.client = TestClient(proxy_server.app)

    def test_positive_reminder_threshold_can_be_set_and_read_back(self):
        response = self.client.post(
            "/api/turn-notice/config",
            json={"reminder_threshold_usd": 0.25},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["reminder_threshold_usd"], 0.25)
        self.assertIn("not a provider account balance", payload["meaning"])
        self.assertEqual(config_manager.get_config()["turn_notice_threshold_usd"], 0.25)

        status = self.client.get("/api/turn-notice").json()
        self.assertTrue(status["enabled"])
        self.assertEqual(status["reminder_threshold_usd"], 0.25)

    def test_null_disables_reminder_threshold(self):
        conf = config_manager.get_config()
        conf["turn_notice_threshold_usd"] = 0.50
        config_manager.save_config(conf)

        response = self.client.post(
            "/api/turn-notice/config",
            json={"reminder_threshold_usd": None},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["enabled"])
        self.assertIsNone(response.json()["reminder_threshold_usd"])
        self.assertIsNone(config_manager.get_config()["turn_notice_threshold_usd"])

    def test_invalid_reminder_threshold_values_are_rejected(self):
        cases = [
            {},
            {"reminder_threshold_usd": 0},
            {"reminder_threshold_usd": -1},
            {"reminder_threshold_usd": "0.25"},
            {"reminder_threshold_usd": True},
        ]
        for body in cases:
            with self.subTest(body=body):
                response = self.client.post("/api/turn-notice/config", json=body)
                self.assertEqual(response.status_code, 400)

        self.assertIsNone(config_manager.get_config()["turn_notice_threshold_usd"])


if __name__ == "__main__":
    unittest.main()
