@echo off
rem Sample-data preview on http://127.0.0.1:5001. Separate SQLite data; MySQL is not needed.
title SOCCS Treasury preview
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The app is not installed yet. Follow "New Windows installation" in README.md.
  pause
  exit /b 1
)
start "" cmd /c "timeout /t 4 >nul & start http://127.0.0.1:5001"
".venv\Scripts\python.exe" scripts\preview.py
pause
