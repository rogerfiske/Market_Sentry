# Claude Code Prompt 026 - Cross-Site Trend Alerts and Watchlist Monitoring Integration

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
5. Review the current codebase through commit 3322f92.
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

Milestone 26 should turn Milestone 25 trend snapshots into practical local operator alerts and watchlist monitoring signals.

This milestone should NOT add live retrieval.

This milestone should NOT broaden scraping.

This milestone should NOT change the Quiet Score gatekeeper.

The goal is to surface cross-site trend changes that need human review:

- confidence dropped materially
- discrepancy severity increased
- manual review priority increased
- status agreement degraded
- DOM agreement degraded
- price agreement degraded
- stale source count increased
- low-confidence source count increased
- cross-site signals improved and may reduce urgency

Cross-site trend alerts are analytical review signals only. They are not purchase recommendations and must not infer seller intent.

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

Your task for Prompt 026:

Implement Cross-Site Trend Alerts and Watchlist Monitoring Integration v1.

## 1. Trend alert model and storage

Add local alert storage for cross-site trend signals.

Suggested table:

```text
cross_site_trend_alerts
```

Suggested columns:

- alert_id
- property_id
- candidate_id
- snapshot_id
- previous_snapshot_id
- created_at
- alert_type
- severity
- alert_status
- trend_direction
- current_value
- previous_value
- delta_value
- message
- recommended_action
- source_context
- notes

Suggested `alert_status` values:

- open
- acknowledged
- resolved
- archived

Suggested `alert_type` values:

- confidence_drop
- confidence_improvement
- severity_increase
- severity_decrease
- manual_review_priority_increase
- manual_review_priority_decrease
- price_agreement_degraded
- status_agreement_degraded
- dom_agreement_degraded
- stale_sources_increased
- low_confidence_sources_increased
- source_quality_improved

Migrations must be non-destructive and idempotent.

## 2. Trend alert module

Create a module, for example:

```text
src/marketsentry/cross_site_trend_alerts.py
```

Required models:

- CrossSiteTrendAlert
- CrossSiteTrendAlertRule
- CrossSiteTrendAlertRunResult
- CrossSiteTrendAlertReportRow

Required functions:

- generate_cross_site_trend_alerts(...)
- generate_alerts_for_property(...)
- classify_trend_alert_severity(...)
- deduplicate_open_alerts(...)
- acknowledge_cross_site_trend_alert(...)
- resolve_cross_site_trend_alert(...)
- export_cross_site_trend_alerts_report(...)

Required behavior:

- Read latest and previous trend snapshots.
- Generate alerts when material trend rules are triggered.
- Do not create duplicate open alerts for the same property + alert_type + snapshot_id.
- Preserve alert history.
- Allow acknowledging/resolving alerts via CLI.
- Use neutral wording.
- Do not infer seller intent.
- Do not overwrite Redfin facts.
- Do not change Quiet Score gatekeeper.

## 3. Alert severity rules

Suggested severity levels:

- info
- warning
- high
- critical

Initial rules:

- confidence drop >= 0.10: warning
- confidence drop >= 0.25: high
- confidence improvement >= 0.10: info
- discrepancy severity increases by one level: warning
- discrepancy severity increases to high: high
- discrepancy severity increases to critical: critical
- manual review priority increases to high: high
- status agreement drops >= 0.25: high
- price agreement drops >= 0.25: warning/high depending on severity label
- DOM agreement drops >= 0.25: warning
- stale source count increases: warning
- low-confidence source count increases: warning

Rules should be centralized and easy to adjust later.

## 4. CLI commands

Add CLI commands:

```text
marketsentry generate-cross-site-trend-alerts
marketsentry list-cross-site-trend-alerts
marketsentry acknowledge-cross-site-trend-alert
marketsentry resolve-cross-site-trend-alert
marketsentry export-cross-site-trend-alerts-report
```

### generate-cross-site-trend-alerts

Options:

- --db
- --output-dir optional

Output:

- properties scanned
- alerts generated
- duplicates skipped
- warnings/errors

### list-cross-site-trend-alerts

Options:

- --db
- --status
- --severity
- --property-id

Output open alerts by default.

### acknowledge-cross-site-trend-alert

Options:

- --alert-id
- --notes optional
- --db

### resolve-cross-site-trend-alert

Options:

- --alert-id
- --notes optional
- --db

### export-cross-site-trend-alerts-report

Options:

- --db
- --output-dir
- --status optional

Output:

```text
data/exports/cross_site_trend_alerts_YYYYMMDD_HHMMSS.csv
```

## 5. Watchlist monitoring integration

Update watchlist monitoring report or dashboard outputs to include alert summary fields.

Suggested report-only fields:

- open_cross_site_alert_count
- highest_cross_site_alert_severity
- latest_cross_site_alert_type
- latest_cross_site_alert_message
- cross_site_alert_recommended_action

Do not change core watchlist state automatically.

Do not change active_watch_status automatically.

Do not let cross-site alerts override Quiet Score gatekeeper.

## 6. Dashboard integration

Add Cross-Site Trend Alerts subsection/table to dashboard.

Show:

- open alert count
- severity counts
- latest alert date
- alert table
- recommended actions
- property/address context where available
- status filters

If changing alert status from dashboard is too much scope, keep dashboard read-only.

## 7. Tests

Add or update tests for:

- schema migration creates cross_site_trend_alerts
- migration is idempotent
- confidence drop warning alert
- confidence drop high alert
- confidence improvement info alert
- severity increase alert
- manual review priority increase alert
- status agreement degraded alert
- price agreement degraded alert
- DOM agreement degraded alert
- stale source count increased alert
- low-confidence source count increased alert
- duplicate open alert prevention
- acknowledge alert
- resolve alert
- list alerts filtering
- export alert report
- watchlist monitoring alert summary fields
- dashboard alert table loads
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-25 tests still pass

All tests must pass.

## 8. Documentation

Update README.md and docs/RUNBOOK.md with a "Cross-Site Trend Alerts" section.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with:

- what trend alerts mean
- how to generate alerts
- how to list/acknowledge/resolve alerts
- alert severity definitions
- reminder that alerts are review aids, not recommendations

Create design decision note:

```text
docs/decisions/025-cross-site-trend-alerts-watchlist-monitoring.md
```

Explain:

- why alerts are added after trend snapshots
- why alerts are neutral review signals
- why alert history is preserved
- why watchlist state is not automatically changed
- why Quiet Score gatekeeper is unchanged
- why walkability remains excluded

## 9. Code standards

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
- Existing Redfin workflows still work.
- Existing cross-site analytics report exports.
- Existing cross-site analytics trend snapshots work.
- Cross-site trend alerts work.
- Cross-site trend alert report exports.
- Dashboard alert fields load.
- Watchlist monitoring alert summary fields work if implemented.
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
8. Schema changes or migration details.
9. Example generate-cross-site-trend-alerts output.
10. Example list-cross-site-trend-alerts output.
11. Example alert report path and row count.
12. Example acknowledged/resolved alert behavior.
13. Dashboard/watchlist report updates added.
14. Confirmation that cross-site alerts do not overwrite Redfin source-of-truth fields.
15. Confirmation that Quiet Score gatekeeper remains unchanged.
16. Confirmation that walkability fields were not added.
17. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
18. Confirmation that tests perform no real network calls.
19. Recommended next implementation step.
20. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 26 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
