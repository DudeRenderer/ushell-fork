import hashlib
import json
import marshal
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from test_launchers import git_bash

REPO = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_all_archive_and_file_hashes_and_licenses(self):
        root = REPO / "dependencies/windows-x64"
        manifest = json.loads((root / "manifest.json").read_text())
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["platform"], "windows-x64")
        self.assertEqual(len(manifest["packages"]), 6)
        for name, package in manifest["packages"].items():
            with self.subTest(package=name):
                archive = root / package["archive"]
                self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), package["sha256"])
                with zipfile.ZipFile(archive) as source:
                    self.assertEqual(set(source.namelist()), set(package["required_files"]))
                    self.assertTrue(any("license" in item.lower() for item in source.namelist()))
                    for item, digest in package["required_files"].items():
                        self.assertEqual(hashlib.sha256(source.read(item)).hexdigest(), digest, item)
                    self.assertNotIn("manifest.2.flow", source.namelist())
                    if name == "python":
                        self.assertIn("Lib/encodings/__init__.pyc", source.namelist())
                        self.assertIn("Lib/site-packages/pip/__init__.py", source.namelist())
                        self.assertIn("DLLs/_ssl.pyd", source.namelist())
                        self.assertFalse(any(item.startswith("Scripts/") for item in source.namelist()))


@unittest.skipUnless(os.name == "nt", "Windows end-to-end runtime")
class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ushell e2e 中文 ")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.repo = cls.root / "repo 中文 space"
        shutil.copytree(REPO, cls.repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))

    def run_command(self, command, working):
        return subprocess.run(
            command, env={**os.environ, "flow_working_dir": str(working), "USHELL_ALLOW_DOWNLOADS": "0"},
            cwd=self.repo, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def check_result(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def check_runtime(self, working):
        state, = working.glob("flow_*/manifest")
        state = state.parent
        python = working / "python/current/flow_python.exe"
        system = self.repo / "channels/flow/core/system"
        native_check = (
            "import sys,ssl,sqlite3,ctypes,marshal,zipfile,pip; "
            f"sys.path[:0] = [{str(system)!r}, {str(self.repo / 'channels/unreal/core/pylib')!r}]; "
            "import flow.native,vs.dte; print('native extensions loaded')"
        )
        self.check_result(self.run_command([str(python), "-Xutf8", "-EsB", "-c", native_check], working))
        self.check_result(self.run_command([str(state / "shims/.help.exe")], working))
        complete = self.run_command([str(state / "shims/$complete.exe"), ".build"], working)
        self.check_result(complete)
        self.assertIn("editor", complete.stdout)
        for binary, version, argument in (
            ("fd.exe", "10.3.0", "--version"), ("fzf.exe", "0.56.3", "--version"),
            ("rg.exe", "14.1.1", "--version"), ("clink_x64.exe", "1.0.0", "--version"),
            ("vswhere.exe", "3.1.7", "-?")):
            result = self.run_command([str(state / "shims" / binary), argument], working)
            if binary == "clink_x64.exe":
                # This pinned Clink build returns 1 for its successful version query.
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            else:
                self.check_result(result)
            self.assertIn(version, result.stdout)
        manifest = state / "manifest"
        stamp = manifest.stat().st_mtime_ns
        boot = [str(python), "-Xutf8", "-Esu", str(system / "boot.py"), "--help"]
        result = self.run_command(boot, working)
        self.assertEqual(result.returncode, 127, result.stdout + result.stderr)
        self.assertEqual(manifest.stat().st_mtime_ns, stamp)
        (working / "tools/fzf-0.56.3/fzf.exe").unlink()
        result = self.run_command(boot, working)
        self.assertEqual(result.returncode, 127, result.stdout + result.stderr)
        self.assertTrue((working / "tools/fzf-0.56.3/fzf.exe").is_file())
        # Corrupt state is rebuilt rather than loaded as a successful warm boot.
        manifest.write_bytes(b"broken marshal")
        result = self.run_command(boot, working)
        self.assertEqual(result.returncode, 127, result.stdout + result.stderr)
        self.assertIn("cmd_tree", marshal.loads(manifest.read_bytes()))

    def test_full_cmd_session(self):
        working = self.root / "cmd working 中文"
        result = self.run_command(
            f'cmd.exe /d /s /c "call "{self.repo / "ushell.bat"}" --cleanprompt && .help"',
            working)
        self.check_result(result)
        self.check_runtime(working)

    def test_full_powershell_session(self):
        working = self.root / "powershell working 中文"
        module = str(self.repo / "powerushell/powerushell.psm1").replace("'", "''")
        result = self.run_command(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
             f"$ErrorActionPreference='Stop'; Import-Module '{module}' -ArgumentList '--cleanprompt'; .help; exit $LASTEXITCODE"],
            working)
        self.check_result(result)
        self.check_runtime(working)

    def test_full_git_bash_session(self):
        bash = git_bash()
        if not bash:
            self.skipTest("Git Bash unavailable")
        working = self.root / "bash working 中文"
        result = self.run_command(
            [str(bash), "--noprofile", "--norc", "-c",
             f"source '{self.repo.as_posix()}/ushell.sh' --cleanprompt && .help"], working)
        self.check_result(result)
        self.check_runtime(working)


if __name__ == "__main__":
    unittest.main()
