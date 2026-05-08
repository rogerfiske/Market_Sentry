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
