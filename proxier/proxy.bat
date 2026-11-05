@echo off
rem SPDX-License-Identifier: GPL-3.0-or-later
rem Windows launcher for mtg-proxier. Usage (from PowerShell or cmd):
rem     .\proxy.bat my-deck.csv --skip-basics
rem First run builds a private Python environment in .venv next to this file
rem and installs the requirements. No activation step and no PowerShell script
rem policy involved: batch files aren't covered by it.
setlocal
set "HERE=%~dp0"
set "VENV_PY=%HERE%.venv\Scripts\python.exe"

if exist "%VENV_PY%" goto deps

rem Find a real Python. The "py" launcher comes with the python.org installer.
rem Plain "python" can be the Microsoft Store stub, which opens the Store instead
rem of running anything, so it's only tried second and is checked by running it.
set "BASE_PY="
where py >nul 2>nul && set "BASE_PY=py -3"
if not defined BASE_PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul && set "BASE_PY=python"
)
if not defined BASE_PY (
    echo Python 3.9 or newer was not found.
    echo Install it from https://www.python.org/downloads/ and re-run this.
    echo In the installer, tick "Add python.exe to PATH".
    exit /b 1
)
%BASE_PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"
if errorlevel 1 (
    echo mtg-proxier needs Python 3.9 or newer. Install a newer one from https://www.python.org/downloads/
    exit /b 1
)
echo First run: setting up Python environment in "%HERE%.venv" ...
%BASE_PY% -m venv "%HERE%.venv"
if errorlevel 1 (
    echo Could not create the environment.
    exit /b 1
)

:deps
rem Cheap when everything is already installed; picks up new requirements after a git pull.
"%VENV_PY%" -m pip install --quiet --disable-pip-version-check -r "%HERE%requirements.txt"
if errorlevel 1 (
    echo Installing requirements failed. Check your internet connection and try again.
    exit /b 1
)

"%VENV_PY%" "%HERE%mtg_proxier.py" %*
exit /b %errorlevel%
