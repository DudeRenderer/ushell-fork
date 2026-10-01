# Copyright Epic Games, Inc. All Rights Reserved.
param([Parameter(Mandatory=$true)][string]$Working)

$ErrorActionPreference = 'Stop'
$Version = '3.14.3'
$UpstreamHash = 'ad4961a479dedbeb7c7d113253f8db1b1935586b73c27488712beec4f2c894e6'
$Packages = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../dependencies/windows-x64'))
$PythonRoot = [IO.Path]::GetFullPath((Join-Path $Working 'python'))
$Current = Join-Path $PythonRoot 'current'
$Stage = Join-Path $PythonRoot ('stage-' + [Guid]::NewGuid())
$Backup = Join-Path $PythonRoot ('previous-' + [Guid]::NewGuid())
$Lock = $null

function Get-Sha256([string]$Path) {
    $Stream = [IO.File]::OpenRead($Path)
    $Hash = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($Hash.ComputeHash($Stream)).Replace('-', '').ToLowerInvariant() }
    finally { $Stream.Dispose(); $Hash.Dispose() }
}

function Get-SafePath([string]$Root, [string]$Relative) {
    if ([IO.Path]::IsPathRooted($Relative) -or $Relative.Contains(':')) {
        throw "Unsafe package path: $Relative"
    }
    $Prefix = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    $Path = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
    if (!$Path.StartsWith($Prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe package path: $Relative"
    }
    return $Path
}

function Test-Files([string]$Root, $Files) {
    if (!$Files -or @($Files.PSObject.Properties).Count -eq 0) { return $false }
    foreach ($File in $Files.PSObject.Properties) {
        $Path = Get-SafePath $Root $File.Name
        if (!(Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
        if ((Get-Sha256 $Path) -ne $File.Value) { return $false }
    }
    return $true
}

function Test-Runtime([string]$Root) {
    $Exe = Join-Path $Root 'flow_python.exe'
    if (!(Test-Path -LiteralPath $Exe)) { return $false }
    try {
        & $Exe -Xutf8 -EsB -c 'import sys, struct, ssl, sqlite3, ctypes, zipfile, marshal, pip; assert sys.version_info[:3] == (3, 14, 3); assert struct.calcsize(chr(80)) == 8' 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

function Expand-SafeZip([string]$Archive, [string]$Destination) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        foreach ($Entry in $Zip.Entries) {
            $Path = Get-SafePath $Destination $Entry.FullName
            if ($Entry.FullName.EndsWith('/')) {
                [IO.Directory]::CreateDirectory($Path) | Out-Null
            } else {
                [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Path)) | Out-Null
                [IO.Compression.ZipFileExtensions]::ExtractToFile($Entry, $Path, $false)
            }
        }
    } finally { $Zip.Dispose() }
}

function Get-OnlineFile([string]$Url, [string]$Destination) {
    if ($env:USHELL_ALLOW_DOWNLOADS -ne '1') { throw 'Dependency downloads require USHELL_ALLOW_DOWNLOADS=1' }
    & "$env:SystemRoot\System32\curl.exe" --fail --location --silent --show-error --output $Destination $Url
    if ($LASTEXITCODE -ne 0) { throw "Failed to download $Url" }
}

try {
    [IO.Directory]::CreateDirectory($PythonRoot) | Out-Null
    # Serialize provisioning so concurrent shells cannot replace each other's runtime.
    $Lock = [IO.File]::Open((Join-Path $PythonRoot 'provision.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $ManifestPath = Join-Path $Packages 'manifest.json'
    $Package = $null
    if (Test-Path -LiteralPath $ManifestPath) {
        $Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
        if ($Manifest.schema_version -ne 1 -or $Manifest.platform -ne 'windows-x64') { throw "Unsupported dependency manifest: $ManifestPath" }
        $Package = $Manifest.packages.python
        if ($Package -and $Package.version -ne $Version) { throw "Python package version mismatch: expected $Version in $ManifestPath" }
    }
    if ($Package -and (Test-Files $Current $Package.required_files) -and (Test-Runtime $Current)) {
        Write-Host "Using cached Python $Version"
        exit 0
    }
    # Online installations retain their own file inventory; they remain reusable offline.
    $ReceiptPath = Join-Path $Current '.ushell-runtime.json'
    if (Test-Path -LiteralPath $ReceiptPath) {
        try {
            $Receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
            if ($Receipt.version -eq $Version -and $Receipt.source -eq 'verified-upstream' -and (Test-Files $Current $Receipt.required_files) -and (Test-Runtime $Current)) {
                Write-Host "Using cached Python $Version"
                exit 0
            }
        } catch { Write-Verbose 'Ignoring invalid Python installation receipt' }
    }
    [IO.Directory]::CreateDirectory($Stage) | Out-Null
    $Archive = if ($Package) { Get-SafePath $Packages $Package.archive } else { Join-Path $Packages "python-$Version.zip" }
    if (Test-Path -LiteralPath $Archive) {
        if (!$Package) { throw "Missing Python metadata in $ManifestPath" }
        Write-Host "Installing Python $Version from $Archive"
        if ((Get-Sha256 $Archive) -ne $Package.sha256) { throw "SHA-256 mismatch: $Archive" }
        Expand-SafeZip $Archive $Stage
        if (!(Test-Files $Stage $Package.required_files)) { throw "Incomplete Python package: $Archive" }
    } else {
        if ($env:USHELL_ALLOW_DOWNLOADS -ne '1') {
            throw "Python $Version is unavailable. Checked cache '$Current' and package '$Archive' (manifest '$ManifestPath'). Restore the repository dependency package or explicitly set USHELL_ALLOW_DOWNLOADS=1."
        }
        Write-Host "Downloading Python $Version (USHELL_ALLOW_DOWNLOADS=1)"
        $Download = Join-Path $Stage 'python.zip'
        Get-OnlineFile "https://www.python.org/ftp/python/$Version/python-$Version-embed-amd64.zip" $Download
        if ((Get-Sha256 $Download) -ne $UpstreamHash) { throw 'Upstream Python SHA-256 mismatch' }
        Expand-SafeZip $Download $Stage
        Remove-Item -LiteralPath $Download
        Get-ChildItem -LiteralPath $Stage -Filter '*._pth' | Remove-Item
        Expand-SafeZip (Join-Path $Stage 'python314.zip') (Join-Path $Stage 'Lib')
        Remove-Item -LiteralPath (Join-Path $Stage 'python314.zip')
        $Dlls = Join-Path $Stage 'DLLs'
        [IO.Directory]::CreateDirectory($Dlls) | Out-Null
        Get-ChildItem -LiteralPath $Stage -File | Where-Object { $_.Name -like '*.pyd' -or $_.Name -like 'lib*.dll' -or $_.Name -like 'sq*.dll' } | Move-Item -Destination $Dlls
        Copy-Item -LiteralPath (Join-Path $Stage 'python.exe') -Destination (Join-Path $Stage 'flow_python.exe')
        $GetPip = Join-Path $Stage 'get-pip.py'
        Get-OnlineFile 'https://bootstrap.pypa.io/get-pip.py' $GetPip
        & (Join-Path $Stage 'flow_python.exe') -Xutf8 -Es $GetPip --no-warn-script-location
        if ($LASTEXITCODE -ne 0) { throw 'Failed to install Pip' }
        Remove-Item -LiteralPath $GetPip
        $Files = [ordered]@{}
        Get-ChildItem -LiteralPath $Stage -File -Recurse | Where-Object { $_.FullName -notmatch '[\\/](__pycache__|Scripts)[\\/]' } | ForEach-Object {
            $Files[$_.FullName.Substring($Stage.Length + 1).Replace('\', '/')] = Get-Sha256 $_.FullName
        }
        @{ version = $Version; source = 'verified-upstream'; required_files = $Files } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Stage '.ushell-runtime.json') -Encoding UTF8
    }
    if (!(Test-Runtime $Stage)) { throw "Python $Version runtime validation failed in $Stage" }
    Set-Content -LiteralPath (Join-Path $Stage "$Version.version") -Value $Version -Encoding ASCII
    if (Test-Path -LiteralPath $Current) { Move-Item -LiteralPath $Current -Destination $Backup }
    try { Move-Item -LiteralPath $Stage -Destination $Current }
    catch {
        if (Test-Path -LiteralPath $Backup) { Move-Item -LiteralPath $Backup -Destination $Current }
        throw
    }
    # Previous interpreters may still be in use. Never fail a valid install for cleanup.
    if (Test-Path -LiteralPath $Backup) { Remove-Item -LiteralPath $Backup -Recurse -Force -ErrorAction SilentlyContinue }
    Write-Host "Python $Version ready"
} catch {
    [Console]::Error.WriteLine("ERROR: " + $_.Exception.Message)
    exit 1
} finally {
    if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force -ErrorAction SilentlyContinue }
    if ($Lock) { $Lock.Dispose() }
}
