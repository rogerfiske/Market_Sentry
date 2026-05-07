# Claude Code Prompt 019 - Redfin Batch Retrieval Approval Workflow

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/LIVE_RETRIEVAL_STRATEGY.md.
5. Read docs/FIXTURE_CAPTURE_QUEUE.md.
6. Read docs/REDFIN_LIVE_HTTP_PHASE_1.md.
7. Read docs/REDFIN_RETRIEVED_FIXTURE_PROCESSING.md.
8. Read docs/REDFIN_PENDING_CAPTURE_BATCH_RETRIEVAL.md.
9. Review the current codebase through commit 2d420d7.
10. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
11. Keep PRD.md and Architecture.md in the project root.
12. Use src/marketsentry/ as the Python package path.
13. Do not move PRD.md or Architecture.md into docs/.
14. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
15. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
16. Do not run any live network calls in tests.
17. Do not make scheduled tasks run live retrieval by default.
18. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 19 should improve operator safety and usability for Redfin batch retrieval.

The goal is to add a two-step approval workflow:

1. Prepare a batch approval package by dry-running pending Redfin capture requests.
2. Let the user review and explicitly approve selected items in a local CSV.
3. Retrieve only approved items, only with --force-live, and only if every policy check still passes.

This milestone must not broaden live retrieval.

This milestone must not schedule live retrieval.

This milestone must not bypass any access controls.

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

Your task for Prompt 019:

Implement Redfin Batch Retrieval Approval Workflow v1.

## 1. Approval package concept

Create a local approval package that contains dry-run results for pending Redfin fixture capture requests.

Approval package files should live under:

```text
data/exports/retrieval_approvals/
```

Suggested files:

```text
redfin_batch_approval_<run_id>.csv
redfin_batch_approval_<run_id>.md
```

The CSV is user-editable.

Required CSV columns:

- approval_run_id
- capture_request_id
- source_site
- source_url
- normalized_url
- request_type
- suggested_fixture_path
- policy_decision
- policy_reasons
- compliance_passed
- robots_passed
- rate_limit_passed
- dry_run_approved
- network_call_performed
- approved_for_live
- user_notes

Default:

```text
approved_for_live = false
```

The user must manually change approved_for_live to true for each item they want to retrieve.

## 2. Approval workflow module

Create a module, for example:

```text
src/marketsentry/retrieval_approval.py
```

Required models:

- RetrievalApprovalRow
- RetrievalApprovalPackage
- RetrievalApprovalImportResult
- ApprovedRetrievalRunResult

Required functions:

- prepare_redfin_batch_approval_package(...)
- load_retrieval_approval_csv(...)
- validate_retrieval_approval_csv(...)
- retrieve_approved_redfin_batch(...)
- summarize_approval_package(...)

Required behavior:

- Prepare package by dry-running pending Redfin capture requests.
- Record dry-run approvals using Milestone 15 mechanism.
- Write approval CSV with approved_for_live=false.
- Write Markdown summary explaining blocked/allowed/warning status.
- Import approved CSV.
- Validate approval_run_id.
- Validate capture_request_id still exists and is pending.
- Validate URL still matches queue item.
- Reject rows approved_for_live=true if policy now fails.
- Retrieve only approved_for_live=true rows.
- Require --force-live for retrieval.
- Still enforce all Milestone 14-18 policy checks per item.
- Use fake/injected HTTP client in tests.
- Save fixtures through Milestone 16 Redfin adapter.
- Optionally process fixtures through Milestone 17 pipeline.
- Mark queue items captured only after successful retrieval and, if requested, successful processing.

## 3. Approval package status tracking

Create append-only manifest:

```text
data/processed/redfin_retrieval_approval_manifest.csv
```

Columns:

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

This manifest may be updated or appended when approvals are imported/retrieved. Choose one strategy and document it.

## 4. CLI commands

Add CLI commands:

```text
marketsentry prepare-redfin-retrieval-approval
marketsentry retrieve-approved-redfin-batch
```

### prepare-redfin-retrieval-approval

Options:

- --max-items
- --request-type
- --db
- --output-dir

Behavior:

- Dry-run pending Redfin capture queue items.
- Write approval CSV and Markdown summary.
- Print approval file path.
- Print instructions to manually edit approved_for_live.
- No network calls.

### retrieve-approved-redfin-batch

Options:

- --approval-file
- --db
- --output-dir
- --force-live
- --process-after-retrieval
- --dry-run-only

Behavior:

- Without --force-live, do not retrieve.
- With --dry-run-only, validate and preview only.
- With --force-live, retrieve only approved_for_live=true rows and only if all policy checks pass.
- Print:
  - rows loaded
  - approved rows
  - attempted live
  - retrieved
  - blocked
  - failed
  - fixtures saved
  - queue items marked captured
  - reports exported if processing occurred

## 5. Approval safety rules

Required:

- approved_for_live defaults to false.
- --force-live required.
- live retrieval environment variables still required.
- local robots policy still required.
- dry-run approval still required.
- rate limit still enforced.
- URL must still match original queue item.
- capture request must still be pending.
- no scheduled scripts may call retrieve-approved-redfin-batch.
- no broad source support; Redfin only.

## 6. Tests

Add or update tests for:

- prepare approval package creates CSV and Markdown summary.
- approved_for_live defaults false.
- approval CSV includes required columns.
- approval manifest written.
- load approval CSV validates run id.
- load approval CSV validates capture_request_id.
- URL mismatch blocks retrieval.
- non-pending capture request blocks retrieval.
- retrieve-approved without force-live performs no network calls.
- dry-run-only retrieval performs no network calls.
- approved false rows are skipped.
- approved true rows still blocked if compliance fails.
- approved true rows still blocked if robots fail.
- approved true rows still blocked if dry-run approval missing.
- fake-client approved retrieval saves fixture.
- queue item marked captured only after successful retrieval/processing.
- processing optional path invokes Milestone 17 pipeline.
- scheduled scripts do not call approval retrieval commands.
- no real network calls in tests.
- existing MVP 1-18 tests still pass.

All tests must pass.

## 7. Documentation

Update README.md and docs/RUNBOOK.md with a "Redfin Retrieval Approval Workflow" section.

Update docs/REDFIN_PENDING_CAPTURE_BATCH_RETRIEVAL.md with:

- approval package workflow
- prepare command
- approval CSV editing instructions
- retrieve approved command
- safety rules

Create:

```text
docs/REDFIN_RETRIEVAL_APPROVAL_WORKFLOW.md
```

Explain:

- why approval package exists
- how to prepare approval package
- how to review CSV
- how to approve selected rows
- how to retrieve approved rows
- why --force-live is still required
- how to inspect audit logs and manifests
- how to use manual fixture capture instead
- no scheduled live retrieval by default

Add design decision note:

```text
docs/decisions/018-redfin-retrieval-approval-workflow.md
```

Explain:

- why user approval is required before batch live retrieval
- why approved_for_live defaults false
- why policy checks are rerun at retrieval time
- why URL/capture request validation is required
- why scheduled tasks do not run approved retrieval

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
- Existing Effective DOM v1/v2 workflows still work.
- Existing cross-site workflows still work.
- Existing county workflows still work.
- Existing watchlist monitoring workflows still work.
- Existing dashboard/report viewer still works.
- Existing Windows automation still works.
- Approval package creation works.
- Approved retrieval fake-client path works in tests.
- No real network calls are performed in tests.
- No scheduled task invokes live retrieval or approved retrieval.
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
8. Example prepare-redfin-retrieval-approval output.
9. Approval CSV path and row count.
10. Approval Markdown summary path.
11. Approval manifest path and row count.
12. Example retrieve-approved-redfin-batch blocked-without-force-live output.
13. Example fake-client approved retrieval output and fixture path.
14. Confirmation that approved_for_live defaults to false.
15. Confirmation that queue items are marked captured only after successful retrieval/processing.
16. Confirmation that scheduled scripts do not invoke live retrieval or approved retrieval.
17. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
18. Confirmation that tests perform no real network calls.
19. Recommended next implementation step.
20. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 19 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
