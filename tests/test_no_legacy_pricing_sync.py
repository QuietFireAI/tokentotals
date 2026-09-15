from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NoLegacyPricingSyncTests(unittest.TestCase):
    def test_pricing_sync_module_is_removed(self):
        self.assertFalse(
            (ROOT / "pricing_sync.py").exists(),
            "pricing_sync.py reintroduces an unused third-party pricing download path",
        )

    def test_gui_does_not_start_pricing_sync(self):
        source = (ROOT / "app_gui.py").read_text(encoding="utf-8")
        self.assertNotIn("import pricing_sync", source)
        self.assertNotIn("pricing_sync.start_daily_sync_daemon", source)

    def test_no_runtime_file_references_litellm_remote_catalog(self):
        runtime_files = [
            ROOT / "app_gui.py",
            ROOT / "proxy_server.py",
            ROOT / "config_manager.py",
            ROOT / "openai_pricing.py",
            ROOT / "anthropic_pricing.py",
            ROOT / "google_pricing.py",
        ]
        forbidden = "model_prices_and_context_window.json"
        for path in runtime_files:
            self.assertNotIn(forbidden, path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main()
