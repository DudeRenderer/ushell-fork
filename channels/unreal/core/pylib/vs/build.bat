@echo off
pushd %~dp0

cl.exe 1>nul 2>nul
if errorlevel 9009 (
    for /f "delims=" %%d in ('vswhere -latest -find VC/Auxiliary/Build/vcvars64.bat') do (
        call "%%d"
    )
)

setlocal

set pysdk=%~f1
if "%pysdk%"=="" goto:usage

for /f "delims=" %%d in ('vswhere -latest -find **/Inc/dte80.h') do (
    echo found VS SDK; vssdk=%%~dpd
    set vssdk=%%~dpd
)

if "%vssdk%"=="" (
    echo ensure vswhere can find dte80.h by installing VS SDK.
    goto:eof
)

if not "%2"=="debug" (
    set _cl=/O1 /Os
) else (
    set _cl=/Od
    set _link=/debug
)

set _cl="/I%vssdk%." "/I%pysdk%/include" /nologo /Zl /Zi /EHs-c- /FC /GS- /c %_cl%
set _link=%_link% /nologo /dll /machine:x64^
    /nodefaultlib /align:16^
    /incremental:no /opt:ref,icf^
    "/libpath:%pysdk%/libs" python3.lib ole32.lib oleaut32.lib kernel32.lib user32.lib ntdll.lib

mkdir 1>nul 2>nul _build
cd _build

call:go cl.exe ../dte.cpp %_cl%
if errorlevel 1 exit /b 1

call:go link.exe %_link% /out:dte.pyd dte.obj
if errorlevel 1 exit /b 1

move /y dte.pyd ..

popd
goto:eof

:go
echo.
echo [96m%*[0m
%*
goto:eof

:usage
echo usage: %~nx0 pysdk [debug]
goto:eof
