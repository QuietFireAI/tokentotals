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
        self.assertIn("Local Estimated Spend / Pacing Threshold", self.html)
        self.assertIn(
            "Local loopback control plane; permitted requests still egress to the selected upstream provider",
            self.html,
        )
        self.assertNotIn("100% Local Zero-Egress Loopback", self.html)
        self.assertIn("LOCAL THRESHOLD REACHED", self.html)

    def test_dashboard_live_fields_are_backed_by_status_endpoint(self):
        original_get_state = self.proxy.config_manager.get_state
        original_get_config = self.proxy.config_manager.get_config
        original_latency = self.proxy.LAST_LATENCY_MS
        self.proxy.config_manager.get_state = lambda: {
            "current_spend_usd": 1.25,
            "thread_spend_usd": 0.5,
            "is_locked": False,
        }
        self.proxy.config_manager.get_config = lambda: {
            "daily_budget_limit_usd": 10.0,
            "warning_threshold_pct": 75,
            "port": 8088,
        }
        self.proxy.LAST_LATENCY_MS = 123
        try:
            client = TestClient(self.proxy.app)
            payload = client.get("/api/status").json()
            dashboard = client.get("/dashboard")
        finally:
            self.proxy.config_manager.get_state = original_get_state
            self.proxy.config_manager.get_config = original_get_config
            self.proxy.LAST_LATENCY_MS = original_latency

        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(payload["current_spend_usd"], 1.25)
        self.assertEqual(payload["thread_spend_usd"], 0.5)
        self.assertEqual(payload["daily_budget_limit_usd"], 10.0)
        self.assertEqual(payload["remaining_budget_usd"], 8.75)
        self.assertEqual(payload["port"], 8088)
        self.assertEqual(payload["last_latency_ms"], 123)

        for field_id in (
            "spendVal",
            "limitVal",
            "remainingVal",
            "pctVal",
            "threadVal",
            "latencyVal",
        ):
            self.assertIn(field_id, self.html)


if __name__ == "__main__":
    unittest.main()
