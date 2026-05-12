@echo off
REM Market Sentry - Operations Digest Report
REM Runs operations digest export, snapshot, and comparison report.
REM Report commands only. No alert mutation. No live retrieval.

set LOGDIR=logs\scheduled
if not exist %LOGDIR% mkdir %LOGDIR%

set TIMESTAMP=%date:~-4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set LOGFILE=%LOGDIR%\operations_digest_%TIMESTAMP%.log

echo [%date% %time%] Starting operations digest report >> %LOGFILE%

python -m marketsentry export-operations-digest --format both >> %LOGFILE% 2>&1

echo [%date% %time%] Creating operations digest snapshot >> %LOGFILE%

python -m marketsentry snapshot-operations-digest >> %LOGFILE% 2>&1

echo [%date% %time%] Exporting operations digest comparison report >> %LOGFILE%

python -m marketsentry export-operations-digest-comparison-report --format both >> %LOGFILE% 2>&1

echo [%date% %time%] Operations digest report complete >> %LOGFILE%
