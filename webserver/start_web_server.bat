@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

echo ========================================
echo  START CRONTAB SCHEDULER
echo ========================================
echo.

rem Check Python
python --version >nul 2>&1 || (echo ERROR: Python not found in PATH.& pause & exit /b 1)

rem Ensure required packages
python -m pip show flask >nul 2>&1 || python -m pip install --quiet --disable-pip-version-check flask
python -m pip show python-telegram-bot >nul 2>&1 || python -m pip install --quiet --disable-pip-version-check python-telegram-bot
python -m pip show pywin32 >nul 2>&1 || python -m pip install --quiet --disable-pip-version-check pywin32
python -m pip show schedule >nul 2>&1 || python -m pip install --quiet --disable-pip-version-check schedule

rem Force terminate ALL python.exe processes for clean start
echo Stopping all existing python processes...
taskkill /IM python3.11.exe /F >nul 2>&1
timeout /t 5 >nul
echo All python processes stopped.
echo.

echo Starting all services...
echo.

echo 1. Starting Crontab Scheduler...
start "crontab" /B python crontab.py
timeout /t 3 >nul

rem Wait a moment
timeout /t 3 >nul

echo.
echo ========================================
echo  ALL SERVICES STARTED SUCCESSFULLY!
echo ========================================
echo.
echo Services running:
echo - Crontab Scheduler (PID: check Task Manager)
echo.
echo To stop all services: run: taskkill /F /IM python.exe
echo To check service status: run: python start_web_server.py
endlocal