from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TurnLedgerDocsTests(unittest.TestCase):
    def test_readme_documents_ledger_privacy_missing_semantics_and_mixed_models(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        lower = readme.lower()
        self.assertIn("~/.tokentotals/turns.jsonl", readme)
        self.assertIn("missing is not zero", lower)
        self.assertIn("one thread can contain multiple models", lower)
        self.assertIn("does not persist prompt text, response text, api keys", lower)
        self.assertIn("not represented as immutable or tamper-evident", lower)

    def test_whitepaper_states_runtime_append_only_not_immutable_and_cost_basis(self):
        whitepaper = (ROOT / "TokenTotals_Security_Whitepaper.md").read_text(encoding="utf-8-sig")
        lower = whitepaper.lower()
        self.assertIn("document version:** 2.8-defensive-spec", lower)
        self.assertIn("append-only local turn telemetry ledger", lower)
        self.assertIn("runtime append-only behavior, not immutable storage", lower)
        self.assertIn("residual/unclassified tokens", lower)
        self.assertIn("independent per-model turn, token, and estimated-cost totals", lower)
        self.assertIn("litellm response-cost fallback", lower)
        self.assertIn("known list-equivalent fallback", lower)


if __name__ == "__main__":
    unittest.main()
