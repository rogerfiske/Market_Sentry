# Claude Code Prompt 020 - Retrieval Operations Dashboard Integration

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository:

https://github.com/rogerfiske/Market_Sentry

Local project folder:

C:\Users\Minis\CascadeProjects\Market_Sentry

Current accepted milestones:

- Milestone 1 scaffold complete at commit c8599761be1aeda80b075cf668c61970e587ebe7
- Milestone 2 candidate review queue and watchlist promotion complete at commit 5da7747a44069696189d1abb8057ee23f17d8754
- Milestone 3 Redfin discovery adapter foundation complete at commit 91eac91085609c38f150881bf35e5a22d1abb8057ee23f17d8754
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
10. Review the current codebase through commit 66628f6.
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

Milestone 20 should improve operator visibility and safety by integrating retrieval operations into the existing local dashboard and CLI summaries.

Do not broaden live retrieval.

Do not add any new live retrieval source.

Do not add automatic scheduled live retrieval.

The goal is to let the user review the retrieval ecosystem locally:

- fixture capture queue
- approval packages
- approval manifests
- batch retrieval manifests
- per-item retrieval manifests
- retrieval audit logs
- dry-run approvals
- blocked reasons
- retrieved fixture files
- processing manifest
- compliance status

This is a read/visibility/reporting milestone, not a new retrieval implementation milestone.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It starts with Redfin candidate discovery, stages homes for human review, and then monitors user-selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, cross-site validation, county sale/ownership-transfer verification, a separate recent Churn Index, local reports, a local dashboard, local workflow automation, compliance-aware source adapters, and safe fixture-first retrieval workflows.

Critical domain rules:

1. Effective DOM v1 is listing-history-derived exposure without county reset integration.
2. Effective DOM v2 applies county-confirmed ownership transfer as a reset boundary when appropriate.
3. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
4. Churn Index measures recent 2-3 year property/listing instability and remains reportable even when Effective DOM is reset.
5. Quiet Score is the gatekeeper. Reject or heavily downgrade if Quiet Score is below threshold, even when Vibrancy is low.
6. Target is very high Quiet and very low Vibrancy.
7. Low Vibrancy alone is not sufficient.
8. Any mention of gas means the property has natural gas supply/service.
9. Walkability-type information is excluded from the initial scope.
10. Use neutral language. Do not infer seller intent.
11. Reports are analytical aids, not purchase recommendations.
12. The workflow is human-in-the-loop.
13. Live retrieval must be explicit, compliant, rate-limited, auditable, fixture-output-only, and disabled by default.

Your task for Prompt 020:

Implement Retrieval Operations Dashboard Integration v1.

## 1. Dashboard retrieval operations data model

Extend or create local dashboard data-loading helpers.

Suggested module additions:

```text
src/marketsentry/dashboard.py
```

or a new module:

```text
src/marketsentry/retrieval_dashboard.py
```

Required typed models:

- RetrievalOperationsSummary
- FixtureCaptureQueueTable
- RetrievalApprovalPackageTable
- BatchRetrievalManifestTable
- RetrievalAuditSummaryTable
- RetrievedFixtureInventoryTable

Required helper functions:

- get_retrieval_operations_summary(...)
- load_fixture_capture_queue_table(...)
- load_retrieval_approval_manifest(...)
- load_latest_retrieval_approval_packages(...)
- load_batch_retrieval_manifest(...)
- load_batch_retrieval_items(...)
- load_retrieval_audit_summary(...)
- load_dry_run_approval_summary(...)
- load_retrieved_fixture_inventory(...)
- build_retrieval_operations_tables(...)

These helpers should be testable without launching Streamlit.

## 2. Dashboard sections

Update the Streamlit dashboard to add a new main section:

```text
Retrieval Operations
```

Subsections/tabs should include:

### Overview

Show:

- pending fixture capture requests
- captured fixture requests
- skipped/invalid/archived capture requests
- approval packages created
- approved rows pending retrieval
- batch retrieval runs
- retrieved fixture count
- blocked retrieval decisions
- audit records with network_call_performed=true
- audit records with network_call_performed=false
- latest retrieval audit file
- latest approval package
- latest batch manifest

### Fixture Capture Queue

Table columns:

- capture_request_id
- created_at
- source_site
- request_type
- source_url
- suggested_fixture_path
- status
- priority
- reason
- notes

Filters:

- source_site
- request_type
- status
- priority

### Approval Packages

Table from approval manifest:

- approval_run_id
- created_at
- pending_scanned
- approval_rows_written
- approval_csv_path
- approval_summary_path
- approved_count_when_imported
- retrieved_count
- blocked_count
- failed_count
- notes

Also list latest approval CSV files from:

```text
data/exports/retrieval_approvals/
```

### Batch Retrieval Runs

Table from:

```text
data/processed/redfin_batch_retrieval_manifest.csv
```

Show:

- run_id
- started_at
- completed_at
- mode
- pending_scanned
- attempted_live
- retrieved
- blocked
- failed
- fixtures_saved
- processed_after_retrieval
- queue_items_marked_captured

### Per-Item Retrieval Results

Table from:

```text
data/processed/redfin_batch_retrieval_items.csv
```

Show:

- run_id
- capture_request_id
- source_url
- request_type
- decision
- network_call_performed
- fixture_path
- status
- reason
- error

### Retrieval Audit

Summarize audit logs under:

```text
logs/retrieval_audit/
```

Show:

- total records
- allowed
- blocked
- dry runs
- live attempts
- network_call_performed=true count
- network_call_performed=false count
- blocked reasons
- latest audit file

### Retrieved Fixture Inventory

Scan:

```text
data/raw/redfin/search/
data/raw/redfin/details/
```

Show:

- fixture_path
- fixture_type
- metadata_path
- source_url
- retrieved_at
- network_call_performed
- content_hash if easy
- processed status from processing manifest

## 3. CLI retrieval operations summary

Add CLI command:

```text
marketsentry retrieval-operations-summary
```

Output:

- pending capture requests
- approval packages
- batch runs
- retrieved fixtures
- audit records
- live network call records
- blocked records
- latest files

ASCII-safe.

## 4. Optional export report

Add optional CLI command:

```text
marketsentry export-retrieval-operations-report
```

Export CSV or Markdown report to:

```text
data/exports/retrieval_operations_YYYYMMDD_HHMMSS.csv
```

or:

```text
data/exports/retrieval_operations_YYYYMMDD_HHMMSS.md
```

If implemented, include summary + key tables.

If too much scope, defer and document why.

## 5. Safety indicators

The dashboard and CLI should clearly show:

- live retrieval disabled/enabled status
- allowed sources
- User-Agent configured yes/no
- contact email configured yes/no
- dry-run required yes/no
- max requests per minute
- no scheduled live retrieval indicator if easy to verify

Use neutral, operational wording.

## 6. Tests

Add or update tests for:

- retrieval operations summary with empty data
- retrieval operations summary with sample fixture queue items
- approval manifest loading
- batch manifest loading
- batch item manifest loading
- audit log summary loading
- dry-run approval summary loading
- retrieved fixture inventory loading
- dashboard table builders
- retrieval-operations-summary CLI command
- optional export report if implemented
- no network calls
- existing MVP 1-19 tests still pass

All tests must pass.

Tests must not perform real network access.

## 7. Documentation

Update README.md and docs/RUNBOOK.md with a "Retrieval Operations Dashboard" section.

Update docs/REDFIN_RETRIEVAL_APPROVAL_WORKFLOW.md with how to view approvals in the dashboard.

Update docs/REDFIN_PENDING_CAPTURE_BATCH_RETRIEVAL.md with how to view manifests in the dashboard.

Update docs/FIXTURE_CAPTURE_QUEUE.md with how to view capture queue in the dashboard.

Add design decision note:

```text
docs/decisions/019-retrieval-operations-dashboard.md
```

Explain:

- why retrieval operations visibility is added before expanding sources
- why dashboard is read-only for retrieval operations in this milestone
- why live retrieval remains manually invoked only
- how visibility reduces operator mistakes

## 8. Code standards

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
- Existing Effective DOM v1/v2 workflows still work.
- Existing cross-site workflows still work.
- Existing county workflows still work.
- Existing watchlist monitoring workflows still work.
- Existing dashboard/report viewer still works.
- Retrieval operations dashboard data loading works.
- Retrieval operations CLI summary works.
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
8. Dashboard sections added.
9. Example retrieval-operations-summary output.
10. Example retrieval operations report path and row count if implemented.
11. Tests added for retrieval operations data loading.
12. Confirmation that retrieval operations dashboard is local/read-only for this milestone.
13. Confirmation that scheduled scripts do not invoke live retrieval or approved retrieval.
14. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
15. Confirmation that tests perform no real network calls.
16. Recommended next implementation step.
17. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 20 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
