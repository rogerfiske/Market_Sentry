# Claude Code Prompt 018 - Redfin Pending Capture Batch Retrieval Orchestrator

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/LIVE_RETRIEVAL_STRATEGY.md.
5. Read docs/FIXTURE_CAPTURE_QUEUE.md.
6. Read docs/REDFIN_LIVE_HTTP_PHASE_1.md.
7. Read docs/REDFIN_RETRIEVED_FIXTURE_PROCESSING.md.
8. Review the current codebase through commit e41e5e4.
9. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
10. Keep PRD.md and Architecture.md in the project root.
11. Use src/marketsentry/ as the Python package path.
12. Do not move PRD.md or Architecture.md into docs/.
13. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
14. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
15. Do not run any live network calls in tests.
16. Do not make scheduled tasks run live retrieval by default.
17. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 18 should add a controlled batch orchestrator for pending Redfin fixture capture requests.

This milestone must NOT add broad scraping.

This milestone must NOT schedule live retrieval by default.

The orchestrator should process pending capture queue items one at a time, applying the full Milestone 14-16 compliance, policy, dry-run, robots, and rate-limit guardrails for each request.

If a request is blocked, the system should leave it pending or mark it with a clear blocked status according to existing queue design.

If a request succeeds, the retrieved HTML should be saved as a local fixture, then optionally processed through the Milestone 17 fixture processing pipeline.

Tests must use fake HTTP clients only. No real network calls in tests.

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

Your task for Prompt 018:

Implement Redfin Pending Capture Batch Retrieval Orchestrator v1.

## 1. Batch retrieval scope

Supported source:

- redfin only

Supported request types:

- search
- property
- property_detail if current code uses this label

Do not add batch retrieval for:

- Zillow
- Realtor.com
- Homes.com
- Compass
- County Recorder
- Assessor
- Tax Collector
- Permit sites

## 2. Batch orchestrator module

Create a module, for example:

```text
src/marketsentry/redfin_batch_retrieval.py
```

Required models:

- BatchRetrievalItemResult
- BatchRetrievalRunResult
- BatchRetrievalConfig

Required functions:

- get_pending_redfin_capture_requests(...)
- retrieve_pending_redfin_capture_request(...)
- retrieve_pending_redfin_capture_batch(...)
- summarize_batch_retrieval_run(...)

Required behavior:

- Read pending fixture capture queue items.
- Filter to Redfin only.
- Filter by request type if requested.
- Respect max_items.
- Respect dry-run-only mode.
- Respect force-live flag.
- Apply full Redfin adapter policy checks for every item.
- Use fake/injected HTTP client in tests.
- Do not perform network call unless explicitly force-live + all checks pass.
- Save retrieved fixtures using Milestone 16 fixture save behavior.
- Optionally call Milestone 17 processing pipeline after successful retrieval.
- Mark capture queue items captured only after successful retrieval and, if processing is requested, successful processing.
- Preserve blocked/pending items with clear reason.
- Return structured counts.

## 3. Batch modes

Support modes:

### dry_run_only

- evaluates pending requests
- writes audit decisions
- does not retrieve
- does not mark captured
- may update queue notes with dry-run status only if non-destructive

### retrieve_only

- retrieves and saves fixtures
- does not process fixtures

### retrieve_and_process

- retrieves fixtures
- processes Redfin retrieved fixtures using Milestone 17 pipeline
- exports reports as applicable
- marks queue items captured after success

Default should be dry_run_only unless explicitly overridden.

## 4. CLI commands

Add CLI commands:

```text
marketsentry retrieve-pending-redfin-fixtures
marketsentry dry-run-pending-redfin-fixtures
```

### dry-run-pending-redfin-fixtures

Options:

- --max-items
- --request-type
- --db
- --output-dir

Behavior:

- No network calls.
- Prints pending item counts.
- Prints per-item dry-run policy results.
- Writes audit records.
- Leaves queue items pending.

### retrieve-pending-redfin-fixtures

Options:

- --max-items
- --request-type
- --db
- --output-dir
- --force-live
- --process-after-retrieval
- --dry-run-only

Behavior:

- If --force-live is absent, do not retrieve; print safe blocked explanation.
- If --dry-run-only is true, behave like dry-run command.
- If --force-live is present, still require all policy checks per item.
- If --process-after-retrieval is true, process successfully saved fixtures after batch completion.
- Print:
  - pending scanned
  - dry-run only count
  - attempted live count
  - retrieved count
  - blocked count
  - failed count
  - fixtures saved
  - queue items marked captured
  - reports exported if processing occurred
  - audit log path

No scheduled script should call these commands by default.

## 5. Batch run manifest

Create append-only manifest:

```text
data/processed/redfin_batch_retrieval_manifest.csv
```

Columns:

- run_id
- started_at
- completed_at
- mode
- max_items
- request_type_filter
- pending_scanned
- attempted_live
- retrieved
- blocked
- failed
- fixtures_saved
- processed_after_retrieval
- queue_items_marked_captured
- audit_log_path
- notes

Also consider per-item manifest:

```text
data/processed/redfin_batch_retrieval_items.csv
```

Columns:

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

## 6. Safety behavior

Required:

- live retrieval disabled by default
- batch command defaults to dry run
- --force-live required for any network call
- all policy checks required per request
- local robots policy required
- recent dry-run approval required if configured
- rate limit enforced
- no request retries by default
- no browser automation
- no bypass mechanisms
- no scheduled live retrieval

## 7. Tests

Add or update tests for:

- pending Redfin capture request filtering
- dry-run batch performs no network calls
- retrieve command without force-live performs no network calls
- force-live still blocked when compliance fails
- force-live blocked when robots missing/disallowed
- force-live blocked when dry-run approval missing
- force-live blocked by rate limit
- fake-client success saves fixtures
- retrieve_only does not process
- retrieve_and_process calls processing pipeline
- queue items marked captured only after success
- blocked items remain pending or are not falsely captured
- batch manifest written
- per-item manifest written
- CLI dry-run-pending-redfin-fixtures
- CLI retrieve-pending-redfin-fixtures blocked default
- no scheduled scripts invoke live retrieval
- no real network calls in tests
- existing MVP 1-17 tests still pass

All tests must pass.

## 8. Documentation

Update README.md and docs/RUNBOOK.md with a "Redfin Pending Capture Batch Retrieval" section.

Update docs/FIXTURE_CAPTURE_QUEUE.md with:

- batch dry-run command
- batch retrieve command
- force-live warning
- process-after-retrieval option
- manifest files
- how blocked items remain pending

Update docs/REDFIN_LIVE_HTTP_PHASE_1.md with:

- batch retrieval constraints
- no scheduled live retrieval
- fake-client-only test behavior

Create:

```text
docs/REDFIN_PENDING_CAPTURE_BATCH_RETRIEVAL.md
```

Explain:

- what the batch orchestrator does
- what it does not do
- how to dry-run pending items
- how to retrieve with force-live
- why force-live is required
- how rate limiting works
- how dry-run approval works
- how fixture processing works after retrieval
- how to inspect manifests and audit logs
- how to continue manual fixture capture instead

Add design decision note:

```text
docs/decisions/017-redfin-pending-capture-batch-retrieval.md
```

Explain:

- why batch retrieval operates on capture queue items only
- why default is dry-run
- why scheduled tasks do not invoke live retrieval
- why retrieved HTML remains fixture-first
- why other sources are deferred

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
- Existing Effective DOM v1/v2 workflows still work.
- Existing cross-site workflows still work.
- Existing county workflows still work.
- Existing watchlist monitoring workflows still work.
- Existing dashboard/report viewer still works.
- Existing Windows automation still works.
- Existing retrieval compliance/policy/fixture capture queue still works.
- Pending capture batch dry-run works.
- Pending capture batch fake-client success path works in tests.
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
8. Example dry-run-pending-redfin-fixtures output.
9. Example retrieve-pending-redfin-fixtures blocked-without-force-live output.
10. Example fake-client success batch output and fixture path.
11. Batch manifest path and row count.
12. Per-item manifest path and row count.
13. Confirmation that queue items are marked captured only after successful retrieval/processing.
14. Confirmation that scheduled scripts do not invoke live retrieval.
15. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
16. Confirmation that tests perform no real network calls.
17. Recommended next implementation step.
18. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 18 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
