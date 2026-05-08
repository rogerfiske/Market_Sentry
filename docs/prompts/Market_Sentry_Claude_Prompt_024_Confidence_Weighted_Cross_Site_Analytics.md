# Claude Code Prompt 024 - Confidence-Weighted Cross-Site Comparison Analytics

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
5. Review the current codebase through commit 3b1470a.
6. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
7. Keep PRD.md and Architecture.md in the project root.
8. Use src/marketsentry/ as the Python package path.
9. Do not move PRD.md or Architecture.md into docs/.
10. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
11. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
12. Do not run any live network calls in tests.
13. Do not make scheduled tasks run live retrieval by default.
14. Do not add walkability parsing or walkability fields.
15. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 24 should leverage Milestone 23 parser confidence fields to improve cross-site comparison analytics.

This milestone should NOT add live retrieval.

This milestone should NOT broaden scraping.

The goal is to make cross-site validation more analytically useful by weighting source observations according to parse confidence, data freshness, source agreement, and field completeness.

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

Your task for Prompt 024:

Implement Confidence-Weighted Cross-Site Comparison Analytics v1.

## 1. Analytics goals

Use cross-site observations from:

- Zillow
- Realtor.com
- Homes.com
- Compass

to produce improved cross-site validation metrics:

- confidence-weighted price agreement
- confidence-weighted status agreement
- confidence-weighted DOM agreement
- confidence-weighted garage agreement
- confidence-weighted gas-service agreement
- source freshness score
- source completeness score
- source agreement score
- overall cross-site confidence score
- discrepancy severity score
- manual review priority

Do not use cross-site data to overwrite Redfin facts.

## 2. New analytics module

Create a module, for example:

```text
src/marketsentry/cross_site_analytics.py
```

Required models:

- CrossSiteSourceWeight
- CrossSiteFieldAgreement
- CrossSiteConfidenceMetrics
- CrossSiteDiscrepancySeverity
- CrossSiteAnalyticsResult
- CrossSiteAnalyticsReportRow

Required functions:

- confidence_to_weight(parse_confidence: str | None) -> float
- freshness_to_weight(observed_at: datetime | None, analysis_date: datetime | None = None) -> float
- completeness_to_weight(observation: dict | Any) -> float
- calculate_source_weight(...)
- calculate_field_agreement(...)
- calculate_price_agreement(...)
- calculate_status_agreement(...)
- calculate_dom_agreement(...)
- calculate_garage_agreement(...)
- calculate_gas_agreement(...)
- calculate_cross_site_confidence_metrics(...)
- calculate_discrepancy_severity(...)
- analyze_cross_site_observations(...)
- analyze_property_cross_site_metrics(...)

Suggested initial weights:

- parse_confidence high = 1.0
- parse_confidence medium = 0.7
- parse_confidence low = 0.4
- parse_status failed = 0.0
- observation age 0-7 days = 1.0
- observation age 8-30 days = 0.8
- observation age 31-90 days = 0.5
- observation age >90 days = 0.2
- missing required fields reduce completeness

These are initial heuristics and should be easy to adjust later.

## 3. Discrepancy severity

Implement neutral discrepancy severity scoring.

Potential severity levels:

- none
- low
- medium
- high
- critical

Signals:

- price difference > $10k = at least low
- price difference > $25k = medium
- price difference > $50k = high
- status conflict active vs pending/sold/off_market = high
- DOM difference > 30 days = medium
- DOM difference > 90 days = high
- gas disagreement = low/medium
- garage disagreement = low/medium
- low parser confidence should reduce severity certainty, not exaggerate it

Use neutral wording:

- price_discrepancy
- status_discrepancy
- dom_discrepancy
- gas_disagreement
- garage_disagreement
- low_confidence_source
- needs_manual_review

Avoid seller-intent language.

## 4. Cross-site report integration

Update existing cross-site comparison/report generation to include:

- weighted_price_agreement_score
- weighted_status_agreement_score
- weighted_dom_agreement_score
- weighted_garage_agreement_score
- weighted_gas_agreement_score
- source_freshness_score
- source_completeness_score
- source_agreement_score
- overall_cross_site_confidence_score
- discrepancy_severity_score
- discrepancy_severity_label
- cross_site_manual_review_priority
- contributing_sources
- low_confidence_sources
- stale_sources
- parse_warning_sources

If adding all fields to existing CSV report is too invasive, create a new report:

```text
data/exports/cross_site_analytics_YYYYMMDD_HHMMSS.csv
```

and add CLI command:

```text
marketsentry export-cross-site-analytics-report
```

## 5. Candidate/watchlist integration

Do not overwrite Redfin facts.

Where appropriate, add report-only analytics fields to candidate/watchlist outputs:

- overall_cross_site_confidence_score
- discrepancy_severity_label
- cross_site_manual_review_priority

Do not change Quiet Score gatekeeper logic.

Do not let cross-site confidence override Quiet Score.

## 6. Dashboard integration

Update dashboard Cross-Site Review section to show:

- overall cross-site confidence score
- discrepancy severity label
- manual review priority
- low confidence sources
- stale sources
- parse warning sources

If Retrieval Operations dashboard has cross-site fixture processing visibility, keep it separate from analytical cross-site validation.

## 7. Tests

Add or update tests for:

- confidence_to_weight
- freshness_to_weight
- completeness_to_weight
- calculate_source_weight
- price agreement with high-confidence sources
- price agreement with low-confidence source downweighted
- status conflict severity
- DOM discrepancy severity
- gas disagreement handling
- garage disagreement handling
- stale source downweighted
- failed parse excluded or zero-weighted
- overall confidence score
- manual review priority
- cross-site analytics report generation
- dashboard table includes analytics fields
- no Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- no walkability fields added
- no real network calls
- existing MVP 1-23 tests still pass

All tests must pass.

## 8. Documentation

Update README.md and docs/RUNBOOK.md with a "Cross-Site Analytics" section.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with:

- cross-site confidence scoring
- discrepancy severity meaning
- manual review priority
- parser confidence impact
- freshness impact
- reminder that cross-site data validates but does not overwrite Redfin facts

Create design decision note:

```text
docs/decisions/023-confidence-weighted-cross-site-analytics.md
```

Explain:

- why confidence weighting is added after parser quality
- why low-confidence sources are downweighted
- why discrepancy severity is neutral
- why cross-site data remains validation-only
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
- Existing cross-site fixture processing works.
- Existing cross-site dashboard/health visibility works.
- Cross-site analytics tests pass.
- Cross-site analytics report exports.
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
8. Example high-confidence cross-site analytics output.
9. Example low-confidence/stale-source downweighted output.
10. Example discrepancy severity output.
11. Cross-site analytics report path and row count.
12. Dashboard/report updates added.
13. Confirmation that cross-site data does not overwrite Redfin source-of-truth fields.
14. Confirmation that Quiet Score gatekeeper remains unchanged.
15. Confirmation that walkability fields were not added.
16. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
17. Confirmation that tests perform no real network calls.
18. Recommended next implementation step.
19. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 24 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
