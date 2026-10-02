:: Copyright Epic Games, Inc. All Rights Reserved.
@echo off
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0provision.ps1" -Working "%~1"
exit /b %errorlevel%
