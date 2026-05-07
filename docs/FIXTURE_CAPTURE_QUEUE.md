# Market_Sentry Fixture Capture Queue

This document explains the fixture capture queue system and how to use it for manual data collection.

## What Is the Fixture Capture Queue?

The fixture capture queue is a local SQLite-backed queue that tracks URLs and pages that need manual HTML fixture capture. When live retrieval is blocked or not implemented, the system tells you exactly which pages to save and where to put them.

This is the primary safe fallback workflow: instead of automated scraping, you browse the site normally in your browser, save pages as HTML, and tell Market_Sentry where you put them.

## How It Works

1. **Dry-run or policy check** identifies a URL that needs data.
2. If live retrieval is blocked (default), a **capture request** is automatically added to the queue.
3. The capture request includes the URL, source site, request type, and a **suggested fixture path**.
4. You manually browse to the URL, save the page as HTML, and place it in the suggested directory.
5. You mark the capture request as **captured** via CLI.
6. Existing fixture parsers process the saved HTML file.

## CLI Commands

### List Pending Capture Requests

```bash
marketsentry list-fixture-capture-queue
```

Shows all pending capture requests with IDs, URLs, types, and suggested paths.

### Export Capture Queue to CSV

```bash
marketsentry export-fixture-capture-queue
```

Exports to `data/exports/fixture_capture_queue_YYYYMMDD_HHMMSS.csv`.

### Mark a Request as Captured

```bash
marketsentry mark-fixture-captured --capture-request-id 1 --fixture-path "data/raw/redfin/details/my_property.html"
```

### Check Retrieval Policy

```bash
marketsentry retrieval-policy-check --source redfin --url "https://www.redfin.com/CA/Temecula/..." --mode live_http
```

Shows whether a URL would be allowed or blocked and recommends fixture capture if blocked.

## How to Save Fixture Files

1. Open the URL in your browser (Chrome, Firefox, Edge, etc.).
2. Use **File > Save As** (or Ctrl+S / Cmd+S).
3. Choose **"Webpage, HTML Only"** format.
4. Save to the suggested fixture path shown in the capture queue.
5. Run the appropriate parse command.

### Suggested Fixture Paths by Source

| Source | Request Type | Suggested Path |
|--------|-------------|----------------|
| redfin | search | `data/raw/redfin/search/` |
| redfin | property_detail | `data/raw/redfin/details/` |
| zillow | property_detail | `data/raw/cross_site/zillow/` |
| realtor | property_detail | `data/raw/cross_site/realtor/` |
| homes | property_detail | `data/raw/cross_site/homes/` |
| compass | property_detail | `data/raw/cross_site/compass/` |
| county | assessor | `data/raw/county/assessor/` |
| county | recorder | `data/raw/county/recorder/` |

## Capture Request Statuses

| Status | Meaning |
|--------|---------|
| `pending` | Waiting for manual capture |
| `captured` | HTML file has been saved |
| `skipped` | User chose to skip this request |
| `invalid` | URL or request was invalid |
| `archived` | Completed and archived |

## Deduplication

The queue deduplicates by `source_site + normalized_url + request_type + pending status`. If a pending request already exists for the same URL and type, a new request will not be added.

## How This Supports Safe Operation

- **No automated scraping.** You browse sites normally in your own browser.
- **No network calls.** All queue operations are local SQLite and CSV.
- **Human-in-the-loop.** You decide which pages to save and when.
- **Audit trail.** All capture requests are tracked with timestamps.
- **Suggested paths.** The system tells you exactly where to save files.

## Batch Retrieval of Pending Items

Milestone 18 adds a batch orchestrator that can process pending capture queue items for Redfin.

### Batch Dry-Run

```bash
# Preview all pending Redfin items (no network calls)
marketsentry dry-run-pending-redfin-fixtures

# Filter by type
marketsentry dry-run-pending-redfin-fixtures --request-type property_detail
```

### Batch Retrieve

```bash
# Retrieve pending items (requires full config + --force-live)
marketsentry retrieve-pending-redfin-fixtures --force-live

# Retrieve and process through parsing pipeline
marketsentry retrieve-pending-redfin-fixtures --force-live --process-after-retrieval
```

**Force-live warning:** Without `--force-live`, no network calls are performed. The command prints a safe explanation and exits.

### Process After Retrieval

Use `--process-after-retrieval` with `--force-live` to automatically run the Milestone 17 processing pipeline after batch retrieval. This parses fixtures, inserts candidates, enriches details, recalculates metrics, and exports reports.

### Manifest Files

- Batch manifest: `data/processed/redfin_batch_retrieval_manifest.csv` (one row per batch run)
- Per-item manifest: `data/processed/redfin_batch_retrieval_items.csv` (one row per item per run)

### How Blocked Items Remain Pending

When a capture request is blocked by policy checks (compliance, robots, rate limit, or dry-run approval), it remains in `pending` status in the queue. The block reason is recorded in the per-item manifest and audit log. The user can address the block condition and retry.

See [REDFIN_PENDING_CAPTURE_BATCH_RETRIEVAL.md](REDFIN_PENDING_CAPTURE_BATCH_RETRIEVAL.md) for the complete guide.

## What the Queue Does Not Do

- Does not fetch web pages or make network calls (batch retrieval requires explicit opt-in).
- Does not automate browser actions.
- Does not bypass paywalls, login walls, or anti-bot protections.
- Does not make purchase recommendations.
