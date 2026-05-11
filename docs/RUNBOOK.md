# Market_Sentry Operating Runbook

This runbook explains how to use Market_Sentry for buyer-side real-estate market observation and watchlist management.

## Project Purpose

Market_Sentry is a local-first tool for observing residential property markets in the Temecula/Murrieta area. It helps buyers track candidate properties through discovery, review, and ongoing monitoring using saved web page fixtures and manual CSV imports.

Key capabilities:

- **Candidate Discovery**: Import properties from saved Redfin search pages or URL CSVs.
- **Candidate Review**: Export candidates for human review, import decisions, promote to watchlist.
- **Watchlist Monitoring**: Snapshot watched properties, detect changes over time.
- **Effective DOM**: Calculate listing exposure (v1 and v2 with county-verified reset).
- **Churn Index**: Measure recent 2-3 year property/listing instability.
- **Quiet/Vibrancy Scoring**: Evaluate property stability (high Quiet + low Vibrancy = target).
- **Cross-Site Validation**: Compare property data across Zillow, Realtor, Homes, Compass.
- **County Verification**: Import county recorder/assessor records for ownership transfer evidence.

## What This System Does Not Do

- **No live scraping or browser automation.** All data comes from manually saved HTML fixtures and CSV files.
- **No Playwright, Selenium, or active network retrieval.**
- **No purchase recommendations.** Reports are analytical aids for human review.
- **No walkability scoring** in the current scope.
- **No seller intent inference.** Language is neutral and analytical.

## Recommended Folder Layout

```text
Market_Sentry/
  db/
    marketsentry.db              # Main database
    demo_marketsentry.db         # Demo database (auto-created)
  data/
    raw/
      redfin/
        search/                  # Saved Redfin search result HTML pages
        details/                 # Saved Redfin property detail HTML pages
      cross_site/
        zillow/                  # Saved Zillow detail HTML pages
        realtor/                 # Saved Realtor detail HTML pages
        homes/                   # Saved Homes.com detail HTML pages
        compass/                 # Saved Compass detail HTML pages
      county/
        assessor/                # Saved county assessor HTML pages
        recorder/                # Saved county recorder HTML pages
    imports/
      redfin_urls.csv            # Redfin URLs for import
      cross_site_urls.csv        # Cross-site URLs for import
      county_records.csv         # County records for import
      reviewed_candidates.csv    # Reviewed candidate decisions
    exports/                     # Generated reports and summaries
    processed/                   # Intermediate processed data
  logs/
    marketsentry.log             # Application log
```

## How to Save Redfin Search Pages as Fixtures

1. Open a Redfin search results page in your browser (e.g., Temecula homes for sale).
2. Use your browser's "Save As" or "Save Page As" feature.
3. Choose "Webpage, HTML Only" format.
4. Save the file to `data/raw/redfin/search/` with a descriptive name (e.g., `temecula_search_20260505.html`).

## How to Save Redfin Detail Pages as Fixtures

1. Open a specific Redfin property detail page in your browser.
2. Use "Save Page As" and choose "Webpage, HTML Only".
3. Save the file to `data/raw/redfin/details/` (e.g., `12345_main_st_temecula.html`).

## How to Create/Import Redfin URL CSVs

Create a CSV file with at minimum a `url` column containing Redfin property URLs:

```csv
url,address,city,state,zip,price
https://www.redfin.com/CA/Temecula/12345-Main-St-92592/home/12345678,12345 Main St,Temecula,CA,92592,650000
```

Import it:

```bash
marketsentry import-redfin-urls --file data/imports/redfin_urls.csv
```

## How to Create/Import Cross-Site URL CSVs

Create a CSV with columns mapping properties to their cross-site URLs:

```csv
property_id,zillow_url,realtor_url,homes_url,compass_url
1,https://www.zillow.com/homedetails/...,https://www.realtor.com/realestateandhomes-detail/...,,
```

Import it:

```bash
marketsentry import-cross-site-urls --file data/imports/cross_site_urls.csv
```

## How to Save Cross-Site Detail Fixtures

1. For each watched property, open its listing on Zillow, Realtor.com, Homes.com, or Compass.
2. Save the HTML page to the appropriate subdirectory under `data/raw/cross_site/`.
3. Parse fixtures:

```bash
marketsentry parse-cross-site-fixtures --source zillow --dir data/raw/cross_site/zillow
```

## How to Create/Import County Records CSVs

Create a CSV with county record information:

```csv
property_id,record_type,record_date,grantor,grantee,document_number,sale_price,confidence
1,grant_deed,2024-01-15,Smith John,Doe Jane,2024-0012345,625000,high
```

Import it:

```bash
marketsentry import-county-records --file data/imports/county_records.csv
```

## How to Save County Fixtures

1. Save county assessor or recorder web pages as HTML to `data/raw/county/assessor/` or `data/raw/county/recorder/`.
2. Parse fixtures:

```bash
marketsentry parse-county-fixtures --source assessor --dir data/raw/county/assessor
```

## Running the Initial Review Workflow

The initial review workflow prepares candidates for human review:

```bash
# Run with all options
marketsentry run-initial-review-workflow \
  --redfin-urls-file data/imports/redfin_urls.csv \
  --redfin-search-dir data/raw/redfin/search \
  --redfin-details-dir data/raw/redfin/details \
  --output-dir data/exports

# Run with just database defaults (skips optional inputs)
marketsentry run-initial-review-workflow
```

This workflow:
1. Initializes/migrates the database.
2. Imports Redfin URLs if file provided.
3. Parses Redfin search fixtures if directory provided.
4. Enriches candidates from detail fixtures if directory provided.
5. Recalculates candidate metrics (Effective DOM, scoring).
6. Persists Effective DOM v2 metrics.
7. Exports a candidate review CSV.
8. Exports a candidate analysis report.
9. Generates a workflow summary.

## How to Review Candidate CSV

1. Open the exported `candidate_review_*.csv` in a spreadsheet editor.
2. Review each candidate row.
3. In the `user_decision` column, enter one of:
   - `save` - Add to watchlist for ongoing monitoring.
   - `reject` - Not interested.
   - `maybe` - Uncertain, keep for later review.
   - `hold_for_more_data` - Need more information.
4. Optionally add notes in the `user_notes` column.
5. Save the CSV file.

## How to Import Reviewed Candidates

```bash
marketsentry import-review --file data/imports/reviewed_candidates.csv
```

Properties marked `save` are automatically promoted to the watchlist.

## Running the Watchlist Refresh Workflow

The watchlist refresh updates existing watched properties:

```bash
marketsentry run-watchlist-refresh-workflow \
  --redfin-details-dir data/raw/redfin/details \
  --cross-site-root-dir data/raw/cross_site \
  --county-records-file data/imports/county_records.csv \
  --output-dir data/exports
```

This workflow:
1. Initializes/migrates the database.
2. Enriches candidates from Redfin detail fixtures.
3. Parses cross-site fixtures (Zillow, Realtor, Homes, Compass).
4. Imports county records or parses county fixtures.
5. Persists Effective DOM v2 metrics.
6. Creates watchlist monitoring snapshots.
7. Exports watchlist monitoring report.
8. Exports Effective DOM v2 report.
9. Exports county verification report.
10. Generates a workflow summary.

## Running the Fixture Demo Workflow

Run a demonstration with sample data:

```bash
marketsentry run-fixture-demo-workflow --reset-demo-db
```

This uses a separate demo database and seeds sample candidates for testing.

## Checking Workflow Status

```bash
marketsentry workflow-status
```

Shows database table counts and latest exported reports.

## Using the Local Dashboard

The local dashboard provides a browser-based interface for reviewing all Market_Sentry data.

### Requirements

Install Streamlit if not already installed:

```bash
pip install streamlit
```

### Launching the Dashboard

```bash
# Via CLI command
marketsentry launch-dashboard

# Or directly with Streamlit
streamlit run src/marketsentry/dashboard_app.py

# Custom port
marketsentry launch-dashboard --port 8502
```

The dashboard opens in your default browser at `http://localhost:8501`.

### Dashboard Summary (No Browser)

For a quick text-based summary without opening a browser:

```bash
marketsentry dashboard-summary
```

### Dashboard Sections

- **Overview**: Summary counts for candidates, watched properties, snapshots, county resets, churn, and quiet gatekeeper failures.
- **Candidate Review**: Filterable table of all candidates with scoring, gatekeeper results, gas service, DOM, and churn columns. Use sidebar filters to narrow by recommendation, decision, gas service, quiet/vibrancy thresholds, and churn index.
- **Watchlist**: Filterable table of watched properties with priority, active status, v1/v2 DOM, and churn. Filter by priority, active status, quiet score, churn threshold, and county reset.
- **Monitoring**: Latest monitoring report showing price/status/DOM changes across snapshots.
- **Effective DOM v2**: v1 vs v2 comparison with county reset dates and churn preservation.
- **County Verification**: County recorder/assessor evidence for watched properties.
- **Cross-Site Review**: Price, status, and DOM discrepancy flags across Zillow, Realtor, Homes, Compass.
- **Reports**: Report manifest showing all generated reports with timestamps and row counts.
- **Workflow Summaries**: Preview of workflow summary markdown files from previous runs.

### What the Dashboard Does Not Do

- The dashboard does not scrape websites or make network calls.
- The dashboard does not make purchase recommendations.
- The dashboard does not infer seller intent.
- All data comes from the local SQLite database and CSV reports.

## How to Interpret Reports

### Candidate Analysis Report

- **quiet_score**: Stability score (0-10). Higher is better. Target: 8+.
- **vibrancy_score**: Activity/instability score (0-10). Lower is better. Target: below 2.5.
- **review_recommendation**: System recommendation (strong_candidate, worth_reviewing, needs_review, not_recommended).
- **effective_dom / effective_dom_delta**: Listing exposure in days.
- **gas_service**: Whether natural gas is available (any mention of gas = yes).
- **garage_spaces**: Number of garage spaces.

### Watchlist Monitoring Report

- Shows current vs. previous snapshot values.
- Detects changes in price, listing status, DOM.
- Includes v2 metrics and Churn Index.

### Effective DOM v2 Report

- Compares v1 (no county reset) vs. v2 (county-verified reset).
- Shows county_reset_applied, reset_date, reset_confidence.
- Churn Index remains visible even when county reset is applied.

### County Verification Report

- Shows county record evidence for each watched property.
- Includes transfer dates, record types, confidence levels.

## Effective DOM v1 vs v2

- **v1**: Calculates listing exposure from listing history only, without county records.
- **v2**: Applies county-confirmed ownership transfer as a reset boundary when evidence supports it.
- v1 is always preserved alongside v2 for comparison.
- Run `marketsentry persist-effective-dom-v2` to update v2 metrics after importing new county records.

## Churn Index

- Measures recent 2-3 year property/listing instability.
- Counts listing events, DOM resets, sale/rent alternations within the lookback window.
- **Not affected by county reset.** Even when Effective DOM is reset by ownership transfer, churn history is preserved.
- High churn is a review signal, not a rejection. It means the property has seen notable listing activity recently.

## How Quiet/Vibrancy Gatekeeper Works

- **Quiet Score is the gatekeeper.** Properties below the minimum Quiet Score threshold (default: 7.0) are rejected or heavily downgraded regardless of other factors.
- Target: very high Quiet (8+) AND very low Vibrancy (below 2.5).
- Low Vibrancy alone is not sufficient. Quiet must also be high.
- The system will not recommend a property that fails the Quiet gatekeeper, even if all other metrics look favorable.

## Windows Task Scheduler Automation

Market_Sentry supports scheduled execution of local workflows using Windows Task Scheduler.

### Checking Automation Status

```bash
marketsentry automation-status
```

Shows project root, Python executable, virtualenv, database path, available scripts, and latest scheduled log.

### Running Workflows Manually via Scripts

```cmd
cd C:\Users\Minis\CascadeProjects\Market_Sentry

REM Run watchlist refresh
scripts\run_watchlist_refresh_workflow.bat

REM Run dashboard summary
scripts\run_dashboard_summary.bat

REM Run initial review
scripts\run_initial_review_workflow.bat

REM Run fixture demo
scripts\run_fixture_demo_workflow.bat
```

### Installing the Weekly Scheduled Task

```powershell
# Default: weekly Saturday 9:00 AM
powershell -ExecutionPolicy Bypass -File scripts\install_task_scheduler_watchlist_refresh.ps1

# Custom day and time
powershell -ExecutionPolicy Bypass -File scripts\install_task_scheduler_watchlist_refresh.ps1 -DayOfWeek Monday -Time "08:00"
```

### Removing the Scheduled Task

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall_task_scheduler_watchlist_refresh.ps1
```

### Scheduled Logs

Logs are written to `logs/scheduled/` with timestamped filenames:

```text
logs/scheduled/watchlist_refresh_20260506_090000.log
logs/scheduled/dashboard_summary_20260505_143000.log
```

### What Scheduled Tasks Do NOT Do

- No live web scraping or network calls.
- No Playwright, Selenium, or browser automation.
- No purchase recommendations.
- All tasks operate on local data only.

See [docs/WINDOWS_TASK_SCHEDULER.md](WINDOWS_TASK_SCHEDULER.md) for the complete automation guide.

## Live Retrieval Strategy

Market_Sentry includes a compliance-aware source adapter architecture for future live data retrieval. **Live retrieval is disabled by default.**

### Checking Compliance Status

```bash
marketsentry retrieval-compliance-status
```

Shows whether live retrieval is blocked, allowed sources, User-Agent, rate limits, and warnings.

### Dry-Run Preview Commands

```bash
# Preview Redfin search retrieval (no network call)
marketsentry dry-run-redfin-search --url "https://www.redfin.com/city/19701/CA/Temecula/filter/..."

# Preview Redfin property detail retrieval (no network call)
marketsentry dry-run-redfin-property --url "https://www.redfin.com/CA/Temecula/.../home/6574263"

# List all registered source adapters
marketsentry source-adapters
```

### Retrieval Audit Logs

All retrieval decisions are logged to `logs/retrieval_audit/` as CSV files. Each record shows whether a request was allowed or blocked and whether a network call was performed.

### Enabling Live Retrieval (Future)

Live retrieval requires explicit environment variable configuration:

```ini
MARKETSENTRY_LIVE_RETRIEVAL_ENABLED=true
MARKETSENTRY_ALLOWED_LIVE_SOURCES=redfin
MARKETSENTRY_LIVE_USER_AGENT=MarketSentry/1.0
MARKETSENTRY_LIVE_CONTACT_EMAIL=user@example.com
MARKETSENTRY_MAX_REQUESTS_PER_MINUTE=6
```

See [LIVE_RETRIEVAL_STRATEGY.md](LIVE_RETRIEVAL_STRATEGY.md) for the complete retrieval strategy guide.

## Fixture Capture Queue

The fixture capture queue tracks URLs that need manual HTML fixture capture. When live retrieval is blocked, the system adds URLs to a local queue and tells you where to save the files.

### Listing Pending Requests

```bash
marketsentry list-fixture-capture-queue
```

### Exporting the Queue

```bash
marketsentry export-fixture-capture-queue
```

### Marking a Request as Captured

After saving the HTML file manually:

```bash
marketsentry mark-fixture-captured --capture-request-id 1 --fixture-path "data/raw/redfin/details/my_property.html"
```

### Checking Retrieval Policy

```bash
marketsentry retrieval-policy-check --source redfin --url "https://www.redfin.com/..." --mode live_http
```

### Retrieval Audit Report

```bash
marketsentry retrieval-audit-report
```

See [FIXTURE_CAPTURE_QUEUE.md](FIXTURE_CAPTURE_QUEUE.md) for the complete fixture capture queue guide.

## Redfin Live HTTP Retrieval Phase 1

Market_Sentry supports optional live HTTP retrieval for Redfin pages only. **Live retrieval is disabled by default** and requires explicit configuration.

### Prerequisites

1. Set environment variables:

```ini
MARKETSENTRY_LIVE_RETRIEVAL_ENABLED=true
MARKETSENTRY_ALLOWED_LIVE_SOURCES=redfin
MARKETSENTRY_LIVE_USER_AGENT=MarketSentry/1.0
MARKETSENTRY_LIVE_CONTACT_EMAIL=user@example.com
MARKETSENTRY_MAX_REQUESTS_PER_MINUTE=6
```

2. Save local robots policy:

```bash
# Manually save https://www.redfin.com/robots.txt to:
data/policies/robots/redfin_robots.txt
```

3. Run dry-run first:

```bash
marketsentry dry-run-redfin-search --url "https://www.redfin.com/city/..."
marketsentry dry-run-redfin-property --url "https://www.redfin.com/CA/..."
```

### Performing Live Retrieval

```bash
# Retrieve a search page
marketsentry retrieve-redfin-search --url "https://www.redfin.com/city/..." --force-live

# Retrieve a property detail page
marketsentry retrieve-redfin-property --url "https://www.redfin.com/CA/..." --force-live

# Dry-run only (no network call)
marketsentry retrieve-redfin-search --url "..." --dry-run-only
marketsentry retrieve-redfin-property --url "..." --dry-run-only
```

### What Happens After Retrieval

Retrieved HTML is saved as a local fixture file with a sidecar metadata JSON. Parse it with existing commands:

```bash
marketsentry parse-redfin-fixtures --dir data/raw/redfin/search
marketsentry enrich-redfin-details --dir data/raw/redfin/details
```

### What Live Retrieval Does NOT Do

- No browser automation, Playwright, Selenium, or JavaScript execution.
- No CAPTCHA bypass, login bypass, or anti-bot bypass.
- No scheduled tasks invoke live retrieval by default.
- No direct database mutation (retrieved HTML is saved as fixtures first).

See [REDFIN_LIVE_HTTP_PHASE_1.md](REDFIN_LIVE_HTTP_PHASE_1.md) for the complete guide.

## Processing Retrieved Redfin Fixtures

After retrieving or manually saving Redfin HTML fixtures, process them through the local parsing pipeline:

### Process All Fixtures

```bash
marketsentry process-redfin-retrieved-fixtures
```

This command:

1. Parses search fixtures and inserts candidates.
2. Parses detail fixtures and enriches candidates.
3. Recalculates Effective DOM metrics.
4. Persists Effective DOM v2.
5. Exports candidate review and analysis reports.
6. Marks matching fixture capture queue items as captured.

### Process Search Fixtures Only

```bash
marketsentry process-redfin-search-fixtures --search-dir data/raw/redfin/search
```

### Process Detail Fixtures Only

```bash
marketsentry process-redfin-detail-fixtures --details-dir data/raw/redfin/details
```

### Retrieve and Process in One Step

```bash
marketsentry retrieve-and-process-redfin-property --url "https://www.redfin.com/CA/..." --force-live
```

### Processing Manifest

The manifest at `data/processed/redfin_fixture_processing_manifest.csv` tracks which fixtures have been processed. By default, unchanged fixtures (same content hash) are skipped. Use `--force-reprocess` to override.

### No Live Retrieval in Processing

Processing reads only local files. No network calls are made during processing.

See [REDFIN_RETRIEVED_FIXTURE_PROCESSING.md](REDFIN_RETRIEVED_FIXTURE_PROCESSING.md) for the complete guide.

## Redfin Pending Capture Batch Retrieval

The batch orchestrator processes pending fixture capture queue items for Redfin one at a time with full policy enforcement.

### Dry-Run Pending Items

```bash
# Preview all pending Redfin capture requests (no network calls)
marketsentry dry-run-pending-redfin-fixtures

# Filter by type or limit count
marketsentry dry-run-pending-redfin-fixtures --request-type search --max-items 5
```

### Retrieve Pending Items

```bash
# Retrieve pending items (requires full config + --force-live)
marketsentry retrieve-pending-redfin-fixtures --force-live

# Retrieve and process through parsing pipeline
marketsentry retrieve-pending-redfin-fixtures --force-live --process-after-retrieval

# Without --force-live: prints safe explanation, no network calls
marketsentry retrieve-pending-redfin-fixtures
```

### Batch Manifests

- Batch manifest: `data/processed/redfin_batch_retrieval_manifest.csv`
- Per-item manifest: `data/processed/redfin_batch_retrieval_items.csv`

### What Batch Retrieval Does NOT Do

- No scheduled tasks invoke batch retrieval by default.
- No browser automation or bypass mechanisms.
- Default mode is dry-run only.
- `--force-live` is required for any network calls.

See [REDFIN_PENDING_CAPTURE_BATCH_RETRIEVAL.md](REDFIN_PENDING_CAPTURE_BATCH_RETRIEVAL.md) for the complete guide.

## Redfin Retrieval Approval Workflow

The approval workflow adds a two-step human review process before batch live retrieval.

### Step 1: Prepare Approval Package

```bash
marketsentry prepare-redfin-retrieval-approval
marketsentry prepare-redfin-retrieval-approval --max-items 10
marketsentry prepare-redfin-retrieval-approval --request-type property_detail
```

This dry-runs pending Redfin capture items and writes an approval CSV with `approved_for_live=false`. No network calls are made.

### Step 2: Review and Approve

Open the approval CSV in a spreadsheet editor. For items you want to retrieve, change `approved_for_live` from `false` to `true`. Save the CSV.

### Step 3: Retrieve Approved Items

```bash
# Retrieve approved items only
marketsentry retrieve-approved-redfin-batch \
    --approval-file "data/exports/retrieval_approvals/redfin_batch_approval_<run_id>.csv" \
    --force-live

# Retrieve and process
marketsentry retrieve-approved-redfin-batch \
    --approval-file "data/exports/retrieval_approvals/redfin_batch_approval_<run_id>.csv" \
    --force-live --process-after-retrieval

# Validate and preview only
marketsentry retrieve-approved-redfin-batch \
    --approval-file "data/exports/retrieval_approvals/redfin_batch_approval_<run_id>.csv" \
    --dry-run-only
```

### Approval Safety Rules

- `approved_for_live` defaults to `false` for every item.
- `--force-live` is required for network calls.
- All policy checks are re-evaluated at retrieval time.
- URL and capture request must still match the queue.
- No scheduled scripts invoke approved retrieval.

See [REDFIN_RETRIEVAL_APPROVAL_WORKFLOW.md](REDFIN_RETRIEVAL_APPROVAL_WORKFLOW.md) for the complete guide.

## Retrieval Operations Dashboard

The Retrieval Operations Dashboard provides read-only visibility into the retrieval ecosystem.

### Dashboard

Open the Streamlit dashboard and navigate to "Retrieval Operations":

```bash
streamlit run src/marketsentry/dashboard_app.py
```

Subsections: Overview, Fixture Capture Queue, Approval Packages, Batch Retrieval Runs, Per-Item Results, Retrieval Audit, Retrieved Fixtures.

### CLI Summary

```bash
marketsentry retrieval-operations-summary
```

Shows capture queue counts, approval packages, batch runs, audit decisions, safety configuration, and latest files.

### Export Report

```bash
# Markdown report
marketsentry export-retrieval-operations-report

# CSV report
marketsentry export-retrieval-operations-report --format csv
```

Reports are saved to `data/exports/`.

### What It Shows

- Fixture capture queue status (pending, captured, skipped, invalid, archived)
- Approval package manifest and latest CSV files
- Batch retrieval manifest and per-item results
- Retrieval audit log summary (allowed, blocked, dry-run, network call counts)
- Retrieved fixture inventory with metadata and processing status
- Safety configuration (live retrieval enabled, allowed sources, User-Agent, rate limits)

The dashboard is read-only. No retrieval actions are triggered from it.

## Retrieval Health Checks

Health checks surface stale items, missing configuration, audit anomalies, and next recommended actions.

### Run Health Checks

```bash
marketsentry retrieval-health-check
```

Shows issue counts by severity, stale capture requests, stale approval packages, unprocessed fixtures, missing policy files, audit anomalies, and next actions.

### Export Health Report

```bash
# Markdown report
marketsentry export-retrieval-health-report

# CSV report
marketsentry export-retrieval-health-report --format csv
```

Reports are saved to `data/exports/retrieval_health_YYYYMMDD_HHMMSS.md` or `.csv`.

### What Is Checked

- **Stale capture requests**: Pending items older than 7 days (configurable)
- **Stale approval packages**: Packages with unretrieved approved rows older than 24 hours
- **Unprocessed fixtures**: Retrieved HTML files not yet in the processing manifest, older than 24 hours
- **Missing policy files**: Missing `data/policies/robots/redfin_robots.txt` when live retrieval is enabled or capture queue has pending items
- **Missing config**: Live retrieval enabled but User-Agent or contact email not set
- **Audit anomalies**: Any `network_call_performed=true` in audit logs (critical)
- **Repeated blocks**: URLs blocked 3+ times in batch retrieval items

### Severity Levels

| Severity | Meaning |
|----------|---------|
| info | Informational, no action needed |
| warning | Stale items or minor config gaps |
| error | Missing required config when live retrieval is enabled |
| critical | Unexpected network calls in audit logs |

### Dashboard

The Health Checks tab in the Retrieval Operations dashboard section shows issue counts, the issues table, and next actions.

Health checks are read-only. No write or mutation actions.

## Cross-Site Manual Fixture Workflow

Non-Redfin sources (Zillow, Realtor.com, Homes.com, Compass) support manual fixture workflows only. No live retrieval is implemented for these sources.

### Dry-Run Cross-Site Property

Preview a cross-site property URL:

```bash
marketsentry dry-run-cross-site-property --source zillow --url "https://www.zillow.com/homedetails/..."
marketsentry dry-run-cross-site-property --source realtor --url "https://www.realtor.com/realestateandhomes-detail/..."
marketsentry dry-run-cross-site-property --source homes --url "https://www.homes.com/property/..."
marketsentry dry-run-cross-site-property --source compass --url "https://www.compass.com/listing/..."
```

No network calls are performed. The dry-run creates a fixture capture queue request.

### Save Cross-Site Fixtures

Save property detail pages as HTML to:

- `data/raw/zillow/details/`
- `data/raw/realtor/details/`
- `data/raw/homes/details/`
- `data/raw/compass/details/`

### Process Cross-Site Fixtures

```bash
# Process all sources
marketsentry process-cross-site-fixtures

# Process one source
marketsentry process-cross-site-source-fixtures --source zillow

# Force reprocess unchanged files
marketsentry process-cross-site-fixtures --force-reprocess
```

### Processing Manifest

The append-only manifest at `data/processed/cross_site_fixture_processing_manifest.csv` tracks all processing results with content hashes for deduplication.

### Cross-Site Dashboard and Health Checks

The Retrieval Operations dashboard includes a "Cross-Site Fixtures" tab showing manifest data, source breakdown, errors, and unprocessed fixture warnings.

Health checks include unprocessed cross-site fixture warnings and stale cross-site capture request warnings.

See [CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md](CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md) for the complete guide.

## Cross-Site Parser Quality

Milestone 23 improved cross-site parser extraction, normalization, and confidence scoring for all four non-Redfin sources (Zillow, Realtor.com, Homes.com, Compass).

### Parse Confidence Levels

Each cross-site parse result includes a confidence level:

| Confidence | Meaning |
| ---------- | ------- |
| high | Address extracted and at least price/status/property facts present |
| medium | Address extracted and some facts present, but important fields missing |
| low | Sparse or uncertain parse (missing address or minimal useful data) |

### Missing Required Fields

The parser tracks which required fields are absent from a given parse:

- address
- price
- listing_status
- beds
- baths
- sqft

Missing fields are listed in the `missing_required_fields` attribute and stored as parse warnings.

### Parse Warnings

Parse warnings are diagnostic messages attached to observations. They indicate extraction issues such as missing fields, ambiguous values, or format problems. Warnings do not prevent insertion but are visible in reports.

### How to Interpret Parse Quality in Reports

The cross-site comparison report includes:

- **lowest_parse_confidence**: The lowest confidence level across all source observations for a property. If this is "low", treat the cross-site data with caution.
- **sources_with_parse_warnings**: Which sources had parse warnings.
- **sources_with_partial_parse**: Which sources had partial (not fully successful) parses.

### Recommended Manual Review for Low-Confidence Parses

When a cross-site observation has **low** confidence:

1. Check the saved HTML fixture to confirm it contains property data.
2. Re-save the page if it was a temporary error page or redirect.
3. Do not weight low-confidence cross-site data equally in comparison analysis.
4. Consider the observation informational only until a higher-confidence parse is available.

### Normalization

Parsers normalize common format variations:

- **Price**: $850,000 / $850K / $1.2M / 850000
- **Sqft**: "2,450 sqft" / "2450 square feet"
- **Lot size**: "0.25 acres" / "7,405 sqft lot" (normalized to acres)
- **DOM**: "12 days on market" / "Listed 45 days ago" / "On site 17 days"
- **Status**: active / pending / contingent / sold / off market / coming soon
- **Garage**: "3-car garage" / "2 garage spaces" / "attached garage"
- **Gas evidence**: gas fireplace / gas range / natural gas / gas dryer hookup / gas heating

### Cross-Site Data Remains Validation-Only

Cross-site observations validate and compare against Redfin source-of-truth data. They do not overwrite:

- `user_decision`
- `user_notes`
- `active_watch_status`
- `watch_priority`
- Redfin-sourced property facts (price, beds, baths, sqft, etc.)

## Cross-Site Analytics

Milestone 24 added confidence-weighted cross-site comparison analytics that weight observations by parse confidence, data freshness, and field completeness.

### Confidence-Weighted Scoring

Source observations are assigned a combined weight based on three factors:

- **Confidence weight**: high=1.0, medium=0.7, low=0.4, failed=0.0
- **Freshness weight**: 0-7 days=1.0, 8-30 days=0.8, 31-90 days=0.5, >90 days=0.2
- **Completeness weight**: fraction of required fields (price, status, beds, baths, sqft) present

The combined weight is the product of all three factors. A high-confidence, recent, complete observation has weight 1.0. A low-confidence, stale, incomplete observation has a much lower weight.

### Agreement Scores

For each field (price, status, DOM, garage, gas), a weighted agreement score indicates how well cross-site sources agree with Redfin:

- **1.0**: All weighted sources agree with Redfin
- **0.0**: No sources agree, or no Redfin baseline

### Discrepancy Severity

Neutral severity levels describe the magnitude of cross-site data disagreement:

| Severity | Meaning |
| -------- | ------- |
| none | No discrepancy detected |
| low | Minor difference (price >$10k, gas/garage disagreement) |
| medium | Moderate difference (price >$25k, DOM >30 days, or low-conf status conflict) |
| high | Significant conflict (price >$50k, active vs sold/pending, DOM >90 days) |
| critical | Reserved for extreme cases |

Low-confidence sources reduce severity certainty rather than exaggerating it.

### Manual Review Priority

| Priority | Trigger |
| -------- | ------- |
| high | High or critical discrepancy severity |
| medium | Medium severity, or low severity with low-confidence sources |
| low | Low severity, or no discrepancy with stale/low-confidence sources |
| none | No discrepancy and all sources are reliable |

### Generating the Analytics Report

```bash
marketsentry export-cross-site-analytics-report
```

Output: `data/exports/cross_site_analytics_YYYYMMDD_HHMMSS.csv`

### Overall Cross-Site Confidence Score

The overall score combines freshness (25%), completeness (25%), and agreement (50%). Higher scores indicate more reliable cross-site validation data.

### Cross-Site Analytics in Dashboard

The Cross-Site Review section of the dashboard includes an analytics subsection showing overall confidence, severity labels, review priority, and source quality flags.

## Cross-Site Analytics Trend Snapshots

Milestone 25 adds point-in-time snapshot persistence for cross-site analytics. Snapshots track how analytics change over time for each watched property.

### Creating Trend Snapshots

```bash
# Create snapshots for all active watched properties
marketsentry snapshot-cross-site-analytics

# Force snapshot even when no material change detected
marketsentry snapshot-cross-site-analytics --force
```

Snapshots are stored in the `cross_site_analytics_snapshots` table and are append-only. By default, a new snapshot is only created when a material change is detected:

- Discrepancy severity label changed
- Manual review priority changed
- Overall confidence score changed by >= 0.10
- Agreement score (price, status, DOM) changed by >= 0.10
- Low-confidence or stale source count changed
- Discrepancy flag (price, status, DOM) changed

### Exporting Trend Reports

```bash
# Export trend report comparing current vs previous snapshots
marketsentry export-cross-site-trend-report

# Export to a specific directory
marketsentry export-cross-site-trend-report --output-dir data/exports
```

The trend report CSV includes current and previous analytics values, change deltas, trend direction (improving/degrading/stable), and recommended next actions.

### Trend Direction Classification

- **improving**: Confidence increasing, severity decreasing, or agreement scores improving
- **degrading**: Confidence decreasing, severity increasing, or agreement scores degrading
- **stable**: No significant changes detected

### Cross-Site Trends in Dashboard

The Cross-Site Review section of the dashboard includes a trends subsection showing trend direction distribution, severity and priority change counts, and per-property trend data.

## Cross-Site Trend Alerts

Milestone 26 generates alerts from cross-site analytics trend snapshot comparisons. Alerts flag material changes that need human review.

### Generating Alerts

```bash
# Generate alerts for all active watched properties
marketsentry generate-cross-site-trend-alerts
```

Alerts are generated by comparing the latest and previous cross-site analytics snapshots. Each property is evaluated against 12 centralized rules covering confidence, severity, priority, agreement scores, and source counts.

### Alert Types

| Alert Type | Trigger | Default Severity |
| --- | --- | --- |
| confidence_drop | Confidence dropped >= 0.10 | warning (>= 0.25: high) |
| confidence_improvement | Confidence improved >= 0.10 | info |
| severity_increase | Discrepancy severity increased | warning (to high: high, to critical: critical) |
| severity_decrease | Discrepancy severity decreased | info |
| manual_review_priority_increase | Review priority increased | high |
| manual_review_priority_decrease | Review priority decreased | info |
| price_agreement_degraded | Price agreement dropped >= 0.25 | warning/high |
| status_agreement_degraded | Status agreement dropped >= 0.25 | high |
| dom_agreement_degraded | DOM agreement dropped >= 0.25 | warning |
| stale_sources_increased | Stale source count increased | warning |
| low_confidence_sources_increased | Low-confidence source count increased | warning |
| source_quality_improved | Stale or low-confidence count decreased | info |

### Alert Severity Levels

- **info**: Positive or neutral change, no action needed
- **warning**: Moderate change, monitor for further trends
- **high**: Significant change, review cross-site data
- **critical**: Severe change, validate against Redfin source

### Managing Alerts

```bash
# List open alerts (default)
marketsentry list-cross-site-trend-alerts

# List alerts with filters
marketsentry list-cross-site-trend-alerts --status open --severity high
marketsentry list-cross-site-trend-alerts --property-id 42

# Acknowledge an alert
marketsentry acknowledge-cross-site-trend-alert --alert-id 1 --notes "Reviewed"

# Resolve an alert
marketsentry resolve-cross-site-trend-alert --alert-id 1 --notes "Data corrected"
```

### Exporting Alert Reports

```bash
# Export all alerts to CSV
marketsentry export-cross-site-trend-alerts-report

# Export with output directory
marketsentry export-cross-site-trend-alerts-report --output-dir data/exports

# Export only acknowledged alerts
marketsentry export-cross-site-trend-alerts-report --status acknowledged
```

### Alert Lifecycle

Alerts follow this lifecycle:

1. **open**: Alert generated, needs human review
2. **acknowledged**: Operator has seen the alert
3. **resolved**: Operator has addressed the alert
4. **archived**: Alert is no longer relevant

### Cross-Site Trend Alerts in Dashboard

The Cross-Site Review section of the dashboard includes a trend alerts subsection showing open alert count, severity distribution, latest alert date, status filters, and the full alert table with recommended actions.

### Watchlist Monitoring Integration

Alert summary fields are available per property for integration with watchlist monitoring reports:

- `open_cross_site_alert_count`
- `highest_cross_site_alert_severity`
- `latest_cross_site_alert_type`
- `latest_cross_site_alert_message`
- `cross_site_alert_recommended_action`

These fields are informational only. They do not change watchlist status or Quiet Score gatekeeper results.

### Reminder: Alerts Are Review Signals

Cross-site trend alerts are analytical review signals for human operators. They are not purchase recommendations and do not infer seller intent. Alerts do not overwrite Redfin source-of-truth fields, user decisions, or watchlist status.

## Cross-Site Alert Analytics

Milestone 27 aggregates individual cross-site trend alerts (Milestone 26) into property-level burden metrics and repeated discrepancy patterns. These are neutral analytical review signals for watchlist review.

### Viewing Alert Analytics Summary

```bash
# Show summary of alert burden across all properties
marketsentry cross-site-alert-analytics-summary

# Specify a database
marketsentry cross-site-alert-analytics-summary --db db/marketsentry.db
```

The summary shows total properties with alerts, open/high-critical counts, repeated patterns, top alert types, top properties by burden, oldest open alert, and recommended next actions.

### Exporting Alert Analytics Report

```bash
# Export analytics report to CSV
marketsentry export-cross-site-alert-analytics-report

# Specify output directory
marketsentry export-cross-site-alert-analytics-report --output-dir data/exports

# Exclude resolved alerts
marketsentry export-cross-site-alert-analytics-report --include-resolved false
```

The report includes: property_id, address, city, zip, total/open/high-critical alert counts, oldest open alert age, latest alert timestamp, most common type/severity, repeated patterns, burden score/label, recommended review action, unresolved alert types, resolved/acknowledged counts.

### Alert Burden Levels

| Burden Label | Criteria |
| --- | --- |
| none | No open alerts |
| low | 1-2 low/warning open alerts |
| moderate | 3+ open alerts or any high open alert |
| high | 2+ high/critical open alerts or any critical open alert |
| elevated_review | Repeated high/critical alerts from different snapshots |

Burden scoring: each open alert = 1.0 x severity weight, acknowledged = 0.5 x weight, resolved = 0.1 x weight. Severity weights: info=1, warning=2, high=4, critical=8.

### Repeated Alert Patterns

Patterns require at least 2 matching events:

| Pattern Type | Trigger |
| --- | --- |
| repeated_confidence_drop | 2+ confidence_drop alerts |
| repeated_status_discrepancy | 2+ status_agreement_degraded alerts |
| repeated_price_agreement_degraded | 2+ price_agreement_degraded alerts |
| repeated_dom_agreement_degraded | 2+ dom_agreement_degraded alerts |
| repeated_stale_sources | 2+ stale_sources_increased alerts |
| repeated_low_confidence_sources | 2+ low_confidence_sources_increased alerts |
| recurring_high_severity_alerts | 2+ high/critical alerts of any type |
| improving_source_quality_pattern | 2+ source_quality_improved alerts |

### Cross-Site Alert Analytics in Dashboard

The Cross-Site Review section of the dashboard includes an alert analytics subsection showing top properties by alert burden, open high/critical counts, repeated patterns table, burden labels, recommended review actions, and resolved vs open counts.

### Alert Analytics Watchlist Monitoring Fields

Alert analytics fields are available per property for watchlist monitoring reports:

- `cross_site_alert_burden_label`
- `cross_site_alert_burden_score`
- `cross_site_repeated_patterns`
- `cross_site_oldest_open_alert_age_days`

These fields are informational only. They do not change watchlist status, active_watch_status, or Quiet Score gatekeeper results.

### Reminder: Analytics Are Review Aids

Cross-site alert analytics are analytical review aids for human operators. They are not purchase recommendations and do not infer seller intent. Analytics do not overwrite Redfin source-of-truth fields, user decisions, or watchlist status.

## Cross-Site Alert Triage Workflow

Milestone 28 provides a CSV-based triage workflow for managing accumulated cross-site trend alerts. Operators export alerts, edit triage decisions offline, and import decisions to batch-update alert statuses.

### Exporting Triage CSV

```bash
# Export open alerts to triage CSV (default: open only)
marketsentry export-cross-site-alert-triage

# Include acknowledged alerts
marketsentry export-cross-site-alert-triage --include-acknowledged

# Filter by severity
marketsentry export-cross-site-alert-triage --severity high

# Filter by property
marketsentry export-cross-site-alert-triage --property-id 42

# Specify output directory
marketsentry export-cross-site-alert-triage --output-dir data/exports
```

The export creates a CSV with columns for alert details, burden context, and editable triage fields: `triage_decision` and `triage_notes`.

### Editing Triage Decisions

Open the exported CSV in a spreadsheet editor. For each row, set the `triage_decision` column to one of:

| Decision | Effect |
| --- | --- |
| keep_open | No status change (default) |
| acknowledge | Changes alert_status to acknowledged |
| resolve | Changes alert_status to resolved |
| archive | Changes alert_status to archived |
| needs_reparse | No status change; records note for fixture re-parse |
| needs_manual_review | No status change; records note for manual review |

Only `acknowledge`, `resolve`, and `archive` change the alert status. The others record notes for operator tracking without modifying alert state.

Optionally add notes in the `triage_notes` column.

### Importing Triage Decisions

```bash
# Import and apply decisions
marketsentry import-cross-site-alert-triage --file data/exports/cross_site_alert_triage_*.csv

# Force apply even if alert status has changed since export
marketsentry import-cross-site-alert-triage --file <path> --force-status-mismatch
```

The import validates each row:

- Alert ID must exist in the database
- Triage decision must be one of the 6 allowed values
- Current alert status must match what was exported (unless `--force-status-mismatch`)
- Invalid rows are skipped and reported

### Triage History

All triage actions are recorded in the `cross_site_alert_triage_actions` table for audit purposes. Each record includes the triage export ID, alert ID, previous and new status, action taken, and notes.

### Cross-Site Alert Triage in Dashboard

The Cross-Site Review section of the dashboard includes a triage subsection showing open/acknowledged/resolved/archived counts, needs_reparse and needs_manual_review counts, triage action history count, and the latest triage export table.

### Reminder: Triage Is Operational Alert Management

Triage actions are operational changes to alert status. They do not modify watchlist state, Redfin source-of-truth fields, user decisions, Quiet Score gatekeeper results, or any property data. Triage is not a purchase recommendation and does not infer seller intent.

## Cross-Site Alert Hygiene Reports

Alert hygiene reports identify alerts that may need attention. They are review aids only and do not auto-archive alerts, change watchlist status, or modify Quiet Score gatekeeper results.

### Running a Hygiene Check

```bash
marketsentry cross-site-alert-hygiene-check
```

This command scans all cross-site trend alerts and identifies:

- **Stale open alerts** - open alerts older than 7 days (configurable via `--open-stale-days`)
- **Stale acknowledged alerts** - acknowledged alerts older than 14 days (configurable via `--ack-stale-days`)
- **Resolved archive candidates** - resolved alerts older than 30 days (configurable via `--resolved-archive-days`)
- **Needs reparse pending** - alerts marked needs_reparse that are still open/acknowledged
- **Needs manual review pending** - alerts marked needs_manual_review that are still open/acknowledged
- **High-burden properties** - properties with high or elevated_review alert burden
- **Repeated unresolved patterns** - properties with 2+ unresolved alerts of the same type

The output shows issue counts by severity and category, plus recommended next actions.

### Exporting a Hygiene Report

```bash
marketsentry export-cross-site-alert-hygiene-report --format both
```

Exports to CSV and/or Markdown:

- `data/exports/cross_site_alert_hygiene_YYYYMMDD_HHMMSS.csv`
- `data/exports/cross_site_alert_hygiene_YYYYMMDD_HHMMSS.md`

### Scheduled Hygiene Reports

The batch script `scripts/run_alert_hygiene_report.bat` runs the hygiene check and exports both CSV and Markdown reports. It can be scheduled via Windows Task Scheduler for regular review reminders. Logs are written to `logs/scheduled/`.

The scheduled script runs local report generation only. It does not invoke live retrieval or approved retrieval.

### Using Hygiene Reports with Triage

The hygiene report recommends specific next actions. For stale open alerts, the recommended action is to export a triage CSV and review. For resolved archive candidates, the recommended action is to export a triage CSV and set triage_decision to archive. These are recommendations only; the operator decides which actions to take.

### Reminder: Hygiene Reports Are Review Aids

Alert hygiene reports do not auto-archive alerts, change watchlist status, modify Redfin source-of-truth fields, or change Quiet Score gatekeeper results. They are neutral operational review aids, not purchase recommendations.

## Cross-Site Alert Archive Policy

Milestone 30 adds an opt-in archive policy workflow for old resolved cross-site alerts. Archive policy does not auto-archive alerts, change watchlist status, or modify Redfin source-of-truth fields.

### Exporting Archive Candidates

```bash
# Export resolved alerts older than 30 days as archive candidates
marketsentry export-cross-site-alert-archive-candidates

# Custom age threshold
marketsentry export-cross-site-alert-archive-candidates --resolved-age-days 60

# Filter by property or severity
marketsentry export-cross-site-alert-archive-candidates --property-id 42
marketsentry export-cross-site-alert-archive-candidates --severity high
```

The export creates a CSV in `data/exports/cross_site_alert_archive_candidates_YYYYMMDD_HHMMSS.csv` with columns for alert details and editable fields: `archive_decision` and `archive_notes`.

### Editing Archive Decisions

Open the exported CSV in a spreadsheet editor. For each row, set the `archive_decision` column to one of:

| Decision | Changes Alert Status? | Effect |
| --- | --- | --- |
| keep_resolved | No | Alert stays resolved. Default value. |
| archive | Yes -> archived | Alert status set to archived. |
| reopen | Yes -> open | Alert status set to open. |
| no_archive | No | Adds `[no_archive]` marker; alert excluded from future candidates. |

Optionally add notes in the `archive_notes` column.

### Importing Archive Decisions

```bash
# Import and apply decisions
marketsentry import-cross-site-alert-archive-decisions --file data/exports/cross_site_alert_archive_candidates_*.csv

# Force apply even if alert status has changed since export
marketsentry import-cross-site-alert-archive-decisions --file <path> --force-status-mismatch
```

The import validates each row:

- Alert ID must exist in the database
- Archive decision must be one of the 4 allowed values
- Current alert status must match what was exported (unless `--force-status-mismatch`)
- Invalid rows are skipped and reported

### Viewing Archive Summary

```bash
marketsentry cross-site-alert-archive-summary
```

Shows eligible archive candidates, already archived alerts, no_archive marked alerts, and recommended next actions.

### Archive Policy in Dashboard

The Cross-Site Review section of the dashboard includes an Archive Policy subsection showing eligible candidate count, archived count, no_archive marked count, and the archive candidates table.

### Using Archive Policy with Hygiene Reports

The hygiene report identifies resolved archive candidates and recommends running `export-cross-site-alert-archive-candidates`. This replaces the previous recommendation to use the triage CSV for archiving resolved alerts. The archive policy workflow provides dedicated archive-specific decisions rather than mixing archive actions with triage decisions.

### Reminder: Archive Policy Is Opt-In Only

Archive policy does not auto-archive alerts, change watchlist status, modify Redfin source-of-truth fields, or change Quiet Score gatekeeper results. The operator reviews archive candidates and makes explicit decisions through the CSV workflow.

## Cross-Site Alert Expiration Policy

Milestone 31 adds configurable alert expiration rule profiles with operator approval gates. Expiration policy does not auto-apply actions, change watchlist status, or modify Redfin source-of-truth fields.

### Available Profiles

```bash
marketsentry list-cross-site-alert-expiration-profiles
```

Three built-in profiles:

| Profile | Resolved Archive | Acknowledged Review | Open Info/Warning Review | High/Critical Open |
| --- | --- | --- | --- | --- |
| conservative | 90 days | 45 days | 30 days | review only |
| standard | 60 days | 30 days | 21 days | review only |
| aggressive_review_only | 30 days | 14 days | 14 days | review only |

High/critical open alerts are never proposed for archive. They are review-only in all profiles.

### Previewing Expiration Policy

```bash
# Preview with default standard profile
marketsentry preview-cross-site-alert-expiration-policy

# Preview with a specific profile
marketsentry preview-cross-site-alert-expiration-policy --profile conservative
```

Preview is read-only. No mutations are performed.

### Exporting Approval CSV

```bash
# Export approval CSV with standard profile
marketsentry export-cross-site-alert-expiration-approval

# Export with a specific profile
marketsentry export-cross-site-alert-expiration-approval --profile aggressive_review_only

# Filter by property or severity
marketsentry export-cross-site-alert-expiration-approval --property-id 42
marketsentry export-cross-site-alert-expiration-approval --severity high
```

The export creates a CSV in `data/exports/cross_site_alert_expiration_approval_YYYYMMDD_HHMMSS.csv` with columns for alert details, proposed action/reason, and editable fields: `approval_decision` and `approval_notes`.

### Editing Approval Decisions

Open the exported CSV in a spreadsheet editor. For each row, set the `approval_decision` column to one of:

| Decision | Changes Alert Status? | Effect |
| --- | --- | --- |
| keep_current | No | No change. Default value. |
| approve_action | Depends | Applies the proposed_action if it mutates status; review/keep append notes only. |
| mark_no_archive | No | Appends `[no_archive]` marker to notes. |
| reopen | Yes -> open | Alert status set to open. |
| acknowledge | Yes -> acknowledged | Alert status set to acknowledged. |
| resolve | Yes -> resolved | Alert status set to resolved. |
| archive | Yes -> archived | Alert status set to archived. |

Optionally add notes in the `approval_notes` column.

### Importing Approval Decisions

```bash
# Import and apply decisions
marketsentry import-cross-site-alert-expiration-approval --file data/exports/cross_site_alert_expiration_approval_*.csv

# Force apply even if alert status has changed since export
marketsentry import-cross-site-alert-expiration-approval --file <path> --force-status-mismatch
```

The import validates each row:

- Expiration export ID must be present
- Profile name must be present
- Alert ID must exist in the database
- Current alert status must match what was exported (unless `--force-status-mismatch`)
- Approval decision must be one of the 7 allowed values
- Invalid rows are skipped and reported

### Viewing Expiration Summary

```bash
marketsentry cross-site-alert-expiration-summary
marketsentry cross-site-alert-expiration-summary --profile conservative
```

Shows candidate counts by proposed action, already archived count, no_archive marked count, and recommended next actions.

### Expiration Policy in Dashboard

The Cross-Site Review section of the dashboard includes an Expiration Policy subsection showing available profiles, candidate counts by proposed action, archived count, no_archive count, and the latest approval CSV table.

### Using Expiration Policy with Other Workflows

- **Hygiene reports** (Milestone 29) identify resolved archive candidates and recommend either `export-cross-site-alert-archive-candidates` or `export-cross-site-alert-expiration-approval`
- **Archive policy** (Milestone 30) handles dedicated archive review for old resolved alerts only
- **Expiration policy** (Milestone 31) handles configurable age-based rules across all non-archived statuses
- All workflows are independent: each serves a distinct purpose in the alert lifecycle

### Reminder: Expiration Policy Does Not Auto-Apply

Expiration policy does not automatically apply any actions. All mutations require an explicit operator-reviewed approval CSV import. It does not change watchlist status, modify Redfin source-of-truth fields, or change Quiet Score gatekeeper results.

## User-Defined Alert Expiration Profiles

Milestone 32 adds support for user-defined expiration profiles loaded from a local JSON config file. Built-in profiles remain available.

### Writing Example Config

```bash
# Write example config template
marketsentry write-alert-expiration-profile-template

# Write to a custom path
marketsentry write-alert-expiration-profile-template --output config/my_profiles.json

# Overwrite existing file
marketsentry write-alert-expiration-profile-template --overwrite
```

### Config File Path

Default: `config/alert_expiration_profiles.json`

This file is optional. If absent, only built-in profiles are used.

### Profile and Rule Fields

Each profile has:

- `profile_name` (required, unique)
- `description` (optional)
- `rules` (list of rule objects)

Each rule has:

- `rule_name` (required, unique within profile)
- `current_status`: open, acknowledged, resolved, or archived
- `severity`: string or list of info, warning, high, critical, any
- `min_age_days`: integer >= 0
- `proposed_action`: archive, review, keep, or reopen_review

### Validation Rules

- High/critical open alerts may only propose review or keep
- Archived alerts may only propose keep or review
- User profiles cannot override built-in profile names
- Invalid configs are rejected with clear errors; built-in profiles remain usable

### Listing All Profiles

```bash
# List built-in and custom profiles
marketsentry list-cross-site-alert-expiration-profiles --profile-config config/alert_expiration_profiles.json
```

### Previewing with Custom Profile

```bash
marketsentry preview-cross-site-alert-expiration-policy --profile my_custom_review --profile-config config/alert_expiration_profiles.json
```

### Exporting Approval CSV with Custom Profile

```bash
marketsentry export-cross-site-alert-expiration-approval --profile my_custom_review --profile-config config/alert_expiration_profiles.json
```

### Importing Approval CSV

Import is unchanged. Actions still require approval import:

```bash
marketsentry import-cross-site-alert-expiration-approval --file data/exports/cross_site_alert_expiration_approval_*.csv
```

See also: [Alert Expiration Profiles](ALERT_EXPIRATION_PROFILES.md) for full config format and examples.

## Profile Comparison and Last-Used Profile Preference

Milestone 33 adds side-by-side profile comparison views and local last-used profile persistence. Profile comparison is read-only. Last-used profile preference does not change alert state, watchlist status, or Redfin source-of-truth fields.

### Comparing Profiles

```bash
# Compare all built-in profiles
marketsentry compare-cross-site-alert-expiration-profiles

# Compare specific profiles
marketsentry compare-cross-site-alert-expiration-profiles --profiles conservative,aggressive_review_only

# Compare including custom profiles
marketsentry compare-cross-site-alert-expiration-profiles --profile-config config/alert_expiration_profiles.json
```

The comparison table shows each profile's candidate counts, archive/review/keep counts, affected property count, and rule count. No mutations are performed.

### Exporting Profile Comparison

```bash
# Export comparison CSV
marketsentry export-cross-site-alert-expiration-profile-comparison

# Export with custom profiles
marketsentry export-cross-site-alert-expiration-profile-comparison --profile-config config/alert_expiration_profiles.json
```

The CSV is saved to `data/exports/cross_site_alert_expiration_profile_comparison_YYYYMMDD_HHMMSS.csv`.

### Setting Last-Used Profile

```bash
# Set last-used profile to conservative
marketsentry set-cross-site-alert-expiration-profile --profile conservative

# Set a custom profile with config path
marketsentry set-cross-site-alert-expiration-profile --profile my_custom_review --profile-config config/alert_expiration_profiles.json
```

The preference is saved to `config/alert_expiration_profile_preference.json`. Only valid profiles can be saved.

### Getting Current Profile Preference

```bash
marketsentry get-cross-site-alert-expiration-profile
```

Shows the current last-used profile name, config path, and whether it is a fallback.

### Clearing Profile Preference

```bash
marketsentry clear-cross-site-alert-expiration-profile
```

Removes the local preference file. Subsequent commands fall back to "standard".

### How Last-Used Profile Affects Existing Commands

When `--profile` is omitted from these commands, the system checks for a last-used profile preference before falling back to "standard":

- `preview-cross-site-alert-expiration-policy`
- `export-cross-site-alert-expiration-approval`
- `cross-site-alert-expiration-summary`

Explicit `--profile` always overrides the last-used preference. Invalid or missing preferences fall back to "standard" with a warning.

### Profile Comparison in Dashboard

The Cross-Site Review section of the dashboard includes a profile comparison table and the current last-used profile preference indicator.

### Reminder: Comparison and Preference Are Read-Only

Profile comparison does not mutate alerts. Last-used profile preference is a local convenience setting only. It does not change alert state, watchlist status, Redfin source-of-truth fields, or Quiet Score gatekeeper results.

## No Live Scraping Warning

Market_Sentry does not perform any active live web scraping, browser automation, or network retrieval by default. Live HTTP retrieval for Redfin is available but disabled by default and requires explicit opt-in. All property data must be manually saved as HTML fixtures or entered as CSV imports unless live retrieval is explicitly enabled.
