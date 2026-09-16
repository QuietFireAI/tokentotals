import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extension"


class BrowserExtensionContractTests(unittest.TestCase):
    def setUp(self):
        self.content = (EXT / "content.js").read_text(encoding="utf-8")
        self.worker = (EXT / "service_worker.js").read_text(encoding="utf-8")

    def test_manifest_targets_existing_provider_surfaces_and_local_engine(self):
        manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertIn("http://127.0.0.1/*", manifest["host_permissions"])
        matches = manifest["content_scripts"][0]["matches"]
        self.assertIn("https://gemini.google.com/*", matches)
        self.assertIn("https://chatgpt.com/*", matches)
        self.assertIn("https://claude.ai/*", matches)
        self.assertNotIn("<all_urls>", manifest["host_permissions"])

    def test_extension_settles_receipt_without_second_model_call(self):
        self.assertIn("/api/external-turns/settle/render", self.worker)
        self.assertNotIn("/v1/chat/completions", self.worker)
        self.assertNotIn("api.openai.com", self.worker)
        self.assertNotIn("generativelanguage.googleapis.com", self.worker)
        self.assertNotIn("api.anthropic.com", self.worker)

    def test_receipt_is_inserted_after_provider_answer(self):
        self.assertIn('insertAdjacentElement("afterend", host)', self.content)
        self.assertIn("TT_SETTLE_EXTERNAL_TURN", self.content)
        self.assertIn("Settling Turn Receipt", self.content)

    def test_content_script_does_not_persist_conversation_text(self):
        self.assertNotIn("chrome.storage.local.set", self.content)
        self.assertNotIn("chrome.storage.sync.set", self.content)

    def test_model_answer_is_not_modified(self):
        self.assertNotIn("answer.innerHTML =", self.content)
        self.assertNotIn("answer.textContent =", self.content)
        self.assertIn("answer.insertAdjacentElement", self.content)

    def test_existing_history_is_baselined_instead_of_backfilled(self):
        self.assertIn("function baselineCurrentPage()", self.content)
        self.assertIn("seenElements.add(answer)", self.content)
        self.assertIn("baselineCurrentPage();", self.content)

    def test_fallback_turn_identity_hashes_current_turn_material(self):
        self.assertIn('crypto.subtle.digest("SHA-256"', self.content)
        self.assertIn("dom-sha256", self.content)
        self.assertNotIn("text.slice(0, 180)", self.content)

    def test_standard_and_expanded_use_same_external_turn(self):
        self.assertIn('requestReceipt(host, payload, "standard")', self.content)
        self.assertIn('host.dataset.turnreceiptMode === "expanded" ? "standard" : "expanded"', self.content)
        self.assertIn("const requestPayload = {...payload, receipt_mode: mode}", self.content)

    def test_engine_failure_is_receipt_local_not_provider_page_blocking(self):
        self.assertIn("Turn Receipt unavailable", self.content)
        self.assertNotIn("document.body.innerHTML =", self.content)
        self.assertNotIn("location.replace(", self.content)


if __name__ == "__main__":
    unittest.main()
