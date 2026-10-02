:: Copyright Epic Games, Inc. All Rights Reserved.
@echo off
setlocal
chcp 65001 1>nul 2>nul

set "_working=%localappdata%\ushell\.working"
if defined flow_working_dir set "_working=%flow_working_dir%"

if exist "%userprofile%\.ushell\hooks\boot.bat" (
    call "%userprofile%\.ushell\hooks\boot.bat"
)

call "%~dp0provision.bat" "%_working%"
if errorlevel 1 exit /b %errorlevel%

if not exist "%temp%\ushell" mkdir "%temp%\ushell"
set "_cookie=%temp%\ushell\cmd_boot_%random%_%random%"
"%_working%\python\current\flow_python.exe" -Xutf8 -Esu "%~dp0..\core\system\boot.py" "--bootarg=cmd,%_cookie%" %*
set "_result=%errorlevel%"
if "%_result%"=="127" exit /b 0
if not "%_result%"=="0" (
    echo ERROR: boot.py failed [%_result%] 1>&2
    exit /b %_result%
)
if not exist "%_cookie%" (
    echo ERROR: Missing ushell boot cookie 1>&2
    exit /b 1
)

endlocal & (
    for /f "usebackq delims=" %%d in ("%_cookie%") do (
        %%d
    )
    del /q "%_cookie%"
)
exit /b 0
