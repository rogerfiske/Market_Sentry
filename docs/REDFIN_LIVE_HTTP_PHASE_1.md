# Redfin Live HTTP Retrieval Phase 1

This document describes the Redfin Live HTTP Retrieval Phase 1 implementation (Milestone 16).

## What Is Implemented

- **HTTP client abstraction** (`src/marketsentry/source_adapters/http_client.py`): `HttpRequest`, `HttpResponse`, `HttpClient` (abstract), `StandardLibraryHttpClient` (urllib-based), `FakeHttpClient` (for tests).
- **Redfin live retrieval methods** in `redfin_adapter.py`: `retrieve_search()`, `retrieve_property_detail()`, `save_retrieved_fixture()`, `retrieve_and_save_search_fixture()`, `retrieve_and_save_property_fixture()`.
- **Full policy enforcement pipeline**: compliance check, robots policy, rate limit, dry-run approval, HTTP client injection, HTTP GET, fixture saving, audit logging.
- **Fixture output with sidecar metadata**: Retrieved HTML is saved as local fixtures with timestamped filenames and a companion JSON metadata file.
- **Two CLI commands**: `retrieve-redfin-search` and `retrieve-redfin-property` with `--force-live`, `--dry-run-only` options.
- **Policy engine update**: When all safety checks pass, the policy decision is `ALLOWED` instead of `NOT_IMPLEMENTED`.

## What Is Not Implemented

- No Zillow, Realtor.com, Homes.com, Compass, County Recorder, or County Assessor live retrieval.
- No browser automation, Playwright, Selenium, or JavaScript execution.
- No CAPTCHA bypass, login bypass, paywall bypass, or anti-bot bypass.
- No live robots.txt fetching from the internet.
- No retries or automatic retry logic.
- No cookies, sessions, or login state.
- No scheduled task integration for live retrieval.
- No automatic parsing of retrieved fixtures (user must run existing fixture parsers separately).

## Required Safety Settings

Live retrieval is **disabled by default**. All of the following must be configured before live retrieval will proceed:

### Environment Variables

```ini
MARKETSENTRY_LIVE_RETRIEVAL_ENABLED=true
MARKETSENTRY_ALLOWED_LIVE_SOURCES=redfin
MARKETSENTRY_LIVE_USER_AGENT=MarketSentry/1.0
MARKETSENTRY_LIVE_CONTACT_EMAIL=user@example.com
MARKETSENTRY_MAX_REQUESTS_PER_MINUTE=6
MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE=true
```

### Local Robots Policy

A local copy of Redfin's robots.txt must be saved before live retrieval:

```text
data/policies/robots/redfin_robots.txt
```

This file is not fetched from the internet. You must manually save it.

### Dry-Run Approval

A recent dry-run approval for the target URL is required (default: within 24 hours). Run the dry-run command first:

```bash
marketsentry dry-run-redfin-search --url "https://www.redfin.com/city/..."
marketsentry dry-run-redfin-property --url "https://www.redfin.com/CA/Temecula/.../home/..."
```

## How to Do a Dry-Run

Dry-run preview shows what would happen without making any network calls:

```bash
# Search page dry-run
marketsentry dry-run-redfin-search --url "https://www.redfin.com/city/19701/CA/Temecula/filter/..."

# Property detail dry-run
marketsentry dry-run-redfin-property --url "https://www.redfin.com/CA/Temecula/12345-Main-St-92592/home/6574263"

# Or use the retrieve commands with --dry-run-only
marketsentry retrieve-redfin-search --url "..." --dry-run-only
marketsentry retrieve-redfin-property --url "..." --dry-run-only
```

## How to Provide Local Robots Policy

1. Open `https://www.redfin.com/robots.txt` in your browser.
2. Save the content to `data/policies/robots/redfin_robots.txt`.
3. The system reads this file locally and checks paths against it.
4. The system does **not** fetch robots.txt from the internet.

## How to Enable Live Retrieval Explicitly

1. Set all required environment variables (see above).
2. Save the local robots policy file.
3. Run a dry-run command for your target URL.
4. Run the retrieve command with `--force-live`:

```bash
marketsentry retrieve-redfin-search --url "https://www.redfin.com/city/..." --force-live
marketsentry retrieve-redfin-property --url "https://www.redfin.com/CA/..." --force-live
```

## How Retrieved Pages Are Saved as Fixtures

Search pages are saved to:
```text
data/raw/redfin/search/redfin_search_YYYYMMDD_HHMMSS.html
```

Property detail pages are saved to:
```text
data/raw/redfin/details/redfin_property_<home_id>_YYYYMMDD_HHMMSS.html
```

Each fixture has a companion metadata JSON file:
```text
data/raw/redfin/details/redfin_property_<home_id>_YYYYMMDD_HHMMSS.json
```

The metadata file contains:
- `source_url`: Original URL retrieved.
- `source_site`: Always "redfin".
- `request_type`: "search" or "property_detail".
- `retrieved_at`: ISO timestamp of retrieval.
- `fixture_path`: Path to the saved HTML file.
- `content_length`: Size of the HTML content.

Existing fixtures are never overwritten.

## How Retrieved Fixtures Are Processed

After retrieving and saving fixtures, process them through the local parsing pipeline:

```bash
# Process all retrieved fixtures (search + detail + recalc + export)
marketsentry process-redfin-retrieved-fixtures

# Or process search/detail separately
marketsentry process-redfin-search-fixtures
marketsentry process-redfin-detail-fixtures

# Retrieve and process in one step
marketsentry retrieve-and-process-redfin-property --url "..." --force-live
```

### How the Processing Manifest Works

The manifest at `data/processed/redfin_fixture_processing_manifest.csv` tracks processed fixtures by content hash. Unchanged fixtures are skipped by default. Use `--force-reprocess` to override.

### How Capture Queue Items Are Marked Captured

When a processed fixture's `source_url` matches a pending fixture capture queue request, the request is automatically marked as captured. Only successfully processed fixtures trigger this.

### How to Continue Using Manual Fixtures Instead

You can continue saving Redfin pages manually and processing them the same way:

```bash
# Save HTML to data/raw/redfin/search/ or data/raw/redfin/details/
# Then process:
marketsentry process-redfin-retrieved-fixtures
```

Or use the original parsers directly:

```bash
marketsentry parse-redfin-fixtures --dir data/raw/redfin/search
marketsentry enrich-redfin-details --dir data/raw/redfin/details
```

See [REDFIN_RETRIEVED_FIXTURE_PROCESSING.md](REDFIN_RETRIEVED_FIXTURE_PROCESSING.md) for the complete processing guide.

## Why Scheduled Tasks Do Not Run Live Retrieval by Default

- Scheduled tasks (Windows Task Scheduler scripts) only run local workflows on existing data.
- Live retrieval requires explicit `--force-live` flag and full environment configuration.
- No scheduled script calls `retrieve-redfin-search` or `retrieve-redfin-property`.
- This is by design: live retrieval must be a conscious, manual decision.

## Troubleshooting Blocked Retrievals

If your retrieval is blocked, check these common causes:

| Block Reason | Fix |
|---|---|
| Live retrieval globally disabled | Set `MARKETSENTRY_LIVE_RETRIEVAL_ENABLED=true` |
| Source not allowlisted | Set `MARKETSENTRY_ALLOWED_LIVE_SOURCES=redfin` |
| User-Agent not configured | Set `MARKETSENTRY_LIVE_USER_AGENT=MarketSentry/1.0` |
| No local robots policy | Save `redfin_robots.txt` to `data/policies/robots/` |
| Robots policy disallows path | Check the path against your local robots.txt |
| Rate limit exceeded | Wait and retry after the cooldown period |
| No dry-run approval | Run `dry-run-redfin-search` or `dry-run-redfin-property` first |
| Missing --force-live | Add `--force-live` to the retrieve command |

Use `marketsentry retrieval-policy-check` to diagnose policy decisions:

```bash
marketsentry retrieval-policy-check --source redfin --url "https://www.redfin.com/..." --mode live_http
```

Use `marketsentry retrieval-audit-report` to review audit logs.

## Compliance Warnings

- **Do not bypass access controls.** If a page requires login, do not attempt to access it.
- **Do not use login-required content.** Only access publicly available pages.
- **Do not bypass CAPTCHAs or anti-bot systems.** If Redfin blocks the request, respect the block.
- **Prefer authorized APIs/feeds when available.** If Redfin offers an API or data feed, use that instead.
- **Respect rate limits.** The system enforces a configurable rate limit (default: 6 requests/minute).
- **Identify your client.** Always configure a descriptive User-Agent and contact email.
