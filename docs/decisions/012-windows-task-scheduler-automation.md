# Decision 012: Windows Task Scheduler Automation

## Status

Accepted

## Context

Market_Sentry has accumulated a comprehensive set of local workflows (initial review, watchlist refresh, dashboard summary, fixture demo) that the user runs manually via CLI commands. To support regular, hands-off monitoring of the Temecula/Murrieta housing market, the user needs a way to schedule these workflows on their Windows 11 machine without requiring manual intervention each time.

## Decision

Add Windows Task Scheduler automation support using batch scripts, PowerShell scripts, and a Python automation helper module. The scheduled tasks run existing local workflows only, operating on SQLite databases, CSV imports, saved HTML fixtures, and generated reports. No live scraping, network calls, or browser automation is introduced.

## Why Task Scheduler Is Added Before Live Retrieval

Task Scheduler automation is added at this stage because:

1. The existing local workflows (watchlist refresh, initial review) are mature and tested through Milestones 1-12.
2. Scheduling local workflows establishes the operational cadence before adding the complexity of live data retrieval.
3. The user can begin regular watchlist monitoring immediately using saved fixtures and manual CSV imports.
4. When live retrieval is added later, the scheduling infrastructure will already be in place.

## Why Scheduled Tasks Run Only Local Workflows

1. Live data retrieval (Redfin, Zillow, county recorders) is not yet implemented and requires separate compliance review.
2. Local-only execution ensures deterministic, predictable behavior suitable for unattended scheduled runs.
3. The user maintains full control over input data through manual fixture saving and CSV preparation.
4. This approach avoids rate-limiting, bot detection, or network reliability issues during scheduled execution.

## Why Logs Are Written Under logs/scheduled

1. Separates scheduled run logs from interactive CLI logs (`logs/marketsentry.log`).
2. Timestamped filenames prevent log overwriting and preserve run history.
3. The `automation-status` CLI command can easily find and display the latest scheduled log.
4. Users can inspect historical runs to verify the system is operating correctly.

## Why Weekly Watchlist Refresh Is the Default

1. The watchlist refresh workflow is the most operationally important recurring task.
2. Weekly frequency matches typical real-estate monitoring cadence for a 12-month purchase horizon.
3. Saturday 9:00 AM provides results before weekend open houses.
4. The user can easily change the schedule via install script parameters.

## Why the Dashboard Is Still Manually Launched

1. The Streamlit dashboard is an interactive browser application, not a batch process.
2. It requires a running web server and an open browser session.
3. The `dashboard-summary` CLI command can be scheduled for text-based summaries.
4. The full dashboard is best launched on-demand when the user wants to review data.

## Consequences

- Users can set up automated weekly monitoring with a single PowerShell command.
- Log files accumulate over time; users should periodically clean old logs.
- The scheduling infrastructure is ready for live retrieval workflows when they are implemented.
- No additional dependencies are required; Windows Task Scheduler is built into Windows.
