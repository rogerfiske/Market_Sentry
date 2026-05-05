# Market_Sentry

Buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties.

## Project Mission

Market_Sentry is a disciplined market observation tool that helps buyers identify residential properties with significant market exposure patterns. The system begins with candidate discovery, stages candidates for user review, and monitors selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, and cross-site validation.

## Current Milestone: Redfin Detail Parser and Candidate Enrichment (MVP 4)

This milestone implements detailed property parsing from saved Redfin HTML files and enriches candidate records with property facts, lifestyle scores, gas evidence, and listing history.

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

### Review Workflow Commands (MVP 2-4)

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
│       ├── watchlist.py                # Watchlist promotion logic
│       └── sample_data.py              # Sample data generation
└── tests/                              # Unit tests
    ├── fixtures/                       # Test fixtures
    │   ├── redfin_urls_valid.csv
    │   ├── redfin_urls_mixed_invalid.csv
    │   ├── redfin_search_fixture.html
    │   └── redfin_detail/              # Redfin detail page fixtures
    │       ├── normal_property_with_gas.html
    │       ├── high_noise_property.html
    │       ├── listing_churn_property.html
    │       └── sparse_data_property.html
    ├── test_database.py
    ├── test_effective_dom.py
    ├── test_scoring.py
    ├── test_gas_detection.py
    ├── test_quiet_vibrancy.py
    ├── test_review_workflow.py
    ├── test_redfin_url_utils.py
    ├── test_redfin_url_import.py
    ├── test_redfin_fixture_parser.py
    └── test_redfin_detail_parser.py
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

### MVP 5: Cross-Site Data Enrichment

- Zillow detail page parser (using saved HTML approach)
- Realtor.com detail page parser
- Cross-site data validation and conflict resolution
- Enhanced Effective DOM with multi-site listing history
- Property history timeline visualization
- Batch enrichment workflows

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
- **No live scraping or network calls are implemented.** Milestones 3 and 4 use manual URL import and saved HTML fixtures.
- See design decisions for rationale:
  - [Decision 002: Redfin Discovery Adapter Foundation](docs/decisions/002-redfin-discovery-adapter-foundation.md)
  - [Decision 003: Redfin Detail Parser and Candidate Enrichment](docs/decisions/003-redfin-detail-parser-saved-fixtures.md)
- The system is designed for disciplined market observation, not automatic purchasing decisions.
- All scoring and filtering logic is deterministic and unit-tested.
- The review workflow is human-in-the-loop: candidates must be reviewed before watchlist promotion.
