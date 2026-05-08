# Claude Code Prompt 022 - Cross-Site Adapter Parity and Manual Fixture Workflow

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
10. Review the current codebase through commit c92f687.
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

Milestone 22 should add cross-site adapter parity and manual fixture workflow support for Zillow, Realtor.com, Homes.com, and Compass.

This milestone should NOT add live HTTP retrieval for those sources.

The goal is to bring non-Redfin sources up to the same safe local workflow pattern:

- dry-run preview
- fixture capture queue request creation
- local saved fixture processing
- processing manifest
- dashboard/health visibility
- cross-site report integration

This milestone is about operational parity for manual fixtures and dry-run planning, not broad source scraping.

Redfin remains the only source with live HTTP Phase 1 support, and even Redfin live retrieval remains disabled by default and manually approved.

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
11. Live retrieval must remain explicit, compliant, rate-limited, auditable, fixture-output-only, and disabled by default.

Your task for Prompt 022:

Implement Cross-Site Adapter Parity and Manual Fixture Workflow v1.

## 1. Cross-site adapter dry-run parity

Extend existing non-Redfin source adapters:

```text
src/marketsentry/source_adapters/zillow_adapter.py
src/marketsentry/source_adapters/realtor_adapter.py
src/marketsentry/source_adapters/homes_adapter.py
src/marketsentry/source_adapters/compass_adapter.py
```

Required behavior for each source:

- validate URL/domain
- infer request type:
  - property_detail
  - search if the source supports a search URL pattern
  - unknown
- provide dry-run preview
- add fixture capture request when live retrieval is blocked/not implemented
- write retrieval audit record with network_call_performed=false
- return structured RetrievalResult
- live retrieve methods must return blocked/not_implemented
- no network call
- no browser automation

Source domain validation examples:

- Zillow:
  - zillow.com
  - www.zillow.com
- Realtor.com:
  - realtor.com
  - www.realtor.com
- Homes.com:
  - homes.com
  - www.homes.com
- Compass:
  - compass.com
  - www.compass.com

Use conservative URL validation. If uncertain, block and recommend manual fixture capture.

## 2. Cross-site fixture capture queue integration

Ensure dry-run preview for each non-Redfin source creates or can create a fixture capture queue request with appropriate suggested path:

```text
data/raw/zillow/details/
data/raw/realtor/details/
data/raw/homes/details/
data/raw/compass/details/
```

If a search URL is supported, suggested paths should be:

```text
data/raw/zillow/search/
data/raw/realtor/search/
data/raw/homes/search/
data/raw/compass/search/
```

If search parsing is not yet supported for a source, dry-run should explain that property detail fixtures are supported first and search fixture support is not implemented.

## 3. Cross-site fixture processing manifest

Milestone 6 implemented cross-site fixture parsing/enrichment. Add or improve a processing manifest for cross-site fixtures:

```text
data/processed/cross_site_fixture_processing_manifest.csv
```

Columns:

- processed_at
- source_site
- fixture_path
- source_url
- fixture_type
- status
- observations_inserted
- candidates_matched
- watched_properties_matched
- warnings
- errors
- content_hash

Required behavior:

- Append-only.
- Avoid reprocessing unchanged fixtures by default using content hash.
- Allow force reprocess via CLI flag.
- Do not delete fixture files.
- Work for:
  - zillow
  - realtor
  - homes
  - compass

## 4. Cross-site retrieved/manual fixture processor

Create or extend a processor module, for example:

```text
src/marketsentry/cross_site_fixture_processor.py
```

Required models:

- CrossSiteFixtureMetadata
- CrossSiteFixtureRecord
- CrossSiteFixtureProcessingResult
- CrossSiteFixtureProcessingRunResult

Required functions:

- load_cross_site_fixture_metadata(...)
- scan_cross_site_fixtures(...)
- process_cross_site_fixtures(...)
- process_cross_site_source_fixtures(...)
- write_cross_site_processing_manifest(...)

Required behavior:

- Process saved HTML fixtures from existing directories.
- Use existing source-specific parsers from Milestone 6.
- Insert cross_site_observations.
- Deduplicate observations using existing logic.
- Match by source URL, Redfin URL if available, normalized address, candidate_id, or property_id where possible.
- Do not overwrite Redfin source-of-truth data.
- Do not overwrite user_decision, user_notes, active_watch_status, or watch_priority.
- Mark matching fixture capture queue items as captured only after successful processing.
- Output counts:
  - files scanned
  - files processed
  - observations inserted
  - matched candidates
  - matched watched properties
  - duplicates skipped
  - queue items marked captured
  - warnings
  - errors

## 5. CLI commands

Add CLI commands:

```text
marketsentry dry-run-cross-site-property
marketsentry process-cross-site-fixtures
marketsentry process-cross-site-source-fixtures
```

### dry-run-cross-site-property

Options:

- --source
- --url
- --db optional
- --output optional

Behavior:

- source values:
  - zillow
  - realtor
  - homes
  - compass
- Validate URL.
- Show dry-run preview.
- Create or show fixture capture queue request.
- No network call.

### process-cross-site-fixtures

Options:

- --root-dir optional
- --db optional
- --output-dir optional
- --force-reprocess optional

Behavior:

- Process all supported source fixture directories.
- Write manifest.
- Mark captured queue items when processing succeeds.
- Export cross-site report if practical.
- No network call.

### process-cross-site-source-fixtures

Options:

- --source
- --dir
- --db optional
- --output-dir optional
- --force-reprocess optional

Behavior:

- Process one source.
- Write manifest.
- No network call.

## 6. Dashboard and health integration

Update Retrieval Operations dashboard and health checks to include cross-site fixture processing manifest.

Dashboard should show:

- cross-site fixtures processed
- cross-site fixture processing errors
- source breakdown by zillow/realtor/homes/compass
- unprocessed cross-site fixtures older than threshold

Health checks should include:

- unprocessed cross-site fixture warning
- stale cross-site fixture capture request warning
- missing source parser warning only if relevant

Do not add dashboard write/mutation actions.

## 7. Tests

Add or update tests for:

- Zillow dry-run property URL validates and creates capture request
- Realtor dry-run property URL validates and creates capture request
- Homes dry-run property URL validates and creates capture request
- Compass dry-run property URL validates and creates capture request
- invalid domain is blocked
- dry-run performs no network call
- live retrieval returns blocked/not_implemented for non-Redfin sources
- cross-site fixture scan finds fixtures
- cross-site fixture processing inserts observations
- cross-site fixture processing deduplicates unchanged files
- force reprocess behavior
- manifest written
- queue item marked captured only after successful processing
- dashboard includes cross-site processing manifest data
- health check detects unprocessed cross-site fixture
- CLI dry-run-cross-site-property
- CLI process-cross-site-fixtures
- CLI process-cross-site-source-fixtures
- no real network calls in tests
- existing MVP 1-21 tests still pass

All tests must pass.

## 8. Documentation

Update README.md and docs/RUNBOOK.md with a "Cross-Site Manual Fixture Workflow" section.

Create:

```text
docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md
```

Explain:

- what sources are supported
- how to dry-run a cross-site property URL
- how fixture capture requests are created
- where to save fixtures
- how to process cross-site fixtures
- how cross-site observations feed reports
- no live retrieval for these sources
- Redfin remains the only source with Live HTTP Phase 1 support

Update docs/FIXTURE_CAPTURE_QUEUE.md with cross-site examples.

Update docs/LIVE_RETRIEVAL_STRATEGY.md to clarify that non-Redfin adapters are dry-run/manual-fixture only.

Add design decision note:

```text
docs/decisions/021-cross-site-adapter-parity-manual-fixtures.md
```

Explain:

- why cross-site sources get manual fixture parity before live retrieval
- why Redfin remains the only live HTTP Phase 1 source
- why search fixture support may be limited
- why cross-site data does not overwrite Redfin source-of-truth fields

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
- Existing Redfin fixture/live/approval workflows still work.
- Existing retrieval health checks still work.
- Existing dashboard/report viewer still works.
- Cross-site dry-run commands work.
- Cross-site fixture processing works.
- Cross-site processing manifest works.
- Capture queue integration works.
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
8. Example dry-run-cross-site-property output.
9. Example cross-site fixture processing output.
10. Cross-site processing manifest path and row count.
11. Capture queue item marked captured example.
12. Dashboard/health updates added.
13. Confirmation that non-Redfin sources remain manual-fixture/dry-run only.
14. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
15. Confirmation that tests perform no real network calls.
16. Recommended next implementation step.
17. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 22 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
