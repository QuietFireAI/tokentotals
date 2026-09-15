import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_manager
import proxy_server


class MoneyPrecisionTests(unittest.TestCase):
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
        config_manager.init_files()
        conf = config_manager.get_config()
        conf["daily_budget_limit_usd"] = 100.0
        config_manager.save_config(conf)

    def test_subcent_turns_are_not_erased_by_display_precision(self):
        for _ in range(1000):
            config_manager.update_spend(0.00004, thread_id="micro-turns")

        state = config_manager.get_state()
        self.assertEqual(state["total_requests"], 1000)
        self.assertAlmostEqual(state["current_spend_usd"], 0.04, places=10)
        self.assertAlmostEqual(state["thread_spend_usd"], 0.04, places=10)
        self.assertAlmostEqual(
            state["thread_spend_by_id"]["micro-turns"],
            0.04,
            places=10,
        )

    def test_internal_precision_exceeds_human_four_decimal_display(self):
        self.assertGreater(config_manager.INTERNAL_MONEY_DECIMALS, 4)
        config_manager.update_spend(0.0000412345, thread_id="precision")
        state = config_manager.get_state()

        self.assertEqual(state["current_spend_usd"], 0.0000412345)
        self.assertIn("toFixed(4)", proxy_server.DASHBOARD_HTML)


if __name__ == "__main__":
    unittest.main()
