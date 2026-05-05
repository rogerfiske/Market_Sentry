# Decision 008: Effective DOM v2 County-Verified Reset and Churn Index

**Date:** 2026-05-05

**Status:** Accepted

**Context:** Milestone 9 - Effective DOM v2 County-Verified Reset Integration

## Decision

Implement Effective DOM v2 with county-confirmed ownership transfer as reset boundary while preserving recent churn metrics separately for comprehensive property analysis. County-verified transfers reset Effective DOM for the current ownership cycle, but churn metrics remain available as a separate analytical signal.

## Rationale

### Why County-Confirmed Transfer as Reset Boundary

County-confirmed ownership transfer provides official public-record verification that a property has changed hands, establishing a logical reset point for market exposure measurement:

1. **Official Verification**: County Recorder deed records are public, official documents that confirm actual ownership transfer events. Unlike MLS "sold" status (which can be inaccurate or delayed), county deeds provide authoritative evidence of ownership change.

2. **Ownership Cycle Alignment**: Effective DOM measures property-level market exposure. When ownership changes, the new owner's listing exposure begins fresh. The previous owner's exposure pattern is no longer directly relevant to the current listing cycle.

3. **Conservative Reset Logic**: Only confirmed ownership transfer documents (Grant Deed, Quitclaim Deed, Trustee Deed, Warranty Deed) trigger reset. This avoids false positives from financing documents or other non-transfer county records.

4. **Inside-Window Requirement**: Transfer must occur inside the listing history window (not before first event, not after latest event) to be applied as a reset. This prevents inappropriate historical resets or future-dated resets.

5. **Preserves Pre-Reset Data**: Pre-reset exposure metrics remain reportable even when reset is applied, ensuring full property timeline visibility for human review.

### Why Non-Transfer Documents Do NOT Reset Effective DOM

The system explicitly excludes non-transfer county records from Effective DOM reset logic:

**Excluded Document Types:**
- **Deed of Trust**: Financing/loan document, not ownership transfer
- **Reconveyance**: Loan payoff/release document, not ownership transfer
- **Lien**: Encumbrance placed on property, not ownership transfer
- **Assessment**: County valuation record, not ownership transfer
- **Permit**: Building/construction authorization, not ownership transfer
- **Tax Record**: Tax payment/delinquency record, not ownership transfer

**Rationale:**

1. **No Ownership Change**: These documents do not indicate a change in property ownership. The same owner remains, so their listing exposure cycle continues uninterrupted.

2. **Prevents False Positives**: Including financing or administrative documents as reset events would incorrectly fragment a continuous ownership exposure period.

3. **Conservative Classification**: When uncertain, the system defaults to NOT resetting. This preserves the full exposure timeline and avoids underestimating market exposure.

4. **Common Loan Events**: Refinancing (new Deed of Trust) or loan payoff (Reconveyance) are common during an active listing period and do not represent ownership transfer.

### Why Churn Remains Separate from Effective DOM

**CRITICAL DESIGN DECISION:** Churn Index is computed from ALL events within the 3-year lookback window regardless of county reset. County-confirmed ownership transfer resets Effective DOM but does NOT erase or zero churn metrics.

**Rationale:**

1. **Different Time Horizons**: Effective DOM measures current ownership-cycle exposure (resets with ownership change). Churn Index measures recent 2-3 year property/listing instability (does NOT reset with ownership change). These are fundamentally different analytical questions.

2. **Analytical Separation Enables Four Scenarios**:
   - **Low Effective DOM + Low Churn**: Stable property, new ownership, clean history (ideal scenario)
   - **Low Effective DOM + High Churn**: New ownership, but property had unstable listing history before sale (buyer intelligence)
   - **High Effective DOM + Low Churn**: Long market exposure, but stable listing behavior
   - **High Effective DOM + High Churn**: Long exposure AND unstable listing behavior (highest risk signal)

3. **Buyer Intelligence**: A property may have a clean Effective DOM v2 (new owner, recent county-confirmed sale) but still exhibit high churn (multiple listing cycles, DOM resets, price changes in the prior 2-3 years). This combination is valuable buyer intelligence that would be lost if churn metrics were erased by county reset.

4. **Property-Level Signal vs Owner-Level Signal**: Churn Index is a property-level instability signal. It does not reset when ownership changes because the property's listing history pattern remains relevant regardless of current ownership.

5. **Future Evaluation**: Churn Index may or may not prove predictive of future buyer experience. Preserving churn metrics separately allows for evaluation and refinement over time without coupling to Effective DOM reset logic.

6. **Prevents Data Loss**: Zeroing churn metrics on ownership transfer would discard valuable analytical information. The `churn_preserved_after_transfer` field is always `True` to guarantee this separation.

### Why Churn Index May or May Not Prove Predictive

Churn Index v1 uses a deterministic weighted formula but remains experimental:

**Formula:** weighted_churn = (listing_churn_count × 1.0) + (dom_reset_count × 1.5) + (sale_rent_alternation_count × 2.0) + (price_change_count × 0.5)

**Uncertainties:**

1. **Unproven Predictive Value**: It is unknown whether high churn in the past 2-3 years correlates with future buyer satisfaction or property issues. Churn may reflect normal market cycles, seller life changes, or genuine property problems.

2. **Weight Calibration**: The current weights (1.0, 1.5, 2.0, 0.5) are initial estimates. Actual predictive weights may differ significantly.

3. **Lookback Window**: 3-year default may be too long or too short depending on market conditions and property characteristics.

4. **Event Type Classification**: Whether price changes should be weighted 0.5 or differently is unproven.

5. **Normalization Scale**: 0-10 scale with 20 weighted points = 10.0 is arbitrary. Alternative normalizations may be more interpretable.

**Why Preserve Despite Uncertainty:**

Churn Index is included as an experimental analytical signal. It provides a composite view of recent property/listing instability that may prove useful for buyers. By preserving churn separately from Effective DOM, the system enables future evaluation without coupling to ownership-transfer reset logic. If churn proves non-predictive, it can be deprecated without affecting Effective DOM v2 calculation.

### Why Reports Are Analytical Aids, Not Purchase Recommendations

All Market_Sentry reports, including Effective DOM v2 comparison reports, are analytical tools designed to support human decision-making:

1. **Data Quality Indicators**: Effective DOM delta, churn index, and discrepancy flags highlight properties where data patterns suggest closer inspection or additional verification.

2. **No Automated Scoring**: The system does not generate "buy/don't buy" recommendations or property rankings. It calculates metrics and presents them for human interpretation.

3. **Human-in-the-Loop**: The review workflow requires user decisions before watchlist promotion. Reports inform those decisions but do not make them.

4. **Neutral Language**: The system uses neutral terms (listing churn, DOM reset pattern, county-confirmed transfer) and avoids inferring seller intent (no "spoofing," "deception," "fraud," "bad actor" language).

5. **Context-Dependent Interpretation**: A high Effective DOM or high Churn Index may be explainable (e.g., seasonal market, seller life changes, property improvements) or concerning (e.g., undisclosed issues). Only human review with full context can make that determination.

6. **Liability and Responsibility**: Buyers are responsible for their own due diligence, inspections, and purchase decisions. Market_Sentry provides observation and data quality tools only.

## Implementation Details

### Effective DOM v2 Calculation Logic

1. **No County Transfer (Scenario A)**: v2 = v1, county_reset_applied = false
2. **Transfer Before All Events (Scenario B)**: v2 = v1, county_reset_applied = false (no reset needed)
3. **Transfer Inside Window (Scenario C)**: v2 = post-reset exposure only, county_reset_applied = true, pre-reset metrics remain reportable
4. **Transfer After Latest Event (Scenario D)**: v2 = v1, county_reset_applied = false (no historical reset)
5. **Non-Transfer Record (Scenario E)**: v2 = v1, county_reset_applied = false (Deed of Trust, Reconveyance, Lien, Permit, Assessment do NOT reset)

### Churn Index v1 Calculation

**Date-Filtered Approach:**
- Filters events to 3-year lookback window from analysis date
- Counts listing churn, DOM resets, sale/rent alternations, price changes within window
- Applies weighted formula and normalizes to 0-10 scale

**Count-Based Fallback:**
- Uses existing all-time churn counts if event dates are unavailable
- Less precise but provides initial signal when date filtering is not possible

**Preservation Guarantee:**
- `churn_preserved_after_transfer` is always `True` in all reports
- Churn metrics are NEVER zeroed or modified when county_reset_applied is true
- Churn Index is computed from ALL events within lookback window (pre and post reset)

### Report-Only Workflow

Milestone 9 implements Effective DOM v2 as a report-only operation:

- `recalc_effective_dom_v2()` computes v2 metrics but does not update database
- `export_effective_dom_v2_report()` generates CSV with v1/v2 comparison
- Database schema is not modified (no new columns added to watched_properties)
- Future milestone can add v2 schema migration if report proves valuable

This conservative approach allows evaluation of v2 metrics without committing to schema changes or workflow integration.

## Consequences

### Positive

1. **Official Reset Verification**: County-confirmed ownership transfer provides authoritative reset boundary for Effective DOM.

2. **Comprehensive Property Analysis**: Separating Effective DOM (ownership-cycle exposure) from Churn Index (property-level instability) enables four analytical scenarios not possible with single metric.

3. **No Data Loss**: Churn metrics are never erased by county reset, ensuring full property timeline remains available.

4. **Conservative Classification**: Non-transfer documents explicitly excluded from reset logic reduces false positives.

5. **Experimental Signal Preserved**: Churn Index included as experimental metric without coupling to Effective DOM, enabling future evaluation/refinement.

6. **Report-Only Safety**: Non-destructive workflow allows v2 evaluation without schema changes or workflow disruption.

7. **Neutral Language**: System avoids inferring seller intent, maintaining objective analytical stance.

### Negative

1. **Churn Predictive Value Unknown**: Churn Index may not correlate with future buyer satisfaction or property issues. May prove to be noise.

2. **Weight Calibration Unverified**: Current churn weights (1.0, 1.5, 2.0, 0.5) are estimates. Actual predictive weights unknown.

3. **Additional Complexity**: v1/v2 comparison adds cognitive load for users interpreting reports.

4. **No Database Persistence**: v2 metrics are report-only. If frequently used, users must recompute on each export.

5. **County Data Dependency**: v2 requires county records. Properties without county data fall back to v1 only.

### Mitigations

- **Churn Evaluation**: Preserve churn as experimental signal. Deprecate if non-predictive. Separation from Effective DOM allows independent evaluation.
- **Weight Refinement**: Churn weights can be adjusted in future milestone if user feedback or data analysis suggests improvements.
- **Documentation**: README and reports clearly explain v1/v2 differences and analytical scenarios.
- **Report-Only**: Users evaluate v2 without workflow disruption. Future milestone can add schema persistence if valuable.
- **Fallback to v1**: Properties without county data use v1 metrics (graceful degradation).

## Future Enhancements

1. **Schema Integration**: Add effective_dom_v2, county_reset_applied, recent_churn_index columns to watched_properties if v2 proves valuable.

2. **Churn Weight Calibration**: Refine churn weights based on user feedback or data analysis.

3. **Lookback Window Tuning**: Make churn lookback window configurable (1 year, 2 years, 3 years, 5 years).

4. **Multi-Transfer Handling**: Extend v2 logic to handle multiple ownership transfers within listing window (currently uses most recent).

5. **Confidence Scoring**: Add county reset confidence levels based on document quality, sale price consistency, grantor/grantee matching.

6. **Visual Timeline**: Generate property exposure timeline visualization showing pre-reset, reset event, and post-reset periods.

## Related Documents

- [PRD.md](../../PRD.md) - MVP 9: Effective DOM v2 section
- [Architecture.md](../../Architecture.md) - Effective DOM v2 design
- [Decision 007: County Verification Foundation](007-county-verification-foundation.md) - Prerequisite milestone
- [Market_Sentry_Claude_Prompt_009](../prompts/Market_Sentry_Claude_Prompt_009_Effective_DOM_v2_County_Reset.md) - Implementation prompt

## Conclusion

Effective DOM v2 with county-verified reset boundaries provides authoritative ownership-cycle exposure measurement while preserving separate churn metrics for comprehensive property analysis. The separation enables four analytical scenarios (Low/High Effective DOM × Low/High Churn) that provide valuable buyer intelligence. Churn Index remains experimental but is preserved separately to allow future evaluation without coupling to Effective DOM reset logic. All reports are analytical aids for human decision-making, not automated purchase recommendations.
