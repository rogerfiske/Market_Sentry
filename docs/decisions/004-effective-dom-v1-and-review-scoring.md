# Design Decision 004: Effective DOM v1 and Review Scoring

**Date:** 2026-05-05
**Status:** Implemented
**Milestone:** 5 - Effective DOM Engine and Candidate Scoring Report

## Context

Market_Sentry can now discover candidates (Milestone 3) and enrich them with property facts, lifestyle scores, gas evidence, and listing history (Milestone 4). However, the system still lacks:

1. **Actionable Analysis Outputs**: Raw listing events need transformation into buyer-side leverage indicators
2. **Comprehensive Effective DOM Metrics**: Multiple DOM variants with fallback hierarchy
3. **Unified Candidate Scoring**: Holistic evaluation combining location fit, property fit, DOM leverage, and data confidence
4. **Review Prioritization**: Clear recommendations for which candidates deserve human review
5. **Exportable Reports**: CSV/Markdown outputs for systematic review workflow

The project needs a way to:
- Calculate multiple Effective DOM variants from parsed listing events
- Implement deterministic, tested scoring that respects critical domain rules
- Generate review-ready analysis reports
- Recalculate metrics as new data becomes available
- Maintain auditability and explainability of all scoring decisions

## Decision

**Implement Effective DOM Engine v1 and Candidate Scoring Report system with deterministic, testable metrics and review recommendations.**

### Implementation

Milestone 5 implements:

1. **Effective DOM Engine v1** (`effective_dom.py` - complete rewrite)
   - **Event Normalization**: Map raw event_type values to normalized categories (sale_listed, sale_removed, sale_relisted, sale_pending, sale_back_on_market, sale_sold, sale_price_changed, rental_listed, rental_removed, unknown)
   - **Current Cycle Detection**: Identify events after last sold event (sold resets the cycle)
   - **Multiple DOM Variants**:
     - `displayed_dom`: DOM from source page
     - `current_listing_instance_dom`: Days from latest listing/relisting event
     - `sale_cycle_dom`: Total active sale-listing exposure days
     - `rent_sale_exposure_dom`: Total exposure across sale and rental periods
     - `calendar_exposure_dom`: Calendar days from earliest event
     - `effective_dom`: Best available estimate using fallback hierarchy
     - `effective_dom_delta`: Difference between effective_dom and displayed_dom
   - **Listing Activity Indicators**:
     - `listing_churn_count`: Count of all churn events
     - `dom_reset_count`: Removals followed by relisting within 90 days
     - `sale_rent_alternation_count`: Transitions between sale and rental exposure
     - `price_change_count`: Price reduction/increase events
   - **Price Tracking**: first_observed_price, current_or_latest_price, lowest_observed_price, highest_observed_price
   - **Date Tracking**: first_observed_event_date, latest_observed_event_date
   - CLI helper: Used by recalc-candidates command

2. **Candidate Scoring v1** (`scoring.py` - complete rewrite)
   - **CandidateScore class**: Structured scoring result with all required fields
   - **Quiet Gatekeeper**: Critical domain rule enforcement (quiet_score < 7.0 fails regardless of vibrancy)
   - **Location Fit Scoring**:
     - excellent_location_fit (100): quiet >= 9.0, vibrancy <= 2.0
     - target_location_fit (85): quiet >= 8.0, vibrancy <= 2.5
     - quiet_but_review_vibrancy (70): quiet >= 7.5, vibrancy > 2.5
     - borderline_quiet (50): quiet >= 7.0 but below targets
     - fail_noise_risk (0): quiet < 7.0
     - needs_manual_location_review (40): missing quiet_score
   - **Property Fit Scoring** (0-100 scale):
     - Gas service: +20 points (has gas) / -10 points (no gas)
     - Garage spaces: +15 points (3+) / +10 points (2) / -5 points (<2)
     - Price within range ($550k-$990k): +15 points
     - Beds/baths meet minimums: +5 points each
     - Base score: 50
   - **Effective DOM Leverage Scoring** (0-100 scale):
     - High DOM delta (>= 90): +20 points
     - DOM resets (>= 1): +15 points
     - High listing churn (>= 3): +10 points
     - Sale/rent alternation: +10 points
     - Price changes: +5 points per change (max +15)
     - Base score: 50
   - **Data Confidence Scoring** (0-100 scale):
     - Redfin URL present: +10 points
     - Address present: +10 points
     - Price present: +10 points
     - Quiet/Vibrancy present: +10 points each
     - Garage/gas fields present: +10 points each
     - Listing events present: +10 points
     - Effective DOM calculable: +10 points
     - Base score: 10
   - **Review Recommendations**:
     - `strong_review`: overall_review_score >= 80
     - `review`: overall_review_score >= 60
     - `maybe_review`: overall_review_score >= 40
     - `reject_location_noise`: quiet_gatekeeper_result == "fail_noise_risk"
     - `needs_more_data`: data_confidence_score < 40
   - **Warning Flags**: low_quiet_score, fail_quiet_gatekeeper, missing_quiet_score, no_gas_service, insufficient_garage_spaces, price_outside_range, missing_property_facts, no_listing_history, low_data_confidence
   - **Positive Flags**: excellent_location, target_location, has_gas_service, good_garage_spaces, high_dom_delta, has_dom_resets, high_listing_churn, sale_rent_alternation, multiple_price_changes
   - **Scoring Explanation**: Human-readable explanation of scoring result

3. **Candidate Analysis Report** (`candidate_report.py`)
   - **CSV Export**: Comprehensive analysis report with all metrics and flags
   - **Markdown Export**: Optional human-readable report format
   - **Report Columns**: candidate_id, review_recommendation, overall_review_score, location_fit_label, quiet_gatekeeper_result, quiet_score, vibrancy_score, price, beds, baths, sqft, garage_spaces, gas_service, gas_evidence, displayed_dom, effective_dom, effective_dom_delta, listing_churn_count, dom_reset_count, sale_rent_alternation_count, price_change_count, data_confidence_score, warning_flags, positive_flags, address, city, zip, redfin_url, user_decision, user_notes
   - Default output: `data/exports/candidate_analysis_YYYYMMDD_HHMMSS.csv`
   - CLI command: `marketsentry export-analysis-report [--output path] [--markdown]`

4. **Candidate Recalculation Workflow** (`candidate_recalc.py`)
   - **Idempotent Recalculation**: Safe to run multiple times
   - **Metric Updates**: Recalculate effective_dom_estimate, listing_churn_count, dom_reset_count, sale_rent_alternation_count, quiet_gatekeeper_result
   - **Preserve User Data**: Never overwrites user_decision or user_notes
   - **Smart Updates**: Only updates fields when new value is not None
   - CLI command: `marketsentry recalc-candidates [--database path]`

5. **CLI Commands** (`cli.py`)
   - `marketsentry recalc-candidates`: Recalculate Effective DOM and scoring metrics for all candidates
   - `marketsentry export-analysis-report`: Export candidate analysis report to CSV/Markdown

6. **Comprehensive Tests**
   - `tests/test_effective_dom_v1.py`: 27 tests for event normalization, DOM metrics (normal history, churn patterns, sale/rent alternation, sold event resets, fallback behavior)
   - `tests/test_scoring_v1.py`: 31 tests for Quiet gatekeeper (including critical rule that low vibrancy cannot override poor quiet), property fit, DOM leverage, data confidence, warning/positive flags, review recommendations, scoring explanations
   - Total: 188 tests passing (58 new comprehensive v1 tests)

## Rationale

### Why Multiple Effective DOM Variants?

Different DOM calculations serve different purposes:

- **displayed_dom**: Source of record (what Redfin shows)
- **current_listing_instance_dom**: Current listing age only
- **sale_cycle_dom**: Active sale exposure (excludes rental periods)
- **rent_sale_exposure_dom**: Total exposure including rental attempts (signals seller motivation)
- **calendar_exposure_dom**: Maximum calendar time (includes gaps)
- **effective_dom**: Best available estimate with intelligent fallback

**Fallback Hierarchy Rationale:**
1. Prefer `rent_sale_exposure_dom` when sale/rent alternation present (strongest signal of seller flexibility)
2. Else prefer `sale_cycle_dom` (active sale exposure)
3. Else prefer `calendar_exposure_dom` (total property-level exposure)
4. Else fallback to `current_listing_instance_dom` (latest listing age)
5. Else fallback to `displayed_dom` (at least show what's visible)

This hierarchy ensures the system always provides the most informative DOM variant available given the data.

### Why Quiet is the Gatekeeper?

**Critical Domain Rule:** Quiet Score is the mandatory gatekeeper. Properties with quiet_score < 7.0 are rejected (review_recommendation = "reject_location_noise") regardless of all other factors.

**Rationale:**
- **User Preference is Absolute**: The user explicitly requires very quiet locations. This is non-negotiable.
- **Noise Risk is Binary**: A location is either acceptably quiet or it's not. No other property attribute can compensate for excessive noise.
- **Prevents False Positives**: Without gatekeeper enforcement, the system might recommend high-vibrancy (noisy) properties based on other positive signals (gas service, good price, high DOM leverage).
- **Workflow Efficiency**: Rejecting noise-risk properties early prevents wasted review time on unsuitable locations.

### Why Low Vibrancy Cannot Override Poor Quiet?

**Critical Domain Rule:** Low Vibrancy alone is NOT sufficient. The target is very high Quiet AND very low Vibrancy.

**Scenario that must be prevented:**
- Property A: quiet_score = 5.0, vibrancy_score = 0.5
- Without proper gatekeeper: might score well due to very low vibrancy
- **Problem**: The property is still too noisy (quiet_score < 7.0)
- **Correct behavior**: Reject due to fail_noise_risk

**Rationale:**
- **Vibrancy Measures Activity, Not Noise**: Low vibrancy means "not much happening" but doesn't guarantee quietness
- **Quiet is the Direct Noise Proxy**: Quiet score directly measures noise risk
- **Domain Expert Requirement**: User specifically wants "very high Quiet" as primary requirement
- **Test Coverage**: Explicit test `test_low_vibrancy_cannot_override_poor_quiet` enforces this rule

**Implementation:**
```python
if quiet_score < 7.0:
    result.quiet_gatekeeper_result = "fail_noise_risk"
    result.location_fit_label = "fail_noise_risk"  # Override regardless of vibrancy
    result.location_fit_score = 0.0
    result.review_recommendation = "reject_location_noise"
```

### Why review_recommendation is NOT a Purchase Recommendation?

**Important Distinction:** The `review_recommendation` field determines queue priority, not purchase suitability.

**Review Recommendation Values:**
- `strong_review`: Top priority for human review (not "strong buy")
- `review`: Recommended for human review (not "recommended purchase")
- `maybe_review`: Low priority review (not "maybe purchase")
- `reject_location_noise`: Remove from review queue due to location (not "never purchase")
- `needs_more_data`: Insufficient data for review (not "not investable")

**Rationale:**
- **Human-in-the-Loop Workflow**: Final purchase decisions are always human-made
- **Queue Prioritization Tool**: Recommendations help users focus limited review time
- **Risk Management**: System explicitly avoids appearing to make purchase recommendations
- **Legal/Ethical Clarity**: Clear that the system is for market observation, not investment advice

**Documentation Requirement:**
- README explicitly states: "Review recommendations are NOT purchase recommendations. They only determine how candidates should be treated in the user review queue."
- CLI help text clarifies: "Generates review priority recommendations, not purchase recommendations"

### Why County Sale Reset Logic Remains Deferred?

**Current Implementation:** Sold events in listing history can reset the current cycle for analysis purposes.

**Not Yet Implemented:** Integration with county recorder data for confirmed ownership transfers.

**Rationale for Deferral:**
- **Milestone Scope**: Milestone 5 focuses on transforming existing Redfin data, not adding new data sources
- **County Integration Complexity**: Requires new parsers, data models, cross-referencing logic
- **Sold Event is Sufficient for v1**: Redfin's "sold" event provides reasonable cycle boundary
- **Future Work Clearly Scoped**: County verification is explicitly planned for Milestone 6+
- **No Over-Engineering**: Implement what's needed now, defer complexity until required

**Future Enhancement Path:**
1. Add county recorder HTML fixture parsing (Milestone 6+)
2. Cross-reference property addresses with title transfer records
3. Confirm or correct sold event dates with county data
4. Detect unreported sales that reset DOM cycles
5. Add "county_verified_sale_reset" flag to DOM metrics

## Consequences

### Positive

1. **Actionable Analysis**: Transforms raw listing events into buyer-side leverage signals
2. **Multiple DOM Perspectives**: Fallback hierarchy ensures best available DOM estimate always provided
3. **Critical Domain Rule Enforcement**: Quiet gatekeeper prevents noise-risk properties from slipping through
4. **Deterministic Scoring**: All calculations fully unit-tested and repeatable
5. **Review Prioritization**: strong_review/review/maybe_review recommendations focus user attention
6. **Warning and Positive Flags**: Quick visual indicators of concerns and opportunities
7. **Exportable Reports**: CSV format enables spreadsheet-based review workflows
8. **Idempotent Recalculation**: Safe to re-run metrics updates as new data arrives
9. **Data Confidence Tracking**: Users know when candidates lack sufficient data for confident evaluation
10. **Scoring Explainability**: Each CandidateScore includes human-readable explanation

### Negative

1. **No County Verification Yet**: Sold event resets rely on Redfin data only (not county-confirmed)
2. **Static Scoring Weights**: Property fit and DOM leverage weights are hardcoded (not user-configurable)
3. **Manual Recalculation**: Users must explicitly run recalc-candidates command
4. **CSV-Only Workflow**: No web UI for reviewing candidates (CSV export only)
5. **No Historical Scoring**: Scoring is point-in-time, not tracked over multiple runs

### Trade-offs

- **Multiple DOM Variants vs. Simplicity**: Accept complexity of 7 DOM types for comprehensive analysis
- **Strict Gatekeeper vs. Flexibility**: Accept that some potentially good properties are rejected due to location noise (user preference is paramount)
- **Deterministic Scoring vs. ML**: Use explicit rules instead of machine learning (transparency and auditability)
- **CSV Export vs. Web UI**: Accept manual CSV workflow to defer UI implementation complexity
- **Comprehensive Reports vs. Storage**: Denormalize data in export for user convenience (some redundancy)

## Critical Domain Rules Enforced

This milestone implements rigorous enforcement of the project's critical domain rules:

1. **Quiet Score is the Gatekeeper**: Enforced via explicit check that sets review_recommendation = "reject_location_noise" when quiet_score < 7.0
2. **Low Vibrancy Cannot Override Poor Quiet**: Explicit test `test_low_vibrancy_cannot_override_poor_quiet` verifies this rule
3. **Target is High Quiet AND Low Vibrancy**: Location fit scoring requires BOTH thresholds (quiet >= 8.0 AND vibrancy <= 2.5 for target fit)
4. **Neutral Language Only**: All metrics, flags, and explanations use neutral terms (listing churn, DOM reset, exposure) not seller-intent language
5. **Review Recommendations ≠ Purchase Recommendations**: Explicitly documented in README, CLI help, and this decision record

## Future Work

When Milestone 6+ implements cross-site enrichment:

1. **County Recorder Integration**: Confirm sold events with title transfer records
2. **Multi-Site DOM Calculation**: Combine listing history from Redfin, Zillow, Realtor.com
3. **User-Configurable Scoring**: Allow users to adjust property fit and DOM leverage weights
4. **Automated Recalculation**: Trigger metric updates on enrichment/import events
5. **Scoring History**: Track scoring changes over time for trend analysis
6. **Web UI for Review**: Replace CSV workflow with interactive candidate review interface
7. **Advanced Filtering**: Allow users to filter analysis report by flags, scores, recommendations
8. **Batch Operations**: Mark multiple candidates as save/reject in single operation

## Related Decisions

- **Decision 001**: Human-in-the-Loop Review Queue (defines candidate → review → watchlist workflow)
- **Decision 003**: Redfin Detail Parser and Candidate Enrichment (provides listing history data)

## Testing

Milestone 5 includes comprehensive test coverage:

- **Event Normalization Tests** (12 tests): Verify all event types map correctly to normalized categories
- **Effective DOM Metrics Tests** (15 tests): Cover normal history, listing churn, sale/rent alternation, sold resets, fallback behavior
- **Scoring Tests** (31 tests): Quiet gatekeeper (including critical low-vibrancy-cannot-override-poor-quiet rule), property fit, DOM leverage, data confidence, warning flags, positive flags, review recommendations, explanations
- **Total**: 188 tests passing (58 new comprehensive v1 tests, 130 existing tests updated/passing)
- **Coverage**: 97% for scoring.py, 92% for effective_dom.py

## CLI Commands

```bash
# Recalculate Effective DOM and scoring metrics for all candidates
marketsentry recalc-candidates

# Export comprehensive candidate analysis report
marketsentry export-analysis-report

# Specify output path
marketsentry export-analysis-report --output data/exports/my_analysis.csv

# Export as Markdown
marketsentry export-analysis-report --markdown
```

## Example Workflow

```bash
# 1. Initialize database
marketsentry init-database

# 2. Import Redfin URLs (Milestone 3)
marketsentry import-redfin-urls --file data/imports/redfin_urls.csv

# 3. Enrich with detail data (Milestone 4)
marketsentry enrich-redfin-details --dir data/detail_pages/

# 4. Recalculate Effective DOM metrics (Milestone 5)
marketsentry recalc-candidates

# 5. Export analysis report (Milestone 5)
marketsentry export-analysis-report

# 6. Open CSV in Excel, sort by review_recommendation and overall_review_score
# 7. Focus on strong_review candidates first
# 8. Review warning_flags and positive_flags
# 9. Check effective_dom_delta for hidden market exposure
# 10. Set user_decision column (save/reject/maybe/hold_for_more_data)

# 11. Import review decisions
marketsentry import-review --file data/exports/candidate_analysis_20260505_120000.csv

# 12. View promoted watchlist
marketsentry list-watched
```

## Files Modified/Created

**New Modules:**
- `src/marketsentry/candidate_recalc.py` (47 lines, 0% coverage - CLI-tested)
- `src/marketsentry/candidate_report.py` (93 lines, 0% coverage - CLI-tested)

**Rewritten Modules:**
- `src/marketsentry/effective_dom.py` (195 lines, 92% coverage - complete v1 rewrite)
- `src/marketsentry/scoring.py` (215 lines, 97% coverage - complete v1 rewrite)

**Modified Modules:**
- `src/marketsentry/models.py`: Made CandidateProperty fields optional with defaults, added price/source_mls to ListingEvent
- `src/marketsentry/cli.py`: Added 2 new commands (recalc-candidates, export-analysis-report)

**New Tests:**
- `tests/test_effective_dom_v1.py` (27 comprehensive v1 tests, all passing)
- `tests/test_scoring_v1.py` (31 comprehensive v1 tests, all passing)

**Modified Tests:**
- `tests/test_effective_dom.py`: Updated 2 tests for v1 behavior
- `tests/test_scoring.py`: Updated 8 tests for v1 function signatures

---

**Approved by:** Claude Sonnet 4.5
**Implementation Date:** 2026-05-05
**Test Status:** 188/188 tests passing
