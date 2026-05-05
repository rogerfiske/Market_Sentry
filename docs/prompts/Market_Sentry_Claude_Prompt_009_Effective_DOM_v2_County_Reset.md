# Claude Code Prompt 009 - Effective DOM v2 County-Verified Reset Integration

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Review the current codebase and Milestone 8 implementation.
4. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
5. Keep PRD.md and Architecture.md in the project root.
6. Use src/marketsentry/ as the Python package path.
7. Do not move PRD.md or Architecture.md into docs/.
8. Do not implement live scraping, browser automation, Playwright, Selenium, or active network retrieval in this milestone.
9. Do not implement live County Recorder/Assessor access in this milestone.
10. Avoid inaccurate commit metadata. Do not add a Claude Sonnet co-authorship tag. If adding any co-author metadata, it must accurately reflect Claude Code Opus 4.6, or omit the co-author line.

Important PM direction:

Milestone 9 should integrate county-verified transfer/reset logic into Effective DOM v2.

The goal is to use county-confirmed ownership transfer records as reset boundaries for Effective DOM while preserving recent Churn Index as a separate reportable factor.

Do not erase churn metrics.

Do not overwrite or discard listing history just because a county transfer exists.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It starts with Redfin candidate discovery, stages homes for human review, and then monitors user-selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, cross-site validation, county sale/ownership-transfer verification, and a separate recent Churn Index.

Critical domain rules:

1. Effective DOM measures property-level market exposure across listing, removal, and relisting events within a defined lookback window, excluding periods reset by confirmed ownership transfer.
2. Confirmed ownership transfer means a county-recorded sale/deed/transfer event that supports resetting the Effective DOM cycle.
3. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
4. Churn Index measures recent 2-3 year property/listing instability and remains reportable even when Effective DOM is reset.
5. Quiet Score is the gatekeeper. Reject or heavily downgrade if Quiet Score is below threshold, even when Vibrancy is low.
6. Target is very high Quiet and very low Vibrancy.
7. Low Vibrancy alone is not sufficient.
8. Any mention of gas means the property has natural gas service/supply.
9. Walkability-type information is excluded from the initial scope.
10. Use neutral language. Do not infer seller intent.
11. The workflow is human-in-the-loop: candidate review queue first, then user-selected watched properties.
12. County data verifies reset boundaries; it should not automatically make purchase recommendations.

Your task for Prompt 009:

Implement Effective DOM v2 County-Verified Reset Integration.

This milestone must update Effective DOM calculations and reporting to support county-confirmed reset boundaries while preserving separate recent churn metrics.

No live network calls.

## 1. Effective DOM v2 model

Create or update typed models for:

- EffectiveDomV2Metrics
- EffectiveDomResetBoundary
- ChurnIndexMetrics
- CountyResetIntegrationResult
- EffectiveDomComparisonRow

The v2 metrics should include:

- displayed_dom
- effective_dom_v1
- effective_dom_v2
- effective_dom_delta_v1
- effective_dom_delta_v2
- county_reset_applied
- county_reset_date
- county_reset_record_type
- county_reset_record_id
- county_reset_confidence
- pre_reset_calendar_exposure_dom
- post_reset_calendar_exposure_dom
- pre_reset_sale_cycle_dom
- post_reset_sale_cycle_dom
- pre_reset_rent_sale_exposure_dom
- post_reset_rent_sale_exposure_dom
- first_observed_event_date
- latest_observed_event_date
- first_post_reset_event_date
- latest_post_reset_event_date
- listing_churn_count
- dom_reset_count
- sale_rent_alternation_count
- price_change_count
- recent_churn_index
- recent_churn_lookback_years
- recent_churn_event_count
- recent_dom_reset_count
- recent_sale_rent_alternation_count
- churn_preserved_after_transfer

## 2. Effective DOM v2 calculation

Enhance or extend:

```text
src/marketsentry/effective_dom.py
```

Required behavior:

- Accept listing events and optional county transfer/reset records.
- Identify the most recent county-confirmed ownership transfer date relevant to the observed event window.
- Treat the most recent confirmed transfer as a reset boundary for Effective DOM v2.
- Exclude listing exposure before the reset boundary from effective_dom_v2.
- Preserve pre-reset exposure metrics for reporting.
- Preserve all churn metrics separately.
- If no county-confirmed transfer exists, effective_dom_v2 should equal effective_dom_v1 or the same fallback result as v1.
- If a county transfer exists before all observed listing events, v2 should usually equal v1.
- If a county transfer occurs inside the listing history window, v2 should recalculate only the post-transfer exposure.
- If a county transfer occurs after the latest observed listing event, do not use it as a reset unless the logic is explicitly justified and tested.

Important:
- Do not treat deed_of_trust, reconveyance, lien, assessment, permit, tax_record, or unknown as reset boundaries.
- Use conservative reset logic.
- County reset support should be based on Milestone 8 county_verification functions.

## 3. Churn Index v1

Implement a deterministic Churn Index function.

Create or update a module, for example:

```text
src/marketsentry/churn_index.py
```

Required functions:

- calculate_churn_index(events: list[ListingEvent], lookback_years: int = 3, analysis_date: date | None = None) -> ChurnIndexMetrics
- calculate_churn_index_from_counts(listing_churn_count: int, dom_reset_count: int, sale_rent_alternation_count: int, price_change_count: int = 0) -> float

Default lookback:

```text
3 years
```

Suggested initial scoring:

- listing_churn_count contributes 1.0 each
- dom_reset_count contributes 1.5 each
- sale_rent_alternation_count contributes 2.0 each
- price_change_count contributes 0.5 each
- normalize/cap score to 0-10

Required behavior:

- Date-filter events to the 3-year lookback when dates are available.
- If event dates are missing, fall back to available counts and document reduced confidence.
- Churn Index is never zeroed by county reset.
- Churn Index should be reportable even when county_reset_applied is true.
- Use neutral language.

## 4. Database recalculation workflow

Add a recalculation workflow that updates candidates and watched properties with v2 metrics where schema supports it, or generates report-only values if schema does not.

Create or update:

```text
src/marketsentry/effective_dom_v2_recalc.py
```

Required behavior:

- Read candidates, watched_properties, listing_events, and county_record_observations.
- Compute Effective DOM v2 metrics for properties with enough data.
- Preserve user_decision and user_notes.
- Preserve active_watch_status and watch_priority.
- Do not delete listing events.
- Do not zero listing_churn_count, dom_reset_count, or sale_rent_alternation_count.
- Store v2 report values in the database only if the schema already supports them or via a documented non-destructive migration.
- Prefer report-only computation if database changes are not necessary.

## 5. Effective DOM v2 report

Create or update a report module:

```text
src/marketsentry/effective_dom_v2_report.py
```

CLI command:

```text
marketsentry export-effective-dom-v2-report
```

Required report columns:

- property_id
- candidate_id
- address
- city
- zip
- apn
- redfin_url
- current_price
- displayed_dom
- effective_dom_v1
- effective_dom_v2
- effective_dom_delta_v1
- effective_dom_delta_v2
- county_reset_applied
- county_reset_date
- county_reset_record_type
- county_reset_record_id
- county_reset_confidence
- pre_reset_calendar_exposure_dom
- post_reset_calendar_exposure_dom
- pre_reset_sale_cycle_dom
- post_reset_sale_cycle_dom
- pre_reset_rent_sale_exposure_dom
- post_reset_rent_sale_exposure_dom
- listing_churn_count
- dom_reset_count
- sale_rent_alternation_count
- price_change_count
- recent_churn_index
- recent_churn_lookback_years
- recent_churn_event_count
- recent_dom_reset_count
- recent_sale_rent_alternation_count
- churn_preserved_after_transfer
- quiet_score
- vibrancy_score
- quiet_gatekeeper_result
- gas_service
- garage_spaces
- user_notes
- notes

Save output by default to:

```text
data/exports/effective_dom_v2_YYYYMMDD_HHMMSS.csv
```

## 6. CLI commands

Add or complete:

```text
marketsentry recalc-effective-dom-v2
marketsentry export-effective-dom-v2-report
```

Behavior:

### recalc-effective-dom-v2

- Computes v2 metrics for candidates and watched properties where possible.
- Prints:
  - properties scanned
  - county transfers considered
  - county resets applied
  - records updated or report-only rows computed
  - churn metrics preserved
  - warnings/errors

### export-effective-dom-v2-report

- Exports CSV report.
- Prints output path and row count.

CLI output must be ASCII-safe.

## 7. Effective DOM v1/v2 comparison behavior

Add tests and logic to prove the following scenarios:

### Scenario A: No county transfer

- effective_dom_v2 equals effective_dom_v1.
- county_reset_applied = false.
- Churn Index still computed.

### Scenario B: County transfer before all listing events

- effective_dom_v2 equals effective_dom_v1 or effectively unchanged.
- county_reset_applied may be false or true only if well documented.
- Churn Index still computed.

### Scenario C: County transfer inside listing-history window

- effective_dom_v2 excludes pre-transfer exposure.
- pre-reset exposure metrics remain reportable.
- post-reset exposure metrics are used for v2.
- county_reset_applied = true.
- Churn Index remains reportable and nonzero when churn exists.

### Scenario D: County transfer after latest listing event

- Do not apply reset to historical Effective DOM.
- county_reset_applied = false unless explicitly justified.
- Churn Index still computed.

### Scenario E: Non-transfer county record inside listing-history window

- Deed of trust, reconveyance, lien, permit, tax record, or assessment does not reset Effective DOM.
- Churn Index still computed.

## 8. Reports and wording

Use neutral report language.

Allowed wording:

- county reset supported
- county-confirmed transfer
- reset boundary applied
- recent churn preserved
- listing churn
- DOM reset pattern
- sale/rent alternation

Avoid:

- spoofing
- deception
- bad actor
- seller manipulation
- fraud
- any seller-intent accusation

## 9. Tests

Add or update tests for:

- Effective DOM v2 no-transfer behavior.
- County transfer before listing events.
- County transfer inside listing window.
- County transfer after listing events.
- Non-transfer county record does not reset.
- Deed of trust does not reset.
- Reconveyance does not reset.
- Lien does not reset.
- Permit does not reset.
- Churn Index calculation from events.
- Churn Index 3-year lookback filtering.
- Churn Index fallback from counts.
- Churn Index remains nonzero when county reset applies.
- Churn metrics are not zeroed by county reset.
- v2 report includes all required columns.
- CLI recalc-effective-dom-v2 command.
- CLI export-effective-dom-v2-report command.
- Existing MVP 1-8 tests still pass.

All tests must pass.

## 10. Documentation

Update README.md with:

- Milestone 9 status.
- Explanation of Effective DOM v2.
- Explanation of county reset boundary logic.
- Explanation of Effective DOM v1 vs v2.
- Explanation of Churn Index.
- Explanation that Churn Index is preserved after county resets.
- How to run recalc-effective-dom-v2.
- How to run export-effective-dom-v2-report.
- Clear statement that Milestone 9 performs no live county access, no scraping, and no network access.

Add design decision note:

```text
docs/decisions/008-effective-dom-v2-county-reset-and-churn-index.md
```

Explain:

- Why county-confirmed transfer is used as a reset boundary.
- Why non-transfer documents do not reset Effective DOM.
- Why churn remains separate from Effective DOM.
- Why Churn Index may or may not prove predictive.
- Why reports are analytical aids, not purchase recommendations.

## 11. Code standards

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
- Preserve source URLs and timestamps for future auditability.
- Avoid inaccurate Claude co-authorship metadata.
- Be conservative when applying county reset boundaries.
- Preserve churn metrics separately from Effective DOM reset logic.

Quality gates:

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works for fresh database.
- Existing candidate review workflow still works.
- Existing Redfin import/fixture parsing/enrichment still works.
- Existing Effective DOM v1/scoring/reporting still works.
- Existing cross-site enrichment/reporting still works.
- Existing watchlist monitoring/reporting still works.
- Existing county import/fixture parsing/verification still works.
- Effective DOM v2 calculations work.
- Churn Index calculations work.
- v2 report exports.
- Churn Index remains reportable even when county_reset_applied is true.
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
8. Any schema changes or migration fixes made.
9. Example CLI workflow used to verify Milestone 9.
10. Example Effective DOM v1 vs v2 output for no-transfer case.
11. Example Effective DOM v1 vs v2 output for transfer-inside-listing-window case.
12. Example non-transfer document case proving no reset occurs.
13. Example Churn Index output showing churn preserved after county reset.
14. Effective DOM v2 report output path and row count.
15. Confirmation that non-transfer documents are not treated as Effective DOM reset records.
16. Confirmation that churn metrics are not zeroed or erased by county reset.
17. Confirmation that no live network calls, scraping, Playwright, Selenium, or browser automation were added.
18. Recommended next implementation step.
19. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 9 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
