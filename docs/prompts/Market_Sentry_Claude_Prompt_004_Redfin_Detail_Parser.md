# Claude Code Prompt 004 - Redfin Detail Parser and Candidate Enrichment

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository:

https://github.com/rogerfiske/Market_Sentry

Local project folder:

C:\Users\Minis\CascadeProjects\Market_Sentry

Current accepted milestones:

- Milestone 1 scaffold complete at commit c8599761be1aeda80b075cf668c61970e587ebe7
- Milestone 2 candidate review queue and watchlist promotion complete at commit 5da7747a44069696189d1abb8057ee23f17d8754
- Milestone 3 Redfin discovery adapter foundation complete at commit 91eac91085609c38f150881bf35e5a22d1f6bdf0

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Review the current codebase and Milestone 3 implementation.
4. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
5. Keep PRD.md and Architecture.md in the project root.
6. Use src/marketsentry/ as the Python package path.
7. Do not move PRD.md or Architecture.md into docs/.
8. Do not implement live scraping, browser automation, Playwright, Selenium, or active network retrieval in this milestone.

Important PM direction:

Milestone 4 must parse individual Redfin property detail pages from saved/static HTML fixtures only.

Do not add live Redfin retrieval. Do not add network calls.

The goal is to extract property facts, listing-history events, and candidate-enrichment signals from user-saved Redfin detail pages, then update existing candidate records and listing event tables.

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

Your task for Prompt 004:

Implement Redfin Detail Parser and Candidate Enrichment v0.

This milestone must make it possible to parse saved Redfin property detail HTML files, extract useful property facts and listing-history data, update candidate records, and store listing events.

No live network calls.

## 1. Input fixture location

Use saved Redfin property detail pages from:

```text
data/raw/redfin/details/
```

Expected file types:

- .html
- .htm

Also add static test fixtures under:

```text
tests/fixtures/redfin_detail/
```

At minimum, include fixtures that cover:

1. A normal property with property facts, garage, gas evidence, Quiet/Vibrancy, and listing history.
2. A high-noise property similar to the Calle Nacido calibration pattern.
3. A listing-history churn property similar to the Via La Tranquila pattern.
4. A sparse/missing-field property that should parse without failing.

All fixtures must be static and minimal. They must not require network access.

## 2. Redfin detail parser models

Create or update typed models for:

- RedfinPropertyDetail
- RedfinPropertyFacts
- RedfinLifestyleScores
- RedfinListingHistoryEvent
- RedfinDetailParseResult
- RedfinDetailEnrichmentResult

Fields to support where available:

### Property identity

- redfin_url
- redfin_home_id
- address
- normalized_address
- city
- state
- zip
- apn
- mls_number
- source_mls

### Property facts

- price
- beds
- baths
- sqft
- lot_size
- year_built
- property_type
- garage_spaces
- parking_features_raw
- hoa_fee
- property_description
- features_raw
- utilities_raw

### Lifestyle scores

- quiet_score
- quiet_label
- quiet_raw_text
- vibrancy_score
- vibrancy_label
- vibrancy_raw_text

Important:
- Do not extract or prioritize Walk Score, Bike Score, Transit Score, or walkability-type information for the initial scope.
- If those fields are visible in a fixture, ignore them unless needed as raw unclassified text for parser stability.

### Gas evidence

- gas_service
- gas_evidence
- gas_evidence_source

Any mention of gas means natural gas service/supply exists.

Examples:
- gas fireplace
- gas range
- gas cooktop
- gas oven
- gas heating
- gas dryer hookup
- natural gas connected
- gas utility
- gas appliances

### Listing history events

- event_date
- event_type
- price
- raw_text
- source_listing_id
- mls_number
- source_mls
- confidence

Supported event_type values:

- listed
- price_changed
- removed
- relisted
- pending
- back_on_market
- sold
- rental_listed
- rental_removed
- unknown

Use neutral language. Do not infer seller intent.

## 3. Redfin detail parser implementation

Implement or complete:

```text
src/marketsentry/redfin_detail_parser.py
```

Required functions:

- parse_redfin_detail_html(html: str, source_url: str | None = None) -> RedfinDetailParseResult
- parse_redfin_detail_file(file_path: Path) -> RedfinDetailParseResult
- parse_redfin_detail_directory(directory: Path) -> list[RedfinDetailParseResult]

Function requirements:

- Type hints required.
- Docstrings required.
- Resilient to missing fields.
- No network calls.
- No browser automation.
- Extract as much as possible without failing the whole parse.
- Preserve parse warnings.
- Preserve raw snippets where helpful.
- Handle both absolute and relative Redfin URLs if present.
- Use existing normalization and gas detection helpers where possible.
- Use existing Quiet/Vibrancy gatekeeper helpers where possible.

## 4. Listing-history parsing

Implement basic listing-history parsing from saved HTML/text.

Expected Redfin-like rows may include text such as:

```text
Apr. 12, 2026 Listed $879,000 SDMLS #260008641
Apr. 12, 2026 Price Changed $889,000 SDMLS #260008641
Mar. 4, 2026 Rental Removed $3,995 SDMLS #250045127
Dec. 4, 2025 Listed for Rent $3,995 SDMLS #250045127
Nov. 29, 2025 Listing Removed CRMLS #SW25224865
Sep. 25, 2025 Listed $799,000 CRMLS #SW25224865
Jun. 30, 2025 Relisted SDMLS #250032070
Jun. 30, 2025 Listing Removed SDMLS #250032070
Jun. 29, 2025 Listed $839,000 SDMLS #250032070
```

Parser behavior:

- Parse dates when feasible.
- Classify event type.
- Extract price where present.
- Extract MLS number where present.
- Extract source MLS where present.
- Store unparsed rows as unknown events with raw_text.
- Do not discard useful raw text.
- Do not infer motive or intent.

## 5. Candidate enrichment

Add workflow to apply parsed Redfin detail data to candidate_review_queue.

Required behavior:

- Match parsed detail to candidate by:
  1. Redfin URL/home ID where available.
  2. Normalized address fallback.
- Update candidate fields where parsed data is available:
  - address
  - normalized_address
  - city
  - zip
  - price
  - beds
  - baths
  - sqft
  - lot_size
  - displayed_dom if extractable
  - quiet_score
  - vibrancy_score
  - quiet_gatekeeper_result
  - garage_spaces
  - gas_service
  - gas_evidence
  - effective_dom_estimate if available from listing history
  - listing_churn_count
  - dom_reset_count
  - sale_rent_alternation_count
- Do not overwrite user_decision, user_notes, or review_status in a destructive way.
- Preserve existing data when parsed value is None.
- Insert listing-history rows into listing_events where practical.
- Avoid duplicate listing_events on repeated parsing/import.
- Record source_pages provenance if practical.

## 6. Preliminary Effective DOM enrichment

Use the existing placeholder Effective DOM module only if appropriate, but improve it enough to support basic listing-history-derived metrics from parsed events.

At minimum, calculate:

- listing_churn_count
- dom_reset_count
- sale_rent_alternation_count
- effective_dom_estimate or preliminary_effective_dom

Basic definitions for this milestone:

- listing_churn_count: number of listing removed/relisted/price-changed/listed events in parsed history, excluding sold if sold resets later.
- dom_reset_count: count of removed followed by relisted/listed within 90 days without an intervening sold event in parsed data.
- sale_rent_alternation_count: count transitions between sale listing events and rental listing events.
- effective_dom_estimate: approximate calendar days from earliest observed non-sold listing/rental event in the current observed cycle to the latest observed listing event or today, unless a sold event appears and should reset the cycle.

Do not over-engineer county sale reset logic yet. County verification comes later.

## 7. CLI commands

Add or complete:

```text
marketsentry parse-redfin-details --dir data/raw/redfin/details
marketsentry enrich-redfin-details --dir data/raw/redfin/details
marketsentry list-candidates
marketsentry export-review
```

Behavior:

### parse-redfin-details

- Parses files and prints summary only.
- Does not modify database unless explicitly designed to do so and documented.

### enrich-redfin-details

- Parses files and updates candidate_review_queue/listing_events.
- Prints:
  - files processed
  - details parsed
  - candidates matched
  - candidates updated
  - listing events inserted
  - duplicates skipped
  - warnings
  - errors

CLI output must be ASCII-safe.

## 8. Tests

Add or update tests for:

- Parsing Redfin property facts from fixture.
- Parsing Quiet/Vibrancy.
- Confirming walkability fields are ignored.
- Gas detection from property description/features/utilities.
- Garage-space extraction.
- APN extraction where visible.
- Listing-history event parsing.
- Listing event type classification.
- Missing/sparse fields handled safely.
- Candidate enrichment updates candidate_review_queue.
- Existing user_decision/user_notes are not overwritten.
- Listing events inserted without duplicates.
- Effective DOM preliminary metrics from listing events.
- CLI parse/enrich commands where practical.

All tests must pass.

## 9. Documentation

Update README.md with:

- Milestone 4 status.
- How to save Redfin detail pages into data/raw/redfin/details/.
- How to run parse-redfin-details.
- How to run enrich-redfin-details.
- How candidate records are updated.
- How listing events are stored.
- Clear statement that Milestone 4 performs no live scraping or network access.

Add design decision note:

```text
docs/decisions/003-redfin-detail-parser-saved-fixtures.md
```

Explain:

- Why saved detail fixtures are used before live retrieval.
- What fields are extracted.
- What fields are intentionally ignored.
- How this supports Effective DOM development.

## 10. Code standards

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
- Saved detail fixture parsing works.
- Candidate enrichment works.
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
9. Example CLI workflow used to verify Milestone 4.
10. Counts from Redfin detail fixture parsing.
11. Counts from candidate enrichment.
12. Counts from listing event insertion.
13. Example parsed detail summary for one fixture.
14. Confirmation that walkability-type fields are ignored.
15. Confirmation that no live network calls, scraping, Playwright, Selenium, or browser automation were added.
16. Recommended next implementation step.
17. Git commit hash after committing and pushing completed changes to origin/main.

Important:

After all quality gates pass, commit and push the completed story changes to origin/main and include the commit hash in your completion report.
