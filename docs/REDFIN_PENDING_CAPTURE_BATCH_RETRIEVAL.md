# Redfin Pending Capture Batch Retrieval

This document describes the batch retrieval orchestrator for pending Redfin fixture capture requests (Milestone 18).

## What the Batch Orchestrator Does

The batch orchestrator processes pending fixture capture queue items for Redfin one at a time:

1. Reads pending Redfin capture requests from the fixture capture queue.
2. Applies full policy checks (compliance, robots, rate limit, dry-run approval) for each item.
3. If allowed and force-live is set, retrieves the page via HTTP and saves it as a local fixture.
4. Optionally processes saved fixtures through the Milestone 17 pipeline (parse, enrich, recalculate, export).
5. Marks successfully retrieved (and optionally processed) capture queue items as captured.
6. Records results in batch and per-item manifests.
7. Logs all decisions to audit files.

## What the Batch Orchestrator Does Not Do

- Does not perform browser automation, Playwright, Selenium, or JavaScript execution.
- Does not bypass CAPTCHAs, login walls, paywalls, or anti-bot protections.
- Does not add broad scraping capability.
- Does not schedule live retrieval by default.
- Does not retry failed requests automatically.
- Does not retrieve from non-Redfin sources.
- Does not modify existing candidate data destructively.

## Batch Modes

### dry_run_only (default)

- Evaluates each pending request against policy checks.
- Writes audit decisions.
- Does not make any network calls.
- Does not mark any items as captured.
- Queue items remain pending.

### retrieve_only

- Requires `--force-live`.
- Retrieves pages and saves as fixtures.
- Does not process fixtures through the parsing pipeline.
- Marks successfully retrieved items as captured.

### retrieve_and_process

- Requires `--force-live` and `--process-after-retrieval`.
- Retrieves pages and saves as fixtures.
- Processes all retrieved fixtures through the Milestone 17 pipeline.
- Exports candidate review and analysis reports.
- Marks successfully retrieved and processed items as captured.

## How to Dry-Run Pending Items

```bash
# Preview all pending Redfin capture requests
marketsentry dry-run-pending-redfin-fixtures

# Filter by request type
marketsentry dry-run-pending-redfin-fixtures --request-type search
marketsentry dry-run-pending-redfin-fixtures --request-type property_detail

# Limit number of items
marketsentry dry-run-pending-redfin-fixtures --max-items 5
```

No network calls are performed. The output shows per-item policy decisions.

## How to Retrieve with Force-Live

```bash
# Retrieve pending items (requires full env config + robots + dry-run approval)
marketsentry retrieve-pending-redfin-fixtures --force-live

# Retrieve and process
marketsentry retrieve-pending-redfin-fixtures --force-live --process-after-retrieval

# Limit items
marketsentry retrieve-pending-redfin-fixtures --force-live --max-items 3
```

Without `--force-live`, the command prints a safe explanation and exits without any network calls.

## Why Force-Live Is Required

Live retrieval is disabled by default. The `--force-live` flag is required because:

1. It ensures the user makes a conscious decision to perform network calls.
2. It prevents accidental live retrieval during testing or automation.
3. It follows the human-in-the-loop principle.
4. Even with `--force-live`, all policy checks are enforced per item.

## How Rate Limiting Works

The rate limiter enforces `MARKETSENTRY_MAX_REQUESTS_PER_MINUTE` (default: 6) and a minimum delay between requests (default: 10 seconds). Each item in the batch is rate-limited independently. If the rate limit is exceeded, the item is blocked with a clear reason.

## How Dry-Run Approval Works

If `MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE=true` (default), each URL must have a recent dry-run approval (within 24 hours) before live retrieval is allowed. Run dry-run commands first:

```bash
marketsentry dry-run-redfin-search --url "https://www.redfin.com/city/..."
marketsentry dry-run-redfin-property --url "https://www.redfin.com/CA/..."
```

Or use the batch dry-run command to preview and create approval records for all pending items.

## How Fixture Processing Works After Retrieval

When `--process-after-retrieval` is used with `--force-live`:

1. All successfully retrieved fixtures are saved as local HTML files with sidecar JSON metadata.
2. After the batch completes, the Milestone 17 processing pipeline runs.
3. Search fixtures are parsed for candidate discovery.
4. Detail fixtures are parsed for candidate enrichment.
5. Effective DOM metrics are recalculated and persisted.
6. Candidate review and analysis reports are exported.
7. Capture queue items are marked as captured only after successful processing.

## How to Inspect Manifests and Audit Logs

### Batch Manifest

```text
data/processed/redfin_batch_retrieval_manifest.csv
```

One row per batch run with aggregate counts.

### Per-Item Manifest

```text
data/processed/redfin_batch_retrieval_items.csv
```

One row per capture request per run with individual decisions and outcomes.

### Audit Logs

```text
logs/retrieval_audit/retrieval_audit_YYYYMMDD.csv
```

All retrieval decisions (allowed/blocked, dry-run/live) are logged here.

## How to Continue Manual Fixture Capture Instead

You can continue using manual fixture capture:

1. Run `marketsentry list-fixture-capture-queue` to see pending items.
2. Browse to each URL in your browser.
3. Save the page as HTML to the suggested fixture path.
4. Run `marketsentry mark-fixture-captured --capture-request-id N --fixture-path "path/to/file.html"`.
5. Process with `marketsentry process-redfin-retrieved-fixtures`.

## Prerequisites for Live Batch Retrieval

All of the following must be configured:

```ini
MARKETSENTRY_LIVE_RETRIEVAL_ENABLED=true
MARKETSENTRY_ALLOWED_LIVE_SOURCES=redfin
MARKETSENTRY_LIVE_USER_AGENT=MarketSentry/1.0
MARKETSENTRY_LIVE_CONTACT_EMAIL=user@example.com
MARKETSENTRY_MAX_REQUESTS_PER_MINUTE=6
MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE=true
```

Plus a local robots policy file at `data/policies/robots/redfin_robots.txt`.

## Scheduled Tasks

No scheduled task invokes batch retrieval by default. Batch retrieval must be a conscious, manual decision.

## Approval Workflow (Milestone 19)

Milestone 19 adds a two-step approval workflow that provides per-item human review before batch live retrieval.

### Prepare Approval Package

```bash
marketsentry prepare-redfin-retrieval-approval
marketsentry prepare-redfin-retrieval-approval --max-items 10
marketsentry prepare-redfin-retrieval-approval --request-type property_detail
```

This dry-runs pending Redfin capture items and writes:

- `data/exports/retrieval_approvals/redfin_batch_approval_<run_id>.csv` - User-editable approval CSV
- `data/exports/retrieval_approvals/redfin_batch_approval_<run_id>.md` - Markdown summary

### Edit Approval CSV

Open the CSV and set `approved_for_live=true` for items you want to retrieve. Save the CSV.

### Retrieve Approved Items

```bash
marketsentry retrieve-approved-redfin-batch \
    --approval-file "data/exports/retrieval_approvals/redfin_batch_approval_<run_id>.csv" \
    --force-live
```

### Approval Safety Rules

- `approved_for_live` defaults to `false` for every item.
- `--force-live` is required for network calls.
- All policy checks are re-evaluated at retrieval time.
- URL and capture request validation is enforced.
- No scheduled scripts invoke approved retrieval.

See [REDFIN_RETRIEVAL_APPROVAL_WORKFLOW.md](REDFIN_RETRIEVAL_APPROVAL_WORKFLOW.md) for the complete guide.
