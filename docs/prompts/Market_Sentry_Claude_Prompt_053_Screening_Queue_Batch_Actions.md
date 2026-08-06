# Claude Code Prompt 053 - Screening Queue Batch Actions and Operator Refresh Integration

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry  
Local project folder: `C:\Users\Minis\CascadeProjects\Market_Sentry`  
Current accepted milestone: Milestone 52A  
Current accepted commit: `5a960be`  
Current known test baseline: `2791 passed, 18 warnings`  
Current branch: `main`

## Purpose

Milestone 53 should improve the operator usability of the new Redfin Screening Queue by adding batch actions and tighter integration with the existing operator refresh workflow.

The goal is to reduce one-at-a-time friction for a non-programmer user.

Target workflow:

```text
Initial Redfin Screening Queue
→ review multiple clicked Redfin links
→ batch hold/reject/save selected items
→ Save for Analysis creates/links candidates
→ system clearly shows next required step
→ optional local refresh/export after operator actions
→ dashboard and reports stay current
```

This milestone must remain local-first and safe. Do not add live retrieval, scraping, browser automation, outbound notifications, credential handling, or walkability fields.

---

## Before starting

1. Read `PRD.md`.
2. Read `Architecture.md`.
3. Read `README.md`.
4. Read `docs/RUNBOOK.md`.
5. Read `docs/OPERATOR_WORKFLOW.md`.
6. Read `docs/REDFIN_SCREENING_QUEUE.md`.
7. Read `docs/LOCAL_OPERATIONS_BUNDLE.md`.
8. Review `src/marketsentry/config.py`.
9. Review `src/marketsentry/cli.py`.
10. Review `src/marketsentry/dashboard_app.py`.
11. Review `src/marketsentry/redfin_screening_queue.py`.
12. Review `src/marketsentry/operator_workflow.py`.
13. Review `src/marketsentry/demo_data_cleanup.py`.
14. Run or inspect the current status commands:
    - `python -m marketsentry.cli status`
    - `python -m marketsentry.cli redfin-screening-status`
    - `python -m marketsentry.cli operator-workflow-status`
15. Confirm the repository URL is `https://github.com/rogerfiske/Market_Sentry`.
16. Keep `PRD.md` and `Architecture.md` in the project root.
17. Use `src/marketsentry/` as the Python package path.
18. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
19. Do not implement new live retrieval or scraping.
20. Do not run live network calls in tests.
21. Do not add outbound notifications or credential storage.
22. Quiet Score gatekeeper must remain unchanged.
23. Low Vibrancy must not override poor Quiet.
24. Do not add walkability parsing or walkability fields.
25. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

---

## Current state and context

Milestone 52 implemented:

- `redfin_screening_queue.py`
- `redfin_screening_queue` table
- CSV import
- saved Redfin search fixture import
- clickable Redfin URLs in reports/dashboard
- Save for Analysis
- Reject/Hold/Open actions
- dashboard section: `Initial Redfin Screening`
- screening CSV/Markdown exports

Milestone 52A stabilized:

- all remaining `data/market_sentry.db` defaults fixed
- correct default DB is now `db/marketsentry.db`
- demo cleanup command added:
  - `python -m marketsentry.cli cleanup-demo-data --dry-run`
  - `python -m marketsentry.cli cleanup-demo-data --confirm`
- README heading fixed
- full tests: `2791 passed, 18 warnings`
- commit: `5a960be`

The operator has imported three real Temecula screening items:

```text
31801 Valone Ct
31457 Britton Cir
41451 Royal Dornoch Ct
```

Known real candidate/watchlist examples:

```text
Candidate 4: 32420 San Marco Dr, Temecula
Quiet 9.9, Vibrancy 1.3, saved/watchlisted

Candidate 5: 32152 Camino Nunez, Temecula
Quiet 6.9, Vibrancy 1.1, fail_noise_risk/noise-risk control
```

---

## Critical project rules

1. Quiet Score is the gatekeeper.
2. Threshold remains Quiet >= 7.0.
3. Low Vibrancy does not override poor Quiet.
4. Churn Index remains separate from Effective DOM.
5. County-confirmed transfer may reset Effective DOM but must not erase Churn Index.
6. Use neutral language.
7. Do not infer seller intent.
8. Reports are analytical aids, not purchase recommendations.
9. Gas mentions are evidence of natural gas service.
10. Walkability is excluded.
11. Local operator knowledge and manual notes must be preserved.
12. Screening imports must not automatically create candidates.
13. Save for Analysis must remain an explicit operator action.

---

## Required implementation

### 1. Batch action models and functions

Extend `src/marketsentry/redfin_screening_queue.py`.

Add models such as:

```text
RedfinScreeningBatchActionRequest
RedfinScreeningBatchActionResult
RedfinScreeningNextStep
RedfinScreeningOperatorStatus
```

or equivalent.

Add functions:

```text
batch_save_screening_items_for_analysis(...)
batch_reject_screening_items(...)
batch_hold_screening_items(...)
batch_mark_screening_items_opened(...)
build_screening_next_steps(...)
summarize_screening_operator_status(...)
```

Batch behavior:

- Accept a list of screening IDs.
- Validate every ID.
- Perform only explicit requested action.
- Report per-item success/failure.
- Continue processing other IDs when one item fails, unless a transaction rollback is needed for data consistency.
- Deduplicate candidate creation exactly as existing single-item Save for Analysis does.
- Do not overwrite existing candidate source-of-truth fields.
- Preserve notes.
- Record updated timestamps.
- Return clear operator-friendly output.

### 2. CLI batch commands

Add CLI commands:

```text
python -m marketsentry.cli batch-save-screening-items --screening-ids 4,5,6 --notes "Batch save after visual review"
python -m marketsentry.cli batch-reject-screening-items --screening-ids 4,5,6 --notes "Does not fit screening criteria"
python -m marketsentry.cli batch-hold-screening-items --screening-ids 4,5,6 --notes "Needs more review"
python -m marketsentry.cli batch-mark-screening-items-opened --screening-ids 4,5,6
python -m marketsentry.cli screening-next-steps
```

Implementation details:

- Accept comma-separated IDs.
- Validate empty list, non-integer tokens, duplicate IDs, missing IDs.
- Output per-item status.
- Use canonical DB default from `config.database_path`.
- Support explicit `--db`.

### 3. Screening next-step logic

Add a clear local status report that tells the operator what to do next.

Examples:

```text
New screening items: open Redfin link and visually inspect.
Opened but undecided: choose Save for Analysis, Hold, or Reject.
Saved for analysis but missing Redfin detail HTML: save Redfin detail page to data/raw/redfin/details and run enrichment.
Candidates missing Quiet/Vibrancy: capture Redfin visual scores and enter them.
Candidates failing Quiet gatekeeper: add local noise notes or reject/hold as noise-risk control.
Watchlist ready: run operator refresh workflow.
```

This should not make purchase recommendations.

### 4. Operator refresh integration

Add optional refresh behavior after batch Save for Analysis and single Save for Analysis.

CLI options:

```text
--refresh
--no-refresh
```

Default should be no automatic heavy refresh unless project conventions already favor refresh. Prefer:

```text
default: --no-refresh
```

When `--refresh` is used:

- run existing local operator refresh workflow
- no live retrieval
- no outbound notifications
- clearly report refresh outputs/report paths
- failures in refresh should not erase successful batch actions

### 5. Dashboard batch actions

Update `src/marketsentry/dashboard_app.py`.

Enhance `Initial Redfin Screening` with:

- multi-ID input field such as `4,5,6`
- batch action forms:
  - Batch Save for Analysis
  - Batch Reject
  - Batch Hold
  - Batch Mark Opened
- notes text area for batch actions
- optional checkbox:
  - Run local refresh after Save for Analysis
- visible `Next Steps` panel
- visible warning when:
  - screening items are saved but candidate details/enrichment are missing
  - candidates are missing Quiet/Vibrancy
  - demo/sample records remain in the DB
  - likely stray DB files exist
- no hidden automatic mutation on dashboard load

Streamlit reliability is more important than fancy UI. Simple forms by comma-separated ID list are acceptable.

### 6. Screening queue export improvements

Enhance `export_redfin_screening_queue(...)` or add a companion export so reports include:

- batch action history if available
- next recommended operator step
- whether item is saved for analysis
- candidate ID
- whether candidate has Redfin detail enrichment
- whether candidate has Quiet/Vibrancy
- whether candidate is watchlisted
- clickable Redfin URL

Do not overcomplicate schema if existing audit/action tracking can be used.

### 7. Documentation

Create:

```text
docs/SCREENING_QUEUE_BATCH_ACTIONS.md
docs/decisions/052-screening-queue-batch-actions.md
docs/prompts/Market_Sentry_Claude_Prompt_053_Screening_Queue_Batch_Actions.md
```

Update:

```text
README.md
docs/RUNBOOK.md
docs/OPERATOR_WORKFLOW.md
docs/REDFIN_SCREENING_QUEUE.md
```

Docs should explain:

- when to use single action vs batch action
- how to enter comma-separated IDs
- what Save for Analysis does
- what Save for Analysis does not do
- how to find IDs in the dashboard/table
- how to refresh reports after saving
- how to use `screening-next-steps`
- how to clean demo data before operator use
- why no live scraping is involved

### 8. Tests

Add tests for:

- parse comma-separated ID list
- duplicate ID handling
- invalid ID handling
- empty ID list handling
- batch mark opened
- batch reject
- batch hold
- batch save creates candidates
- batch save links existing candidates
- batch save does not duplicate candidates
- batch actions preserve notes
- per-item success/failure reporting
- transaction safety / partial failure behavior
- refresh option calls local refresh workflow only when requested
- refresh failure does not roll back successful save actions unless intentionally designed
- `screening-next-steps` output
- dashboard batch section loads
- export includes next steps and candidate status
- canonical DB default is used
- explicit custom `--db` works
- no live retrieval
- no browser automation
- no outbound notifications
- no credentials stored/requested
- no walkability fields
- Quiet gatekeeper unchanged
- tests perform no real network calls

### 9. Code standards

- Python 3.11+
- type hints
- docstrings for public functions
- PEP8 compliant
- no unused imports
- keep functions small and testable
- use existing patterns from the repo
- use standard library unless existing dependencies are already in use
- no network calls
- no browser automation
- no outbound notifications
- no credential handling
- no walkability fields

---

## Quality gates

- Full pytest suite passes 100%.
- Test count must be at least current baseline `2791`.
- CLI commands import and run.
- Dashboard loads.
- Batch actions work from CLI.
- Batch actions visible in dashboard.
- `screening-next-steps` provides clear next actions.
- Save for Analysis remains explicit.
- No screening import automatically creates candidates.
- No live retrieval or scraping added.
- No browser automation added.
- No outbound notifications added.
- No credentials stored/requested.
- Quiet gatekeeper unchanged.
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
7. Assumptions made.
8. Blockers or risks remaining.
9. Schema changes, if any.
10. Example `screening-next-steps` output.
11. Example `batch-save-screening-items` output.
12. Example `batch-reject-screening-items` output.
13. Example `batch-hold-screening-items` output.
14. Example `batch-mark-screening-items-opened` output.
15. Example Save for Analysis with `--refresh`.
16. Example dashboard behavior added.
17. Confirmation that Save for Analysis creates/links candidates only through explicit operator action.
18. Confirmation that screening import does not create candidates.
19. Confirmation that no live retrieval or scraping was added.
20. Confirmation that no outbound notifications are sent.
21. Confirmation that no credentials are stored or requested.
22. Confirmation that Redfin source-of-truth fields are not overwritten outside explicit local candidate creation/linking.
23. Confirmation that Quiet Score gatekeeper remains unchanged.
24. Confirmation that walkability fields were not added.
25. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
26. Confirmation that tests perform no real network calls.
27. Recommended next implementation step.
28. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 53 complete until all tests pass.
