# Cross-Site Manual Fixture Workflow

This document explains how to use the cross-site manual fixture workflow for Zillow, Realtor.com, Homes.com, and Compass property data.

## Supported Sources

| Source | Property Detail | Search | Live Retrieval |
|--------|----------------|--------|----------------|
| Redfin | Yes | Yes | Phase 1 (disabled by default) |
| Zillow | Yes | Not yet | No |
| Realtor.com | Yes | Not yet | No |
| Homes.com | Yes | Not yet | No |
| Compass | Yes | Not yet | No |

Redfin remains the only source with Live HTTP Phase 1 support. All other sources use the manual fixture workflow exclusively.

## How to Dry-Run a Cross-Site Property URL

Preview what would happen if you process a cross-site property URL:

```bash
# Zillow
marketsentry dry-run-cross-site-property --source zillow --url "https://www.zillow.com/homedetails/..."

# Realtor.com
marketsentry dry-run-cross-site-property --source realtor --url "https://www.realtor.com/realestateandhomes-detail/..."

# Homes.com
marketsentry dry-run-cross-site-property --source homes --url "https://www.homes.com/property/..."

# Compass
marketsentry dry-run-cross-site-property --source compass --url "https://www.compass.com/listing/..."
```

The dry-run preview shows:

- URL validation result
- Inferred request type (property_detail, search, unknown)
- Recommended action
- Fixture capture queue request status
- No network calls are performed

## How Fixture Capture Requests Are Created

When you run a dry-run preview or when live retrieval is blocked/not implemented, the system automatically creates a fixture capture queue request. This tells you:

- Which URL needs manual capture
- Which source site it belongs to
- What type of page it is
- Where to save the fixture file

View pending capture requests:

```bash
marketsentry list-fixture-capture-queue
```

## Where to Save Fixtures

Save HTML fixtures to the appropriate directory based on source and type:

| Source | Type | Directory |
|--------|------|-----------|
| Zillow | property_detail | `data/raw/zillow/details/` |
| Zillow | search | `data/raw/zillow/search/` |
| Realtor.com | property_detail | `data/raw/realtor/details/` |
| Realtor.com | search | `data/raw/realtor/search/` |
| Homes.com | property_detail | `data/raw/homes/details/` |
| Homes.com | search | `data/raw/homes/search/` |
| Compass | property_detail | `data/raw/compass/details/` |
| Compass | search | `data/raw/compass/search/` |

Legacy directories (`data/raw/cross_site/{source}/`) are also scanned for backward compatibility.

### How to Save a Fixture

1. Open the property URL in your browser (Chrome, Firefox, Edge).
2. Use **File > Save As** (or Ctrl+S / Cmd+S).
3. Choose **"Webpage, HTML Only"** format.
4. Save to the appropriate directory listed above.
5. Mark the capture request as captured (optional):

```bash
marketsentry mark-fixture-captured --capture-request-id <id> --fixture-path "data/raw/zillow/details/my_property.html"
```

## How to Process Cross-Site Fixtures

### Process All Sources

```bash
marketsentry process-cross-site-fixtures
```

This scans all supported source directories, processes HTML fixtures through source-specific parsers, writes the processing manifest, and marks matching capture queue items as captured.

### Process One Source

```bash
marketsentry process-cross-site-source-fixtures --source zillow
marketsentry process-cross-site-source-fixtures --source realtor --dir data/raw/realtor/details
```

### Force Reprocess

By default, fixtures with unchanged content (same SHA-256 hash) are skipped. Use `--force-reprocess` to override:

```bash
marketsentry process-cross-site-fixtures --force-reprocess
```

### Processing Output

The processor reports:

- Files scanned
- Files processed
- Files skipped (duplicate content hash)
- Files failed
- Observations inserted
- Candidates matched
- Watched properties matched
- Queue items marked captured
- Warnings and errors

### Processing Manifest

The append-only manifest at `data/processed/cross_site_fixture_processing_manifest.csv` tracks all processing results with content hashes for deduplication.

## How Cross-Site Observations Feed Reports

Processed cross-site fixtures insert `cross_site_observations` into the database. These observations:

- Provide supplementary property data from non-Redfin sources
- Enable cross-site price, status, and DOM discrepancy detection
- Feed the Cross-Site Review section of the dashboard
- Do not overwrite Redfin source-of-truth data
- Do not overwrite user decisions or watchlist status

## No Live Retrieval for These Sources

All non-Redfin sources are manual-fixture and dry-run only:

- No network calls are performed
- No browser automation
- No CAPTCHA, login, paywall, or anti-bot bypass
- All data comes from manually saved HTML fixtures

Redfin remains the only source with Live HTTP Phase 1 support, and even Redfin live retrieval is disabled by default and requires explicit opt-in.

## Dashboard Visibility

The Retrieval Operations dashboard includes a "Cross-Site Fixtures" tab showing:

- Total manifest records
- Processed and failed counts
- Source breakdown (Zillow, Realtor.com, Homes.com, Compass)
- Processing errors
- Unprocessed fixture warnings

The Health Checks tab includes:

- Unprocessed cross-site fixture count
- Stale cross-site capture request count
- Missing parser warnings

```bash
streamlit run src/marketsentry/dashboard_app.py
```

## Cross-Site Parser Quality (Milestone 23)

### Fixture Variants

Each source (Zillow, Realtor.com, Homes.com, Compass) has at least 8 test fixture variants in `tests/fixtures/cross_site/<source>/`:

| Fixture | Purpose |
| ------- | ------- |
| `normal_property.html` | Full property data with all fields |
| `price_discrepancy.html` | Price difference from Redfin baseline |
| `status_pending.html` | Pending listing status |
| `sold_or_off_market.html` | Sold or off-market status |
| `missing_optional_fields.html` | Partial data, some fields absent |
| `gas_evidence.html` | Multiple gas service keywords |
| `garage_evidence.html` | Garage spaces (e.g., 3-car garage) |
| `sparse_or_malformed.html` | Minimal/broken HTML, graceful handling |

### Parser Confidence

Each parse result includes a confidence level indicating extraction reliability:

- **high**: Address extracted and at least price/status/property facts present. The observation is suitable for cross-site comparison.
- **medium**: Address extracted and some facts present, but important fields (price, status, beds, baths, sqft) are missing. Use with caution in comparisons.
- **low**: Sparse or uncertain parse. Missing address or minimal useful data extracted. Do not weight equally in comparison analysis.

### Parse Warnings

Parse warnings are diagnostic messages listing issues encountered during extraction. Common warnings include:

- Missing required fields (e.g., "missing: price, listing_status")
- Format ambiguity or unrecognized patterns
- Partial extraction from malformed HTML

Warnings are stored with the observation and visible in cross-site comparison reports via `sources_with_parse_warnings`.

### Recommended Manual Review for Low-Confidence Parses

When a cross-site observation has **low** parse confidence:

1. Open the saved HTML fixture and verify it contains actual property data (not an error page, redirect, or CAPTCHA challenge).
2. Re-save the page from the source site if the original fixture was incomplete.
3. Do not use low-confidence observations as evidence of price, status, or DOM discrepancies.
4. Treat the observation as informational only until a higher-confidence parse is available.
5. Check the `missing_required_fields` list to understand what data is absent.

### Cross-Site Data Validates Redfin (Does Not Overwrite)

Cross-site observations exist to validate and compare against Redfin source-of-truth data. They do **not** overwrite:

- `user_decision` or `user_notes`
- `active_watch_status` or `watch_priority`
- Redfin-sourced property facts (price, beds, baths, sqft, listing status, DOM, etc.)

Discrepancy flags (price, status, DOM) are data quality indicators for human review. They are not automatic overrides or purchase recommendations.

## Cross-Site Analytics (Milestone 24)

### Confidence-Weighted Scoring

Cross-site observations are weighted by:

- **Parser confidence**: high=1.0, medium=0.7, low=0.4, failed=0.0
- **Freshness**: Recent observations (0-7 days) have full weight; older observations are progressively downweighted (8-30d=0.8, 31-90d=0.5, >90d=0.2)
- **Completeness**: Observations with more required fields (price, status, beds, baths, sqft) contribute more weight

### Discrepancy Severity

Severity uses neutral language and accounts for source reliability:

- **none**: No cross-site disagreement
- **low**: Minor differences (e.g., price >$10k, gas/garage disagreement)
- **medium**: Moderate differences (e.g., price >$25k, DOM >30 days)
- **high**: Significant conflicts (e.g., price >$50k, active vs sold/pending)

Low-confidence sources reduce severity certainty. A price discrepancy from a low-confidence source is less alarming than one from a high-confidence source.

### Manual Review Priority

Based on severity and confidence:

- **high**: Significant discrepancy from reliable sources
- **medium**: Moderate discrepancy, or low discrepancy with uncertain sources
- **low**: Minor issues or stale/low-confidence data
- **none**: No issues, reliable data

### Generating the Analytics Report

```bash
marketsentry export-cross-site-analytics-report
```

### Parser Confidence Impact on Analytics

Parser confidence directly affects how much weight an observation carries in analytics. A low-confidence observation from a sparse HTML page contributes less to agreement scores and reduces discrepancy severity certainty.

## Cross-Site Analytics Trend Snapshots (Milestone 25)

### Creating Trend Snapshots

After cross-site analytics are available (Milestone 24), create point-in-time snapshots to track how analytics change over time:

```bash
# Create snapshots for all active watched properties
marketsentry snapshot-cross-site-analytics

# Force snapshot even when no material change detected
marketsentry snapshot-cross-site-analytics --force
```

Snapshots are only created when material changes are detected (severity/priority label changes, confidence delta >= 0.10, agreement delta >= 0.10, source count changes, or discrepancy flag changes). Use `--force` to override this behavior.

### Exporting Trend Reports

```bash
marketsentry export-cross-site-trend-report
```

The trend report CSV compares current vs previous snapshots and includes trend direction (improving/degrading/stable) and recommended next actions.

### Trend Direction

- **improving**: Confidence increasing, severity decreasing, or agreement scores improving
- **degrading**: Confidence decreasing, severity increasing, or agreement scores degrading
- **stable**: No significant changes detected

### Reminder: Cross-Site Data Validates but Does Not Overwrite

All analytics scores, severity labels, review priorities, and trend snapshots are informational aids for human review. They do not overwrite Redfin source-of-truth fields, user decisions, or watchlist status.

## Cross-Site Trend Alerts (Milestone 26)

### What Trend Alerts Mean

Cross-site trend alerts flag material changes between consecutive analytics snapshots that may warrant human review. They cover confidence score changes, discrepancy severity shifts, manual review priority changes, agreement score degradation, and source quality changes.

Alerts are neutral review signals. They are not purchase recommendations and do not infer seller intent.

### Generating Alerts

After creating trend snapshots (Milestone 25), generate alerts:

```bash
# Generate alerts from latest vs previous snapshots
marketsentry generate-cross-site-trend-alerts
```

Alerts are only created when trend rules are triggered. Duplicate open alerts for the same property, alert type, and snapshot are automatically skipped.

### Listing Alerts

```bash
# List open alerts (default)
marketsentry list-cross-site-trend-alerts

# Filter by severity
marketsentry list-cross-site-trend-alerts --severity high

# Filter by property
marketsentry list-cross-site-trend-alerts --property-id 42
```

### Acknowledging and Resolving Alerts

```bash
# Acknowledge an alert
marketsentry acknowledge-cross-site-trend-alert --alert-id 1 --notes "Reviewed data"

# Resolve an alert
marketsentry resolve-cross-site-trend-alert --alert-id 1 --notes "Data corrected"
```

### Exporting Alert Reports

```bash
marketsentry export-cross-site-trend-alerts-report
marketsentry export-cross-site-trend-alerts-report --status open
```

### Alert Severity Definitions

- **info**: Positive or neutral change (confidence improved, severity decreased). No immediate action needed.
- **warning**: Moderate change (confidence dropped 0.10-0.24, price/DOM agreement degraded, stale/low-confidence sources increased). Monitor for further trends.
- **high**: Significant change (confidence dropped >= 0.25, status agreement degraded, severity increased to high, review priority increased to high). Review cross-site data and validate against Redfin source.
- **critical**: Severe change (discrepancy severity reached critical). Validate immediately.

### Reminder: Alerts Are Review Aids

Cross-site trend alerts are analytical review aids for human operators. They do not overwrite Redfin source-of-truth fields, change watchlist status, modify Quiet Score gatekeeper results, or make purchase recommendations.
