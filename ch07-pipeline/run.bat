@echo off
rem ch07-pipeline one-click pipeline: generate -> batch_run -> gates
rem Optional: set AFSIM_ROOT to your AFSIM install root before running.
setlocal
cd /d "%~dp0"

set PY=python
where "%PY%" >nul 2>nul
if errorlevel 1 (
  echo [ERR] Python not found in PATH.
  exit /b 1
)

echo ==== 1/3 generate ====
"%PY%" generate.py --clean
if errorlevel 1 exit /b 1

echo.
echo ==== 2/3 batch_run (6 scenarios x 4 runs) ====
"%PY%" batch_run.py --workers 6 --repeats 4 --timeout 120
if errorlevel 1 exit /b 1

echo.
echo ==== 3/3 gates ====
"%PY%" gates.py --run-engine --regress

echo.
echo Done. See reports\ for csv/json/txt output.
endlocal
