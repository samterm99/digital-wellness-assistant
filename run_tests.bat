@echo off
rem Runs all automated tests (about 2 minutes). Nothing appears on screen except one brief
rem black full-screen flash from the last test.
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
set PYTHONIOENCODING=utf-8
echo === 1/4 unit tests ===
python -m unittest discover -s tests
echo === 2/4 live app test ===
python tests\live_integration.py
echo === 3/4 control panel test ===
python tests\live_panel.py
echo === 4/4 full-screen detection (screen flashes black for ~5 s) ===
python tests\live_fullscreen.py
echo.
echo Optional long test: python tests\soak.py 300
pause
