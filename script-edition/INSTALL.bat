@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Digital Wellness Assistant - Install
echo.
echo  Digital Wellness Assistant - installer
echo  ======================================
echo.

call :findpython
if defined PY goto :run

echo  Python 3.9+ (with tkinter) was not found on this PC.
where winget >nul 2>nul
if errorlevel 1 goto :nowinget
echo  Installing Python 3.12 with winget (official, signed by Python Software Foundation)...
echo  If Windows asks for permission, click Yes.
echo.
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
call :findpython
if defined PY goto :run

echo.
echo  Python is still not usable. Showing diagnostic information...
call :diag
echo.
echo  winget says Python is installed but the files are missing (the earlier install was probably blocked).
echo  Removing the incomplete Python entry first...
winget uninstall -e --id Python.Python.3.12 --silent
echo.
echo  Installing Python again. IMPORTANT: if your antivirus (for example 360 Total Security)
echo  shows a warning window about this installer, click ALLOW quickly (before its countdown ends).
echo  Do NOT tick "do not remind me again".
echo.
winget install -e --id Python.Python.3.12 --force --accept-package-agreements --accept-source-agreements
call :findpython
if defined PY goto :run

echo.
echo  ------------------------------------------------------------
echo  Still not found. Please take a photo/screenshot of THIS window
echo  (including the diagnostic information above) and send it to
echo  the person who gave you this installer.
echo  If the window says Python was just installed, close it and
echo  double-click INSTALL.bat once more.
echo  ------------------------------------------------------------
pause
exit /b 1

:nowinget
echo  Please install Python from https://www.python.org/downloads/
echo  (keep "tcl/tk and IDLE" ticked), then double-click INSTALL.bat again.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:run
echo  Using Python: %PY%
echo.
%PY% "%~dp0installer\install.py"
echo.
pause
exit /b 0

:findpython
set "PY="
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import tkinter,sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY=py -3"
)
if defined PY exit /b 0
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*" "C:\Python3*") do call :trydir "%%~D"
if defined PY exit /b 0
where python >nul 2>nul
if not errorlevel 1 (
  python -c "import tkinter,sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
exit /b 0

:trydir
if defined PY exit /b 0
if not exist "%~1\python.exe" exit /b 0
"%~1\python.exe" -c "import tkinter,sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
if not errorlevel 1 set "PY="%~1\python.exe""
exit /b 0

:diag
echo  ---- diagnostics ----
echo  where py:
where py 2>&1
echo  where python:
where python 2>&1
echo  py -0p:
py -0p 2>&1
echo  Python folders (user):
dir /b "%LOCALAPPDATA%\Programs\Python" 2>&1
echo  Python folders (Program Files):
dir /b "%ProgramFiles%\Python3*" 2>&1
echo  tkinter check via py:
py -3 -c "import sys,tkinter;print(sys.version)" 2>&1
echo  ---------------------
exit /b 0
