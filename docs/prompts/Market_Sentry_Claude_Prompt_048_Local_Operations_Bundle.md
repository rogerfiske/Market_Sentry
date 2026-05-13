# Claude Code Prompt 048 - Final Local Operations Bundle and Release Candidate Hardening

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: f554806 (Milestone 47 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Read docs/PORTFOLIO_TREND_ALERT_RULES.md.
8. Read docs/PORTFOLIO_ALERT_FOCUS_PREFERENCES.md.
9. Read docs/PORTFOLIO_ALERT_EMAIL_DIGEST.md.
10. Review the current codebase through commit f554806.
11. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
12. Keep PRD.md and Architecture.md in the project root.
13. Use src/marketsentry/ as the Python package path.
14. Do not move PRD.md or Architecture.md into docs/.
15. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
16. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
17. Do not implement new Redfin live retrieval behavior in this milestone.
18. Do not run any live network calls in tests.
19. Do not make scheduled tasks run live retrieval by default.
20. Do not add walkability parsing or walkability fields.
21. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

## PM direction

Milestone 48 should create a final local operations bundle and release-candidate hardening layer.

This milestone must not add live retrieval, broaden scraping, change the Quiet Score gatekeeper, send outbound notifications, or automatically apply candidate/watchlist/alert actions.

The goal is to make the project easier to operate locally after 47 milestones by producing:

- command inventory
- report inventory
- scheduled script inventory
- configuration inventory
- local safety audit
- report freshness audit
- database schema inventory
- end-to-end local smoke test workflow
- release candidate summary report
- dashboard visibility

This is a local read-only/reporting milestone, except for generating local report files. It must not change candidate decisions, watchlist status, alert status, Redfin source-of-truth fields, retrieval behavior, alert evaluation rules, or focus preferences. It must not infer seller intent. It must not make purchase recommendations. It must not send email, SMS, webhooks, or other outbound notifications.

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
11. Release-candidate audit reports are local files only.
12. No outbound notifications should be sent in this milestone.

## Implement

### 1. Local operations bundle module

Create:

```text
src/marketsentry/local_operations_bundle.py
```

Required models:

- LocalOperationsCommandInventoryItem
- LocalOperationsReportInventoryItem
- LocalOperationsScriptInventoryItem
- LocalOperationsConfigInventoryItem
- LocalOperationsSafetyCheck
- LocalOperationsBundleSummary
- LocalOperationsBundleRunResult

Required functions:

- build_command_inventory(...)
- build_report_inventory(...)
- build_scheduler_script_inventory(...)
- build_config_inventory(...)
- run_local_safety_audit(...)
- run_report_freshness_audit(...)
- build_database_schema_inventory(...)
- build_local_operations_bundle(...)
- export_local_operations_bundle(...)

## 2. Command inventory

Inventory CLI commands from the Typer app where practical.

At minimum, include known command categories:

- database/init/status
- candidate review
- Redfin fixture processing
- cross-site fixture processing
- county verification
- Effective DOM v2
- monitoring snapshots
- retrieval compliance/health
- dashboard
- workflow/runbook
- alert lifecycle
- alert hygiene/triage/archive/expiration
- portfolio review pack
- portfolio comparison/trends/alerts/focus/email draft
- operations digest/history

For each command include:

- command name
- category
- short purpose
- mutates_db: true/false
- live_retrieval_related: true/false
- safe_for_scheduler_default: true/false
- notes

Be conservative. Commands that import decisions, apply triage/archive/expiration decisions, or retrieve live pages should not be marked safe for default scheduling.

## 3. Report inventory

Scan `data/exports/` for known report patterns.

Include:

- report type
- latest file path
- latest modified timestamp
- file count
- row count if CSV
- freshness label: fresh/stale/missing/unknown
- notes

Known report groups should include:

- candidate review
- candidate analysis
- watchlist monitoring
- Effective DOM v2
- county verification
- cross-site comparison
- cross-site analytics
- cross-site trends
- cross-site alerts
- alert hygiene
- alert lifecycle
- lifecycle health
- operations digest/history
- portfolio review pack
- portfolio comparison
- portfolio trends
- portfolio trend alerts
- alert focus digest
- local email digest draft

## 4. Scheduled script inventory

Scan `scripts/*.bat` and `scripts/*.ps1`.

For each script include:

- script path
- script type
- exists
- contains_live_retrieval_command
- contains_force_live
- contains_mutation_command
- contains_outbound_notification_command
- safe_status: safe/review/unsafe
- notes

Known mutation command patterns include:

- import-
- retrieve-
- acknowledge-
- resolve-
- archive
- apply
- delete
- update
- send
- email send
- smtp
- webhook

Be careful not to mark local export-only email draft generation as outbound notification. It is safe if it only exports local draft files.

## 5. Config inventory

Inspect local config templates/files:

- .env.example
- config/alert_expiration_profiles.example.json
- config/portfolio_trend_alert_rules.example.json
- config/portfolio_alert_highlight_preferences.example.json
- any actual local config files if present

For each config include:

- config path
- exists
- is_template
- validation_status if a validator exists
- notes

Do not read credentials or secrets. If a `.env` file exists, report existence only and do not print contents.

## 6. Safety audit

Run local static checks for:

- browser automation references
- outbound notification references
- live retrieval scheduled by default
- unsafe scheduler commands
- walkability fields
- Redfin source-of-truth overwrite patterns
- Quiet Score gatekeeper modifications
- network imports in modules that should be report-only

Safety check result fields:

- check_name
- status: pass/warning/fail
- detail
- file_path if applicable
- recommended_local_action

This is an audit only. Do not modify files automatically.

## 7. Database schema inventory

Using SQLite introspection on the configured DB path:

- table count
- table names
- column counts
- index counts
- known milestone tables present/missing
- notes

If DB missing, report missing gracefully.

## 8. Local smoke test workflow

Add a read-only/lightweight smoke-test command that verifies:

- package imports
- config loads
- database init can run against a temporary DB path
- dashboard summary command can be imported
- key report modules import
- local export directories exist or can be created
- no live retrieval is invoked

Do not run full pytest from inside the CLI command.

## 9. Report export

Export Markdown and CSV:

```text
data/exports/local_operations_bundle_YYYYMMDD_HHMMSS.md
data/exports/local_operations_bundle_YYYYMMDD_HHMMSS.csv
```

Markdown should include:

- release candidate local operations summary
- command inventory
- report inventory/freshness
- script safety inventory
- config inventory
- safety audit
- schema inventory
- smoke test summary
- recommended local next actions

CSV should include rows with:

- section
- item_name
- status
- category
- detail
- file_path
- recommended_local_action

## 10. CLI commands

Add:

```text
marketsentry local-operations-bundle
marketsentry export-local-operations-bundle
marketsentry local-operations-smoke-test
```

### local-operations-bundle

Options:

- --db optional
- --exports-dir optional

Output:

- concise summary
- command count
- report group count
- safety audit pass/warn/fail counts
- script safety counts
- config validation counts
- no mutations
- no outbound notifications

### export-local-operations-bundle

Options:

- --db optional
- --exports-dir optional
- --output-dir optional
- --format csv/md/both optional default both

Output:

- report path(s)
- row counts
- safety status summary

### local-operations-smoke-test

Options:

- --db optional
- --temp-db optional default true

Output:

- pass/warn/fail checks
- no live retrieval invoked
- no outbound notification sent

## 11. Dashboard integration

Add **Local Operations Bundle** dashboard subsection.

Show:

- bundle summary metrics
- safety audit table
- report freshness table
- scheduled script safety table
- config inventory table
- latest bundle report link

Dashboard remains read-only.

## 12. Scheduled script

Optionally add:

```text
scripts/run_local_operations_bundle_report.bat
```

Behavior:

- activate local venv if present
- run export-local-operations-bundle --format both
- write logs to logs/scheduled/
- no live retrieval
- no --force-live
- no mutation/import commands
- no outbound notification commands

Tests must verify the script is safe if added.

## 13. Tests

Add or update tests for:

- command inventory builds
- report inventory with empty exports dir
- report inventory with sample CSV/MD files
- scheduled script inventory scans safe scripts
- scheduled script inventory flags unsafe patterns
- config inventory with templates
- config inventory with missing config directory
- safety audit passes clean test fixtures
- safety audit flags live retrieval scheduled command
- safety audit flags outbound notification command
- safety audit flags walkability string outside allowed docs/tests if applicable
- schema inventory with missing DB
- schema inventory with temp initialized DB
- local operations bundle builds
- bundle Markdown export
- bundle CSV export
- CLI local-operations-bundle
- CLI export-local-operations-bundle
- CLI local-operations-smoke-test
- dashboard bundle data loads
- scheduled script safety if script added
- no candidate/watchlist/alert mutation
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- no outbound notifications
- existing MVP 1-47 tests still pass

## 14. Documentation

Update README.md and docs/RUNBOOK.md with a "Local Operations Bundle" section.

Update docs/WINDOWS_TASK_SCHEDULER.md if a scheduled script is added.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with a short section on using the local operations bundle before weekly review.

Create:

```text
docs/LOCAL_OPERATIONS_BUNDLE.md
```

Include:

- command inventory explanation
- report inventory explanation
- safety audit explanation
- config inventory explanation
- smoke test explanation
- CLI examples
- safety limitations

Create decision note:

```text
docs/decisions/047-local-operations-bundle.md
```

Explain:

- why local operations bundle follows the email draft feature
- why release-candidate hardening is local/report-only
- why it audits rather than mutates
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
- use standard library only unless existing dependencies are already used
- no browser automation
- no Playwright/Selenium
- no bypassing CAPTCHAs, paywalls, login walls, anti-bot protections, or technical access controls
- no network calls in tests
- do not import smtplib
- do not import requests/httpx/urllib.request for this feature
- preserve source file paths and timestamps for auditability
- use neutral language
- do not make purchase recommendations
- do not add walkability parsing or fields

## Quality gates

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- Existing portfolio alert email digest works.
- Local operations bundle builds.
- Local operations bundle exports Markdown/CSV.
- Local operations smoke test runs without live retrieval.
- Dashboard local operations section loads.
- Scheduled scripts remain safe.
- No candidate/watchlist/alert status mutations occur.
- No Redfin source-of-truth fields are overwritten.
- Quiet gatekeeper remains unchanged.
- No real network calls are performed in tests.
- No scheduled task invokes live retrieval, mutation commands, or outbound notifications.
- No SMTP/Gmail/Outlook/webhook/SMS code is added.
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
8. Example local-operations-bundle output.
9. Example local operations bundle report paths and row counts.
10. Example local-operations-smoke-test output.
11. Safety audit summary.
12. Dashboard Local Operations Bundle section added.
13. Scheduled script added or explicitly not added.
14. Confirmation that local operations bundle is read-only and does not mutate candidate/watchlist/alert state.
15. Confirmation that no outbound notifications are sent.
16. Confirmation that no credentials are stored or requested.
17. Confirmation that local operations bundle does not overwrite Redfin source-of-truth fields.
18. Confirmation that Quiet Score gatekeeper remains unchanged.
19. Confirmation that walkability fields were not added.
20. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
21. Confirmation that tests perform no real network calls.
22. Recommended next implementation step.
23. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 48 complete until all tests pass.
