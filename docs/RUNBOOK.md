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

## No Live Scraping Warning

Market_Sentry does not perform any live web scraping, browser automation, or active network retrieval. All property data must be manually saved as HTML fixtures or entered as CSV imports. This is by design for the current milestone.
