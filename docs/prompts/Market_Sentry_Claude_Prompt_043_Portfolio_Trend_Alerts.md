# Claude Code Prompt 043 - Portfolio Trend Threshold Alerts and Local Notification Digest

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: ed0149e (Milestone 42 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Review the current codebase through commit ed0149e.
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

Milestone 43 should add portfolio trend threshold alerts and a local notification-style digest.

This milestone must not add live retrieval, broaden scraping, change the Quiet Score gatekeeper, or automatically apply candidate/watchlist/alert actions.

The goal is to convert portfolio trend analysis into local, read-only operational flags:

- aggregate review burden threshold alerts
- aggregate burden increase alerts
- degraded property trend alerts
- rising immediate/high review backlog alerts
- rising high/critical alert burden alerts
- rising lifecycle attention_required/needs_review burden alerts
- worsening cross-site confidence trend alerts
- high churn trend alerts
- local notification-style Markdown digest
- dashboard visibility

This is a read-only/reporting milestone. It must not change candidate decisions, watchlist status, alert status, Redfin source-of-truth fields, or retrieval behavior. It must not infer seller intent. It must not make purchase recommendations. It should not send email, SMS, webhook, or other external notifications in this milestone.

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
11. Trend threshold alerts are local review prompts only and must not mutate candidate/watchlist/alert state.
12. No outbound notifications should be sent in this milestone.

## Implement

### 1. Portfolio trend alert module

Create:

```text
src/marketsentry/portfolio_trend_alerts.py
```

Required models:

- PortfolioTrendAlert
- PortfolioTrendAlertRule
- PortfolioTrendAlertSummary
- PortfolioTrendAlertDigest
- PortfolioTrendAlertRunResult

Required functions:

- get_default_portfolio_trend_alert_rules(...)
- evaluate_portfolio_trend_alerts(...)
- evaluate_aggregate_burden_alerts(...)
- evaluate_property_trend_alerts(...)
- summarize_portfolio_trend_alerts(...)
- export_portfolio_trend_alert_digest(...)

## 2. Alert inputs

Use outputs from Milestone 42 trend analysis:

- discovered portfolio review pack exports
- portfolio trend series
- property trend series
- aggregate review burden score/label
- property trend direction
- alert count deltas
- lifecycle health deltas
- cross-site confidence deltas
- churn deltas

Do not require database writes.

Do not mutate any database state.

## 3. Default local alert rules

Suggested default rules:

### aggregate burden

- aggregate_review_burden_score >= 60 => warning/high depending threshold
- aggregate_review_burden_score >= 80 => high
- aggregate_review_burden_score increased by >= 15 since previous pack => warning
- aggregate_review_status_label changed to elevated_burden or high_burden => warning/high

### property degradation

- property trend_direction = degraded => warning
- lifecycle health score decreased by >= 15 => warning
- lifecycle health label changed into needs_review or attention_required => high
- open alert count increased by >= 2 => warning
- high/critical alert count increased by >= 1 if available => high
- cross-site confidence decreased by >= 15 => warning
- Churn Index increased by >= 1.5 => info/warning
- Effective DOM v2 increased by >= 30 days => info/warning

### backlog

- immediate_review_count increased => warning
- high_review_count increased by >= 2 => warning
- no pack trend data available => info

Use neutral severity labels:

- info
- warning
- high

Avoid "critical" unless there is already an established critical severity convention in the codebase and tests.

## 4. Local notification-style digest

Export Markdown and CSV:

```text
data/exports/portfolio_trend_alert_digest_YYYYMMDD_HHMMSS.md
data/exports/portfolio_trend_alert_digest_YYYYMMDD_HHMMSS.csv
```

Markdown structure:

- title and timestamp
- safety note: local analytical review aid, not purchase recommendation
- alert summary by severity
- aggregate portfolio trend alerts
- property-level trend alerts
- recommended local review actions
- source pack files analyzed
- no outbound notification sent

CSV required columns:

- alert_id or deterministic key
- alert_scope: portfolio/property
- property_id
- candidate_id
- address
- severity
- alert_type
- message
- metric_name
- previous_value
- current_value
- delta_value
- recommended_local_action
- source_pack_file
- generated_at

## 5. CLI commands

Add:

```text
marketsentry portfolio-trend-alerts
marketsentry export-portfolio-trend-alert-digest
```

### portfolio-trend-alerts

Options:

- --exports-dir optional
- --limit optional default 20

Output:

- pack files analyzed
- alert counts by severity
- top alerts
- recommended local actions
- no mutations
- no outbound notifications

### export-portfolio-trend-alert-digest

Options:

- --exports-dir optional
- --output-dir optional
- --format csv/md/both optional default both

Output:

- report path(s)
- alert count
- severity counts
- no outbound notification sent

## 6. Dashboard integration

Add **Portfolio Trend Alerts** subsection.

Show:

- alert counts by severity
- top aggregate alerts
- top property alerts
- latest alert digest link
- source pack count/date range if available

Dashboard remains read-only.

## 7. Scheduled script update

Update existing:

```text
scripts/run_portfolio_review_pack_report.bat
```

So it may run:

- export-portfolio-review-pack --format both
- export-portfolio-review-comparison --format both
- export-portfolio-review-trends --format both
- export-portfolio-trend-alert-digest --format both

Script must still:

- not run live retrieval
- not use --force-live
- not run mutation/import commands
- not send outbound notifications
- write logs to logs/scheduled/

Tests must verify scheduled script does not contain live retrieval, mutation, or outbound notification commands.

## 8. Tests

Add or update tests for:

- default alert rules load
- no pack data produces info alert
- aggregate burden high threshold alert
- aggregate burden increase alert
- burden label worsening alert
- degraded property trend alert
- lifecycle health score drop alert
- lifecycle label attention_required alert
- open alert count increase alert
- cross-site confidence drop alert
- churn increase alert
- Effective DOM v2 increase alert
- summarize alerts by severity
- Markdown digest export
- CSV digest export
- CLI portfolio-trend-alerts
- CLI export-portfolio-trend-alert-digest
- dashboard alert data loads
- scheduled script safety
- no outbound notification behavior
- no candidate/watchlist/alert mutation
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-42 tests still pass

## 9. Documentation

Update README.md and docs/RUNBOOK.md with a "Portfolio Trend Alerts" section.

Update docs/WINDOWS_TASK_SCHEDULER.md with updated portfolio review pack scheduled script behavior.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with a short section on using trend alert digest for offline review.

Create:

```text
docs/decisions/042-portfolio-trend-alerts.md
```

Explain:

- why trend alerts follow portfolio trends
- why alerts are local/report-only
- why no outbound notification is sent
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
- Existing portfolio trend report exports work.
- Portfolio trend alert digest exports Markdown/CSV.
- Dashboard portfolio trend alert section loads.
- Scheduled portfolio review script remains safe.
- No candidate/watchlist/alert status mutations occur.
- No Redfin source-of-truth fields are overwritten.
- Quiet gatekeeper remains unchanged.
- No real network calls are performed in tests.
- No scheduled task invokes live retrieval, mutation commands, or outbound notifications.
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
8. Example portfolio-trend-alerts output.
9. Example alert digest report paths and row counts.
10. Example aggregate burden alert.
11. Example property-level degradation alert.
12. Dashboard Portfolio Trend Alerts section added.
13. Scheduled script update added.
14. Confirmation that trend alerts are read-only and do not mutate candidate/watchlist/alert state.
15. Confirmation that no outbound notifications are sent.
16. Confirmation that trend alerts do not overwrite Redfin source-of-truth fields.
17. Confirmation that Quiet Score gatekeeper remains unchanged.
18. Confirmation that walkability fields were not added.
19. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
20. Confirmation that tests perform no real network calls.
21. Recommended next implementation step.
22. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 43 complete until all tests pass.
