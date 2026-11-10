@echo off
rem Closes the running reminder app.
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
python -m wellness --quit
ping -n 3 127.0.0.1 >nul
