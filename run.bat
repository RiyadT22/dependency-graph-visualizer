@echo off
rem Usage: run.bat [config.csv]   Tests: run.bat test
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
if "%~1"=="test" (
    python -m unittest discover -s tests -v
    exit /b %errorlevel%
)
python -m depgraph %*
