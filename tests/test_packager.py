import importlib.util
from pathlib import Path
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("packager", REPO / "scripts/package_windows_dependencies.py")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class PackagerTests(unittest.TestCase):
    def test_exclusions_preserve_embedded_bytecode(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            names = ("Lib/encodings/__init__.pyc", "Lib/site-packages/pip/__init__.py",
                     "Lib/__pycache__/generated.pyc", "Scripts/pip.exe",
                     "provision.log", "3.14.3.version", "manifest.2.flow",
                     ".ushell-runtime.json", "LICENSE", "flow_python.exe")
            for name in names:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"test")
            self.assertEqual(set(packager.collect_files(root, "python")),
                             {"Lib/encodings/__init__.pyc", "Lib/site-packages/pip/__init__.py",
                              "LICENSE", "flow_python.exe"})


if __name__ == "__main__":
    unittest.main()
