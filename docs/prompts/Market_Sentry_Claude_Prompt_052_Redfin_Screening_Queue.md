# Claude Code Prompt 052 - Initial Redfin Screening Queue with Clickable Links and Save for Analysis

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: f36600f (Milestone 51A complete)

## Purpose

Milestone 52 should create an operator-friendly initial Redfin screening queue.

The user wants to move from command-line/CSV-heavy workflow toward a dashboard workflow:

```text
screening list -> clickable Redfin links -> Save for Analysis -> candidate added/processed -> dashboard/reports updated
```

This milestone should provide a local, safe, dashboard-based queue for initial property screening. It should not implement new live scraping or browser automation.

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read README.md.
4. Read docs/RUNBOOK.md.
5. Read docs/OPERATOR_WORKFLOW.md.
6. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
7. Review src/marketsentry/operator_workflow.py.
8. Review src/marketsentry/redfin_url_import.py.
9. Review src/marketsentry/redfin_fixture_parser.py.
10. Review src/marketsentry/redfin_detail_enrichment.py.
11. Review src/marketsentry/dashboard_app.py.
12. Review src/marketsentry/cli.py.
13. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
14. Keep PRD.md and Architecture.md in the project root.
15. Use src/marketsentry/ as the Python package path.
16. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
17. Do not implement new Redfin live retrieval behavior in this milestone.
18. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval.
19. Do not run any live network calls in tests.
20. Do not make scheduled tasks run live retrieval by default.
21. Do not add walkability parsing or walkability fields.
22. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

## Context from live user validation

The user successfully validated:

- importing Redfin URLs
- enriching candidates from saved Redfin detail HTML
- manually adding Quiet/Vibrancy
- adding noise notes
- saving candidate 4 to watchlist
- holding candidate 5 as a noise-risk control case
- running operator refresh workflow

Milestone 51A fixed operator workflow defaults and refresh workflow bugs.

Now the next usability gap is the initial screening stage: the user needs a dashboard list of potential Redfin properties with clickable links and a simple “Save for Analysis” action.

## Critical project rules

1. Quiet Score remains the gatekeeper.
2. Target is very high Quiet and very low Vibrancy.
3. Low Vibrancy does not override poor Quiet.
4. Any mention of gas means natural gas evidence.
5. Walkability-type information is excluded.
6. Effective DOM and Churn Index remain separate.
7. Churn Index remains reportable even if Effective DOM is reset.
8. Use neutral language. Do not infer seller intent.
9. Reports are analytical aids, not purchase recommendations.
10. No live retrieval/scraping/browser automation in this milestone.
11. Operator actions can mutate local candidate queue only when explicitly clicked or invoked.

## Implement

### 1. Screening queue module

Create:

```text
src/marketsentry/redfin_screening_queue.py
```

Purpose: manage a local initial screening queue before full candidate analysis.

Required models:

- RedfinScreeningItem
- RedfinScreeningImportResult
- RedfinScreeningActionResult
- RedfinScreeningQueueSummary
- RedfinScreeningReportRow

Required functions:

- ensure_redfin_screening_queue_schema(...)
- import_redfin_screening_urls(...)
- list_redfin_screening_items(...)
- summarize_redfin_screening_queue(...)
- save_screening_item_for_analysis(...)
- reject_screening_item(...)
- hold_screening_item(...)
- mark_screening_item_opened(...)
- export_redfin_screening_queue(...)

### 2. Database schema

Add a local table:

```sql
redfin_screening_queue
```

Suggested columns:

- screening_id INTEGER PRIMARY KEY AUTOINCREMENT
- redfin_url TEXT NOT NULL
- normalized_redfin_url TEXT
- address TEXT
- city TEXT
- state TEXT DEFAULT 'CA'
- zip TEXT
- price REAL
- beds INTEGER
- baths REAL
- sqft INTEGER
- lot_size REAL
- displayed_dom INTEGER
- quiet_score REAL
- vibrancy_score REAL
- status TEXT DEFAULT 'new'
- user_screening_decision TEXT DEFAULT 'new'
- user_notes TEXT
- source_file TEXT
- source_type TEXT
- opened_at TIMESTAMP
- saved_for_analysis_at TIMESTAMP
- candidate_id INTEGER
- created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

Statuses/decisions:

- new
- opened
- saved_for_analysis
- rejected
- hold
- duplicate
- error

Add useful indexes:

- normalized_redfin_url
- status
- user_screening_decision
- candidate_id
- created_at

Schema must be idempotent.

### 3. Import sources

Support two local import methods:

#### A. CSV import

CLI command:

```text
marketsentry import-redfin-screening-urls --file data/imports/redfin_screening_urls.csv
```

CSV should accept flexible columns:

- redfin_url required
- address optional
- city optional
- price optional
- beds optional
- baths optional
- sqft optional
- notes optional

Deduplicate by normalized Redfin URL.

#### B. Saved Redfin search fixture import

CLI command:

```text
marketsentry import-redfin-screening-fixture --file data/raw/redfin/search/<file>.html
```

Use existing Redfin search fixture parsing logic where possible. Extract property URLs and any available summary fields. Insert into screening queue, not directly into candidate_review_queue.

This is local-only fixture parsing, not live retrieval.

### 4. Save for Analysis action

Implement:

```text
marketsentry save-screening-item-for-analysis --screening-id <id>
```

Behavior:

1. Locate screening item.
2. Insert into candidate_review_queue using existing candidate insertion/dedup logic where possible.
3. Preserve Redfin URL and available summary data.
4. Mark screening item as saved_for_analysis.
5. Store candidate_id on screening item.
6. Do not duplicate candidates if URL already exists.
7. If candidate already exists, link to existing candidate_id and mark saved_for_analysis.
8. Return operator-friendly summary.

This is the key “Save for Analysis” action.

### 5. Other screening actions

Add CLI commands:

```text
marketsentry redfin-screening-status
marketsentry list-redfin-screening-items
marketsentry reject-screening-item --screening-id <id> --notes "..."
marketsentry hold-screening-item --screening-id <id> --notes "..."
marketsentry mark-screening-item-opened --screening-id <id>
marketsentry export-redfin-screening-queue
```

These should be local-only and explicit operator actions.

### 6. Dashboard integration

Add a dashboard section:

```text
Initial Redfin Screening
```

It should include:

- summary metrics:
  - total screening items
  - new
  - opened
  - saved_for_analysis
  - rejected
  - hold
  - duplicates/errors
- screening queue table
- clickable Redfin URL links
- row/action workflow using forms:
  - screening_id input
  - Open/mark opened
  - Save for Analysis
  - Reject
  - Hold
  - Notes text area
- import helper section:
  - show expected CSV format
  - show local folder paths for saved search fixtures
- latest screening export link

Important: Streamlit cannot always make per-row buttons easily without state issues. Use simple explicit forms by screening_id if needed. Reliability is more important than fancy UI.

### 7. Operator-facing reports

Export:

```text
data/exports/redfin_screening_queue_YYYYMMDD_HHMMSS.csv
data/exports/redfin_screening_queue_YYYYMMDD_HHMMSS.md
```

Report should include:

- screening ID
- address
- city
- price
- beds/baths/sqft
- quiet/vibrancy if known
- status/decision
- candidate_id if saved
- clickable Redfin URL in Markdown
- user notes

### 8. Documentation

Create:

```text
docs/REDFIN_SCREENING_QUEUE.md
docs/decisions/051-redfin-screening-queue.md
docs/prompts/Market_Sentry_Claude_Prompt_052_Redfin_Screening_Queue.md
```

Update:

- README.md
- docs/RUNBOOK.md
- docs/OPERATOR_WORKFLOW.md
- docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md

Documentation should explain in plain English:

- how the screening queue differs from the candidate review queue
- how to import Redfin URLs into screening
- how to use clickable links
- how to save for analysis
- how to reject/hold
- when a property becomes a candidate
- when a property becomes watched
- why this does not scrape Redfin
- why this is safe/local-only

### 9. Tests

Add tests for:

- schema creation idempotent
- CSV import with valid URLs
- CSV import missing required URL rejected
- duplicate URL skipped/linked
- saved fixture import uses local fixture only
- list screening items
- summarize screening queue
- mark opened
- reject item
- hold item
- save for analysis creates candidate
- save for analysis links existing candidate without duplicate
- save for analysis preserves available summary fields
- invalid screening ID handled
- export CSV
- export Markdown
- CLI import-redfin-screening-urls
- CLI redfin-screening-status
- CLI list-redfin-screening-items
- CLI save-screening-item-for-analysis
- CLI reject/hold/open
- dashboard Initial Redfin Screening section loads
- clickable URL values present in report/table
- no live retrieval
- no browser automation
- no outbound notifications
- no credentials stored/requested
- no Redfin source-of-truth overwrite outside explicit local candidate creation
- Quiet Score gatekeeper unchanged
- no walkability fields
- no real network calls in tests

### 10. Code standards

- Python 3.11+
- PEP8 compliant
- type hints required
- docstrings required for all functions
- remove unused imports
- use standard library only unless existing dependencies are already used
- no browser automation
- no Playwright/Selenium
- no bypassing CAPTCHAs, paywalls, login walls, anti-bot protections, or technical access controls
- no network calls in tests
- do not import smtplib
- do not import requests/httpx/urllib.request for this feature
- use neutral language
- do not make purchase recommendations
- do not add walkability parsing or fields

## Quality gates

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- Dashboard Initial Redfin Screening section loads.
- CSV import works.
- Saved fixture import works locally.
- Save for Analysis creates/links candidate correctly.
- Duplicate Save for Analysis does not duplicate candidate.
- Reject/Hold/Open actions update only screening queue.
- No live retrieval or scraping added.
- No browser automation added.
- No outbound notifications added.
- No credentials stored/requested.
- Quiet gatekeeper remains unchanged.
- Walkability remains excluded.
- Changes committed and pushed to origin/main.

## Completion report required

When finished, provide:

1. Summary of what was implemented.
2. Files created or modified.
3. Exact commands run.
4. Final test results with full pytest summary showing 100% pass.
5. Dependency changes, if any.
6. Assumptions made.
7. Blockers or risks remaining.
8. Schema changes.
9. Example `redfin-screening-status` output.
10. Example `import-redfin-screening-urls` output.
11. Example `import-redfin-screening-fixture` output.
12. Example `list-redfin-screening-items` output.
13. Example `save-screening-item-for-analysis` output.
14. Example reject/hold/open outputs.
15. Example screening queue report paths and row counts.
16. Dashboard Initial Redfin Screening section added.
17. Confirmation that Save for Analysis creates/links candidates only through explicit operator action.
18. Confirmation that no live retrieval or scraping was added.
19. Confirmation that no outbound notifications are sent.
20. Confirmation that no credentials are stored or requested.
21. Confirmation that Redfin source-of-truth fields are not overwritten outside explicit local candidate creation.
22. Confirmation that Quiet Score gatekeeper remains unchanged.
23. Confirmation that walkability fields were not added.
24. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
25. Confirmation that tests perform no real network calls.
26. Recommended next implementation step.
27. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 52 complete until all tests pass.
