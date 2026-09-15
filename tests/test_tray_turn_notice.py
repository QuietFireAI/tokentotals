import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "app_gui.py"
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


class TrayTurnNoticeTests(unittest.TestCase):
    def test_tray_reads_shared_turn_notice_and_deduplicates_event_ids(self):
        self.assertIn("import turn_notice", SOURCE)
        self.assertIn("LAST_NOTIFIED_TURN_NOTICE_ID = None", SOURCE)
        self.assertIn("notice = turn_notice.latest_notice()", SOURCE)
        self.assertIn("turn_notice.normalize_threshold", SOURCE)
        self.assertIn('GLOBAL_ICON.notify(notice["message"], "TokenTotals Turn Notice")', SOURCE)
        self.assertIn("LAST_NOTIFIED_TURN_NOTICE_ID = notice_id", SOURCE)

    def test_disabled_notice_consumes_stale_event_before_reenable(self):
        self.assertIn("if notice_id and not notice_enabled:", SOURCE)
        self.assertIn("LAST_NOTIFIED_TURN_NOTICE_ID = notice_id", SOURCE)
        self.assertIn("notice_id != LAST_NOTIFIED_TURN_NOTICE_ID", SOURCE)

    def test_tray_removes_credit_card_and_absolute_freeze_overclaims(self):
        lowered = SOURCE.lower()
        self.assertNotIn("hard-frozen", lowered)
        self.assertNotIn("credit card will not be billed", lowered)
        self.assertNotIn("daily budget cap reached", lowered)
        self.assertNotIn("in budget:", lowered)
        self.assertIn("new requests routed through this tokentotals proxy are paused", lowered)
        self.assertIn("requests outside tokentotals", lowered)
        self.assertIn("already in-flight provider work", lowered)
        self.assertIn("provider-account billing remain outside this local lock", lowered)

    def test_monitor_loop_contains_notice_logic_without_second_persistent_store(self):
        monitor = next(
            node for node in TREE.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "monitor_state_loop"
        )
        names = {
            node.id for node in ast.walk(monitor)
            if isinstance(node, ast.Name)
        }
        attrs = {
            node.attr for node in ast.walk(monitor)
            if isinstance(node, ast.Attribute)
        }
        self.assertIn("turn_notice", names)
        self.assertIn("latest_notice", attrs)
        self.assertNotIn("open", names)
        self.assertNotIn("requests", names)


if __name__ == "__main__":
    unittest.main()
