# Claude Code Prompt 035 - Alert Lifecycle Trend Snapshots and Throughput Metrics

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: 43794a4 (Milestone 34 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Review the current codebase through commit 43794a4.
8. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
9. Keep PRD.md and Architecture.md in the project root.
10. Use src/marketsentry/ as the Python package path.
11. Do not move PRD.md or Architecture.md into docs/.
12. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
13. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
14. Do not implement new Redfin live retrieval behavior in this milestone.
15. Do not run any live network calls in tests.
16. Do not make scheduled tasks run live retrieval by default.
17. Do not add walkability parsing or walkability fields.
18. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

## PM direction

Milestone 35 should add alert lifecycle trend snapshots and throughput metrics.

This milestone must not add live retrieval, broaden scraping, change the Quiet Score gatekeeper, or automatically apply triage, archive, expiration, or alert status actions.

The goal is to measure alert-management efficiency over time:

- total alerts trend
- open alert trend
- lifecycle gap trend
- time-to-first-triage
- time-to-resolution
- time-to-archive
- triage throughput
- resolution throughput
- archive throughput
- stale alert burden trend
- needs_reparse/manual_review backlog trend
- property-level lifecycle health trend

This is a read-only/reporting milestone except for writing append-only lifecycle metric snapshots. It must not change watchlist status automatically, must not overwrite Redfin source-of-truth fields, and must not infer seller intent.

## Critical project rules

1. Effective DOM v1 is listing-history-derived exposure without county reset integration.
2. Effective DOM v2 applies county-confirmed ownership transfer as a reset boundary when appropriate.
3. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
4. Churn Index remains reportable even when Effective DOM is reset.
5. Quiet Score is the gatekeeper.
6. Target is very high Quiet and very low Vibrancy.
7. Any mention of gas means natural gas supply/service evidence.
8. Walkability-type information is excluded.
9. Use neutral language. Do not infer seller intent.
10. Reports are analytical aids, not purchase recommendations.
11. Lifecycle trend snapshots are operational metrics only and must not mutate alert/watchlist state.

## Implement

### 1. Snapshot storage

Add append-only table:

```text
cross_site_alert_lifecycle_snapshots
```

Suggested columns:

- lifecycle_snapshot_id
- captured_at
- total_alerts
- open_alerts
- acknowledged_alerts
- resolved_alerts
- archived_alerts
- high_or_critical_open_alerts
- lifecycle_gap_count
- stale_open_alert_count
- needs_reparse_count
- needs_manual_review_count
- no_archive_count
- total_lifecycle_events
- triage_actions_count
- archive_actions_count
- expiration_actions_count
- avg_time_to_first_triage_days
- median_time_to_first_triage_days
- avg_time_to_resolution_days
- median_time_to_resolution_days
- avg_time_to_archive_days
- median_time_to_archive_days
- triage_throughput_7d
- resolution_throughput_7d
- archive_throughput_7d
- active_property_count
- property_count_with_open_alerts
- property_count_with_lifecycle_gaps
- notes
- created_at

Migrations must be non-destructive and idempotent.

### 2. Lifecycle metrics module

Create:

```text
src/marketsentry/cross_site_alert_lifecycle_metrics.py
```

Required models:

- CrossSiteAlertLifecycleSnapshot
- CrossSiteAlertThroughputMetrics
- CrossSiteAlertTimeToActionMetrics
- CrossSiteAlertLifecycleTrendChange
- CrossSiteAlertLifecycleTrendReportRow
- CrossSiteAlertLifecycleSnapshotRunResult

Required functions:

- calculate_lifecycle_snapshot_metrics(...)
- create_alert_lifecycle_snapshot(...)
- get_latest_lifecycle_snapshot(...)
- get_previous_lifecycle_snapshot(...)
- calculate_lifecycle_trend_change(...)
- calculate_time_to_action_metrics(...)
- calculate_throughput_metrics(...)
- export_alert_lifecycle_trend_report(...)

### 3. Time-to-action metrics

Calculate:

- alert_created to first acknowledged/resolved/archived/reopened action
- alert_created to first resolved action
- alert_created to first archived action

Return average days, median days, count used, and skipped count. Return None/0 safely when no qualifying events exist.

### 4. Throughput metrics

Calculate recent counts:

- triage actions in last 7 days
- resolution actions in last 7 days
- archive actions in last 7 days

Optional: include 30-day counts if straightforward.

### 5. Snapshot creation behavior

Add CLI command:

```text
marketsentry snapshot-cross-site-alert-lifecycle
```

Options:

- --db
- --force

Behavior:

- create append-only snapshot from current lifecycle metrics
- skip same-day duplicate if no material change unless --force
- material changes include alert count, open count, gap count, stale backlog count, throughput, or material average time-to-resolution change
- no alert mutations

### 6. Trend report

Add report export:

```text
data/exports/cross_site_alert_lifecycle_trends_YYYYMMDD_HHMMSS.csv
```

Required columns:

- current_snapshot_id
- current_captured_at
- previous_snapshot_id
- previous_captured_at
- total_alerts_current
- total_alerts_previous
- total_alerts_delta
- open_alerts_current
- open_alerts_previous
- open_alerts_delta
- lifecycle_gap_count_current
- lifecycle_gap_count_previous
- lifecycle_gap_count_delta
- stale_open_alert_count_current
- stale_open_alert_count_previous
- stale_open_alert_count_delta
- avg_time_to_resolution_current
- avg_time_to_resolution_previous
- avg_time_to_resolution_delta
- triage_throughput_7d_current
- triage_throughput_7d_previous
- triage_throughput_7d_delta
- resolution_throughput_7d_current
- resolution_throughput_7d_previous
- resolution_throughput_7d_delta
- archive_throughput_7d_current
- archive_throughput_7d_previous
- archive_throughput_7d_delta
- trend_direction
- trend_summary
- recommended_review_action

Add CLI command:

```text
marketsentry export-cross-site-alert-lifecycle-trend-report
```

Options:

- --db
- --output-dir

### 7. Dashboard integration

Add Lifecycle Trends and Throughput subsection to Cross-Site Review dashboard.

Show:

- latest snapshot metrics
- previous snapshot comparison
- open alert trend
- lifecycle gap trend
- stale open alert trend
- time-to-resolution metric
- throughput metrics
- latest trend report table if available

Dashboard remains read-only.

### 8. Scheduled report integration

Optionally add:

```text
scripts/run_alert_lifecycle_trend_report.bat
```

If added, it must run snapshot/report commands only, not mutate alert status, not run live retrieval, not use --force-live, and write logs to logs/scheduled/.

Tests must verify scheduled scripts do not contain live retrieval or mutation commands.

### 9. Tests

Add or update tests for:

- schema migration creates cross_site_alert_lifecycle_snapshots
- migration is idempotent
- calculate metrics with no alerts
- calculate metrics with open/resolved/archived alerts
- time-to-first-triage metrics
- time-to-resolution metrics
- time-to-archive metrics
- throughput 7-day metrics
- snapshot creation
- same-day no-change skip
- force snapshot creates new row
- material change creates new row
- latest/previous snapshot retrieval
- trend change calculation
- trend report export
- CLI snapshot-cross-site-alert-lifecycle
- CLI export-cross-site-alert-lifecycle-trend-report
- dashboard lifecycle trends data loads
- scheduled script safety if added
- no alert/watchlist mutation
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-34 tests still pass

### 10. Documentation

Update README.md and docs/RUNBOOK.md with an Alert Lifecycle Trends and Throughput section.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with:

- lifecycle trend snapshot concept
- snapshot command
- trend report command
- time-to-triage/time-to-resolution/time-to-archive definitions
- throughput metrics
- reminder that this is read-only except append-only metric snapshots

Update docs/WINDOWS_TASK_SCHEDULER.md only if scheduled script is added.

Create:

```text
docs/decisions/034-alert-lifecycle-trend-snapshots.md
```

Explain why lifecycle trends follow lifecycle audit, why snapshots are append-only, why same-day/no-change snapshots are skipped, why metrics are operational only, why watchlist state is not automatically changed, why Quiet Score gatekeeper is unchanged, and why walkability remains excluded.

## Code standards

- Python 3.11+
- PEP8 compliant
- type hints required
- docstrings required for all functions
- remove unused imports
- no browser automation
- no Playwright/Selenium
- no bypassing CAPTCHAs, paywalls, login walls, anti-bot protections, or technical access controls
- no network calls in tests
- preserve source URLs and timestamps for auditability
- use neutral language
- do not make purchase recommendations
- do not add walkability parsing or fields

## Quality gates

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works for fresh database.
- Existing lifecycle audit works.
- Lifecycle metric snapshot works.
- Lifecycle trend report exports.
- Dashboard lifecycle trend section loads.
- No alert/watchlist status mutations occur.
- No Redfin source-of-truth fields are overwritten.
- Quiet gatekeeper remains unchanged.
- No real network calls are performed in tests.
- No scheduled task invokes live retrieval or alert mutation.
- Changes committed and pushed to origin/main.

## Completion report required

When finished, provide:

1. Summary of what you implemented.
2. Files created or modified.
3. Exact commands run.
4. Final test results with full pytest summary showing 100% pass.
5. Any dependency changes.
6. Any assumptions made.
7. Any blockers or risks remaining.
8. Schema changes or migration details.
9. Example snapshot-cross-site-alert-lifecycle output.
10. Example lifecycle trend report path and row count.
11. Example time-to-resolution metrics.
12. Example throughput metrics.
13. Dashboard lifecycle trends section added.
14. Scheduled script added or explicitly not added.
15. Confirmation that lifecycle trends do not mutate alert/watchlist state.
16. Confirmation that lifecycle trends do not overwrite Redfin source-of-truth fields.
17. Confirmation that Quiet Score gatekeeper remains unchanged.
18. Confirmation that walkability fields were not added.
19. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
20. Confirmation that tests perform no real network calls.
21. Recommended next implementation step.
22. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 35 complete until all tests pass.
