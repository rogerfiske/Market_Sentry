# Claude Code Prompt 040 - Local Portfolio Review Pack and Print-Ready Property Briefs

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: df01665 (Milestone 39 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Review the current codebase through commit df01665.
8. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
9. Keep PRD.md and Architecture.md in the project root.
10. Use src/marketsentry/ as the Python package path.
11. Do not move PRD.md or Architecture.md into docs/.
12. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
13. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
14. Do not implement new Redfin live retrieval behavior in this milestone.
15. Do not run any live network calls in tests.
16. Do not make scheduled tasks run live retrieval by default.
17. Do not add walkability parsing or walkability fields.
18. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

## PM direction

Milestone 40 should add a local Portfolio Review Pack and print-ready Property Briefs.

This milestone must not add live retrieval, broaden scraping, change the Quiet Score gatekeeper, or automatically apply candidate/watchlist/alert actions.

The goal is to generate a practical local review packet that can be printed or viewed offline:

- portfolio-level summary
- per-property brief pages
- watchlist review priority
- Quiet/Vibrancy gatekeeper status
- Effective DOM v1/v2 and Churn Index
- gas and garage evidence
- county reset status
- cross-site confidence/discrepancies
- alert burden and lifecycle health
- operations digest status
- local next actions for review

This is a read-only/reporting milestone. It must not change candidate decisions, watchlist status, alert status, Redfin source-of-truth fields, or retrieval behavior. It must not infer seller intent. It must not make purchase recommendations.

## Critical project rules

1. Effective DOM v1 is listing-history-derived exposure without county reset integration.
2. Effective DOM v2 applies county-confirmed ownership transfer as a reset boundary when appropriate.
3. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
4. Churn Index remains reportable even when Effective DOM is reset.
5. Quiet Score is the gatekeeper and must remain unchanged.
6. Target is very high Quiet and very low Vibrancy.
7. Any mention of gas means natural gas supply/service evidence.
8. Walkability-type information is excluded.
9. Use neutral language. Do not infer seller intent.
10. Reports are analytical aids, not purchase recommendations.
11. Review packs are offline/local reports only and must not mutate candidate/watchlist/alert state.

## Implement

### 1. Portfolio review module

Create:

```text
src/marketsentry/portfolio_review_pack.py
```

Required models:

- PortfolioReviewPackSummary
- PortfolioReviewPropertyBrief
- PortfolioReviewMetric
- PortfolioReviewFlag
- PortfolioReviewNextAction
- PortfolioReviewPackRunResult

Required functions:

- build_portfolio_review_pack(...)
- build_property_review_brief(...)
- build_portfolio_summary(...)
- rank_portfolio_review_briefs(...)
- generate_property_next_actions(...)
- export_portfolio_review_pack(...)

## 2. Portfolio summary

Summarize:

- total watched properties
- active watched properties
- high priority watched properties
- properties passing Quiet gatekeeper
- properties failing Quiet gatekeeper
- properties missing Quiet score
- properties with gas evidence
- properties with garage evidence
- county reset applied count
- high Churn Index count
- high Effective DOM delta count
- low cross-site confidence count
- high discrepancy severity count
- open alert count
- high/critical open alert count
- lifecycle attention_required count
- lifecycle needs_review count
- digest score/status if available

Use neutral wording.

## 3. Property brief content

Each property brief should include:

- property_id
- candidate_id
- address/city/state/zip
- current price if available
- beds/baths/sqft if available
- watch priority/status
- Redfin URL if available
- Quiet Score and gatekeeper result
- Vibrancy Score
- gas evidence
- garage spaces
- Effective DOM v1
- Effective DOM v2
- Effective DOM delta
- county reset applied
- county reset date if available
- recent Churn Index
- listing churn count
- DOM reset count
- sale/rent alternation count
- cross-site confidence score
- discrepancy severity label
- open alert count
- high/critical alert count
- alert burden label
- lifecycle health score/label
- lifecycle gap count
- latest alert/lifecycle event if available
- recommended local review action

Do not include walkability fields.

Do not make purchase recommendations.

## 4. Review priority ranking

Create a neutral ordering for report presentation.

Priority inputs:

- Quiet gatekeeper failure should remain visible and separate.
- attention_required lifecycle health
- high/critical open alerts
- high discrepancy severity
- low cross-site confidence
- high Churn Index
- high Effective DOM delta
- missing key data
- active watch status
- user watch priority

Priority labels:

- immediate_review
- high_review
- normal_review
- monitor
- low_current_activity

Use neutral language.

## 5. Report export

Export Markdown as primary output:

```text
data/exports/portfolio_review_pack_YYYYMMDD_HHMMSS.md
```

Also export CSV summary/detail if straightforward:

```text
data/exports/portfolio_review_pack_YYYYMMDD_HHMMSS.csv
```

Markdown structure:

- Title and generated timestamp
- Safety note: local analytical review aid, not purchase recommendation
- Portfolio summary
- Top review priorities
- Per-property briefs
- Local next actions
- Source/report freshness note

CSV rows can be one property per row with key fields.

## 6. CLI commands

Add:

```text
marketsentry portfolio-review-pack
marketsentry export-portfolio-review-pack
```

### portfolio-review-pack

Options:

- --db
- --limit optional default 10
- --include-inactive optional default false

Output:

- concise terminal summary
- top property briefs
- next actions
- no mutations

### export-portfolio-review-pack

Options:

- --db
- --output-dir
- --format md/csv/both optional default both
- --include-inactive optional default false

Output:

- report path(s)
- property count
- priority count
- next action count

## 7. Dashboard integration

Add **Portfolio Review Pack** section or subsection.

Show:

- portfolio summary metrics
- top review priorities
- property brief table
- lifecycle/cross-site/DOM highlights
- latest exported review pack path

Dashboard remains read-only.

## 8. Scheduled local report script

Add:

```text
scripts/run_portfolio_review_pack_report.bat
```

Behavior:

- activate local venv if present
- run export-portfolio-review-pack --format both
- write logs to logs/scheduled/
- no live retrieval
- no --force-live
- no mutation/import commands

Update docs/WINDOWS_TASK_SCHEDULER.md and automation script list if relevant.

Tests must verify scheduled script does not contain live retrieval commands, import/mutation commands, or `--force-live`.

## 9. Tests

Add or update tests for:

- build pack with empty database
- build pack with watched properties
- build property brief with quiet/vibrancy values
- quiet gatekeeper failure remains visible
- build property brief with Effective DOM v2 fields
- build property brief with Churn Index fields
- build property brief with gas/garage evidence
- build property brief with cross-site analytics fields
- build property brief with alert burden/lifecycle health fields
- review priority ranking
- next action generation
- Markdown export
- CSV export
- CLI portfolio-review-pack
- CLI export-portfolio-review-pack
- dashboard portfolio review data loads
- scheduled script safety
- no candidate/watchlist/alert mutation
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-39 tests still pass

## 10. Documentation

Update README.md and docs/RUNBOOK.md with a "Portfolio Review Pack" section.

Update docs/WINDOWS_TASK_SCHEDULER.md with the new scheduled review pack script.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with a short section on using the review pack for offline property review.

Create:

```text
docs/decisions/039-portfolio-review-pack.md
```

Explain:

- why review pack follows operations digest history
- why it is read-only
- why it consolidates property-level details without replacing detailed reports
- why scheduled script is local/report-only
- why candidate/watchlist/alert state is not automatically changed
- why Quiet Score gatekeeper is unchanged
- why walkability remains excluded

## Code standards

- Python 3.11+
- PEP8 compliant
- type hints required
- docstrings required for all functions
- remove unused imports
- no browser automation
- no Playwright/Selenium
- no bypassing CAPTCHAs, paywalls, login walls, anti-bot protections, or technical access controls
- no network calls in tests
- preserve source URLs and timestamps for auditability
- use neutral language
- do not make purchase recommendations
- do not add walkability parsing or fields

## Quality gates

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works for fresh database.
- Existing operations digest/history works.
- Portfolio review pack builds.
- Portfolio review pack exports Markdown/CSV.
- Dashboard portfolio review section loads.
- Scheduled portfolio review script is safe.
- No candidate/watchlist/alert status mutations occur.
- No Redfin source-of-truth fields are overwritten.
- Quiet gatekeeper remains unchanged.
- No real network calls are performed in tests.
- No scheduled task invokes live retrieval or mutation commands.
- Changes committed and pushed to origin/main.

## Completion report required

When finished, provide:

1. Summary of what you implemented.
2. Files created or modified.
3. Exact commands run.
4. Final test results with full pytest summary showing 100% pass.
5. Any dependency changes.
6. Any assumptions made.
7. Any blockers or risks remaining.
8. Example portfolio-review-pack output.
9. Example portfolio review pack report paths and row/property counts.
10. Example top review priority.
11. Example property brief.
12. Dashboard Portfolio Review Pack section added.
13. Scheduled script added.
14. Confirmation that review pack is read-only and does not mutate candidate/watchlist/alert state.
15. Confirmation that review pack does not overwrite Redfin source-of-truth fields.
16. Confirmation that Quiet Score gatekeeper remains unchanged.
17. Confirmation that walkability fields were not added.
18. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
19. Confirmation that tests perform no real network calls.
20. Recommended next implementation step.
21. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 40 complete until all tests pass.
