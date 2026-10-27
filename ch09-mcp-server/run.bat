@echo off
chcp 936 >nul
cd /d "%~dp0"
echo [1/2] RPC protocol test
python test_rpc.py
if errorlevel 1 goto fail
echo.
echo [2/2] Agent demo
python agent_demo.py
if errorlevel 1 goto fail
echo.
echo ALL PASS
goto end
:fail
echo FAILED
:end
