import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class WindowsPackagingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui = (ROOT / "app_gui.py").read_text(encoding="utf-8")
        cls.smoke = (ROOT / "packaging_smoke.py").read_text(encoding="utf-8")
        cls.build = (ROOT / "build.ps1").read_text(encoding="utf-8")
        cls.workflow = (ROOT / ".github" / "workflows" / "windows-package.yml").read_text(encoding="utf-8")

    def test_packaged_smoke_branches_before_desktop_imports_and_forces_exit(self):
        self.assertIn('if "--smoke-test" in sys.argv:', self.gui)
        self.assertIn("from packaging_smoke import run_packaging_smoke_test", self.gui)
        self.assertIn("run_packaging_smoke_test()", self.gui)
        self.assertIn("os._exit(1)", self.gui)
        self.assertIn("os._exit(0)", self.gui)

        smoke_branch = self.gui.index('if "--smoke-test" in sys.argv:')
        for desktop_import in ("import winsound", "import pystray", "import tkinter as tk", "from proxy_server import app"):
            self.assertLess(smoke_branch, self.gui.index(desktop_import))

    def test_packaging_smoke_traces_assets_registries_and_proxy_routes(self):
        for required in (
            '_trace("entry")',
            '_trace("pil_import_start")',
            'icon_start:{name}',
            '_trace("pricing_import_start")',
            '_trace("openai_registry_ok")',
            '_trace("anthropic_registry_ok")',
            '_trace("google_registry_ok")',
            '_trace("proxy_import_start")',
            '_trace("proxy_routes_ok")',
            '_trace("complete")',
            'error:{type(exc).__name__}:{exc}',
        ):
            self.assertIn(required, self.smoke)

    def test_build_script_bounds_smoke_wait_and_prints_phase_trace(self):
        self.assertIn('Start-Process -FilePath $exe -ArgumentList "--smoke-test" -WorkingDirectory $PSScriptRoot -PassThru', self.build)
        self.assertIn("WaitForExit(90000)", self.build)
        self.assertIn("Stop-Process -Id $smoke.Id -Force", self.build)
        self.assertIn("Packaged smoke test timed out after 90 seconds", self.build)
        self.assertIn('packaging-smoke-trace.txt', self.build)
        self.assertIn("Write-SmokeTrace", self.build)

    def test_build_bundles_litellm_data_and_tiktoken_encoding_plugin(self):
        self.assertIn('--collect-data "litellm"', self.build)
        self.assertIn('--hidden-import "tiktoken_ext"', self.build)
        self.assertIn('--hidden-import "tiktoken_ext.openai_public"', self.build)
        self.assertIn('"packaging_smoke.py"', self.workflow)
        self.assertIn('model_prices_and_context_window_backup.json', self.workflow)
        self.assertIn('LiteLLM runtime pricing/context backup data is missing from package', self.workflow)
        for registry_name in ("openai_registry.json", "anthropic_registry.json", "google_registry.json"):
            self.assertIn(registry_name, self.workflow)
        self.assertNotIn('Filter "*_registry.json"', self.workflow)
        self.assertNotIn('Expected exactly three bundled pricing registries', self.workflow)

    def test_workflow_separates_candidate_zip_identity_from_actions_artifact_identity(self):
        self.assertIn('Get-FileHash $candidate.FullName -Algorithm SHA256', self.workflow)
        self.assertIn('CANDIDATE_ZIP_SHA256=', self.workflow)
        self.assertIn('CANDIDATE_ZIP_SIZE_BYTES=', self.workflow)
        self.assertIn('id: upload_candidate', self.workflow)
        self.assertIn('steps.upload_candidate.outputs.artifact-id', self.workflow)
        self.assertIn('steps.upload_candidate.outputs.artifact-digest', self.workflow)
        self.assertIn('TokenTotals-Windows-candidate-${{ steps.candidate_identity.outputs.sha256 }}', self.workflow)


if __name__ == "__main__":
    unittest.main()
