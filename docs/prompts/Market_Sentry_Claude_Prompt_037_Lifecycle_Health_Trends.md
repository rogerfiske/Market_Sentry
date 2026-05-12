# Claude Code Prompt 037 - Lifecycle Health Trend Snapshots and Scheduled Health Reports

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: 0ba187b (Milestone 36 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Review the current codebase through commit 0ba187b.
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

Milestone 37 should add lifecycle health trend snapshots and scheduled local health reports.

This milestone must not add live retrieval, broaden scraping, change the Quiet Score gatekeeper, or automatically apply triage, archive, expiration, or alert status actions.

The goal is to track health-score movement over time:

- per-property lifecycle health score trend
- health label changes
- improvement/degradation detection
- attention_required backlog trend
- needs_review backlog trend
- component-level trend changes
- latest health report and scheduled report visibility
- local scheduled report script that does not mutate alert/watchlist state

This is read-only/reporting except for append-only health snapshot rows. It must not change alert status, watchlist status, Redfin source-of-truth fields, or retrieval behavior. It must not infer seller intent. It must not make purchase recommendations.

## Critical project rules

1. Effective DOM v1 is listing-history-derived exposure without county reset integration.
2. Effective DOM v2 applies county-confirmed ownership transfer as a reset boundary when appropriate.
3. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
4. Churn Index remains reportable even when Effective DOM is reset.
5. Quiet Score is the gatekeeper and must remain unchanged.
6. Target is very high Quiet and very low Vibrancy.
7. Any mention of gas means natural gas supply/service evidence.
8. Walkability-type information is excluded.
9. Use neutral language. Do not infer seller intent.
10. Reports are analytical aids, not purchase recommendations.
11. Lifecycle health trend snapshots are operational metrics only and must not mutate alert/watchlist state.

## Implement

### 1. Health snapshot storage

Add append-only table:

```text
cross_site_lifecycle_health_snapshots
```

Suggested columns:

- health_snapshot_id
- property_id
- candidate_id
- captured_at
- lifecycle_health_score
- lifecycle_health_label
- open_alert_count
- high_or_critical_open_alert_count
- lifecycle_gap_count
- stale_open_alert_count
- needs_reparse_count
- needs_manual_review_count
- alert_burden_label
- repeated_patterns
- oldest_open_alert_age_days
- avg_time_to_resolution_days
- latest_lifecycle_event_at
- component_summary
- recommended_review_action
- notes
- created_at

Indexes:

- property_id
- captured_at

Migrations must be non-destructive and idempotent.

### 2. Health trend module

Create:

```text
src/marketsentry/cross_site_lifecycle_health_trends.py
```

Required models:

- CrossSiteLifecycleHealthSnapshot
- CrossSiteLifecycleHealthTrendChange
- CrossSiteLifecycleHealthTrendReportRow
- CrossSiteLifecycleHealthTrendSummary
- CrossSiteLifecycleHealthSnapshotRunResult

Required functions:

- create_lifecycle_health_snapshots(...)
- get_latest_lifecycle_health_snapshot(...)
- get_previous_lifecycle_health_snapshot(...)
- calculate_lifecycle_health_trend_change(...)
- summarize_lifecycle_health_trends(...)
- export_lifecycle_health_trend_report(...)

### 3. Snapshot behavior

Use Milestone 36 health scores as source.

Behavior:

- Compute current health scores for watched properties.
- Persist one snapshot per property when health data exists.
- Skip same-day/no-change snapshots by default.
- `--force` creates snapshots even without material change.
- Material changes:
  - health score changed by >= 5 points
  - health label changed
  - open alert count changed
  - high/critical alert count changed
  - lifecycle gap count changed
  - needs_reparse/manual_review count changed
  - component_summary changed materially

No alert/watchlist mutation.

### 4. Trend report

Export:

```text
data/exports/cross_site_lifecycle_health_trends_YYYYMMDD_HHMMSS.csv
```

Required columns:

- property_id
- candidate_id
- address
- city
- zip
- current_health_score
- previous_health_score
- health_score_delta
- current_health_label
- previous_health_label
- health_label_changed
- current_open_alert_count
- previous_open_alert_count
- open_alert_delta
- current_high_or_critical_open_alert_count
- previous_high_or_critical_open_alert_count
- high_or_critical_delta
- current_lifecycle_gap_count
- previous_lifecycle_gap_count
- lifecycle_gap_delta
- current_needs_reparse_count
- previous_needs_reparse_count
- needs_reparse_delta
- current_needs_manual_review_count
- previous_needs_manual_review_count
- needs_manual_review_delta
- trend_direction
- trend_summary
- recommended_review_action

Trend direction values:

- improved
- degraded
- stable
- new

Use neutral wording.

### 5. CLI commands

Add:

```text
marketsentry snapshot-cross-site-lifecycle-health
marketsentry export-cross-site-lifecycle-health-trend-report
marketsentry cross-site-lifecycle-health-trend-summary
```

#### snapshot-cross-site-lifecycle-health

Options:

- --db
- --force

Output:

- properties scanned
- snapshots created
- snapshots skipped
- material changes detected
- label counts

#### export-cross-site-lifecycle-health-trend-report

Options:

- --db
- --output-dir

Output:

- report path
- row count
- trend direction counts

#### cross-site-lifecycle-health-trend-summary

Options:

- --db

Output:

- properties with health snapshots
- improved count
- degraded count
- stable count
- new count
- attention_required current count
- needs_review current count
- recommended next actions

### 6. Dashboard integration

Add **Lifecycle Health Trends** subsection to Cross-Site Review dashboard.

Show:

- latest health snapshot counts
- improved/degraded/stable/new counts
- properties with label changes
- lowest current health scores
- trend report table
- latest trend report link

Dashboard remains read-only.

### 7. Scheduled report script

Add local scheduled report script:

```text
scripts/run_lifecycle_health_report.bat
```

Behavior:

- activate local venv if present
- run lifecycle health report export
- run lifecycle health snapshot
- run lifecycle health trend report export
- write logs to logs/scheduled/
- no live retrieval
- no --force-live
- no alert/watchlist mutation commands

Update automation-status or script list if relevant.

Tests must verify scheduled script does not contain live retrieval commands, import/mutation commands, or `--force-live`.

### 8. Tests

Add or update tests for:

- schema migration creates cross_site_lifecycle_health_snapshots
- migration is idempotent
- snapshot creation from health scores
- same-day/no-change skip
- force snapshot creates rows
- score delta material change creates new row
- label change creates new row
- alert count change creates new row
- latest/previous snapshot retrieval
- trend change improved
- trend change degraded
- trend change stable
- trend change new
- trend report export
- trend summary
- CLI snapshot-cross-site-lifecycle-health
- CLI export-cross-site-lifecycle-health-trend-report
- CLI cross-site-lifecycle-health-trend-summary
- dashboard health trends data loads
- scheduled script safety
- no alert/watchlist mutation
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-36 tests still pass

### 9. Documentation

Update README.md and docs/RUNBOOK.md with a "Lifecycle Health Trends" section.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with:

- health snapshot concept
- snapshot command
- trend report command
- trend summary command
- scheduled local health report script
- reminder that health trends are operational/review-only

Update docs/WINDOWS_TASK_SCHEDULER.md with the new scheduled script.

Create:

```text
docs/decisions/036-lifecycle-health-trend-snapshots.md
```

Explain:

- why health trends follow lifecycle health scoring
- why snapshots are append-only
- why same-day/no-change snapshots are skipped
- why scheduled script is local/report-only
- why watchlist state is not automatically changed
- why Quiet Score gatekeeper is unchanged
- why walkability remains excluded

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
- Existing lifecycle health report works.
- Health snapshots work.
- Health trend report exports.
- Dashboard health trends section loads.
- Scheduled health script is safe.
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
9. Example snapshot-cross-site-lifecycle-health output.
10. Example lifecycle health trend report path and row count.
11. Example improved health trend output.
12. Example degraded health trend output.
13. Dashboard lifecycle health trends section added.
14. Scheduled script added.
15. Confirmation that lifecycle health trends do not mutate alert/watchlist state.
16. Confirmation that lifecycle health trends do not overwrite Redfin source-of-truth fields.
17. Confirmation that Quiet Score gatekeeper remains unchanged.
18. Confirmation that walkability fields were not added.
19. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
20. Confirmation that tests perform no real network calls.
21. Recommended next implementation step.
22. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 37 complete until all tests pass.
