import unittest

import turn_notice


class TurnNoticeTests(unittest.TestCase):
    def setUp(self):
        turn_notice.reset_runtime_notices()
        self.addCleanup(turn_notice.reset_runtime_notices)

    def test_disabled_or_invalid_threshold_produces_no_notice(self):
        for threshold in (None, 0, -1, "bad"):
            notice = turn_notice.evaluate_notice(
                stage="completed",
                estimated_cost_usd=2.0,
                threshold_usd=threshold,
                thread_id="thread-a",
                turn_id="turn-1",
            )
            self.assertIsNone(notice)

    def test_below_threshold_produces_no_notice(self):
        notice = turn_notice.evaluate_notice(
            stage="completed",
            estimated_cost_usd=0.99,
            threshold_usd=1.0,
            thread_id="thread-a",
            turn_id="turn-1",
        )
        self.assertIsNone(notice)

    def test_exact_threshold_fires(self):
        notice = turn_notice.evaluate_notice(
            stage="completed",
            estimated_cost_usd=1.0,
            threshold_usd=1.0,
            thread_id="thread-a",
            turn_id="turn-1",
            model_id="gpt-5.6-sol",
            cost_basis="provider_registry_complete",
            estimate_complete=True,
        )
        self.assertEqual(notice["event"], "turn_notice")
        self.assertEqual(notice["event_id"], "turn-1:completed")
        self.assertEqual(notice["estimated_cost_usd"], 1.0)
        self.assertEqual(notice["reminder_threshold_usd"], 1.0)
        self.assertTrue(notice["estimate_complete"])
        self.assertNotIn("remaining", notice["message"].lower())
        self.assertNotIn("budget", notice["message"].lower())

    def test_preflight_and_completed_messages_keep_scope_distinct(self):
        preflight = turn_notice.evaluate_notice(
            stage="preflight",
            estimated_cost_usd=1.2,
            threshold_usd=1.0,
            thread_id="thread-a",
            turn_id="turn-1",
            cost_basis="openai_registry",
        )
        completed = turn_notice.evaluate_notice(
            stage="completed",
            estimated_cost_usd=1.4,
            threshold_usd=1.0,
            thread_id="thread-a",
            turn_id="turn-1",
            cost_basis="provider_registry_complete",
            estimate_complete=True,
        )
        self.assertIn("input-side", preflight["message"])
        self.assertIn("Final turn cost can differ", preflight["message"])
        self.assertIn("Provider account records remain authoritative", completed["message"])
        self.assertNotEqual(preflight["event_id"], completed["event_id"])

    def test_latest_notice_is_available_globally_and_by_thread(self):
        first = turn_notice.evaluate_and_publish(
            stage="completed",
            estimated_cost_usd=1.1,
            threshold_usd=1.0,
            thread_id="thread-a",
            turn_id="turn-a",
        )
        second = turn_notice.evaluate_and_publish(
            stage="completed",
            estimated_cost_usd=2.2,
            threshold_usd=1.0,
            thread_id="thread-b",
            turn_id="turn-b",
        )
        self.assertEqual(turn_notice.latest_notice()["event_id"], second["event_id"])
        self.assertEqual(turn_notice.latest_notice("thread-a")["event_id"], first["event_id"])
        self.assertEqual(turn_notice.latest_notice("thread-b")["event_id"], second["event_id"])

    def test_duplicate_event_id_is_not_published_twice(self):
        event = turn_notice.evaluate_notice(
            stage="completed",
            estimated_cost_usd=1.5,
            threshold_usd=1.0,
            thread_id="thread-a",
            turn_id="turn-1",
        )
        self.assertTrue(turn_notice.publish_notice(event))
        self.assertFalse(turn_notice.publish_notice(event))
        self.assertEqual(turn_notice.latest_notice("thread-a")["event_id"], "turn-1:completed")


if __name__ == "__main__":
    unittest.main()
