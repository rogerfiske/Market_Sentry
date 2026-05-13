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

## Cross-Site Alert Analytics (Milestone 27)

### What Alert Burden Means

Alert burden measures the cumulative weight of cross-site trend alerts for a property. It helps operators identify which properties have the most unresolved cross-site discrepancies and may benefit from priority review.

Burden labels:

- **none**: No open alerts. No action needed.
- **low**: 1-2 low or warning open alerts. Routine monitoring sufficient.
- **moderate**: 3+ open alerts or any high open alert. Monitor cross-site data.
- **high**: 2+ high/critical open alerts or any critical open alert. Review cross-site data.
- **elevated_review**: Repeated high/critical alerts from different snapshots over time. Prioritize review.

Alert burden is a neutral analytical measure. It does not indicate seller intent, property quality, or purchase suitability. Higher burden means more unresolved cross-site discrepancies need human attention.

### What Repeated Patterns Mean

Repeated patterns identify recurring alert types for a property over multiple snapshots. A pattern requires at least 2 matching events to trigger.

Examples:

- **repeated_confidence_drop**: Confidence scores have dropped across multiple snapshots, suggesting unstable cross-site data.
- **repeated_status_discrepancy**: Listing status disagreement has recurred, possibly indicating data lag or stale fixtures.
- **repeated_price_agreement_degraded**: Price disagreement has recurred across sources.
- **repeated_dom_agreement_degraded**: DOM value disagreement has recurred across sources.
- **improving_source_quality_pattern**: Source quality has improved across multiple snapshots.

Patterns are informational. They help operators understand whether an issue is one-time or recurring.

### Alert Analytics Report

```bash
# Export alert analytics report
marketsentry export-cross-site-alert-analytics-report

# View summary
marketsentry cross-site-alert-analytics-summary
```

The analytics report includes per-property: total/open/high-critical alert counts, oldest open alert age, latest alert timestamp, most common alert type and severity, repeated patterns, burden score and label, recommended review action, unresolved alert types, and resolved/acknowledged counts.

### How to Use Alert Analytics During Watchlist Review

1. Run `marketsentry cross-site-alert-analytics-summary` to see which properties have the highest alert burden.
2. Focus review time on properties labeled **high** or **elevated_review**.
3. Check repeated patterns to understand whether discrepancies are one-time or recurring.
4. Use `marketsentry export-cross-site-alert-analytics-report` to export a CSV for offline review.
5. Acknowledge or resolve individual alerts using the Milestone 26 alert management commands.
6. Re-run analytics after resolving alerts to see updated burden levels.

### Reminder: Analytics Are Review Aids, Not Recommendations

Cross-site alert analytics are analytical review aids for human operators. They help identify where to focus review effort based on alert burden and recurring patterns. They are not purchase recommendations, do not infer seller intent, and do not overwrite Redfin source-of-truth fields, watchlist status, or Quiet Score gatekeeper results.

## Cross-Site Alert Triage Workflow (Milestone 28)

### How to Export a Triage CSV

Export filtered alerts to a triage CSV for offline review:

```bash
# Export open alerts (default)
marketsentry export-cross-site-alert-triage

# Export with severity filter
marketsentry export-cross-site-alert-triage --severity high

# Include acknowledged alerts
marketsentry export-cross-site-alert-triage --include-acknowledged

# Export specific property
marketsentry export-cross-site-alert-triage --property-id 42
```

The CSV file is saved to `data/exports/cross_site_alert_triage_YYYYMMDD_HHMMSS.csv`.

### How to Edit triage_decision

Open the CSV in a spreadsheet editor. Each row has two editable columns:

- **triage_decision**: Set to one of the 6 allowed values (see below)
- **triage_notes**: Optional notes to attach to the alert

### Allowed Triage Decisions

| Decision | Changes Alert Status? | Effect |
| --- | --- | --- |
| keep_open | No | Alert stays open. Default value. |
| acknowledge | Yes -> acknowledged | Marks alert as seen by operator. |
| resolve | Yes -> resolved | Marks alert as addressed. |
| archive | Yes -> archived | Marks alert as no longer relevant. |
| needs_reparse | No | Records note for fixture re-parse needed. |
| needs_manual_review | No | Records note for manual review needed. |

### How to Import Triage Decisions

After editing the CSV, import it to apply decisions:

```bash
# Import triage decisions
marketsentry import-cross-site-alert-triage --file data/exports/cross_site_alert_triage_*.csv

# Force apply if alert status changed since export
marketsentry import-cross-site-alert-triage --file <path> --force-status-mismatch
```

The import validates each row before applying:

- The alert must still exist in the database
- The triage decision must be one of the 6 allowed values
- The current alert status must match what was in the CSV (unless `--force-status-mismatch` is used)
- Invalid or mismatched rows are skipped and reported in the output

### What Changes Alert Status and What Does Not

Only these three decisions change alert status:

- **acknowledge** -> alert_status = "acknowledged"
- **resolve** -> alert_status = "resolved"
- **archive** -> alert_status = "archived"

These three decisions do NOT change alert status:

- **keep_open** -> alert stays in current status
- **needs_reparse** -> alert stays in current status, note recorded
- **needs_manual_review** -> alert stays in current status, note recorded

### Triage History

All triage actions are recorded in the `cross_site_alert_triage_actions` database table. This provides an audit trail showing which alerts were triaged, when, what decision was made, and any notes. Use this history to track triage activity over time.

### Reminder: Triage Is Not a Purchase Recommendation

Cross-site alert triage is operational alert management for human operators. It helps manage review workload by batch-updating alert statuses. Triage does not modify watchlist status, Redfin source-of-truth fields, property data, user decisions, or Quiet Score gatekeeper results. Triage decisions do not infer seller intent and are not purchase recommendations.

## Cross-Site Alert Hygiene Reports (Milestone 29)

### What Is Alert Hygiene

Alert hygiene is a scheduled review process that identifies alerts needing attention. It scans all cross-site trend alerts and flags stale open alerts, old acknowledged alerts, resolved archive candidates, pending reparse/manual review items, high-burden properties, and repeated unresolved patterns.

Hygiene reports are review aids. They do not automatically archive alerts, change watchlist status, modify Redfin source-of-truth fields, or change Quiet Score gatekeeper results.

### How to Run a Hygiene Check

```bash
marketsentry cross-site-alert-hygiene-check
```

Options:

- `--db` - database path (default: from config)
- `--open-stale-days` - days before open alerts are flagged stale (default: 7)
- `--ack-stale-days` - days before acknowledged alerts are flagged (default: 14)
- `--resolved-archive-days` - days before resolved alerts become archive candidates (default: 30)
- `--format` - report format: csv, md, or both (default: both)

### How to Export a Hygiene Report

```bash
marketsentry export-cross-site-alert-hygiene-report --format both
```

Exports to:

- `data/exports/cross_site_alert_hygiene_YYYYMMDD_HHMMSS.csv`
- `data/exports/cross_site_alert_hygiene_YYYYMMDD_HHMMSS.md`

### Using the Hygiene Report with the Triage Workflow

The hygiene report identifies alerts that may need triage action. The recommended workflow:

1. Run `marketsentry cross-site-alert-hygiene-check` to see current alert state
2. Review the hygiene report for stale alerts and archive candidates
3. Export a triage CSV: `marketsentry export-cross-site-alert-triage --status open`
4. Edit the triage CSV in a spreadsheet, setting triage_decision for each alert
5. Import the triage CSV: `marketsentry import-cross-site-alert-triage --file <path>`
6. Re-run the hygiene check to confirm issues are resolved

### Scheduled Hygiene Reports

The batch script `scripts/run_alert_hygiene_report.bat` runs the hygiene check automatically. It can be scheduled via Windows Task Scheduler for regular review reminders (e.g., weekly on Fridays). The script logs to `logs/scheduled/` and does not invoke live retrieval.

### Reminder: Hygiene Is a Review Aid

Alert hygiene reports do not change alert status, watchlist state, property data, or Quiet Score. They identify alerts that the operator should review and provide recommended next actions. The operator decides which actions to take through the triage workflow.

## Cross-Site Alert Archive Policy (Milestone 30)

### What Is Archive Policy

Archive policy provides a dedicated workflow for reviewing old resolved cross-site alerts for archival. Unlike the triage workflow (Milestone 28), which handles active alert management across all statuses, the archive policy workflow focuses specifically on resolved alerts that may be ready for archiving.

### How to Export Archive Candidates

```bash
# Export resolved alerts older than 30 days
marketsentry export-cross-site-alert-archive-candidates

# Custom age threshold
marketsentry export-cross-site-alert-archive-candidates --resolved-age-days 60

# Filter by property or severity
marketsentry export-cross-site-alert-archive-candidates --property-id 42
marketsentry export-cross-site-alert-archive-candidates --severity high
```

The CSV includes alert details, age, and editable `archive_decision` and `archive_notes` columns.

### Archive Candidate Criteria

An alert is eligible for archive review when:

- alert_status is `resolved`
- resolved/last-updated age >= 30 days (or `created_at` age >= 30 days as fallback)
- alert is not already `archived`
- alert is not `open` or `acknowledged`
- alert notes do not contain `[no_archive]` marker

### How to Edit Archive Decisions

Open the CSV in a spreadsheet editor. For each row, set `archive_decision` to:

- **keep_resolved** (default): No status change. Alert stays resolved.
- **archive**: Status changed to archived. Action recorded.
- **reopen**: Status changed to open. Action recorded.
- **no_archive**: No status change. `[no_archive]` marker added to notes. Alert excluded from future archive candidates.

### How to Import Archive Decisions

```bash
marketsentry import-cross-site-alert-archive-decisions --file <path>
```

Use `--force-status-mismatch` if alert statuses have changed since the export.

### Viewing Archive Summary

```bash
marketsentry cross-site-alert-archive-summary
```

Shows eligible candidates, already archived alerts, no_archive marked alerts, and recommended next actions.

### How Archive Policy Relates to Other Workflows

- **Hygiene reports** (Milestone 29) identify resolved archive candidates and recommend running the archive candidate export
- **Triage workflow** (Milestone 28) handles active alert management (acknowledge, resolve, archive, etc.)
- **Archive policy** (Milestone 30) handles dedicated archive review for old resolved alerts
- All three workflows are independent: each serves a distinct purpose in the alert lifecycle

### Reminder: Archive Policy Does Not Auto-Archive

Archive policy is opt-in only. It does not automatically archive alerts, change watchlist status, modify Redfin source-of-truth fields, property data, user decisions, or Quiet Score gatekeeper results. The operator reviews and decides.

## Cross-Site Alert Expiration Policy (Milestone 31)

### What Are Expiration Profiles

Expiration profiles are named collections of age-based rules that identify alerts eligible for operator review or archive consideration. Three built-in profiles are provided with different age thresholds:

- **conservative**: Long thresholds (resolved 90d, acknowledged 45d, open info/warning 30d)
- **standard**: Balanced thresholds (resolved 60d, acknowledged 30d, open info/warning 21d)
- **aggressive_review_only**: Short thresholds (resolved 30d, acknowledged 14d, open info/warning 14d)

All profiles treat high/critical open alerts as review-only (never archive candidates).

### How to Preview a Profile

```bash
# Preview with default standard profile
marketsentry preview-cross-site-alert-expiration-policy

# Preview with conservative profile
marketsentry preview-cross-site-alert-expiration-policy --profile conservative
```

Preview shows candidate counts by proposed action (archive, review, keep). No mutations occur.

### How to Export Approval CSV

```bash
marketsentry export-cross-site-alert-expiration-approval --profile standard
```

The CSV includes alert details, the proposed action and reason, and two editable columns: `approval_decision` (default: `keep_current`) and `approval_notes`.

### Allowed Decisions

| Decision | Effect |
| --- | --- |
| keep_current | No change (default) |
| approve_action | Apply the proposed action (archive or review/keep with notes) |
| mark_no_archive | Append `[no_archive]` marker; exclude from future archive proposals |
| reopen | Set status to open |
| acknowledge | Set status to acknowledged |
| resolve | Set status to resolved |
| archive | Set status to archived |

### How to Import Approvals

```bash
marketsentry import-cross-site-alert-expiration-approval --file <path>
```

Use `--force-status-mismatch` if alert statuses have changed since the export.

### Why No Automatic Policy Application Occurs

Expiration profiles only generate preview and approval rows. They never apply actions automatically. All status mutations require the operator to:

1. Export an approval CSV
2. Review and edit the `approval_decision` column
3. Import the edited CSV

This preserves the human-in-the-loop principle established throughout the project.

### How Expiration Policy Relates to Other Workflows

- **Hygiene reports** (Milestone 29) identify alerts needing attention and recommend both archive and expiration workflows
- **Archive policy** (Milestone 30) focuses specifically on resolved alerts for dedicated archive review
- **Expiration policy** (Milestone 31) provides configurable age-based rules across all non-archived statuses
- Each workflow serves a distinct purpose; they complement rather than replace each other

### Reminder: Expiration Policy Does Not Change Watchlist Status

Expiration policy is an operational alert-state workflow only. It does not change watchlist status, active_watch_status, watch_priority, Redfin source-of-truth fields, property data, user decisions, or Quiet Score gatekeeper results.

## User-Defined Alert Expiration Profiles (Milestone 32)

Milestone 32 adds user-defined expiration profiles loaded from a local JSON config file.

### Writing the Example Config

```bash
marketsentry write-alert-expiration-profile-template
```

This writes an example to `config/alert_expiration_profiles.example.json`. Copy and edit it:

```bash
copy config\alert_expiration_profiles.example.json config\alert_expiration_profiles.json
```

### Config File Path

Default path: `config/alert_expiration_profiles.json`

This file is optional. If absent, only built-in profiles are used.

### Profile and Rule Fields

Each profile requires:

- `profile_name`: unique name (lowercase/snake_case recommended)
- `rules`: list of rule objects

Each rule requires:

- `rule_name`: unique within the profile
- `current_status`: open, acknowledged, resolved, or archived
- `min_age_days`: integer >= 0
- `proposed_action`: archive, review, keep, or reopen_review

Optional rule field:

- `severity`: string or list of info, warning, high, critical, any (default: any)

### Validation Rules

- High/critical open alerts may only propose review or keep (never archive)
- Archived alerts may only propose keep or review
- User profiles cannot silently override built-in profile names (conservative, standard, aggressive_review_only)
- Invalid configs are rejected with clear errors; built-in profiles remain usable

### Previewing with Custom Profile

```bash
marketsentry preview-cross-site-alert-expiration-policy --profile my_custom_review --profile-config config/alert_expiration_profiles.json
```

### Exporting Approval CSV with Custom Profile

```bash
marketsentry export-cross-site-alert-expiration-approval --profile my_custom_review --profile-config config/alert_expiration_profiles.json
```

### Reminder: Actions Still Require Approval Import

Custom profiles generate candidates only. To apply actions, the operator must:

1. Export the approval CSV
2. Edit `approval_decision` for each row
3. Import the edited CSV:

```bash
marketsentry import-cross-site-alert-expiration-approval --file data/exports/cross_site_alert_expiration_approval_*.csv
```

See also: [Alert Expiration Profiles](ALERT_EXPIRATION_PROFILES.md) for full config format, examples, and safety limits.

## Profile Comparison and Last-Used Profile (Milestone 33)

### Comparing Profiles Before Choosing

Before selecting a profile for expiration review, compare all available profiles side by side:

```bash
# Compare all built-in profiles
marketsentry compare-cross-site-alert-expiration-profiles

# Compare including custom profiles
marketsentry compare-cross-site-alert-expiration-profiles --profile-config config/alert_expiration_profiles.json
```

This shows candidate counts, archive/review/keep proposals, and affected properties per profile without performing any mutations.

### Setting a Default Profile

Set a last-used profile preference so you do not need to specify `--profile` on every command:

```bash
# Set default profile
marketsentry set-cross-site-alert-expiration-profile --profile conservative

# Check current preference
marketsentry get-cross-site-alert-expiration-profile

# Clear preference (revert to standard)
marketsentry clear-cross-site-alert-expiration-profile
```

When `--profile` is omitted from preview, export, or summary commands, the system uses the last-used profile (or falls back to "standard" if no preference is set).

### Reminder: Comparison and Preference Are Read-Only

Profile comparison does not mutate alerts. Last-used profile preference is a local convenience setting only. It does not change alert state, watchlist status, Redfin source-of-truth fields, or Quiet Score gatekeeper results.

## Alert Lifecycle Audit Trail (Milestone 34)

### What Is Lifecycle Audit

The lifecycle audit consolidates alert activity from triage, archive, and expiration workflows into a unified read-only event stream. It normalizes actions from all workflows into common event types and detects potential workflow gaps.

### Lifecycle Summary

```bash
# View aggregate lifecycle summary
marketsentry cross-site-alert-lifecycle-summary

# View lifecycle for one property
marketsentry cross-site-alert-lifecycle-summary --property-id 42
```

### Lifecycle Report

```bash
# Export lifecycle report (CSV)
marketsentry export-cross-site-alert-lifecycle-report

# Export both CSV and Markdown
marketsentry export-cross-site-alert-lifecycle-report --format both
```

### Show Alert Lifecycle

```bash
marketsentry show-cross-site-alert-lifecycle --alert-id 5
```

Shows the chronological event stream for a single alert.

### How Lifecycle Gaps Relate to Other Workflows

Lifecycle gaps identify where expected follow-up actions have not occurred:

- **open_no_triage**: Open alert needs triage export and review (Milestone 28)
- **needs_reparse_unresolved**: Re-parse fixture and run triage (Milestones 22-23, 28)
- **needs_manual_review_unresolved**: Manual review needed (Milestone 28)
- **acknowledged_stale**: Resolve or archive via triage (Milestone 28)
- **resolved_archive_candidate**: Consider archive policy (Milestone 30) or expiration (Milestone 31)
- **reopened_stale**: Review and resolve reopened alert (Milestone 28)

### Reminder: Lifecycle Audit Is Read-Only

The lifecycle audit does not change alert status, watchlist state, property data, Redfin source-of-truth fields, or Quiet Score gatekeeper results. It is an observability tool for human operators.

## Alert Lifecycle Trend Snapshots (Milestone 35)

### What Are Lifecycle Trend Snapshots

Lifecycle trend snapshots are append-only metric records that capture the state of alert lifecycle management at a point in time. They enable operators to track alert-management efficiency trends over time.

### Snapshot Command

```bash
marketsentry snapshot-cross-site-alert-lifecycle
marketsentry snapshot-cross-site-alert-lifecycle --force
```

Creates a snapshot of current lifecycle metrics. Skips same-day duplicates unless `--force` is used or a material change is detected.

### Trend Report Command

```bash
marketsentry export-cross-site-alert-lifecycle-trend-report
marketsentry export-cross-site-alert-lifecycle-trend-report --output-dir data/exports
```

Exports a CSV comparing the latest and previous snapshots.

### Time-to-Action Definitions

- **Time-to-first-triage**: Days from alert creation to the first action of any type (acknowledge, resolve, archive, reopen)
- **Time-to-resolution**: Days from alert creation to the first resolved action
- **Time-to-archive**: Days from alert creation to the first archived action

Each metric returns average days, median days, count of alerts used, and count of alerts skipped (no qualifying action).

### Throughput Metrics

- **Triage throughput (7d/30d)**: Count of triage workflow actions in the last 7 or 30 days
- **Resolution throughput (7d/30d)**: Count of actions resulting in resolved status in the last 7 or 30 days
- **Archive throughput (7d/30d)**: Count of actions resulting in archived status in the last 7 or 30 days

### Reminder: Lifecycle Trends Are Read-Only

Lifecycle trend snapshots do not change alert status, watchlist state, property data, or Quiet Score gatekeeper results. The only database write is the append-only snapshot record.

## Lifecycle Health Scoring (Milestone 36)

### What Is Lifecycle Health Scoring?

Lifecycle health scoring computes a 0-100 score for each watched property based on alert lifecycle metrics. Higher scores indicate better operational lifecycle health. The score is an operator-health metric, not a property desirability indicator.

### Health Labels

| Label | Range | Meaning |
| ----- | ----- | ------- |
| excellent | 90-100 | No immediate action needed |
| good | 75-89 | Continue monitoring |
| watch | 60-74 | Address gaps when possible |
| needs_review | 40-59 | Review recommended |
| attention_required | 0-39 | Immediate review recommended |

### Score Components

The score starts at 100 and deducts for operational health indicators:

- Open high/critical alerts: -10 each
- Lifecycle gaps: -5 each
- Stale open alerts: -4 each
- Needs reparse backlog: -6 each
- Needs manual review backlog: -6 each
- Repeated unresolved patterns: -3 each
- Old acknowledged alerts: -2 each
- High alert burden: -5

### Summary Command

```bash
python -m marketsentry cross-site-lifecycle-health-summary
python -m marketsentry cross-site-lifecycle-health-summary --property-id 1
```

### Report Export Command

```bash
python -m marketsentry export-cross-site-lifecycle-health-report
python -m marketsentry export-cross-site-lifecycle-health-report --format both --output-dir data/exports
```

### Reminder: Health Score Is Operational/Review-Only

Lifecycle health scores are operational metrics. They do not indicate property investment quality, seller intent, or purchase suitability. They do not change alert status, watchlist state, property data, or Quiet Score gatekeeper results.

## Lifecycle Health Trends (Milestone 37)

### What Are Lifecycle Health Trend Snapshots?

Lifecycle health trend snapshots are append-only records that capture per-property health scores at a point in time. By comparing consecutive snapshots, operators can track whether a property's operational health is improving, degrading, or stable.

### Health Snapshot Concept

Each snapshot records the full health state of a property: health score, health label, open alert counts, lifecycle gap counts, reparse/manual review backlogs, component summary, and recommended action. Snapshots are only created when material changes are detected (score delta >= 5, label change, alert count change, gap count change, or backlog count change). Use `--force` to create snapshots regardless.

### Health Snapshot Command

```bash
# Create health snapshots for all watched properties
marketsentry snapshot-cross-site-lifecycle-health

# Force snapshot even without material changes
marketsentry snapshot-cross-site-lifecycle-health --force
```

Output includes: properties scanned, snapshots created, snapshots skipped, material changes detected, and label counts.

### Health Trend Report Command

```bash
# Export lifecycle health trend report CSV
marketsentry export-cross-site-lifecycle-health-trend-report

# Custom output directory
marketsentry export-cross-site-lifecycle-health-trend-report --output-dir data/exports
```

The trend report compares current vs previous health snapshots and includes trend direction (improved, degraded, stable, new) for each property.

### Health Trend Summary Command

```bash
marketsentry cross-site-lifecycle-health-trend-summary
```

Shows: properties with health snapshots, improved/degraded/stable/new counts, attention_required and needs_review current counts, and recommended next actions.

### Scheduled Local Health Report

The batch script `scripts/run_lifecycle_health_report.bat` automates health reporting:

1. Exports the lifecycle health report (Milestone 36)
2. Creates health snapshots (Milestone 37)
3. Exports the lifecycle health trend report (Milestone 37)

The script logs to `logs/scheduled/` and does not perform live retrieval or alert/watchlist mutation.

### Reminder: Health Trends Are Operational/Review-Only

Lifecycle health trend snapshots are operational metrics. The only database write is the append-only snapshot record. Health trends do not change alert status, watchlist state, property data, or Quiet Score gatekeeper results. They do not indicate property investment quality, seller intent, or purchase suitability.

## Operations Digest (Milestone 38)

### What Is the Operations Digest?

The operations digest consolidates all local reports into a single concise operator summary. It provides a unified view of candidate review status, watchlist health, Effective DOM/churn, cross-site validation, alert hygiene, lifecycle health, and retrieval operations.

### Operations Digest Command

```bash
marketsentry operations-digest
```

Shows all digest sections, top review priorities, and recommended next local actions.

### Operations Digest Export Command

```bash
# Export as Markdown and CSV
marketsentry export-operations-digest

# Export CSV only
marketsentry export-operations-digest --format csv

# Export Markdown only
marketsentry export-operations-digest --format md
```

Exports to `data/exports/operations_digest_YYYYMMDD_HHMMSS.csv` and/or `.md`.

### Scheduled Operations Digest Report

The batch script `scripts/run_operations_digest_report.bat` automates digest export. It logs to `logs/scheduled/` and does not perform live retrieval or alert/watchlist mutation.

### Reminder: Operations Digest Is Read-Only

The operations digest is entirely read-only. It does not change candidate decisions, alert status, watchlist state, property data, or Quiet Score gatekeeper results. It does not indicate property investment quality, seller intent, or purchase suitability.

## Operations Digest History (Milestone 39)

### What Is Digest History?

Digest history tracks high-level operations changes over time through append-only snapshots. Each snapshot captures aggregate metric counts from the operations digest and computes a digest score (0-100) that reflects the current local review backlog.

### Digest Snapshot Command

```bash
marketsentry snapshot-operations-digest
marketsentry snapshot-operations-digest --force
```

Creates one aggregate snapshot row. Skips same-day/no-change snapshots unless `--force` is set. Material changes include: candidate backlog changes, active watched count changes, high/critical alert changes, lifecycle attention changes, digest score changes >= 5, and digest status label changes.

### Digest Comparison Report Command

```bash
marketsentry export-operations-digest-comparison-report --format csv
marketsentry export-operations-digest-comparison-report --format md
marketsentry export-operations-digest-comparison-report --format both
```

Exports snapshot-over-snapshot comparison to `data/exports/operations_digest_comparison_YYYYMMDD_HHMMSS.csv` and/or `.md`. Shows trend direction (improved, degraded, stable, new).

### Digest History Summary Command

```bash
marketsentry operations-digest-history-summary
```

Shows snapshot count, latest/previous digest scores and statuses, trend direction, backlog deltas, and recommended next local actions.

### Reminder: Digest History Is Operational and Review-Only

Digest history is an operational metrics tracking tool. It does not mutate candidate decisions, watchlist state, alert status, or property data. The digest score is a local review backlog metric and is not purchase advice, property desirability, or seller intent. Quiet Score gatekeeper remains unchanged.

## Portfolio Review Pack (Milestone 40)

### What Is the Portfolio Review Pack?

The Portfolio Review Pack is a local, printable review packet that consolidates property-level details into a single document for offline review. It pulls from watched properties, cross-site analytics, alert/lifecycle health, Effective DOM, Churn Index, and Quiet/Vibrancy scores to create per-property briefs ranked by review priority.

### Using the Review Pack for Offline Property Review

After building cross-site observations and running alert/lifecycle workflows, generate the review pack:

```bash
marketsentry export-portfolio-review-pack --format both
```

This exports a Markdown report and CSV with:

- Portfolio-level summary (counts, gatekeeper pass/fail, gas/garage evidence)
- Per-property briefs with all key metrics
- Review priority ranking (immediate_review through low_current_activity)
- Recommended local next actions

The Markdown report is designed to be printed or viewed offline for hands-on property review sessions.

### Reminder: Review Pack Is Read-Only

The review pack is an analytical aid. It does not change candidate decisions, alert status, watchlist state, property data, or Quiet Score gatekeeper results. It does not make purchase recommendations or infer seller intent.

## Portfolio Review Comparison (Milestone 41)

### Comparing Review Packs Over Time

After generating multiple review pack exports, compare them to track property-level changes:

```bash
marketsentry export-portfolio-review-comparison --format both
```

This compares the latest two review pack CSVs and produces a comparison report showing:

- Properties added or removed from the pack
- Priority and lifecycle health changes
- Alert burden, Effective DOM, Churn Index, and cross-site confidence movement
- Trend labels: improved, degraded, changed, unchanged, new, removed

The scheduled script `run_portfolio_review_pack_report.bat` now runs both review pack export and comparison automatically.

### Reminder: Comparison Is Read-Only

The comparison report is an analytical aid. It does not change candidate decisions, alert status, watchlist state, property data, or Quiet Score gatekeeper results.

## Portfolio Review Trends (Milestone 42)

### Using Trends for Offline Review

After accumulating multiple review pack CSV exports over time, analyze the full series for trends:

```bash
marketsentry portfolio-review-trends
marketsentry export-portfolio-review-trends --format both
```

The trend report shows:

- Portfolio-level burden over time (aggregate review burden score 0-100)
- Per-property trend direction: improved, degraded, stable, new, insufficient_data
- Priority label and lifecycle health label change counts
- Metric deltas for lifecycle health score, open alerts, Effective DOM v2, Churn Index, and cross-site confidence

Use these trends alongside comparison reports to identify which properties are consistently improving or degrading across multiple review cycles.

The scheduled script `run_portfolio_review_pack_report.bat` now runs pack export, comparison, and trend analysis automatically.

### Reminder: Trends Are Read-Only

The trend report is an analytical aid for offline review. It does not change candidate decisions, alert status, watchlist state, property data, or Quiet Score gatekeeper results.

## Portfolio Trend Alerts (Milestone 43)

### Using Trend Alert Digest for Offline Review

After generating trend reports, the alert digest highlights properties and portfolio metrics that crossed threshold rules:

```bash
marketsentry portfolio-trend-alerts
marketsentry export-portfolio-trend-alert-digest --format both
```

The alert digest flags:

- Aggregate burden score crossing warning (60) or high (80) thresholds
- Burden increases, label worsening, and backlog growth
- Individual property degradation, health score drops, alert increases, confidence drops, churn increases, and DOM v2 increases
- Severity levels: info, warning, high

Use the alert digest alongside trend and comparison reports to prioritize which properties need immediate review attention.

The scheduled script `run_portfolio_review_pack_report.bat` now runs pack export, comparison, trend analysis, and alert digest automatically.

### Reminder: Trend Alerts Are Read-Only

The alert digest is a local analytical aid for offline review. It does not change candidate decisions, alert status, watchlist state, property data, or Quiet Score gatekeeper results. No outbound notifications are sent.
