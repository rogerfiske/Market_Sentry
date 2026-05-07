# Claude Code Prompt 016 - Redfin Live HTTP Retrieval Phase 1

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/LIVE_RETRIEVAL_STRATEGY.md.
6. Read docs/FIXTURE_CAPTURE_QUEUE.md.
7. Review the current codebase through commit e4010d8.
8. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
9. Keep PRD.md and Architecture.md in the project root.
10. Use src/marketsentry/ as the Python package path.
11. Do not move PRD.md or Architecture.md into docs/.
12. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
13. Do not implement live County Recorder/Assessor access in this milestone.
14. Do not run any live network calls in tests.
15. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 16 is the first possible live HTTP retrieval implementation, but it must be extremely constrained.

The purpose is not broad scraping.

The purpose is to add a safe, explicit, auditable, opt-in HTTP retrieval path for Redfin pages only, which saves retrieved HTML as local fixtures and then reuses the existing fixture parsers.

Live retrieval must remain disabled by default.

No scheduled task may run live retrieval by default.

No tests may perform network calls.

If any compliance guardrail fails, retrieval must be blocked and a fixture capture request should be created instead.

Do not add support for Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor live retrieval in this milestone.

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

Your task for Prompt 016:

Implement Redfin Live HTTP Retrieval Phase 1.

This milestone may add actual HTTP retrieval code, but it must be:

- Redfin only
- disabled by default
- explicit opt-in only
- rate-limited
- policy-checked
- dry-run-gated
- local-fixture-output only
- audited
- fully mocked in tests
- never run automatically by scheduled tasks

## 1. HTTP client abstraction

Create a small HTTP client abstraction so tests can use a fake client.

Suggested module:

```text
src/marketsentry/source_adapters/http_client.py
```

Required classes/models:

- HttpRequest
- HttpResponse
- HttpClient
- RequestsHttpClient or StandardLibraryHttpClient
- FakeHttpClient for tests if useful

Required behavior:

- GET only for this milestone.
- Configurable timeout.
- Configurable headers.
- No cookies/session/login logic.
- No retries by default unless explicitly conservative and tested.
- Raise or return structured errors for:
  - timeout
  - non-200 status
  - blocked by policy
  - unsupported content type
  - response too large
- Do not implement browser rendering.
- Do not execute JavaScript.

If adding a dependency such as `requests`, update requirements.txt. Prefer standard library if practical.

## 2. Redfin live retrieval adapter

Extend:

```text
src/marketsentry/source_adapters/redfin_adapter.py
```

Required methods:

- retrieve_search(...)
- retrieve_property_detail(...)
- save_retrieved_fixture(...)
- retrieve_and_save_search_fixture(...)
- retrieve_and_save_property_fixture(...)

Behavior:

- Validate URL is Redfin and is search or property detail as appropriate.
- Run retrieval policy check.
- Confirm live retrieval is explicitly enabled.
- Confirm source is allowlisted.
- Confirm User-Agent and contact email are configured.
- Confirm local/offline robots policy is known and allows the path.
- Confirm rate limit allows request.
- Confirm recent dry-run approval exists if required.
- If any check fails:
  - do not perform network call
  - write audit record with network_call_performed=false
  - add fixture capture queue request
  - return blocked result
- If all checks pass:
  - perform one HTTP GET through injected HTTP client
  - enforce timeout
  - enforce max response size
  - save HTML to fixture path
  - write audit record with network_call_performed=true
  - return result with fixture path

## 3. Fixture output paths

Save retrieved HTML as local fixtures.

Search pages:

```text
data/raw/redfin/search/redfin_search_YYYYMMDD_HHMMSS.html
```

Property detail pages:

```text
data/raw/redfin/details/redfin_property_<home_id_or_slug>_YYYYMMDD_HHMMSS.html
```

Required behavior:

- Create directories if missing.
- Sanitize filenames.
- Preserve source URL in a sidecar metadata JSON file or in an audit record.
- Do not overwrite existing fixtures.

## 4. Rate limit enforcement

Use Milestone 15 rate limiter.

Required behavior:

- Request is blocked if rate limit would be exceeded.
- Successful live retrieval attempt records rate limiter state.
- Failed HTTP response may still count as an attempt; document chosen behavior.
- Dry-run does not consume live quota unless explicitly configured.

## 5. Local robots policy requirement

Use Milestone 15 offline robots policy interface.

Required behavior:

- Live retrieval must not proceed if no local robots policy is available.
- Live retrieval must not proceed if local robots policy disallows the path.
- CLI should tell user where to place local robots fixture, for example:
  - data/policies/robots/redfin_robots.txt
- Do not fetch robots.txt from the internet in this milestone.

## 6. Dry-run approval requirement

Use Milestone 15 dry-run approval mechanism.

Required behavior:

- Live retrieval must not proceed unless a recent matching dry-run approval exists when MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE=true.
- Dry-run approval max age defaults to 24 hours.
- If missing, block retrieval and tell user to run dry-run-redfin-search or dry-run-redfin-property first.

## 7. CLI commands

Add CLI commands:

```text
marketsentry retrieve-redfin-search
marketsentry retrieve-redfin-property
```

### retrieve-redfin-search

Options:

- --url
- --output-dir optional
- --db optional
- --force-live optional default false
- --dry-run-only optional default false

Behavior:

- If dry-run-only is true, perform dry-run only.
- If force-live is false, explain that live retrieval requires explicit opt-in and config.
- If force-live is true, still require all compliance/policy checks.
- Save fixture if live retrieval succeeds.
- Print:
  - policy decision
  - network_call_performed true/false
  - fixture path if saved
  - audit log path
  - capture queue request if blocked

### retrieve-redfin-property

Same behavior for Redfin property detail URL.

Important:
- These commands must not be used by scheduled tasks by default.
- Do not modify existing scheduled scripts to call live retrieval.

## 8. Tests

Add or update tests for:

- HTTP client abstraction with fake client.
- Redfin live retrieval blocked by default.
- Redfin live retrieval blocked if source not allowlisted.
- Redfin live retrieval blocked if User-Agent missing.
- Redfin live retrieval blocked if contact email missing.
- Redfin live retrieval blocked if robots policy missing.
- Redfin live retrieval blocked if robots policy disallows path.
- Redfin live retrieval blocked if rate limit exceeded.
- Redfin live retrieval blocked if dry-run approval missing.
- Redfin live retrieval succeeds with fake HTTP client when all checks pass.
- Successful fake live retrieval saves fixture file.
- Metadata/audit written for successful fake retrieval.
- Failed HTTP status does not save fixture.
- Response too large is blocked.
- CLI retrieve commands in dry-run mode.
- CLI retrieve commands blocked in default config.
- Existing MVP 1-15 tests still pass.

All tests must pass.

Tests must not perform real network access.

Use fake/mocked HTTP client for any success-path tests.

## 9. Documentation

Update README.md and docs/RUNBOOK.md with a "Redfin Live HTTP Phase 1" section.

Update docs/LIVE_RETRIEVAL_STRATEGY.md with:

- live retrieval remains disabled by default
- Redfin-only Phase 1 scope
- required environment variables
- local robots policy requirement
- dry-run approval requirement
- rate-limit requirement
- fixture output behavior
- audit logging
- how to run retrieve commands
- how to keep using manual fixtures instead

Create:

```text
docs/REDFIN_LIVE_HTTP_PHASE_1.md
```

Explain:

- What is implemented.
- What is not implemented.
- Required safety settings.
- How to do a dry-run.
- How to provide local robots policy.
- How to enable live retrieval explicitly.
- How retrieved pages are saved as fixtures.
- How to parse saved fixtures afterward.
- Why scheduled tasks do not run live retrieval by default.
- Troubleshooting blocked retrievals.
- Compliance warnings:
  - do not bypass access controls
  - do not use login-required content
  - do not bypass CAPTCHAs or anti-bot systems
  - prefer authorized APIs/feeds when available

Add design decision note:

```text
docs/decisions/015-redfin-live-http-phase-1.md
```

Explain:

- Why Redfin is first.
- Why retrieval saves fixtures instead of directly mutating candidate tables.
- Why dry-run approval is required.
- Why local robots policy is required.
- Why live retrieval is not scheduled by default.
- Why browser automation is excluded.

## 10. Code standards

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
- Existing Effective DOM v1/v2 workflows still work.
- Existing cross-site workflows still work.
- Existing county workflows still work.
- Existing watchlist monitoring workflows still work.
- Existing dashboard/report viewer still works.
- Existing Windows automation still works.
- Existing retrieval compliance dry-run commands still work.
- Existing retrieval policy engine works.
- Fixture capture queue still works.
- Redfin live retrieval blocked by default.
- Redfin success path works only with fake HTTP client in tests.
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
8. Config/env variables used.
9. Example retrieve-redfin-search blocked-by-default output.
10. Example retrieve-redfin-property dry-run output.
11. Example fake-client success test result and fixture path.
12. Audit log path and example record showing network_call_performed=true only in fake-client test context.
13. Confirmation that live retrieval remains disabled by default.
14. Confirmation that scheduled tasks do not invoke live retrieval.
15. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
16. Confirmation that tests perform no real network calls.
17. Recommended next implementation step.
18. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 16 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
