# Decision 024: Cross-Site Analytics Trend Snapshots

## Date

2026-05-08

## Status

Accepted

## Context

Milestone 24 introduced confidence-weighted cross-site comparison analytics. However, analytics were computed on-demand and not persisted. There was no way to track how analytics changed over time, detect trends, or identify whether cross-site data quality was improving or degrading for a given property.

## Decision

### Add point-in-time snapshot persistence

A new `cross_site_analytics_snapshots` table stores the full analytics result for each property at each capture time. Snapshots are append-only; historical records are never modified or deleted.

### Skip duplicate snapshots by default

If the most recent snapshot for a property shows no material change from the current analytics, a new snapshot is not created. The `--force` flag overrides this behavior.

### Material change thresholds

Material changes that trigger a new snapshot include:
- Discrepancy severity label changed
- Manual review priority changed
- Overall confidence score changed by >= 0.10
- Any agreement score (price, status, DOM) changed by >= 0.10
- Low-confidence or stale source count changed
- Any discrepancy flag (price, status, DOM) changed

### Trend direction classification

Each trend change is classified as `improving`, `degrading`, or `stable` based on the balance of improving vs degrading signals across confidence, severity, priority, and agreement scores.

### Recommended next actions

Trend changes include a recommended action:
- Degrading: "Review cross-site data" with specific reason
- Improving: "Continue monitoring"
- Stable: "No action needed"

### Cross-site trend data remains validation-only

Trend snapshots do not overwrite user_decision, user_notes, active_watch_status, watch_priority, or any Redfin-sourced property facts.

### Quiet Score gatekeeper is unchanged

Cross-site trend snapshots do not influence or override the Quiet Score gatekeeper.

### Walkability remains excluded

Walkability-type information is not part of the cross-site analytics trend scope.

## Consequences

### Positive

- Historical analytics are preserved for trend analysis
- Material change detection avoids unnecessary duplicate snapshots
- Trend direction and recommended actions help operators prioritize review
- New CLI commands for snapshot creation and trend report export
- Dashboard shows trend data alongside existing cross-site analytics
- CSV trend report enables offline analysis

### Negative

- Material change thresholds (0.10 delta) are initial heuristics that may need tuning
- Trend direction classification uses simple signal counting that may need refinement
- Snapshot storage grows over time (one row per property per material change)

## Related

- Milestone 24: Confidence-weighted cross-site analytics
- Milestone 23: Cross-site parser quality and fixture corpus expansion
- Milestone 6: Cross-site enrichment foundation
