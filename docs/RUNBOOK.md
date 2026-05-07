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

## No Live Scraping Warning

Market_Sentry does not perform any active live web scraping, browser automation, or network retrieval by default. Live HTTP retrieval for Redfin is available but disabled by default and requires explicit opt-in. All property data must be manually saved as HTML fixtures or entered as CSV imports unless live retrieval is explicitly enabled.
