@echo off
setlocal
cd /d "%~dp0"
title SOCCS Treasury
if not exist ".venv\Scripts\python.exe" (
  echo Python environment is missing. Follow the setup steps in README.md.
  pause
  exit /b 1
)
echo Checking the treasury database...
".venv\Scripts\python.exe" -m flask --app app check-db
if errorlevel 1 (
  echo.
  echo Start MySQL in XAMPP, then check the database settings in .env.
  echo If this is a new installation, follow README.md first.
  pause
  exit /b 1
)
echo.
echo Open http://127.0.0.1:5000 in your browser.
echo Keep this window open while using Treasury. Press Ctrl+C to stop.
".venv\Scripts\python.exe" run.py
if errorlevel 1 pause
