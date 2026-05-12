# Claude Code Prompt 039 - Operations Digest Historical Snapshots and Weekly Comparison Reports

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: 0aa661f (Milestone 38 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Review the current codebase through commit 0aa661f.
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

Milestone 39 should add historical snapshots and comparison reports for the Watchlist Operations Digest.

This milestone must not add live retrieval, broaden scraping, change the Quiet Score gatekeeper, or automatically apply triage/archive/expiration/alert status actions.

The goal is to track high-level operations changes over time:

- candidate review backlog trend
- active watchlist count trend
- Effective DOM / churn issue trend
- cross-site confidence/discrepancy trend
- alert burden trend
- lifecycle health trend
- retrieval health trend
- top review priority movement
- next-action backlog trend
- week-over-week or snapshot-over-snapshot comparison

This is a read-only/reporting milestone except for writing append-only digest snapshot rows. It must not change candidate decisions, watchlist status, alert status, Redfin source-of-truth fields, or retrieval behavior. It must not infer seller intent. It must not make purchase recommendations.

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
11. Digest snapshots are operational metrics only and must not mutate candidate/watchlist/alert state.

## Implement

### 1. Digest snapshot storage

Add append-only table:

```text
operations_digest_snapshots
```

Suggested columns:

- digest_snapshot_id
- captured_at
- candidate_count
- pending_user_decision_count
- strong_review_count
- reject_location_noise_count
- watched_property_count
- active_watched_count
- high_priority_watched_count
- gas_evidence_count
- garage_evidence_count
- county_reset_applied_count
- high_churn_count
- high_effective_dom_delta_count
- cross_site_observed_property_count
- low_cross_site_confidence_count
- high_discrepancy_severity_count
- open_alert_count
- high_or_critical_open_alert_count
- stale_open_alert_count
- needs_reparse_count
- needs_manual_review_count
- archive_candidate_count
- lifecycle_attention_required_count
- lifecycle_needs_review_count
- lifecycle_degraded_trend_count
- lifecycle_gap_count
- retrieval_pending_capture_count
- retrieval_health_issue_count
- top_priority_count
- immediate_review_count
- high_review_count
- next_action_count
- digest_score
- digest_status_label
- notes
- created_at

Indexes:

- captured_at

Migrations must be non-destructive and idempotent.

### 2. Digest history module

Create:

```text
src/marketsentry/operations_digest_history.py
```

Required models:

- OperationsDigestSnapshot
- OperationsDigestTrendChange
- OperationsDigestComparisonReportRow
- OperationsDigestHistorySummary
- OperationsDigestSnapshotRunResult

Required functions:

- create_operations_digest_snapshot(...)
- calculate_operations_digest_snapshot_metrics(...)
- get_latest_operations_digest_snapshot(...)
- get_previous_operations_digest_snapshot(...)
- calculate_operations_digest_trend_change(...)
- summarize_operations_digest_history(...)
- export_operations_digest_comparison_report(...)

### 3. Digest score and status label

Create a read-only operational score, 0-100, where higher means fewer local review backlogs.

This score is not property desirability and must not be framed as purchase advice.

Suggested deductions:

- pending candidate decisions
- reject_location_noise count
- high DOM/churn issues
- low cross-site confidence
- high discrepancy severity
- high/critical open alerts
- stale open alerts
- needs_reparse/manual_review
- lifecycle attention_required/needs_review
- lifecycle gaps
- retrieval health issues
- pending capture queue items

Suggested labels:

- clear
- light_review
- active_review
- heavy_review
- backlog_attention

Suggested thresholds:

- 90-100: clear
- 75-89: light_review
- 60-74: active_review
- 40-59: heavy_review
- 0-39: backlog_attention

Use neutral wording.

### 4. Snapshot behavior

Use Milestone 38 digest as source.

Behavior:

- Build current operations digest.
- Persist one aggregate snapshot.
- Skip same-day/no-change snapshot unless --force.
- `--force` creates snapshot even without material change.
- Material changes:
  - candidate backlog changed
  - active watched count changed
  - high/critical alerts changed
  - lifecycle attention_required/needs_review changed
  - digest_score changed by >= 5
  - digest_status_label changed
  - retrieval health issue count changed
  - top_priority_count changed

No candidate/watchlist/alert mutation.

### 5. Comparison report

Export:

```text
data/exports/operations_digest_comparison_YYYYMMDD_HHMMSS.csv
```

Also optionally Markdown:

```text
data/exports/operations_digest_comparison_YYYYMMDD_HHMMSS.md
```

Required columns:

- current_snapshot_id
- current_captured_at
- previous_snapshot_id
- previous_captured_at
- digest_score_current
- digest_score_previous
- digest_score_delta
- digest_status_current
- digest_status_previous
- digest_status_changed
- candidate_count_current
- candidate_count_previous
- candidate_count_delta
- pending_user_decision_current
- pending_user_decision_previous
- pending_user_decision_delta
- active_watched_current
- active_watched_previous
- active_watched_delta
- high_or_critical_open_alerts_current
- high_or_critical_open_alerts_previous
- high_or_critical_open_alerts_delta
- lifecycle_attention_required_current
- lifecycle_attention_required_previous
- lifecycle_attention_required_delta
- lifecycle_needs_review_current
- lifecycle_needs_review_previous
- lifecycle_needs_review_delta
- retrieval_health_issues_current
- retrieval_health_issues_previous
- retrieval_health_issues_delta
- top_priority_count_current
- top_priority_count_previous
- top_priority_count_delta
- trend_direction
- trend_summary
- recommended_review_action

Trend direction values:

- improved
- degraded
- stable
- new

Use neutral wording.

### 6. CLI commands

Add:

```text
marketsentry snapshot-operations-digest
marketsentry export-operations-digest-comparison-report
marketsentry operations-digest-history-summary
```

#### snapshot-operations-digest

Options:

- --db
- --exports-dir optional
- --force

Output:

- snapshot created/skipped
- digest score
- digest status label
- key counts
- material changes detected

#### export-operations-digest-comparison-report

Options:

- --db
- --output-dir
- --format csv/md/both optional default csv

Output:

- report path(s)
- row count
- trend direction

#### operations-digest-history-summary

Options:

- --db

Output:

- snapshot count
- latest digest score/status
- previous digest score/status
- trend direction
- backlog deltas
- recommended next local actions

### 7. Dashboard integration

Add **Operations Digest History** subsection to dashboard.

Show:

- latest digest score/status
- previous digest score/status
- score delta
- trend direction
- candidate backlog delta
- alert burden delta
- lifecycle health delta
- retrieval health delta
- latest comparison report link

Dashboard remains read-only.

### 8. Scheduled script

Update existing:

```text
scripts/run_operations_digest_report.bat
```

So it may run:

- export-operations-digest --format both
- snapshot-operations-digest
- export-operations-digest-comparison-report --format both

Script must still:

- not run live retrieval
- not use --force-live
- not run mutation/import commands
- write logs to logs/scheduled/

Tests must verify scheduled script does not contain live retrieval or mutation commands.

### 9. Tests

Add or update tests for:

- schema migration creates operations_digest_snapshots
- migration is idempotent
- digest snapshot metrics with empty database
- digest snapshot metrics with populated candidate/watchlist/alert data
- digest score label thresholds
- snapshot creation
- same-day/no-change skip
- force snapshot creates row
- material change creates row
- latest/previous snapshot retrieval
- trend change improved
- trend change degraded
- trend change stable
- trend change new
- comparison CSV export
- comparison Markdown export if implemented
- CLI snapshot-operations-digest
- CLI export-operations-digest-comparison-report
- CLI operations-digest-history-summary
- dashboard digest history data loads
- scheduled script safety
- no candidate/watchlist/alert mutation
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-38 tests still pass

### 10. Documentation

Update README.md and docs/RUNBOOK.md with an "Operations Digest History" section.

Update docs/WINDOWS_TASK_SCHEDULER.md with updated digest scheduled script behavior.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with:

- digest snapshot concept
- snapshot command
- comparison report command
- history summary command
- reminder that digest history is operational/review-only

Create:

```text
docs/decisions/038-operations-digest-history.md
```

Explain:

- why digest history follows operations digest
- why snapshots are append-only
- why same-day/no-change snapshots are skipped
- why digest score is operational only and not purchase advice
- why scheduled script is local/report-only
- why watchlist/candidate/alert state is not automatically changed
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
- Existing operations digest works.
- Operations digest snapshot works.
- Operations comparison report exports.
- Dashboard digest history section loads.
- Scheduled digest script remains safe.
- No candidate/watchlist/alert status mutations occur.
- No Redfin source-of-truth fields are overwritten.
- Quiet gatekeeper remains unchanged.
- No real network calls are performed in tests.
- No scheduled task invokes live retrieval or mutation commands.
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
9. Example snapshot-operations-digest output.
10. Example operations digest comparison report path and row count.
11. Example improved digest trend output.
12. Example degraded digest trend output.
13. Dashboard Operations Digest History section added.
14. Scheduled script update added.
15. Confirmation that digest history does not mutate candidate/watchlist/alert state.
16. Confirmation that digest history does not overwrite Redfin source-of-truth fields.
17. Confirmation that Quiet Score gatekeeper remains unchanged.
18. Confirmation that walkability fields were not added.
19. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
20. Confirmation that tests perform no real network calls.
21. Recommended next implementation step.
22. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 39 complete until all tests pass.
