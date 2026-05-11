# Decision 028: Cross-Site Alert Hygiene and Scheduled Reminders

## Date

2026-05-11

## Status

Accepted

## Context

Milestones 26-28 introduced cross-site trend alerts, alert aggregation with burden scoring, and a CSV-based triage workflow. As alert state accumulates over time, operators need periodic reminders about stale alerts, pending work items, and properties with high alert burden. Milestone 29 adds alert hygiene checks and scheduled report generation for this purpose.

## Decisions

### Why hygiene reports follow the triage workflow

Alert hygiene reports identify alerts that may need triage action. The recommended workflow is: run hygiene check, review the report, export a triage CSV for the relevant alerts, make triage decisions, and import the CSV. This follows the same human-in-the-loop pattern used throughout the project. Hygiene reports feed into the triage workflow rather than replacing it.

### Why alert hygiene is report-only

Hygiene reports identify issues and recommend actions but do not take actions automatically. This is consistent with the project principle that state-changing operations happen through explicit CLI commands and CSV import, not through background processes. The operator reviews the hygiene report and decides which actions to take.

### Why resolved alerts are not auto-archived

Automatically archiving resolved alerts would violate the human-in-the-loop principle. Some resolved alerts may need to be kept visible for reference. The hygiene report identifies resolved alerts older than 30 days as archive candidates and recommends exporting a triage CSV where the operator can set triage_decision to archive. The operator decides which alerts to archive.

### Why the scheduled task runs local report only

The scheduled batch script runs the hygiene check and exports CSV and Markdown reports. It does not invoke live retrieval, approved retrieval, or --force-live commands. This is consistent with the project requirement that scheduled tasks do not perform live scraping by default. The script is a reminder mechanism, not an automation of state changes.

### Why watchlist state is not automatically changed

Alert hygiene is separate from watchlist management. Automatically changing watchlist status based on alert hygiene findings would conflate two different workflows. Operators manage watchlist state through explicit commands. Hygiene reports inform the operator about alert state but do not modify property data.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper evaluates property stability based on listing history and churn patterns. Alert hygiene evaluates cross-site data quality signals. These are different dimensions of analysis. Mixing hygiene findings into the gatekeeper would conflate data quality management with property stability assessment.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields, parsing, or scoring have been added in any milestone. This decision remains unchanged.

## Consequences

- Operators receive regular reminders about stale alerts and pending work items.
- Hygiene reports provide actionable recommendations without modifying alert state.
- The scheduled script enables automated report generation without live retrieval.
- Alert triage and alert hygiene form a complementary workflow for managing cross-site data quality.
- Future milestones could add auto-archive policies or configurable alert expiration rules.
