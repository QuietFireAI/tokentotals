import importlib
import unittest

from fastapi.testclient import TestClient


class DashboardTruthfulnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proxy = importlib.import_module("proxy_server")
        cls.html = cls.proxy.DASHBOARD_HTML

    def test_dashboard_omits_uncollected_live_metrics(self):
        for unsupported in (
            "Token Velocity & Session Total",
            "~199k",
            "14.5M tokens processed",
            "Prompt Cache Savings",
            "~85%",
            "Prompt caching discount active",
        ):
            self.assertNotIn(unsupported, self.html)

    def test_dashboard_states_actual_local_and_upstream_boundary(self):
        self.assertIn("Posted Local Estimate / Pacing Threshold", self.html)
        self.assertIn(
            "Local loopback control plane; permitted requests still egress to the selected upstream provider",
            self.html,
        )
        self.assertNotIn("100% Local Zero-Egress Loopback", self.html)
        self.assertIn("LOCAL PACING THRESHOLD REACHED", self.html)

    def test_dashboard_avoids_financial_clearance_wording(self):
        self.assertNotIn("Available headroom", self.html)
        self.assertNotIn("IN BUDGET", self.html)
        self.assertNotIn("you have $", self.html.lower())
        self.assertIn("BELOW LOCAL THRESHOLD", self.html)
        self.assertIn("Combined local estimate", self.html)
        self.assertIn("not provider-account clearance", self.html)

    def test_dashboard_live_fields_are_backed_by_status_endpoint(self):
        original_get_state = self.proxy.config_manager.get_state
        original_get_config = self.proxy.config_manager.get_config
        original_pacing = self.proxy.config_manager.get_pacing_snapshot
        original_latency = self.proxy.LAST_LATENCY_MS
        self.proxy.config_manager.get_state = lambda: {
            "current_spend_usd": 1.25,
            "thread_spend_usd": 0.5,
            "active_thread_id": "thread-live",
            "is_locked": False,
        }
        self.proxy.config_manager.get_config = lambda: {
            "daily_budget_limit_usd": 10.0,
            "warning_threshold_pct": 75,
            "port": 8088,
        }
        self.proxy.config_manager.get_pacing_snapshot = lambda: {
            "current_spend_usd": 1.25,
            "inflight_reserved_usd": 0.25,
            "committed_spend_usd": 1.50,
            "available_budget_usd": 8.50,
            "daily_budget_limit_usd": 10.0,
            "is_locked": False,
            "reservation_count": 1,
        }
        self.proxy.LAST_LATENCY_MS = 123
        try:
            client = TestClient(self.proxy.app)
            payload = client.get("/api/status").json()
            dashboard = client.get("/dashboard")
        finally:
            self.proxy.config_manager.get_state = original_get_state
            self.proxy.config_manager.get_config = original_get_config
            self.proxy.config_manager.get_pacing_snapshot = original_pacing
            self.proxy.LAST_LATENCY_MS = original_latency

        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(payload["posted_estimated_spend_usd"], 1.25)
        self.assertEqual(payload["inflight_preflight_estimate_usd"], 0.25)
        self.assertEqual(payload["combined_local_estimate_usd"], 1.50)
        self.assertEqual(payload["pacing_threshold_usd"], 10.0)
        self.assertEqual(payload["posted_threshold_pct"], 12.5)
        self.assertEqual(payload["combined_threshold_pct"], 15.0)
        self.assertEqual(payload["active_thread_id"], "thread-live")
        self.assertEqual(payload["thread_spend_usd"], 0.5)
        self.assertEqual(payload["port"], 8088)
        self.assertEqual(payload["last_latency_ms"], 123)

        # Legacy names intentionally remain for API compatibility during migration.
        self.assertEqual(payload["current_spend_usd"], 1.25)
        self.assertEqual(payload["remaining_budget_usd"], 8.50)

        for field_id in (
            "spendVal",
            "limitVal",
            "remainingVal",
            "pctVal",
            "threadVal",
            "threadIdVal",
            "latencyVal",
            "noticeStatus",
            "noticeMessage",
            "telemetryModel",
            "telemetryCost",
            "modelsBreakdown",
        ):
            self.assertIn(field_id, self.html)

    def test_dashboard_consumes_presentation_apis_not_raw_ledger(self):
        self.assertIn("/api/turn-notice", self.html)
        self.assertIn("/api/telemetry/thread", self.html)
        self.assertIn("/api/turn-notice/config", self.html)
        self.assertNotIn("turns.jsonl", self.html)
        self.assertIn("Unavailable", self.html)
        self.assertIn("Models used in this thread", self.html)


if __name__ == "__main__":
    unittest.main()
