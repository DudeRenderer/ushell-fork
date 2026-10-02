# Windows offline dependencies

These ZIP files are snapshots of an existing ushell installation, not copies of
the upstream release archives. `manifest.json` records their versions, SHA-256
digests, required files, and local-cache provenance. The archives include their
licenses. They are ordinary Git files; Git LFS is not required.

Rebuild them from a known installation with:

```powershell
python scripts/package_windows_dependencies.py --cache-root "$env:LOCALAPPDATA\ushell\.working"
```

The packager preserves the embedded Python standard library's `.pyc` files and
installed Pip module, but excludes generated `__pycache__` directories, logs,
installation markers, tool manifests, and machine-specific Pip launchers.
Archive entries have fixed timestamps and a stable order for reproducible output.
