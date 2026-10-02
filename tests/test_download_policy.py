import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SYSTEM = Path(__file__).resolve().parents[1] / "channels/flow/core/system"
sys.path[:0] = [str(SYSTEM), str(SYSTEM / "lib")]
import bootstrap
import fsutils
from flow import dependencies, describe


class DownloadPolicyTests(unittest.TestCase):
    def test_only_exact_opt_in_allows_windows(self):
        with patch.object(dependencies, "is_windows", return_value=True):
            for value in ("", "0", "true", "yes"):
                with patch.dict(os.environ, {"USHELL_ALLOW_DOWNLOADS": value}):
                    with self.assertRaises(RuntimeError):
                        dependencies.require_downloads("test")
            with patch.dict(os.environ, {"USHELL_ALLOW_DOWNLOADS": "1"}):
                dependencies.require_downloads("test")

    def test_posix_policy_is_unchanged(self):
        with patch.object(dependencies, "is_windows", return_value=False), patch.dict(os.environ, {"USHELL_ALLOW_DOWNLOADS": "0"}):
            dependencies.require_downloads("POSIX is not gated")
            with patch("urllib.request.urlopen", side_effect=OSError("network reached")) as urlopen:
                with self.assertRaisesRegex(OSError, "network reached"):
                    bootstrap._http_get("https://invalid.example/tool", "./")
                urlopen.assert_called_once()

    def test_http_entrypoints_do_not_call_network_by_default(self):
        debug = fsutils.import_script(SYSTEM.parent / "cmds/debug.py")
        with patch.object(dependencies, "is_windows", return_value=True), patch.dict(os.environ, {"USHELL_ALLOW_DOWNLOADS": "0"}):
            with patch("urllib.request.urlopen") as network:
                with self.assertRaises(RuntimeError):
                    bootstrap._http_get("https://invalid.example/tool", "./")
                network.assert_not_called()
            with patch.object(debug, "urlopen") as network:
                with self.assertRaises(RuntimeError):
                    debug._http_get("https://invalid.example/tool", lambda *args: None)
                network.assert_not_called()

    def test_legacy_pip_is_gated_before_subprocess(self):
        channel = describe.Channel()
        channel.version("1")
        channel._pips = ["not-installed"]
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(dependencies, "is_windows", return_value=True), \
                patch.dict(os.environ, {"USHELL_ALLOW_DOWNLOADS": "0"}), \
                patch.object(bootstrap, "_log", bootstrap._Log(Path(temp) / "log")), \
                patch.object(fsutils, "import_script", return_value=SimpleNamespace(channel=channel)), \
                patch.object(bootstrap.sp, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "Pip dependencies"):
                bootstrap._build_channel("test", Path(temp), None)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
