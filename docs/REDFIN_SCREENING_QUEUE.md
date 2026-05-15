# Redfin Screening Queue

## Overview

The Redfin Screening Queue is a pre-candidate screening stage that provides an operator-friendly queue for initial property screening. Properties enter the screening queue via CSV import or saved Redfin search fixture parsing, and are promoted to the full candidate review queue only when the operator explicitly clicks "Save for Analysis."

This is entirely local-only. No live retrieval, no browser automation, no outbound notifications, no credential storage.

## How the Screening Queue Differs from the Candidate Review Queue

| Aspect | Screening Queue | Candidate Review Queue |
|--------|----------------|----------------------|
| Purpose | Initial triage of potential properties | Full analysis and monitoring |
| Entry method | CSV import or fixture import | Save for Analysis from screening, or direct URL import |
| Data depth | URL + optional summary fields | Full enrichment from detail pages |
| Actions | Open, Save for Analysis, Reject, Hold | Decision (save/reject/maybe/hold), scoring, noise notes |
| Promotion | "Save for Analysis" moves to candidate queue | "Save" decision promotes to watchlist |

Properties in the screening queue are not yet candidates. They become candidates only when the operator explicitly saves them for analysis.

## Importing Redfin URLs into Screening

### CSV Import

Create a CSV file with at least a `redfin_url` column:

```csv
redfin_url,address,city,price,beds,baths,sqft,notes
https://www.redfin.com/CA/Murrieta/12345-Example-St-92562/home/1234567,12345 Example St,Murrieta,499000,3,2,1800,Looks promising
https://www.redfin.com/CA/Temecula/67890-Sample-Ave-92592/home/7654321,,,550000,,,,
```

Run:

```bash
marketsentry import-redfin-screening-urls --file data/imports/redfin_screening_urls.csv
```

Optional CSV columns: `address`, `city`, `price`, `beds`, `baths`, `sqft`, `notes`. If address, city, or zip are not provided, they will be extracted from the Redfin URL where possible.

Duplicate URLs (by normalized Redfin URL) are automatically skipped.

### Saved Search Fixture Import

If you have saved Redfin search result pages as HTML files:

```bash
marketsentry import-redfin-screening-fixture --file data/raw/redfin/search/murrieta_search.html
```

This parses the saved HTML locally to extract property URLs and inserts them into the screening queue. This does not fetch anything from Redfin. The HTML file must already exist on your local disk.

## Using Clickable Links

The screening queue table in both the dashboard and the Markdown export includes clickable Redfin URLs. In the dashboard, these appear in the "Redfin URL" column. In the Markdown export, they render as `[View](https://www.redfin.com/...)` links.

To mark that you have opened a link:

```bash
marketsentry mark-screening-item-opened --screening-id 3
```

Or use the "Mark Opened" form in the dashboard.

## Saving for Analysis

When you decide a property is worth full analysis:

```bash
marketsentry save-screening-item-for-analysis --screening-id 3 --notes "Good location"
```

Or use the "Save for Analysis" form in the dashboard.

This:

1. Creates a candidate in the candidate_review_queue (or links to an existing one if the URL already exists).
2. Marks the screening item as `saved_for_analysis`.
3. Records the linked `candidate_id` on the screening item.
4. Does not duplicate candidates.

After saving for analysis, you can proceed with the normal candidate workflow: enrich from saved detail HTML, enter Quiet/Vibrancy scores, make a decision, and optionally promote to the watchlist.

## Rejecting and Holding

### Reject

```bash
marketsentry reject-screening-item --screening-id 5 --notes "Price too high"
```

Marks the item as rejected. It remains in the screening queue for audit but will not be promoted.

### Hold

```bash
marketsentry hold-screening-item --screening-id 7 --notes "Wait for price reduction"
```

Marks the item as hold for later review.

## When a Property Becomes a Candidate

A screening item becomes a candidate only when the operator explicitly runs "Save for Analysis." This is the single transition point.

## When a Property Becomes Watched

A candidate becomes a watched property when the operator sets the candidate decision to "save" using the candidate-decision command. This is separate from the screening queue and follows the existing candidate workflow.

## Checking Status

```bash
marketsentry redfin-screening-status
```

Shows counts: total, new, opened, saved_for_analysis, rejected, hold, duplicate, error.

## Listing Screening Items

```bash
marketsentry list-redfin-screening-items
marketsentry list-redfin-screening-items --status new
marketsentry list-redfin-screening-items --limit 50
```

## Exporting the Screening Queue

```bash
marketsentry export-redfin-screening-queue
marketsentry export-redfin-screening-queue --format csv
marketsentry export-redfin-screening-queue --format md
```

Exports to `data/exports/redfin_screening_queue_YYYYMMDD_HHMMSS.csv` and/or `.md`.

## Dashboard

The Streamlit dashboard includes an "Initial Redfin Screening" section with:

- Summary metrics (total, new, opened, saved, rejected, hold, duplicate, error)
- Screening queue table with all items
- Action forms: Save for Analysis, Mark Opened, Reject, Hold
- Import instructions with expected CSV format and fixture paths
- Export button

Launch the dashboard:

```bash
streamlit run src/marketsentry/dashboard_app.py
```

## Why This Does Not Scrape Redfin

The screening queue is a local data management tool. All data comes from:

- CSV files you create manually
- HTML files you save manually from your browser

No HTTP requests are made to Redfin or any other website. No browser automation is used. No CAPTCHAs, logins, paywalls, or anti-bot protections are bypassed.

## Why This Is Safe and Local-Only

- All operations read/write only the local SQLite database
- No network connections are made
- No credentials are stored or requested
- No notifications are sent
- No browser automation is used
- The Quiet Score gatekeeper remains unchanged
- Walkability fields are not added
