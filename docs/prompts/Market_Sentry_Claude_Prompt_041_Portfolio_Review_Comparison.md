# Claude Code Prompt 041 - Portfolio Review Pack Historical Comparison Reports

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: c4d20d1 (Milestone 40 complete)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/WINDOWS_TASK_SCHEDULER.md.
5. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
6. Read docs/ALERT_EXPIRATION_PROFILES.md.
7. Review the current codebase through commit c4d20d1.
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

Milestone 41 should add Portfolio Review Pack Historical Comparison Reports.

This milestone must not add live retrieval, broaden scraping, change the Quiet Score gatekeeper, or automatically apply candidate/watchlist/alert actions.

The goal is to compare review packs over time:

- compare current pack to previous pack
- show property priority changes
- show newly added/removed/inactive properties
- show changes in Quiet/Vibrancy availability
- show Effective DOM v2 and Churn Index movement
- show cross-site confidence/discrepancy movement
- show alert burden and lifecycle health movement
- show changes in recommended local review actions
- export comparison report for offline review

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
11. Portfolio comparison is offline/local reporting only and must not mutate candidate/watchlist/alert state.

## Implement

### 1. Portfolio comparison module

Create:

```text
src/marketsentry/portfolio_review_comparison.py
```

Required models:

- PortfolioReviewPackSnapshot
- PortfolioReviewPropertyChange
- PortfolioReviewComparisonSummary
- PortfolioReviewComparisonReportRow
- PortfolioReviewComparisonRunResult

Required functions:

- load_portfolio_review_pack_csv(...)
- compare_portfolio_review_packs(...)
- compare_current_to_previous_portfolio_pack(...)
- find_latest_portfolio_review_pack(...)
- find_previous_portfolio_review_pack(...)
- summarize_portfolio_review_changes(...)
- export_portfolio_review_comparison(...)

## 2. Comparison inputs

The primary comparison source should be CSV exports from Milestone 40:

```text
data/exports/portfolio_review_pack_*.csv
```

Behavior:

- Find latest and previous CSV automatically.
- Allow explicit current/previous file paths.
- Handle missing previous report gracefully.
- Handle schema drift or missing columns gracefully.
- Do not require database writes.
- Optional: build current pack in memory if no current CSV exists, but do not mutate DB.

## 3. Change detection

Detect per-property changes:

- property added
- property removed from pack
- active/inactive status changed
- priority label changed
- priority score changed
- quiet gatekeeper result changed
- quiet score changed materially
- vibrancy score changed materially
- effective_dom_v2 changed materially
- recent_churn_index changed materially
- cross_site_confidence changed materially
- discrepancy severity changed
- open alert count changed
- high/critical alert count changed
- lifecycle health label changed
- lifecycle health score changed materially
- recommended local review action changed

Suggested material thresholds:

- score deltas >= 5 points
- DOM delta >= 14 days
- Churn Index delta >= 1.0
- cross-site confidence delta >= 10 points
- alert count delta >= 1

Use neutral wording.

## 4. Summary metrics

Compute:

- total properties current
- total properties previous
- added properties
- removed properties
- priority_up_count
- priority_down_count
- lifecycle_health_improved_count
- lifecycle_health_degraded_count
- alert_burden_increased_count
- alert_burden_decreased_count
- effective_dom_increased_count
- effective_dom_decreased_count
- churn_increased_count
- churn_decreased_count
- cross_site_confidence_improved_count
- cross_site_confidence_degraded_count
- no_change_count

Trend labels:

- improved
- degraded
- changed
- unchanged
- new
- removed

Do not imply purchase recommendations.

## 5. Report export

Export CSV and Markdown:

```text
data/exports/portfolio_review_comparison_YYYYMMDD_HHMMSS.csv
data/exports/portfolio_review_comparison_YYYYMMDD_HHMMSS.md
```

Required CSV columns:

- property_id
- candidate_id
- address
- city
- zip
- change_type
- trend_label
- previous_priority_label
- current_priority_label
- priority_score_delta
- previous_lifecycle_health_label
- current_lifecycle_health_label
- lifecycle_health_score_delta
- previous_open_alert_count
- current_open_alert_count
- open_alert_delta
- previous_effective_dom_v2
- current_effective_dom_v2
- effective_dom_v2_delta
- previous_recent_churn_index
- current_recent_churn_index
- churn_index_delta
- previous_cross_site_confidence
- current_cross_site_confidence
- cross_site_confidence_delta
- change_summary
- recommended_review_action

Markdown structure:

- title and timestamp
- source files compared
- summary metrics
- added/removed properties
- priority changes
- lifecycle health changes
- alert burden changes
- Effective DOM/Churn highlights
- local review actions
- note: local analytical review aid only

## 6. CLI commands

Add:

```text
marketsentry compare-portfolio-review-packs
marketsentry export-portfolio-review-comparison
```

### compare-portfolio-review-packs

Options:

- --current optional path
- --previous optional path
- --exports-dir optional
- --limit optional default 10

Output:

- current/previous files
- summary metrics
- top changes
- no mutations

### export-portfolio-review-comparison

Options:

- --current optional path
- --previous optional path
- --exports-dir optional
- --output-dir optional
- --format csv/md/both optional default both

Output:

- report path(s)
- row count
- summary metrics

## 7. Dashboard integration

Add **Portfolio Review Comparison** subsection.

Show:

- latest comparison report link
- current/previous pack files
- summary metrics
- property changes table
- priority/lifecycle/alert change highlights

Dashboard remains read-only.

## 8. Scheduled script update

Update existing:

```text
scripts/run_portfolio_review_pack_report.bat
```

So it may run:

- export-portfolio-review-pack --format both
- export-portfolio-review-comparison --format both

Script must still:

- not run live retrieval
- not use --force-live
- not run mutation/import commands
- write logs to logs/scheduled/

Tests must verify scheduled script does not contain live retrieval or mutation commands.

## 9. Tests

Add or update tests for:

- load portfolio review pack CSV
- find latest pack
- find previous pack
- handle missing previous pack
- compare added property
- compare removed property
- compare unchanged property
- detect priority label change
- detect priority score change
- detect lifecycle health label change
- detect alert count change
- detect Effective DOM v2 material change
- detect Churn Index material change
- detect cross-site confidence material change
- summary metrics
- CSV export
- Markdown export
- CLI compare-portfolio-review-packs
- CLI export-portfolio-review-comparison
- dashboard comparison data loads
- scheduled script safety
- no candidate/watchlist/alert mutation
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-40 tests still pass

## 10. Documentation

Update README.md and docs/RUNBOOK.md with a "Portfolio Review Comparison" section.

Update docs/WINDOWS_TASK_SCHEDULER.md with updated portfolio review pack scheduled script behavior.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with a short section on comparing review packs over time.

Create:

```text
docs/decisions/040-portfolio-review-comparison.md
```

Explain:

- why comparison follows print-ready review packs
- why comparisons use exported CSVs as the stable interface
- why it is read-only
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
- preserve source file paths and timestamps for auditability
- use neutral language
- do not make purchase recommendations
- do not add walkability parsing or fields

## Quality gates

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- Existing portfolio review pack export works.
- Portfolio comparison works.
- Portfolio comparison exports Markdown/CSV.
- Dashboard portfolio comparison section loads.
- Scheduled portfolio review script remains safe.
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
8. Example compare-portfolio-review-packs output.
9. Example comparison report paths and row counts.
10. Example added/removed property change.
11. Example priority/lifecycle health change.
12. Dashboard Portfolio Review Comparison section added.
13. Scheduled script update added.
14. Confirmation that comparison is read-only and does not mutate candidate/watchlist/alert state.
15. Confirmation that comparison does not overwrite Redfin source-of-truth fields.
16. Confirmation that Quiet Score gatekeeper remains unchanged.
17. Confirmation that walkability fields were not added.
18. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
19. Confirmation that tests perform no real network calls.
20. Recommended next implementation step.
21. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 41 complete until all tests pass.
