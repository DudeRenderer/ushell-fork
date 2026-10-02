"""Build reproducible offline packages from an explicitly selected ushell cache."""

import argparse
import hashlib
import json
import marshal
from pathlib import Path
import subprocess
import zipfile


REPO = Path(__file__).resolve().parents[1]
PACKAGES = {
    "python": ("3.14.3", "python/current"),
    "clink": ("1.0.0a6", "tools/clink-1.0.0a6"),
    "fd": ("10.3.0", "tools/fd-10.3.0"),
    "fzf": ("0.56.3", "tools/fzf-0.56.3"),
    "ripgrep": ("14.1.1", "tools/ripgrep-14.1.1"),
    "vswhere": ("3.1.7", "tools/vswhere-3.1.7"),
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def collect_files(root, name):
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix in (".log", ".version"):
            continue
        if path.name in ("manifest.2.flow", ".ushell-runtime.json") or relative.parts[0] == "Scripts":
            continue
        # Embedded Python's standard library is distributed as .pyc files.
        files[relative.as_posix()] = path.read_bytes()
    if name in ("fzf", "vswhere"):
        files["LICENSE"] = (REPO / "tps" / (name + ".LICENSE")).read_bytes()
    return files


def package(cache, output):
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "platform": "windows-x64",
                "source": "local-installed-cache", "packages": {}}
    for name, (version, relative) in PACKAGES.items():
        root = cache / relative
        if not root.is_dir():
            raise FileNotFoundError(f"Missing installed dependency: {root}")
        if name == "python":
            subprocess.run([str(root / "flow_python.exe"), "-EsSB", "-c",
                            f"import sys,struct; assert sys.version_info[:3] == {tuple(map(int, version.split('.')))!r}; assert struct.calcsize('P') == 8"],
                           check=True)
        else:
            with (root / "manifest.2.flow").open("rb") as stream:
                cached = marshal.load(stream)
            if cached.get("version") != version or cached.get("double") != f"{name}-{version}":
                raise ValueError(f"Unexpected cached version for {name}")
        files = collect_files(root, name)
        if not files:
            raise ValueError(f"Empty dependency: {root}")
        archive_name = f"{name}-{version}.zip"
        archive_path = output / archive_name
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=9) as archive:
            for filename, content in sorted(files.items()):
                info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, content, compresslevel=9)
        # All bundled files are required. This also catches missing DLLs,
        # standard-library modules, and licenses in installed snapshots.
        manifest["packages"][name] = {
            "version": version,
            "archive": archive_name,
            "sha256": sha256(archive_path.read_bytes()),
            "required_files": {key: sha256(value) for key, value in sorted(files.items())},
        }
        print(f"{archive_name}: {len(files)} files, {archive_path.stat().st_size:,} bytes")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=REPO / "dependencies/windows-x64")
    args = parser.parse_args()
    package(args.cache_root.resolve(), args.output.resolve())
