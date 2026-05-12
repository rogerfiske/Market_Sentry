# Decision 036: Lifecycle Health Trend Snapshots and Scheduled Health Reports

## Date

2026-05-12

## Status

Accepted

## Context

Milestone 36 added per-property lifecycle health scoring, giving operators a 0-100 health score and label for each watched property. The health score is computed on demand and not persisted. Operators now need the ability to track how health scores change over time, detect improvement or degradation, and receive scheduled reports without manual CLI invocations.

## Decisions

### Why health trends follow lifecycle health scoring

Health trend snapshots build on Milestone 36 health scoring. The scoring module provides the per-property health score, label, and component breakdown. The trend module captures these as append-only snapshots and compares consecutive snapshots to detect change direction. This ordering ensures trend data is computed from well-tested health scores.

### Why snapshots are append-only

Append-only storage preserves the full history of health score observations. Each snapshot is an immutable record of the property's health state at a point in time. This enables historical trend analysis without risk of data loss from updates or deletions. The `cross_site_lifecycle_health_snapshots` table uses an auto-increment primary key and never deletes or updates existing rows.

### Why same-day/no-change snapshots are skipped

Creating a snapshot for every run would generate redundant data when nothing has changed. The module detects material changes (score delta >= 5, label change, open alert count change, high/critical alert count change, lifecycle gap count change, needs_reparse count change, needs_manual_review count change) and only creates a snapshot when at least one material change is detected. The `--force` flag overrides this behavior when operators want an unconditional snapshot.

### Why the scheduled script is local/report-only

The `run_lifecycle_health_report.bat` script runs three commands: health report export, health snapshot creation, and trend report export. It does not invoke live retrieval, alert mutation, or watchlist status changes. This keeps the scheduled automation safe for unattended execution. The script follows the same local-data-only principle as all other scheduled scripts in the project.

### Why watchlist state is not automatically changed

Health trend snapshots observe health metrics over time. They do not modify individual alert status, watchlist fields, or property data. The trend direction (improved, degraded, stable, new) is informational. Operators use the existing triage, archive, and expiration workflows to take actions based on trend observations.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper evaluates property stability based on listing history and churn patterns. Lifecycle health trends evaluate alert workflow efficiency over time. These are orthogonal dimensions. The health trend module does not reference or modify Quiet Score or Vibrancy Score.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields, parsing, or scoring have been added in any milestone, including this one.

## Consequences

- Operators can track per-property health score movement over time.
- Trend direction labels (improved, degraded, stable, new) provide at-a-glance status.
- Material change detection prevents redundant snapshot accumulation.
- CSV trend reports enable offline review and sharing.
- Dashboard displays trend counts, label changes, and lowest health scores.
- The scheduled script enables automated local reporting without manual CLI invocations.
- No alerts are automatically modified by health trend operations.
- All existing triage, archive, expiration, lifecycle audit, health scoring, and trend workflows continue unchanged.
- The only database write is the append-only snapshot record.
