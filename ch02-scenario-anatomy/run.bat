@echo off
setlocal
rem ---------------------------------------------------------------
rem ch02-scenario-anatomy / run.bat
rem 2v2 air combat: geometric sensor + explicit weapon flyout.
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
"%AFSIM_ROOT%\bin\mission.exe" scenario.txt > console.txt 2>&1
set RC=%ERRORLEVEL%
popd

echo mission.exe exit code: %RC%
echo.
echo ---- console tail ----
powershell -NoProfile -Command "Get-Content -Tail 6 '%~dp0console.txt'"
echo.
for %%F in ("%~dp0output\scenario.evt" "%~dp0output\scenario.aer" "%~dp0output\scenario.log") do (
    if exist "%%F" (echo %%~nxF  %%~zF bytes) else (echo %%~nxF  MISSING)
)
exit /b %RC%
