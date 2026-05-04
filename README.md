# Market_Sentry

Buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties.

## Project Mission

Market_Sentry is a disciplined market observation tool that helps buyers identify residential properties with significant market exposure patterns. The system begins with candidate discovery, stages candidates for user review, and monitors selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, and cross-site validation.

## Current Milestone: Candidate Review Workflow (MVP 2)

This milestone implements the human-in-the-loop candidate review workflow.

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

**No live scraping or network calls are implemented yet. The system uses manually seeded sample data for testing the review workflow.**

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

### Review Workflow Commands (MVP 2)

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

### Complete Review Workflow Example

```bash
# 1. Initialize database
marketsentry init-database

# 2. Seed sample candidates
marketsentry seed-sample-candidates

# 3. Export candidates for review
marketsentry export-review

# 4. Edit the exported CSV file (data/exports/review_queue_*.csv)
#    Set user_decision column to: save, reject, maybe, or hold_for_more_data

# 5. Import reviewed decisions
marketsentry import-review --file data/exports/review_queue_20260504_123456.csv

# 6. View watched properties
marketsentry list-watched
```

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
│       ├── effective_dom.py   # Effective DOM calculation
│       ├── scoring.py         # Property scoring engine
│       ├── review_export.py   # Review queue export
│       └── review_import.py   # Review decision import
└── tests/                     # Unit tests
    ├── test_database.py
    ├── test_effective_dom.py
    ├── test_scoring.py
    ├── test_gas_detection.py
    └── test_quiet_vibrancy.py
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

### MVP 3: Redfin Candidate Discovery

- Implement compliant Redfin search page access
- Extract candidate property URLs from search results
- Parse property summary data (address, price, beds, baths, etc.)
- Collect Quiet/Vibrancy scores where available
- Detect garage spaces and gas service evidence
- Store candidates in review queue for user review
- No automated decisions - all candidates go through human review

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
- No network calls or live scraping are implemented in the current milestone.
- The system is designed for disciplined market observation, not automatic purchasing decisions.
- All scoring and filtering logic is deterministic and unit-tested.
