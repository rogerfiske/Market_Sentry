# Claude Code Prompt 012 - Local Review Dashboard and Report Viewer

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository:

https://github.com/rogerfiske/Market_Sentry

Local project folder:

C:\Users\Minis\CascadeProjects\Market_Sentry

Current accepted milestones:

- Milestone 1 scaffold complete at commit c8599761be1aeda80b075cf668c61970e587ebe7
- Milestone 2 candidate review queue and watchlist promotion complete at commit 5da7747a44069696189d1abb8057ee23f17d8754
- Milestone 3 Redfin discovery adapter foundation complete at commit 5da7747a44069696189d1abb8057ee23f17d8754
- Milestone 4 Redfin detail parser and candidate enrichment complete at commit dafb63d
- Milestone 5 Effective DOM engine and candidate scoring report complete at commit 52ea72d
- Milestone 6 cross-site enrichment foundation stabilized and accepted at commit 01b6887
- Milestone 7 watchlist monitoring snapshots and change detection complete at commit 23ac2b5
- Milestone 8 county recorder and assessor verification foundation complete at commit 89ce91a
- Milestone 9 Effective DOM v2 county-verified reset integration complete at commit 0e83285
- Milestone 10 Effective DOM v2 operational integration complete at commit 44b655d
- Milestone 11 end-to-end operating workflow and runbook complete at commit 6cf5627
- Prompt 011A export path stabilization complete at commit 4475634

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Review the current codebase through commit 4475634.
5. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
6. Keep PRD.md and Architecture.md in the project root.
7. Use src/marketsentry/ as the Python package path.
8. Do not move PRD.md or Architecture.md into docs/.
9. Do not implement live scraping, browser automation, Playwright, Selenium, or active network retrieval in this milestone.
10. Do not implement live County Recorder/Assessor access in this milestone.
11. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 12 should add a local dashboard/report viewer that makes Market_Sentry easier to use day to day.

Do not add live data retrieval.

The dashboard must read only local data:

- SQLite database
- generated CSV reports
- local workflow summaries
- local report_manifest.csv

The dashboard is a local review interface and report viewer. It is not a purchase recommendation tool.

Preferred implementation:

Use Streamlit for the local dashboard if feasible with the current dependency strategy.

If adding Streamlit as a dependency, update requirements.txt, README.md, and tests accordingly.

If Streamlit is not practical, implement a static local HTML report viewer instead and explain why.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It starts with Redfin candidate discovery, stages homes for human review, and then monitors user-selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, cross-site validation, county sale/ownership-transfer verification, and a separate recent Churn Index.

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

Your task for Prompt 012:

Implement Local Review Dashboard and Report Viewer v1.

No live network calls.

## 1. Dashboard scope

The dashboard should provide a local browser interface for reviewing:

- candidate review queue
- watched properties
- latest candidate analysis report
- latest watchlist monitoring report
- Effective DOM v1/v2 comparison
- Churn Index
- Quiet/Vibrancy gatekeeper status
- cross-site discrepancy flags
- county verification status
- report manifest
- workflow summaries

## 2. Dashboard implementation

Create a dashboard module, for example:

```text
src/marketsentry/dashboard.py
```

If using Streamlit, also create:

```text
src/marketsentry/dashboard_app.py
```

or an equivalent launchable module.

Required helper functions:

- load_dashboard_data(db_path: Path | str | None = None) -> DashboardData
- get_dashboard_summary(db_path: Path | str | None = None) -> DashboardSummary
- load_latest_report_manifest(exports_dir: Path | str | None = None) -> list[ReportManifestRow]
- find_latest_report(report_type: str, exports_dir: Path | str | None = None) -> Path | None
- load_report_csv(report_path: Path) -> pandas.DataFrame
- build_candidate_table(...)
- build_watchlist_table(...)
- build_monitoring_table(...)
- build_county_verification_table(...)
- build_effective_dom_v2_table(...)

Add typed models where useful:

- DashboardSummary
- DashboardData
- DashboardTableSpec
- ReportManifestRow

## 3. Dashboard pages or sections

Implement these dashboard sections:

### Overview

Show summary counts:

- candidates in review queue
- watched properties
- active watched properties
- latest snapshots
- cross-site observations
- county records
- reports in manifest
- high-priority watchlist count
- Quiet gatekeeper failures
- strong review candidates
- properties with county reset applied
- properties with high Churn Index

### Candidate Review

Show candidate table with:

- candidate_id
- review_recommendation
- overall_review_score
- address
- city
- zip
- price
- quiet_score
- vibrancy_score
- quiet_gatekeeper_result
- garage_spaces
- gas_service
- displayed_dom
- effective_dom_v1
- effective_dom_v2
- effective_dom_delta_v2
- recent_churn_index
- county_reset_applied
- user_decision
- redfin_url

Filters:

- review_recommendation
- quiet_gatekeeper_result
- user_decision
- gas_service
- minimum Quiet Score
- maximum Vibrancy Score
- minimum Churn Index

### Watchlist

Show watched properties with:

- property_id
- watch_priority
- active_watch_status
- address
- city
- zip
- current_price
- quiet_score
- vibrancy_score
- gas_service
- garage_spaces
- effective_dom_v1
- effective_dom_v2
- recent_churn_index
- county_reset_applied
- last_checked_date
- user_notes
- redfin_url

Filters:

- watch_priority
- active_watch_status
- quiet score threshold
- high churn threshold
- county reset applied

### Monitoring

Show latest monitoring report if available.

Columns:

- property_id
- address
- current_price
- previous_price
- price_change
- listing_status
- previous_listing_status
- effective_dom_v2
- previous_effective_dom_v2
- effective_dom_v2_change
- recent_churn_index
- recent_churn_index_change
- change_summary
- warning_flags
- positive_flags

### Effective DOM v2

Show latest Effective DOM v2 report if available.

Highlight:

- effective_dom_v1 vs effective_dom_v2
- county_reset_applied
- county_reset_date
- Churn Index preserved
- pre-reset vs post-reset exposure

### County Verification

Show latest county verification report if available.

Highlight:

- county_transfer_found
- county_reset_supported
- county_transfer_date
- county_transfer_record_type
- recent_churn_index
- churn_preserved_after_transfer
- non-transfer document notes if available

### Cross-Site Review

Show latest cross-site report if available.

Highlight:

- price_discrepancy_flag
- status_discrepancy_flag
- dom_discrepancy_flag
- cross_site_confidence_score
- which sources were seen

### Reports

Show report_manifest.csv with clickable/local file paths where practical.

Columns:

- created_at
- workflow_name
- report_type
- file_path
- row_count
- notes

### Workflow Summaries

Show list of workflow summary markdown files and preview selected summary text.

## 4. CLI commands

Add CLI commands:

```text
marketsentry launch-dashboard
marketsentry dashboard-summary
```

### launch-dashboard

If using Streamlit:

- Runs Streamlit app locally.
- Accepts:
  - --db
  - --exports-dir
  - --port
- Prints exact launch command or starts the app.

If direct Streamlit launch from Typer is difficult, provide a clear command such as:

```text
streamlit run src/marketsentry/dashboard_app.py
```

and make `marketsentry launch-dashboard` print/run that command safely.

### dashboard-summary

Prints an ASCII-safe summary of current dashboard counts without launching browser UI.

## 5. Streamlit requirements if used

If using Streamlit:

- Add streamlit to requirements.txt.
- Keep app local.
- Do not make network calls.
- Do not require any Streamlit Cloud features.
- Do not require secrets or external APIs.
- Use pandas DataFrames for tables.
- Include filters in sidebar where practical.
- Keep UI simple and stable.

Suggested local command:

```text
streamlit run src/marketsentry/dashboard_app.py
```

## 6. Static HTML fallback

If Streamlit is not used, implement:

```text
marketsentry export-dashboard-html
```

and create:

```text
data/exports/dashboard_YYYYMMDD_HHMMSS.html
```

Static HTML should include the same sections at a basic level.

Only choose this route if Streamlit is not practical.

## 7. Tests

Add or update tests for:

- dashboard summary counts
- latest report discovery
- report manifest loading
- CSV report loading
- candidate table preparation
- watchlist table preparation
- monitoring table preparation
- Effective DOM v2 table preparation
- county verification table preparation
- cross-site table preparation
- dashboard-summary CLI command
- no live network calls
- existing MVP 1-11 tests still pass

If Streamlit app itself is difficult to test directly, test its data-loading and table-preparation functions, not the browser runtime.

All tests must pass.

## 8. Documentation

Update README.md with:

- Milestone 12 status.
- How to install/run dashboard.
- How to run `marketsentry dashboard-summary`.
- How to launch dashboard locally.
- What dashboard sections mean.
- Clear statement that the dashboard reads local files/database only.
- Clear statement that the dashboard does not scrape, fetch, or make purchase recommendations.

Update docs/RUNBOOK.md with a dashboard usage section.

Add design decision note:

```text
docs/decisions/011-local-dashboard-report-viewer.md
```

Explain:

- Why dashboard is added before live retrieval.
- Why dashboard reads only local SQLite/CSV/manifest data.
- Why Streamlit or static HTML was chosen.
- Why this is a review tool, not a recommendation engine.

## 9. Code standards

- Python 3.11+
- PEP8 compliant.
- Type hints required.
- Docstrings required for all functions.
- Remove unused imports.
- Keep modules small and readable.
- No live scraping.
- No network calls.
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
- Existing Redfin workflows still work.
- Existing Effective DOM v1/v2 workflows still work.
- Existing cross-site workflows still work.
- Existing county workflows still work.
- Existing watchlist monitoring workflows still work.
- Existing end-to-end workflows still work.
- Dashboard summary works.
- Dashboard data loading works.
- Dashboard/report viewer can be launched or exported locally.
- No live scraping or network calls implemented.
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
8. Whether Streamlit or static HTML was used and why.
9. How to launch the dashboard locally.
10. Example dashboard-summary output.
11. Dashboard sections implemented.
12. Tests added for dashboard data loading/report loading.
13. Confirmation that the dashboard reads local SQLite/CSV/manifest data only.
14. Confirmation that no live network calls, scraping, Playwright, Selenium, or browser automation were added.
15. Recommended next implementation step.
16. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 12 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
