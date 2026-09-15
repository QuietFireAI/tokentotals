import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PublicWordingCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        cls.proxy = (ROOT / "proxy_server.py").read_text(encoding="utf-8")
        cls.calendar_source = (ROOT / "generate_launch_calendar.py").read_text(encoding="utf-8-sig")
        cls.calendar_ics = (ROOT / "TokenTotals_30Day_Launch_Plan.ics").read_text(encoding="utf-8")

    def test_readme_uses_real_network_boundary(self):
        text = self.readme.lower()
        self.assertNotIn("zero-egress", text)
        self.assertNotIn("zero--egress", text)
        self.assertIn("upstream egress exists", text)
        self.assertIn("permitted requests still leave the local machine", text)

    def test_readme_avoids_financial_clearance_copy(self):
        text = self.readme.lower()
        for stale in (
            "in budget",
            "dollar headroom",
            "available local headroom",
            "checks daily cap",
            "advisory budget threshold",
        ):
            self.assertNotIn(stale, text)
        self.assertIn("local pacing threshold", text)
        self.assertIn("not provider-account clearance", text)

    def test_proxy_user_messages_do_not_claim_card_or_account_protection(self):
        text = self.proxy.lower()
        for stale in (
            "protect your card",
            "daily budget cap reached",
            "outgoing calls are hard-locked",
            "would exceed your daily budget",
            "outgoing calls locked",
            "available local headroom is temporarily",
        ):
            self.assertNotIn(stale, text)
        self.assertIn("new requests routed through this tokentotals proxy are paused", text)
        self.assertIn("provider-account billing are outside this local lock", text)

    def test_legacy_api_names_are_explicitly_compatibility_only(self):
        self.assertIn("Legacy budget_* fields remain below for API", self.proxy)
        self.assertIn('"remaining_budget_usd"', self.proxy)
        self.assertIn('"daily_budget_limit_usd"', self.proxy)

    def test_launch_calendar_source_and_generated_file_match_current_boundary(self):
        for text in (self.calendar_source.lower(), self.calendar_ics.lower()):
            self.assertNotIn("zero-egress", text)
            self.assertNotIn("hard $5/day ceiling", text)
            self.assertIn("local pacing threshold", text)
            self.assertIn("egress upstream", text)


if __name__ == "__main__":
    unittest.main()
