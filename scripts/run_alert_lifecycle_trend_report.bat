@echo off
REM Market Sentry - Alert Lifecycle Trend Report
REM Runs lifecycle snapshot and trend report export only.
REM Does NOT run live retrieval or mutate alert status.
REM Snapshot and report commands only. No browser automation.
REM Append-only snapshot writes only.

set LOGDIR=logs\scheduled
if not exist %LOGDIR% mkdir %LOGDIR%

set TIMESTAMP=%date:~-4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set LOGFILE=%LOGDIR%\alert_lifecycle_trend_%TIMESTAMP%.log

echo [%date% %time%] Starting alert lifecycle trend report >> %LOGFILE%

python -m marketsentry snapshot-cross-site-alert-lifecycle >> %LOGFILE% 2>&1
python -m marketsentry export-cross-site-alert-lifecycle-trend-report >> %LOGFILE% 2>&1

echo [%date% %time%] Alert lifecycle trend report complete >> %LOGFILE%
