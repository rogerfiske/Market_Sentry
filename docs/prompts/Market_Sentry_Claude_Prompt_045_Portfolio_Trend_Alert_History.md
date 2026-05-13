# Claude Code Prompt 045 - Portfolio Trend Alert History and Persistence

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\\Users\\Minis\\CascadeProjects\\Market_Sentry
Current accepted commit: 6ab8276 (Milestone 44 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Read docs/PORTFOLIO_TREND_ALERT_RULES.md.
8. Review the current codebase through commit 6ab8276.
9. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
10. Keep PRD.md and Architecture.md in the project root.
11. Use src/marketsentry/ as the Python package path.
12. Do not move PRD.md or Architecture.md into docs/.
13. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
14. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
15. Do not implement new Redfin live retrieval behavior in this milestone.
16. Do not run any live network calls in tests.
17. Do not make scheduled tasks run live retrieval by default.
18. Do not add walkability parsing or walkability fields.
19. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

## PM direction

Milestone 45 should add portfolio trend alert history and persistence.

This milestone must not add live retrieval, broaden scraping, change the Quiet Score gatekeeper, send outbound notifications, or automatically apply candidate/watchlist/alert actions.

The goal is to distinguish persistent vs. transient portfolio trend threshold violations over time:

- persist local alert evaluation results as append-only history
- summarize recurring alerts by alert type/property/severity/rule
- identify persistent threshold violations
- identify newly appeared alerts
- identify resolved/disappeared alerts compared with prior runs
- identify worsening/improving alert severity patterns
- export history reports and current-vs-previous alert comparison reports
- show dashboard history/recurrence visibility

This is local-only operational history. It may write append-only alert evaluation snapshots/history rows, but it must not change candidate decisions, watchlist status, alert status, Redfin source-of-truth fields, or retrieval behavior. It must not infer seller intent. It must not make purchase recommendations. It must not send email, SMS, webhooks, or other outbound notifications.

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
11. Portfolio trend alert history must not mutate candidate/watchlist/alert state.
12. No outbound notifications should be sent in this milestone.

## Implement

### 1. Alert history storage

Add append-only tables:

```text
portfolio_trend_alert_runs
portfolio_trend_alert_history
```

Suggested `portfolio_trend_alert_runs` columns:

- run_id INTEGER PRIMARY KEY AUTOINCREMENT
- run_key TEXT UNIQUE
- evaluated_at TIMESTAMP
- rule_config_path TEXT
- rule_config_mode TEXT
- rules_evaluated_count INTEGER
- alerts_generated_count INTEGER
- high_count INTEGER
- warning_count INTEGER
- info_count INTEGER
- portfolio_alert_count INTEGER
- property_alert_count INTEGER
- source_pack_count INTEGER
- source_date_range_start TEXT
- source_date_range_end TEXT
- digest_csv_path TEXT
- digest_md_path TEXT
- notes TEXT
- created_at TIMESTAMP

Suggested `portfolio_trend_alert_history` columns:

- history_id INTEGER PRIMARY KEY AUTOINCREMENT
- run_id INTEGER
- alert_key TEXT
- alert_scope TEXT
- property_id INTEGER
- candidate_id INTEGER
- address TEXT
- severity TEXT
- alert_type TEXT
- rule_id TEXT
- rule_name TEXT
- metric_name TEXT
- previous_value TEXT
- current_value TEXT
- delta_value TEXT
- message TEXT
- recommended_local_action TEXT
- source_pack_file TEXT
- generated_at TIMESTAMP
- created_at TIMESTAMP

Indexes:

- run_id
- alert_key
- property_id
- alert_type
- severity
- generated_at/evaluated_at

Migrations must be non-destructive and idempotent.

### 2. Alert history module

Create:

```text
src/marketsentry/portfolio_trend_alert_history.py
```

Required models:

- PortfolioTrendAlertRunRecord
- PortfolioTrendAlertHistoryRecord
- PortfolioTrendAlertHistorySummary
- PortfolioTrendAlertPersistenceSummary
- PortfolioTrendAlertComparisonRow
- PortfolioTrendAlertHistoryRunResult

Required functions:

- create_portfolio_trend_alert_run(...)
- persist_portfolio_trend_alerts(...)
- get_latest_portfolio_trend_alert_run(...)
- get_previous_portfolio_trend_alert_run(...)
- compare_portfolio_trend_alert_runs(...)
- summarize_portfolio_trend_alert_history(...)
- export_portfolio_trend_alert_history_report(...)
- export_portfolio_trend_alert_comparison_report(...)

## 3. Alert key generation

Create deterministic alert keys so the same logical alert can be compared across runs.

Suggested key fields:

- alert_scope
- property_id if present
- alert_type
- rule_id if present
- metric_name

Use a stable normalized string or SHA-256 hash. Preserve human-readable fields in report rows.

## 4. Persistence behavior

Add CLI command:

```text
marketsentry persist-portfolio-trend-alerts
```

Options:

- --exports-dir optional
- --rule-config optional
- --output-dir optional
- --write-digest optional default true

Behavior:

- evaluate portfolio trend alerts using current M43/M44 logic
- optionally export digest files
- insert one run row
- insert one history row per alert
- no candidate/watchlist/alert mutation
- no outbound notifications

This is append-only operational history.

## 5. Current vs previous run comparison

Compare latest run to previous run:

- new alerts
- persistent alerts
- disappeared/resolved-by-absence alerts
- severity increased
- severity decreased
- metric value worsened
- metric value improved
- property alerts recurring count

Use neutral labels:

- new
- persistent
- disappeared
- worsened
- improved
- unchanged

Do not imply that disappeared alerts were solved unless the evidence is only absence from latest evaluation. Use wording such as "not present in latest evaluation".

Add CLI command:

```text
marketsentry compare-portfolio-trend-alert-runs
```

Options:

- --current-run-id optional
- --previous-run-id optional
- --db
- --limit optional default 20

Output:

- current/previous run IDs
- new/persistent/disappeared counts
- severity increased/decreased counts
- top recurring/persistent alerts
- no mutations

## 6. History summary and reports

Add CLI command:

```text
marketsentry portfolio-trend-alert-history-summary
```

Options:

- --db
- --property-id optional
- --days optional default 30

Output:

- run count
- total alert history rows
- recurring alert count
- most frequent alert types
- properties with repeated alerts
- persistent high alerts
- no outbound notifications

Add export commands:

```text
marketsentry export-portfolio-trend-alert-history-report
marketsentry export-portfolio-trend-alert-run-comparison
```

Options:

- --db
- --output-dir
- --format csv/md/both optional default both

Report files:

```text
data/exports/portfolio_trend_alert_history_YYYYMMDD_HHMMSS.csv
data/exports/portfolio_trend_alert_history_YYYYMMDD_HHMMSS.md
data/exports/portfolio_trend_alert_run_comparison_YYYYMMDD_HHMMSS.csv
data/exports/portfolio_trend_alert_run_comparison_YYYYMMDD_HHMMSS.md
```

History report should include:

- run IDs/dates
- alert key
- alert scope
- property/address
- severity
- alert type
- count seen
- first_seen
- latest_seen
- latest message
- recommended local action

Comparison report should include:

- alert_key
- property_id
- address
- alert_type
- previous_severity
- current_severity
- comparison_status
- previous_value
- current_value
- delta_value
- summary
- recommended_local_action

## 7. Dashboard integration

Add **Portfolio Trend Alert History** subsection.

Show:

- latest run summary
- previous run summary
- new/persistent/disappeared counts
- recurring alert table
- persistent high alert table
- latest history/comparison report links

Dashboard remains read-only.

## 8. Scheduled script update

Update existing:

```text
scripts/run_portfolio_review_pack_report.bat
```

So it may run:

- export-portfolio-review-pack --format both
- export-portfolio-review-comparison --format both
- export-portfolio-review-trends --format both
- export-portfolio-trend-alert-digest --format both
- persist-portfolio-trend-alerts
- export-portfolio-trend-alert-run-comparison --format both

Script must still:

- not run live retrieval
- not use --force-live
- not run mutation/import commands that change candidate/watchlist/alert state
- not send outbound notifications
- write logs to logs/scheduled/

Append-only alert history persistence is allowed.

Tests must verify scheduled script does not contain live retrieval, protected mutation, or outbound notification commands.

## 9. Tests

Add or update tests for:

- schema migration creates run/history tables
- migration is idempotent
- deterministic alert key generation
- persist run with no alerts
- persist run with alerts
- latest/previous run retrieval
- compare first run returns all new or no previous safely
- compare two runs with persistent alert
- compare two runs with new alert
- compare two runs with disappeared alert
- severity increased detection
- severity decreased detection
- history summary recurring alerts
- property-specific history summary
- history CSV export
- history Markdown export
- run comparison CSV export
- run comparison Markdown export
- CLI persist-portfolio-trend-alerts
- CLI compare-portfolio-trend-alert-runs
- CLI portfolio-trend-alert-history-summary
- CLI export history report
- CLI export comparison report
- dashboard history data loads
- scheduled script safety
- no outbound notification behavior
- no candidate/watchlist/alert mutation except append-only portfolio trend alert history tables
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-44 tests still pass

## 10. Documentation

Update README.md and docs/RUNBOOK.md with a "Portfolio Trend Alert History" section.

Update docs/WINDOWS_TASK_SCHEDULER.md with updated portfolio review pack scheduled script behavior.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with a short section on persistent vs transient trend alerts.

Update docs/PORTFOLIO_TREND_ALERT_RULES.md with a note that evaluated alerts can be persisted locally as append-only history.

Create:

```text
docs/decisions/044-portfolio-trend-alert-history.md
```

Explain:

- why history follows configurable trend alert rules
- why history is append-only
- why absence from latest run is labeled "not present" rather than resolved
- why no outbound notification is sent
- why scheduled script is local/report-only plus append-only history
- why candidate/watchlist/alert state is not automatically changed
- why Quiet Score gatekeeper is unchanged
- why walkability remains excluded

## Code standards

- Python 3.11+
- PEP8 compliant
- type hints required
- docstrings required for all functions
- remove unused imports
- use standard library only unless existing dependencies suffice
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
- SQLite init works for fresh database.
- Existing portfolio trend alert digest exports work.
- Configurable rules still work.
- Alert history persistence works.
- Alert run comparison works.
- Dashboard alert history section loads.
- Scheduled portfolio review script remains safe.
- No candidate/watchlist/alert status mutations occur.
- No Redfin source-of-truth fields are overwritten.
- Quiet gatekeeper remains unchanged.
- No real network calls are performed in tests.
- No scheduled task invokes live retrieval, protected mutation commands, or outbound notifications.
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
9. Example persist-portfolio-trend-alerts output.
10. Example compare-portfolio-trend-alert-runs output.
11. Example history report paths and row counts.
12. Example persistent alert.
13. Example disappeared/not-present alert.
14. Dashboard Portfolio Trend Alert History section added.
15. Scheduled script update added.
16. Confirmation that alert history is append-only and does not mutate candidate/watchlist/alert state.
17. Confirmation that no outbound notifications are sent.
18. Confirmation that alert history does not overwrite Redfin source-of-truth fields.
19. Confirmation that Quiet Score gatekeeper remains unchanged.
20. Confirmation that walkability fields were not added.
21. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
22. Confirmation that tests perform no real network calls.
23. Recommended next implementation step.
24. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 45 complete until all tests pass.
