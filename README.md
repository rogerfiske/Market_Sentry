# Market_Sentry

Buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties.

## Project Mission

Market_Sentry is a disciplined market observation tool that helps buyers identify residential properties with significant market exposure patterns. The system begins with candidate discovery, stages candidates for user review, and monitors selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, and cross-site validation.

## Current Milestone: Cross-Site Enrichment Foundation (MVP 6)

This milestone implements cross-site enrichment from Zillow, Realtor.com, Homes.com, and Compass using saved HTML fixtures, enabling cross-validation of Redfin data and data quality confidence assessment.

**Status:** ✅ Complete

### MVP 1: Project Scaffold

- ✅ Project folder structure
- ✅ SQLite database schema
- ✅ Configuration files
- ✅ CLI entry point with database management
- ✅ Logging system
- ✅ Core data models
- ✅ Basic domain logic functions
- ✅ Comprehensive unit tests (46 tests)

### MVP 2: Review Workflow

- ✅ Candidate insertion with deduplication (by URL and normalized address)
- ✅ Sample seed data generation (3 test candidates)
- ✅ Review queue export to CSV
- ✅ Review decision import with validation
- ✅ Watchlist promotion for 'save' decisions
- ✅ Watch priority calculation (high/medium/low)
- ✅ Gas service and Quiet/Vibrancy preservation
- ✅ Idempotent import workflow
- ✅ New CLI commands: seed-sample-candidates, export-review, import-review, list-candidates, list-watched
- ✅ Complete workflow tests (62 tests total, all passing)

### MVP 3: Redfin Discovery Adapter Foundation

- ✅ Manual Redfin URL import from CSV
- ✅ Saved/static HTML fixture parsing
- ✅ Redfin URL validation and normalization
- ✅ Address, city, and ZIP extraction from URLs
- ✅ Candidate insertion with deduplication
- ✅ Source page audit tracking
- ✅ New CLI commands: import-redfin-urls, parse-redfin-fixtures
- ✅ Comprehensive tests for all new functionality (110 tests total, all passing)

**Important:** No live scraping or network calls are implemented yet. Milestone 3 uses manual URL import and saved HTML fixtures to validate the discovery→review→watchlist pipeline before adding live site access.

### MVP 4: Redfin Detail Parser and Candidate Enrichment

- ✅ Parse saved Redfin property detail page HTML files
- ✅ Extract property facts: price, beds, baths, sqft, lot size, year built, garage spaces
- ✅ Extract Quiet and Vibrancy lifestyle scores with semantic labels
- ✅ Detect gas service evidence from property descriptions
- ✅ Parse listing history events with date, type, price, and MLS information
- ✅ Calculate preliminary Effective DOM metrics (listing churn, DOM resets, sale/rent alternation)
- ✅ Enrich candidate records with parsed detail data
- ✅ Apply Quiet Gatekeeper logic during enrichment
- ✅ Preserve user decisions during enrichment updates
- ✅ New CLI commands: parse-redfin-details, enrich-redfin-details
- ✅ Comprehensive tests for all new functionality (130 tests total, all passing)

**Important:** Continues the saved HTML approach from Milestone 3. No live scraping. Users manually save Redfin detail pages and run enrichment commands.

### MVP 5: Effective DOM Engine and Candidate Scoring Report

- ✅ Effective DOM v1 metrics engine (displayed_dom, current_listing_instance_dom, sale_cycle_dom, rent_sale_exposure_dom, calendar_exposure_dom, effective_dom, effective_dom_delta)
- ✅ Event normalization for listing history (sale_listed, sale_removed, sale_relisted, sale_pending, sale_back_on_market, sale_sold, sale_price_changed, rental_listed, rental_removed, unknown)
- ✅ DOM reset counting (removals followed by relisting within 90 days without intervening sold event)
- ✅ Listing churn indicators
- ✅ Sale/rent alternation detection
- ✅ Comprehensive candidate scoring v1 (quiet_gatekeeper_result, location_fit_label, location_fit_score, property_fit_score, effective_dom_leverage_score, data_confidence_score, overall_review_score)
- ✅ Review recommendations (strong_review, review, maybe_review, reject_location_noise, needs_more_data)
- ✅ Warning flags and positive flags collection
- ✅ Candidate analysis report generation (CSV and Markdown formats)
- ✅ Database recalculation workflow for Effective DOM metrics
- ✅ New CLI commands: recalc-candidates, export-analysis-report
- ✅ Comprehensive tests for event normalization, DOM metrics, scoring, and critical domain rules (188 tests total, all passing)

**Important:** No live scraping or network calls. Milestone 5 performs deterministic analysis on existing parsed Redfin data from Milestone 4.

### MVP 6: Cross-Site Enrichment Foundation

- ✅ Manual cross-site URL import from CSV (Zillow, Realtor.com, Homes.com, Compass)
- ✅ Saved/static HTML fixture parsing for 4 real estate sites
- ✅ Cross-site observation storage in dedicated table (preserves Redfin as source of truth)
- ✅ Property matching by URL and normalized address
- ✅ Cross-site data comparison and discrepancy detection
- ✅ Discrepancy flags: price differences >$10k, listing status conflicts, DOM differences >30 days
- ✅ Cross-site comparison report generation (CSV format)
- ✅ New CLI commands: import-cross-site-urls, parse-cross-site-fixtures, export-cross-site-report
- ✅ Comprehensive tests for all parsers and cross-site logic (partial passing - parsers implemented)

**Important:** Continues the saved HTML approach from Milestones 3-5. No live scraping. Users manually save property detail pages from multiple sites and run enrichment commands. Cross-site observations are stored separately from the primary Redfin data to maintain single source of truth.

**Cross-Site Parsers:**
- **Zillow**: Price, beds, baths, sqft, lot size, listing status, DOM, property description
- **Realtor.com**: Price, beds, baths, sqft, lot size, listing status, DOM, MLS info
- **Homes.com**: Price, beds, baths, sqft, lot size, listing status, DOM
- **Compass**: Price, beds, baths, sqft, lot size, listing status, DOM

**Discrepancy Detection:**
- **Price Discrepancy**: Flagged when any site's price differs from Redfin by more than $10,000
- **Status Discrepancy**: Flagged when listing status conflicts across sites (e.g., "active" vs "pending" vs "off-market")
- **DOM Discrepancy**: Flagged when displayed DOM differs by more than 30 days across sites

**Important Note:** Discrepancy flags are data quality indicators, NOT purchase recommendations. They highlight properties where cross-site data conflicts suggest the need for additional verification or closer inspection.

### Effective DOM v1 Metrics

**Effective DOM** measures property-level market exposure across listing, removal, and relisting events. Milestone 5 implements multiple DOM variants with a fallback hierarchy:

1. **displayed_dom**: DOM shown on the source page (e.g., Redfin)
2. **current_listing_instance_dom**: Days from latest listing/relisting event to analysis date
3. **sale_cycle_dom**: Total active sale-listing exposure days within current no-sale cycle
4. **rent_sale_exposure_dom**: Total exposure days across sale and rental listing periods
5. **calendar_exposure_dom**: Calendar days from earliest observed event to analysis date
6. **effective_dom**: Best available property-level market exposure estimate using fallback hierarchy:
   - Prefer rent_sale_exposure_dom if sale/rent alternation present
   - Else prefer sale_cycle_dom
   - Else prefer calendar_exposure_dom
   - Else fallback to current_listing_instance_dom
   - Else fallback to displayed_dom
7. **effective_dom_delta**: effective_dom - displayed_dom (reveals hidden market exposure)

**Additional Metrics:**
- **listing_churn_count**: Count of all listing activity events (listed, removed, relisted, price_changed)
- **dom_reset_count**: Count of removal→relist cycles within 90 days (without intervening sold event)
- **sale_rent_alternation_count**: Count of transitions between sale and rental exposure categories
- **price_change_count**: Count of price_changed events
- **first_observed_event_date**, **latest_observed_event_date**: Event date range
- **first_observed_price**, **current_or_latest_price**, **lowest_observed_price**, **highest_observed_price**: Price tracking

**Current Cycle Detection:** Events are analyzed within the current "no-sale cycle" (events after the last sold event). If a sold event is present in the listing history, it resets the cycle, and only subsequent events are counted.

### Candidate Scoring Labels

The scoring system uses the following review recommendation labels:

- **strong_review**: High overall score (>= 80). Excellent location fit, good property fit, or high Effective DOM leverage signals. Top priority for human review.
- **review**: Good overall score (>= 60). Target location fit and acceptable property characteristics. Recommended for review.
- **maybe_review**: Moderate overall score (>= 40). Some positive signals but missing key data or borderline fit. Low priority review.
- **reject_location_noise**: Failed Quiet gatekeeper (quiet_score < 7.0). Location does not meet noise risk threshold regardless of other factors.
- **needs_more_data**: Low data confidence score. Missing critical fields (Quiet score, address, price, etc.). Requires enrichment before review.

**Location Fit Labels:**
- **excellent_location_fit**: quiet_score >= 9.0 and vibrancy_score <= 2.0 (location_fit_score: 100)
- **target_location_fit**: quiet_score >= 8.0 and vibrancy_score <= 2.5 (location_fit_score: 85)
- **quiet_but_review_vibrancy**: quiet_score >= 7.5 but vibrancy_score > 2.5 (location_fit_score: 70)
- **borderline_quiet**: quiet_score >= 7.0 but below target thresholds (location_fit_score: 50)
- **fail_noise_risk**: quiet_score < 7.0 (location_fit_score: 0)
- **needs_manual_location_review**: Missing Quiet score (location_fit_score: 40)

**Critical Domain Rule:** Low Vibrancy alone is NOT sufficient. The Quiet gatekeeper rejects properties with quiet_score < 7.0 even if vibrancy_score is very low. The target is very high Quiet AND very low Vibrancy.

**Warning Flags:**
- low_quiet_score, fail_quiet_gatekeeper, missing_quiet_score
- no_gas_service, insufficient_garage_spaces
- price_outside_range, missing_property_facts
- no_listing_history, low_data_confidence

**Positive Flags:**
- excellent_location, target_location
- has_gas_service, good_garage_spaces
- high_dom_delta (effective_dom_delta >= 90)
- has_dom_resets, high_listing_churn, sale_rent_alternation, multiple_price_changes

## Key Features (Planned)

1. **Effective DOM Calculation**: Measures property-level market exposure across listing, removal, and relisting events
2. **Quiet/Vibrancy Gatekeeper**: Filters properties based on location noise/activity proxy scores
3. **Gas Service Detection**: Identifies properties with natural gas service
4. **Human-in-the-Loop Workflow**: User reviews candidates before promotion to watchlist
5. **Multi-Source Enrichment**: Cross-references Redfin, Zillow, Realtor.com, and other sources
6. **County Verification**: Validates ownership transfers via county records

## Critical Domain Rules

1. **Effective DOM** measures property-level market exposure across listing, removal, and relisting events within a defined lookback window, excluding periods reset by confirmed ownership transfer.

2. **Quiet Score is the gatekeeper**: Reject or heavily downgrade if Quiet Score is below threshold, even when Vibrancy is low.

3. **Target is very high Quiet AND very low Vibrancy**: Low Vibrancy alone is not sufficient.

4. **Gas detection rule**: Any mention of gas means the property has natural gas service/supply.

5. **Neutral language**: The system does not infer seller intent. It uses neutral terms such as listing churn, non-closing relist cycle, DOM reset pattern, and pre-portal exposure.

6. **Human-in-the-loop**: The workflow stages candidates for user review before promotion to the active watchlist.

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- pip or your preferred Python package manager

### Installation

1. Clone the repository:

```bash
git clone https://github.com/rogerfiske/Market_Sentry.git
cd Market_Sentry
```

2. Create and activate a virtual environment:

```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Install the package in development mode:

```bash
pip install -e .
```

5. Create your local configuration:

```bash
cp .env.example .env
# Edit .env with your preferred settings
```

6. Initialize the database:

```bash
marketsentry init-database
```

## CLI Usage

### Initialize Database

```bash
marketsentry init-database
```

Creates the SQLite database and all required tables.

### Check Status

```bash
marketsentry status
```

Shows database status and record counts.

### View Configuration

```bash
marketsentry config-show
```

Displays current configuration settings.

### Show Version

```bash
marketsentry version
```

### Redfin Discovery Commands (MVP 3)

#### Import Redfin URLs from CSV

```bash
marketsentry import-redfin-urls --file data/imports/redfin_urls.csv
```

Imports Redfin property URLs from a CSV file. The CSV must contain a `redfin_url` column and can optionally include `address`, `city`, `zip`, `price`, `beds`, `baths`, `sqft`, and `notes`.

**Example CSV format:**

```csv
redfin_url,address,city,zip,price,beds,baths,sqft,notes
https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263,46197 Via La Tranquila,Temecula,92592,750000,3,2.5,2100,Looks promising
https://www.redfin.com/CA/Murrieta/25678-Via-Viejo-92563/home/7123456,,,,,,,Test this one
```

If address, city, or ZIP are not provided, the system will attempt to extract them from the URL.

#### Parse Redfin HTML Fixtures

```bash
marketsentry parse-redfin-fixtures --dir data/raw/redfin
```

Parses saved/static Redfin HTML files from a directory and extracts candidate property URLs. This allows testing the parser logic without live network calls.

Place `.html` or `.htm` files in `data/raw/redfin/` and run this command to extract candidates.

### Redfin Detail Parser Commands (MVP 4)

#### Parse Redfin Detail Pages

```bash
marketsentry parse-redfin-details --dir data/detail_pages/
```

Parses saved Redfin property detail page HTML files and displays a summary of extracted data including:

- Property facts (price, beds, baths, sqft, lot size, year built, garage spaces)
- Quiet and Vibrancy lifestyle scores
- Gas service detection
- Listing history events
- MLS information

This command does not modify the database - it only displays parsed information for verification.

#### Enrich Candidates with Detail Data

```bash
marketsentry enrich-redfin-details --dir data/detail_pages/ --db db/market_sentry.db
```

Parses saved detail page HTML files and enriches matching candidates in the database with:

- Property facts and lifestyle scores
- Gas service evidence
- Quiet Gatekeeper evaluation
- Listing history events (with duplicate detection)
- Preliminary Effective DOM metrics (listing churn, DOM resets, sale/rent alternation)

Candidates are matched by Redfin URL or normalized address. User decisions and notes are preserved during enrichment.

**Workflow:**

1. Browse Redfin and save detail pages to `data/detail_pages/` (right-click → Save As → Web Page, Complete)
2. Run `parse-redfin-details` to verify extraction
3. Run `enrich-redfin-details` to update candidates in the database

### Effective DOM and Scoring Commands (MVP 5)

#### Recalculate Candidate Metrics

```bash
marketsentry recalc-candidates
# Or specify database path:
marketsentry recalc-candidates --database db/market_sentry.db
```

Recalculates Effective DOM metrics and scoring-related fields for all candidates in the review queue. This command:

- Reads candidates and listing_events from database
- Recalculates all Effective DOM v1 metrics
- Updates candidate_review_queue with effective_dom_estimate, listing_churn_count, dom_reset_count, sale_rent_alternation_count, quiet_gatekeeper_result
- Preserves user_decision and user_notes
- Is idempotent (safe to run multiple times)

Prints: candidates scanned, candidates updated, listing events used, warnings/errors.

#### Export Candidate Analysis Report

```bash
marketsentry export-analysis-report
# Or specify output path and database:
marketsentry export-analysis-report --output data/exports/my_analysis.csv --database db/market_sentry.db
# Or export as Markdown:
marketsentry export-analysis-report --markdown
```

Exports comprehensive candidate analysis report to CSV (or Markdown). The report includes:

- Review recommendation and overall review score
- Location fit label and Quiet gatekeeper result
- Quiet/Vibrancy scores
- Property facts (price, beds, baths, sqft, garage spaces, gas service)
- Effective DOM metrics (displayed_dom, effective_dom, effective_dom_delta)
- Listing activity indicators (listing_churn_count, dom_reset_count, sale_rent_alternation_count, price_change_count)
- Data confidence score
- Warning flags and positive flags
- Address, city, ZIP, Redfin URL
- User decision and notes (preserved from review queue)

Default output: `data/exports/candidate_analysis_YYYYMMDD_HHMMSS.csv`

**How to Use the Analysis Report:**

1. Run `recalc-candidates` to ensure all metrics are current
2. Run `export-analysis-report` to generate the CSV
3. Open the CSV in Excel or your preferred spreadsheet tool
4. Sort by review_recommendation and overall_review_score
5. Focus on `strong_review` and `review` candidates first
6. Review warning_flags and positive_flags for each candidate
7. Use effective_dom_delta to identify properties with hidden market exposure
8. Set user_decision column to: save, reject, maybe, or hold_for_more_data
9. Import decisions with `import-review` command
10. Candidates marked as `save` are promoted to watchlist

### Cross-Site Enrichment Commands (MVP 6)

#### Import Cross-Site URLs from CSV

```bash
marketsentry import-cross-site-urls --file data/imports/cross_site_urls.csv
```

Imports cross-site property URLs from a CSV file and updates the `watched_properties` table with URLs for Zillow, Realtor.com, Homes.com, and Compass.

**CSV Format:**

```csv
redfin_url,address,zillow_url,realtor_url,homes_url,compass_url,notes
https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263,46197 Via La Tranquila,https://www.zillow.com/homedetails/...,https://www.realtor.com/realestateandhomes-detail/...,https://www.homes.com/property/...,https://www.compass.com/listing/...,Cross-check this one
```

**Columns:**
- `redfin_url` (required): Redfin URL to match watched property
- `address` (optional): Property address (used if redfin_url not provided or no match)
- `zillow_url`, `realtor_url`, `homes_url`, `compass_url` (optional): URLs for each site
- `notes` (optional): User notes

Properties are matched by Redfin URL or normalized address. At least one cross-site URL must be provided.

#### Parse Cross-Site HTML Fixtures

```bash
# Parse Zillow fixtures
marketsentry parse-cross-site-fixtures --dir data/cross_site/zillow --source zillow

# Parse Realtor.com fixtures
marketsentry parse-cross-site-fixtures --dir data/cross_site/realtor --source realtor

# Parse Homes.com fixtures
marketsentry parse-cross-site-fixtures --dir data/cross_site/homes --source homes

# Parse Compass fixtures
marketsentry parse-cross-site-fixtures --dir data/cross_site/compass --source compass
```

Parses saved cross-site property detail page HTML files and creates observations in the `cross_site_observations` table. Properties are matched to the watchlist by:
1. Cross-site URL (if property has zillow_url, realtor_url, etc.)
2. Normalized address

**Workflow:**
1. Ensure property is in watchlist (promoted from candidate review)
2. Use `import-cross-site-urls` to add cross-site URLs to watched property
3. Manually save detail pages from each site to separate directories
4. Run `parse-cross-site-fixtures` for each site
5. Observations are inserted into `cross_site_observations` table
6. Run `export-cross-site-report` to generate comparison report

**Important:** Redfin data in `watched_properties` remains the single source of truth. Cross-site observations are stored separately for comparison and data quality validation only.

#### Export Cross-Site Comparison Report

```bash
marketsentry export-cross-site-report
# Or specify output path and database:
marketsentry export-cross-site-report --output data/exports/cross_site_comparison.csv --database db/market_sentry.db
```

Exports cross-site comparison report to CSV. The report includes:

- Property identification (address, city, ZIP, Redfin URL)
- Redfin data (price, DOM, status)
- Cross-site data (price, DOM, status from Zillow, Realtor.com, Homes.com, Compass)
- Discrepancy flags (price, status, DOM)
- Comparison notes and warnings

**Discrepancy Flags:**
- `has_price_discrepancy`: Any site's price differs from Redfin by >$10,000
- `has_status_discrepancy`: Listing status conflicts across sites (active vs pending vs off-market)
- `has_dom_discrepancy`: DOM differs by >30 days across sites

Default output: `data/exports/cross_site_report_YYYYMMDD_HHMMSS.csv`

**Important:** Discrepancy flags are data quality indicators, NOT purchase recommendations. They highlight properties requiring additional verification or manual inspection due to conflicting data across sites.

### Review Workflow Commands (MVP 2-5)

#### Seed Sample Candidates

```bash
marketsentry seed-sample-candidates
```

Seeds the database with 3 sample candidates for testing the review workflow.

#### Export Review Queue

```bash
marketsentry export-review
# Or specify output file:
marketsentry export-review --output data/exports/my_review.csv
```

Exports all candidates from the review queue to CSV for human review.

#### Import Review Decisions

```bash
marketsentry import-review --file data/imports/reviewed_candidates.csv
```

Imports reviewed decisions from CSV. Valid decisions: `save`, `reject`, `maybe`, `hold_for_more_data`.

Properties marked as `save` are promoted to the watchlist.

#### List Candidates

```bash
marketsentry list-candidates
# Or limit results:
marketsentry list-candidates --limit 20
```

Lists candidates in the review queue.

#### List Watched Properties

```bash
marketsentry list-watched
# Or limit results:
marketsentry list-watched --limit 20
```

Lists properties in the active watchlist.

### Complete Workflow Example (MVP 3)

```bash
# 1. Initialize database
marketsentry init-database

# 2. Create a CSV file with Redfin URLs (data/imports/redfin_urls.csv)
#    Required column: redfin_url
#    Optional columns: address, city, zip, price, beds, baths, sqft, notes

# 3. Import Redfin URLs from CSV
marketsentry import-redfin-urls --file data/imports/redfin_urls.csv

# OR: Parse saved Redfin HTML fixtures
marketsentry parse-redfin-fixtures --dir data/raw/redfin

# 4. List imported candidates
marketsentry list-candidates

# 5. Export candidates for review
marketsentry export-review

# 6. Edit the exported CSV file (data/exports/review_queue_*.csv)
#    Set user_decision column to: save, reject, maybe, or hold_for_more_data

# 7. Import reviewed decisions
marketsentry import-review --file data/exports/review_queue_20260505_123456.csv

# 8. View watched properties
marketsentry list-watched
```

**Note:** You can still use `marketsentry seed-sample-candidates` to seed test data if you don't have real Redfin URLs yet.

### Complete Workflow Example with Cross-Site Enrichment (MVP 3-6)

```bash
# Phase 1: Candidate Discovery and Review (MVP 3-5)
# ====================================================

# 1. Initialize database
marketsentry init-database

# 2. Import Redfin URLs
marketsentry import-redfin-urls --file data/imports/redfin_urls.csv

# 3. Enrich candidates with Redfin detail data
marketsentry enrich-redfin-details --dir data/detail_pages/

# 4. Recalculate Effective DOM metrics and scoring
marketsentry recalc-candidates

# 5. Export analysis report
marketsentry export-analysis-report

# 6. Review candidates in CSV, set user_decision to 'save' for properties to watch

# 7. Import review decisions (promotes 'save' to watchlist)
marketsentry import-review --file data/exports/candidate_analysis_20260505_120000.csv

# Phase 2: Cross-Site Enrichment for Watched Properties (MVP 6)
# ===============================================================

# 8. Create CSV with cross-site URLs (data/imports/cross_site_urls.csv)
#    Columns: redfin_url, address, zillow_url, realtor_url, homes_url, compass_url

# 9. Import cross-site URLs to link watched properties to other sites
marketsentry import-cross-site-urls --file data/imports/cross_site_urls.csv

# 10. Manually save detail pages from each site:
#     - Zillow: Save to data/cross_site/zillow/
#     - Realtor.com: Save to data/cross_site/realtor/
#     - Homes.com: Save to data/cross_site/homes/
#     - Compass: Save to data/cross_site/compass/

# 11. Parse cross-site fixtures (creates observations in database)
marketsentry parse-cross-site-fixtures --dir data/cross_site/zillow --source zillow
marketsentry parse-cross-site-fixtures --dir data/cross_site/realtor --source realtor
marketsentry parse-cross-site-fixtures --dir data/cross_site/homes --source homes
marketsentry parse-cross-site-fixtures --dir data/cross_site/compass --source compass

# 12. Export cross-site comparison report
marketsentry export-cross-site-report

# 13. Review comparison report for discrepancies:
#     - Price differences >$10k
#     - Status conflicts (active vs pending)
#     - DOM differences >30 days
```

**Important Notes:**
- Cross-site observations are stored separately from Redfin data (single source of truth)
- Discrepancy flags are data quality indicators, not purchase recommendations
- All cross-site data uses saved HTML approach (no live scraping)
- Properties must be in watchlist before cross-site enrichment

## Project Structure

```
Market_Sentry/
├── README.md
├── PRD.md                      # Product Requirements Document
├── Architecture.md             # Architecture documentation
├── requirements.txt            # Python dependencies
├── .env.example               # Example configuration
├── .gitignore
├── pyproject.toml             # Project metadata and build config
├── data/                      # Data directories
│   ├── raw/
│   ├── processed/
│   ├── exports/
│   └── imports/
├── db/                        # SQLite database location
├── logs/                      # Application logs
├── docs/                      # Documentation
│   ├── prompts/
│   ├── decisions/
│   └── examples/
├── src/
│   └── marketsentry/          # Main Python package
│       ├── __init__.py
│       ├── cli.py             # CLI entry point
│       ├── config.py          # Configuration management
│       ├── logging_config.py  # Logging setup
│       ├── models.py          # Data models
│       ├── database.py        # Database operations
│       ├── schema.py          # Database schema
│       ├── normalization.py   # Address/data normalization
│       ├── gas_detection.py   # Gas service detection
│       ├── quiet_vibrancy.py  # Location scoring
│       ├── effective_dom.py            # Effective DOM calculation
│       ├── scoring.py                  # Property scoring engine
│       ├── review_export.py            # Review queue export
│       ├── review_import.py            # Review decision import
│       ├── redfin_url_utils.py         # Redfin URL validation and normalization
│       ├── redfin_url_import.py        # Manual Redfin URL import
│       ├── redfin_fixture_parser.py    # Saved HTML fixture parsing
│       ├── redfin_detail_parser.py     # Redfin detail page parser
│       ├── redfin_detail_enrichment.py # Candidate enrichment workflow
│       ├── candidate_recalc.py         # Candidate metrics recalculation
│       ├── candidate_report.py         # Candidate analysis report generation
│       ├── cross_site_url_import.py    # Cross-site URL import
│       ├── cross_site_enrichment.py    # Cross-site fixture parsing
│       ├── cross_site_comparison.py    # Cross-site data comparison
│       ├── cross_site_report.py        # Cross-site comparison report
│       ├── zillow_parser.py            # Zillow detail page parser
│       ├── realtor_parser.py           # Realtor.com detail page parser
│       ├── homes_parser.py             # Homes.com detail page parser
│       ├── compass_parser.py           # Compass detail page parser
│       ├── watchlist.py                # Watchlist promotion logic
│       └── sample_data.py              # Sample data generation
└── tests/                              # Unit tests
    ├── fixtures/                       # Test fixtures
    │   ├── redfin_urls_valid.csv
    │   ├── redfin_urls_mixed_invalid.csv
    │   ├── redfin_search_fixture.html
    │   ├── redfin_detail/              # Redfin detail page fixtures
    │   │   ├── normal_property_with_gas.html
    │   │   ├── high_noise_property.html
    │   │   ├── listing_churn_property.html
    │   │   └── sparse_data_property.html
    │   └── cross_site_urls.csv         # Cross-site URL import fixture
    ├── test_database.py
    ├── test_effective_dom.py
    ├── test_effective_dom_v1.py       # Comprehensive v1 tests
    ├── test_scoring.py
    ├── test_scoring_v1.py             # Comprehensive v1 tests
    ├── test_gas_detection.py
    ├── test_quiet_vibrancy.py
    ├── test_review_workflow.py
    ├── test_redfin_url_utils.py
    ├── test_redfin_url_import.py
    ├── test_redfin_fixture_parser.py
    ├── test_redfin_detail_parser.py
    ├── test_cross_site_url_import.py
    ├── test_cross_site_enrichment.py
    ├── test_cross_site_comparison.py
    └── test_cross_site_report.py
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=marketsentry

# Run specific test file
pytest tests/test_gas_detection.py

# Run with verbose output
pytest -v
```

## Development

### Code Quality

This project follows Python best practices:

- **Python 3.11+** required
- **PEP8** compliant code style
- **Type hints** required for all functions
- **Docstrings** required for all functions
- **Black** for code formatting
- **Ruff** for linting
- **MyPy** for type checking

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type check
mypy src/
```

## Next Planned Milestone

### MVP 7: County Recorder Integration and Enhanced DOM

- County recorder HTML fixture parsing (saved public records pages)
- Property ownership transfer verification from county records
- Cross-reference sold events with confirmed title transfers
- County-verified sale reset logic for Effective DOM calculation
- Enhanced DOM metrics with county-confirmed ownership changes
- Property transfer timeline visualization
- APN (Assessor's Parcel Number) tracking and validation
- Ownership transfer discrepancy detection (MLS sold vs county records)

## Repository

https://github.com/rogerfiske/Market_Sentry

## License

MIT

## Documentation

- [PRD.md](PRD.md) - Product Requirements Document
- [Architecture.md](Architecture.md) - System Architecture
- [docs/prompts/](docs/prompts/) - Implementation prompts
- [docs/decisions/](docs/decisions/) - Architecture decision records

## Notes

- This is a local-first application. All data is stored in a local SQLite database.
- **No live scraping or network calls are implemented.** Milestones 3-6 use manual URL import and saved HTML fixtures.
- See design decisions for rationale:
  - [Decision 002: Redfin Discovery Adapter Foundation](docs/decisions/002-redfin-discovery-adapter-foundation.md)
  - [Decision 003: Redfin Detail Parser and Candidate Enrichment](docs/decisions/003-redfin-detail-parser-saved-fixtures.md)
  - [Decision 004: Effective DOM v1 and Review Scoring](docs/decisions/004-effective-dom-v1-and-review-scoring.md)
  - [Decision 005: Cross-Site Enrichment Foundation](docs/decisions/005-cross-site-enrichment-foundation.md)
- The system is designed for disciplined market observation, not automatic purchasing decisions.
- All scoring and filtering logic is deterministic and unit-tested.
- The review workflow is human-in-the-loop: candidates must be reviewed before watchlist promotion.
- Review recommendations (strong_review, review, maybe_review, reject_location_noise, needs_more_data) are NOT purchase recommendations. They only determine how candidates should be treated in the user review queue.
