# MarketSentry Architecture

## 1. Architecture overview

MarketSentry is a local-first Python application with a SQLite database, CSV/Excel review workflow, deterministic scoring modules, and staged source enrichment.

The system is intentionally human-in-the-loop. Discovery results are first staged into a candidate review queue. The user then chooses which properties are promoted to the watched database.

## 2. Recommended technology stack

- Python 3.11+
- SQLite
- SQLAlchemy or sqlite-utils for database access
- Pydantic for data validation
- pandas for CSV/Excel import/export
- requests/httpx for compliant HTTP retrieval where allowed
- beautifulsoup4/lxml for HTML parsing where allowed
- Playwright only if required for browser-rendered pages and compliant use
- pytest for tests
- rich or typer for CLI usability
- python-dotenv for local configuration

## 3. Project folder structure

```text
Market_Sentry/
  README.md
  PRD.md
  Architecture.md
  requirements.txt
  .env.example
  .gitignore
  pyproject.toml
  data/
    raw/
    processed/
    exports/
    imports/
  db/
    .gitkeep
  logs/
    .gitkeep
  docs/
    prompts/
    decisions/
    examples/
  src/
    marketsentry/
      __init__.py
      cli.py
      config.py
      logging_config.py
      models.py
      database.py
      schema.py
      redfin_discovery.py
      redfin_detail_parser.py
      effective_dom.py
      scoring.py
      review_export.py
      review_import.py
      crosscheck_zillow.py
      crosscheck_realtor.py
      crosscheck_homes.py
      crosscheck_compass.py
      county_verification.py
      normalization.py
      gas_detection.py
      quiet_vibrancy.py
  tests/
    test_database.py
    test_effective_dom.py
    test_scoring.py
    test_gas_detection.py
    test_quiet_vibrancy.py
    test_review_workflow.py
```

## 4. Core modules

### 4.1 config.py

Responsibilities:

- Load environment variables
- Store Redfin start URLs
- Store threshold values
- Store database path
- Store export path

### 4.2 database.py

Responsibilities:

- Open SQLite connection
- Initialize schema
- Run migrations in a simple controlled way
- Provide helper functions for inserts/updates

### 4.3 models.py

Responsibilities:

- Define typed data structures for:
  - CandidateProperty
  - WatchedProperty
  - ListingEvent
  - ObservationSnapshot
  - ReviewDecision
  - ScoreResult

### 4.4 redfin_discovery.py

Responsibilities:

- Accept Redfin search URLs
- Discover candidate property URLs where feasible
- Normalize URLs
- Deduplicate candidates
- Save candidate summary records

### 4.5 redfin_detail_parser.py

Responsibilities:

- Parse Redfin detail pages
- Extract property facts
- Extract listing history events
- Extract displayed DOM
- Extract Quiet/Vibrancy
- Extract garage spaces
- Extract gas evidence
- Extract APN when visible

### 4.6 effective_dom.py

Responsibilities:

- Convert listing history into market-exposure metrics
- Apply sale/ownership-transfer resets
- Calculate Effective DOM variants

### 4.7 scoring.py

Responsibilities:

- Apply Quiet gatekeeper
- Score Vibrancy after Quiet passes
- Score property fit
- Score Effective DOM leverage
- Score data confidence

### 4.8 review_export.py

Responsibilities:

- Export candidate_review_queue to CSV and optionally Excel
- Include Save/Reject/Maybe fields for human review

### 4.9 review_import.py

Responsibilities:

- Read reviewed CSV/Excel
- Promote Save rows to watched_properties
- Preserve Maybe and Reject rows appropriately

### 4.10 crosscheck modules

Responsibilities:

- Cross-check watched properties only
- Store source presence, price, status, and URL
- Avoid unnecessary work on rejected candidates

### 4.11 county_verification.py

Responsibilities:

- Assist with APN and ownership-transfer validation
- Store county sale/transfer findings
- Determine whether Effective DOM cycle resets

## 5. Database schema

### 5.1 candidate_review_queue

Temporary staging table.

Fields:

- candidate_id
- discovery_date
- source_site
- source_search_url
- redfin_url
- address
- normalized_address
- city
- zip
- price
- beds
- baths
- sqft
- lot_size
- displayed_dom
- quiet_score
- vibrancy_score
- quiet_gatekeeper_result
- garage_spaces
- gas_service
- gas_evidence
- effective_dom_estimate
- listing_churn_count
- dom_reset_count
- sale_rent_alternation_count
- review_status
- user_decision
- user_notes
- created_at
- updated_at

### 5.2 watched_properties

Long-term watch table.

Fields:

- property_id
- first_saved_date
- active_watch_status
- redfin_url
- zillow_url
- realtor_url
- homes_url
- compass_url
- address
- normalized_address
- city
- zip
- apn
- current_price
- original_observed_price
- beds
- baths
- sqft
- lot_size
- garage_spaces
- gas_service
- gas_evidence
- quiet_score
- vibrancy_score
- displayed_dom
- effective_dom
- effective_dom_delta
- listing_churn_count
- dom_reset_count
- sale_rent_alternation_count
- county_sale_verified
- ownership_transfer_found
- last_checked_date
- next_check_date
- watch_priority
- user_notes
- created_at
- updated_at

### 5.3 property_observation_snapshots

Append-only table.

Fields:

- snapshot_id
- property_id
- snapshot_date
- source_site
- listing_status
- price
- displayed_dom
- effective_dom
- quiet_score
- vibrancy_score
- garage_spaces
- gas_service
- listing_history_hash
- property_detail_hash
- raw_source_url
- notes

### 5.4 listing_events

Append-only table.

Fields:

- event_id
- property_id
- candidate_id
- event_date
- source_site
- event_type
- old_value
- new_value
- source_listing_id
- mls_number
- confidence
- notes
- created_at

Event types:

- listed
- price_changed
- removed
- relisted
- pending
- back_on_market
- sold
- rental_listed
- rental_removed
- source_disappeared
- county_sale_found
- ownership_transfer_found

### 5.5 source_pages

Audit table.

Fields:

- source_page_id
- property_id
- candidate_id
- source_site
- source_url
- retrieved_at
- retrieval_method
- content_hash
- parser_version
- parse_status
- notes

### 5.6 user_review_actions

Fields:

- review_action_id
- candidate_id
- action_date
- user_decision
- user_notes
- promoted_property_id

## 6. Scoring architecture

### 6.1 Quiet gatekeeper

```text
if quiet_score is not null and quiet_score < 7.0:
    quiet_gatekeeper_result = "fail_noise_risk"
```

### 6.2 Target location fit

```text
target_location_fit = quiet_score >= 8.0 and vibrancy_score <= 2.5
excellent_location_fit = quiet_score >= 9.0 and vibrancy_score <= 2.0
```

### 6.3 Gas detection

Any text containing gas-related evidence sets:

```text
gas_service = true
```

Evidence text must be preserved.

### 6.4 Effective DOM leverage

Important signals:

- Effective DOM much greater than displayed DOM
- Multiple listing removals/relistings
- Sale/rent alternation
- Price reductions
- No confirmed sale between listing cycles

## 7. CLI design

Initial CLI commands:

```text
marketsentry init-db
marketsentry discover-redfin
marketsentry export-review
marketsentry import-review --file data/imports/reviewed_candidates.csv
marketsentry list-candidates
marketsentry list-watched
marketsentry score-candidates
marketsentry run-tests
```

## 8. Compliance and safety

MarketSentry should:

- Prefer authorized or allowed access methods.
- Respect robots.txt, terms, rate limits, and site restrictions.
- Avoid bypassing bot protections.
- Store URLs and timestamps for auditability.
- Be designed so source adapters can later be replaced by licensed APIs.

## 9. Milestone sequence

### Milestone 1: Scaffold, schema, CLI, tests

No live scraping. Build project foundation.

### Milestone 2: Candidate queue and review export/import

Support manual seed data and user review flow.

### Milestone 3: Redfin discovery adapter

Collect candidate URLs from supplied Redfin paths where feasible.

### Milestone 4: Redfin detail parser

Parse property details and listing history.

### Milestone 5: Effective DOM calculator

Implement and test Effective DOM metrics.

### Milestone 6: Scoring engine

Implement Quiet/Vibrancy, gas, garage, and leverage scoring.

### Milestone 7: Watchlist promotion and monitoring snapshots

Move selected properties to watched_properties and save observations.

### Milestone 8: Cross-site enrichment

Add Zillow, Realtor.com, Homes.com, Compass cross-checks.

### Milestone 9: County verification

Add county sale/transfer verification workflow.

### Milestone 10: Market observation reports

Generate ranked watchlist reports and property detail reports.

## 10. Claude Code handoff rules

Claude Code must work one milestone at a time.

For each milestone, Claude must:

1. Read PRD.md and Architecture.md.
2. Implement only the requested scope.
3. Add or update tests.
4. Run tests.
5. Update README if needed.
6. Report files changed.
7. Report commands run.
8. Report test results.
9. Report assumptions and blockers.
10. Commit and push to origin/main after quality gates pass.
11. Provide the commit hash.

Claude must not proceed to the next milestone until the user supplies the next PM prompt.
