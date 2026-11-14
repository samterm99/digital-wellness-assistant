@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Digital Wellness Assistant - Uninstall
set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%~D\python.exe" set "PY="%%~D\python.exe""
if not defined PY set "PY=python"
%PY% "%~dp0installer\install.py" --uninstall
echo.
pause
