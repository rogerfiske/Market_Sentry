# Decision 044: Portfolio Trend Alert History

## Date

2026-05-13

## Status

Accepted

## Context

Milestone 44 established configurable portfolio trend alert rules. Operators needed a way to distinguish persistent vs. transient threshold violations over time, detect recurring alerts, and compare evaluation runs without manually tracking alert outputs.

## Decisions

### Why history follows configurable trend alert rules

Milestone 44 provides the configurable rule evaluation engine. Milestone 45 adds a persistence layer: append-only SQLite tables that store evaluation results and enable cross-run comparison. This layered approach preserves the existing evaluation behavior while adding historical visibility.

### Why history is append-only

Alert history rows are INSERT-only. No UPDATE or DELETE statements are performed on the history tables. This ensures a complete audit trail of every evaluation run and prevents accidental loss of historical data. Append-only design also prevents the history system from inadvertently modifying operational state.

### Why absence from latest run is labeled "not present" rather than resolved

When an alert appears in a previous run but not in the latest run, it is labeled "not present in latest evaluation" rather than "resolved". Absence from the latest evaluation does not confirm resolution; the underlying condition may still exist but not be captured in the current data. Using neutral language avoids implying certainty about the underlying condition.

### Why no outbound notification is sent

Outbound notifications (email, SMS, webhook) are explicitly excluded. The alert history system is designed for local, offline operational review. Future milestones may add optional notification channels, but the current design prioritizes local-first operation without external dependencies.

### Why scheduled script is local/report-only plus append-only history

The `run_portfolio_review_pack_report.bat` script now includes `persist-portfolio-trend-alerts` and `export-portfolio-trend-alert-run-comparison`. These commands write append-only history and export reports but do not perform live retrieval, mutation, or outbound notifications. The script remains safe for unattended scheduled execution.

### Why candidate/watchlist/alert state is not automatically changed

Alert history observes and records threshold violations. Operators use existing triage, archive, and expiration workflows to take actions. Automatic state changes from a history/persistence system would bypass the human-in-the-loop design.

### Why Quiet Score gatekeeper is unchanged

The alert history system does not modify Quiet Score gatekeeper logic, thresholds, or scoring. The quiet gatekeeper threshold remains at 70.0.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. The alert history module does not reference walkability metrics.

## Consequences

- Operators can track alert persistence and recurrence over time.
- New, persistent, disappeared, worsened, and improved alerts are identified between runs.
- History reports show first-seen/latest-seen dates and occurrence counts.
- Dashboard shows latest run summary, comparison counts, and persistent high alerts.
- Scheduled script persists alerts and exports comparison reports automatically.
- No outbound notifications are sent.
- No candidates, watchlist entries, or alert statuses are modified.
- All existing alert, trend, review pack, comparison, digest, triage, archive, expiration, lifecycle, health, and configurable rule workflows continue unchanged.
