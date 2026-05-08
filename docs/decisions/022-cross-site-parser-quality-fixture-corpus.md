# Decision 022: Cross-Site Parser Quality and Fixture Corpus Expansion

## Date

2026-05-08

## Status

Accepted

## Context

Milestones 6 and 22 established cross-site enrichment and manual fixture workflows for Zillow, Realtor.com, Homes.com, and Compass. Parsers extracted basic property facts but lacked:

- Confidence scoring to indicate parse reliability
- Missing required field tracking
- Listing agent/broker/MLS extraction
- Lot size extraction
- Robust normalization for price ($850K, $1.2M), sqft ("square feet"), DOM ("Listed 45 days ago"), status ("contingent", "coming soon"), and garage ("3-car garage")
- Sufficient fixture coverage for parser testing across status variants, gas evidence, garage evidence, and sparse/malformed pages

## Decision

### Improve parser quality before live cross-site retrieval

Parser reliability must be validated against known fixture variants before extending live retrieval to non-Redfin sources. Improving extraction, normalization, and confidence scoring with local fixtures reduces risk and improves cross-site validation usefulness.

### Use synthetic fixtures for testing

Synthetic/minimal HTML fixtures provide deterministic test inputs without requiring network access, real website content, or browser automation. Each source has 8+ fixture variants covering:

- Normal property (full data)
- Price discrepancy variant
- Pending status
- Sold/off-market status
- Missing optional fields (partial parse)
- Gas evidence (multiple gas keywords)
- Garage evidence (3-car garage, etc.)
- Sparse/malformed page (graceful handling)

### Parse confidence matters

Confidence levels (high, medium, low) help operators assess parse reliability:

- **high**: address and at least price/status/property facts extracted
- **medium**: address and some facts, but important fields missing
- **low**: sparse or uncertain parse (missing address or no useful data)

Low-confidence parses should be flagged for manual review. Cross-site data with low confidence should not be weighted equally in comparison reports.

### Cross-site data stays validation-only

Cross-site observations validate Redfin source-of-truth data. They do not overwrite user_decision, user_notes, active_watch_status, watch_priority, or Redfin-sourced property facts.

### Walkability remains excluded

Walkability-type information (walk score, transit score, bike score) is excluded from the initial scope per PRD direction.

## Consequences

### Positive

- All 4 parsers now extract 19 fields including listing agent/broker, MLS, lot size
- Parse confidence helps operators identify unreliable cross-site data
- Missing required fields are tracked for diagnostic purposes
- Normalization handles common price/sqft/DOM/status/garage format variations
- 32+ fixture files provide comprehensive parser test coverage
- Comparison reports include parse quality summary (lowest_parse_confidence, sources_with_parse_warnings)

### Negative

- Confidence classification is heuristic-based and may not cover all edge cases
- Parser extraction relies on CSS class patterns that may not match real site HTML exactly
- Synthetic fixtures are simpler than real web pages

## Related

- Milestone 6: Cross-site enrichment foundation
- Milestone 14: Live retrieval strategy and compliance adapters
- Milestone 22: Cross-site adapter parity and manual fixture workflow
