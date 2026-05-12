# Decision 033: Alert Lifecycle Audit Trail

## Date

2026-05-12

## Status

Accepted

## Context

Milestones 28-33 introduced triage, archive, expiration, profile comparison, and preference workflows for cross-site trend alerts. As the number of alert management workflows grew, operators needed a way to inspect the full lifecycle of an alert across all workflows in a single view. Milestone 34 adds a unified read-only audit trail that consolidates alert lifecycle events.

## Decisions

### Why lifecycle audit follows triage/archive/expiration workflows

The lifecycle audit builds on the action recording infrastructure established in Milestones 28-31. All three workflows (triage, archive, expiration) record actions in the `cross_site_alert_triage_actions` table, differentiated by the `triage_export_id` prefix (triage_, archive_, expiration_). The lifecycle module normalizes these into a unified event stream without requiring schema changes.

### Why event normalization is read-only

The lifecycle module reads from existing tables and generates normalized events in memory. It does not write to any database table, create new tables, or modify existing records. All output is through console display, CSV export, and Markdown export. This ensures the audit trail cannot accidentally corrupt the data it reports on.

### Why gaps are review aids only

Lifecycle gaps (stale open alerts, unresolved reparse markers, etc.) are informational flags that help operators identify where expected follow-up actions have not occurred within configured thresholds. The module does not auto-fix gaps, auto-archive alerts, or auto-resolve markers. The operator decides which actions to take through the existing triage, archive, and expiration workflows.

### Why watchlist state is not automatically changed

The lifecycle audit observes alert lifecycle state. Alert lifecycle and watchlist management are separate concerns. Lifecycle summaries and gap detection do not modify active_watch_status, watch_priority, or any watchlist fields. This separation is consistent with all previous milestones.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper evaluates property stability based on listing history and churn patterns. The lifecycle audit evaluates alert workflow state. These are orthogonal dimensions. The lifecycle module does not reference or modify Quiet Score or Vibrancy Score.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields, parsing, or scoring have been added in any milestone, including this one.

### Why the module uses _row_to_dict conversion

The `execute_query` function returns `sqlite3.Row` objects which support bracket access (`row["key"]`) but not `.get()` with defaults. The lifecycle module converts rows to plain dicts using `_row_to_dict()` to enable safe `.get()` access with fallback values, preventing KeyError on missing columns.

### Why property address comes from watched_properties first

The lifecycle module looks up property address/city/zip from `watched_properties` first, falling back to `candidates` if not found. This is because alerts reference `property_id` from `watched_properties`, which is the primary property record after watchlist promotion.

## Consequences

- Operators can view the full lifecycle of any alert across all workflows.
- Property-level summaries show aggregate lifecycle metrics and labels.
- Gap detection identifies where follow-up actions are overdue.
- CSV and Markdown exports enable offline review and sharing.
- Dashboard shows lifecycle metrics, property table, and gap table.
- No database schema changes are required.
- No alerts are automatically modified by lifecycle operations.
- All existing triage, archive, and expiration workflows continue to work unchanged.
- The lifecycle module is a pure observer: it reads but never writes.
