import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

REPO = Path(__file__).resolve().parents[1]
SYSTEM = REPO / "channels/flow/core/system"
sys.path[:0] = [str(SYSTEM), str(SYSTEM / "lib")]
import fsutils


class GatherTests(unittest.TestCase):
    def test_distribution_contains_offline_resources(self):
        gather = fsutils.import_script(REPO / "channels/unreal/core/cmds/gather.py")
        with tempfile.TemporaryDirectory(prefix="ushell gather ") as temp:
            root = Path(temp)
            (root / "GenerateProjectFiles.bat").touch()
            source = root / "Engine/Extras/ushell"
            shutil.copytree(REPO, source, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            destination = root / "distribution"
            command = gather.Gather()
            command.args = SimpleNamespace(srcdir=str(source), destdir=destination, overwrite=False)
            with contextlib.redirect_stdout(io.StringIO()):
                command.main()
            packages = destination / "dependencies/windows-x64"
            self.assertEqual(len(list(packages.glob("*.zip"))), 6)
            self.assertTrue((packages / "manifest.json").is_file())
            for original in (REPO / "tps").glob("*.LICENSE"):
                self.assertEqual(original.read_bytes(), (destination / "tps" / original.name).read_bytes())
            self.assertTrue((destination / "channels/flow/nt/provision.ps1").is_file())
            if os.name == "nt":
                working = root / "gathered cache"
                result = subprocess.run(
                    f'cmd.exe /d /s /c ""{destination / "channels/flow/nt/boot.bat"}" --help"',
                    env={**os.environ, "flow_working_dir": str(working), "USHELL_ALLOW_DOWNLOADS": "0"},
                    capture_output=True, text=True, errors="replace", timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(list(working.glob("flow_*/manifest")))


if __name__ == "__main__":
    unittest.main()
