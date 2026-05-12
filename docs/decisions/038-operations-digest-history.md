# Decision 038: Operations Digest Historical Snapshots

## Date

2026-05-12

## Status

Accepted

## Context

Milestone 38 added a consolidated operations digest that provides a single-command view of all operational metrics. However, the digest only shows the current state. Operators need to track how operational metrics change over time to identify trends, measure review progress, and detect emerging backlogs.

## Decisions

### Why digest history follows operations digest

The operations digest (Milestone 38) established the consolidated metric framework. Historical snapshots build on that framework by persisting point-in-time metric counts, enabling snapshot-over-snapshot comparison without adding new metric categories or changing how metrics are calculated.

### Why snapshots are append-only

Each snapshot row captures the aggregate metric state at a single point in time. Rows are never updated or deleted. This preserves the historical record and ensures audit integrity. The `operations_digest_snapshots` table uses `CREATE TABLE IF NOT EXISTS` and `INSERT` only.

### Why same-day/no-change snapshots are skipped

Repeated snapshots with identical metrics waste storage without adding analytical value. Material change detection compares the current metrics against the most recent snapshot. Snapshots are created only when a meaningful metric changes (candidate backlog, active watched count, high/critical alerts, lifecycle attention, digest score change >= 5, or status label change). The `--force` flag overrides this behavior.

### Why digest score is operational only and not purchase advice

The digest score (0-100) measures the local review backlog: higher scores indicate fewer items requiring operator attention. It reflects operational workload, not property desirability, market conditions, or investment quality. Score labels (clear, light_review, active_review, heavy_review, backlog_attention) use neutral operational language.

### Why the scheduled script is local and report-only

The `run_operations_digest_report.bat` script runs three read-only commands: digest export, digest snapshot, and comparison report. It does not invoke live retrieval, alert mutation, or watchlist status changes. All output goes to `logs/scheduled/`.

### Why watchlist/candidate/alert state is not automatically changed

Digest history observes and reports. It does not modify candidate decisions, alert statuses, watchlist fields, or property data. Operators use existing triage, archive, and expiration workflows to take actions based on digest observations and trend analysis.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper evaluates property stability based on listing history and churn patterns. Digest history does not reference or modify Quiet Score or Vibrancy Score. The gatekeeper logic remains in its original module without modification.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields, parsing, or scoring have been added in any milestone, including this one.

## Consequences

- Operators can track operations metric trends over time.
- Digest score provides a single-number summary of local review workload.
- Comparison reports highlight what changed between snapshots.
- Same-day skip logic prevents redundant snapshot accumulation.
- Append-only storage preserves the full historical record.
- The scheduled script automates snapshot creation and comparison reporting.
- Dashboard integration provides interactive trend exploration.
- No alerts, candidates, or watchlist entries are modified by digest history operations.
- All existing digest, triage, archive, expiration, lifecycle, and health workflows continue unchanged.
