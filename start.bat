@echo off
rem Starts the reminder (tray icon) and, normally, the control window.
rem   start.bat           manual start: always opens the control window
rem   start.bat startup   Windows-login start: window only if enabled in the panel
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
set EXTRA=
if /i "%~1"=="startup" set EXTRA=--startup
start "" pythonw -m wellness
start "" pythonw -m wellness --auto-panel %EXTRA%
