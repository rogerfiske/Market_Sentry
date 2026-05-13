# Claude Code Prompt 042 - Portfolio Review Pack Trend Visualization and Aggregate Trend Scoring

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: 647c9e7 (Milestone 41 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Review the current codebase through commit 647c9e7.
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

Milestone 42 should add portfolio review pack trend visualization and aggregate trend scoring from sequential portfolio review pack CSV exports.

This milestone must not add live retrieval, broaden scraping, change the Quiet Score gatekeeper, or automatically apply candidate/watchlist/alert actions.

The goal is to analyze multiple portfolio review packs over time:

- portfolio-level trend series
- per-property trend series
- aggregate review burden score over time
- count of properties by priority label over time
- count of properties by lifecycle health label over time
- open alert and high/critical alert trend over time
- Effective DOM v2 and Churn Index trend highlights
- cross-site confidence trend highlights
- static dashboard-ready CSV/Markdown outputs

This is a read-only/reporting milestone. It must not change candidate decisions, watchlist status, alert status, Redfin source-of-truth fields, or retrieval behavior. It must not infer seller intent. It must not make purchase recommendations.

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
11. Portfolio trends are offline/local reporting only and must not mutate candidate/watchlist/alert state.

## Implement

### 1. Portfolio trend module

Create:

```text
src/marketsentry/portfolio_review_trends.py
```

Required models:

- PortfolioReviewTrendPoint
- PortfolioReviewPropertyTrendPoint
- PortfolioReviewTrendSummary
- PortfolioReviewTrendReportRow
- PortfolioReviewTrendRunResult

Required functions:

- discover_portfolio_review_pack_exports(...)
- load_portfolio_review_pack_series(...)
- build_portfolio_trend_series(...)
- build_property_trend_series(...)
- calculate_portfolio_trend_score(...)
- summarize_portfolio_review_trends(...)
- export_portfolio_review_trend_report(...)

## 2. Inputs

Use existing Milestone 40 CSV exports:

```text
data/exports/portfolio_review_pack_*.csv
```

Behavior:

- Discover all matching pack CSV files.
- Parse timestamp from filename when possible.
- Fall back to file modified time if timestamp unavailable.
- Sort chronologically.
- Handle missing or inconsistent columns gracefully.
- Do not require database writes.
- Do not mutate any database state.

## 3. Portfolio-level trend series

For each pack timestamp, compute:

- pack_file
- captured_at
- property_count
- immediate_review_count
- high_review_count
- normal_review_count
- monitor_count
- low_current_activity_count
- quiet_fail_count
- quiet_missing_count
- lifecycle_attention_required_count
- lifecycle_needs_review_count
- open_alert_total
- high_critical_alert_total
- avg_lifecycle_health_score
- avg_cross_site_confidence
- avg_recent_churn_index
- avg_effective_dom_v2
- high_churn_count
- high_effective_dom_delta_count
- aggregate_review_burden_score
- aggregate_review_status_label

Aggregate review burden score is a neutral operational score, not a purchase score.

Suggested score direction:

- higher = more review burden
- 0 = no visible review burden
- cap at 100

Suggested labels:

- low_burden
- moderate_burden
- elevated_burden
- high_burden

## 4. Per-property trend series

For each property across packs, compute:

- property_id
- candidate_id
- address
- first_seen_at
- latest_seen_at
- times_seen
- latest_priority_label
- priority_label_changes
- latest_lifecycle_health_label
- lifecycle_health_label_changes
- latest_lifecycle_health_score
- lifecycle_health_score_delta_first_to_latest
- latest_open_alert_count
- open_alert_delta_first_to_latest
- latest_effective_dom_v2
- effective_dom_v2_delta_first_to_latest
- latest_recent_churn_index
- churn_index_delta_first_to_latest
- latest_cross_site_confidence
- cross_site_confidence_delta_first_to_latest
- trend_direction
- trend_summary
- recommended_review_action

Trend directions:

- improved
- degraded
- stable
- new
- insufficient_data

Use neutral wording.

## 5. Reports

Export CSV and Markdown:

```text
data/exports/portfolio_review_trends_YYYYMMDD_HHMMSS.csv
data/exports/portfolio_review_trends_YYYYMMDD_HHMMSS.md
```

CSV can include both portfolio-level and property-level rows using a `row_type` column:

- portfolio_summary
- property_trend

Required CSV columns:

- row_type
- captured_at
- pack_file
- property_id
- candidate_id
- address
- metric_name
- metric_value
- trend_direction
- trend_summary
- recommended_review_action

Markdown should include:

- source files analyzed
- portfolio trend summary
- aggregate burden over time
- priority count trend
- lifecycle health trend
- alert burden trend
- top property trend changes
- local next actions
- note: local analytical review aid only

## 6. Optional chart outputs

If straightforward, generate simple static PNG charts using matplotlib only if matplotlib is already an existing dependency. If matplotlib is not already a dependency, do not add it. Static charts are optional.

## 7. CLI commands

Add:

```text
marketsentry portfolio-review-trends
marketsentry export-portfolio-review-trends
```

### portfolio-review-trends

Options:

- --exports-dir optional
- --limit optional default 10

Output:

- number of pack files analyzed
- time range
- latest aggregate burden score/label
- burden trend direction
- top property trend changes
- no mutations

### export-portfolio-review-trends

Options:

- --exports-dir optional
- --output-dir optional
- --format csv/md/both optional default both

Output:

- report path(s)
- source file count
- portfolio trend points
- property trend rows

## 8. Dashboard integration

Add **Portfolio Review Trends** subsection.

Show:

- number of portfolio packs found
- date range
- latest aggregate burden score/label
- portfolio trend table
- property trend table
- latest trend report link

Dashboard remains read-only.

## 9. Scheduled script update

Update existing:

```text
scripts/run_portfolio_review_pack_report.bat
```

So it may run:

- export-portfolio-review-pack --format both
- export-portfolio-review-comparison --format both
- export-portfolio-review-trends --format both

Script must still:

- not run live retrieval
- not use --force-live
- not run mutation/import commands
- write logs to logs/scheduled/

Tests must verify scheduled script does not contain live retrieval or mutation commands.

## 10. Tests

Add or update tests for:

- discover portfolio review pack exports
- parse timestamps from filenames
- fallback to modified time
- load pack series
- handle missing columns gracefully
- build portfolio trend series
- aggregate review burden score low
- aggregate review burden score high
- property trend series with one pack
- property trend series across multiple packs
- priority label change count
- lifecycle health label change count
- open alert delta
- Effective DOM v2 delta
- Churn Index delta
- cross-site confidence delta
- property trend direction improved
- property trend direction degraded
- property trend direction stable
- trend CSV export
- trend Markdown export
- CLI portfolio-review-trends
- CLI export-portfolio-review-trends
- dashboard trend data loads
- scheduled script safety
- no candidate/watchlist/alert mutation
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-41 tests still pass

## 11. Documentation

Update README.md and docs/RUNBOOK.md with a "Portfolio Review Trends" section.

Update docs/WINDOWS_TASK_SCHEDULER.md with updated portfolio review pack scheduled script behavior.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with a short section on using trends for offline review.

Create:

```text
docs/decisions/041-portfolio-review-trends.md
```

Explain:

- why trends follow review pack comparison
- why trends use exported CSVs as a stable interface
- why aggregate burden is operational, not a property desirability score
- why this is read-only
- why scheduled script is local/report-only
- why candidate/watchlist/alert state is not automatically changed
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
- preserve source file paths and timestamps for auditability
- use neutral language
- do not make purchase recommendations
- do not add walkability parsing or fields

## Quality gates

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- Existing portfolio review pack and comparison exports work.
- Portfolio trend report exports Markdown/CSV.
- Dashboard portfolio trends section loads.
- Scheduled portfolio review script remains safe.
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
8. Example portfolio-review-trends output.
9. Example trend report paths and row counts.
10. Example aggregate burden trend.
11. Example property-level trend change.
12. Dashboard Portfolio Review Trends section added.
13. Scheduled script update added.
14. Confirmation that trends are read-only and do not mutate candidate/watchlist/alert state.
15. Confirmation that trends do not overwrite Redfin source-of-truth fields.
16. Confirmation that Quiet Score gatekeeper remains unchanged.
17. Confirmation that walkability fields were not added.
18. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
19. Confirmation that tests perform no real network calls.
20. Recommended next implementation step.
21. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 42 complete until all tests pass.
