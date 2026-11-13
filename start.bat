@echo off
rem Start HPMulti-Tool on Windows. Creates the virtual environment on first run.
rem   start.bat              real instruments
rem   start.bat --simulate   two simulated instruments
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo First start: setting up the Python environment ...
    py -3 -m venv .venv || python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
start "" ".venv\Scripts\pythonw.exe" -m hpmultitool %*
