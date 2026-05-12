# Decision 035: Property-Level Lifecycle Health Scoring

## Date

2026-05-12

## Status

Accepted

## Context

Milestones 34-35 added a unified alert lifecycle audit trail and append-only lifecycle metric snapshots. These milestones provide per-alert event tracking, gap detection, and aggregate throughput metrics. Operators now need a per-property summary that translates lifecycle metrics into a single read-only health score, enabling quick identification of properties requiring operational attention.

## Decisions

### Why health scoring follows lifecycle trends

Health scoring builds on the lifecycle audit (Milestone 34) and lifecycle trend snapshots (Milestone 35). The audit provides per-alert gap detection, and the trend snapshots provide aggregate metrics. Health scoring translates these into a per-property 0-100 score. This ordering ensures health scores are computed from well-tested lifecycle data.

### Why score is read-only

The health score is a computed metric, not stored in the database. It is recalculated on demand from current alert and lifecycle data. No database table is needed for health scores because they derive entirely from existing lifecycle data. This avoids stale score issues and keeps the module purely analytical.

### Why score is operator-health and not property desirability

The health score measures alert-management efficiency for a property, not the property's investment quality or market position. A low score means the operator has unresolved alerts, lifecycle gaps, or stale backlogs for that property. A high score means the operator is on top of their alert management. This distinction prevents misuse of the score for purchase decisions.

### Why watchlist state is not automatically changed

Health scores observe lifecycle metrics. They do not modify individual alert status, watchlist fields, or property data. Operators use the existing triage, archive, and expiration workflows to take actions. This separation is consistent with all previous milestones.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper evaluates property stability based on listing history and churn patterns. Lifecycle health scoring evaluates alert workflow efficiency. These are orthogonal dimensions. The health module does not reference or modify Quiet Score or Vibrancy Score.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields, parsing, or scoring have been added in any milestone, including this one.

## Consequences

- Operators can quickly identify properties with poor lifecycle health.
- Health labels (excellent, good, watch, needs_review, attention_required) provide at-a-glance prioritization.
- Component breakdown shows exactly which factors contribute to each score.
- CSV and Markdown reports enable offline review and sharing.
- Dashboard displays health label counts, lowest-scoring properties, and component details.
- CLI commands provide terminal-based health assessment.
- No alerts are automatically modified by health scoring operations.
- All existing triage, archive, expiration, lifecycle audit, and trend workflows continue unchanged.
- The health module performs no database writes.
