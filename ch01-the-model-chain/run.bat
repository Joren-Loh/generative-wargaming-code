@echo off
setlocal
rem ---------------------------------------------------------------
rem ch01-the-model-chain / run.bat
rem Run the minimal scenario with mission.exe and report exit code.
rem AFSIM_ROOT may be preset; otherwise use the in-repo install.
rem ---------------------------------------------------------------
if "%AFSIM_ROOT%"=="" set AFSIM_ROOT=%~dp0..\..\..\afsim-2.9.0
if not exist "%AFSIM_ROOT%\bin\mission.exe" (
    echo [ERROR] mission.exe not found under "%AFSIM_ROOT%\bin".
    echo         Set AFSIM_ROOT to your AFSIM install root and retry.
    exit /b 1
)
if not exist "%~dp0output" mkdir "%~dp0output"

pushd "%~dp0"
"%AFSIM_ROOT%\bin\mission.exe" scenario.txt
set RC=%ERRORLEVEL%
popd

echo.
echo mission.exe exit code: %RC%
if exist "%~dp0output\scenario.evt" (
    for %%A in ("%~dp0output\scenario.evt") do echo scenario.evt size: %%~zA bytes
) else (
    echo [WARN] output\scenario.evt was not created.
)
exit /b %RC%
