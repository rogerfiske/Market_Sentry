# Decision 027: Cross-Site Alert Triage Workflow

## Date

2026-05-11

## Status

Accepted

## Context

Milestones 26-27 introduced individual cross-site trend alerts with lifecycle management and property-level alert burden metrics. As alerts accumulate over time, operators need a way to batch-review and manage them without clicking through individual alert commands. Milestone 28 adds a CSV-based triage workflow for this purpose.

## Decisions

### Why triage is CSV-based

CSV-based triage follows the same human-in-the-loop pattern used for candidate review (Milestone 2). Operators export alerts, review them in their preferred spreadsheet editor, make decisions offline, and import the results. This approach requires no additional UI, works on any system, integrates naturally with existing data pipelines, and provides a clear audit trail through the exported and imported CSV files.

### Why dashboard remains read-only

The dashboard shows triage state (open/acknowledged/resolved counts, latest export, triage history) but does not allow triage actions from the dashboard UI. This is consistent with the project's principle that state-changing operations happen through CLI commands, not through the dashboard. The dashboard is an observation tool, not a workflow tool.

### Why only acknowledge/resolve/archive change alert status

These three decisions correspond to the alert lifecycle defined in Milestone 26 (open -> acknowledged -> resolved -> archived). They represent meaningful state transitions in the alert lifecycle. The other decisions (keep_open, needs_reparse, needs_manual_review) represent operator annotations that should not alter the alert's lifecycle state but should be recorded for tracking purposes.

### Why watchlist state is not automatically changed

Triage actions manage alert status, which is a separate concept from watchlist state. Automatically changing watchlist status (active_watch_status, watch_priority, user_notes) based on triage decisions would violate the human-in-the-loop principle. Operators make watchlist decisions independently of alert triage. The two workflows inform each other but operate independently.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper evaluates property stability based on listing history and churn patterns. Alert triage manages cross-site data quality signals. These are different dimensions of analysis. Mixing triage decisions into the gatekeeper would conflate data quality management with property stability assessment.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields, parsing, or scoring have been added in any milestone. This decision remains unchanged.

## Consequences

- Operators can batch-manage accumulated alerts using familiar CSV tools.
- The triage workflow provides an audit trail through the history table.
- Watchlist state and Quiet Score remain fully under human control.
- needs_reparse and needs_manual_review flags enable tracking of pending work without affecting alert lifecycle.
- Future milestones could add scheduled triage reminders or auto-archive policies for old resolved alerts.
