# Claude Code Prompt 027 - Cross-Site Alert Aggregation and Historical Pattern Analysis

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
- Milestone 16 Redfin Live HTTP Retrieval Phase 1 complete at commit d8ed591
- Milestone 17 Redfin retrieved fixture processing pipeline complete at commit e41e5e4
- Milestone 18 Redfin pending capture batch retrieval orchestrator complete at commit 2d420d7
- Milestone 19 Redfin batch retrieval approval workflow complete at commit 66628f6
- Milestone 20 retrieval operations dashboard integration complete at commit 9df9300
- Milestone 21 retrieval operations aging, alerts, and health checks complete at commit c92f687
- Milestone 22 cross-site adapter parity and manual fixture workflow complete at commit 1e3235c
- Milestone 23 cross-site parser quality and fixture corpus expansion complete at commit 3b1470a
- Milestone 24 confidence-weighted cross-site comparison analytics complete at commit 788ac84
- Milestone 25 cross-site analytics trend snapshots complete at commit 3322f92
- Milestone 26 cross-site trend alerts and watchlist monitoring integration complete at commit 67d2265

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
5. Review the current codebase through commit 67d2265.
6. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
7. Keep PRD.md and Architecture.md in the project root.
8. Use src/marketsentry/ as the Python package path.
9. Do not move PRD.md or Architecture.md into docs/.
10. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
11. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
12. Do not implement new Redfin live retrieval behavior in this milestone.
13. Do not run any live network calls in tests.
14. Do not make scheduled tasks run live retrieval by default.
15. Do not add walkability parsing or walkability fields.
16. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 27 should aggregate and summarize cross-site trend alert history so the user can see property-level alert burden and repeated discrepancy patterns over time.

This milestone should NOT add live retrieval.

This milestone should NOT broaden scraping.

This milestone should NOT change the Quiet Score gatekeeper.

The goal is to turn individual alert rows from Milestone 26 into higher-level local review insights:

- repeated alert patterns by property
- alert frequency by type
- alert burden by property
- unresolved high-severity alert counts
- oldest open alert age
- recurring confidence drops
- recurring status/price/DOM agreement problems
- improving alert patterns after resolution
- alert history report for watchlist review

These are neutral analytical review signals only. Do not infer seller intent. Do not make purchase recommendations.

Cross-site data remains validation/check data. It must not overwrite Redfin source-of-truth fields.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It uses a human-in-the-loop, fixture-first workflow to observe candidate and watched properties using Effective DOM v1/v2, Churn Index, Quiet/Vibrancy gatekeeper logic, gas evidence, garage spaces, cross-site validation, county verification, local reports, dashboard views, and compliance-aware retrieval operations.

Critical domain rules:

1. Effective DOM v1 is listing-history-derived exposure without county reset integration.
2. Effective DOM v2 applies county-confirmed ownership transfer as a reset boundary when appropriate.
3. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
4. Churn Index remains reportable even when Effective DOM is reset.
5. Quiet Score is the gatekeeper.
6. Target is very high Quiet and very low Vibrancy.
7. Any mention of gas means the property has natural gas supply/service.
8. Walkability-type information is excluded from the initial scope.
9. Use neutral language. Do not infer seller intent.
10. Reports are analytical aids, not purchase recommendations.
11. Cross-site data should validate and compare; it should not overwrite Redfin source-of-truth fields.

Your task for Prompt 027:

Implement Cross-Site Alert Aggregation and Historical Pattern Analysis v1.

## 1. Aggregation module

Create a module, for example:

```text
src/marketsentry/cross_site_alert_analytics.py
```

Required models:

- CrossSiteAlertBurdenMetrics
- CrossSiteAlertPattern
- CrossSiteAlertHistorySummary
- CrossSiteAlertAggregationResult
- CrossSiteAlertAnalyticsReportRow

Required functions:

- calculate_alert_burden_for_property(...)
- identify_repeated_alert_patterns(...)
- summarize_alert_history_for_property(...)
- summarize_alert_history_for_all_properties(...)
- calculate_alert_age_days(...)
- classify_alert_burden_level(...)
- export_cross_site_alert_analytics_report(...)

## 2. Property-level alert burden

Calculate property-level burden metrics:

- total_alert_count
- open_alert_count
- high_or_critical_open_alert_count
- acknowledged_alert_count
- resolved_alert_count
- oldest_open_alert_age_days
- latest_alert_at
- repeated_alert_type_count
- most_common_alert_type
- most_common_severity
- alert_burden_score
- alert_burden_label

Suggested burden labels:

- none
- low
- moderate
- high
- elevated_review

Suggested heuristic:

- no open alerts = none
- 1-2 low/warning open alerts = low
- 3+ open alerts or any high open alert = moderate
- 2+ high open alerts or any critical open alert = high
- repeated high/critical pattern over time = elevated_review

Use neutral language.

## 3. Pattern identification

Identify repeated patterns:

- repeated_confidence_drop
- repeated_status_discrepancy
- repeated_price_agreement_degraded
- repeated_dom_agreement_degraded
- repeated_stale_sources
- repeated_low_confidence_sources
- recurring_high_severity_alerts
- improving_source_quality_pattern

A pattern should require at least two matching events unless explicitly configured otherwise.

Patterns should include:

- pattern_type
- count
- first_seen
- latest_seen
- severity_summary
- status_summary
- message
- recommended_review_action

Do not infer seller intent.

## 4. Alert analytics report

Add report export:

```text
data/exports/cross_site_alert_analytics_YYYYMMDD_HHMMSS.csv
```

Required columns:

- property_id
- candidate_id
- address
- city
- zip
- total_alert_count
- open_alert_count
- high_or_critical_open_alert_count
- oldest_open_alert_age_days
- latest_alert_at
- most_common_alert_type
- most_common_severity
- repeated_patterns
- alert_burden_score
- alert_burden_label
- recommended_review_action
- unresolved_alert_types
- resolved_alert_count
- acknowledged_alert_count

Add CLI command:

```text
marketsentry export-cross-site-alert-analytics-report
```

Options:

- --db
- --output-dir
- --include-resolved optional default true

## 5. CLI summary command

Add CLI command:

```text
marketsentry cross-site-alert-analytics-summary
```

Output:

- total properties with alerts
- properties with open alerts
- properties with high/critical alerts
- properties with repeated patterns
- top alert types
- top properties by alert burden
- oldest open alert
- recommended next actions

ASCII-safe.

## 6. Dashboard integration

Add Cross-Site Alert Analytics subsection to dashboard.

Show:

- top properties by alert burden
- open high/critical alert counts
- repeated patterns table
- alert burden label
- recommended review actions
- resolved vs open counts

Keep dashboard read-only.

## 7. Watchlist monitoring/report integration

Where practical, add report-only alert aggregation fields to watchlist monitoring export:

- cross_site_alert_burden_label
- cross_site_alert_burden_score
- cross_site_repeated_patterns
- cross_site_oldest_open_alert_age_days

Do not change watchlist state automatically.

Do not change active_watch_status automatically.

Do not let alert burden override Quiet Score gatekeeper.

## 8. Tests

Add or update tests for:

- alert burden calculation with no alerts
- alert burden calculation with low open alerts
- alert burden calculation with high/critical alerts
- oldest open alert age calculation
- most common alert type/severity
- repeated confidence drop pattern
- repeated status discrepancy pattern
- repeated price agreement degraded pattern
- repeated DOM agreement degraded pattern
- improving source quality pattern
- property-level history summary
- all-property aggregation summary
- alert analytics report export
- cross-site-alert-analytics-summary CLI
- export-cross-site-alert-analytics-report CLI
- dashboard alert analytics table loads
- watchlist monitoring report includes alert aggregation fields if implemented
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-26 tests still pass

All tests must pass.

## 9. Documentation

Update README.md and docs/RUNBOOK.md with a "Cross-Site Alert Analytics" section.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with:

- alert burden meaning
- repeated pattern meaning
- alert analytics report
- how to use alert analytics during watchlist review
- reminder that analytics are review aids, not recommendations

Create design decision note:

```text
docs/decisions/026-cross-site-alert-aggregation-patterns.md
```

Explain:

- why aggregation follows individual alerts
- why alert burden is neutral
- why repeated patterns require multiple events
- why watchlist state is not automatically changed
- why Quiet Score gatekeeper is unchanged
- why walkability remains excluded

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
- Preserve source URLs and timestamps for auditability.
- Avoid inaccurate Claude co-authorship metadata.
- Use neutral language.
- Do not make purchase recommendations.
- Do not add walkability parsing or walkability fields.

Quality gates:

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works for fresh database.
- Existing candidate review workflow still works.
- Existing cross-site trend alerts work.
- Cross-site alert analytics work.
- Alert analytics report exports.
- Dashboard alert analytics fields load.
- Watchlist report integration works if implemented.
- No Redfin source-of-truth fields are overwritten.
- Quiet gatekeeper remains unchanged.
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
8. Example cross-site-alert-analytics-summary output.
9. Example alert analytics report path and row count.
10. Example alert burden output.
11. Example repeated pattern output.
12. Dashboard/watchlist report updates added.
13. Confirmation that alert analytics do not overwrite Redfin source-of-truth fields.
14. Confirmation that Quiet Score gatekeeper remains unchanged.
15. Confirmation that walkability fields were not added.
16. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
17. Confirmation that tests perform no real network calls.
18. Recommended next implementation step.
19. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 27 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
