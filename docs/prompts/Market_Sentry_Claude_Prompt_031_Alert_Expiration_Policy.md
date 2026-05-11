# Claude Code Prompt 031 - Configurable Alert Expiration Rules and Operator Approval Gates

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Review the current codebase through commit e5261c0.
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

Milestone 31 should add configurable local alert expiration rules and operator approval gates.

This milestone should NOT add live retrieval.

This milestone should NOT broaden scraping.

This milestone should NOT change the Quiet Score gatekeeper.

This milestone should NOT automatically archive, resolve, reopen, or delete alerts without a user-reviewed approval/import step.

The goal is to make alert lifecycle handling more systematic while preserving explicit operator control:

- define local expiration/archive rule profiles
- preview which alerts each rule would affect
- export rule preview to CSV
- require operator-edited approval CSV before applying
- apply only approved actions
- preserve alert and triage/archive history
- show policy status in dashboard and reports

This is an operational alert-state workflow only. It must not change watchlist status automatically, must not overwrite Redfin source-of-truth fields, and must not infer seller intent.

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
11. Expiration policy workflow may change alert status only after explicit user-reviewed import.
12. Expiration policy workflow must not change watchlist status automatically.

Your task for Prompt 031:

Implement Configurable Alert Expiration Rules and Operator Approval Gates v1.

## 1. Expiration policy module

Create a module, for example:

```text
src/marketsentry/cross_site_alert_expiration_policy.py
```

Required models:

- CrossSiteAlertExpirationRule
- CrossSiteAlertExpirationProfile
- CrossSiteAlertExpirationCandidate
- CrossSiteAlertExpirationPreviewResult
- CrossSiteAlertExpirationApprovalRow
- CrossSiteAlertExpirationApplyResult
- CrossSiteAlertExpirationSummary

Required functions:

- get_default_expiration_profiles(...)
- load_expiration_profile(...)
- preview_alert_expiration_policy(...)
- export_alert_expiration_approval_csv(...)
- load_alert_expiration_approval_csv(...)
- validate_alert_expiration_approvals(...)
- apply_alert_expiration_approvals(...)
- summarize_alert_expiration_policy(...)

## 2. Rule profiles

Provide safe local default profiles.

Suggested profiles:

### conservative

- resolved -> archive candidate after 90 days
- acknowledged -> review candidate after 45 days
- open warning/info alerts -> review candidate after 30 days
- high/critical open alerts are never auto-candidates for archive

### standard

- resolved -> archive candidate after 60 days
- acknowledged -> review candidate after 30 days
- open info/warning alerts -> review candidate after 21 days
- high/critical open alerts are review-only

### aggressive_review_only

- resolved -> archive candidate after 30 days
- acknowledged -> review candidate after 14 days
- open info/warning alerts -> review candidate after 14 days
- high/critical open alerts are review-only

Important:

- These profiles only generate preview/approval rows.
- They must not apply actions automatically.
- They must not affect alerts with `[no_archive]` unless the row is review-only.
- They must not archive high/critical open alerts.

## 3. Candidate action types

Supported proposed actions:

- archive
- review
- keep
- reopen_review

Suggested behavior:

- resolved old alerts -> proposed archive
- acknowledged stale alerts -> proposed review
- open info/warning stale alerts -> proposed review
- high/critical open alerts -> proposed review only
- no_archive alerts -> proposed keep or review only

Approval CSV allowed decisions:

- approve_action
- keep_current
- mark_no_archive
- reopen
- acknowledge
- resolve
- archive

Only approved decisions may mutate alert status or notes.

## 4. Approval CSV

Export to:

```text
data/exports/cross_site_alert_expiration_approval_YYYYMMDD_HHMMSS.csv
```

Required columns:

- expiration_export_id
- profile_name
- rule_name
- alert_id
- property_id
- candidate_id
- address
- city
- zip
- alert_type
- severity
- current_status
- alert_age_days
- proposed_action
- proposed_reason
- current_notes
- approval_decision
- approval_notes

Default:

```text
approval_decision = keep_current
```

Allowed decisions:

- approve_action
- keep_current
- mark_no_archive
- reopen
- acknowledge
- resolve
- archive

Decision behavior:

- approve_action: apply proposed_action if it is a mutation action; review/keep actions append notes only
- keep_current: no status change; optional notes
- mark_no_archive: append `[no_archive]`; no status change
- reopen: status open
- acknowledge: status acknowledged
- resolve: status resolved
- archive: status archived

## 5. Apply approvals

Required behavior:

- Validate expiration_export_id.
- Validate profile_name.
- Validate alert_id exists.
- Validate current_status still matches unless force flag is used.
- Validate approval_decision.
- Apply only approved decisions.
- Append approval_notes to alert notes.
- Record action in cross_site_alert_triage_actions or another existing audit/action table.
- Do not modify property, watchlist, Redfin fields, or Quiet Score.
- Return counts:
  - rows_read
  - valid_decisions
  - invalid_rows
  - approved_actions
  - archived
  - reopened
  - acknowledged
  - resolved
  - kept_current
  - marked_no_archive
  - skipped_status_mismatch
  - errors

## 6. CLI commands

Add CLI commands:

```text
marketsentry list-cross-site-alert-expiration-profiles
marketsentry preview-cross-site-alert-expiration-policy
marketsentry export-cross-site-alert-expiration-approval
marketsentry import-cross-site-alert-expiration-approval
marketsentry cross-site-alert-expiration-summary
```

### list-cross-site-alert-expiration-profiles

Output profile names and thresholds.

### preview-cross-site-alert-expiration-policy

Options:

- --profile default standard
- --db

Output:

- candidate count
- proposed archive count
- proposed review count
- proposed keep count

No mutations.

### export-cross-site-alert-expiration-approval

Options:

- --profile default standard
- --db
- --output-dir
- --property-id optional
- --severity optional

Output:

- CSV path
- row count
- expiration_export_id
- allowed decisions

### import-cross-site-alert-expiration-approval

Options:

- --file
- --db
- --force-status-mismatch default false

Output:

- rows read
- actions applied
- archived/reopened/acknowledged/resolved/kept/no_archive counts
- invalid/skipped counts

### cross-site-alert-expiration-summary

Options:

- --profile default standard
- --db

Output:

- preview summary
- already archived count
- no_archive count
- recommended next commands

## 7. Dashboard integration

Add Cross-Site Alert Expiration Policy subsection.

Show:

- available profiles
- selected/default profile summary
- candidate count by proposed action
- latest approval export if available
- no_archive count
- archived count
- table of current policy candidates

Dashboard remains read-only.

## 8. Hygiene integration

Update hygiene recommendations so resolved archive candidates may mention both:

```text
export-cross-site-alert-archive-candidates
```

and:

```text
export-cross-site-alert-expiration-approval
```

Do not auto-apply.

## 9. Scheduled scripts

Do not add scheduled mutation scripts.

It is acceptable to add a scheduled preview/report script only if it does not mutate status and does not invoke live retrieval. If added, tests must verify it does not include import commands, mutation commands, `--force-live`, or live retrieval commands.

## 10. Tests

Add or update tests for:

- default profiles exist
- conservative profile thresholds
- standard profile thresholds
- aggressive_review_only profile thresholds
- preview resolved alert archive candidate
- preview acknowledged stale review candidate
- preview open warning review candidate
- high/critical open alert review-only behavior
- no_archive alert excluded from archive mutation
- export approval CSV
- default approval_decision is keep_current
- import validates expiration_export_id
- import validates profile_name
- import validates alert_id exists
- import validates current_status mismatch
- force status mismatch allows apply
- approve_action applies proposed archive
- approve_action for review appends notes only
- mark_no_archive appends marker
- reopen sets status open
- acknowledge sets status acknowledged
- resolve sets status resolved
- archive sets status archived
- action history recorded
- CLI list profiles
- CLI preview policy
- CLI export approval
- CLI import approval
- CLI summary
- dashboard expiration policy table loads
- hygiene recommendation mentions expiration approval workflow
- no auto-apply behavior
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-30 tests still pass

All tests must pass.

## 11. Documentation

Update README.md and docs/RUNBOOK.md with a "Cross-Site Alert Expiration Policy" section.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with:

- what expiration profiles are
- how to preview a profile
- how to export approval CSV
- allowed decisions
- how to import approvals
- why no automatic policy application occurs
- reminder that expiration policy does not change watchlist status

Update docs/WINDOWS_TASK_SCHEDULER.md only if adding a scheduled preview/report script.

Create design decision note:

```text
docs/decisions/030-cross-site-alert-expiration-policy.md
```

Explain:

- why expiration policy follows archive policy
- why profiles are local heuristics
- why approval gates are required
- why high/critical alerts are review-only
- why no auto-apply is implemented
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
- Existing cross-site alert archive workflow works.
- Existing alert hygiene check/report works.
- Expiration profile preview works.
- Expiration approval export/import works.
- Dashboard expiration policy section loads.
- No Redfin source-of-truth fields are overwritten.
- Quiet gatekeeper remains unchanged.
- No real network calls are performed in tests.
- No scheduled task invokes live retrieval or expiration mutation.
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
9. Example list-cross-site-alert-expiration-profiles output.
10. Example preview-cross-site-alert-expiration-policy output.
11. Example approval CSV path and row count.
12. Example import-cross-site-alert-expiration-approval output.
13. Example behavior for approve_action, keep_current, mark_no_archive, reopen, acknowledge, resolve, archive.
14. Dashboard expiration policy section added.
15. Hygiene recommendation update added.
16. Confirmation that expiration policy does not overwrite Redfin source-of-truth fields.
17. Confirmation that expiration policy does not automatically apply actions or change watchlist status.
18. Confirmation that Quiet Score gatekeeper remains unchanged.
19. Confirmation that walkability fields were not added.
20. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
21. Confirmation that tests perform no real network calls.
22. Recommended next implementation step.
23. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 31 complete until all tests pass.
