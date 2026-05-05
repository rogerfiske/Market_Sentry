# Design Decision 002: Redfin Discovery Adapter Foundation

**Date:** 2026-05-05
**Status:** Implemented
**Milestone:** 3 - Redfin Discovery Adapter Foundation

## Context

Market_Sentry needs to discover candidate properties from Redfin search results for the Temecula/Murrieta market. However, implementing live web scraping as the first approach would:

1. Introduce compliance and legal risks before validating the core workflow
2. Add complexity with browser automation (Playwright/Selenium)
3. Potentially violate Redfin's terms of service or robots.txt
4. Create dependencies on external services before the internal pipeline is proven

The project needs a way to:
- Validate the candidate discovery → review → watchlist workflow
- Test the database schema and business logic
- Establish parsing patterns for Redfin data
- Build auditable source tracking from day one

## Decision

**Defer live scraping and implement a foundation using manual URL import and saved HTML fixture parsing.**

### Implementation

Milestone 3 implements:

1. **Manual Redfin URL Import**
   - CSV file format: `data/imports/redfin_urls.csv`
   - Required column: `redfin_url`
   - Optional columns: `address`, `city`, `zip`, `price`, `beds`, `baths`, `sqft`, `notes`
   - URL validation and normalization
   - Extraction of address data from URL when not provided
   - CLI command: `marketsentry import-redfin-urls --file <path>`

2. **Saved HTML Fixture Parsing**
   - Parse static/saved Redfin search result HTML files
   - Extract property URLs from anchor tags
   - Parse available summary data where feasible
   - No network calls, no live scraping
   - CLI command: `marketsentry parse-redfin-fixtures --dir <path>`

3. **Source Page Audit Tracking**
   - Record provenance in `source_pages` table
   - Store: source file path, retrieval method, content hash, parse status
   - Enable future auditability and debugging

4. **Parser Foundation**
   - URL validation: `is_redfin_url()`
   - URL normalization: `normalize_redfin_url()` (removes tracking params, ensures https/www)
   - Data extraction helpers: `extract_address_from_redfin_url()`, `extract_city_from_redfin_url()`, `extract_zip_from_redfin_url()`
   - Resilient to missing fields (fail gracefully, not fatally)

## Rationale

### Why Manual URL Import?

- **User Control:** User manually curates candidate URLs from legitimate browsing
- **Zero Compliance Risk:** User provides data they have legal access to
- **Immediate Validation:** Tests the candidate insertion and review workflow without complexity
- **Realistic Data:** Uses real Redfin property URLs

### Why Saved HTML Fixtures?

- **No Network Dependency:** Tests parsing logic without external services
- **Repeatable:** Same fixtures produce consistent test results
- **Parser Development:** Allows building and testing parsers safely
- **Future Compatibility:** Parser patterns can be reused when/if compliant live access is added

### Why Defer Live Scraping?

- **Compliance First:** Need to research Redfin's terms, robots.txt, and legal requirements
- **Technical Simplicity:** Manual import validates the core workflow faster
- **Risk Mitigation:** Don't build on a foundation that might be prohibited
- **Separation of Concerns:** Parsing logic should be independent of retrieval method

## Consequences

### Positive

1. **Compliant by Design:** No risk of violating terms of service
2. **Testable:** Parser logic can be unit tested with fixtures
3. **Auditable:** Source tracking built from the start
4. **Flexible:** Can later add authorized API access, RSS feeds, or compliant scraping
5. **User in Control:** User provides the data, system processes it

### Negative

1. **Manual Effort:** User must initially collect URLs or save HTML manually
2. **Limited Scale:** Cannot automatically monitor all active listings
3. **Static Data:** Fixtures don't automatically update with live changes

### Future Path

When ready to consider live access:

1. Research Redfin's official API (if available)
2. Review robots.txt and terms of service
3. Implement rate limiting and respectful access patterns
4. Consider authorized MLS/CRMLS access instead
5. Evaluate RSS/feed options
6. Build on the existing parser foundation

## Alternatives Considered

### Alternative 1: Immediate Live Scraping
**Rejected:** Too risky legally and technically before validating the workflow.

### Alternative 2: Redfin API Integration
**Deferred:** Unknown if Redfin provides a public API; research required.

### Alternative 3: MLS/CRMLS Direct Integration
**Deferred:** Requires authorized access and licensing; future milestone.

## Implementation Notes

- URL normalization ensures consistency (https, www, no tracking params)
- Missing fields are allowed (None/null) rather than failing parsing
- Duplicate detection works by both URL and normalized address
- Existing user decisions are preserved on re-import
- Source tracking includes: retrieval method, source file, content hash

## References

- PRD.md: Section 4.1-4.3 (Primary source workflow)
- Architecture.md: Section 4.4 (redfin_discovery.py) and 4.5 (redfin_detail_parser.py)
- Prompt 003: Redfin Discovery Adapter Foundation requirements
