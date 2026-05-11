# Decision 029: Cross-Site Alert Archive Policy

## Date

2026-05-11

## Status

Accepted

## Context

Milestones 26-29 introduced cross-site trend alerts, alert aggregation with burden scoring, a CSV-based triage workflow, and alert hygiene reports. As resolved alerts accumulate over time, operators need a dedicated workflow for reviewing and archiving old resolved alerts. The hygiene reports (Milestone 29) identify resolved archive candidates but do not provide a mechanism to act on them directly. Milestone 30 adds an opt-in archive policy workflow for this purpose.

## Decisions

### Why archive policy follows hygiene reports

Hygiene reports identify resolved alerts older than 30 days as archive candidates and recommend exporting them for review. The archive policy workflow provides the mechanism to act on that recommendation. This follows the same pattern as hygiene -> triage: one system identifies issues, another provides the workflow to address them.

### Why archiving is opt-in

Automatically archiving resolved alerts would violate the human-in-the-loop principle established throughout the project. Some resolved alerts may need to remain visible for reference, especially if they document recurring cross-site discrepancy patterns. The operator reviews each candidate and makes an explicit decision.

### Why no auto-archive is implemented

No scheduled task or background process archives alerts automatically. Archive decisions happen through an explicit export-review-import CSV workflow. This is consistent with the project principle that state-changing operations happen through explicit CLI commands and CSV import, not through background processes.

### Why no_archive marker exists

The `[no_archive]` marker provides a permanent exemption mechanism. When an operator determines that a resolved alert should never be archived (e.g., it documents an important historical pattern), they can mark it with `no_archive`. This adds `[no_archive]` to the alert notes and excludes it from future archive candidate identification. The marker is persistent and survives across multiple archive review cycles.

### Why watchlist state is not automatically changed

Archive policy operates on alert state only. It does not modify `active_watch_status`, `watch_priority`, property facts, or any watchlist management fields. Alert lifecycle management and watchlist management are separate concerns. Operators manage watchlist state through explicit commands.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper evaluates property stability based on listing history and churn patterns. Archive policy evaluates alert lifecycle state (how long an alert has been resolved). These are different dimensions of analysis. The gatekeeper remains unchanged by archive operations.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields, parsing, or scoring have been added in any milestone. This decision remains unchanged.

## Consequences

- Operators have a dedicated workflow for reviewing and archiving old resolved alerts.
- The `[no_archive]` marker provides a permanent exemption for alerts that should remain visible.
- Archive policy integrates with hygiene reports (Milestone 29) as the recommended action for resolved archive candidates.
- Archive decisions are recorded in the triage actions table for audit purposes.
- The archive workflow complements the triage workflow (Milestone 28) without replacing it.
- No alerts are automatically archived by any scheduled task or background process.
