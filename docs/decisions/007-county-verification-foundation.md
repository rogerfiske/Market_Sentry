# Decision 007: County Recorder and Assessor Verification Foundation

**Date:** 2026-05-05

**Status:** Accepted

**Context:** Milestone 8 - County Recorder and Assessor Verification Foundation

## Decision

Implement county record verification foundation using saved/static fixtures and manual CSV imports only. County records provide official/public-record-style verification data to support APN confirmation, ownership transfer detection, and county-verified Effective DOM reset logic.

**CRITICAL:** Preserve the distinction between Effective DOM and Churn Index. County-confirmed transfers may reset Effective DOM, but churn metrics remain available separately.

## Rationale

### Why County Verification After Watchlist Monitoring

County verification (originally planned earlier) is implemented after watchlist monitoring snapshots because:

1. **Foundation Prerequisites**: Watchlist monitoring established the historical tracking foundation needed for comparing listing-site events with county-recorded events.

2. **No Live Access Delay**: County Recorder/Assessor websites often require manual navigation or have restricted access. Implementing with saved fixtures first validates the data model and matching logic before adding live access.

3. **Progressive Enhancement**: County verification enhances existing watchlist data without requiring it to function. Properties can be monitored without county records, and county verification adds confirmation when available.

4. **Data Quality Validation**: County records serve as a "ground truth" check against listing-site data, useful after cross-site enrichment is established.

### Why Manual CSV and Saved Fixtures

County verification uses manual CSV import and saved HTML fixtures (NO live scraping) because:

1. **Access Restrictions**: County Recorder/Assessor sites often have bot protection, CAPTCHAs, or require manual navigation through search forms.

2. **Data Model Validation**: Manual import validates the county data model, matching logic, and verification workflow before implementing automated retrieval.

3. **Compliance**: Manual retrieval respects county website terms while still enabling verification functionality.

4. **Future Flexibility**: Foundation supports future authorized API access or licensed data feeds when available.

### County Record Types and Transfer Classification

County records are classified into ownership-transfer and non-transfer types:

**Ownership Transfer Records** (support Effective DOM reset):
- **Grant Deed**: Standard ownership transfer, most common residential sale document
- **Quitclaim Deed**: Ownership transfer without warranty of title
- **Trustee Deed**: Foreclosure or trust sale transfer
- **Warranty Deed**: Ownership transfer with title guarantee

**NOT Ownership Transfer** (do NOT support Effective DOM reset):
- **Deed of Trust**: Loan/financing document, secures debt against property (NOT a sale)
- **Reconveyance**: Loan payoff/release document (NOT a sale)
- **Lien**: Encumbrance placed on property (NOT a sale)
- **Assessment**: County valuation record (NOT a sale)
- **Permit**: Building/construction authorization (NOT a sale)
- **Tax Record**: Tax payment or delinquency record (NOT a sale)

**Rationale for Conservative Classification:**

The system uses conservative logic when classifying ownership transfers. Only documents that clearly indicate an ownership change are classified as transfer records. Financing documents (Deed of Trust), loan releases (Reconveyance), and liens are explicitly excluded to avoid false positives that could incorrectly reset Effective DOM.

### Effective DOM Reset vs Churn Preservation

**CRITICAL DESIGN DECISION:**

County-confirmed ownership transfer may reset Effective DOM for the current ownership cycle, but it does NOT erase or zero out recent churn metrics.

**Why This Distinction Matters:**

1. **Different Time Horizons**: Effective DOM measures current ownership-cycle exposure. Churn Index measures recent 2-3 year property/listing instability.

2. **Analytical Separation**: A property may have a clean Effective DOM (new owner, recent sale) but still exhibit high churn (multiple listing cycles, removals, price changes in the prior 2-3 years).

3. **Buyer Intelligence**: Both signals are useful:
   - **Low Effective DOM + Low Churn**: Stable property, new ownership, clean history
   - **Low Effective DOM + High Churn**: New ownership, but property had unstable listing history before sale
   - **High Effective DOM + Low Churn**: Long market exposure, but stable listing behavior
   - **High Effective DOM + High Churn**: Long exposure AND unstable listing behavior

4. **Future Evaluation**: Churn may or may not prove useful as a buyer signal. Preserving it allows for evaluation and refinement.

**Implementation:**

- County transfer records set `county_reset_supported = True`
- `county_reset_supported` signals that Effective DOM reset is justified
- Listing churn metrics (`listing_churn_count`, `dom_reset_count`, `sale_rent_alternation_count`) are NOT modified
- Churn Index is calculated and reported alongside Effective DOM
- `churn_preserved_after_transfer` field is always `True` in reports

### Churn Index Placeholder

Milestone 8 implements a simple Churn Index placeholder:

**Formula:** Weighted sum normalized to 0-10 scale
```
weighted_churn = (listing_churn_count * 1.0) + (dom_reset_count * 1.5) + (sale_rent_alternation_count * 2.0)
churn_index = min(10.0, (weighted_churn / 20.0) * 10.0)
```

**Weights Rationale:**
- Listing churn (1.0): Baseline instability
- DOM resets (1.5): More significant than simple churn
- Sale/rent alternation (2.0): Strongest signal of property/listing instability

**Limitations:**
- Not date-bounded to a specific lookback window
- Uses all-time churn counts from existing fields
- Placeholder pending date-bounded Churn Index v1 in future milestone

**Why Placeholder is Acceptable:**

The current churn metrics (`listing_churn_count`, `dom_reset_count`, `sale_rent_alternation_count`) are already calculated and stored. The placeholder provides a quick composite score for initial evaluation. A refined, date-bounded Churn Index v1 is deferred to a later milestone when event-date filtering is more robust.

### Matching Logic

County records are matched to properties/candidates using a priority hierarchy:

1. **property_id**: Direct match (highest confidence)
2. **candidate_id**: Direct match (high confidence)
3. **APN**: Normalized match (medium-high confidence)
4. **normalized_address**: Fallback match (medium confidence)

**Unmatched Records**: County records that cannot be matched are still inserted into the database with `property_id = NULL` and `candidate_id = NULL`. This preserves the data for future manual review or improved matching logic.

### County Verification Report

The county verification report includes 35 columns:

**Property Identification**: property_id, candidate_id, address, city, zip, apn, redfin_url

**Current Metrics**: current_price, effective_dom, displayed_dom

**Churn Metrics**: listing_churn_count, dom_reset_count, sale_rent_alternation_count

**Churn Index**: recent_churn_index, recent_churn_lookback_years, recent_churn_event_count, recent_dom_reset_count, recent_sale_rent_alternation_count, churn_preserved_after_transfer

**County Verification**: county_records_seen, county_transfer_found, county_transfer_date, county_transfer_record_type, county_transfer_document_number, county_transfer_confidence, county_reset_supported

**Source Presence**: assessor_seen, recorder_seen, tax_collector_seen, permit_seen

**Additional Data**: assessed_value, latest_permit_type, latest_permit_status, verification_notes, user_notes

**Purpose:** The report shows both Effective DOM reset support and churn metrics side-by-side, enabling comprehensive analysis without hiding any signals.

## Consequences

### Positive

1. **Official Verification**: County records provide official/public-record confirmation of ownership transfers and property data.

2. **Effective DOM Reset Foundation**: Verification API enables future Effective DOM v2 integration with county-confirmed reset logic.

3. **Churn Preservation**: Churn metrics remain reportable even when county_reset_supported is true, ensuring no data loss.

4. **Flexible Matching**: Multi-tier matching logic (property_id > candidate_id > APN > address) handles various data scenarios.

5. **No Live Access Required**: Manual CSV and saved fixtures enable county verification without implementing live scraping.

6. **Conservative Classification**: Conservative ownership-transfer logic reduces false positives that could incorrectly reset Effective DOM.

7. **Future-Ready**: Foundation supports future authorized API access or licensed data feeds.

### Negative

1. **Manual Data Entry**: Users must manually obtain county records via CSV or saved HTML pages.

2. **Incomplete Coverage**: Not all properties will have county records (requires manual effort).

3. **Placeholder Churn Index**: Current Churn Index is not date-bounded, pending future enhancement.

4. **No Automated County Access**: System does not fetch county data automatically.

### Mitigations

- **Manual Entry**: CLI commands make CSV import straightforward; users can batch-process multiple properties.
- **Incomplete Coverage**: County verification is optional enhancement; properties function without it.
- **Placeholder Churn Index**: Simple weighted sum provides initial signal; date-bounded v1 is planned.
- **No Automation**: Future milestone can add authorized county API access when available.

## Implementation Notes

### Files Created

- **src/marketsentry/county_parser.py**: Parses saved county HTML fixtures
- **src/marketsentry/county_verification.py**: Transfer classification and verification logic
- **src/marketsentry/county_import.py**: CSV import and matching logic
- **src/marketsentry/county_verification_report.py**: Report generation with Churn Index

### Schema Changes

- **county_record_observations** table: Stores all county records (matched and unmatched)
- **Indexes**: property_id, candidate_id, normalized_apn, normalized_address, record_date, normalized_record_type, document_number

### Models Added

- CountyRecordImportRow
- CountyRecordObservation
- CountyRecordParseResult
- CountyTransferEvent
- CountyVerificationResult
- CountyRecordImportResult
- CountyVerificationReportRow

### CLI Commands

- `import-county-records --file <csv>`: Import county records from CSV
- `parse-county-fixtures --source <type> --dir <directory>`: Parse saved county HTML fixtures
- `verify-county-records`: Verify county records for all watched properties
- `export-county-verification-report`: Export county verification report to CSV

### Test Coverage

- 30 new county tests, all passing
- Total: 298 tests, 100% pass rate
- Coverage: 66% overall

### Test Fixtures

- Assessor: property_001.html, property_002_sparse.html
- Recorder: grant_deed_001.html, deed_of_trust_001.html, no_transfer_found.html
- Tax Collector: property_001.html
- Permits: building_permit_001.html

## Future Enhancements

1. **Date-Bounded Churn Index v1**: Refine Churn Index to filter events to a specific 2-3 year lookback window based on event dates.

2. **Effective DOM v2 Integration**: Integrate `county_reset_supported` flag into Effective DOM calculation engine.

3. **Authorized County API Access**: Add live county data retrieval via authorized APIs or licensed data feeds when available.

4. **Multi-County Support**: Extend parsers to handle additional county formats beyond Riverside County.

5. **APN Auto-Discovery**: Extract APN from Redfin detail pages to improve county matching.

6. **Transfer Confidence Scoring**: Refine confidence levels based on document quality, grantor/grantee matching, and sale price consistency.

## Related Documents

- [PRD.md](../../PRD.md) - MVP 9: County verification section
- [Architecture.md](../../Architecture.md) - County verification design
- [Decision 006: Watchlist Monitoring Snapshots](006-watchlist-monitoring-snapshots.md) - Prerequisite milestone
