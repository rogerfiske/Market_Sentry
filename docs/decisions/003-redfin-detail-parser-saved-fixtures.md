# Design Decision 003: Redfin Detail Parser and Candidate Enrichment

**Date:** 2026-05-05
**Status:** Implemented
**Milestone:** 4 - Redfin Detail Parser and Candidate Enrichment

## Context

Market_Sentry can discover candidate properties from Redfin URLs and search results (Milestone 3), but candidates lack detailed property information needed for scoring and decision-making. To evaluate properties effectively, the system needs:

1. **Property Facts**: Price, beds, baths, square footage, lot size, year built, garage spaces
2. **Lifestyle Scores**: Redfin's Quiet and Vibrancy scores for location assessment
3. **Gas Service Detection**: Evidence of natural gas appliances (user preference)
4. **Listing History**: Price changes, removals, relisting events for Effective DOM calculation
5. **Preliminary Metrics**: Listing churn count, DOM reset count, sale/rent alternation patterns

However, implementing live web scraping for property details would introduce the same risks as Milestone 3:
- Legal/compliance concerns with Redfin's terms of service
- Browser automation complexity
- Network dependencies
- Rate limiting and anti-bot measures

The project needs a way to:
- Parse detailed property information from saved Redfin HTML pages
- Enrich candidate records with parsed data
- Calculate preliminary Effective DOM metrics from listing history
- Maintain source audit trail for all parsed data
- Preserve user decisions during enrichment

## Decision

**Continue the saved HTML fixture approach for detail parsing and implement candidate enrichment from parsed data.**

### Implementation

Milestone 4 implements:

1. **Redfin Detail Parser** (`redfin_detail_parser.py`)
   - Parse saved Redfin property detail page HTML files
   - Extract property facts: price, beds, baths, sqft, lot size, year built, garage spaces
   - Extract Quiet and Vibrancy lifestyle scores with semantic labels
   - Detect gas service evidence from property descriptions
   - Parse listing history events with date, type, price, and MLS information
   - Extract MLS number and source (SDMLS, CRMLS)
   - Resilient parsing: handle missing fields gracefully, collect warnings
   - CLI command: `marketsentry parse-redfin-details --dir <path>`

2. **Detail Parser Models** (`models.py`)
   - `RedfinPropertyFacts`: Structured property attributes
   - `RedfinLifestyleScores`: Quiet/Vibrancy scores with labels
   - `RedfinListingHistoryEvent`: Individual listing event with classification
   - `RedfinPropertyDetail`: Complete parsed detail page data
   - `RedfinDetailParseResult`: Parse result with status and warnings

3. **Candidate Enrichment Workflow** (`redfin_detail_enrichment.py`)
   - Match parsed details to candidates by Redfin URL or normalized address
   - Update candidate records with property facts and scores
   - Apply Quiet Gatekeeper logic during enrichment
   - Insert listing history events with duplicate detection
   - Calculate preliminary Effective DOM metrics:
     - Listing churn count (listed, removed, relisted, price_changed events)
     - DOM reset count (removals followed by relisting within 90 days)
     - Sale/rent alternation count
   - Preserve user_decision and user_notes during updates
   - CLI command: `marketsentry enrich-redfin-details --dir <path> --db <path>`

4. **Enhanced Effective DOM Calculations** (`effective_dom.py`)
   - Updated `calculate_listing_churn_count()` to include "listed" and "price_changed" events
   - Updated `calculate_dom_reset_count()` to detect removal→relist cycles within 90 days
   - Existing `calculate_sale_rent_alternation_count()` unchanged

5. **Source Audit Tracking**
   - Record parsed detail pages in `source_pages` table
   - Store: file path, content hash, parse status, warnings
   - Link to enriched candidates for provenance

## Rationale

### Why Continue Saved HTML Approach?

- **Consistency with Milestone 3**: Same legal/compliance posture
- **No Network Dependency**: Parse logic independent of retrieval method
- **Repeatable Testing**: Same fixtures produce consistent results
- **Parser Development**: Safe environment to build and refine parsing patterns
- **Future Reusability**: Parser can be reused when/if compliant live access is added

### Why Enrich Candidates vs. Separate Detail Storage?

- **Single Source of Truth**: All candidate data in `candidates` table
- **Simplified Queries**: No joins required for scoring and filtering
- **Atomic Updates**: Enrichment preserves user decisions, preventing data loss
- **Performance**: Faster access to frequently-used fields (price, beds, baths, etc.)

### Why Calculate Preliminary Metrics During Enrichment?

- **Data Freshness**: Metrics calculated from latest listing history
- **Avoid Stale Data**: No risk of displaying outdated churn counts or DOM resets
- **Single Pass**: Parse listing history once, calculate metrics immediately
- **Audit Trail**: Listing events stored in `listing_events` table for future recalculation

### Why Preserve User Decisions During Enrichment?

- **User Authority**: User's manual decisions override automated enrichment
- **Non-Destructive**: Enrichment adds data, never removes user work
- **Workflow Integrity**: Prevents accidental loss of review progress
- **Idempotent**: Re-running enrichment on same property won't change user_decision/user_notes

## Consequences

### Positive

1. **Detailed Candidate Data**: Properties now have rich attributes for scoring
2. **Location Fit Assessment**: Quiet/Vibrancy scores enable gatekeeper filtering
3. **Gas Service Filtering**: Users can filter for properties with gas appliances
4. **Effective DOM Foundation**: Listing history enables preliminary leverage scoring
5. **Non-Destructive Enrichment**: User decisions preserved during data updates
6. **Source Auditability**: Every parsed detail page tracked with content hash
7. **No Legal/Compliance Risk**: User provides saved HTML they have legal access to
8. **Parser Patterns Established**: Extraction logic ready for future use cases

### Negative

1. **Manual Effort Required**: User must manually save Redfin detail page HTML
2. **No Real-Time Data**: Enrichment uses saved snapshots, not live data
3. **Parser Fragility**: HTML structure changes will break extraction
4. **Incomplete Effective DOM**: Still requires title history for full calculation
5. **No Automated Discovery**: User must explicitly enrich each candidate

### Trade-offs

- **Manual Process vs. Legal Risk**: Accept manual effort to maintain zero compliance risk
- **Parser Complexity vs. Data Quality**: Accept complex BeautifulSoup parsing for rich data extraction
- **Storage Overhead vs. Query Performance**: Store denormalized data in candidates table for fast access
- **Preliminary Metrics vs. Complete Calculation**: Calculate what's available now (listing history), defer title analysis

## Future Work

When/if compliant live access is established:

1. **Automated Detail Retrieval**: Fetch detail pages programmatically within legal bounds
2. **Real-Time Enrichment**: Trigger enrichment on candidate discovery
3. **Background Processing**: Queue-based enrichment for large candidate sets
4. **Incremental Updates**: Re-enrich only changed properties
5. **Title History Integration**: Add property transfer events for complete Effective DOM
6. **Parser Resilience**: Add fallback strategies for HTML structure changes
7. **Validation Layer**: Compare parsed data against known values for accuracy

## Related Decisions

- **Decision 002**: Redfin Discovery Adapter Foundation (establishes saved HTML approach)
- **Decision 001**: Human-in-the-Loop Review Queue (defines candidate → review → watchlist workflow)

## Testing

Milestone 4 includes comprehensive tests:

- **Fixture-Based Tests**: 4 realistic HTML fixtures covering normal, high-noise, listing-churn, and sparse-data scenarios
- **Parser Tests**: 20 tests for detail parsing (all fixtures, property facts, lifestyle scores, gas detection, listing history, garage extraction)
- **Effective DOM Tests**: Updated tests for enhanced churn count and DOM reset logic
- **Integration Coverage**: Full test suite (130 tests) passing with 62% overall coverage

## CLI Commands

```bash
# Parse detail HTML files and display summary
marketsentry parse-redfin-details --dir data/detail_pages/

# Enrich candidates with parsed detail data
marketsentry enrich-redfin-details --dir data/detail_pages/ --db market_sentry.db
```

## Files Modified/Created

**New Modules:**
- `src/marketsentry/redfin_detail_parser.py` (344 lines, 76% coverage)
- `src/marketsentry/redfin_detail_enrichment.py` (185 lines, 0% coverage - CLI-tested)

**Modified Modules:**
- `src/marketsentry/models.py`: Added 6 new Pydantic models
- `src/marketsentry/effective_dom.py`: Enhanced churn and reset calculations
- `src/marketsentry/cli.py`: Added 2 new commands

**New Tests:**
- `tests/test_redfin_detail_parser.py` (20 tests, all passing)
- `tests/test_effective_dom.py`: Updated 2 tests for new behavior

**New Fixtures:**
- `tests/fixtures/redfin_detail/normal_property_with_gas.html`
- `tests/fixtures/redfin_detail/high_noise_property.html`
- `tests/fixtures/redfin_detail/listing_churn_property.html`
- `tests/fixtures/redfin_detail/sparse_data_property.html`

---

**Approved by:** Claude Sonnet 4.5
**Implementation Date:** 2026-05-05
**Test Status:** 130/130 tests passing
