# Claude Code Prompt 013 - Windows Task Scheduler Automation

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository:

https://github.com/rogerfiske/Market_Sentry

Local project folder:

C:\Users\Minis\CascadeProjects\Market_Sentry

Current accepted milestones:

- Milestone 1 scaffold complete at commit c8599761be1aeda80b075cf668c61970e587ebe7
- Milestone 2 candidate review queue and watchlist promotion complete at commit 5da7747a44069696189d1abb8057ee23f17d8754
- Milestone 3 Redfin discovery adapter foundation complete at commit 91eac91085609c38f150881bf35e5a22d1f6bdf0
- Milestone 4 Redfin detail parser and candidate enrichment complete at commit dafb63d
- Milestone 5 Effective DOM engine and candidate scoring report complete at commit 52ea72d
- Milestone 6 cross-site enrichment foundation stabilized and accepted at commit 01b6887
- Milestone 7 watchlist monitoring snapshots and change detection complete at commit 23ac2b5
- Milestone 8 county recorder and assessor verification foundation complete at commit 89ce91a
- Milestone 9 Effective DOM v2 county-verified reset integration complete at commit 0e83285
- Milestone 10 Effective DOM v2 operational integration complete at commit 44b655d
- Milestone 11 end-to-end operating workflow and runbook complete at commit 6cf5627
- Prompt 011A export path stabilization complete at commit 4475634
- Milestone 12 local dashboard and report viewer complete at commit 6cb30f1

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Review the current codebase through commit 6cb30f1.
5. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
6. Keep PRD.md and Architecture.md in the project root.
7. Use src/marketsentry/ as the Python package path.
8. Do not move PRD.md or Architecture.md into docs/.
9. Do not implement live scraping, browser automation, Playwright, Selenium, or active network retrieval in this milestone.
10. Do not implement live County Recorder/Assessor access in this milestone.
11. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 13 should add Windows Task Scheduler automation support for the existing local workflows.

Do not add live data retrieval.

The goal is to make Market_Sentry easy to run on a regular schedule on the user's Windows 11 machine using local workflows, local database files, local CSV inputs, saved HTML fixtures, generated reports, dashboard summaries, and logs.

This milestone should produce scripts, CLI helpers, documentation, and tests that support scheduled local operation without external network access.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It starts with Redfin candidate discovery, stages homes for human review, and then monitors user-selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, cross-site validation, county sale/ownership-transfer verification, a separate recent Churn Index, local reports, and a local dashboard.

Critical domain rules:

1. Effective DOM v1 is listing-history-derived exposure without county reset integration.
2. Effective DOM v2 applies county-confirmed ownership transfer as a reset boundary when appropriate.
3. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
4. Churn Index measures recent 2-3 year property/listing instability and remains reportable even when Effective DOM is reset.
5. Quiet Score is the gatekeeper. Reject or heavily downgrade if Quiet Score is below threshold, even when Vibrancy is low.
6. Target is very high Quiet and very low Vibrancy.
7. Low Vibrancy alone is not sufficient.
8. Any mention of gas means the property has natural gas supply/service.
9. Walkability-type information is excluded from the initial scope.
10. Use neutral language. Do not infer seller intent.
11. Reports are analytical aids, not purchase recommendations.
12. The workflow is human-in-the-loop.

Your task for Prompt 013:

Implement Windows Task Scheduler Automation Support v1.

No live network calls.

## 1. Automation scope

Support scheduled execution for these existing workflows:

- initial review workflow
- watchlist refresh workflow
- fixture demo workflow
- dashboard summary
- report manifest update/summary if needed

The most important scheduled workflow is:

```text
marketsentry run-watchlist-refresh-workflow
```

This should be safe to run weekly or manually on demand.

## 2. Windows script outputs

Create Windows-friendly scripts under:

```text
scripts/
```

Required scripts:

```text
scripts/run_initial_review_workflow.bat
scripts/run_watchlist_refresh_workflow.bat
scripts/run_dashboard_summary.bat
scripts/run_fixture_demo_workflow.bat
scripts/install_task_scheduler_watchlist_refresh.ps1
scripts/uninstall_task_scheduler_watchlist_refresh.ps1
scripts/run_marketsentry_task.ps1
```

Script behavior:

- Use the project root path safely.
- Activate local virtual environment if present:
  - .venv\Scripts\activate.bat
  - venv\Scripts\activate.bat
- Fall back to current Python environment if no venv is found.
- Run the correct `marketsentry` CLI command.
- Write logs to:
  - logs/scheduled/
- Use timestamped log files.
- Return a nonzero exit code on failure.
- Use ASCII-safe output.
- Do not require administrator rights unless absolutely necessary.
- Do not perform network calls.

## 3. Task Scheduler install/uninstall scripts

Create PowerShell scripts:

```text
scripts/install_task_scheduler_watchlist_refresh.ps1
scripts/uninstall_task_scheduler_watchlist_refresh.ps1
```

Install script requirements:

- Create a Windows Scheduled Task named:
  - Market_Sentry_Watchlist_Refresh
- Default schedule:
  - weekly
  - Saturday
  - 9:00 AM local time
- Allow parameters:
  - TaskName
  - ProjectRoot
  - Schedule
  - DayOfWeek
  - Time
  - PythonExe optional
  - DatabasePath optional
  - OutputDir optional
- Configure working directory to project root.
- Use `scripts/run_marketsentry_task.ps1` as the execution wrapper.
- Set task to run only when user is logged on unless otherwise specified.
- Avoid storing passwords.
- Print clear instructions after install.
- Be idempotent: if task exists, update or replace safely.

Uninstall script requirements:

- Remove scheduled task by name.
- Handle task not found gracefully.
- Print clear result.

## 4. Generic scheduled task wrapper

Create:

```text
scripts/run_marketsentry_task.ps1
```

Purpose:

A reusable PowerShell wrapper for scheduled Market_Sentry commands.

Parameters:

- CommandName
- ProjectRoot
- DatabasePath optional
- OutputDir optional
- LogDir optional

Supported CommandName values:

- watchlist-refresh
- initial-review
- dashboard-summary
- fixture-demo

Behavior:

- Change to project root.
- Activate venv if present.
- Run the appropriate CLI command.
- Capture stdout/stderr.
- Write timestamped log file.
- Return correct exit code.
- Print log path.
- Do not run external network retrieval.

## 5. Python automation helper module

Create a Python module, for example:

```text
src/marketsentry/automation.py
```

Required helper functions:

- get_project_root() -> Path
- find_python_executable(project_root: Path | None = None) -> Path | None
- find_virtualenv_activate_script(project_root: Path | None = None) -> Path | None
- build_task_command(command_name: str, project_root: Path, db_path: Path | None = None, output_dir: Path | None = None) -> list[str]
- write_automation_status(...)
- read_latest_scheduled_log(...)

These helpers should be testable without actually registering Windows tasks.

## 6. CLI commands

Add CLI commands:

```text
marketsentry automation-status
marketsentry write-scheduler-scripts
```

### automation-status

Print:

- project root
- Python executable
- detected venv
- database path
- exports directory
- scheduled logs directory
- whether Task Scheduler scripts exist
- latest scheduled log if present

### write-scheduler-scripts

If scripts are already committed, this command may simply validate that expected scripts exist and print paths.

If you choose to generate scripts dynamically, this command should write/update them. But committed script files are preferred.

## 7. Logging

Ensure scheduled runs write logs under:

```text
logs/scheduled/
```

Log naming examples:

```text
watchlist_refresh_YYYYMMDD_HHMMSS.log
dashboard_summary_YYYYMMDD_HHMMSS.log
initial_review_YYYYMMDD_HHMMSS.log
fixture_demo_YYYYMMDD_HHMMSS.log
```

Include:

- start time
- command
- working directory
- Python/venv info if known
- stdout
- stderr
- exit code
- end time

## 8. Documentation

Update README.md and docs/RUNBOOK.md with a Windows automation section.

Create:

```text
docs/WINDOWS_TASK_SCHEDULER.md
```

It should include:

- What automation does and does not do.
- How to run scripts manually.
- How to install the weekly watchlist refresh task.
- How to uninstall the task.
- How to change schedule.
- How to inspect logs.
- How to troubleshoot common issues.
- Clear statement that scheduled tasks run local workflows only.
- Clear statement that no live scraping/network access is implemented.

Add design decision note:

```text
docs/decisions/012-windows-task-scheduler-automation.md
```

Explain:

- Why Task Scheduler is added before live retrieval.
- Why scheduled tasks run only local workflows.
- Why logs are written under logs/scheduled.
- Why weekly watchlist refresh is the default.
- Why dashboard is still manually launched.

## 9. Tests

Add or update tests for:

- automation helper path detection
- virtualenv detection logic
- task command generation
- automation-status data gathering
- expected script files exist
- script content contains expected command names
- log directory handling
- no live network call behavior
- existing MVP 1-12 tests still pass

Do not attempt to actually register Windows Scheduled Tasks in pytest. Test script generation/content and helper functions only.

All tests must pass.

## 10. Code standards

- Python 3.11+
- PEP8 compliant.
- Type hints required.
- Docstrings required for all functions.
- Remove unused imports.
- Keep modules small and readable.
- PowerShell scripts should be readable and commented.
- Batch scripts should be simple and robust.
- No live scraping.
- No network calls.
- No Playwright/Selenium/browser automation.
- No bypassing bot protections.
- Preserve source URLs and timestamps for auditability.
- Avoid inaccurate Claude co-authorship metadata.
- Use neutral language.
- Do not make purchase recommendations.

Quality gates:

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works for fresh database.
- Existing candidate review workflow still works.
- Existing Redfin workflows still work.
- Existing Effective DOM v1/v2 workflows still work.
- Existing cross-site workflows still work.
- Existing county workflows still work.
- Existing watchlist monitoring workflows still work.
- Existing end-to-end workflows still work.
- Existing dashboard/report viewer still works.
- Automation helper tests pass.
- Script files exist and contain expected commands.
- No scheduled task registration is attempted by pytest.
- No live scraping or network calls implemented.
- Changes committed and pushed to origin/main.

Completion report required:

When finished, provide:

1. Summary of what you implemented.
2. Files created or modified.
3. Exact commands run.
4. Final test results with full pytest summary showing 100% pass.
5. Any dependency changes.
6. Any assumptions made.
7. Any blockers or risks remaining.
8. How to manually run the watchlist refresh script.
9. How to install the weekly Scheduled Task.
10. How to uninstall the Scheduled Task.
11. Example automation-status output.
12. Log file path example.
13. Tests added for automation helpers/scripts.
14. Confirmation that pytest does not register real Windows tasks.
15. Confirmation that no live network calls, scraping, Playwright, Selenium, or browser automation were added.
16. Recommended next implementation step.
17. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 13 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
