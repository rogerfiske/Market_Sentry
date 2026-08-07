# Claude Code Prompt 055 - HowLoud Noise Enrichment Adapter

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry  
Local project folder: `C:\Users\Minis\CascadeProjects\Market_Sentry`  
Current accepted milestone: Milestone 54  
Current accepted commit: `0543872`  
Current known test baseline: `2979 passed, 18 warnings`  
Current branch: `main`

## PM decision

The previously sequenced Redfin Rendered Lifestyle Score Capture Agent is deferred because it would require browser automation and explicit compliance scoping.

Milestone 55 will instead implement the HowLoud Noise Enrichment Adapter. This preserves the current compliance posture while improving the noise-analysis workflow that is central to Market_Sentry.

Do not implement browser automation in this milestone.

---

## Purpose

Milestone 55 should add a local-first, opt-in HowLoud noise enrichment adapter.

The goal is to supplement Redfin Quiet/Vibrancy and local operator knowledge with a separately stored third-party noise signal.

Target workflow:

```text
Candidate exists
→ candidate has address / Redfin URL / location fields
→ operator explicitly requests HowLoud enrichment
→ system calls HowLoud only when explicitly enabled and configured
→ result is stored separately from Redfin Quiet/Vibrancy
→ dashboard/report compares HowLoud vs Redfin Quiet without blending them
→ operator can use differences as evidence for manual review
```

This milestone must not overwrite Redfin Quiet/Vibrancy scores.

This milestone must not make purchase recommendations.

---

## Before starting

1. Read `PRD.md`.
2. Read `Architecture.md`.
3. Read `README.md`.
4. Read `docs/RUNBOOK.md`.
5. Read `docs/OPERATOR_WORKFLOW.md`.
6. Read `docs/MANUAL_SCORE_ENTRY.md`.
7. Read `docs/REDFIN_SCREENING_QUEUE.md`.
8. Read `docs/SCREENING_QUEUE_BATCH_ACTIONS.md`.
9. Review `src/marketsentry/config.py`.
10. Review `src/marketsentry/cli.py`.
11. Review `src/marketsentry/dashboard_app.py`.
12. Review `src/marketsentry/operator_workflow.py`.
13. Review `src/marketsentry/manual_score_entry.py`.
14. Review existing source adapter patterns in `src/marketsentry/source_adapters/`.
15. Search for the local HowLoud OpenAPI file if present:
    - `docs/HowLoud openapi.json`
    - `docs/howloud_openapi.json`
    - any similarly named HowLoud file under `docs/`
16. Do not print, request, expose, commit, or log any API key or secret.
17. Confirm the repository URL is `https://github.com/rogerfiske/Market_Sentry`.
18. Keep `PRD.md` and `Architecture.md` in the project root.
19. Use `src/marketsentry/` as the Python package path.
20. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
21. Do not implement Redfin rendered capture in this milestone.
22. Do not implement new Redfin live retrieval or scraping.
23. Do not run live network calls in tests.
24. Do not add outbound notifications or email sending.
25. Quiet Score gatekeeper must remain unchanged.
26. Low Vibrancy must not override poor Quiet.
27. Do not add walkability parsing or walkability fields.
28. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

---

## Current state and context

Milestone 54 completed:

- manual score validation
- `candidate-score-status`
- `list-candidates-needing-scores`
- combined score/noise entry command
- manual score entry export
- dashboard Manual Quiet/Vibrancy Entry section
- full tests: `2979 passed, 18 warnings`
- commit: `0543872`

Known real data:

```text
Candidate 4: 32420 San Marco Dr
Quiet 9.9
Vibrancy 1.3
Gatekeeper pass
Watchlisted

Candidate 5: 32152 Camino Nunez
Quiet 6.9
Vibrancy 1.1
Gatekeeper fail_noise_risk
Noise risk high
Sources: traffic, airport, nighttime_racing
Purpose: noise-risk control case
```

The user has a HowLoud basic/free API key, but the key must not be requested, printed, stored in source, or committed.

The user may have saved HowLoud OpenAPI documentation locally in `docs/`.

---

## Critical project rules

1. Quiet Score remains the gatekeeper.
2. Quiet threshold remains `>= 7.0`.
3. Low Vibrancy never overrides poor Quiet.
4. Redfin Quiet/Vibrancy and HowLoud are separate evidence sources.
5. Do not blend HowLoud into Redfin Quiet.
6. Do not overwrite Redfin source-of-truth fields.
7. Local operator knowledge must be preserved.
8. Use neutral language.
9. Do not infer seller intent.
10. Do not make purchase recommendations.
11. Walkability is excluded.
12. HowLoud calls must be explicit and opt-in.
13. Tests must not perform live network calls.
14. Browser automation is out of scope.

---

## Required implementation

### 1. HowLoud configuration

Add configuration support without storing secrets.

Preferred pattern:

```text
MARKETSENTRY_HOWLOUD_API_KEY
MARKETSENTRY_HOWLOUD_ENABLED
MARKETSENTRY_HOWLOUD_BASE_URL
MARKETSENTRY_HOWLOUD_TIMEOUT_SECONDS
```

Requirements:

- API key read only from environment or existing local `.env` mechanism if the project already supports it.
- Never print the API key.
- Never include the API key in logs, reports, test output, or exceptions.
- Default enabled state should be safe/off unless an explicit command is run.
- Provide a `--dry-run` option for CLI commands.
- Provide clear error if key is missing.

### 2. Schema

Add a table such as:

```sql
howloud_observations
```

Suggested columns:

```text
observation_id INTEGER PRIMARY KEY AUTOINCREMENT
candidate_id INTEGER
watched_property_id INTEGER
address TEXT
city TEXT
state TEXT
zip TEXT
request_source TEXT
noise_score REAL
traffic_score REAL
airport_score REAL
locality_score REAL
raw_score_label TEXT
provider TEXT DEFAULT 'HowLoud'
provider_version TEXT
raw_response_json TEXT
confidence REAL
status TEXT
error_message TEXT
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

Use the actual HowLoud response shape after inspecting local OpenAPI docs. Adjust columns as needed, but keep provider-specific values separate from Redfin fields.

Schema must be idempotent.

### 3. Adapter module

Create:

```text
src/marketsentry/howloud_adapter.py
```

or a source adapter under:

```text
src/marketsentry/source_adapters/howloud_adapter.py
```

Implement models such as:

```text
HowLoudAddressRequest
HowLoudObservation
HowLoudEnrichmentResult
HowLoudComparisonResult
HowLoudConfigStatus
```

Functions:

```text
build_howloud_request_for_candidate(...)
fetch_howloud_noise(...)
save_howloud_observation(...)
get_latest_howloud_observation(...)
compare_howloud_to_redfin(...)
enrich_candidate_with_howloud(...)
list_candidates_needing_howloud(...)
export_howloud_noise_report(...)
```

Network behavior:

- No network call unless explicit command or function option requests it.
- Tests must monkeypatch/mock network calls.
- HTTP client must have timeout.
- HTTP errors must be captured in `status` and `error_message`.
- Raw response may be stored only if it contains no secrets.
- Sanitize any headers/errors before writing logs/reports.
- If existing `source_adapters/http_client.py` provides a safe audited pattern, use it.

### 4. Comparison logic

Create neutral comparison fields.

Examples:

```text
redfin_quiet_score
redfin_vibrancy_score
howloud_noise_score
howloud_traffic_score
howloud_airport_score
agreement_level
comparison_note
needs_manual_review
```

Do not convert HowLoud into Redfin Quiet. Do not change gatekeeper logic.

Suggested comparison categories:

```text
agreement_clear
possible_disagreement
missing_redfin_score
missing_howloud_score
manual_review_needed
```

Example neutral note:

```text
HowLoud indicates elevated traffic noise while Redfin Quiet is high. Review manually before relying on either source.
```

For Candidate 5-like cases:

```text
Redfin Quiet is below the gatekeeper threshold. HowLoud can provide supporting context but does not change the gatekeeper result.
```

### 5. CLI commands

Add commands:

```text
python -m marketsentry.cli howloud-config-status
python -m marketsentry.cli list-candidates-needing-howloud
python -m marketsentry.cli enrich-candidate-howloud --candidate-id <id> --dry-run
python -m marketsentry.cli enrich-candidate-howloud --candidate-id <id>
python -m marketsentry.cli compare-howloud-redfin --candidate-id <id>
python -m marketsentry.cli export-howloud-noise-report
```

Requirements:

- canonical DB default
- explicit `--db` supported
- dry-run does not call network or mutate DB
- non-dry-run requires explicit command and API key
- clear output when key missing
- no API key printed
- no live call in tests

### 6. Dashboard integration

Add a dashboard section:

```text
HowLoud Noise Enrichment
```

It should include:

- config status without exposing key
- candidates needing HowLoud
- candidate selector
- dry-run preview
- explicit Enrich with HowLoud button
- latest HowLoud observation
- comparison to Redfin Quiet/Vibrancy
- warning that HowLoud does not override Quiet gatekeeper
- export report button
- no mutation on dashboard load

Dashboard must not call HowLoud on load.

### 7. Reports

Create exports:

```text
data/exports/howloud_noise_report_YYYYMMDD_HHMMSS.csv
data/exports/howloud_noise_report_YYYYMMDD_HHMMSS.md
```

Report fields:

- candidate ID
- address
- Redfin URL clickable in Markdown
- Redfin Quiet/Vibrancy
- Redfin gatekeeper result
- latest HowLoud scores/labels
- comparison category
- needs manual review
- noise notes
- created_at
- status/error if failed

### 8. Documentation

Create:

```text
docs/HOWLOUD_NOISE_ENRICHMENT.md
docs/decisions/054-howloud-noise-enrichment.md
docs/prompts/Market_Sentry_Claude_Prompt_055_HowLoud_Noise_Enrichment.md
```

Update:

```text
README.md
docs/RUNBOOK.md
docs/OPERATOR_WORKFLOW.md
docs/MANUAL_SCORE_ENTRY.md
```

Docs should explain:

- why HowLoud is separate from Redfin Quiet
- how to configure the API key without committing it
- how to check config status
- dry-run vs real enrichment
- how to enrich one candidate
- how to compare HowLoud to Redfin
- how to export report
- that no browser automation is used
- that no Redfin fields are overwritten
- that HowLoud does not override the Quiet gatekeeper

### 9. Tests

Add tests for:

- schema creation idempotent
- config status with no key
- config status with key present but masked
- dry-run builds request and does not call network
- missing key prevents real call
- mocked successful response saved
- mocked HTTP error saved or reported safely
- no secret appears in result/report/log output
- latest observation retrieval
- candidate needing HowLoud list
- compare HowLoud to Redfin with agreement
- compare HowLoud to Redfin with possible disagreement
- compare HowLoud to Redfin with missing Redfin scores
- compare HowLoud to Redfin with missing HowLoud scores
- candidate 5-like gatekeeper failure remains failure
- report CSV export
- report Markdown export with clickable Redfin link
- CLI `howloud-config-status`
- CLI `list-candidates-needing-howloud`
- CLI `enrich-candidate-howloud --dry-run`
- CLI missing-key behavior
- CLI mocked success path
- CLI `compare-howloud-redfin`
- CLI `export-howloud-noise-report`
- dashboard HowLoud section loads
- dashboard does not call network on load
- canonical DB default is used
- explicit custom `--db` works
- no browser automation
- no Redfin live scraping
- no outbound notifications
- no credentials stored/requested
- no walkability fields
- Quiet gatekeeper unchanged
- low Vibrancy does not override poor Quiet
- tests perform no real network calls

### 10. Code standards

- Python 3.11+
- type hints
- docstrings for public functions
- PEP8 compliant
- no unused imports
- keep functions small and testable
- use existing project patterns
- no browser automation
- no outbound notifications
- no credential logging
- no walkability fields
- all network behavior opt-in and mocked in tests

---

## Quality gates

- Full pytest suite passes 100%.
- Test count must be at least current baseline `2979`.
- CLI commands import and run.
- Dashboard loads.
- HowLoud section loads.
- Dry-run makes no network call and no DB mutation.
- Real enrichment requires explicit command and API key.
- API key is never printed/logged/reported.
- HowLoud observations are stored separately from Redfin fields.
- Redfin Quiet/Vibrancy are not overwritten.
- Quiet gatekeeper unchanged.
- Low Vibrancy does not override poor Quiet.
- No Redfin live retrieval or scraping added.
- No browser automation added.
- No outbound notifications added.
- No credentials stored/requested.
- Walkability remains excluded.
- Custom `--db` still works.
- README and docs updated.
- Changes committed and pushed to origin/main.

---

## Completion report required

When finished, provide:

1. Summary of what was implemented.
2. Files created or modified.
3. Exact commands run.
4. Final test results with full pytest summary showing 100% pass.
5. Coverage result and whether coverage changed.
6. Dependency changes, if any.
7. Assumptions made from the HowLoud OpenAPI docs.
8. Blockers or risks remaining.
9. Schema changes.
10. Example `howloud-config-status` output with no key and with masked key.
11. Example `list-candidates-needing-howloud` output.
12. Example `enrich-candidate-howloud --dry-run` output.
13. Example missing-key output for real enrichment.
14. Example mocked/successful enrichment output if exercised safely.
15. Example `compare-howloud-redfin` output.
16. Example `export-howloud-noise-report` output.
17. Example dashboard behavior added.
18. Confirmation that HowLoud data is stored separately from Redfin Quiet/Vibrancy.
19. Confirmation that Redfin source-of-truth fields are not overwritten.
20. Confirmation that Quiet Score gatekeeper remains unchanged.
21. Confirmation that low Vibrancy does not override poor Quiet.
22. Confirmation that no Redfin live retrieval or scraping was added.
23. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
24. Confirmation that no outbound notifications are sent.
25. Confirmation that no credentials are stored, printed, logged, committed, or requested.
26. Confirmation that walkability fields were not added.
27. Confirmation that tests perform no real network calls.
28. Recommended next implementation step.
29. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 55 complete until all tests pass.
