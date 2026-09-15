import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_manager


class TurnNoticeConfigTests(unittest.TestCase):
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

    def test_new_config_disables_turn_notice_by_default(self):
        config_manager.init_files()
        conf = config_manager.get_config()
        self.assertIn("turn_notice_threshold_usd", conf)
        self.assertIsNone(conf["turn_notice_threshold_usd"])

    def test_legacy_config_without_key_reads_as_disabled(self):
        config_manager.APP_DIR.mkdir(parents=True, exist_ok=True)
        with config_manager.CONFIG_FILE.open("w", encoding="utf-8") as handle:
            json.dump({
                "daily_budget_limit_usd": 10.0,
                "port": 8080,
                "warning_threshold_pct": 75,
            }, handle)
        with config_manager.STATE_FILE.open("w", encoding="utf-8") as handle:
            json.dump(config_manager._fresh_default_state(), handle)

        conf = config_manager.get_config()
        self.assertIsNone(conf["turn_notice_threshold_usd"])


if __name__ == "__main__":
    unittest.main()
