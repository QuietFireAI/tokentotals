"""Claude Code plugin: vendored pricing must match the repo, and its own tests must pass."""
import filecmp
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "claude-code-plugin")


class ClaudeCodePluginContractTests(unittest.TestCase):
    def test_vendored_pricing_engine_matches_repo(self):
        self.assertTrue(filecmp.cmp(
            os.path.join(ROOT, "anthropic_pricing.py"),
            os.path.join(PLUGIN, "scripts", "tokentotals_cc", "anthropic_pricing.py"), shallow=False))

    def test_vendored_registry_matches_repo(self):
        self.assertTrue(filecmp.cmp(
            os.path.join(ROOT, "pricing", "anthropic_registry.json"),
            os.path.join(PLUGIN, "scripts", "tokentotals_cc", "pricing", "anthropic_registry.json"), shallow=False))

    def test_marketplace_points_at_plugin(self):
        with open(os.path.join(ROOT, ".claude-plugin", "marketplace.json"), encoding="utf-8") as f:
            market = json.load(f)
        with open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        entry = market["plugins"][0]
        self.assertEqual(entry["name"], manifest["name"])
        self.assertEqual(os.path.normpath(os.path.join(ROOT, entry["source"])), PLUGIN)
        self.assertEqual(entry["version"], manifest["version"])


def load_tests(loader, standard_tests, pattern):
    sys.path.insert(0, os.path.join(PLUGIN, "tests"))
    import test_receipts  # noqa: E402  (plugin's own suite)

    standard_tests.addTests(loader.loadTestsFromModule(test_receipts))
    return standard_tests
