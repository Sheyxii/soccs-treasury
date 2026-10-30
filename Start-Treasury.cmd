@echo off
rem SOCCS Treasury launcher. Start MySQL in the XAMPP Control Panel first, then double-click this file.
title SOCCS Treasury
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo The app is not installed yet. Follow "New Windows installation" in README.md.
  pause
  exit /b 1
)
if not exist ".env" (
  echo .env is missing. Run: .venv\Scripts\python.exe scripts\setup_xampp.py
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m flask --app app check-db >nul 2>&1
if errorlevel 1 (
  echo Cannot open the database.
  echo  - Is MySQL started in the XAMPP Control Panel? Start it and try again.
  echo  - After installing or updating the app, run: .venv\Scripts\python.exe scripts\upgrade_database.py
  pause
  exit /b 1
)

echo Opening http://127.0.0.1:5000 in your browser. Keep this window open while you work.
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000"
".venv\Scripts\python.exe" run.py
pause
