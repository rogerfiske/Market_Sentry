# Decision 006: Watchlist Monitoring Snapshots

**Date:** 2026-05-05

**Status:** Accepted

**Context:** Milestone 7 - Watchlist Monitoring Snapshots and Change Detection

## Decision

Implement watchlist monitoring using periodic snapshots of watched properties stored in the `property_observation_snapshots` table. Snapshots capture property state from existing database data (watched_properties, listing_events, cross_site_observations) and enable change detection over time.

## Rationale

### Why Snapshots Before County Verification

County Recorder/Assessor integration (originally planned as Milestone 7) has been deferred to Milestone 8. Watchlist monitoring snapshots are implemented first because:

1. **Immediate Value**: Users who have promoted properties to their watchlist need a way to monitor changes over time without waiting for county verification.

2. **Foundation for Future Features**: Snapshot infrastructure establishes the historical tracking foundation needed for county verification comparisons.

3. **Progressive Enhancement**: Snapshots work with existing data and don't require new external data sources.

4. **Validation of Cross-Site Enrichment**: Monitoring enables validation of cross-site discrepancy detection over time.

### Snapshot Data Model

The `property_observation_snapshots` table was extended with additional fields to support comprehensive monitoring:

**Original Fields:**
- snapshot_id, property_id, snapshot_date, source_site
- listing_status, price, displayed_dom, effective_dom
- quiet_score, vibrancy_score, garage_spaces, gas_service
- listing_history_hash, property_detail_hash, raw_source_url, notes

**Added Fields (Milestone 7):**
- effective_dom_delta
- listing_churn_count, dom_reset_count, sale_rent_alternation_count
- cross_site_confidence_score
- price_discrepancy_flag, status_discrepancy_flag, dom_discrepancy_flag
- price_change_count

These fields enable tracking of:
- Effective DOM metrics and listing activity
- Cross-site data quality indicators
- Discrepancy patterns over time

### Snapshot Creation Workflow

1. **Data Sources**: Snapshots are built from existing database tables:
   - `watched_properties`: Current property data (Redfin as source of truth)
   - `listing_events`: Historical listing activity
   - `cross_site_observations`: Latest observations from Zillow, Realtor.com, Homes.com, Compass

2. **Cross-Site Integration**: Each snapshot includes:
   - Cross-site confidence score (how many sources agree with Redfin price)
   - Discrepancy flags (price, status, DOM mismatches)
   - Latest cross-site observations used for comparison

3. **Recalculation**: Snapshots recalculate derived metrics:
   - Effective DOM from listing events
   - Cross-site confidence from latest observations
   - Listing history hash for change detection
   - Property detail hash for structural change detection

4. **No Live Data**: All snapshot data comes from existing database records. No network calls or scraping is performed.

### Change Detection

Change detection compares the current snapshot to the previous snapshot for the same property.

**Detected Changes:**
- **Price Changes**: Any difference, with direction (increased/decreased) and amount
- **Status Changes**: Listing status differences (active, pending, sold, etc.)
- **DOM Changes**: Displayed DOM and Effective DOM differences
- **Score Changes**: Quiet/Vibrancy score changes >= 0.5 threshold
- **Garage/Gas Changes**: Property characteristic changes
- **Discrepancy Changes**: Cross-site flag changes

**Material Change Definition:**
Material changes are changes that warrant a new snapshot on the same day:
- Price change
- Listing status change
- Displayed DOM change
- Effective DOM change
- Discrepancy flag change (price, status, DOM)

Non-material changes (e.g., only listing_history_hash changed) do not trigger a new same-day snapshot.

### Idempotency and Duplicate Handling

**Rule:** Allow one snapshot per property per run timestamp. If a user runs `snapshot-watchlist` twice on the same day:

1. Check if a snapshot already exists for the property today
2. If yes, compare current property data to the latest snapshot
3. If material fields changed, create new snapshot
4. If no material changes, skip snapshot and return "no material changes" message

**Benefits:**
- Prevents meaningless duplicate snapshots
- Allows manual re-runs without pollution
- Supports scheduled daily/weekly runs
- Material changes always captured

**Alternative Considered:** Always create append-only snapshots regardless of duplicates. Rejected because it creates noise and makes change tracking harder.

### Watched Property Status Updates

**Decision:** Watched property `active_watch_status` is NOT automatically changed based on cross-site status disagreements.

**Rationale:**
- Cross-site status conflicts may be temporary or incorrect
- Redfin remains the primary source of truth
- Status changes should be under user/system review, not automatic
- Monitoring report provides status signals for manual review

Snapshots capture `listing_status` from cross-site observations, and discrepancy flags highlight conflicts, but no automatic watchlist status changes occur.

### Monitoring Report Design

The watchlist monitoring report is a comprehensive CSV export showing:

**Property Identification:**
- property_id, address, city, ZIP, Redfin URL
- watch_priority, active_watch_status

**Current vs Previous Values:**
- current_price, previous_price, price_change, price_change_direction
- listing_status, previous_listing_status, status_changed
- displayed_dom, previous_displayed_dom
- effective_dom, previous_effective_dom, effective_dom_delta

**Property Characteristics:**
- quiet_score, vibrancy_score, quiet_gatekeeper_result
- garage_spaces, gas_service
- listing_churn_count, dom_reset_count, sale_rent_alternation_count

**Cross-Site Data Quality:**
- price_discrepancy_flag, status_discrepancy_flag, dom_discrepancy_flag
- cross_site_confidence_score

**Summary Fields:**
- change_summary: Human-readable change description
- warning_flags: Discrepancies, low quiet score
- positive_flags: Gas service, garage, excellent location
- user_notes: User annotations
- last_checked_date, snapshot_date

**Purpose:** The report is for watchlist monitoring and data quality assessment, NOT a purchase recommendation.

### Change Summary Generation

Each property in the monitoring report includes a `change_summary` field:

- **Price Changes**: "Price +$25,000" or "Price -$10,000"
- **Status Changes**: "Status: active -> pending"
- **Multiple Changes**: Semicolon-separated list
- **No Changes**: "No recent changes"

This provides quick at-a-glance change identification without opening snapshots.

### CLI Commands

Three new commands support the monitoring workflow:

1. **`snapshot-watchlist`**: Create snapshots for all active watched properties
   - Scans all active properties
   - Creates snapshots with change detection
   - Implements idempotency
   - Prints: scanned, created, skipped, changes detected

2. **`list-snapshots`**: List recent snapshots
   - Optionally filter by property_id
   - Shows: snapshot_id, property_id, address, date, price, effective_dom, status
   - Useful for verification and debugging

3. **`export-watchlist-monitoring-report`**: Export monitoring report CSV
   - Includes current and previous values
   - Shows changes and discrepancies
   - Generates change summaries and flags
   - Output: timestamped CSV in data/exports/

### Testing Strategy

Comprehensive tests cover:

- Snapshot creation for single and all properties
- Sparse data handling (missing fields)
- Latest snapshot retrieval
- Change detection (price, status, DOM, scores, discrepancies)
- No-material-change behavior
- Idempotency with and without material changes
- Multiple snapshots over time
- Monitoring report CSV columns and row counts
- Inactive property handling

All 251 tests pass (including existing tests from Milestones 1-6).

## Consequences

### Positive

1. **Historical Tracking**: Snapshots provide append-only history of property changes
2. **Change Detection**: Automated change identification reduces manual monitoring effort
3. **Data Quality**: Cross-site discrepancy tracking over time reveals data quality patterns
4. **Idempotency**: Same-day duplicate prevention reduces noise
5. **Foundation**: Snapshot infrastructure ready for county verification integration
6. **No Live Data**: Works entirely with existing database data, no network calls

### Negative

1. **Storage Growth**: Snapshots are append-only, database grows over time
2. **Manual Triggering**: User must remember to run `snapshot-watchlist` periodically
3. **No Alerts**: System does not proactively notify users of changes
4. **Schema Migration**: Existing databases need migration to add new snapshot columns

### Mitigations

- **Storage**: SQLite is efficient, snapshots are small, cleanup can be added later if needed
- **Manual Triggering**: CLI command is simple, can be scheduled with cron/Task Scheduler
- **No Alerts**: Future enhancement, monitoring report provides change visibility
- **Schema Migration**: `migrate_schema()` function safely adds columns if missing

## Future Enhancements

1. **Scheduled Snapshots**: Add cron/Task Scheduler integration
2. **Change Alerts**: Email or notification system for significant changes
3. **Snapshot Pruning**: Archive or delete very old snapshots
4. **Chart Generation**: Visualize price/DOM changes over time
5. **County Verification Integration**: Cross-reference snapshots with county ownership transfers
6. **Advanced Queries**: SQL queries for "properties with 3+ price changes" or "high listing churn"

## Implementation Notes

- All snapshot data sourced from existing database tables (no network calls)
- Migration function added to `database.py` to safely add new columns
- ObservationSnapshot model updated with new fields
- Monitoring module (monitoring.py) implements core snapshot logic
- Monitoring report module (monitoring_report.py) generates CSV exports
- CLI commands added to cli.py
- Comprehensive tests in test_monitoring.py

## Related Documents

- [PRD.md](../../PRD.md) - MVP 10: Monitoring section
- [Architecture.md](../../Architecture.md) - Snapshot and monitoring design
- [Decision 005: Cross-Site Enrichment Foundation](005-cross-site-enrichment-foundation.md) - Cross-site data integration
