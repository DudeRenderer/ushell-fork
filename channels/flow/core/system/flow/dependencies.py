# Copyright Epic Games, Inc. All Rights Reserved.
"""Windows dependency snapshots. No network access occurs in this module."""

import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import stat
import sys
import uuid
import zipfile

PACKAGE_ROOT = Path(__file__).resolve().parents[5] / "dependencies/windows-x64"


def is_windows():
    return sys.platform == "win32"


def require_downloads(description):
    if is_windows() and os.getenv("USHELL_ALLOW_DOWNLOADS") != "1":
        raise RuntimeError(
            f"{description}: dependency downloads are disabled on Windows. "
            "Restore the matching repository package or set USHELL_ALLOW_DOWNLOADS=1.")


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_path(root, relative):
    root = Path(root).resolve()
    win = PureWindowsPath(relative)
    if not relative or win.is_absolute() or win.drive or ":" in relative:
        raise ValueError(f"Unsafe dependency path: {relative!r}")
    path = (root / relative.replace("\\", "/")).resolve()
    if path == root or root not in path.parents:
        raise ValueError(f"Unsafe dependency path: {relative!r}")
    return path


def fingerprint():
    path = PACKAGE_ROOT / "manifest.json"
    return sha256(path) if path.is_file() else ""


def package_for(name, version):
    path = PACKAGE_ROOT / "manifest.json"
    if not path.is_file():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest["schema_version"] != 1 or manifest["platform"] != "windows-x64":
            raise ValueError("expected schema 1 and platform windows-x64")
        # The bundled interpreter and executables are x64, including under emulation.
        if sys.maxsize <= 2**32:
            raise ValueError("Windows dependency packages require a 64-bit interpreter")
        package = manifest["packages"].get(name)
        if package is None:
            return None
        if package["version"] != version:
            raise ValueError(f"{name}: expected version {version}, found {package['version']}")
        if not package["required_files"]:
            raise ValueError(f"{name}: required file inventory is empty")
        safe_path(PACKAGE_ROOT, package["archive"])
        for relative in package["required_files"]:
            safe_path(PACKAGE_ROOT, relative)
        return package
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"Invalid dependency manifest '{path}': {error}") from error


def valid_files(root, files):
    if not files:
        return False
    try:
        return all(safe_path(root, name).is_file() and sha256(safe_path(root, name)) == digest
                   for name, digest in files.items())
    except (OSError, ValueError):
        return False


def inventory(root):
    return {path.relative_to(root).as_posix(): sha256(path)
            for path in sorted(Path(root).rglob("*")) if path.is_file()
            and path.name != "manifest.2.flow"}


def extract(package, destination):
    archive = safe_path(PACKAGE_ROOT, package["archive"])
    if sha256(archive) != package["sha256"]:
        raise RuntimeError(f"SHA-256 mismatch for dependency package '{archive}'")
    destination = Path(destination)
    destination.mkdir(parents=True)
    with zipfile.ZipFile(archive) as source:
        seen = set()
        for entry in source.infolist():
            path = safe_path(destination, entry.filename)
            key = str(path).casefold()
            if key in seen or stat.S_ISLNK(entry.external_attr >> 16):
                raise RuntimeError(f"Duplicate or symbolic-link package entry: {entry.filename}")
            seen.add(key)
            if entry.is_dir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with source.open(entry) as inp, path.open("xb") as out:
                    shutil.copyfileobj(inp, out)
    if not valid_files(destination, package["required_files"]):
        raise RuntimeError(f"Incomplete dependency package '{archive}'")


def publish(stage, destination):
    """Replace only after validation; restore the old directory if publication fails."""
    stage, destination = Path(stage), Path(destination)
    backup = destination.with_name(destination.name + ".previous-" + uuid.uuid4().hex)
    previous = destination.exists()
    if previous:
        destination.rename(backup)
    try:
        stage.rename(destination)
    except BaseException:
        if previous:
            backup.rename(destination)
        raise
    if previous:
        shutil.rmtree(backup, ignore_errors=True)  # Running tools may retain handles.
