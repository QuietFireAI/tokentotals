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
        cls.calculations = (ROOT / "CALCULATION_TRANSPARENCY.md").read_text(encoding="utf-8")

    def test_readme_uses_real_network_boundary(self):
        text = self.readme.lower()
        self.assertNotIn("zero-egress", text)
        self.assertNotIn("zero--egress", text)
        self.assertIn("upstream egress exists", text)
        self.assertIn("permitted requests still leave the local machine", text)

    def test_readme_avoids_financial_clearance_copy_and_stale_platform_claims(self):
        text = self.readme.lower()
        for stale in (
            "in budget",
            "dollar headroom",
            "available local headroom",
            "checks daily cap",
            "advisory budget threshold",
            "platform-windows%20%7c%20macos%20%7c%20linux",
            "### 3. 📊 built-in web dashboard",
            "quietfireai@gmail.com",
        ):
            self.assertNotIn(stale, text)
        self.assertIn("local pacing threshold", text)
        self.assertIn("not provider-account clearance", text)
        self.assertIn("desktop-windows", text)
        self.assertIn("does not currently claim a validated macos or linux desktop release", text)
        self.assertIn("support@quietfireai.com", text)

    def test_readme_quickstart_and_math_document_match_runtime(self):
        lower = self.readme.lower()
        self.assertIn("8080` through `8089", self.readme)
        self.assertIn("/api/telemetry/thread?thread_id=<id>", self.readme)
        self.assertIn("calculation_transparency.md", lower)
        self.assertIn("the data is often there. the usable receipt usually isn't. tokentotals makes one.", lower)

        calc = self.calculations.lower()
        for required in (
            "estimated_input_tokens = litellm token_counter",
            "estimated_turn_cost = σ(all defensibly priced billing components)",
            "cached_input_share_pct = (cached_input_tokens / input_tokens) × 100",
            "output_tokens_per_wall_second = output_tokens / (latency_ms / 1000)",
            "rank = ceil(0.95 × sample_count)",
            "combined_local_estimate = posted_local_estimated_spend + inflight_preflight_estimate",
            "metrics already calculable from the current ledger but not yet surfaced",
            "classified_token_share_pct = (classified_tokens / provider_reported_total_tokens) × 100",
            "this must never be relabeled as `99.18% billing accuracy`",
            "cache price differential — not claimed savings",
            "retrospective burn rate",
            "financial runway / safe amount for the next turn",
            "invoice accuracy percentage",
        ):
            self.assertIn(required, calc)

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

    def test_legacy_api_names_and_launch_calendar_keep_current_boundary(self):
        self.assertIn("Legacy budget_* fields remain below for API", self.proxy)
        self.assertIn('"remaining_budget_usd"', self.proxy)
        self.assertIn('"daily_budget_limit_usd"', self.proxy)

        for text in (self.calendar_source.lower(), self.calendar_ics.lower()):
            self.assertNotIn("zero-egress", text)
            self.assertNotIn("hard $5/day ceiling", text)
            self.assertIn("local pacing threshold", text)
            self.assertIn("egress upstream", text)


if __name__ == "__main__":
    unittest.main()
