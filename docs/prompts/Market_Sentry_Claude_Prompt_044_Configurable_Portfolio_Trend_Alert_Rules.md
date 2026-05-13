# Claude Code Prompt 044 - Configurable Portfolio Trend Alert Rules

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: 4099399 (Milestone 43 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Review the current codebase through commit 4099399.
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

Milestone 44 should add configurable local portfolio trend alert rules.

This milestone must not add live retrieval, broaden scraping, change the Quiet Score gatekeeper, send outbound notifications, or automatically apply candidate/watchlist/alert actions.

The goal is to make Milestone 43 threshold rules tunable without code changes:

- write an example JSON config file
- load user-defined local alert rules
- validate rules safely
- merge or replace default rules only when explicitly requested
- list active rule set
- preview/evaluate alerts using a specified rule config
- export digest using a specified rule config
- dashboard visibility for rule config status

This is a local read-only/reporting milestone. It must not change candidate decisions, watchlist status, alert status, Redfin source-of-truth fields, or retrieval behavior. It must not infer seller intent. It must not make purchase recommendations. It must not send email, SMS, webhooks, or other outbound notifications.

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
11. Configurable trend alert rules are local review prompts only and must not mutate candidate/watchlist/alert state.
12. No outbound notifications should be sent in this milestone.

## Implement

### 1. Trend alert rule configuration

Add support for a local JSON config file.

Suggested path:

```text
config/portfolio_trend_alert_rules.json
```

Add example template:

```text
config/portfolio_trend_alert_rules.example.json
```

Do not require the file to exist. Built-in rules from Milestone 43 must continue to work without config.

Example format:

```json
{
  "mode": "merge",
  "rules": [
    {
      "rule_id": "custom_aggregate_burden_high",
      "rule_name": "Custom aggregate burden high threshold",
      "scope": "portfolio",
      "metric_name": "aggregate_review_burden_score",
      "threshold_value": 75,
      "comparison": ">=",
      "severity": "high",
      "enabled": true,
      "message_template": "Aggregate review burden is {current_value}, threshold {threshold_value}",
      "recommended_local_action": "Review top burden contributors in the trend digest"
    }
  ]
}
```

Allowed mode values:

- merge
- replace

Default mode:

- merge

Allowed scope values:

- portfolio
- property

Allowed comparison values:

- >=
- >
- <=
- <
- ==
- !=
- delta>=
- delta<=

Allowed severity values:

- info
- warning
- high

Allowed enabled values:

- true
- false

Validation rules:

- rule_id required and unique
- rule_name required
- scope required
- metric_name required
- comparison required
- severity required
- threshold_value numeric where applicable
- disabled rules are valid but not evaluated
- no rule may cause writes or notifications
- no rule may reference walkability
- no rule may reference live retrieval
- invalid config must fail safely with clear errors

## 2. Rule loader functions

Extend `portfolio_trend_alerts.py` or create a helper module.

Required functions:

- load_portfolio_trend_alert_rule_config(...)
- validate_portfolio_trend_alert_rule_config(...)
- merge_portfolio_trend_alert_rules(...)
- write_portfolio_trend_alert_rule_template(...)
- get_active_portfolio_trend_alert_rules(...)

Behavior:

- Built-in rules are always available.
- Config file is optional.
- `merge` adds enabled custom rules after built-ins.
- `replace` uses only enabled custom rules.
- Disabled custom rules are shown in validation/list output but not evaluated.
- Duplicate rule IDs should be rejected unless exact duplicate built-in override is explicitly disallowed by default.
- User config must not silently override built-in rule IDs.
- Invalid config should not break default commands unless user explicitly supplies the invalid config. If explicitly supplied, return a clear validation error.

## 3. CLI updates

Update Milestone 43 commands to support:

```text
--rule-config config/portfolio_trend_alert_rules.json
```

Commands:

- portfolio-trend-alerts
- export-portfolio-trend-alert-digest

Add new commands:

```text
marketsentry list-portfolio-trend-alert-rules
marketsentry write-portfolio-trend-alert-rule-template
marketsentry validate-portfolio-trend-alert-rules
```

### list-portfolio-trend-alert-rules

Options:

- --rule-config optional

Output:

- rule count
- enabled/disabled counts
- mode
- table of active rules

### write-portfolio-trend-alert-rule-template

Options:

- --output config/portfolio_trend_alert_rules.example.json
- --overwrite optional default false

Behavior:

- writes example JSON config
- refuses overwrite unless --overwrite true

### validate-portfolio-trend-alert-rules

Options:

- --rule-config required

Output:

- valid/invalid
- errors/warnings
- enabled rule count
- disabled rule count

## 4. Dashboard integration

Add rule configuration visibility to Portfolio Trend Alerts dashboard subsection.

Show:

- built-in rule count
- custom config detected
- custom config validation status
- active rule count
- enabled/disabled custom rule count
- latest alert digest link

Dashboard remains read-only.

## 5. Scheduled script

Do not require scheduled script to use a custom rule config.

Optionally allow users to edit script manually later, but default script should keep using built-in rules unless a safe default config path exists and is valid.

Tests must verify scheduled script still does not contain live retrieval, mutation, or outbound notification commands.

## 6. Tests

Add or update tests for:

- built-in rules still load without config
- missing config does not error
- template writer creates file
- template writer refuses overwrite by default
- valid custom rule config loads
- merge mode includes built-in + custom rules
- replace mode uses only custom rules
- disabled rule is not evaluated
- duplicate rule ID rejected
- built-in override rejected
- invalid JSON handled
- missing required rule_id rejected
- invalid scope rejected
- invalid comparison rejected
- invalid severity rejected
- threshold_value missing where required rejected
- walkability metric rejected
- live retrieval metric rejected
- portfolio-trend-alerts uses custom rules when provided
- export digest uses custom rules when provided
- CLI list rules
- CLI write template
- CLI validate valid config
- CLI validate invalid config
- dashboard rule config data loads
- no outbound notification behavior
- no candidate/watchlist/alert mutation
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-43 tests still pass

## 7. Documentation

Update README.md and docs/RUNBOOK.md with a "Configurable Portfolio Trend Alert Rules" section.

Update docs/WINDOWS_TASK_SCHEDULER.md only if scheduled script behavior changes.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with a short section on configuring trend alert thresholds.

Create:

```text
docs/PORTFOLIO_TREND_ALERT_RULES.md
```

Include:

- built-in rules
- config file path
- config schema
- merge vs replace
- validation rules
- CLI examples
- safety limitations
- no outbound notifications

Create decision note:

```text
docs/decisions/043-configurable-portfolio-trend-alert-rules.md
```

Explain:

- why configurable rules follow default trend alerts
- why config is local JSON
- why invalid configs fail safely
- why built-in rule override is disallowed by default
- why no outbound notification is sent
- why scheduled script remains local/report-only
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
- Existing portfolio trend alert digest exports work.
- Custom rule config loads and validates.
- Custom rules evaluate correctly.
- Dashboard rule config visibility loads.
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
8. Example portfolio_trend_alert_rules.example.json path/content summary.
9. Example list-portfolio-trend-alert-rules output.
10. Example validate-portfolio-trend-alert-rules output.
11. Example portfolio-trend-alerts output using custom rules.
12. Dashboard rule config visibility added.
13. Confirmation that trend alert rule config is read-only and does not mutate candidate/watchlist/alert state.
14. Confirmation that no outbound notifications are sent.
15. Confirmation that custom rules do not overwrite Redfin source-of-truth fields.
16. Confirmation that Quiet Score gatekeeper remains unchanged.
17. Confirmation that walkability fields were not added.
18. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
19. Confirmation that tests perform no real network calls.
20. Recommended next implementation step.
21. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 44 complete until all tests pass.
