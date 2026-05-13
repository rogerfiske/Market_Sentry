# Decision 045: Portfolio Alert Focus Preferences

## Date

2026-05-13

## Status

Accepted

## Context

Milestone 45 established append-only alert history with persistence tracking and cross-run comparison. Operators needed a way to configure which alert categories should be emphasized in reports and dashboard views without changing the underlying alert evaluation or history systems.

## Decisions

### Why focus preferences follow alert history

Milestone 45 provides the persistence layer with append-only alert history and cross-run comparison. Milestone 46 adds a display/filtering layer on top of that history. Focus preferences read existing persisted data and apply local display filters. This layered approach preserves the existing evaluation and history behavior while adding configurable emphasis for operator review.

### Why preferences are display-only

Focus preferences affect which alerts are shown prominently in reports and dashboard views. They do not change which alerts are generated, how alerts are evaluated, or what gets persisted to history. This separation ensures that changing display preferences never introduces side effects in the underlying analytical pipeline.

### Why no outbound notification is sent

Outbound notifications (email, SMS, webhook) are explicitly excluded. The focus preference system is designed for local, offline operational review. Future milestones may add optional notification channels, but the current design prioritizes local-first operation without external dependencies.

### Why scheduled script is local/report-only

The `run_portfolio_review_pack_report.bat` script now includes `export-portfolio-alert-focus-digest`. This command reads existing data and exports reports but does not perform live retrieval, mutation, or outbound notifications. The script remains safe for unattended scheduled execution.

### Why candidate/watchlist/alert state is not automatically changed

Focus preferences highlight alerts for human review. Operators use existing triage, archive, and expiration workflows to take actions. Automatic state changes from a display preference system would bypass the human-in-the-loop design.

### Why Quiet Score gatekeeper is unchanged

The focus preference system does not modify Quiet Score gatekeeper logic, thresholds, or scoring. The quiet gatekeeper threshold remains at 70.0.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. The focus preference module does not reference walkability metrics. Config keys containing walkability terms are rejected during validation.

## Consequences

- Operators can configure which alert categories are emphasized in dashboard and reports.
- Severity filtering, alert type filtering, persistence thresholds, and scope filtering are available.
- Four sort orders provide flexible display ordering.
- Focus digest reports (CSV and Markdown) can be exported on demand or via scheduled script.
- Dashboard shows a dedicated Portfolio Alert Focus View subsection.
- No outbound notifications are sent.
- No candidates, watchlist entries, or alert statuses are modified.
- All existing alert, trend, review pack, comparison, digest, triage, archive, expiration, lifecycle, health, configurable rule, and alert history workflows continue unchanged.
