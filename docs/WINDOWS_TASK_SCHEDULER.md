# Market_Sentry Windows Task Scheduler Guide

This guide explains how to automate Market_Sentry workflows using Windows Task Scheduler.

## What Automation Does

- Runs Market_Sentry CLI workflows on a regular schedule (e.g., weekly).
- Processes local data only: SQLite database, CSV imports, saved HTML fixtures, and generated reports.
- Writes timestamped log files to `logs/scheduled/` for each run.
- Returns proper exit codes so Task Scheduler can report success or failure.

## What Automation Does Not Do

- No live web scraping or network calls.
- No Playwright, Selenium, or browser automation.
- No purchase recommendations.
- No bypassing of bot protections.
- No external API calls.

All scheduled tasks operate on local data that has been manually prepared by the user.

## Available Scripts

All scripts are located in the `scripts/` directory:

| Script | Purpose |
|--------|---------|
| `run_watchlist_refresh_workflow.bat` | Run weekly watchlist refresh (primary scheduled workflow) |
| `run_initial_review_workflow.bat` | Run initial candidate review workflow |
| `run_dashboard_summary.bat` | Print text-based dashboard summary |
| `run_fixture_demo_workflow.bat` | Run fixture-based demonstration workflow |
| `run_alert_hygiene_report.bat` | Run cross-site alert hygiene check and export reports |
| `run_alert_lifecycle_trend_report.bat` | Run lifecycle snapshot and trend report export |
| `run_lifecycle_health_report.bat` | Run lifecycle health report, snapshot, and trend report |
| `run_operations_digest_report.bat` | Run operations digest export (Markdown and CSV) |
| `run_marketsentry_task.ps1` | Generic PowerShell wrapper for any command |
| `install_task_scheduler_watchlist_refresh.ps1` | Install weekly scheduled task |
| `uninstall_task_scheduler_watchlist_refresh.ps1` | Remove scheduled task |

## Running Scripts Manually

### Batch Scripts

Double-click any `.bat` file or run from Command Prompt:

```cmd
cd C:\Users\Minis\CascadeProjects\Market_Sentry
scripts\run_watchlist_refresh_workflow.bat
```

### PowerShell Wrapper

The PowerShell wrapper supports all commands with optional parameters:

```powershell
cd C:\Users\Minis\CascadeProjects\Market_Sentry

# Watchlist refresh (default)
powershell -ExecutionPolicy Bypass -File scripts\run_marketsentry_task.ps1 -CommandName watchlist-refresh

# Dashboard summary
powershell -ExecutionPolicy Bypass -File scripts\run_marketsentry_task.ps1 -CommandName dashboard-summary

# Initial review
powershell -ExecutionPolicy Bypass -File scripts\run_marketsentry_task.ps1 -CommandName initial-review

# Fixture demo
powershell -ExecutionPolicy Bypass -File scripts\run_marketsentry_task.ps1 -CommandName fixture-demo

# With custom database path
powershell -ExecutionPolicy Bypass -File scripts\run_marketsentry_task.ps1 -CommandName watchlist-refresh -DatabasePath "db\custom.db"
```

## Installing the Weekly Scheduled Task

### Default Installation (Saturday 9:00 AM)

```powershell
cd C:\Users\Minis\CascadeProjects\Market_Sentry
powershell -ExecutionPolicy Bypass -File scripts\install_task_scheduler_watchlist_refresh.ps1
```

### Custom Schedule

```powershell
# Monday at 8:00 AM
powershell -ExecutionPolicy Bypass -File scripts\install_task_scheduler_watchlist_refresh.ps1 -DayOfWeek Monday -Time "08:00"

# Daily at 7:30 AM
powershell -ExecutionPolicy Bypass -File scripts\install_task_scheduler_watchlist_refresh.ps1 -Schedule Daily -Time "07:30"

# Custom project root
powershell -ExecutionPolicy Bypass -File scripts\install_task_scheduler_watchlist_refresh.ps1 -ProjectRoot "D:\Projects\Market_Sentry"
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `-TaskName` | `Market_Sentry_Watchlist_Refresh` | Name in Task Scheduler |
| `-ProjectRoot` | Auto-detected | Path to Market_Sentry project |
| `-Schedule` | `Weekly` | `Weekly` or `Daily` |
| `-DayOfWeek` | `Saturday` | Day of week (Weekly only) |
| `-Time` | `09:00` | Time to run |
| `-DatabasePath` | (default) | Custom database path |
| `-OutputDir` | (default) | Custom output directory |

## Uninstalling the Scheduled Task

```powershell
cd C:\Users\Minis\CascadeProjects\Market_Sentry
powershell -ExecutionPolicy Bypass -File scripts\uninstall_task_scheduler_watchlist_refresh.ps1
```

To uninstall a custom-named task:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall_task_scheduler_watchlist_refresh.ps1 -TaskName "Custom_Task_Name"
```

## Changing the Schedule

To change the schedule, re-run the install script with new parameters. The installer is idempotent and will replace the existing task:

```powershell
# Change from Saturday to Sunday at 10:00 AM
powershell -ExecutionPolicy Bypass -File scripts\install_task_scheduler_watchlist_refresh.ps1 -DayOfWeek Sunday -Time "10:00"
```

## Inspecting Logs

Logs are written to `logs/scheduled/` with timestamped filenames:

```text
logs/scheduled/
  watchlist_refresh_20260506_090000.log
  dashboard_summary_20260505_143000.log
  initial_review_20260504_080000.log
```

Each log file contains:

- Start time
- Working directory
- Python/virtualenv information
- Full command output (stdout and stderr)
- Exit code
- End time and duration

To view the latest log:

```cmd
dir /o-d logs\scheduled\*.log
type logs\scheduled\watchlist_refresh_LATEST.log
```

Or use the CLI:

```cmd
marketsentry automation-status
```

## CLI Commands

### automation-status

Prints the current automation environment:

```cmd
marketsentry automation-status
```

Shows: project root, Python executable, virtualenv, database path, exports directory, available scripts, and latest log.

### write-scheduler-scripts

Validates that all expected scripts exist:

```cmd
marketsentry write-scheduler-scripts
```

## Troubleshooting

### Task does not run

1. Open Task Scheduler (`taskschd.msc`).
2. Find `Market_Sentry_Watchlist_Refresh` in the task list.
3. Check the "Last Run Result" column.
4. Right-click the task and select "Run" to test manually.
5. Check `logs/scheduled/` for the log file.

### Python not found

The scripts look for a virtual environment in `.venv/` or `venv/` under the project root. If no venv is found, system Python is used. Ensure Python is on your PATH or create a virtual environment:

```cmd
cd C:\Users\Minis\CascadeProjects\Market_Sentry
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Permission errors

The scheduled task runs with your user account at "Limited" privilege. No administrator rights are required. If you see permission errors:

1. Ensure the project directory is writable.
2. Ensure the database file is not locked by another process.
3. Check that `logs/scheduled/` exists or can be created.

### Exit code is non-zero

Check the log file for error details. Common causes:

- Database not initialized: Run `marketsentry init-database` first.
- Missing input files: Ensure CSV/fixture files exist.
- Python import errors: Ensure all dependencies are installed.

## Security Notes

- The scheduled task runs with your current Windows user credentials.
- No passwords are stored in the task configuration.
- The task runs only when you are logged on (default).
- No network access is required or attempted.
- All data is processed locally.
