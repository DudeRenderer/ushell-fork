import hashlib
import json
import marshal
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

REPO = Path(__file__).resolve().parents[1]
SYSTEM = REPO / "channels/flow/core/system"
sys.path[:0] = [str(SYSTEM), str(SYSTEM / "lib")]
import bootstrap
from flow import dependencies, describe


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packages = self.root / "packages"
        self.packages.mkdir()
        self.working = self.root / "working"
        self.stage = self.working / "$cleaner/pid/0/flow_test"
        self.stage.mkdir(parents=True)
        (self.working / "tools").mkdir()
        previous = Path.cwd()
        os.chdir(self.stage)
        self.addCleanup(os.chdir, previous)
        self.tool = describe.Tool()
        self.tool.version("1.0")
        self.tool.payload("https://invalid.example/tool.zip")
        self.tool.bin("test.exe")
        self.files = {"test.exe": b"test binary", "companion.dll": b"required dll"}
        self.package = self.make_package()
        self.directory = self.working / "tools/test-1.0"
        for p in (patch.object(dependencies, "PACKAGE_ROOT", self.packages),
                  patch.object(dependencies, "is_windows", return_value=True),
                  patch.dict(os.environ, {"USHELL_ALLOW_DOWNLOADS": "0"}),
                  patch.object(bootstrap, "_log", bootstrap._Log(self.root / "setup.log"))):
            p.start()
            self.addCleanup(p.stop)

    def make_package(self):
        archive = self.packages / "test-1.0.zip"
        with zipfile.ZipFile(archive, "w") as out:
            for name, data in self.files.items():
                out.writestr(name, data)
        package = {"version": "1.0", "archive": archive.name,
                   "sha256": dependencies.sha256(archive),
                   "required_files": {name: hashlib.sha256(data).hexdigest()
                                      for name, data in self.files.items()}}
        manifest = {"schema_version": 1, "platform": "windows-x64", "packages": {"test": package}}
        (self.packages / "manifest.json").write_text(json.dumps(manifest))
        return package

    def install(self):
        return bootstrap._install_tool("test", self.tool, None)

    def test_local_install_cache_priority_and_repair(self):
        with patch.object(bootstrap, "_http_get", side_effect=AssertionError("network called")):
            installed = self.install()
            self.assertEqual(installed["acquisition"], "repository")
            marker = self.directory / "manifest.2.flow"
            stamp = marker.stat().st_mtime_ns
            (self.packages / "test-1.0.zip").write_bytes(b"bad archive")
            self.install()  # Valid cache wins, even with an invalid archive.
            self.assertEqual(marker.stat().st_mtime_ns, stamp)
            self.make_package()
            (self.directory / "companion.dll").unlink()
            self.install()
            self.assertEqual((self.directory / "companion.dll").read_bytes(), b"required dll")

    def test_legacy_cache_is_reused(self):
        self.directory.mkdir()
        for name, content in self.files.items():
            (self.directory / name).write_bytes(content)
        manifest = bootstrap._manifest_tool("test", self.tool)
        manifest["bin_paths"] = bootstrap._enabled_bins(manifest)
        (self.directory / "manifest.2.flow").write_bytes(marshal.dumps(manifest))
        with patch.object(dependencies, "extract", side_effect=AssertionError("cache not reused")):
            self.install()

    def test_disabled_bundle_does_not_reuse_same_named_cache(self):
        self.install()
        self.tool.platform("darwin")
        with patch.object(dependencies, "package_for", side_effect=AssertionError("disabled")):
            self.assertEqual(self.install()["bin_paths"], ())

    def test_missing_package_denies_download(self):
        (self.packages / "test-1.0.zip").unlink()
        with patch.object(bootstrap, "_acquire_tool") as acquire:
            with self.assertRaisesRegex(RuntimeError, "USHELL_ALLOW_DOWNLOADS=1"):
                self.install()
            acquire.assert_not_called()
        self.assertFalse(self.directory.exists())

    def test_corruption_does_not_fall_back_even_when_allowed(self):
        (self.packages / "test-1.0.zip").write_bytes(b"bad")
        with patch.dict(os.environ, {"USHELL_ALLOW_DOWNLOADS": "1"}), patch.object(bootstrap, "_acquire_tool") as acquire:
            with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                self.install()
            acquire.assert_not_called()
        self.assertFalse(self.directory.exists())

    def test_wrong_version_and_platform(self):
        path = self.packages / "manifest.json"
        original = path.read_text()
        for bad in (original.replace('"1.0"', '"2.0"'), original.replace("windows-x64", "linux")):
            path.write_text(bad)
            with self.assertRaisesRegex(RuntimeError, "Invalid dependency manifest"):
                self.install()
        self.assertFalse(self.directory.exists())

    def test_incomplete_package_is_not_published(self):
        self.package["required_files"]["absent.dll"] = "0" * 64
        path = self.packages / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["packages"]["test"] = self.package
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(RuntimeError, "Incomplete dependency package"):
            self.install()
        self.assertFalse(self.directory.exists())

    def test_interruption_keeps_previous_installation(self):
        self.install()
        marker = (self.directory / "manifest.2.flow").read_bytes()
        (self.directory / "companion.dll").write_bytes(b"old modified content")
        with patch.object(dependencies, "extract", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.install()
        self.assertEqual((self.directory / "manifest.2.flow").read_bytes(), marker)
        self.assertEqual((self.directory / "companion.dll").read_bytes(), b"old modified content")
        self.assertEqual(list((self.working / "tools").glob("install-*")), [])

    def test_explicit_download_fallback_and_offline_reuse(self):
        (self.packages / "test-1.0.zip").unlink()
        def acquire(name, tool, manifest, target, progress):
            target = Path(target)
            target.mkdir()
            (target / "test.exe").write_bytes(b"downloaded binary")
            (target / "companion.dll").write_bytes(b"downloaded companion")
        with patch.dict(os.environ, {"USHELL_ALLOW_DOWNLOADS": "1"}), patch.object(bootstrap, "_acquire_tool", side_effect=acquire) as download:
            self.assertEqual(self.install()["acquisition"], "download")
            download.assert_called_once()
        with patch.object(bootstrap, "_acquire_tool", side_effect=AssertionError("unexpected download")):
            self.install()
            (self.directory / "companion.dll").unlink()
            with self.assertRaisesRegex(RuntimeError, "downloads are disabled"):
                self.install()

    def test_publish_rolls_back(self):
        old, stage = self.root / "old", self.root / "new"
        old.mkdir()
        stage.mkdir()
        (old / "preserved").touch()
        original = Path.rename
        def rename(path, target):
            if path == stage:
                raise PermissionError("test publication failure")
            return original(path, target)
        with patch.object(Path, "rename", rename):
            with self.assertRaises(PermissionError):
                dependencies.publish(stage, old)
        self.assertTrue((old / "preserved").is_file())

    def test_unsafe_archive_is_rejected(self):
        self.files = {"../escape.exe": b"bad"}
        self.package = self.make_package()
        with self.assertRaises(ValueError):
            dependencies.extract(self.package, self.root / "extract")
        self.assertFalse((self.root / "escape.exe").exists())

    def test_download_pipeline_checks_upstream_hash_and_extracts(self):
        archive = self.packages / "test-1.0.zip"
        data = archive.read_bytes()
        archive.unlink()
        self.tool.sha1(hashlib.sha1(data).hexdigest())
        def http_get(url, destination, callback):
            path = Path(destination) / "tool.zip"
            path.write_bytes(data)
            return str(path)
        with patch.dict(os.environ, {"USHELL_ALLOW_DOWNLOADS": "1"}), \
                patch.object(bootstrap, "_http_get", side_effect=http_get) as download:
            self.install()
            download.assert_called_once()
        self.assertTrue((self.directory / "companion.dll").is_file())
        (self.directory / "companion.dll").unlink()
        self.tool.sha1("0" * 40)
        with patch.dict(os.environ, {"USHELL_ALLOW_DOWNLOADS": "1"}), \
                patch.object(bootstrap, "_http_get", side_effect=http_get):
            with self.assertRaisesRegex(RuntimeError, "Unexpected content bundle"):
                self.install()

    def test_malformed_cache_shapes_are_rebuilt(self):
        for bad in (None, [], {"bundles": None}):
            with self.subTest(cache=bad):
                self.directory.mkdir(exist_ok=True)
                (self.directory / "manifest.2.flow").write_bytes(marshal.dumps(bad))
                self.install()
                self.assertTrue((self.directory / "test.exe").is_file())
        for bad in (None, [], {"dependency_fingerprint": dependencies.fingerprint(), "channels": [None]}):
            (self.stage / "manifest").write_bytes(marshal.dumps(bad))
            self.assertFalse(bootstrap._valid_dependency_state(self.stage))

    def test_non_windows_install_uses_existing_path(self):
        self.install()
        with patch.object(dependencies, "is_windows", return_value=False), \
                patch.object(bootstrap, "_install_tool_windows", side_effect=AssertionError("Windows resolver reached")):
            manifest = self.install()
            self.assertEqual(manifest["double"], "test-1.0")


if __name__ == "__main__":
    unittest.main()
