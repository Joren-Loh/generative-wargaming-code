@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if "%AFSIM_ROOT%"=="" (
  if exist config.json (
    echo Using config.json
  ) else (
    echo [ERROR] AFSIM_ROOT is not set and config.json not found.
    echo         set AFSIM_ROOT=C:\path\to\afsim-2.9.0
    exit /b 1
  )
)

python wargame.py
endlocal
