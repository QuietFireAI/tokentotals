import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extension"


class BrowserExtensionContractTests(unittest.TestCase):
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
        worker = (EXT / "service_worker.js").read_text(encoding="utf-8")
        self.assertIn("/api/external-turns/settle/render", worker)
        self.assertNotIn("/v1/chat/completions", worker)
        self.assertNotIn("api.openai.com", worker)
        self.assertNotIn("generativelanguage.googleapis.com", worker)
        self.assertNotIn("api.anthropic.com", worker)

    def test_receipt_is_inserted_after_provider_answer(self):
        content = (EXT / "content.js").read_text(encoding="utf-8")
        self.assertIn('insertAdjacentElement("afterend", host)', content)
        self.assertIn("TT_SETTLE_EXTERNAL_TURN", content)
        self.assertIn("Settling Turn Receipt", content)

    def test_content_script_does_not_persist_conversation_text(self):
        content = (EXT / "content.js").read_text(encoding="utf-8")
        self.assertNotIn("chrome.storage.local.set", content)
        self.assertNotIn("chrome.storage.sync.set", content)

    def test_model_answer_is_not_modified(self):
        content = (EXT / "content.js").read_text(encoding="utf-8")
        self.assertNotIn("answer.innerHTML =", content)
        self.assertNotIn("answer.textContent =", content)
        self.assertIn("answer.insertAdjacentElement", content)


if __name__ == "__main__":
    unittest.main()
