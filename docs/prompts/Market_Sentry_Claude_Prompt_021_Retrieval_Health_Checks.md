# Claude Code Prompt 021 - Retrieval Operations Aging, Alerts, and Health Checks

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/LIVE_RETRIEVAL_STRATEGY.md.
5. Read docs/FIXTURE_CAPTURE_QUEUE.md.
6. Read docs/REDFIN_LIVE_HTTP_PHASE_1.md.
7. Read docs/REDFIN_RETRIEVED_FIXTURE_PROCESSING.md.
8. Read docs/REDFIN_PENDING_CAPTURE_BATCH_RETRIEVAL.md.
9. Read docs/REDFIN_RETRIEVAL_APPROVAL_WORKFLOW.md.
10. Review the current codebase through commit 9df9300.
11. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
12. Keep PRD.md and Architecture.md in the project root.
13. Use src/marketsentry/ as the Python package path.
14. Do not move PRD.md or Architecture.md into docs/.
15. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
16. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
17. Do not run any live network calls in tests.
18. Do not make scheduled tasks run live retrieval by default.
19. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 21 should add retrieval operations aging, alerts, and health checks.

This milestone should not broaden retrieval.

This milestone should not add new live sources.

This milestone should not schedule live retrieval.

The goal is to help the user manage retrieval operations safely by surfacing:

- stale pending fixture capture requests
- stale approval packages
- approvals that were never retrieved
- capture requests repeatedly blocked
- missing local robots policy files
- missing live retrieval config values
- audit logs with unexpected network_call_performed=true records
- old/unprocessed retrieved fixtures
- fixture processing manifest gaps
- next recommended local action

This is an observability and operator-guidance milestone.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It uses a human-in-the-loop workflow, local fixture-first retrieval, local reports, a local dashboard, and compliance-aware adapters.

Critical domain rules:

1. Effective DOM v1 is listing-history-derived exposure without county reset integration.
2. Effective DOM v2 applies county-confirmed ownership transfer as a reset boundary when appropriate.
3. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
4. Churn Index remains reportable even when Effective DOM is reset.
5. Quiet Score is the gatekeeper.
6. Use neutral language. Do not infer seller intent.
7. Reports are analytical aids, not purchase recommendations.
8. Live retrieval must remain explicit, compliant, rate-limited, auditable, fixture-output-only, and disabled by default.

Your task for Prompt 021:

Implement Retrieval Operations Aging, Alerts, and Health Checks v1.

## 1. Health check module

Create a module, for example:

```text
src/marketsentry/retrieval_health.py
```

Required models:

- RetrievalHealthIssue
- RetrievalHealthSummary
- RetrievalHealthCheckConfig
- RetrievalNextAction
- RetrievalAgingBucket

Required functions:

- run_retrieval_health_checks(...)
- check_fixture_capture_queue_aging(...)
- check_approval_package_aging(...)
- check_batch_retrieval_failures(...)
- check_retrieval_audit_anomalies(...)
- check_retrieved_fixture_processing_gaps(...)
- check_local_policy_files(...)
- generate_retrieval_next_actions(...)

## 2. Aging thresholds

Add configurable default thresholds:

- pending capture request stale after 7 days
- approval package stale after 24 hours
- dry-run approval stale after 24 hours
- retrieved fixture unprocessed after 24 hours
- repeated blocked retrieval threshold: 3 blocked attempts
- audit anomaly: any network_call_performed=true record outside explicit live retrieval commands
- missing local robots policy file warning when Redfin live retrieval is configured or capture queue is non-empty

Use safe defaults and allow overrides through function arguments or config.

## 3. Health issue severity

Use severity levels:

- info
- warning
- error
- critical

Examples:

- stale pending capture request: warning
- approved retrieval CSV older than 24 hours: warning
- missing robots policy while live retrieval enabled: error
- unexpected network_call_performed=true in audit logs: critical
- unprocessed retrieved fixture older than threshold: warning
- live retrieval enabled but contact email missing: error

## 4. CLI commands

Add CLI commands:

```text
marketsentry retrieval-health-check
marketsentry export-retrieval-health-report
```

### retrieval-health-check

Print:

- total health issues
- issue counts by severity
- stale capture requests
- stale approval packages
- unprocessed fixtures
- missing policy files
- audit anomalies
- next recommended actions

ASCII-safe.

### export-retrieval-health-report

Export Markdown and/or CSV to:

```text
data/exports/retrieval_health_YYYYMMDD_HHMMSS.md
```

or:

```text
data/exports/retrieval_health_YYYYMMDD_HHMMSS.csv
```

Include issue details and next actions.

## 5. Dashboard integration

Extend the Retrieval Operations dashboard section with a new tab:

```text
Health Checks
```

Show:

- total issues
- severity counts
- issue table
- next actions
- stale capture request count
- stale approval package count
- unprocessed fixture count
- audit anomaly count
- missing policy count

Do not add write/mutation actions in the dashboard for this milestone.

## 6. Report/manifest integration

If useful, append health report entries to report_manifest.csv as type:

```text
retrieval_health
```

Do this only if it fits existing report manifest helpers.

## 7. Tests

Add or update tests for:

- empty health check returns no critical errors
- stale pending capture request detected
- stale approval package detected
- stale dry-run approval detected
- unprocessed retrieved fixture detected
- repeated blocked retrieval detected
- missing robots policy detected
- live retrieval enabled but missing User-Agent/contact detected
- unexpected network_call_performed=true anomaly detected
- next actions generated
- retrieval-health-check CLI command
- export-retrieval-health-report CLI command
- dashboard Health Checks data loading
- no network calls
- existing MVP 1-20 tests still pass

All tests must pass.

Tests must not perform real network access.

## 8. Documentation

Update README.md and docs/RUNBOOK.md with a "Retrieval Health Checks" section.

Update docs/LIVE_RETRIEVAL_STRATEGY.md with:

- health check command
- health report
- issue severities
- stale approval guidance
- missing robots policy guidance
- audit anomaly guidance

Update docs/FIXTURE_CAPTURE_QUEUE.md with stale pending item guidance.

Update docs/REDFIN_RETRIEVAL_APPROVAL_WORKFLOW.md with stale approval guidance.

Add design decision note:

```text
docs/decisions/020-retrieval-health-checks.md
```

Explain:

- why health checks are added before expanding sources
- why stale approvals are flagged
- why network_call_performed=true records are highlighted
- why dashboard remains read-only

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
- Live retrieval disabled by default.
- Preserve source URLs and timestamps for auditability.
- Avoid inaccurate Claude co-authorship metadata.
- Use neutral language.
- Do not make purchase recommendations.

Quality gates:

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works for fresh database.
- Existing candidate review workflow still works.
- Existing Redfin fixture workflows still work.
- Existing Redfin live HTTP Phase 1 still works.
- Existing Redfin retrieved fixture processing works.
- Existing pending capture batch retrieval works.
- Existing retrieval approval workflow works.
- Existing retrieval operations dashboard works.
- Retrieval health checks work.
- Health Checks dashboard tab works.
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
8. Example retrieval-health-check output.
9. Example retrieval health report path and row/issue count.
10. Health Checks dashboard tab added.
11. Tests added for retrieval health checks.
12. Confirmation that health checks are local/read-only.
13. Confirmation that scheduled scripts do not invoke live retrieval or approved retrieval.
14. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
15. Confirmation that tests perform no real network calls.
16. Recommended next implementation step.
17. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 21 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
