# Decision 034: Alert Lifecycle Trend Snapshots

## Date

2026-05-12

## Status

Accepted

## Context

Milestone 34 added a unified read-only audit trail that consolidates alert lifecycle events across triage, archive, and expiration workflows. With the audit trail in place, operators need a way to measure alert-management efficiency over time: how quickly alerts are triaged, resolved, and archived, and whether the overall backlog is growing or shrinking. Milestone 35 adds append-only lifecycle metric snapshots to track these trends.

## Decisions

### Why lifecycle trends follow lifecycle audit

The lifecycle trend snapshots build on the lifecycle audit (Milestone 34) and the existing triage action recording infrastructure (Milestones 28-31). The audit trail provides the normalized event stream that trend metrics summarize. This ordering ensures trend metrics are computed from a well-understood, tested event model.

### Why snapshots are append-only

Lifecycle snapshots are write-once records. Each snapshot captures the state of the system at a point in time. Snapshots are never updated or deleted. This ensures trend comparisons remain consistent and auditable. The append-only pattern matches the cross-site analytics snapshots (Milestone 25) and provides a complete history for analysis.

### Why same-day no-change snapshots are skipped

Creating identical snapshots within the same day adds storage without analytical value. The module detects same-day duplicates and skips them unless a material change has occurred. Material changes include changes in alert count, open count, gap count, stale backlog count, throughput, or a significant (> 0.5 day) change in average time-to-resolution. The `--force` flag overrides this check when operators need to capture a snapshot regardless.

### Why metrics are operational only

Time-to-action and throughput metrics measure workflow efficiency, not property quality or investment potential. They help operators understand whether their alert management practices are effective. The metrics do not influence scoring, recommendations, or property evaluations.

### Why watchlist state is not automatically changed

Lifecycle trend snapshots observe aggregate lifecycle metrics. They do not modify individual alert status, watchlist fields, or property data. This separation is consistent with all previous milestones. Operators use the existing triage, archive, and expiration workflows to take actions on individual alerts.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper evaluates property stability based on listing history and churn patterns. Lifecycle trend metrics evaluate alert workflow efficiency. These are orthogonal dimensions. The trend metrics module does not reference or modify Quiet Score or Vibrancy Score.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields, parsing, or scoring have been added in any milestone, including this one.

## Consequences

- Operators can track alert-management efficiency trends over time.
- Time-to-action metrics reveal how quickly alerts move through the lifecycle.
- Throughput metrics show the rate of triage, resolution, and archive actions.
- Same-day duplicate prevention keeps snapshot history concise.
- Material change detection ensures meaningful snapshots are captured.
- Trend direction analysis (improving, worsening, stable) provides actionable insight.
- CSV trend reports enable offline review and sharing.
- Dashboard shows latest snapshot metrics, trend comparison, and throughput.
- Scheduled script automates snapshot and report generation.
- No alerts are automatically modified by trend snapshot operations.
- All existing triage, archive, expiration, and lifecycle audit workflows continue unchanged.
- The trend module writes only append-only snapshot records.
