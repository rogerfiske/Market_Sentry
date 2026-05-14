# Local Operations Bundle

## Overview

The local operations bundle provides a release-candidate hardening layer that aggregates system inventory, safety audits, and smoke tests into a single report. It makes the project easier to operate locally after 48 milestones by providing visibility into commands, reports, scripts, configs, safety status, database schema, and system readiness.

## Command Inventory

The command inventory catalogs all known CLI commands with:

- **command_name**: The CLI command name
- **category**: Functional category (database, candidate review, portfolio alerts, etc.)
- **purpose**: Short description of what the command does
- **mutates_db**: Whether the command writes to the database
- **live_retrieval_related**: Whether the command involves live network retrieval
- **safe_for_scheduler_default**: Whether the command is safe for unattended scheduled execution

Commands that import decisions, apply triage/archive/expiration, or retrieve live pages are not marked safe for default scheduling.

## Report Inventory

The report inventory scans `data/exports/` for known report file patterns and reports:

- **report_type**: The report category
- **latest_file_path**: Path to the most recent file
- **latest_modified**: Timestamp of the most recent file
- **file_count**: Total number of files matching the pattern
- **row_count**: Number of data rows (CSV files only)
- **freshness**: fresh (< 7 days), stale (>= 7 days), or missing

Known report groups include candidate review, watchlist monitoring, cross-site analytics, alert hygiene, lifecycle health, operations digest, portfolio review pack, trend alerts, alert focus digest, email digest draft, and operations bundle.

## Safety Audit

The safety audit runs static checks against the project source code:

| Check | Description |
|-------|-------------|
| browser_automation | Detects playwright/selenium imports |
| outbound_notification_imports | Detects smtplib/twilio imports |
| walkability_fields | Detects walkability_score/walk_score fields |
| scheduled_script_safety | Verifies all scripts are safe |
| quiet_gatekeeper_modification | Detects Quiet Score threshold changes |
| redfin_sot_overwrite | Detects Redfin source-of-truth overwrite patterns |
| report_module_network_imports | Detects network imports in report modules |

Each check returns pass, warning, or fail with recommended actions.

## Config Inventory

The config inventory inspects known configuration files:

- `.env.example` / `.env`
- `config/alert_expiration_profiles.example.json` / `.json`
- `config/portfolio_trend_alert_rules.example.json` / `.json`
- `config/portfolio_alert_highlight_preferences.example.json` / `.json`

Reports existence, template status, and validation status. Does not read or print credential contents.

## Smoke Test

The smoke test verifies basic system readiness:

| Check | Description |
|-------|-------------|
| package_import | marketsentry package imports cleanly |
| config_load | Config module loads without errors |
| database_init | Database can be initialized (uses temp DB) |
| dashboard_import | Dashboard summary module can be imported |
| report_modules_import | Key report modules import cleanly |
| export_directory | data/exports directory exists or can be created |

The smoke test does not run full pytest, invoke live retrieval, or send notifications.

## CLI Examples

```bash
# Show operations bundle summary
marketsentry local-operations-bundle

# Show with custom database
marketsentry local-operations-bundle --db data/market_sentry.db

# Export Markdown and CSV reports
marketsentry export-local-operations-bundle --format both

# Export CSV only
marketsentry export-local-operations-bundle --format csv

# Export to custom directory
marketsentry export-local-operations-bundle --output-dir reports/bundles

# Run smoke test with temporary database
marketsentry local-operations-smoke-test

# Run smoke test against existing database
marketsentry local-operations-smoke-test --no-temp-db --db data/market_sentry.db
```

## Export Files

The bundle exports to:

```
data/exports/local_operations_bundle_YYYYMMDD_HHMMSS.md
data/exports/local_operations_bundle_YYYYMMDD_HHMMSS.csv
```

The Markdown report includes all inventory sections, safety audit results, smoke test summary, and recommended next actions.

The CSV report includes rows with section, item_name, status, category, detail, file_path, and recommended_local_action columns.

## Integration with Release Candidate

The local operations bundle feeds the release candidate report (Milestone 49). The release candidate validation runs the operations bundle build, smoke test, and safety audit as part of its automated checks. See `docs/RELEASE_CANDIDATE_CHECKLIST.md` for the full release candidate status.

## Safety Limitations

- The operations bundle is read-only and does not mutate candidate, watchlist, or alert state
- No outbound notifications are sent (email, SMS, webhook)
- No live retrieval is performed
- No credentials are stored or requested
- No Redfin source-of-truth fields are overwritten
- No Quiet Score gatekeeper modifications
- No walkability fields are referenced
- No browser automation is used
- The safety audit is informational only and does not automatically fix issues
