# Copyright Epic Games, Inc. All Rights Reserved.

# Importing this module recursively imports the boot.ps1 module into the host's
# session. That module will in turn import a dynamically created module into
# the session. For more details see README.txt.

$BootPs1Path = Split-Path $PSScriptRoot
$BootPs1Path = [IO.Path]::Combine($BootPs1Path, "channels\flow\nt\boot.ps1")
Import-Module $BootPs1Path -ArgumentList $Args