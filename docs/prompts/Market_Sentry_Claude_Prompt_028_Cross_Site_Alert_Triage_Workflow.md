# Claude Code Prompt 028 - Cross-Site Alert Triage Workflow

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
5. Review the current codebase through commit 1cfaf34.
6. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
7. Keep PRD.md and Architecture.md in the project root.
8. Use src/marketsentry/ as the Python package path.
9. Do not move PRD.md or Architecture.md into docs/.
10. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
11. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
12. Do not implement new Redfin live retrieval behavior in this milestone.
13. Do not run any live network calls in tests.
14. Do not make scheduled tasks run live retrieval by default.
15. Do not add walkability parsing or walkability fields.
16. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 28 should add a local cross-site alert triage workflow.

This milestone should NOT add live retrieval.

This milestone should NOT broaden scraping.

This milestone should NOT change the Quiet Score gatekeeper.

The goal is to help the user review and manage accumulated cross-site alerts:

- filter alert sets
- export a triage CSV
- manually edit triage decisions
- import decisions
- batch acknowledge/resolve/archive selected alerts
- preserve alert history
- generate a triage summary
- update dashboard/read-only visibility of triage state

Triage actions are operational alert-state changes only. They must not change watchlist status automatically, must not overwrite Redfin source-of-truth fields, and must not infer seller intent.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It uses a human-in-the-loop, fixture-first workflow to observe candidate and watched properties using Effective DOM v1/v2, Churn Index, Quiet/Vibrancy gatekeeper logic, gas evidence, garage spaces, cross-site validation, county verification, local reports, dashboard views, and compliance-aware retrieval operations.

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
11. Cross-site alert triage changes alert status only; it must not alter Redfin facts or watchlist status.

Your task for Prompt 028:

Implement Cross-Site Alert Triage Workflow v1.

## 1. Triage module

Create a module, for example:

```text
src/marketsentry/cross_site_alert_triage.py
```

Required models:

- CrossSiteAlertTriageRow
- CrossSiteAlertTriageExportResult
- CrossSiteAlertTriageImportResult
- CrossSiteAlertTriageDecision
- CrossSiteAlertTriageSummary

Required functions:

- export_cross_site_alert_triage_csv(...)
- load_cross_site_alert_triage_csv(...)
- validate_cross_site_alert_triage_decisions(...)
- apply_cross_site_alert_triage_decisions(...)
- summarize_cross_site_alert_triage(...)
- filter_alerts_for_triage(...)

## 2. Triage export CSV

Export filtered alert rows to:

```text
data/exports/cross_site_alert_triage_YYYYMMDD_HHMMSS.csv
```

Required columns:

- triage_export_id
- alert_id
- property_id
- candidate_id
- address
- city
- zip
- alert_type
- severity
- current_status
- trend_direction
- message
- recommended_action
- source_context
- created_at
- alert_age_days
- alert_burden_label
- repeated_patterns
- triage_decision
- triage_notes

Default:

```text
triage_decision = keep_open
```

Allowed triage decisions:

- keep_open
- acknowledge
- resolve
- archive
- needs_reparse
- needs_manual_review

Only these should change alert state:

- acknowledge -> alert_status acknowledged
- resolve -> alert_status resolved
- archive -> alert_status archived

These should not change alert state:

- keep_open
- needs_reparse
- needs_manual_review

But they should be recorded in notes/history.

## 3. Triage import/apply

Import user-edited CSV and apply valid decisions.

Required behavior:

- Validate triage_export_id.
- Validate alert_id exists.
- Validate current_status still matches unless a force flag is provided.
- Validate triage_decision is allowed.
- Append triage_notes to alert notes.
- Do not modify property, watchlist, Redfin fields, or Quiet Score.
- Return counts:
  - rows_read
  - valid_decisions
  - invalid_rows
  - acknowledged
  - resolved
  - archived
  - kept_open
  - needs_reparse
  - needs_manual_review
  - skipped_status_mismatch
  - errors

## 4. Optional triage history

If useful, add table:

```text
cross_site_alert_triage_actions
```

Suggested columns:

- triage_action_id
- triage_export_id
- alert_id
- property_id
- action
- previous_status
- new_status
- triage_notes
- applied_at

If implemented, migration must be idempotent.

If not implemented, explain in completion report why alert notes are sufficient for v1.

## 5. CLI commands

Add CLI commands:

```text
marketsentry export-cross-site-alert-triage
marketsentry import-cross-site-alert-triage
```

### export-cross-site-alert-triage

Options:

- --db
- --output-dir
- --status optional default open
- --severity optional
- --property-id optional
- --include-acknowledged optional default false

Output:

- export path
- row count
- triage_export_id
- allowed decisions

### import-cross-site-alert-triage

Options:

- --file
- --db
- --force-status-mismatch optional default false

Output:

- rows read
- decisions applied
- acknowledged/resolved/archived counts
- skipped/invalid counts

## 6. Dashboard integration

Add a read-only Cross-Site Alert Triage subsection to dashboard.

Show:

- latest triage export path
- pending open alerts count
- acknowledged/resolved/archived counts
- needs_reparse count if available from notes/history
- needs_manual_review count if available from notes/history
- recent triage actions if history table implemented

Dashboard remains read-only in this milestone.

## 7. Tests

Add or update tests for:

- triage export creates CSV
- exported rows include required columns
- default triage_decision is keep_open
- filtering by status/severity/property_id
- import validates triage_export_id
- import validates alert_id exists
- import validates current_status mismatch
- force status mismatch allows apply
- acknowledge decision updates status
- resolve decision updates status
- archive decision updates status
- keep_open does not change status
- needs_reparse does not change status but notes recorded
- needs_manual_review does not change status but notes recorded
- invalid triage decision rejected
- optional triage history rows if implemented
- CLI export-cross-site-alert-triage
- CLI import-cross-site-alert-triage
- dashboard triage summary loads
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-27 tests still pass

All tests must pass.

## 8. Documentation

Update README.md and docs/RUNBOOK.md with a "Cross-Site Alert Triage" section.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with:

- how to export triage CSV
- how to edit triage_decision
- how to import triage decisions
- allowed decisions
- what changes alert status and what does not
- reminder that triage is not a purchase recommendation

Create design decision note:

```text
docs/decisions/027-cross-site-alert-triage-workflow.md
```

Explain:

- why triage is CSV-based
- why dashboard remains read-only
- why only acknowledge/resolve/archive change alert status
- why watchlist state is not automatically changed
- why Quiet Score gatekeeper is unchanged
- why walkability remains excluded

## 9. Code standards

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
- Existing candidate review workflow still works.
- Existing cross-site trend alerts work.
- Existing cross-site alert analytics work.
- Cross-site alert triage export/import works.
- Dashboard triage summary loads.
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
8. Schema changes or migration details.
9. Example export-cross-site-alert-triage output.
10. Example triage CSV path and row count.
11. Example import-cross-site-alert-triage output.
12. Example status transitions for acknowledge/resolve/archive.
13. Example needs_reparse or needs_manual_review behavior.
14. Dashboard triage summary added.
15. Confirmation that triage does not overwrite Redfin source-of-truth fields.
16. Confirmation that Quiet Score gatekeeper remains unchanged.
17. Confirmation that walkability fields were not added.
18. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
19. Confirmation that tests perform no real network calls.
20. Recommended next implementation step.
21. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 28 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
