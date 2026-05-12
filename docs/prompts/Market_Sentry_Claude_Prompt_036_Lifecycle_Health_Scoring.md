# Claude Code Prompt 036 - Property-Level Lifecycle Health Scoring

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: 39ddaba (Milestone 35 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Review the current codebase through commit 39ddaba.
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

Milestone 36 should add property-level lifecycle health scoring.

This milestone must not add live retrieval, broaden scraping, change the Quiet Score gatekeeper, or automatically apply triage, archive, expiration, or alert status actions.

The goal is to translate lifecycle/alert metrics into a read-only operator-facing health score for each watched property:

- alert lifecycle burden
- unresolved lifecycle gaps
- stale open alerts
- time-to-resolution health
- alert throughput/aging context
- needs_reparse/manual_review backlog
- high/critical unresolved alert presence
- recurring repeated patterns
- no_archive and archived history context

This is a read-only/reporting milestone. It must not change alert status, watchlist status, Redfin source-of-truth fields, or retrieval behavior. It must not infer seller intent. It must not make purchase recommendations.

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
11. Lifecycle health score is an alert-management/operator-health metric only.

## Implement

### 1. Lifecycle health scoring module

Create:

```text
src/marketsentry/cross_site_alert_lifecycle_health.py
```

Required models:

- CrossSiteLifecycleHealthScore
- CrossSiteLifecycleHealthComponent
- CrossSiteLifecycleHealthReportRow
- CrossSiteLifecycleHealthSummary
- CrossSiteLifecycleHealthRunResult

Required functions:

- calculate_lifecycle_health_score_for_property(...)
- calculate_lifecycle_health_scores(...)
- classify_lifecycle_health_label(...)
- build_lifecycle_health_components(...)
- summarize_lifecycle_health_scores(...)
- export_lifecycle_health_report(...)

### 2. Health score behavior

Create a 0-100 score where higher is better operational lifecycle health.

Initial scoring guidance:

- Start at 100.
- Subtract for open high/critical alerts.
- Subtract for lifecycle gaps.
- Subtract for stale open alerts.
- Subtract for unresolved needs_reparse.
- Subtract for unresolved needs_manual_review.
- Subtract for high alert burden label.
- Subtract for repeated unresolved patterns.
- Subtract mildly for old acknowledged alerts.
- Add or preserve score for mostly resolved/archived history.

Suggested health labels:

- excellent
- good
- watch
- needs_review
- attention_required

Suggested thresholds:

- 90-100: excellent
- 75-89: good
- 60-74: watch
- 40-59: needs_review
- 0-39: attention_required

Use neutral wording.

### 3. Component breakdown

Each score should include component rows:

- component_name
- component_score_delta
- severity
- explanation
- supporting_count

Components may include:

- open_high_critical_alerts
- lifecycle_gaps
- stale_open_alerts
- needs_reparse_backlog
- needs_manual_review_backlog
- repeated_patterns
- old_acknowledged_alerts
- resolved_archive_candidates
- archived_history

### 4. Report export

Export report:

```text
data/exports/cross_site_lifecycle_health_YYYYMMDD_HHMMSS.csv
```

Required columns:

- property_id
- candidate_id
- address
- city
- zip
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

Add optional Markdown report if straightforward.

### 5. CLI commands

Add:

```text
marketsentry export-cross-site-lifecycle-health-report
marketsentry cross-site-lifecycle-health-summary
```

#### export-cross-site-lifecycle-health-report

Options:

- --db
- --output-dir
- --format csv/md/both optional default csv

Output:

- report path(s)
- row count
- label counts

#### cross-site-lifecycle-health-summary

Options:

- --db
- --property-id optional

Output:

- properties scored
- label counts
- attention_required count
- needs_review count
- top properties by lowest health score
- recommended next actions

### 6. Dashboard integration

Add **Lifecycle Health** subsection to Cross-Site Review dashboard.

Show:

- health label counts
- lowest health-score properties
- component summary
- latest health report if available
- filters by health label

Dashboard remains read-only.

### 7. Watchlist monitoring integration

Where practical, include read-only lifecycle health fields in dashboard/report outputs:

- cross_site_lifecycle_health_score
- cross_site_lifecycle_health_label
- cross_site_lifecycle_health_action

Do not change watchlist state automatically.

### 8. Tests

Add or update tests for:

- score with no alerts = excellent or good
- score with open high/critical alerts decreases
- score with lifecycle gaps decreases
- score with stale open alerts decreases
- score with needs_reparse decreases
- score with needs_manual_review decreases
- score with repeated patterns decreases
- score with mostly resolved/archived history remains high
- health label thresholds
- component breakdown
- summary label counts
- CSV report export
- Markdown report export if implemented
- CLI lifecycle health summary
- CLI lifecycle health report export
- dashboard lifecycle health data loads
- no alert/watchlist mutation
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-35 tests still pass

### 9. Documentation

Update README.md and docs/RUNBOOK.md with a "Lifecycle Health Scoring" section.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with:

- lifecycle health score concept
- health labels
- score components
- summary command
- report export command
- reminder that health score is operational/review-only

Create:

```text
docs/decisions/035-lifecycle-health-scoring.md
```

Explain:

- why health scoring follows lifecycle trends
- why score is read-only
- why score is operator-health and not property desirability
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
- Existing lifecycle audit works.
- Existing lifecycle trend snapshots work.
- Lifecycle health score works.
- Lifecycle health report exports.
- Dashboard lifecycle health section loads.
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
8. Example cross-site-lifecycle-health-summary output.
9. Example lifecycle health report path and row count.
10. Example excellent/good property health output.
11. Example attention_required property health output.
12. Dashboard lifecycle health section added.
13. Confirmation that lifecycle health is read-only and does not mutate alert/watchlist state.
14. Confirmation that lifecycle health does not overwrite Redfin source-of-truth fields.
15. Confirmation that Quiet Score gatekeeper remains unchanged.
16. Confirmation that walkability fields were not added.
17. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
18. Confirmation that tests perform no real network calls.
19. Recommended next implementation step.
20. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 36 complete until all tests pass.
