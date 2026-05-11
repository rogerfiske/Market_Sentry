# Claude Code Prompt 030 - Opt-In Resolved Alert Archive Policy Workflow

You are Claude Code Opus 4.6 working in Windsurf for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: a752068 (Milestone 29 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Review the codebase through commit a752068.
7. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
8. Keep PRD.md and Architecture.md in the project root.
9. Use src/marketsentry/ as the Python package path.
10. Do not move PRD.md or Architecture.md into docs/.
11. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
12. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval.
13. Do not implement new Redfin live retrieval behavior.
14. Do not run live network calls in tests.
15. Do not make scheduled tasks run live retrieval by default.
16. Do not add walkability parsing or walkability fields.
17. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

## PM direction

Milestone 30 adds an **opt-in archive policy workflow** for old resolved cross-site alerts.

This milestone must not automatically archive alerts. It must not change watchlist status. It must not overwrite Redfin source-of-truth fields. It must not infer seller intent. It is an operational alert-state workflow only.

The workflow should:

- identify old resolved alerts eligible for archive review
- export archive candidates to a user-reviewable CSV
- let the user choose archive, keep_resolved, reopen, or no_archive
- import reviewed decisions
- apply only allowed alert status changes
- preserve action history
- show archive-policy status in dashboard and reports

## Critical project rules

1. Quiet Score is the gatekeeper and must remain unchanged.
2. Cross-site data and alert state are validation/review aids only.
3. Any mention of gas means natural gas supply/service evidence.
4. Walkability information remains out of scope.
5. Reports are analytical aids, not purchase recommendations.
6. Archive policy must not change active_watch_status or any Redfin facts.

## Implement

### 1. Archive policy module

Create:

```text
src/marketsentry/cross_site_alert_archive_policy.py
```

Required models, either in models.py or the module:

- CrossSiteAlertArchiveCandidate
- CrossSiteAlertArchiveExportResult
- CrossSiteAlertArchiveImportResult
- CrossSiteAlertArchiveDecision
- CrossSiteAlertArchiveSummary

Required functions:

- identify_resolved_alert_archive_candidates(...)
- export_cross_site_alert_archive_candidates(...)
- load_cross_site_alert_archive_csv(...)
- validate_cross_site_alert_archive_decisions(...)
- apply_cross_site_alert_archive_decisions(...)
- summarize_cross_site_alert_archive_policy(...)

### 2. Archive candidate criteria

Default criteria:

- alert_status = resolved
- resolved or last-updated age >= 30 days if available
- fallback to created_at age >= 30 days when no resolved_at/updated_at exists
- exclude archived alerts
- exclude open or acknowledged alerts
- exclude alerts whose notes include `[no_archive]`

Allow threshold override:

```text
--resolved-age-days
```

Default is 30.

### 3. Archive candidate CSV

Export to:

```text
data/exports/cross_site_alert_archive_candidates_YYYYMMDD_HHMMSS.csv
```

Required columns:

- archive_export_id
- alert_id
- property_id
- candidate_id
- address
- city
- zip
- alert_type
- severity
- current_status
- created_at
- alert_age_days
- message
- recommended_action
- source_context
- existing_notes
- archive_decision
- archive_notes

Default:

```text
archive_decision = keep_resolved
```

Allowed decisions:

- keep_resolved
- archive
- reopen
- no_archive

Decision behavior:

- keep_resolved: no status change; append optional notes
- archive: status becomes archived; append notes; record action
- reopen: status becomes open; append notes; record action
- no_archive: no status change; append `[no_archive]` marker and notes; record action

### 4. Import/apply reviewed decisions

Required behavior:

- validate archive_export_id
- validate alert_id exists
- validate current_status is still resolved unless force flag is used
- validate archive_decision is allowed
- append archive_notes to alert notes
- record action in cross_site_alert_triage_actions if practical, or add a new archive action table if needed
- do not modify property, watchlist, Redfin fields, or Quiet Score
- return counts:
  - rows_read
  - valid_decisions
  - invalid_rows
  - archived
  - reopened
  - kept_resolved
  - no_archive
  - skipped_status_mismatch
  - errors

### 5. CLI commands

Add:

```text
marketsentry export-cross-site-alert-archive-candidates
marketsentry import-cross-site-alert-archive-decisions
marketsentry cross-site-alert-archive-summary
```

#### export-cross-site-alert-archive-candidates

Options:

- --db
- --output-dir
- --resolved-age-days default 30
- --property-id optional
- --severity optional

Output:

- export path
- row count
- archive_export_id
- allowed decisions

#### import-cross-site-alert-archive-decisions

Options:

- --file
- --db
- --force-status-mismatch default false

Output:

- rows read
- archived/reopened/kept/no_archive counts
- invalid/skipped counts

#### cross-site-alert-archive-summary

Options:

- --db
- --resolved-age-days default 30

Output:

- eligible archive candidates
- already archived alerts
- no_archive marked alerts
- reopened-from-archive candidates if any
- recommended next actions

### 6. Dashboard integration

Add a read-only **Cross-Site Alert Archive Policy** subsection.

Show:

- eligible archive candidate count
- archived alert count
- no_archive marked count
- latest archive candidate export if available
- latest archive/import actions if available
- table of current archive candidates

Dashboard remains read-only.

### 7. Hygiene integration

Update alert hygiene recommendations for `resolved_archive_candidate` to reference:

```text
export-cross-site-alert-archive-candidates
```

Do not auto-archive.

### 8. Scheduled scripts

Do not add scheduled auto-archive.

Ensure no scheduled script invokes:

- import-cross-site-alert-archive-decisions
- any alert-state mutation command
- --force-live
- live retrieval commands

### 9. Tests

Add tests for:

- identify archive candidates by age
- exclude open alerts
- exclude acknowledged alerts
- exclude already archived alerts
- exclude no_archive marked alerts
- export archive candidate CSV
- default archive_decision is keep_resolved
- import validates archive_export_id
- import validates alert_id exists
- import validates current_status mismatch
- force status mismatch allows apply
- archive decision sets status archived
- reopen decision sets status open
- keep_resolved does not change status
- no_archive adds marker and does not change status
- archive notes appended
- action history recorded
- CLI export-cross-site-alert-archive-candidates
- CLI import-cross-site-alert-archive-decisions
- CLI cross-site-alert-archive-summary
- dashboard archive policy table loads
- hygiene recommendation references archive workflow
- no auto-archive behavior
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-29 tests still pass

### 10. Documentation

Update:

- README.md
- docs/RUNBOOK.md
- docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md

Create:

```text
docs/decisions/029-cross-site-alert-archive-policy.md
```

Explain:

- why archive policy follows hygiene reports
- why archiving is opt-in
- why no auto-archive is implemented
- why no_archive marker exists
- why watchlist state is not automatically changed
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
- preserve URLs and timestamps for auditability
- use neutral language
- do not make purchase recommendations
- do not add walkability parsing or fields

## Quality gates

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works for fresh database.
- Existing cross-site trend alerts work.
- Existing cross-site alert analytics work.
- Existing cross-site alert triage export/import works.
- Existing alert hygiene check/report works.
- Archive candidate export/import works.
- Dashboard archive policy section loads.
- No Redfin source-of-truth fields are overwritten.
- Quiet gatekeeper remains unchanged.
- No real network calls are performed in tests.
- No scheduled task invokes live retrieval or archive mutation.
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
9. Example export-cross-site-alert-archive-candidates output.
10. Example archive candidate CSV path and row count.
11. Example import-cross-site-alert-archive-decisions output.
12. Example archive/reopen/keep_resolved/no_archive behavior.
13. Dashboard archive policy section added.
14. Hygiene recommendation update added.
15. Confirmation that archive policy does not overwrite Redfin source-of-truth fields.
16. Confirmation that archive policy does not automatically archive alerts or change watchlist status.
17. Confirmation that Quiet Score gatekeeper remains unchanged.
18. Confirmation that walkability fields were not added.
19. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
20. Confirmation that tests perform no real network calls.
21. Recommended next implementation step.
22. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 30 complete until all tests pass.
