# Claude Code Prompt 023 - Cross-Site Parser Quality and Fixture Corpus Expansion

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Read docs/RUNBOOK.md.
4. Read docs/LIVE_RETRIEVAL_STRATEGY.md.
5. Read docs/FIXTURE_CAPTURE_QUEUE.md.
6. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
7. Review the current codebase through commit 1e3235c.
8. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
9. Keep PRD.md and Architecture.md in the project root.
10. Use src/marketsentry/ as the Python package path.
11. Do not move PRD.md or Architecture.md into docs/.
12. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
13. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
14. Do not run any live network calls in tests.
15. Do not make scheduled tasks run live retrieval by default.
16. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

Milestone 23 should improve cross-site parser quality and fixture coverage for Zillow, Realtor.com, Homes.com, and Compass using local saved/synthetic fixtures only.

This milestone should NOT add live retrieval.

This milestone should NOT broaden scraping.

The goal is to make cross-site validation more useful by improving extraction reliability, field normalization, confidence scoring, parse warnings, and parser coverage across common HTML variations.

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

Your task for Prompt 023:

Implement Cross-Site Parser Quality and Fixture Corpus Expansion v1.

## 1. Parser quality goals

Improve parser robustness for:

```text
src/marketsentry/zillow_parser.py
src/marketsentry/realtor_parser.py
src/marketsentry/homes_parser.py
src/marketsentry/compass_parser.py
```

Each parser should improve extraction of:

- address
- city
- state
- zip
- price
- beds
- baths
- sqft
- lot size
- listing status
- displayed DOM / days on market when available
- garage spaces where available
- gas service evidence
- listing agent
- listing broker
- MLS number
- source MLS
- property description
- parse warnings
- parse confidence

Do not add walkability fields.

## 2. Fixture corpus expansion

Add synthetic/local fixtures for each source.

For each source, add at least these fixture variants:

```text
tests/fixtures/cross_site/<source>/normal_property.html
tests/fixtures/cross_site/<source>/price_discrepancy.html
tests/fixtures/cross_site/<source>/status_pending.html
tests/fixtures/cross_site/<source>/sold_or_off_market.html
tests/fixtures/cross_site/<source>/missing_optional_fields.html
tests/fixtures/cross_site/<source>/gas_evidence.html
tests/fixtures/cross_site/<source>/garage_evidence.html
tests/fixtures/cross_site/<source>/sparse_or_malformed.html
```

If some already exist, preserve them and add only missing variants.

Fixtures must be static, synthetic/minimal, and must not require network access.

## 3. Parser confidence model

Create or improve a parser confidence approach.

Suggested fields:

- parse_status:
  - success
  - partial
  - failed
- parse_confidence:
  - high
  - medium
  - low
- parse_warnings:
  - list or semicolon-separated text
- missing_required_fields:
  - list or semicolon-separated text

Confidence guidance:

- high: address and at least price/status/property facts extracted
- medium: address and some facts extracted, but important fields missing
- low: sparse or uncertain parse
- failed: no useful property identity

If existing models use strings or integer warning counts, preserve backward compatibility.

## 4. Normalization improvements

Improve normalization helpers where useful:

- price parsing:
  - $850,000
  - $850K
  - $1.2M
  - 850000
- sqft parsing:
  - 2,450 sqft
  - 2450 square feet
- lot size parsing:
  - 7,405 sqft lot
  - 0.25 acres
- beds/baths parsing:
  - 4 beds
  - 3.5 baths
- DOM parsing:
  - 12 days on market
  - Listed 45 days ago
  - On site 17 days
- status parsing:
  - active
  - pending
  - contingent
  - sold
  - off market
  - coming soon
- garage parsing:
  - 2 garage spaces
  - 3-car garage
  - attached garage
- gas evidence:
  - gas fireplace
  - gas range
  - natural gas
  - gas dryer hookup
  - gas heating

Remember: any mention of gas means gas service/supply evidence.

## 5. Cross-site observation quality fields

If current `cross_site_observations` schema lacks parse confidence fields, prefer non-destructive migration or structured notes.

Potential fields:

- parse_status
- parse_confidence
- parse_warnings
- missing_required_fields

If schema changes are made, they must be non-destructive and idempotent.

## 6. Cross-site comparison/report improvements

Update cross-site comparison/report where practical to include parser quality fields:

- source_parse_status
- source_parse_confidence
- source_parse_warnings
- source_missing_required_fields

Do not make this too invasive. If adding source-specific columns is too much, include summary fields such as:

- lowest_parse_confidence
- sources_with_parse_warnings
- sources_with_partial_parse

## 7. Tests

Add or update tests for each source:

- normal property parse
- price discrepancy variant parse
- pending status parse
- sold/off-market status parse
- missing optional fields partial parse
- gas evidence parse
- garage evidence parse
- sparse/malformed fixture graceful handling
- price normalization variants
- sqft normalization variants
- lot size normalization variants
- DOM normalization variants
- status normalization variants
- confidence classification
- warnings/missing required fields
- no walkability fields added
- no real network calls
- existing MVP 1-22 tests still pass

All tests must pass.

## 8. Documentation

Update README.md and docs/RUNBOOK.md with a "Cross-Site Parser Quality" section.

Update docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md with:

- fixture variants
- parser confidence meaning
- parse warning meaning
- recommended manual review behavior for low-confidence parse
- reminder that cross-site data validates Redfin and does not overwrite Redfin source-of-truth fields

Create design decision note:

```text
docs/decisions/022-cross-site-parser-quality-fixture-corpus.md
```

Explain:

- why parser quality is improved before live cross-site retrieval
- why synthetic fixtures are used
- why parse confidence matters
- why cross-site data stays validation-only
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
- Do not add walkability parsing.

Quality gates:

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works for fresh database.
- Existing candidate review workflow still works.
- Existing Redfin workflows still work.
- Existing cross-site dry-run/manual-fixture workflow still works.
- Existing cross-site fixture processing works.
- Existing cross-site dashboard/health visibility works.
- Parser quality tests pass for all four non-Redfin sources.
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
8. Fixture variants added by source.
9. Parser fields improved by source.
10. Example parse output with high confidence.
11. Example parse output with partial/low confidence and warnings.
12. Schema changes or migration details, if any.
13. Confirmation that cross-site data does not overwrite Redfin source-of-truth fields.
14. Confirmation that walkability fields were not added.
15. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
16. Confirmation that tests perform no real network calls.
17. Recommended next implementation step.
18. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 23 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
