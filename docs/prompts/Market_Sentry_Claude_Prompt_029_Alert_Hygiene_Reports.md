# Claude Code Prompt 029 - Scheduled Triage Reminder and Alert Hygiene Reports

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository:

https://github.com/rogerfiske/Market_Sentry

Local project folder:

C:\Users\Minis\CascadeProjects\Market_Sentry

Current accepted milestones:

- Milestone 1 scaffold complete at commit c8599761be1aeda80b075cf668c61970e587ebe7
- Milestone 2 candidate review queue and watchlist promotion complete at commit 5da7747a44069696189d1abb8057ee23f17d8754
- Milestone 3 Redfin discovery adapter foundation complete at commit 91eac91085609c38f150881bf35e5a22d1f6bdf0
- Milestone 4 Redfin detail parser and candidate enrichment complete at commit dafb63d
- Milestone 5 Effective DOM engine and candidate scoring report complete at commit 52ea72d
- Milestone 6 cross-site enrichment foundation stabilized and accepted at commit 01b6887
- Milestone 7 watchlist monitoring snapshots and change detection complete at commit 23ac2b5
- Milestone 8 county recorder and assessor verification foundation complete at commit 89ce91a
- Milestone 9 Effective DOM v2 county-verified reset integration complete at commit 0e83285
- Milestone 10 Effective DOM v2 operational integration complete at commit 44b655d
- Milestone 11 end-to-end operating workflow and runbook complete at commit 6cf5627
- Prompt 011A export path stabilization complete at commit 4475634
- Milestone 12 local dashboard and report viewer complete at commit 6cb30f1
- Milestone 13 Windows Task Scheduler automation complete at commit deaa042
- Milestone 14 live retrieval strategy and compliance adapters complete at commit ee7e81f
- Milestone 15 retrieval safety enforcement and fixture capture queue complete at commit e4010d8
- Milestone 16 Redfin Live HTTP Retrieval Phase 1 complete at commit d8ed591
- Milestone 17 Redfin retrieved fixture processing pipeline complete at commit e41e5e4
- Milestone 18 Redfin pending capture batch retrieval orchestrator complete at commit 2d420d7
- Milestone 19 Redfin batch retrieval approval workflow complete at commit 66628f6
- Milestone 20 retrieval operations dashboard integration complete at commit 9df9300
- Milestone 21 retrieval operations aging, alerts, and health checks complete at commit c92f687
- Milestone 22 cross-site adapter parity and manual fixture workflow complete at commit 1e3235c
- Milestone 23 cross-site parser quality and fixture corpus expansion complete at commit 3b1470a
- Milestone 24 confidence-weighted cross-site comparison analytics complete at commit 788ac84
- Milestone 25 cross-site analytics trend snapshots complete at commit 3322f92
- Milestone 26 cross-site trend alerts and watchlist monitoring integration complete at commit 67d2265
- Milestone 27 cross-site alert aggregation and historical pattern analysis complete at commit 1cfaf34
- Milestone 28 cross-site alert triage workflow complete at commit b044306

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Review the current codebase through commit b044306.
7. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
8. Keep PRD.md and Architecture.md in the project root.
9. Use src/marketsentry/ as the Python package path.
10. Do not move PRD.md or Architecture.md into docs/.
11. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
12. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
13. Do not implement new Redfin live retrieval behavior in this milestone.
14. Do not run any live network calls in tests.
15. Do not make scheduled tasks run live retrieval by default.
16. Do not add walkability parsing or walkability fields.
17. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 29 should add scheduled/local reminder and alert hygiene reporting around the cross-site alert and triage system.

This milestone should NOT add live retrieval.

This milestone should NOT broaden scraping.

This milestone should NOT change the Quiet Score gatekeeper.

This milestone may add scheduled scripts, but they must be local report-generation scripts only. They must not invoke live retrieval, approved retrieval, or --force-live commands.

The goal is to help the user regularly review accumulated alert state:

- stale open alerts
- old acknowledged alerts
- old resolved alerts that may be candidates for archive
- alerts marked needs_reparse
- alerts marked needs_manual_review
- high alert-burden properties
- repeated unresolved patterns
- latest triage export status
- recommended local next actions

These are neutral operational reminders only. Do not infer seller intent. Do not make purchase recommendations.

Cross-site alert and triage state must not overwrite Redfin source-of-truth fields or automatically change watchlist status.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It uses a human-in-the-loop, fixture-first workflow to observe candidate and watched properties using Effective DOM v1/v2, Churn Index, Quiet/Vibrancy gatekeeper logic, gas evidence, garage spaces, cross-site validation, county verification, local reports, dashboard views, Windows Task Scheduler support, and compliance-aware retrieval operations.

Critical domain rules:

1. Effective DOM v1 is listing-history-derived exposure without county reset integration.
2. Effective DOM v2 applies county-confirmed ownership transfer as a reset boundary when appropriate.
3. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
4. Churn Index remains reportable even when Effective DOM is reset.
5. Quiet Score is the gatekeeper.
6. Target is very high Quiet and very low Vibrancy.
7. Any mention of gas means the property has natural gas supply/service.
8. Walkability-type information is excluded from the initial scope.
9. Use neutral language. Do not infer seller intent.
10. Reports are analytical aids, not purchase recommendations.
11. Alert hygiene and reminders may recommend review actions only; they must not change watchlist status automatically.

Your task for Prompt 029:

Implement Scheduled Triage Reminder and Alert Hygiene Reports v1.

## 1. Alert hygiene module

Create a module, for example:

```text
src/marketsentry/cross_site_alert_hygiene.py
```

Required models:

- CrossSiteAlertHygieneIssue
- CrossSiteAlertHygieneSummary
- CrossSiteAlertHygieneConfig
- CrossSiteAlertHygieneReportRow
- CrossSiteAlertHygieneRunResult

Required functions:

- run_cross_site_alert_hygiene_check(...)
- identify_stale_open_alerts(...)
- identify_old_acknowledged_alerts(...)
- identify_old_resolved_alerts(...)
- identify_needs_reparse_alerts(...)
- identify_needs_manual_review_alerts(...)
- identify_high_burden_properties(...)
- identify_repeated_unresolved_patterns(...)
- generate_alert_hygiene_next_actions(...)
- export_cross_site_alert_hygiene_report(...)

## 2. Hygiene thresholds

Use configurable default thresholds:

- open alert stale after 7 days
- acknowledged alert stale after 14 days
- resolved alert archive candidate after 30 days
- needs_reparse alert stale after 7 days
- needs_manual_review alert stale after 7 days
- high alert burden threshold: burden label high or elevated_review
- repeated unresolved pattern threshold: 2 or more unresolved alerts of same type

Allow overrides via function args or config object.

## 3. Hygiene issue categories

Suggested issue categories:

- stale_open_alert
- stale_acknowledged_alert
- resolved_archive_candidate
- needs_reparse_pending
- needs_manual_review_pending
- high_alert_burden_property
- repeated_unresolved_pattern
- no_recent_triage_export
- triage_import_pending_review

Suggested severity levels:

- info
- warning
- high
- critical

Use neutral wording.

## 4. Hygiene reports

Export report to:

```text
data/exports/cross_site_alert_hygiene_YYYYMMDD_HHMMSS.csv
```

and optionally Markdown:

```text
data/exports/cross_site_alert_hygiene_YYYYMMDD_HHMMSS.md
```

Required report columns:

- issue_id
- category
- severity
- property_id
- candidate_id
- alert_id
- alert_type
- alert_status
- alert_age_days
- burden_label
- repeated_pattern
- message
- recommended_action
- source_context
- created_at

If Markdown is implemented, include:

- summary counts
- high-priority issues
- recommended next commands
- list of affected properties

## 5. CLI commands

Add CLI commands:

```text
marketsentry cross-site-alert-hygiene-check
marketsentry export-cross-site-alert-hygiene-report
```

### cross-site-alert-hygiene-check

Options:

- --db
- --open-stale-days optional
- --acknowledged-stale-days optional
- --resolved-archive-days optional

Output:

- issue counts by severity
- issue counts by category
- high-burden property count
- stale open alert count
- needs_reparse count
- needs_manual_review count
- recommended next actions

### export-cross-site-alert-hygiene-report

Options:

- --db
- --output-dir
- --format csv/md/both optional default csv

Output:

- report path(s)
- row count
- issue count

## 6. Scheduled local reminder scripts

Add Windows-safe scheduled script support for alert hygiene reports only.

Required script:

```text
scripts/run_alert_hygiene_report.bat
```

Optional PowerShell installer/uninstaller:

```text
scripts/install_task_scheduler_alert_hygiene.ps1
scripts/uninstall_task_scheduler_alert_hygiene.ps1
```

Default schedule if installer is implemented:

- weekly
- Friday
- 4:00 PM local time

Script behavior:

- Activate local venv if present.
- Run local report command only.
- Write logs to:
  - logs/scheduled/
- Do not run live retrieval.
- Do not run approved retrieval.
- Do not use --force-live.

Update automation-status or write-scheduler-scripts if necessary to recognize the new script.

Tests should verify scheduled scripts do not contain live retrieval commands or --force-live.

## 7. Dashboard integration

Add Alert Hygiene subsection to dashboard.

Show:

- issue counts by severity
- issue counts by category
- stale open alerts
- needs_reparse
- needs_manual_review
- resolved archive candidates
- high burden properties
- repeated unresolved patterns
- recommended next actions
- latest hygiene report path if available

Dashboard remains read-only.

## 8. Optional auto-archive recommendation only

Do NOT auto-archive resolved alerts in this milestone.

It is acceptable to identify candidates for archive and recommend exporting a triage CSV where the user can choose `archive`.

## 9. Tests

Add or update tests for:

- stale open alert detection
- old acknowledged alert detection
- old resolved alert archive candidate detection
- needs_reparse pending detection
- needs_manual_review pending detection
- high burden property detection
- repeated unresolved pattern detection
- no_recent_triage_export issue if implemented
- hygiene summary counts
- next actions generated
- CSV report export
- Markdown report export if implemented
- cross-site-alert-hygiene-check CLI
- export-cross-site-alert-hygiene-report CLI
- scheduled hygiene batch script exists
- scheduled hygiene script does not include live retrieval or --force-live
- dashboard hygiene data loads
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-28 tests still pass

All tests must pass.

## 10. Documentation

Update README.md and docs/RUNBOOK.md with a "Cross-Site Alert Hygiene" section.

Update docs/WINDOWS_TASK_SCHEDULER.md with the optional alert hygiene scheduled report workflow if scheduler installer is implemented.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with:

- what alert hygiene means
- how to run hygiene check
- how to export hygiene report
- how to use report with triage workflow
- reminder that hygiene is a review aid, not an automatic status changer

Create design decision note:

```text
docs/decisions/028-cross-site-alert-hygiene-scheduled-reminders.md
```

Explain:

- why hygiene reports follow triage workflow
- why alert hygiene is report-only
- why resolved alerts are not auto-archived
- why scheduled task runs local report only
- why watchlist state is not automatically changed
- why Quiet Score gatekeeper is unchanged
- why walkability remains excluded

## 11. Code standards

- Python 3.11+
- PEP8 compliant.
- Type hints required.
- Docstrings required for all functions.
- Remove unused imports.
- Keep modules small and readable.
- No browser automation.
- No Playwright/Selenium.
- No bypassing CAPTCHAs, paywalls, login walls, anti-bot protections, or technical access controls.
- No network calls in tests.
- Preserve source URLs and timestamps for auditability.
- Avoid inaccurate Claude co-authorship metadata.
- Use neutral language.
- Do not make purchase recommendations.
- Do not add walkability parsing or walkability fields.

Quality gates:

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works for fresh database.
- Existing cross-site trend alerts work.
- Existing cross-site alert analytics work.
- Existing cross-site alert triage export/import works.
- Alert hygiene check works.
- Alert hygiene report exports.
- Scheduled hygiene script exists and does not invoke live retrieval.
- Dashboard hygiene section loads.
- No Redfin source-of-truth fields are overwritten.
- Quiet gatekeeper remains unchanged.
- No real network calls are performed in tests.
- No scheduled task invokes live retrieval.
- Changes committed and pushed to origin/main.

Completion report required:

When finished, provide:

1. Summary of what you implemented.
2. Files created or modified.
3. Exact commands run.
4. Final test results with full pytest summary showing 100% pass.
5. Any dependency changes.
6. Any assumptions made.
7. Any blockers or risks remaining.
8. Example cross-site-alert-hygiene-check output.
9. Example hygiene report path and row count.
10. Scheduled hygiene script(s) added.
11. Dashboard hygiene section added.
12. Example stale open alert issue.
13. Example resolved archive candidate issue.
14. Example needs_reparse/needs_manual_review issue.
15. Confirmation that hygiene reports do not overwrite Redfin source-of-truth fields.
16. Confirmation that hygiene reports do not automatically archive alerts or change watchlist status.
17. Confirmation that Quiet Score gatekeeper remains unchanged.
18. Confirmation that walkability fields were not added.
19. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
20. Confirmation that tests perform no real network calls.
21. Recommended next implementation step.
22. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 29 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
