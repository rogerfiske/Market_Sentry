@echo off
REM Market Sentry - Local Operations Bundle Report
REM Runs local operations bundle export. Report command only. No alert mutation.
REM No live retrieval. No forced live flags. No import/mutation commands.
REM No outbound notifications. No SMTP/Gmail/Outlook/webhook/SMS.

set LOGDIR=logs\scheduled
if not exist %LOGDIR% mkdir %LOGDIR%

set TIMESTAMP=%date:~-4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set LOGFILE=%LOGDIR%\local_operations_bundle_%TIMESTAMP%.log

echo [%date% %time%] Starting local operations bundle report >> %LOGFILE%

python -m marketsentry export-local-operations-bundle --format both >> %LOGFILE% 2>&1

echo [%date% %time%] Local operations bundle report complete >> %LOGFILE%
