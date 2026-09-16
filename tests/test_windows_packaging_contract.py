import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class WindowsPackagingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui = (ROOT / "app_gui.py").read_text(encoding="utf-8")
        cls.build = (ROOT / "build.ps1").read_text(encoding="utf-8")

    def test_packaged_smoke_path_forces_process_exit(self):
        self.assertIn('if "--smoke-test" in sys.argv:', self.gui)
        self.assertIn("packaging_smoke_test()", self.gui)
        self.assertIn("os._exit(1)", self.gui)
        self.assertIn("os._exit(0)", self.gui)

    def test_build_script_bounds_smoke_test_wait(self):
        self.assertIn('Start-Process -FilePath $exe -ArgumentList "--smoke-test" -PassThru', self.build)
        self.assertIn("WaitForExit(90000)", self.build)
        self.assertIn("Stop-Process -Id $smoke.Id -Force", self.build)
        self.assertIn("Packaged smoke test timed out after 90 seconds", self.build)


if __name__ == "__main__":
    unittest.main()
