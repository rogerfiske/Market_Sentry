# Claude Code Prompt 005 - Effective DOM Engine and Candidate Scoring Report

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Review the current codebase and Milestone 4 implementation.
4. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
5. Keep PRD.md and Architecture.md in the project root.
6. Use src/marketsentry/ as the Python package path.
7. Do not move PRD.md or Architecture.md into docs/.
8. Do not implement live scraping, browser automation, Playwright, Selenium, or active network retrieval in this milestone.

Important PM direction:

Milestone 5 should harden the Effective DOM engine and scoring/reporting layer before cross-site enrichment.

Do not implement Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor parsing in this milestone.

The goal is to transform parsed Redfin listing events into more useful buyer-side analysis outputs:

- Effective DOM variants
- DOM reset indicators
- listing churn indicators
- sale/rent alternation indicators
- Quiet gatekeeper result
- gas service confirmation
- garage match
- candidate scoring
- review-ready CSV/report outputs

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It starts with Redfin candidate discovery, stages homes for human review, and then monitors user-selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, and cross-site/county validation.

Critical domain rules:

1. Effective DOM measures property-level market exposure across listing, removal, and relisting events within a defined lookback window, excluding periods reset by confirmed ownership transfer.
2. Quiet Score is the gatekeeper. Reject or heavily downgrade if Quiet Score is below threshold, even when Vibrancy is low.
3. Target is very high Quiet and very low Vibrancy.
4. Low Vibrancy alone is not sufficient.
5. Any mention of gas means the property has natural gas service/supply.
6. Walkability-type information is excluded from the initial scope.
7. Use neutral language. Do not infer seller intent.
8. The workflow is human-in-the-loop: candidate review queue first, then user-selected watched properties.

Your task for Prompt 005:

Implement Effective DOM Engine and Candidate Scoring Report v1.

This milestone must make Market_Sentry useful for analyzing the Redfin-derived candidates already in the review queue, without adding new web sources.

No live network calls.

## 1. Effective DOM metrics v1

Enhance or complete:

```text
src/marketsentry/effective_dom.py
```

Implement deterministic, tested calculations based on parsed listing events.

Required metrics:

- displayed_dom
- current_listing_instance_dom
- sale_cycle_dom
- rent_sale_exposure_dom
- calendar_exposure_dom
- effective_dom
- effective_dom_delta
- listing_churn_count
- dom_reset_count
- sale_rent_alternation_count
- price_change_count
- first_observed_event_date
- latest_observed_event_date
- first_observed_price
- current_or_latest_price
- lowest_observed_price
- highest_observed_price

Definitions:

### displayed_dom

The DOM displayed on the source page, if present. If not present, keep None.

### current_listing_instance_dom

Approximate days from the latest listing/relisting event to the analysis date, unless a sold/removed event indicates the listing is no longer active.

### sale_cycle_dom

Total active sale-listing exposure days across listed/relisted/pending/back-on-market periods within the current no-sale cycle.

### rent_sale_exposure_dom

Total active exposure days across sale and rental listing periods within the current no-sale cycle.

### calendar_exposure_dom

Calendar days from the earliest observed non-sold listing/rental event in the current cycle to the analysis date or latest observed event date.

### effective_dom

For this milestone, define effective_dom as the best available property-level market exposure estimate:

1. Prefer rent_sale_exposure_dom if sale/rent alternation is present.
2. Else prefer sale_cycle_dom if calculable.
3. Else prefer calendar_exposure_dom.
4. Else fallback to current_listing_instance_dom.
5. Else fallback to displayed_dom.

### effective_dom_delta

effective_dom - displayed_dom, when both exist.

### dom_reset_count

Count removed followed by relisted/listed within 90 days without an intervening sold event in parsed events.

### sale_rent_alternation_count

Count transitions between sale exposure and rental exposure event categories.

### price_change_count

Count price_changed events.

Important:

- Do not over-engineer county sale reset logic yet.
- County verification comes later.
- If a sold event is present, it can reset the current observed cycle in the parsed data.
- Use neutral terminology only.

## 2. Event normalization

Create or improve event normalization helpers.

Supported normalized event categories:

- sale_listed
- sale_removed
- sale_relisted
- sale_pending
- sale_back_on_market
- sale_sold
- sale_price_changed
- rental_listed
- rental_removed
- unknown

Map existing event_type values to these normalized categories.

Add tests that verify event normalization.

## 3. Candidate scoring v1

Enhance or complete:

```text
src/marketsentry/scoring.py
```

Add a consolidated candidate scoring result with:

- quiet_gatekeeper_result
- location_fit_label
- location_fit_score
- property_fit_score
- effective_dom_leverage_score
- data_confidence_score
- overall_review_score
- review_recommendation
- warning_flags
- positive_flags
- explanation

Scoring rules:

### Quiet gatekeeper

- quiet_score < 7.0: fail_noise_risk
- quiet_score >= 8.0 and vibrancy_score <= 2.5: target_location_fit
- quiet_score >= 9.0 and vibrancy_score <= 2.0: excellent_location_fit
- quiet_score missing: needs_manual_location_review

Low Vibrancy alone must never override poor Quiet.

### Location fit score

Suggested:

- excellent_location_fit: 100
- target_location_fit: 85
- quiet_but_review_vibrancy: 70
- borderline_quiet: 50
- fail_noise_risk: 0
- needs_manual_location_review: 40

### Property fit score

Use available fields:

- garage_spaces >= 2 is positive.
- gas_service = true is positive.
- price within configured range is positive.
- minimum beds/baths from the baseline Redfin filters is positive.
- missing fields reduce confidence but do not automatically fail.

### Effective DOM leverage score

Positive signals:

- effective_dom_delta >= 90
- dom_reset_count >= 1
- listing_churn_count >= 3
- sale_rent_alternation_count >= 1
- price_change_count >= 1

### Data confidence score

Positive signals:

- Redfin URL present.
- Address present.
- Price present.
- Quiet/Vibrancy present.
- Garage/gas fields present.
- Listing events present.
- Effective DOM calculable.

### review_recommendation values

Use these exact values:

- strong_review
- review
- maybe_review
- reject_location_noise
- needs_more_data

Important:
- review_recommendation is not a purchase recommendation.
- It only determines how the candidate should be treated in the user review queue.
- Rejecting due to location noise is acceptable because Quiet is the user's gatekeeper.

## 4. Candidate analysis report

Create a report module, for example:

```text
src/marketsentry/candidate_report.py
```

Required outputs:

1. CSV report for candidate review.
2. Optional Markdown report for human-readable summaries.

At minimum, implement CSV report output.

Report columns:

- candidate_id
- review_recommendation
- overall_review_score
- location_fit_label
- quiet_gatekeeper_result
- quiet_score
- vibrancy_score
- price
- beds
- baths
- sqft
- garage_spaces
- gas_service
- gas_evidence
- displayed_dom
- effective_dom
- effective_dom_delta
- listing_churn_count
- dom_reset_count
- sale_rent_alternation_count
- price_change_count
- data_confidence_score
- warning_flags
- positive_flags
- address
- city
- zip
- redfin_url
- user_decision
- user_notes

Save output by default to:

```text
data/exports/candidate_analysis_YYYYMMDD_HHMMSS.csv
```

## 5. Database update workflow

Add functionality to recalculate and persist Effective DOM/scoring fields for candidates.

Required behavior:

- Read candidates and listing_events from database.
- Recalculate Effective DOM metrics.
- Update candidate_review_queue with:
  - effective_dom_estimate
  - listing_churn_count
  - dom_reset_count
  - sale_rent_alternation_count
  - quiet_gatekeeper_result
- Do not overwrite user_decision or user_notes.
- Preserve existing fields when new value is None.
- This recalculation should be idempotent.

If schema lacks columns needed for v1 scoring/reporting, either:

1. Use computed report-only fields without schema change, or
2. Add a simple migration with documentation.

Prefer report-only fields unless schema change is clearly justified.

## 6. CLI commands

Add or complete:

```text
marketsentry recalc-candidates
marketsentry export-analysis-report
marketsentry list-candidates
marketsentry export-review
```

Behavior:

### recalc-candidates

- Recalculates Effective DOM and scoring-related fields for candidate_review_queue.
- Prints:
  - candidates scanned
  - candidates updated
  - listing events used
  - warnings/errors

### export-analysis-report

- Exports candidate analysis report CSV.
- Prints output file path and row count.

CLI output must be ASCII-safe.

## 7. Tests

Add or update tests for:

- Event normalization.
- Effective DOM metrics with normal listing history.
- Effective DOM metrics with Via La Tranquila-style churn.
- Effective DOM metrics with sale/rent alternation.
- Effective DOM metrics with sold reset.
- Effective DOM fallback behavior when events are missing.
- Quiet gatekeeper scoring.
- Low Vibrancy not overriding poor Quiet.
- Candidate scoring warning/positive flags.
- Analysis report CSV columns.
- Recalculation updates candidates without overwriting user decisions.
- CLI recalc/export report commands where practical.

All tests must pass.

## 8. Documentation

Update README.md with:

- Milestone 5 status.
- Explanation of Effective DOM v1.
- Explanation of candidate scoring labels.
- How to run recalc-candidates.
- How to run export-analysis-report.
- How to use the analysis CSV for review.
- Clear statement that Milestone 5 performs no live scraping or network access.

Add design decision note:

```text
docs/decisions/004-effective-dom-v1-and-review-scoring.md
```

Explain:

- Effective DOM v1 definitions.
- Why Quiet is the gatekeeper.
- Why low Vibrancy cannot overcome poor Quiet.
- Why review_recommendation is not a purchase recommendation.
- Why county sale reset logic remains deferred.

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
- Preserve source URLs and timestamps for future auditability.
- Avoid inaccurate Claude co-authorship metadata.

Quality gates:

- Project imports cleanly.
- CLI commands run.
- SQLite init still works.
- Existing review queue workflow still works.
- Manual Redfin URL import still works.
- Saved search fixture parsing still works.
- Saved detail fixture parsing/enrichment still works.
- Effective DOM v1 calculations work.
- Candidate analysis report exports.
- Unit tests pass.
- No live scraping or network calls implemented.
- Changes committed and pushed to origin/main.

Completion report required:

When finished, provide:

1. Summary of what you implemented.
2. Files created or modified.
3. Exact commands run.
4. Test results.
5. Any dependency changes.
6. Any assumptions made.
7. Any blockers or risks.
8. Any schema changes made.
9. Example CLI workflow used to verify Milestone 5.
10. Example Effective DOM metric output for one normal fixture.
11. Example Effective DOM metric output for one churn fixture.
12. Example scoring output showing Quiet gatekeeper behavior.
13. Analysis report output path and row count from verification.
14. Confirmation that no live network calls, scraping, Playwright, Selenium, or browser automation were added.
15. Recommended next implementation step.
16. Git commit hash after committing and pushing completed changes to origin/main.

Important:

After all quality gates pass, commit and push the completed story changes to origin/main and include the commit hash in your completion report.
