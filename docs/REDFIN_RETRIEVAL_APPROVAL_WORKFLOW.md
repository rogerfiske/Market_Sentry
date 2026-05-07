# Redfin Retrieval Approval Workflow

This document explains the two-step approval workflow for Redfin batch live retrieval (Milestone 19).

## Why the Approval Package Exists

Milestones 14-18 established compliance-aware retrieval with policy enforcement, fixture-first HTTP retrieval for Redfin, a processing pipeline, and a batch orchestrator for pending capture queue items. The approval workflow adds an explicit human review step before any batch live retrieval:

1. **Prevent accidental mass retrieval.** The operator reviews each URL before approving.
2. **Document intent.** The approval CSV provides a record of what was approved and why.
3. **Enforce human-in-the-loop.** No batch retrieval without explicit user approval per item.
4. **Support audit.** The approval manifest tracks every approval package and retrieval run.

## How to Prepare an Approval Package

Run the prepare command to dry-run all pending Redfin capture queue items:

```bash
# Prepare approval package for all pending Redfin items
marketsentry prepare-redfin-retrieval-approval

# Limit to a specific number of items
marketsentry prepare-redfin-retrieval-approval --max-items 10

# Filter by request type
marketsentry prepare-redfin-retrieval-approval --request-type property_detail
```

This produces two files in `data/exports/retrieval_approvals/`:

```text
redfin_batch_approval_<run_id>.csv    # User-editable approval CSV
redfin_batch_approval_<run_id>.md     # Markdown summary for reference
```

No network calls are performed by this command.

## How to Review the Approval CSV

Open the CSV file in a spreadsheet editor (Excel, Google Sheets, LibreOffice Calc, etc.) or a text editor.

Each row represents a pending capture queue item with its dry-run policy status:

| Column | Description |
|--------|-------------|
| approval_run_id | Unique ID for this approval package |
| capture_request_id | ID of the capture queue item |
| source_site | Always "redfin" |
| source_url | URL to be retrieved |
| normalized_url | Normalized form of the URL |
| request_type | "search" or "property_detail" |
| suggested_fixture_path | Where the fixture would be saved |
| policy_decision | Dry-run policy decision (ALLOWED, BLOCKED, etc.) |
| policy_reasons | Explanation of policy check results |
| compliance_passed | Whether compliance check passed |
| robots_passed | Whether robots policy check passed |
| rate_limit_passed | Whether rate limit check passed |
| dry_run_approved | Whether dry-run approval was recorded |
| network_call_performed | Always false in the approval CSV |
| approved_for_live | **User-editable.** Set to `true` to approve. |
| user_notes | **User-editable.** Optional notes. |

## How to Approve Selected Rows

1. Review each row's `policy_decision` and `policy_reasons`.
2. For items you want to retrieve live, change `approved_for_live` from `false` to `true`.
3. Optionally add notes in the `user_notes` column.
4. Save the CSV file.

Items with `approved_for_live=false` (the default) will be skipped during retrieval.

## How to Retrieve Approved Rows

Run the retrieve command with `--force-live` and the path to the edited approval CSV:

```bash
# Retrieve approved items
marketsentry retrieve-approved-redfin-batch \
    --approval-file "data/exports/retrieval_approvals/redfin_batch_approval_<run_id>.csv" \
    --force-live

# Retrieve and process through parsing pipeline
marketsentry retrieve-approved-redfin-batch \
    --approval-file "data/exports/retrieval_approvals/redfin_batch_approval_<run_id>.csv" \
    --force-live --process-after-retrieval

# Validate and preview only (no retrieval)
marketsentry retrieve-approved-redfin-batch \
    --approval-file "data/exports/retrieval_approvals/redfin_batch_approval_<run_id>.csv" \
    --dry-run-only
```

## Why --force-live Is Still Required

Even with `approved_for_live=true` in the CSV, the `--force-live` flag is required on the command line. This ensures:

1. The operator consciously opts in to live retrieval at execution time.
2. Accidental runs of the retrieve command without `--force-live` perform no network calls.
3. Consistency with the Milestone 16 and 18 retrieval commands.

Without `--force-live`, the command prints a blocked message and exits cleanly.

## Policy Re-Evaluation at Retrieval Time

All Milestone 14-18 policy checks are re-evaluated per item at retrieval time:

- **Compliance check**: Source must be allowed.
- **Robots policy check**: URL must be allowed by local robots.txt.
- **Rate limit check**: Must not exceed configured rate limit.
- **Dry-run approval check**: A recent dry-run approval must exist.

If any policy check fails at retrieval time, the item is blocked even if the user approved it in the CSV. This prevents retrieval of items whose policy status changed between preparation and retrieval.

## How to Inspect Audit Logs and Manifests

### Approval Manifest

The append-only manifest at `data/processed/redfin_retrieval_approval_manifest.csv` tracks every approval package and retrieval run:

| Column | Description |
|--------|-------------|
| approval_run_id | Unique ID for the approval package |
| created_at | When the package was created |
| pending_scanned | Number of pending items scanned |
| approval_rows_written | Number of rows written to the CSV |
| approval_csv_path | Path to the approval CSV |
| approval_summary_path | Path to the Markdown summary |
| approved_count_when_imported | Number of approved rows when imported |
| retrieved_count | Number successfully retrieved |
| blocked_count | Number blocked at retrieval |
| failed_count | Number that failed |
| notes | Additional notes |

### Retrieval Audit Logs

Use the existing audit log tools:

```bash
marketsentry retrieval-audit-report
```

### Dashboard

Open the Streamlit dashboard and navigate to "Retrieval Operations" > "Approval Packages" to view the approval manifest and latest CSV files:

```bash
streamlit run src/marketsentry/dashboard_app.py
```

Or use the CLI summary:

```bash
marketsentry retrieval-operations-summary
```

## How to Use Manual Fixture Capture Instead

You can always skip the approval workflow and use manual fixture capture:

1. Browse to the URL in your browser.
2. Save the page as HTML to the suggested fixture path.
3. Mark the capture request as captured:
   ```bash
   marketsentry mark-fixture-captured --capture-request-id <id> --fixture-path "path/to/file.html"
   ```
4. Process the fixture:
   ```bash
   marketsentry process-redfin-retrieved-fixtures
   ```

## No Scheduled Live Retrieval by Default

Scheduled tasks (Windows Task Scheduler scripts) do not invoke:
- `prepare-redfin-retrieval-approval`
- `retrieve-approved-redfin-batch`
- `retrieve-pending-redfin-fixtures` with `--force-live`
- `retrieve-redfin-search` or `retrieve-redfin-property`

Live retrieval remains a conscious, manual decision requiring human oversight.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "No pending Redfin capture requests found" | Add items to the capture queue via dry-run or policy check |
| "Approval CSV not found" | Check the file path |
| "Mixed approval_run_id" | Ensure all rows have the same approval_run_id |
| "Capture request not found or no longer pending" | The item may have been captured or archived |
| "URL mismatch" | The queue item's URL changed since the approval was prepared |
| "BLOCKED: requires --force-live" | Add `--force-live` to the command |
| "No approved rows to retrieve" | Edit the CSV and set approved_for_live=true for desired items |

## Stale Approval Package Guidance

Approval packages with unretrieved approved rows older than 24 hours are flagged by the retrieval health check. Policy checks are re-evaluated at retrieval time, so stale approvals may fail if policy conditions changed.

To check for stale approvals:

```bash
marketsentry retrieval-health-check
```

If an approval package is stale, re-run `marketsentry prepare-redfin-retrieval-approval` to generate a fresh package with current policy evaluations.

## Compliance Warnings

- **Do not bypass access controls.** If a page requires login, do not approve it for retrieval.
- **Do not bypass CAPTCHAs or anti-bot systems.** If Redfin blocks the request, respect the block.
- **Prefer authorized APIs/feeds when available.** If Redfin offers an API or data feed, use that instead.
- **Respect rate limits.** The system enforces a configurable rate limit per item.
- **Identify your client.** Always configure a descriptive User-Agent and contact email.
