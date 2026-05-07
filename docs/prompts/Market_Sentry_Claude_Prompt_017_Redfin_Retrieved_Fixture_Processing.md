# Claude Code Prompt 017 - Redfin Retrieved Fixture Processing Pipeline

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/LIVE_RETRIEVAL_STRATEGY.md.
5. Read docs/FIXTURE_CAPTURE_QUEUE.md.
6. Read docs/REDFIN_LIVE_HTTP_PHASE_1.md.
7. Review the current codebase through commit d8ed591.
8. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
9. Keep PRD.md and Architecture.md in the project root.
10. Use src/marketsentry/ as the Python package path.
11. Do not move PRD.md or Architecture.md into docs/.
12. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
13. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
14. Do not run any live network calls in tests.
15. Do not make scheduled tasks run live retrieval by default.
16. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 17 should connect Redfin live-retrieved fixtures to the existing local fixture parsing pipeline.

Milestone 16 can retrieve Redfin HTML and save it as local fixtures. Milestone 17 should add an explicit post-retrieval processing workflow:

- process newly saved Redfin search fixtures
- process newly saved Redfin property detail fixtures
- insert discovered candidates into candidate_review_queue
- enrich candidate details
- recalculate Effective DOM v1/v2
- export candidate review and candidate analysis reports
- optionally clear or mark fixture capture queue items as captured when matching fixture files exist

Do not expand live retrieval to other sources.

Do not make retrieval automatic in scheduled tasks.

Live retrieval remains opt-in and disabled by default.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It starts with Redfin candidate discovery, stages homes for human review, and then monitors user-selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, cross-site validation, county sale/ownership-transfer verification, a separate recent Churn Index, local reports, a local dashboard, local workflow automation, and compliance-aware source adapters.

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
13. Live retrieval must be explicit, compliant, rate-limited, auditable, and disabled by default.

Your task for Prompt 017:

Implement Redfin Retrieved Fixture Processing Pipeline v1.

No new live retrieval sources.

## 1. Retrieved fixture metadata handling

Milestone 16 saves retrieved Redfin HTML fixtures with sidecar JSON metadata.

Implement a robust metadata loader.

Suggested module:

```text
src/marketsentry/retrieved_fixture_processor.py
```

Required models:

- RetrievedFixtureMetadata
- RetrievedFixtureRecord
- RetrievedFixtureProcessingResult
- RedfinFixtureProcessingRunResult

Required behavior:

- Load Redfin search fixture HTML files and sidecar metadata JSON files.
- Load Redfin property detail fixture HTML files and sidecar metadata JSON files.
- Handle missing metadata gracefully.
- Distinguish:
  - search fixture
  - property detail fixture
  - unknown Redfin fixture
- Preserve:
  - source_url
  - retrieval_timestamp
  - retrieval_mode
  - network_call_performed
  - audit record reference if present
  - fixture path
  - metadata path

## 2. Process Redfin search fixtures

Implement function:

```text
process_redfin_search_fixtures(...)
```

Required behavior:

- Parse files from:
  - data/raw/redfin/search/
- Use existing Redfin search fixture parser.
- Insert discovered candidates into candidate_review_queue.
- Deduplicate using existing candidate insertion logic.
- Record processing status.
- Do not overwrite user_decision or user_notes.
- Output counts:
  - files scanned
  - files processed
  - candidates discovered
  - candidates inserted
  - duplicates skipped
  - warnings
  - errors

## 3. Process Redfin detail fixtures

Implement function:

```text
process_redfin_detail_fixtures(...)
```

Required behavior:

- Parse files from:
  - data/raw/redfin/details/
- Use existing Redfin detail parser and enrichment workflow.
- Match by Redfin URL/home ID/address where possible.
- Enrich candidate_review_queue.
- Insert listing_events without duplicates.
- Do not overwrite user_decision or user_notes.
- Output counts:
  - files scanned
  - files processed
  - details parsed
  - candidates matched
  - candidates enriched
  - listing events inserted
  - duplicates skipped
  - warnings
  - errors

## 4. Integrated Redfin fixture processing workflow

Implement function:

```text
process_redfin_retrieved_fixtures(...)
```

Suggested behavior:

1. Process Redfin search fixtures.
2. Process Redfin detail fixtures.
3. Recalculate candidates.
4. Persist Effective DOM v2.
5. Export candidate review CSV.
6. Export candidate analysis report.
7. Optionally mark matching fixture capture queue items as captured.
8. Return structured run result.

Do not run live retrieval inside this function.

## 5. Fixture processing manifest

Create or update a processing manifest:

```text
data/processed/redfin_fixture_processing_manifest.csv
```

Columns:

- processed_at
- fixture_path
- metadata_path
- source_url
- fixture_type
- status
- candidates_discovered
- candidates_inserted
- candidates_enriched
- listing_events_inserted
- warnings
- errors
- content_hash

Required behavior:

- Append-only.
- Avoid reprocessing unchanged fixtures by default using content hash.
- Allow force reprocess via CLI flag.
- Do not delete fixture files.

## 6. Fixture capture queue integration

If possible, integrate with Milestone 15 fixture capture queue.

Required behavior:

- If fixture metadata source_url matches pending capture queue request, mark captured when successfully processed.
- If no match, do nothing.
- Report captures marked.
- Do not mark failed parses as captured.

## 7. CLI commands

Add CLI commands:

```text
marketsentry process-redfin-retrieved-fixtures
marketsentry process-redfin-search-fixtures
marketsentry process-redfin-detail-fixtures
```

### process-redfin-retrieved-fixtures

Options:

- --db
- --search-dir
- --details-dir
- --output-dir
- --force-reprocess

Output:

- files scanned
- files processed
- candidates discovered
- candidates inserted
- candidates enriched
- listing events inserted
- reports exported
- capture queue items marked
- manifest path

### process-redfin-search-fixtures

Search-only processing.

### process-redfin-detail-fixtures

Detail-only processing.

CLI output must be ASCII-safe.

## 8. Optional safe convenience workflow

Add optional CLI command:

```text
marketsentry retrieve-and-process-redfin-property
```

Only if this can be implemented safely without broadening scope.

Behavior:

- Accept --url
- Require --force-live for live retrieval.
- If live retrieval succeeds, immediately process the saved fixture.
- If live retrieval is blocked, add fixture capture queue request.
- Must still follow all Milestone 16 guardrails.
- Tests must use fake HTTP client or avoid live path.

If this adds too much complexity, defer it and document why.

## 9. Tests

Add or update tests for:

- metadata loading with sidecar JSON
- metadata missing gracefully
- search fixture processing inserts candidates
- search fixture processing deduplicates
- detail fixture processing enriches candidates
- detail fixture processing inserts listing events without duplicates
- integrated processing workflow exports reports
- processing manifest created
- unchanged fixtures skipped by default
- force reprocess behavior
- fixture capture queue item marked captured when matching fixture processed
- CLI process-redfin-retrieved-fixtures command
- CLI process-redfin-search-fixtures command
- CLI process-redfin-detail-fixtures command
- no live network calls
- existing MVP 1-16 tests still pass

All tests must pass.

Tests must not perform real network access.

## 10. Documentation

Update README.md and docs/RUNBOOK.md with a "Processing Retrieved Redfin Fixtures" section.

Update docs/REDFIN_LIVE_HTTP_PHASE_1.md with:

- how retrieved fixtures are processed
- how to run process-redfin-retrieved-fixtures
- how processing manifest works
- how capture queue items are marked captured
- how to continue using manual fixtures instead

Create:

```text
docs/REDFIN_RETRIEVED_FIXTURE_PROCESSING.md
```

Explain:

- purpose of processing retrieved fixtures
- expected fixture directories
- metadata sidecar files
- processing manifest
- skip/reprocess behavior
- candidate insertion and enrichment
- report generation
- no live retrieval in processing step

Add design decision note:

```text
docs/decisions/016-redfin-retrieved-fixture-processing.md
```

Explain:

- why retrieval saves fixtures first
- why parsing is a separate step
- why direct database mutation from HTTP response is avoided
- why manifest-based idempotency is used
- why capture queue integration is useful

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
- Live retrieval remains disabled by default.
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
- Existing Effective DOM v1/v2 workflows still work.
- Existing cross-site workflows still work.
- Existing county workflows still work.
- Existing watchlist monitoring workflows still work.
- Existing dashboard/report viewer still works.
- Existing Windows automation still works.
- Existing retrieval compliance/policy/fixture capture queue still works.
- Retrieved fixture processing works.
- Processing manifest works.
- Capture queue integration works if implemented.
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
8. Example process-redfin-retrieved-fixtures output.
9. Example processing manifest path and row count.
10. Example candidate insertion/enrichment counts.
11. Example capture queue item marked captured if implemented.
12. Confirmation that processing step itself performs no live retrieval.
13. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
14. Confirmation that tests perform no real network calls.
15. Recommended next implementation step.
16. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 17 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
