import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extension"


class ExtensionContractTests(unittest.TestCase):
    def test_manifest_is_minimal_mv3(self):
        manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertNotIn("<all_urls>", manifest.get("host_permissions", []))
        self.assertIn("http://127.0.0.1/*", manifest["host_permissions"])
        self.assertIn("https://gemini.google.com/*", manifest["optional_host_permissions"])
        self.assertIn("https://claude.ai/*", manifest["optional_host_permissions"])
        self.assertIn("https://chatgpt.com/*", manifest["optional_host_permissions"])
        self.assertNotIn("webRequest", manifest.get("permissions", []))
        self.assertNotIn("cookies", manifest.get("permissions", []))

    def test_probe_only_whitelists_telemetry_keys(self):
        probe = (EXT / "telemetry_probe.js").read_text(encoding="utf-8")
        self.assertIn("usageMetadata", probe)
        self.assertIn("totalTokenCount", probe)
        self.assertNotIn("promptText", probe)
        self.assertNotIn("answerText", probe)
        self.assertNotIn("Authorization", probe)
        self.assertNotIn("Cookie", probe)

    def test_content_script_refuses_timing_only_correlation(self):
        content = (EXT / "content.js").read_text(encoding="utf-8")
        self.assertIn("Time proximity alone is not enough", content)
        self.assertIn("if (!nodeId) return", content)
        self.assertIn("if (!event) return", content)
        self.assertIn("TT_INGEST_EXTERNAL_TURN", content)
        self.assertIn("TT_RENDER_RECEIPT", content)

    def test_service_worker_uses_local_engine(self):
        worker = (EXT / "service_worker.js").read_text(encoding="utf-8")
        self.assertIn("http://127.0.0.1:8080", worker)
        self.assertIn("/api/external-turn", worker)
        self.assertIn("/api/turn-receipt/", worker)


if __name__ == "__main__":
    unittest.main()
