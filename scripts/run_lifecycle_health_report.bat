@echo off
REM Market Sentry - Lifecycle Health Report
REM Runs health report export, health snapshot, and trend report.
REM Report and snapshot commands only. No alert mutation.

set LOGDIR=logs\scheduled
if not exist %LOGDIR% mkdir %LOGDIR%

set TIMESTAMP=%date:~-4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set LOGFILE=%LOGDIR%\lifecycle_health_%TIMESTAMP%.log

echo [%date% %time%] Starting lifecycle health report >> %LOGFILE%

python -m marketsentry export-cross-site-lifecycle-health-report >> %LOGFILE% 2>&1
python -m marketsentry snapshot-cross-site-lifecycle-health >> %LOGFILE% 2>&1
python -m marketsentry export-cross-site-lifecycle-health-trend-report >> %LOGFILE% 2>&1

echo [%date% %time%] Lifecycle health report complete >> %LOGFILE%
