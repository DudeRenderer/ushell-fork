import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


def git_bash():
    if not shutil.which("git"):
        return None
    result = subprocess.run(["git", "--exec-path"], capture_output=True, text=True)
    candidate = Path(result.stdout.strip()).parents[2] / "bin/bash.exe"
    return candidate if candidate.is_file() else None


@unittest.skipUnless(os.name == "nt", "Windows launcher integration")
class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ushell launchers 中文 ")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.repo = cls.root / "repo space 中文"
        shutil.copytree(REPO, cls.repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        cls.bash = git_bash()

    def invoke(self, shell, working):
        env = {**os.environ, "flow_working_dir": str(working), "USHELL_ALLOW_DOWNLOADS": "0"}
        nt = self.repo / "channels/flow/nt"
        if shell == "cmd":
            command = f'cmd.exe /d /s /c ""{nt / "boot.bat"}" --help"'
        elif shell == "powershell":
            command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                       "-File", str(nt / "boot.ps1"), "--help"]
        else:
            if not self.bash:
                self.skipTest("Git Bash is unavailable")
            command = [str(self.bash), "--noprofile", "--norc", "-c",
                       f"source '{self.repo.as_posix()}/ushell.sh' --help"]
        return subprocess.run(command, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=60)

    def check_shell(self, shell):
        working = self.root / (shell + " working 中文")
        result = self.invoke(shell, working)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Launches a new session", result.stdout)
        self.assertTrue(list(working.glob("flow_*/manifest")))
        # A bad package must fail at the caller without publishing a command registry.
        archive = self.repo / "dependencies/windows-x64/fzf-0.56.3.zip"
        backup = archive.with_suffix(".held")
        archive.rename(backup)
        try:
            result = self.invoke(shell, self.root / (shell + " missing 中文"))
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("USHELL_ALLOW_DOWNLOADS=1", result.stdout + result.stderr)
            self.assertFalse(list((self.root / (shell + " missing 中文")).glob("flow_*/manifest")))
        finally:
            backup.rename(archive)

    def test_cmd(self):
        self.check_shell("cmd")

    def test_powershell(self):
        self.check_shell("powershell")

    def test_windows_bash(self):
        self.check_shell("bash")


if __name__ == "__main__":
    unittest.main()
