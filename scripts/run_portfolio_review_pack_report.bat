@echo off
REM Market Sentry - Portfolio Review Pack Report
REM Runs portfolio review pack export. Report command only. No alert mutation.
REM No live retrieval. No forced live flags. No import/mutation commands.

set LOGDIR=logs\scheduled
if not exist %LOGDIR% mkdir %LOGDIR%

set TIMESTAMP=%date:~-4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set LOGFILE=%LOGDIR%\portfolio_review_pack_%TIMESTAMP%.log

echo [%date% %time%] Starting portfolio review pack report >> %LOGFILE%

python -m marketsentry export-portfolio-review-pack --format both >> %LOGFILE% 2>&1

python -m marketsentry export-portfolio-review-comparison --format both >> %LOGFILE% 2>&1

python -m marketsentry export-portfolio-review-trends --format both >> %LOGFILE% 2>&1

echo [%date% %time%] Portfolio review pack report complete >> %LOGFILE%
