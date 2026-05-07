# Redfin Retrieved Fixture Processing Pipeline

This document describes how retrieved Redfin fixtures are processed through the local parsing pipeline (Milestone 17).

## Purpose

Milestone 16 added the ability to retrieve Redfin HTML pages via HTTP and save them as local fixtures. Milestone 17 connects those saved fixtures to the existing parsing pipeline so they can be:

- Parsed for candidate discovery (search fixtures)
- Used for candidate enrichment (detail fixtures)
- Tracked via a processing manifest for idempotency
- Integrated with the fixture capture queue

The processing step itself performs **no live retrieval or network calls**.

## Expected Fixture Directories

Search fixtures:
```text
data/raw/redfin/search/
```

Detail fixtures:
```text
data/raw/redfin/details/
```

## Metadata Sidecar Files

When fixtures are saved by Milestone 16 live retrieval, each HTML file has a companion `.json` metadata file:

```text
data/raw/redfin/search/redfin_search_20260507_090000.html
data/raw/redfin/search/redfin_search_20260507_090000.json
```

The JSON metadata contains:
- `source_url` - Original URL retrieved
- `source_site` - Always "redfin"
- `request_type` - "search" or "property_detail"
- `retrieved_at` - ISO timestamp
- `fixture_path` - Path to the HTML file
- `content_length` - Size of the HTML content

Metadata is optional. Fixtures without sidecar JSON (e.g., manually saved) are still processed normally. The fixture type is inferred from the filename if metadata is missing.

## Processing Manifest

A CSV manifest tracks which fixtures have been processed:

```text
data/processed/redfin_fixture_processing_manifest.csv
```

Columns:
- `processed_at` - Timestamp of processing
- `fixture_path` - Path to the fixture HTML
- `metadata_path` - Path to sidecar JSON (if any)
- `source_url` - Original URL
- `fixture_type` - "search" or "property_detail"
- `status` - "processed", "skipped", or "error"
- `candidates_discovered` - Count for search fixtures
- `candidates_inserted` - Count of new candidates
- `candidates_enriched` - Count for detail fixtures
- `listing_events_inserted` - Count of listing events
- `warnings` - Semicolon-separated warnings
- `errors` - Semicolon-separated errors
- `content_hash` - SHA-256 of the fixture HTML

### Skip/Reprocess Behavior

- By default, fixtures with a `content_hash` already in the manifest (status = "processed") are skipped.
- Use `--force-reprocess` to reprocess all fixtures regardless of hash.
- The manifest is append-only; it does not delete or overwrite rows.
- Fixture files are never deleted by the processing pipeline.

## Candidate Insertion and Enrichment

### Search Fixtures
- Parsed using the existing `parse_redfin_fixtures_from_directory()` function.
- Candidates are inserted into `candidate_review_queue` with deduplication by normalized address and Redfin URL.
- Existing `user_decision` and `user_notes` are never overwritten.

### Detail Fixtures
- Parsed using the existing `enrich_candidates_from_detail_directory()` function.
- Matches detail pages to existing candidates by URL or normalized address.
- Enriches candidates with price, beds, baths, sqft, lot_size, garage_spaces, gas_service, quiet_score, vibrancy_score.
- Inserts listing history events into `listing_events` table without duplicates.
- Existing `user_decision` and `user_notes` are never overwritten.

## Report Generation

After processing, the integrated workflow:

1. Recalculates Effective DOM metrics from listing events.
2. Persists Effective DOM v2 metrics.
3. Exports a candidate review CSV to `data/exports/`.
4. Exports a candidate analysis report to `data/exports/`.

## CLI Commands

### Process All Retrieved Fixtures

```bash
marketsentry process-redfin-retrieved-fixtures
```

Options:
- `--db` - Database path
- `--search-dir` - Search fixtures directory
- `--details-dir` - Detail fixtures directory
- `--output-dir` - Report output directory
- `--force-reprocess` - Reprocess all fixtures

### Process Search Fixtures Only

```bash
marketsentry process-redfin-search-fixtures
```

### Process Detail Fixtures Only

```bash
marketsentry process-redfin-detail-fixtures
```

### Retrieve and Process (Convenience)

```bash
marketsentry retrieve-and-process-redfin-property --url "..." --force-live
```

Retrieves a property page and immediately processes the saved fixture. Requires all Milestone 16 guardrails (env vars, robots policy, dry-run approval, rate limit).

## No Live Retrieval in Processing Step

The processing pipeline reads only from local files on disk. It does not:
- Fetch any URLs from the internet
- Make any HTTP requests
- Require network connectivity
- Bypass any access controls

Processing works identically for manually saved fixtures and live-retrieved fixtures.
