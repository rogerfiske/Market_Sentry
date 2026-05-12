# Claude Code Prompt 038 - Watchlist Operations Digest and Executive Summary Reports

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: e9c64c9 (Milestone 37 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Review the current codebase through commit e9c64c9.
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

Milestone 38 should add a consolidated Watchlist Operations Digest and Executive Summary report.

This milestone must not add live retrieval, broaden scraping, change the Quiet Score gatekeeper, or automatically apply triage/archive/expiration/alert status actions.

The goal is to turn the many local reports into one practical, concise operator digest:

- candidate review queue status
- watchlist status
- Effective DOM v1/v2 highlights
- Churn Index highlights
- Quiet/Vibrancy gatekeeper status
- gas and garage evidence summary
- cross-site confidence and discrepancy status
- cross-site alert burden and alert hygiene status
- lifecycle audit/lifecycle health summary
- lifecycle health trend summary
- retrieval operations health summary
- top review priorities
- recommended next local actions

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
11. Operations digest is a local review summary only and must not mutate alert/watchlist/candidate state.

## Implement

### 1. Operations digest module

Create:

```text
src/marketsentry/operations_digest.py
```

Required models:

- OperationsDigestSection
- OperationsDigestMetric
- OperationsDigestPropertyPriority
- OperationsDigestNextAction
- OperationsDigestSummary
- OperationsDigestReportRow
- OperationsDigestRunResult

Required functions:

- build_operations_digest(...)
- build_candidate_review_digest(...)
- build_watchlist_digest(...)
- build_effective_dom_digest(...)
- build_cross_site_digest(...)
- build_alert_digest(...)
- build_lifecycle_digest(...)
- build_retrieval_operations_digest(...)
- rank_operations_review_priorities(...)
- generate_operations_next_actions(...)
- export_operations_digest(...)

## 2. Digest content

The digest should summarize the current local database and latest reports.

### Candidate review section

Include:

- candidate count
- strong_review count
- review count
- maybe/needs_more_data count
- reject_location_noise count
- pending user_decision count
- latest candidate analysis report path if available

### Watchlist section

Include:

- watched property count
- active watched property count
- high priority watched count
- properties with gas evidence
- properties with garage evidence
- latest monitoring report path if available

### Effective DOM / Churn section

Include:

- properties with county_reset_applied
- properties with high recent_churn_index
- properties with effective_dom_v2 materially below v1
- properties with high Effective DOM delta
- latest Effective DOM v2 report path if available

### Cross-site section

Include:

- properties with cross-site observations
- low cross-site confidence count
- high discrepancy severity count
- stale/low-confidence source count if available
- latest cross-site analytics report path if available
- latest cross-site trend report path if available

### Alerts and hygiene section

Include:

- open alert count
- high/critical open alert count
- stale open alert count
- needs_reparse count
- needs_manual_review count
- archive candidates count
- latest hygiene report path if available
- latest alert triage/export report paths if available

### Lifecycle section

Include:

- properties scored for lifecycle health
- attention_required count
- needs_review count
- improved health trend count
- degraded health trend count
- lifecycle gap count
- latest lifecycle health report path if available
- latest lifecycle health trend report path if available

### Retrieval operations section

Include:

- pending fixture capture queue count
- stale pending capture count if available
- retrieval health issue count if available
- latest retrieval health report path if available
- live retrieval enabled status from config/environment
- clear note that digest performs no network calls

## 3. Review priorities

Create a ranked list of top local review priorities.

Suggested priority signals:

- Quiet gatekeeper failure should remain separate and must not be overridden.
- attention_required lifecycle health
- high/critical open alerts
- stale open alerts
- needs_reparse/manual_review
- high cross-site discrepancy severity
- low cross-site confidence with active watched property
- high recent_churn_index
- high Effective DOM delta
- missing key data
- pending review decisions

Priority labels:

- immediate_review
- high_review
- normal_review
- monitor
- no_current_action

Use neutral wording.

Do not make purchase recommendations.

## 4. Next local actions

Generate recommended local actions such as:

- Export candidate review CSV.
- Review properties with reject_location_noise separately.
- Run cross-site alert hygiene check.
- Export cross-site alert triage CSV.
- Review lifecycle health report.
- Save missing fixtures manually.
- Process pending local fixtures.
- Run dashboard locally.

No action should instruct live retrieval unless the existing safe approval-gated workflow is explicitly referenced as optional and disabled by default.

## 5. Report export

Export Markdown and CSV.

Suggested outputs:

```text
data/exports/operations_digest_YYYYMMDD_HHMMSS.md
data/exports/operations_digest_YYYYMMDD_HHMMSS.csv
```

Markdown should be the primary human-readable report.

CSV should include rows:

- section
- metric_name
- metric_value
- severity
- notes
- source_report_path

Also export top priorities section as CSV rows if straightforward.

## 6. CLI commands

Add:

```text
marketsentry operations-digest
marketsentry export-operations-digest
```

### operations-digest

Options:

- --db
- --exports-dir optional

Output:

- concise summary to terminal
- key counts
- top priorities
- next actions
- no mutations

### export-operations-digest

Options:

- --db
- --output-dir
- --format md/csv/both optional default both

Output:

- report path(s)
- metric row count
- priority count
- next action count

## 7. Dashboard integration

Add **Operations Digest** section or subsection to dashboard.

Show:

- summary metrics
- section cards/tables
- top review priorities
- next local actions
- latest exported digest path

Dashboard remains read-only.

## 8. Scheduled local report script

Add:

```text
scripts/run_operations_digest_report.bat
```

Behavior:

- activate local venv if present
- run export-operations-digest --format both
- optionally run dashboard-summary
- write logs to logs/scheduled/
- no live retrieval
- no --force-live
- no mutation commands

Update automation-status or script list if relevant.

Tests must verify scheduled script does not contain live retrieval commands, import/mutation commands, or `--force-live`.

## 9. Tests

Add or update tests for:

- build digest with empty database
- build digest with candidate data
- build digest with watched properties
- build digest with Effective DOM v2 fields
- build digest with cross-site analytics fields
- build digest with alert/hygiene data
- build digest with lifecycle health/trend data
- build digest with retrieval health data
- top priority ranking
- next action generation
- Markdown export
- CSV export
- CLI operations-digest
- CLI export-operations-digest
- dashboard digest data loads
- scheduled script safety
- no candidate/watchlist/alert mutation
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-37 tests still pass

## 10. Documentation

Update README.md and docs/RUNBOOK.md with an "Operations Digest" section.

Update docs/WINDOWS_TASK_SCHEDULER.md with the new scheduled digest script.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with a short section on using the digest for weekly local review.

Create:

```text
docs/decisions/037-watchlist-operations-digest.md
```

Explain:

- why digest follows lifecycle health trends
- why it is read-only
- why it consolidates reports instead of replacing detailed reports
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
- Existing reports still work.
- Operations digest builds.
- Operations digest exports Markdown/CSV.
- Dashboard digest section loads.
- Scheduled digest script is safe.
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
8. Example operations-digest output.
9. Example operations digest report paths and row counts.
10. Example top review priorities.
11. Example next local actions.
12. Dashboard Operations Digest section added.
13. Scheduled script added.
14. Confirmation that operations digest is read-only and does not mutate candidate/watchlist/alert state.
15. Confirmation that operations digest does not overwrite Redfin source-of-truth fields.
16. Confirmation that Quiet Score gatekeeper remains unchanged.
17. Confirmation that walkability fields were not added.
18. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
19. Confirmation that tests perform no real network calls.
20. Recommended next implementation step.
21. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 38 complete until all tests pass.
