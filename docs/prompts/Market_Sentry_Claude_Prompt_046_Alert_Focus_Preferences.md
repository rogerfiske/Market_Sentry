# Claude Code Prompt 046 - Local Alert Highlight Preferences and Dashboard Focus Views

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: d7756c1 (Milestone 45 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Read docs/PORTFOLIO_TREND_ALERT_RULES.md.
8. Review the current codebase through commit d7756c1.
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

Milestone 46 should add local alert highlight preferences and dashboard focus views.

This milestone must not add live retrieval, broaden scraping, change the Quiet Score gatekeeper, send outbound notifications, or automatically apply candidate/watchlist/alert actions.

The goal is to let the operator configure which local alert categories should be emphasized in reports and dashboard views:

- highlight persistent high alerts
- highlight recurring property alerts
- highlight aggregate burden alerts
- highlight lifecycle health degradation
- highlight cross-site confidence drop
- highlight Churn Index increase
- hide/de-emphasize info-only alerts
- define a local focus profile for dashboard review
- export a focused alert digest
- show focus views in dashboard

This is a local read-only/reporting milestone. It must not change candidate decisions, watchlist status, alert status, Redfin source-of-truth fields, retrieval behavior, or underlying alert evaluation rules. It must not infer seller intent. It must not make purchase recommendations. It must not send email, SMS, webhooks, or other outbound notifications.

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
11. Highlight preferences are local display preferences only and must not mutate candidate/watchlist/alert state.
12. No outbound notifications should be sent in this milestone.

## Implement

### 1. Local highlight preference config

Add support for a local JSON config file:

```text
config/portfolio_alert_highlight_preferences.json
```

Add example template:

```text
config/portfolio_alert_highlight_preferences.example.json
```

Suggested format:

```json
{
  "profile_name": "default_focus",
  "description": "Local display preferences for portfolio trend alert focus views.",
  "include_severities": ["high", "warning"],
  "exclude_severities": ["info"],
  "include_alert_types": [
    "aggregate_burden_high",
    "aggregate_burden_increase",
    "property_degraded",
    "lifecycle_health_drop",
    "cross_site_confidence_drop",
    "churn_increase"
  ],
  "exclude_alert_types": [],
  "minimum_persistence_count": 1,
  "include_persistent_only": false,
  "include_property_alerts": true,
  "include_portfolio_alerts": true,
  "max_items": 25,
  "sort_order": "severity_then_persistence",
  "notes": "Local display preferences only. No notifications are sent."
}
```

Allowed severities:

- info
- warning
- high

Allowed sort orders:

- severity_then_persistence
- persistence_then_severity
- newest_first
- property_then_severity

Validation:

- profile_name required
- include/exclude severity values must be valid
- include/exclude alert type values are strings
- max_items positive integer
- minimum_persistence_count non-negative integer
- no live retrieval / notification / walkability keys accepted
- invalid config fails safely with clear errors

## 2. Highlight preference module

Create:

```text
src/marketsentry/portfolio_alert_focus.py
```

Required models:

- PortfolioAlertHighlightPreferences
- PortfolioAlertFocusItem
- PortfolioAlertFocusSummary
- PortfolioAlertFocusDigest
- PortfolioAlertFocusRunResult

Required functions:

- load_portfolio_alert_highlight_preferences(...)
- validate_portfolio_alert_highlight_preferences(...)
- write_portfolio_alert_highlight_template(...)
- build_portfolio_alert_focus_items(...)
- summarize_portfolio_alert_focus(...)
- export_portfolio_alert_focus_digest(...)

Input sources:

- latest persisted alert history from Milestone 45
- latest trend alert digest from Milestone 43
- latest run comparison from Milestone 45 if available

Behavior:

- If no preference file is provided, use safe default focus profile.
- Preferences affect display/focus only.
- Preferences do not change alert evaluation or history.
- Focus digest reads existing local history and/or latest generated alerts.
- No database writes.

## 3. Focus item behavior

Each focus item should include:

- focus_key
- alert_key if available
- alert_scope
- property_id
- candidate_id
- address
- severity
- alert_type
- persistence_count if available
- run_count if available
- latest_seen_at
- trend_state: new/persistent/disappeared/worsened/improved/unchanged if available
- message
- recommended_local_action
- focus_reason
- source

Focus reasons examples:

- high severity
- persistent across runs
- recurring property alert
- aggregate burden alert
- lifecycle degradation
- cross-site confidence decrease
- Churn Index increase

Use neutral wording.

## 4. CLI commands

Add:

```text
marketsentry portfolio-alert-focus
marketsentry export-portfolio-alert-focus-digest
marketsentry write-portfolio-alert-focus-template
marketsentry validate-portfolio-alert-focus-config
```

### portfolio-alert-focus

Options:

- --preference-config optional
- --limit optional default 25
- --db optional
- --exports-dir optional

Output:

- profile name
- focus item count
- severity counts
- top focus items
- no mutations
- no outbound notifications

### export-portfolio-alert-focus-digest

Options:

- --preference-config optional
- --output-dir optional
- --format csv/md/both optional default both
- --db optional
- --exports-dir optional

Output:

- report path(s)
- focus item count
- severity counts
- no outbound notification sent

### write-portfolio-alert-focus-template

Options:

- --output config/portfolio_alert_highlight_preferences.example.json
- --overwrite optional default false

Behavior:

- writes example JSON
- refuses overwrite unless --overwrite true

### validate-portfolio-alert-focus-config

Options:

- --preference-config required

Output:

- valid/invalid
- errors/warnings
- parsed profile name
- max_items
- included severities/types

## 5. Dashboard integration

Add **Portfolio Alert Focus View** subsection.

Show:

- active focus profile name
- config validation status
- focus item count
- severity counts
- focus item table
- latest focus digest link

Dashboard remains read-only.

## 6. Scheduled script update

Update existing:

```text
scripts/run_portfolio_review_pack_report.bat
```

So it may optionally run:

- export-portfolio-alert-focus-digest --format both

Script must still:

- not run live retrieval
- not use --force-live
- not run mutation/import commands
- not send outbound notifications
- write logs to logs/scheduled/

Tests must verify scheduled script does not contain live retrieval, mutation, or outbound notification commands.

## 7. Tests

Add or update tests for:

- default preferences load without config
- template writer creates file
- template writer refuses overwrite by default
- valid preference config loads
- invalid JSON handled
- missing profile_name rejected
- invalid severity rejected
- invalid sort_order rejected
- negative max_items rejected
- negative minimum_persistence_count rejected
- live retrieval key rejected
- notification key rejected
- walkability key rejected
- focus items from alert history
- focus items from latest alert digest if history empty
- include/exclude severity filtering
- include/exclude alert type filtering
- persistent-only filtering
- max_items limit
- sort by severity_then_persistence
- sort by persistence_then_severity
- focus summary counts
- Markdown focus digest export
- CSV focus digest export
- CLI portfolio-alert-focus
- CLI export-portfolio-alert-focus-digest
- CLI write template
- CLI validate config
- dashboard focus data loads
- scheduled script safety
- no outbound notification behavior
- no candidate/watchlist/alert mutation
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-45 tests still pass

## 8. Documentation

Update README.md and docs/RUNBOOK.md with a "Portfolio Alert Focus Preferences" section.

Update docs/WINDOWS_TASK_SCHEDULER.md with updated portfolio review pack scheduled script behavior if changed.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with a short section on focus profiles.

Create:

```text
docs/PORTFOLIO_ALERT_FOCUS_PREFERENCES.md
```

Include:

- config file path
- example config
- fields and validation
- CLI examples
- dashboard behavior
- safety limitations
- no outbound notifications

Create decision note:

```text
docs/decisions/045-portfolio-alert-focus-preferences.md
```

Explain:

- why focus preferences follow alert history
- why preferences are display-only
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
- use standard library JSON
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
- Existing portfolio trend alert history works.
- Focus preferences load and validate.
- Focus digest exports Markdown/CSV.
- Dashboard focus section loads.
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
8. Example portfolio_alert_highlight_preferences.example.json path/content summary.
9. Example portfolio-alert-focus output.
10. Example validate-portfolio-alert-focus-config output.
11. Example focus digest report paths and row counts.
12. Dashboard Portfolio Alert Focus View added.
13. Scheduled script update added or explicitly not added.
14. Confirmation that focus preferences are display-only and do not mutate candidate/watchlist/alert state.
15. Confirmation that no outbound notifications are sent.
16. Confirmation that focus preferences do not overwrite Redfin source-of-truth fields.
17. Confirmation that Quiet Score gatekeeper remains unchanged.
18. Confirmation that walkability fields were not added.
19. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
20. Confirmation that tests perform no real network calls.
21. Recommended next implementation step.
22. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 46 complete until all tests pass.
