# Claude Code Prompt 015 - Retrieval Safety Enforcement and Fixture Capture Queue

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/LIVE_RETRIEVAL_STRATEGY.md.
6. Review the current codebase through commit ee7e81f.
7. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
8. Keep PRD.md and Architecture.md in the project root.
9. Use src/marketsentry/ as the Python package path.
10. Do not move PRD.md or Architecture.md into docs/.
11. Do not implement active live scraping, browser automation, Playwright, Selenium, or bypass mechanisms in this milestone.
12. Do not implement live County Recorder/Assessor access in this milestone.
13. Do not make any external network calls in tests or implementation.
14. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 15 is still NOT a live scraper implementation milestone.

Milestone 15 should harden the compliance foundation from Milestone 14 by adding:

- retrieval policy checks
- mocked/offline robots policy parsing interfaces
- deterministic rate limit enforcement
- dry-run approval/history gating
- manual fixture capture queue
- retrieval audit report
- better operator visibility into what is safe/blocked/pending

No live HTTP retrieval should be performed.

No robots.txt should be fetched from the internet in this milestone. Robots checks should be interface-based and testable using saved/local fixtures only.

The output of this milestone should make a future live retrieval milestone safer, but it should not perform live retrieval itself.

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
13. Live retrieval, if ever enabled later, must be explicit, compliant, rate-limited, auditable, and disabled by default.

Your task for Prompt 015:

Implement Retrieval Safety Enforcement and Fixture Capture Queue v1.

No active live scraping.

## 1. Retrieval policy engine

Create or extend:

```text
src/marketsentry/source_adapters/policy.py
```

Required models/classes:

- RetrievalPolicy
- RetrievalPolicyDecision
- RetrievalPolicyReason
- SourceRobotsPolicy
- SourceRateLimitState
- DryRunApprovalRecord
- FixtureCaptureRequest
- FixtureCaptureQueueResult

Required behavior:

- Evaluate whether a retrieval request is allowed, blocked, or requires manual action.
- Combine existing compliance checks with new policy checks.
- Support retrieval modes:
  - disabled
  - dry_run
  - manual_fixture
  - authorized_api
  - live_http
- live_http remains disabled by default.
- manual_fixture remains safe/default.
- dry_run always performs no network call.
- authorized_api remains interface-only unless credentials/API integration exist later.
- blocked decisions must include specific reasons.

Decision values:

- allowed
- blocked
- requires_manual_fixture
- requires_dry_run
- requires_authorized_access
- not_implemented

## 2. Offline robots policy interface

Create a robots-policy interface that uses local/saved robots text only.

Do not fetch robots.txt from the internet.

Suggested module:

```text
src/marketsentry/source_adapters/robots_policy.py
```

Required functions:

- parse_robots_text(robots_text: str) -> SourceRobotsPolicy
- check_robots_allowed(policy: SourceRobotsPolicy, user_agent: str, path: str) -> RobotsCheckResult
- load_local_robots_policy(source_site: str, policies_dir: Path | str | None = None) -> SourceRobotsPolicy | None

Local policies directory:

```text
data/policies/robots/
```

Test fixtures:

```text
tests/fixtures/robots/
```

Required behavior:

- Supports simple User-agent and Disallow rules.
- Handles wildcard user-agent `*`.
- Handles empty or missing policy as unknown, not automatically allowed for live mode.
- If robots policy is unknown and live mode requested, block or require manual review.
- Dry-run may still preview without network call.

## 3. Rate limiter

Create a deterministic local rate limiter.

Suggested module:

```text
src/marketsentry/source_adapters/rate_limiter.py
```

Required classes/functions:

- RateLimiter
- RateLimitDecision
- check_rate_limit(source_site: str, config: RateLimitConfig, state: SourceRateLimitState, now: datetime | None = None) -> RateLimitDecision
- record_retrieval_attempt(...)

Required behavior:

- Enforce max requests per minute.
- Enforce optional minimum delay between requests.
- State should be injectable/testable.
- No sleeping in tests.
- If live retrieval were enabled later, request should be blocked when rate limit exceeded.
- Dry-run should not consume live retrieval quota unless explicitly configured.

## 4. Dry-run approval/history gate

Implement a dry-run approval/history mechanism.

Purpose:

Before live retrieval is ever attempted in a future milestone, a matching dry-run should exist.

Create or extend audit logs to record:

- source_site
- url
- normalized_url
- request_type
- dry_run timestamp
- compliance status at dry-run time
- allowed/blocked reasons
- network_call_performed = false

Required functions:

- record_dry_run_approval(...)
- has_recent_dry_run_approval(source_site: str, url: str, max_age_hours: int = 24, ...) -> bool
- require_recent_dry_run_before_live(...) -> RetrievalPolicyDecision

Important:
- This should be used in policy decisions.
- No live retrieval occurs in this milestone.

## 5. Manual fixture capture queue

Create a local queue for URLs/pages that need manual fixture capture.

Purpose:

When live retrieval is blocked or not implemented, the system should tell the user what local HTML fixture to save manually.

Suggested module:

```text
src/marketsentry/fixture_capture_queue.py
```

Suggested table:

```text
fixture_capture_queue
```

Fields:

- capture_request_id
- created_at
- source_site
- source_url
- normalized_url
- request_type
- suggested_fixture_path
- status
- priority
- reason
- candidate_id
- property_id
- notes

Statuses:

- pending
- captured
- skipped
- invalid
- archived

Required behavior:

- Add capture request from dry-run or blocked policy decision.
- Deduplicate by source_site + normalized_url + request_type + pending status.
- Suggest a fixture path under:
  - data/raw/redfin/details/
  - data/raw/redfin/search/
  - data/raw/zillow/details/
  - data/raw/realtor/details/
  - data/raw/homes/details/
  - data/raw/compass/details/
  - data/raw/county/
- List pending capture requests.
- Mark capture request captured/skipped.
- Export capture queue to CSV.

## 6. CLI commands

Add CLI commands:

```text
marketsentry retrieval-policy-check
marketsentry list-fixture-capture-queue
marketsentry export-fixture-capture-queue
marketsentry mark-fixture-captured
marketsentry retrieval-audit-report
```

### retrieval-policy-check

Accept:

- --source
- --url
- --request-type
- --mode

Behavior:

- Prints policy decision.
- Prints reasons.
- Prints whether dry-run is required.
- Prints whether local fixture capture is recommended.
- Does not make network calls.

### list-fixture-capture-queue

Print pending/manual fixture capture requests.

### export-fixture-capture-queue

Exports CSV to:

```text
data/exports/fixture_capture_queue_YYYYMMDD_HHMMSS.csv
```

### mark-fixture-captured

Accept:

- --capture-request-id
- --fixture-path

Marks capture request as captured.

### retrieval-audit-report

Summarizes audit logs under:

```text
logs/retrieval_audit/
```

Output should include:

- total decisions
- allowed
- blocked
- dry-runs
- live attempts
- network_call_performed true/false counts
- blocked reasons summary

All commands must be ASCII-safe.

## 7. Adapter integration

Update Redfin adapter dry-run behavior to:

- call policy engine
- record dry-run approval when appropriate
- add fixture capture request if retrieval is blocked/not implemented
- write audit record

Update source registry/adapters as needed.

No live network calls.

## 8. Tests

Add or update tests for:

- retrieval policy decisions
- live mode blocked by default
- dry-run allowed without network call
- unknown robots policy blocks live mode
- local robots policy parse allow/disallow
- rate limiter allows under threshold
- rate limiter blocks over threshold
- dry-run approval record creation
- recent dry-run approval lookup
- fixture capture queue insert
- fixture capture queue deduplication
- suggested fixture paths by source/request type
- mark fixture captured
- export fixture capture queue
- retrieval audit report counts
- retrieval-policy-check CLI
- list/export/mark fixture queue CLI
- no network imports/calls
- existing MVP 1-14 tests still pass

All tests must pass.

Tests must not perform network access.

Do not register scheduled tasks in pytest.

## 9. Documentation

Update README.md and docs/RUNBOOK.md with a "Retrieval Safety and Fixture Capture Queue" section.

Update docs/LIVE_RETRIEVAL_STRATEGY.md with:

- retrieval policy engine
- local robots policy interface
- rate limiter
- dry-run approval requirement
- fixture capture queue
- retrieval audit report
- exact statement that live retrieval is still not implemented

Create:

```text
docs/FIXTURE_CAPTURE_QUEUE.md
```

Explain:

- What the fixture capture queue is.
- How to use dry-run commands to create capture requests.
- How to manually save fixture files.
- How to mark requests captured.
- How to export the queue.
- How this supports safe/manual operation before live retrieval.

Add design decision note:

```text
docs/decisions/014-retrieval-safety-and-fixture-capture-queue.md
```

Explain:

- Why safety enforcement is added before live retrieval.
- Why robots policy is local/offline in this milestone.
- Why rate limiting is implemented before HTTP.
- Why dry-run approval is required.
- Why fixture capture queue remains the primary workflow.

## 10. Code standards

- Python 3.11+
- PEP8 compliant.
- Type hints required.
- Docstrings required for all functions.
- Remove unused imports.
- Keep modules small and readable.
- No active live scraping.
- No network calls in tests.
- No Playwright/Selenium/browser automation.
- No bypassing bot protections.
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
- Existing Effective DOM v1/v2 workflows still work.
- Existing cross-site workflows still work.
- Existing county workflows still work.
- Existing watchlist monitoring workflows still work.
- Existing dashboard/report viewer still works.
- Existing Windows automation still works.
- Existing retrieval compliance dry-run commands still work.
- Retrieval policy engine works.
- Local robots parser works.
- Rate limiter works.
- Fixture capture queue works.
- Retrieval audit report works.
- No network calls are performed.
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
9. Example retrieval-policy-check output.
10. Example fixture capture queue output.
11. Example fixture capture queue export path and row count.
12. Example retrieval-audit-report output.
13. Confirmation that live retrieval is still not implemented.
14. Confirmation that no active network calls, scraping, Playwright, Selenium, or browser automation were added.
15. Recommended next implementation step.
16. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 15 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
