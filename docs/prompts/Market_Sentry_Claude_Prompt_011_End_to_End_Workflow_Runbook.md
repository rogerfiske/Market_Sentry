# Claude Code Prompt 011 - End-to-End Operating Workflow and Runbook

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Review the current codebase and Milestone 10 implementation.
4. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
5. Keep PRD.md and Architecture.md in the project root.
6. Use src/marketsentry/ as the Python package path.
7. Do not move PRD.md or Architecture.md into docs/.
8. Do not implement live scraping, browser automation, Playwright, Selenium, or active network retrieval in this milestone.
9. Do not implement live County Recorder/Assessor access in this milestone.
10. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 11 should make the existing system operational and easy to use end-to-end.

Do not add live data retrieval yet.

The goal is to provide one coherent local workflow that exercises the existing pipeline using manual CSVs and saved fixtures:

- initialize database
- seed or import candidates
- import Redfin URLs
- parse Redfin search/detail fixtures
- enrich candidates
- export candidate review queue
- import user review decisions
- promote saved properties to watchlist
- import/parse cross-site observations
- import/parse county records
- persist Effective DOM v2
- snapshot watchlist
- export all review/monitoring reports
- generate an end-to-end run summary

This milestone is about orchestration, reliability, documentation, and usability.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It starts with Redfin candidate discovery, stages homes for human review, and then monitors user-selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, cross-site validation, county sale/ownership-transfer verification, and a separate recent Churn Index.

Critical domain rules:

1. Effective DOM v1 is listing-history-derived exposure without county reset integration.
2. Effective DOM v2 applies county-confirmed ownership transfer as a reset boundary when appropriate.
3. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
4. Churn Index measures recent 2-3 year property/listing instability and remains reportable even when Effective DOM is reset.
5. Quiet Score is the gatekeeper. Reject or heavily downgrade if Quiet Score is below threshold, even when Vibrancy is low.
6. Target is very high Quiet and very low Vibrancy.
7. Low Vibrancy alone is not sufficient.
8. Any mention of gas means the property has natural gas service/supply.
9. Walkability-type information is excluded from the initial scope.
10. Use neutral language. Do not infer seller intent.
11. Reports are analytical aids, not purchase recommendations.
12. The workflow is human-in-the-loop.

Your task for Prompt 011:

Implement End-to-End Operating Workflow and Runbook v1.

No live network calls.

## 1. End-to-end workflow orchestration module

Create a module, for example:

```text
src/marketsentry/workflow.py
```

Required functions:

- run_initial_review_workflow(...)
- run_watchlist_refresh_workflow(...)
- run_full_fixture_demo_workflow(...)
- generate_workflow_summary(...)

These functions should orchestrate existing modules and CLI-equivalent operations. They should not duplicate business logic already implemented elsewhere.

### run_initial_review_workflow

Purpose:

Prepare new candidates for user review.

Suggested steps:

1. Ensure database initialized/migrated.
2. Import Redfin URLs from CSV if file is present.
3. Parse Redfin search fixtures if directory exists.
4. Parse/enrich Redfin detail fixtures if directory exists.
5. Recalculate candidate metrics.
6. Persist Effective DOM v2 where possible.
7. Export candidate review CSV.
8. Export candidate analysis report.
9. Return structured workflow result.

### run_watchlist_refresh_workflow

Purpose:

Refresh existing watched properties using available local data.

Suggested steps:

1. Ensure database initialized/migrated.
2. Parse/enrich Redfin detail fixtures if directory exists.
3. Parse cross-site fixtures if directories exist.
4. Parse/import county fixtures or CSV if present.
5. Persist Effective DOM v2.
6. Snapshot watchlist.
7. Export watchlist monitoring report.
8. Export Effective DOM v2 report.
9. Export county verification report.
10. Return structured workflow result.

### run_full_fixture_demo_workflow

Purpose:

Run a deterministic fixture-based demonstration with test/sample data.

Suggested steps:

1. Use a configurable demo database path.
2. Initialize database.
3. Seed sample candidates.
4. Import fixture Redfin URLs if available.
5. Parse fixtures.
6. Simulate review decisions or use a supplied reviewed CSV.
7. Promote saved candidates.
8. Parse cross-site and county fixtures.
9. Persist v2.
10. Snapshot watchlist.
11. Export all reports.
12. Return a summary.

This must not depend on external websites.

## 2. Workflow result models

Create typed models for:

- WorkflowStepResult
- WorkflowRunResult
- WorkflowOutputFile
- WorkflowWarning
- WorkflowError

Fields should include:

- step_name
- status
- started_at
- completed_at
- duration_seconds
- records_processed
- records_created
- records_updated
- records_skipped
- warnings
- errors
- output_files
- notes

Use Pydantic if consistent with existing project conventions.

## 3. CLI commands

Add CLI commands:

```text
marketsentry run-initial-review-workflow
marketsentry run-watchlist-refresh-workflow
marketsentry run-fixture-demo-workflow
marketsentry workflow-status
```

### run-initial-review-workflow

Options should include:

- --db
- --redfin-urls-file
- --redfin-search-dir
- --redfin-details-dir
- --output-dir

### run-watchlist-refresh-workflow

Options should include:

- --db
- --redfin-details-dir
- --cross-site-root-dir
- --county-root-dir
- --county-records-file
- --output-dir

### run-fixture-demo-workflow

Options should include:

- --db
- --output-dir
- --reset-demo-db

This command should use sample/fixture data only.

### workflow-status

Print counts for:

- candidate_review_queue
- watched_properties
- listing_events
- cross_site_observations
- county_record_observations
- property_observation_snapshots
- latest exported reports if easy to detect

CLI output must be ASCII-safe.

## 4. Run summary output

Each workflow should produce a local summary file.

Default path:

```text
data/exports/workflow_summary_YYYYMMDD_HHMMSS.md
```

Summary should include:

- workflow name
- start/end time
- database path
- steps run
- step statuses
- records processed/created/updated/skipped
- warnings/errors
- output files created
- next recommended user action

Do not include any sensitive personal data beyond property addresses already in local inputs/reports.

## 5. Documentation/runbook

Create a user-facing runbook:

```text
docs/RUNBOOK.md
```

It should explain:

- Project purpose in plain language.
- Recommended folder layout for manual inputs.
- How to save Redfin search/detail pages as fixtures.
- How to create/import Redfin URL CSVs.
- How to create/import cross-site URL CSVs.
- How to save cross-site detail fixtures.
- How to create/import county records CSVs.
- How to save county fixtures.
- How to run the initial review workflow.
- How to review candidate CSV and mark Save/Reject/Maybe.
- How to import reviewed candidates.
- How to run watchlist refresh.
- How to interpret reports.
- How to use Effective DOM v1 vs v2.
- How to use Churn Index.
- How Quiet/Vibrancy gatekeeper works.
- What the system does not do.
- No live scraping/network access warning.

Also update README.md to link to docs/RUNBOOK.md.

## 6. Report manifest

Create a lightweight report manifest feature.

After each workflow run, write/update:

```text
data/exports/report_manifest.csv
```

Columns:

- created_at
- workflow_name
- report_type
- file_path
- row_count
- notes

Report types:

- candidate_review
- candidate_analysis
- watchlist_monitoring
- effective_dom_v2
- county_verification
- cross_site
- workflow_summary

## 7. Tests

Add or update tests for:

- WorkflowStepResult and WorkflowRunResult models.
- Workflow summary file generation.
- Report manifest append/update.
- workflow-status count collection.
- run_initial_review_workflow with sample/local fixtures.
- run_watchlist_refresh_workflow with sample/local fixtures.
- run_fixture_demo_workflow deterministic behavior.
- CLI workflow commands where practical.
- No live network call behavior.
- Existing MVP 1-10 tests still pass.

All tests must pass.

## 8. Documentation

Update README.md with:

- Milestone 11 status.
- Link to docs/RUNBOOK.md.
- CLI workflow command examples.
- Explanation that workflows are fixture/manual-input based.
- Explanation that no live scraping/network access is implemented.

Add design decision note:

```text
docs/decisions/010-end-to-end-operating-workflow.md
```

Explain:

- Why orchestration is added before live retrieval.
- Why workflows use manual inputs and saved fixtures.
- How report manifests help auditability.
- Why this improves user operations and reduces mistakes.

## 9. Code standards

- Python 3.11+
- PEP8 compliant.
- Type hints required.
- Docstrings required for all functions.
- Remove unused imports.
- Keep modules small and readable.
- No live scraping.
- No network calls.
- No Playwright/Selenium/browser automation.
- No bypassing bot protections.
- Preserve source URLs and timestamps for future auditability.
- Avoid inaccurate Claude co-authorship metadata.
- Use neutral language.
- Do not make purchase recommendations.

Quality gates:

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works for fresh database.
- Existing candidate review workflow still works.
- Existing Redfin workflows still work.
- Existing Effective DOM v1/v2 workflows still work.
- Existing cross-site workflows still work.
- Existing county workflows still work.
- Existing watchlist monitoring workflows still work.
- End-to-end workflow commands run locally with fixtures/sample data.
- Workflow summary file generated.
- Report manifest generated/updated.
- No live scraping or network calls implemented.
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
8. Any schema changes or migration fixes made.
9. Example CLI workflow used to verify Milestone 11.
10. Workflow summary output path.
11. Report manifest output path and row count.
12. List of reports generated during fixture demo.
13. Example next recommended user action from workflow summary.
14. Confirmation that no live network calls, scraping, Playwright, Selenium, or browser automation were added.
15. Recommended next implementation step.
16. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 11 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
