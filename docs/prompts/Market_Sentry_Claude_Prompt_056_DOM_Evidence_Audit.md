# Claude Code Prompt 056 - Effective DOM Evidence Audit and Confidence Report

You are Claude Code Opus 4.6 working in Windsurf IDE on Market_Sentry.

Repository: https://github.com/rogerfiske/Market_Sentry
Local path: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted milestone: 55A
Current accepted commit: a30dfde
Current test baseline: 3115 passed, 18 warnings

## PM decision

Proceed with Milestone 56: Effective DOM Evidence Audit and Confidence Report.

This is the next feature milestone after the M55A stabilization pass. It adds no new external dependency and strengthens one of Market_Sentry's differentiators: property-level exposure history, reset evidence, and churn preservation.

Do not implement live retrieval, scraping, browser automation, outbound notifications, credential handling, walkability fields, or bypass mechanisms.

## Purpose

Milestone 56 should create an operator-facing evidence audit for Effective DOM v1/v2 and Churn Index.

Target workflow:

```text
Candidate or watched property exists
-> system gathers listing-event and county-verification evidence
-> Effective DOM v1/v2 and Churn Index are shown side by side
-> reset boundary and evidence are explained
-> missing/weak evidence is flagged
-> operator receives a confidence rating and audit trail
-> report can be exported for review
```

This is an evidence and confidence report, not a purchase recommendation.

## Before starting

Read:

- PRD.md
- Architecture.md
- README.md
- docs/RUNBOOK.md
- docs/OPERATOR_WORKFLOW.md

Review:

- src/marketsentry/effective_dom.py
- src/marketsentry/effective_dom_v2_calculator.py
- src/marketsentry/effective_dom_v2_persistence.py
- src/marketsentry/churn_index.py
- county-related modules
- src/marketsentry/candidate_report.py
- src/marketsentry/operator_workflow.py
- src/marketsentry/dashboard_app.py
- src/marketsentry/cli.py
- existing DOM v1/v2, churn, county, watchlist tests

Confirm repo URL. Keep PRD.md and Architecture.md in root. Use src/marketsentry/ as package path.

Do not add live retrieval, scraping, browser automation, outbound notifications, credentials, walkability, or bypass mechanisms. Quiet gatekeeper remains unchanged. Low Vibrancy must not override poor Quiet. Churn Index must remain separate from Effective DOM. County-confirmed transfer may reset Effective DOM but must not erase Churn Index.

## Current state

Milestone 55A completed:

- exports_dir propagation fixed
- release-doc test isolation fixed
- coverage floor fail_under = 75 enforced
- tests: 3115 passed, 18 warnings
- commit: a30dfde

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
Purpose: noise-risk control case
```

## Critical project rules

1. Effective DOM and Churn Index are separate.
2. Effective DOM v2 may use county-confirmed transfer as a reset boundary.
3. Churn Index survives transfer/reset boundaries.
4. Evidence quality must be visible.
5. Missing evidence must be visible.
6. Do not infer seller intent.
7. Use neutral language.
8. Do not make purchase recommendations.
9. Reports are analytical aids.
10. Do not add live retrieval or scraping.
11. Do not add browser automation.
12. Do not add walkability fields.

## Required implementation

### 1. Evidence audit module

Create:

```text
src/marketsentry/dom_evidence_audit.py
```

Implement models such as:

- DomEvidenceItem
- DomResetEvidence
- DomChurnEvidence
- DomEvidenceGap
- DomConfidenceScore
- DomEvidenceAudit
- DomEvidenceAuditSummary
- DomEvidenceReportRow

The audit should gather and explain:

- candidate/property ID
- address
- Redfin URL if available
- listing events used
- current listing instance start/end if known
- listing status changes
- price-change events if available
- displayed DOM if present
- Effective DOM v1
- Effective DOM v2
- v2 reset boundary, if any
- county-confirmed transfer date, if any
- county evidence source/status
- Churn Index
- relist/remove/price-change counts if available
- evidence gaps
- confidence score/category
- neutral explanation

### 2. Confidence scoring

Add a simple explainable confidence model.

Categories:

```text
high
moderate
low
insufficient
```

Factors that increase confidence:

- multiple listing events available
- current listing start date known
- county transfer evidence present when reset applied
- Redfin detail enrichment present
- source pages present
- cross-site/county corroboration present if available

Factors that lower confidence:

- displayed DOM only, no event history
- missing current listing start date
- missing listing events
- missing or conflicting county evidence
- v1/v2 mismatch without reset evidence
- sparse source pages
- stale observations

The scoring must be deterministic and tested.

### 3. Reset explanation

For any v2 reset, report:

- transfer date
- evidence source
- whether reset was applied
- what DOM value changed because of reset
- what churn evidence remains

Example language:

```text
Effective DOM v2 applies a county-confirmed transfer reset on 2025-11-18. Exposure before that boundary is excluded from Effective DOM v2, but listing churn remains separately reported in the Churn Index.
```

If reset evidence is missing:

```text
No county-confirmed transfer reset evidence is available. Effective DOM v2 does not apply a reset.
```

### 4. Evidence gaps

Add explicit evidence gaps such as:

- missing_listing_events
- missing_current_listing_start
- missing_displayed_dom
- missing_county_transfer_evidence
- missing_source_page
- conflicting_dom_values
- stale_observation

These should appear in CLI output and reports.

### 5. CLI commands

Add commands:

```text
python -m marketsentry.cli dom-evidence-audit --candidate-id <id>
python -m marketsentry.cli dom-evidence-audit --watched-property-id <id>
python -m marketsentry.cli list-dom-evidence-gaps
python -m marketsentry.cli export-dom-evidence-audit-report
```

Requirements:

- canonical DB default
- explicit --db supported
- optional --candidate-id
- optional --watched-property-id
- report all if no ID supplied for export
- clear output
- no live retrieval
- no mutation except report exports
- no purchase recommendation language

### 6. Dashboard integration

Add dashboard section:

```text
Effective DOM Evidence Audit
```

Include:

- total audited
- confidence counts
- number with evidence gaps
- number with v2 reset evidence
- number with churn preserved
- candidate/property selector
- v1/v2 side-by-side
- Churn Index shown separately
- reset explanation
- evidence gaps
- confidence category
- clickable Redfin link when available
- export report button
- no mutation on dashboard load

### 7. Reports

Export:

```text
data/exports/dom_evidence_audit_YYYYMMDD_HHMMSS.csv
data/exports/dom_evidence_audit_YYYYMMDD_HHMMSS.md
```

Report fields:

- candidate ID
- watched property ID
- address
- Redfin URL clickable in Markdown
- displayed DOM
- Effective DOM v1
- Effective DOM v2
- v1/v2 delta
- reset applied yes/no
- reset date
- reset evidence source/status
- Churn Index
- churn event counts
- confidence category
- confidence score
- evidence gaps
- neutral explanation

### 8. Documentation

Create:

- docs/DOM_EVIDENCE_AUDIT.md
- docs/decisions/056-dom-evidence-audit-confidence-report.md
- docs/prompts/Market_Sentry_Claude_Prompt_056_DOM_Evidence_Audit.md

Update:

- README.md
- docs/RUNBOOK.md
- docs/OPERATOR_WORKFLOW.md

Docs should explain Effective DOM v1 vs v2, county reset, churn preservation, confidence categories, evidence gaps, CLI usage, export usage, and the no-seller-intent/no-live-retrieval boundary.

### 9. Tests

Add tests for:

- audit with no listing events
- audit with displayed DOM only
- audit with listing events and no county reset
- audit with listing events and county reset
- v2 reset excludes pre-transfer exposure
- churn remains after reset
- evidence gaps for missing listing events
- evidence gaps for missing county evidence
- confidence high/moderate/low/insufficient
- deterministic confidence scoring
- reset explanation text
- neutral language checks
- no seller-intent language
- CLI dom-evidence-audit --candidate-id
- CLI dom-evidence-audit --watched-property-id
- CLI list-dom-evidence-gaps
- CLI export-dom-evidence-audit-report
- dashboard section loads
- report CSV export
- report Markdown export with clickable Redfin links
- canonical DB default
- explicit custom --db
- no live retrieval
- no browser automation
- no outbound notifications
- no credentials
- no walkability fields
- Quiet gatekeeper unchanged
- low Vibrancy does not override poor Quiet
- tests perform no real network calls

## Quality gates

- Full pytest suite passes 100%.
- Test count at least 3115.
- Coverage floor remains enforced and passing.
- Dashboard loads.
- CLI commands run.
- DOM Evidence Audit report exports CSV and Markdown.
- Churn Index remains separate from Effective DOM.
- County reset does not erase churn.
- No seller-intent or purchase-recommendation language.
- No live retrieval or scraping added.
- No browser automation added.
- No outbound notifications added.
- No credentials stored/requested/printed/logged/committed.
- Quiet gatekeeper unchanged.
- Low Vibrancy does not override poor Quiet.
- Walkability remains excluded.
- Working tree clean after tests.
- Changes committed and pushed to origin/main.

## Completion report required

Provide:

1. Summary of what was implemented.
2. Files created or modified.
3. Exact commands run.
4. Final pytest result.
5. Coverage result and whether the fail_under gate passed.
6. Dependency changes.
7. Assumptions made.
8. Blockers or risks remaining.
9. Schema changes, if any.
10. Example dom-evidence-audit --candidate-id output.
11. Example dom-evidence-audit --watched-property-id output.
12. Example list-dom-evidence-gaps output.
13. Example export-dom-evidence-audit-report output.
14. Example dashboard behavior added.
15. Confirmation Effective DOM v1/v2 and Churn Index are reported separately.
16. Confirmation county reset does not erase Churn Index.
17. Confirmation no seller-intent language or purchase recommendations were added.
18. Confirmation no live retrieval or scraping was added.
19. Confirmation no outbound notifications are sent.
20. Confirmation no credentials are stored, printed, logged, committed, or requested.
21. Confirmation Redfin source-of-truth fields are not overwritten.
22. Confirmation Quiet Score gatekeeper remains unchanged.
23. Confirmation low Vibrancy does not override poor Quiet.
24. Confirmation walkability fields were not added.
25. Confirmation no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
26. Confirmation tests perform no real network calls.
27. Recommended next implementation step.
28. Git commit hash after committing and pushing to origin/main.

Do not mark Milestone 56 complete until all tests pass, coverage gate passes, and the working tree is clean after tests.
