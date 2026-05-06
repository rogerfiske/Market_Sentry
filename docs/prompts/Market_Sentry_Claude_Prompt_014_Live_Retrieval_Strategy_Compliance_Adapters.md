# Claude Code Prompt 014 - Live Retrieval Strategy and Compliance Adapter Design

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Review the current codebase through commit deaa042.
6. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
7. Keep PRD.md and Architecture.md in the project root.
8. Use src/marketsentry/ as the Python package path.
9. Do not move PRD.md or Architecture.md into docs/.
10. Do not implement active live scraping, browser automation, Playwright, Selenium, or bypass mechanisms in this milestone.
11. Do not implement live County Recorder/Assessor access in this milestone.
12. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 14 is NOT a live scraper implementation milestone.

Milestone 14 should implement the compliance-aware source adapter architecture and dry-run retrieval framework needed before any live source access is attempted.

The goal is to make future live retrieval safe, explicit, auditable, rate-limited, disabled by default, and easy to swap with authorized APIs/feeds later.

Do not bypass robots.txt, paywalls, login walls, anti-bot protections, CAPTCHAs, or technical access controls.

Do not implement Playwright/Selenium/browser automation.

Do not run live network calls in tests.

No scheduled task should run live retrieval by default.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It starts with Redfin candidate discovery, stages homes for human review, and then monitors user-selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, cross-site validation, county sale/ownership-transfer verification, a separate recent Churn Index, local reports, a local dashboard, and local workflow automation.

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

Your task for Prompt 014:

Implement Live Retrieval Strategy and Compliance Adapter Design v1.

No active live scraping implementation.

## 1. Source adapter architecture

Create a source adapter foundation, for example:

```text
src/marketsentry/source_adapters/
  __init__.py
  base.py
  compliance.py
  registry.py
  redfin_adapter.py
  zillow_adapter.py
  realtor_adapter.py
  homes_adapter.py
  compass_adapter.py
  county_adapter.py
```

Adapters may be skeletons/stubs in this milestone.

Required base abstractions:

- SourceAdapter
- SourceAdapterConfig
- RetrievalRequest
- RetrievalResult
- RetrievalMode
- ComplianceCheckResult
- RateLimitConfig
- RobotsCheckResult
- SourceAdapterRegistry

Supported RetrievalMode values:

- disabled
- dry_run
- manual_fixture
- authorized_api
- live_http

Important:

- Default mode must be disabled or dry_run.
- live_http must be disabled by default.
- live_http must require explicit config/environment opt-in.
- manual_fixture should remain the default practical path for now.
- authorized_api should be supported as a future mode but not implemented beyond interface placeholders.

## 2. Compliance guardrails

Implement a compliance module that supports:

- checking whether live retrieval is globally enabled
- checking whether a source adapter is allowed to run in live mode
- validating allowed domains per source
- validating that rate limits are configured
- validating that User-Agent/contact string is configured if live mode is enabled
- requiring dry-run preview before live retrieval
- recording compliance decisions in logs or audit records

Do not implement robots.txt network fetching in this milestone unless it is fully mocked in tests and disabled by default. It is acceptable to define interfaces and documentation for future robots checks.

Required behavior:

- If live retrieval is not explicitly enabled, adapter live retrieval returns a blocked/dry-run result.
- If source domain is not allowlisted, request is blocked.
- If source adapter has no rate limit, request is blocked.
- If user has not enabled live retrieval in environment/config, request is blocked.
- If retrieval mode is dry_run, no network call occurs and the result explains what would have happened.

## 3. Configuration

Add configuration settings to .env.example and Config:

Suggested environment variables:

```text
MARKETSENTRY_LIVE_RETRIEVAL_ENABLED=false
MARKETSENTRY_ALLOWED_LIVE_SOURCES=
MARKETSENTRY_LIVE_USER_AGENT=
MARKETSENTRY_LIVE_CONTACT_EMAIL=
MARKETSENTRY_MAX_REQUESTS_PER_MINUTE=6
MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE=true
```

Default values must be conservative:

- live retrieval disabled
- no sources allowed
- low request rate
- dry-run required

## 4. Redfin adapter skeleton

Implement Redfin adapter skeleton only.

Do not implement active Redfin page fetching.

Required methods:

- validate_request
- build_search_request_preview
- build_property_request_preview
- dry_run_search
- dry_run_property_detail
- retrieve_search
- retrieve_property_detail

Behavior:

- dry_run methods return structured preview objects.
- live retrieve methods must be blocked unless live retrieval is explicitly enabled and compliance checks pass.
- Even when enabled, live methods may return NotImplemented until a later milestone.
- Do not make network calls.

## 5. Source adapter registry

Implement adapter registration and lookup:

- redfin
- zillow
- realtor
- homes
- compass
- county

Only Redfin needs meaningful dry-run preview behavior in this milestone. Other adapters can be skeletons.

## 6. CLI commands

Add CLI commands:

```text
marketsentry source-adapters
marketsentry retrieval-compliance-status
marketsentry dry-run-redfin-search
marketsentry dry-run-redfin-property
```

### source-adapters

Print registered adapters and supported modes.

### retrieval-compliance-status

Print:

- live retrieval globally enabled?
- allowed live sources
- user agent configured?
- contact email configured?
- max requests per minute
- dry-run required?
- warnings
- whether live retrieval is blocked or potentially allowed

### dry-run-redfin-search

Accept:

- --url
- --db optional
- --output optional

Behavior:

- Validate Redfin search URL.
- Show what would be retrieved.
- Show whether it would be blocked in live mode and why.
- No network call.

### dry-run-redfin-property

Accept:

- --url
- --db optional
- --output optional

Behavior:

- Validate Redfin property URL.
- Show what would be retrieved.
- Show whether it would be blocked in live mode and why.
- No network call.

## 7. Audit/logging

Add lightweight audit logging for retrieval decisions.

Possible output:

```text
logs/retrieval_audit/
```

Audit records should capture:

- timestamp
- source_site
- retrieval_mode
- url/domain
- allowed/blocked
- reason
- dry_run flag
- network_call_performed = false

For this milestone, all records should have:

```text
network_call_performed = false
```

## 8. Tests

Add or update tests for:

- RetrievalMode enum/values.
- Config defaults live retrieval disabled.
- Env/config parsing for live retrieval settings.
- Compliance blocks live retrieval by default.
- Compliance blocks unallowlisted domains.
- Compliance blocks missing rate limit.
- Compliance blocks missing User-Agent/contact when live enabled.
- Dry-run performs no network calls.
- Redfin search URL dry-run preview.
- Redfin property URL dry-run preview.
- Source adapter registry includes all expected adapters.
- source-adapters CLI command.
- retrieval-compliance-status CLI command.
- dry-run-redfin-search CLI command.
- dry-run-redfin-property CLI command.
- Audit record writes with network_call_performed=false.
- Existing MVP 1-13 tests still pass.

All tests must pass.

Tests must not perform network access.

## 9. Documentation

Update README.md and docs/RUNBOOK.md with a "Live Retrieval Strategy" section.

Create:

```text
docs/LIVE_RETRIEVAL_STRATEGY.md
```

It should explain:

- Live retrieval is disabled by default.
- Current implementation is adapter design + dry-run only.
- Manual fixtures remain the default safe workflow.
- Authorized APIs/feeds are preferred for future production use.
- No bypassing paywalls, CAPTCHAs, login walls, anti-bot protections, or access controls.
- How compliance settings work.
- How to run dry-run commands.
- What future live retrieval implementation must satisfy.
- How to use retrieval audit logs.
- Why Task Scheduler should not run live retrieval by default.

Add design decision note:

```text
docs/decisions/013-live-retrieval-strategy-and-compliance-adapters.md
```

Explain:

- Why this milestone adds compliance adapters before live retrieval.
- Why dry-run comes first.
- Why live_http is disabled by default.
- Why authorized APIs/feeds are preferred.
- Why source adapters are swappable.
- Why no browser automation/bypass is implemented.

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
- Existing end-to-end workflows still work.
- Existing dashboard/report viewer still works.
- Existing Windows automation still works.
- Compliance status command works.
- Dry-run Redfin commands work.
- Audit log writes.
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
8. Config/env variables added.
9. Example retrieval-compliance-status output.
10. Example dry-run-redfin-search output.
11. Example dry-run-redfin-property output.
12. Audit log path and example record.
13. Confirmation that live retrieval is disabled by default.
14. Confirmation that no active network calls, scraping, Playwright, Selenium, or browser automation were added.
15. Recommended next implementation step.
16. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 14 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
