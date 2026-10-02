import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "Windows provisioning")
class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ushell 测试 ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo with spaces 中文"
        self.nt = self.repo / "channels/flow/nt"
        self.nt.mkdir(parents=True)
        for name in ("provision.bat", "provision.ps1"):
            shutil.copyfile(REPO / "channels/flow/nt" / name, self.nt / name)
        self.packages = self.repo / "dependencies/windows-x64"
        self.packages.mkdir(parents=True)
        self.manifest = json.loads((REPO / "dependencies/windows-x64/manifest.json").read_text())
        (self.packages / "manifest.json").write_text(json.dumps(self.manifest))
        self.working = self.root / "working 中文"

    def provision(self, allow="0"):
        env = {**os.environ, "USHELL_ALLOW_DOWNLOADS": allow}
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(self.nt / "provision.ps1"), "-Working", str(self.working)],
            env=env, capture_output=True, text=True, errors="replace")

    def assert_failed_cleanly(self, result, message):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(message, result.stderr)
        self.assertFalse((self.working / "python/current/3.14.3.version").exists())
        self.assertEqual(list((self.working / "python").glob("stage-*")), [])

    def test_missing_package_is_offline(self):
        self.assert_failed_cleanly(self.provision(), "USHELL_ALLOW_DOWNLOADS=1")

    def test_corrupt_package_never_falls_back(self):
        (self.packages / "python-3.14.3.zip").write_bytes(b"corrupt")
        self.assert_failed_cleanly(self.provision("1"), "SHA-256 mismatch")

    def test_wrong_version(self):
        self.manifest["packages"]["python"]["version"] = "0.0.0"
        (self.packages / "manifest.json").write_text(json.dumps(self.manifest))
        self.assert_failed_cleanly(self.provision(), "version mismatch")

    def test_install_reuse_and_repair(self):
        shutil.copyfile(REPO / "dependencies/windows-x64/python-3.14.3.zip",
                        self.packages / "python-3.14.3.zip")
        result = self.provision()
        self.assertEqual(result.returncode, 0, result.stderr)
        marker = self.working / "python/current/3.14.3.version"
        stamp = marker.stat().st_mtime_ns
        # Cache takes priority even if the archive has subsequently become unavailable.
        (self.packages / "python-3.14.3.zip").rename(self.packages / "held.zip")
        result = self.provision()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Using cached Python", result.stdout)
        self.assertEqual(marker.stat().st_mtime_ns, stamp)
        (self.packages / "held.zip").rename(self.packages / "python-3.14.3.zip")
        dll = self.working / "python/current/DLLs/_ssl.pyd"
        dll.unlink()
        result = self.provision()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(dll.is_file())


if __name__ == "__main__":
    unittest.main()
