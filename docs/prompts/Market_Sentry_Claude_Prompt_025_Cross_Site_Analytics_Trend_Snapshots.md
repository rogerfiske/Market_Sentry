# Claude Code Prompt 025 - Cross-Site Analytics Trend Snapshots

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
5. Review the current codebase through commit 788ac84.
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

Milestone 25 should add trend snapshots for Milestone 24 cross-site analytics.

This milestone should NOT add live retrieval.

This milestone should NOT broaden scraping.

The goal is to track how cross-site analytics change over time for watched properties:

- overall cross-site confidence trend
- discrepancy severity trend
- source agreement trend
- stale/low-confidence source trend
- price/status/DOM agreement trend
- manual review priority trend

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

Your task for Prompt 025:

Implement Cross-Site Analytics Trend Snapshots v1.

## 1. Trend snapshot model and storage

Add local snapshot storage for cross-site analytics trends.

Suggested table:

```text
cross_site_analytics_snapshots
```

Suggested columns:

- snapshot_id
- property_id
- candidate_id
- captured_at
- overall_cross_site_confidence_score
- discrepancy_severity_score
- discrepancy_severity_label
- cross_site_manual_review_priority
- weighted_price_agreement_score
- weighted_status_agreement_score
- weighted_dom_agreement_score
- weighted_garage_agreement_score
- weighted_gas_agreement_score
- source_freshness_score
- source_completeness_score
- source_agreement_score
- contributing_sources
- low_confidence_sources
- stale_sources
- parse_warning_sources
- source_count
- high_confidence_source_count
- low_confidence_source_count
- stale_source_count
- price_discrepancy_flag
- status_discrepancy_flag
- dom_discrepancy_flag
- notes
- created_at

Migrations must be non-destructive and idempotent.

## 2. Trend snapshot module

Create a module, for example:

```text
src/marketsentry/cross_site_trends.py
```

Required models:

- CrossSiteAnalyticsSnapshot
- CrossSiteTrendChange
- CrossSiteTrendSummary
- CrossSiteTrendRunResult
- CrossSiteTrendReportRow

Required functions:

- create_cross_site_analytics_snapshots(...)
- get_latest_cross_site_analytics_snapshot(...)
- get_previous_cross_site_analytics_snapshot(...)
- calculate_cross_site_trend_change(...)
- summarize_cross_site_trends(...)
- export_cross_site_trend_report(...)

Required behavior:

- Compute current analytics using Milestone 24 logic.
- Persist one snapshot per active watched property when analytics exist.
- Avoid duplicate same-day/no-change snapshots by default.
- Create a new snapshot if material fields changed.
- Preserve historical snapshots.
- Do not overwrite cross_site_observations.
- Do not overwrite Redfin source-of-truth fields.
- Return counts:
  - properties scanned
  - analytics computed
  - snapshots created
  - snapshots skipped no change
  - trend changes detected
  - warnings/errors

Material changes may include:

- severity label changed
- manual review priority changed
- overall confidence changed by >= 0.10
- any agreement score changed by >= 0.10
- stale/low-confidence source count changed
- discrepancy flag changed

## 3. Trend report

Add report export:

```text
data/exports/cross_site_trends_YYYYMMDD_HHMMSS.csv
```

Required columns:

- property_id
- candidate_id
- address
- city
- zip
- current_overall_cross_site_confidence_score
- previous_overall_cross_site_confidence_score
- overall_cross_site_confidence_change
- current_discrepancy_severity_label
- previous_discrepancy_severity_label
- discrepancy_severity_changed
- current_manual_review_priority
- previous_manual_review_priority
- manual_review_priority_changed
- current_weighted_price_agreement_score
- previous_weighted_price_agreement_score
- price_agreement_change
- current_weighted_status_agreement_score
- previous_weighted_status_agreement_score
- status_agreement_change
- current_weighted_dom_agreement_score
- previous_weighted_dom_agreement_score
- dom_agreement_change
- current_low_confidence_sources
- previous_low_confidence_sources
- current_stale_sources
- previous_stale_sources
- trend_direction
- trend_summary
- recommended_next_action

Use neutral wording.

## 4. CLI commands

Add CLI commands:

```text
marketsentry snapshot-cross-site-analytics
marketsentry export-cross-site-trend-report
```

### snapshot-cross-site-analytics

Options:

- --db
- --force
- --output-dir optional

Output:

- properties scanned
- analytics computed
- snapshots created
- snapshots skipped
- changes detected
- warnings/errors

### export-cross-site-trend-report

Options:

- --db
- --output-dir

Output:

- output path
- row count

## 5. Dashboard integration

Update dashboard Cross-Site Review section to include a "Trends" subsection/table.

Show:

- confidence change
- severity change
- manual review priority change
- price/status/DOM agreement change
- low-confidence/stale source changes
- trend direction
- recommended next action

Optionally add a simple line chart if straightforward, but do not overcomplicate.

## 6. Watchlist monitoring integration

Where practical, include cross-site trend summary fields in watchlist monitoring reports or dashboard only.

Do not modify core watchlist monitoring logic in a risky way.

Suggested report-only fields:

- cross_site_confidence_change
- cross_site_severity_changed
- cross_site_manual_review_priority_changed

## 7. Tests

Add or update tests for:

- schema migration creates cross_site_analytics_snapshots
- migration is idempotent
- snapshot creation from analytics result
- no duplicate same-day/no-change snapshot
- force snapshot creates new snapshot
- severity change triggers snapshot
- confidence delta >= 0.10 triggers snapshot
- agreement score delta >= 0.10 triggers snapshot
- trend change calculation
- trend report export
- CLI snapshot-cross-site-analytics
- CLI export-cross-site-trend-report
- dashboard includes trend fields
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-24 tests still pass

All tests must pass.

## 8. Documentation

Update README.md and docs/RUNBOOK.md with a "Cross-Site Analytics Trends" section.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with:

- how to snapshot cross-site analytics
- how to export trend report
- how to interpret trend direction
- reminder that trend data is validation-only and not a purchase recommendation

Create design decision note:

```text
docs/decisions/024-cross-site-analytics-trend-snapshots.md
```

Explain:

- why trends are added after confidence-weighted analytics
- why snapshots are append-only
- why same-day/no-change snapshots are skipped by default
- why cross-site trends remain validation-only
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
- Existing cross-site dry-run/manual-fixture workflow still works.
- Existing cross-site parser quality tests still pass.
- Existing cross-site analytics report exports.
- Cross-site analytics trend snapshots work.
- Cross-site trend report exports.
- Dashboard trend fields load.
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
9. Example snapshot-cross-site-analytics output.
10. Example cross-site trend report path and row count.
11. Example trend output showing confidence improvement.
12. Example trend output showing severity increase.
13. Dashboard/report updates added.
14. Confirmation that cross-site trend data does not overwrite Redfin source-of-truth fields.
15. Confirmation that Quiet Score gatekeeper remains unchanged.
16. Confirmation that walkability fields were not added.
17. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
18. Confirmation that tests perform no real network calls.
19. Recommended next implementation step.
20. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 25 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
