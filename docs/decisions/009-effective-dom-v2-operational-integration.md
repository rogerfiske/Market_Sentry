# Decision 009: Effective DOM v2 Operational Integration

## Status

Accepted

## Date

2026-05-05

## Context

Milestone 9 introduced Effective DOM v2 calculation with county-confirmed ownership transfer reset boundaries and Churn Index v1 with date-bounded 3-year lookback. However, Milestone 9 implemented v2 as a report-only workflow: v2 metrics were calculated on-the-fly for comparison reports but not persisted into the operational database tables used by monitoring, scoring, and candidate review workflows.

Users had to run a separate v2 report command to see county-reset-adjusted exposure. The normal candidate analysis report, watchlist monitoring snapshots, and scoring recommendations did not reflect v2 or Churn Index values.

Milestone 10 operationalizes Effective DOM v2 by integrating v2 metrics and Churn Index into the recurring operational workflows.

## Decision

### 1. Persist v2 fields into operational tables

Add 14 v2/churn columns to all three operational tables:

- **property_observation_snapshots**: Captures v2 state at each monitoring snapshot for change detection over time.
- **watched_properties**: Stores current v2 metrics for watched properties, used by monitoring report and scoring.
- **candidate_review_queue**: Stores current v2 metrics for candidates, used by candidate analysis report and scoring.

All fields added via safe ALTER TABLE ADD COLUMN migrations with column_exists checks (idempotent, no data loss).

### 2. Create a persistence workflow

New module `effective_dom_v2_persistence.py` with a `persist-effective-dom-v2` CLI command that:

- Reads listing events and county records for each watched property and candidate.
- Computes Effective DOM v2 and Churn Index using existing Milestone 9 calculators.
- Updates the operational tables with computed v2 metrics.
- Preserves user_notes, user_decision, active_watch_status, and watch_priority.
- Never zeros churn metrics when county reset applies.

### 3. Preserve v1 alongside v2

Both `effective_dom_v1` and `effective_dom_v2` are persisted as separate columns. The original `effective_dom` and `effective_dom_delta` columns from v1 remain untouched. This enables v1 vs v2 comparison at any time.

### 4. Keep Churn Index separate from Effective DOM

Churn Index measures recent 2-3 year property/listing instability. It is computed from ALL listing events within the lookback window regardless of county reset. When `county_reset_applied` is true, `churn_preserved_after_transfer` is always true.

This design supports four analytical scenarios:
1. Low Effective DOM + Low Churn: Stable property, clean history
2. Low Effective DOM + High Churn: New ownership, but unstable listing history
3. High Effective DOM + Low Churn: Long exposure, stable behavior
4. High Effective DOM + High Churn: Long exposure AND unstable behavior

### 5. Treat churn as a review signal, not a rejection

Scoring uses v2-aware flags with neutral language:

- `churn_review_flag`: Set when `recent_churn_index >= 6` (positive flag: "high_recent_churn")
- `county_reset_with_churn_flag`: Set when county reset applied AND `recent_churn_index >= 5` ("county_reset_with_preserved_churn")
- `v2_leverage_flag`: Set when `effective_dom_delta_v2 >= 90` ("high_v2_dom_delta")

These flags are added to positive_flags (buyer review signals), not warning_flags. They do not override the Quiet Score gatekeeper, which remains the primary rejection mechanism.

### 6. Add v2 fields to CandidateProperty and WatchedProperty models

Both Pydantic models receive the 14 v2/churn fields with sensible defaults. This enables the scoring engine to access v2 fields directly via attribute access rather than relying solely on `getattr()` fallbacks.

## Consequences

### Positive

- Users see v2 and Churn Index in normal operating reports without running separate commands.
- Watchlist monitoring snapshots track v2 changes over time.
- Scoring recommendations incorporate v2 leverage signals.
- v1 remains fully available for comparison.
- Churn metrics are never lost or zeroed.
- All migrations are safe and idempotent.

### Negative

- Schema has 14 additional columns per table (42 columns total across 3 tables). Acceptable for SQLite operational scale.
- Users must run `persist-effective-dom-v2` to populate v2 fields before they appear in reports. This is intentional: v2 persistence is a deliberate step, not automatic.

### Neutral

- Existing Milestone 1-9 tests continue to pass without modification.
- No live network calls or scraping added.
- No change to the human-in-the-loop review workflow.

## Alternatives Considered

1. **JSON blob column**: Store v2 metrics as JSON in a single column. Rejected because it prevents SQL queries, sorting, and filtering on individual v2 fields.

2. **Separate v2 tables**: Create new tables for v2 metrics. Rejected because it adds join complexity and makes monitoring reports harder to generate.

3. **Auto-compute v2 on every report**: Calculate v2 on-the-fly during report generation. Rejected because it's computationally expensive for large watchlists and doesn't support change detection in snapshots.

4. **Replace v1 with v2**: Remove v1 columns entirely. Rejected because v1 provides a useful baseline and some properties may not have county records.
