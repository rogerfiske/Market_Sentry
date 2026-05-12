# Claude Code Prompt 034 - Alert Lifecycle Audit Trail and Operations Summary

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
- Milestone 29 scheduled triage reminder and alert hygiene reports complete at commit a752068
- Milestone 30 opt-in resolved alert archive policy workflow complete at commit e5261c0
- Milestone 31 configurable alert expiration rules and operator approval gates complete at commit d9fbe84
- Milestone 32 user-defined alert expiration profiles complete at commit c211670
- Milestone 33 alert expiration profile comparison and last-used profile persistence complete at commit c883f3e

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Review the current codebase through commit c883f3e.
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

Important PM direction:

Milestone 34 should consolidate alert lifecycle activity into a local audit trail and operations summary.

This milestone should NOT add live retrieval.

This milestone should NOT broaden scraping.

This milestone should NOT change the Quiet Score gatekeeper.

This milestone should NOT automatically apply expiration, archive, triage, or alert state actions.

The goal is to make the growing alert-management system easier to inspect:

- show alert lifecycle history across triage, archive, and expiration actions
- summarize alert state transitions by property
- summarize action types and operators/notes where present
- expose stale/unresolved lifecycle chains
- export a unified audit report
- add dashboard visibility
- support read-only CLI summaries

This is an observability/audit/reporting milestone. It must not change watchlist status automatically, must not overwrite Redfin source-of-truth fields, and must not infer seller intent.

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
11. Lifecycle audit is read-only; it must not mutate alert status or watchlist status.

Your task for Prompt 034:

Implement Alert Lifecycle Audit Trail and Operations Summary v1.

## 1. Lifecycle audit module

Create a module, for example:

```text
src/marketsentry/cross_site_alert_lifecycle.py
```

Required models:

- CrossSiteAlertLifecycleEvent
- CrossSiteAlertLifecyclePropertySummary
- CrossSiteAlertLifecycleSummary
- CrossSiteAlertLifecycleReportRow
- CrossSiteAlertLifecycleRunResult

Required functions:

- load_alert_lifecycle_events(...)
- build_alert_lifecycle_for_alert(...)
- summarize_alert_lifecycle_for_property(...)
- summarize_alert_lifecycle_for_all_properties(...)
- detect_alert_lifecycle_gaps(...)
- export_cross_site_alert_lifecycle_report(...)
- format_alert_lifecycle_summary(...)

## 2. Event sources

The lifecycle should combine existing local data sources:

- cross_site_trend_alerts
  - alert creation event
  - current status
  - notes
- cross_site_alert_triage_actions
  - triage actions
  - archive actions
  - expiration actions if recorded there
- report/export manifests where practical:
  - triage exports
  - archive candidate exports
  - expiration approval exports
- optional notes parsing:
  - [triage:needs_reparse]
  - [triage:needs_manual_review]
  - [no_archive]

Do not invent data that is not present. If a source is unavailable, use empty results and warnings.

## 3. Lifecycle event normalization

Normalize events into a single event stream.

Suggested event types:

- alert_created
- triage_exported
- triage_applied
- acknowledged
- resolved
- archived
- reopened
- no_archive_marked
- needs_reparse_marked
- needs_manual_review_marked
- expiration_previewed
- expiration_approved
- archive_candidate_exported
- archive_decision_applied
- hygiene_issue_reported

Each event should include:

- event_id or generated deterministic key
- alert_id
- property_id
- candidate_id
- event_type
- previous_status
- new_status
- action
- source_workflow
- event_notes
- event_at
- source_table
- source_reference

Use neutral wording.

## 4. Property summary metrics

For each property:

- total_alerts
- total_lifecycle_events
- open_alerts
- acknowledged_alerts
- resolved_alerts
- archived_alerts
- reopened_count
- no_archive_count
- needs_reparse_count
- needs_manual_review_count
- latest_event_at
- oldest_open_alert_age_days
- unresolved_high_or_critical_count
- lifecycle_gap_count
- lifecycle_summary_label

Suggested lifecycle labels:

- no_alerts
- active_alerts
- under_review
- mostly_resolved
- archived_history
- needs_attention

Use neutral language.

## 5. Lifecycle gap detection

Identify potential workflow gaps:

- open alert older than threshold with no triage action
- needs_reparse marker with no later resolved/archive action
- needs_manual_review marker with no later acknowledged/resolved/archive action
- acknowledged alert older than threshold with no later resolution
- resolved alert older than archive threshold but not archived/no_archive
- reopened alert still open beyond threshold

These are review aids only.

Do not auto-fix gaps.

## 6. Report export

Add report export:

```text
data/exports/cross_site_alert_lifecycle_YYYYMMDD_HHMMSS.csv
```

Required columns:

- property_id
- candidate_id
- address
- city
- zip
- alert_id
- alert_type
- severity
- current_status
- event_count
- first_event_at
- latest_event_at
- latest_event_type
- lifecycle_summary_label
- lifecycle_gap_count
- gap_categories
- needs_reparse_count
- needs_manual_review_count
- no_archive_count
- recommended_review_action

Also support Markdown if easy:

```text
data/exports/cross_site_alert_lifecycle_YYYYMMDD_HHMMSS.md
```

## 7. CLI commands

Add CLI commands:

```text
marketsentry cross-site-alert-lifecycle-summary
marketsentry export-cross-site-alert-lifecycle-report
marketsentry show-cross-site-alert-lifecycle
```

### cross-site-alert-lifecycle-summary

Options:

- --db
- --property-id optional
- --alert-id optional

Output:

- properties with alerts
- active alerts
- lifecycle events
- gap counts
- needs_reparse/manual_review counts
- recommended next actions

### export-cross-site-alert-lifecycle-report

Options:

- --db
- --output-dir
- --format csv/md/both optional default csv

Output:

- report path(s)
- row count
- gap count

### show-cross-site-alert-lifecycle

Options:

- --alert-id required
- --db

Output:

- chronological event stream for one alert
- status transitions
- notes
- source workflow

Read-only.

## 8. Dashboard integration

Add **Cross-Site Alert Lifecycle** subsection to the Cross-Site Review dashboard.

Show:

- lifecycle summary metrics
- property summary table
- gap table
- latest lifecycle report
- optional alert timeline table if latest report or database data available

Dashboard remains read-only.

## 9. Watchlist/report integration

Where practical, add read-only lifecycle summary fields to watchlist monitoring report or dashboard:

- cross_site_lifecycle_label
- cross_site_lifecycle_gap_count
- cross_site_latest_alert_event_at
- cross_site_recommended_review_action

Do not change watchlist state automatically.

## 10. Tests

Add or update tests for:

- lifecycle events load with no data
- alert creation event generated
- triage action event loaded
- archive action event loaded
- expiration action event loaded if available
- no_archive marker parsed
- needs_reparse marker parsed
- needs_manual_review marker parsed
- chronological event order
- property summary metrics
- lifecycle labels
- open alert gap detection
- needs_reparse unresolved gap
- needs_manual_review unresolved gap
- acknowledged stale gap
- resolved archive candidate gap
- reopened stale gap
- lifecycle CSV report export
- lifecycle Markdown report export if implemented
- CLI lifecycle summary
- CLI export lifecycle report
- CLI show alert lifecycle
- dashboard lifecycle table loads
- no mutation behavior
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-33 tests still pass

All tests must pass.

## 11. Documentation

Update README.md and docs/RUNBOOK.md with an "Alert Lifecycle Audit Trail" section.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with:

- lifecycle audit concept
- lifecycle summary command
- lifecycle report export command
- show alert lifecycle command
- how lifecycle gaps relate to triage/archive/expiration workflows
- reminder that lifecycle audit is read-only

Update docs/ALERT_EXPIRATION_PROFILES.md with a note that expiration actions appear in lifecycle audit.

Create design decision note:

```text
docs/decisions/033-alert-lifecycle-audit-trail.md
```

Explain:

- why lifecycle audit follows triage/archive/expiration workflows
- why event normalization is read-only
- why gaps are review aids only
- why watchlist state is not automatically changed
- why Quiet Score gatekeeper is unchanged
- why walkability remains excluded

## 12. Code standards

- Python 3.11+
- PEP8 compliant.
- Type hints required.
- Docstrings required for all functions.
- Remove unused imports.
- Keep modules small and readable.
- Use Python standard library only unless existing deps suffice.
- No browser automation.
- No Playwright/Selenium.
- No bypassing CAPTCHAs, paywalls, login walls, anti-bot protections, or technical access controls.
- No network calls in tests.
- Preserve source URLs and timestamps for auditability.
- Avoid inaccurate Claude co-authorship metadata.
- Use neutral language.
- Do not make purchase recommendations.
- Do not add walkability parsing or walkability fields.

## Quality gates

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works for fresh database.
- Existing alert triage/archive/expiration workflows work.
- Lifecycle summary works.
- Lifecycle report exports.
- Dashboard lifecycle section loads.
- No Redfin source-of-truth fields are overwritten.
- Quiet gatekeeper remains unchanged.
- No real network calls are performed in tests.
- No scheduled task invokes live retrieval or lifecycle mutation.
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
8. Example cross-site-alert-lifecycle-summary output.
9. Example show-cross-site-alert-lifecycle output.
10. Example lifecycle report path and row count.
11. Example lifecycle gap output.
12. Dashboard lifecycle section added.
13. Confirmation that lifecycle audit is read-only and does not mutate alert/watchlist state.
14. Confirmation that lifecycle audit does not overwrite Redfin source-of-truth fields.
15. Confirmation that Quiet Score gatekeeper remains unchanged.
16. Confirmation that walkability fields were not added.
17. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
18. Confirmation that tests perform no real network calls.
19. Recommended next implementation step.
20. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 34 complete until all tests pass.
