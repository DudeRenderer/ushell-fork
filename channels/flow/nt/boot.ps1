# Copyright Epic Games, Inc. All Rights Reserved.

$Working = [IO.Path]::Combine($env:LOCALAPPDATA, "ushell\.working")
if (![String]::IsNullOrEmpty($env:flow_working_dir)) {
    $Working = $env:flow_working_dir
}

$ProvisionScript = [IO.Path]::Combine($PSScriptRoot, "provision.ps1")
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File $ProvisionScript -Working $Working
if ($LASTEXITCODE -ne 0) {
    throw "Ushell provisioning failed"
}

$PythonPath = [IO.Path]::Combine($Working, "python\current\flow_python.exe")
$Bootpy = [IO.Path]::Combine($PSScriptRoot, "..\core\system\boot.py")
$TempDir = [IO.Path]::Combine($env:TEMP, "ushell")
[IO.Directory]::CreateDirectory($TempDir) | Out-Null
$Cookie = [IO.Path]::Combine($TempDir, "pwsh_boot_$([Guid]::NewGuid()).ps1")
& $PythonPath "-Xutf8" "-Esu" $Bootpy "--bootarg=pwsh,$Cookie" @Args | Out-Host
$PythonReturn = $LASTEXITCODE
if ($PythonReturn -eq 127) {
    $global:LASTEXITCODE = 0
    return
}
if ($PythonReturn -ne 0) {
    throw "Python boot failed (exit $PythonReturn)"
}
try {
    if (!(Test-Path -LiteralPath $Cookie)) { throw "Missing ushell boot cookie: $Cookie" }
    Import-Module $Cookie -ErrorAction Stop
}
finally {
    if (Test-Path -LiteralPath $Cookie) {
        Remove-Item -LiteralPath $Cookie
    }
}
