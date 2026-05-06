@echo off
REM Market_Sentry - Run Watchlist Refresh Workflow
REM This script runs the watchlist refresh workflow using local data only.
REM No live scraping or network calls are performed.
REM This is the primary script for weekly scheduled execution.

setlocal enabledelayedexpansion

REM Determine project root (parent of scripts directory)
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
cd /d "%PROJECT_ROOT%"

REM Create scheduled log directory
if not exist "logs\scheduled" mkdir "logs\scheduled"

REM Timestamp for log file
for /f "tokens=1-6 delims=/:. " %%a in ("%date% %time%") do (
    set "TIMESTAMP=%%c%%a%%b_%%d%%e%%f"
)
set "LOG_FILE=logs\scheduled\watchlist_refresh_%TIMESTAMP%.log"

echo ================================================== >> "%LOG_FILE%"
echo Market_Sentry Watchlist Refresh Workflow >> "%LOG_FILE%"
echo Start: %date% %time% >> "%LOG_FILE%"
echo Working Directory: %CD% >> "%LOG_FILE%"
echo ================================================== >> "%LOG_FILE%"

REM Activate virtual environment if present
if exist ".venv\Scripts\activate.bat" (
    echo Activating .venv >> "%LOG_FILE%"
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    echo Activating venv >> "%LOG_FILE%"
    call "venv\Scripts\activate.bat"
) else (
    echo No virtual environment found, using system Python >> "%LOG_FILE%"
)

echo Python: >> "%LOG_FILE%"
python --version >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo Running: marketsentry run-watchlist-refresh-workflow >> "%LOG_FILE%"
echo ================================================== >> "%LOG_FILE%"

python -c "from marketsentry.cli import app; app()" run-watchlist-refresh-workflow >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

echo ================================================== >> "%LOG_FILE%"
echo Exit Code: %EXIT_CODE% >> "%LOG_FILE%"
echo End: %date% %time% >> "%LOG_FILE%"
echo ================================================== >> "%LOG_FILE%"

echo Log written to: %LOG_FILE%

exit /b %EXIT_CODE%
