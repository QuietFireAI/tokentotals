from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATHS = (
    "pricing/openai_registry.json",
    "pricing/anthropic_registry.json",
    "pricing/google_registry.json",
)


class PricingDocsReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = (ROOT / "MODEL_COMPARISON_MATRIX.md").read_text(encoding="utf-8")
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        cls.whitepaper = (ROOT / "TokenTotals_Security_Whitepaper.md").read_text(
            encoding="utf-8-sig"
        )

    def test_mechanics_matrix_does_not_duplicate_stale_price_leaderboard(self):
        self.assertIn("Provider Pricing Mechanics Matrix", self.matrix)
        self.assertIn("source of truth", self.matrix)
        for stale in (
            "Claude 3.7 Sonnet",
            "Claude 3.5 Sonnet",
            "Claude 3.5 Haiku",
            "Gemini 2.0 Flash",
            "Gemini 2.0 Flash-Lite",
            "Multiplier vs. Baseline",
            "Frontier / Advanced",
            "Economy / High-Speed",
        ):
            self.assertNotIn(stale, self.matrix)

    def test_current_pricing_docs_all_reference_the_three_registries(self):
        for path in REGISTRY_PATHS:
            self.assertIn(path, self.matrix)
            self.assertIn(path, self.readme)
            self.assertIn(path, self.whitepaper)

    def test_readme_does_not_present_static_rates_as_live_runtime_truth(self):
        for stale in (
            "## 📊 Standardized Cross-Platform Pricing Comparison",
            "Public Sync: 2026-09-09",
            "| **OpenAI** | OpenAI o1 | Frontier",
            "| **Anthropic** | Claude 3.7 Sonnet | Frontier",
            "| **Google** | Gemini 2.0 Flash | Workhorse",
        ):
            self.assertNotIn(stale, self.readme)

        self.assertIn("Versioned Provider Rules, Not a Second Billing Portal", self.readme)
        self.assertIn("illustrative UI copy, not a live pricing snapshot", self.readme)

    def test_whitepaper_describes_provider_specific_preflight_not_one_rate_matrix(self):
        self.assertNotIn("local real-time pricing matrix", self.whitepaper)
        self.assertNotIn("\\text{BPE}(M, \\text{Encoding}(m))", self.whitepaper)
        self.assertIn("InputPricingEstimate", self.whitepaper)
        self.assertIn("provider-specific pricing rules", self.whitepaper)
        self.assertIn("exact-model input rate from the pinned LiteLLM catalog", self.whitepaper)

    def test_whitepaper_states_real_network_boundary(self):
        self.assertIn("Upstream Egress Still Exists", self.whitepaper)
        self.assertIn("does not mean “no network egress to the provider.”", self.whitepaper)
        self.assertIn("No TokenTotals SaaS Account", self.whitepaper)
        self.assertNotIn("## 2.2 The Zero-Egress Guarantee", self.whitepaper)


if __name__ == "__main__":
    unittest.main()
