@echo off
rem one shot: retrieval -> validation -> repair loop -> end-to-end generation
if "%AFSIM_ROOT%"=="" set AFSIM_ROOT=%~dp0..\..\..\afsim-2.9.0

echo [1/4] BM25 retrieval demo ...
python rag.py "air-to-air missile stealth fighter"
if errorlevel 1 goto :err

echo [2/4] Schema check on ten samples (errors expected, exit code 1 is normal) ...
python schema_check.py samples

echo [3/4] Execution-feedback repair loop (about a minute) ...
python repair.py --all
if errorlevel 1 goto :err

echo [4/4] End-to-end generation (offline surrogate) ...
python generate.py --demo3
echo All done.
goto :eof

:err
echo Failed. Check AFSIM_ROOT and the Python environment.
