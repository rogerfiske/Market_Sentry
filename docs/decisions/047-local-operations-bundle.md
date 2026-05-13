# Decision 047: Local Operations Bundle

## Date

2026-05-13

## Status

Accepted

## Context

After 47 milestones of feature development, the project accumulated 45+ CLI commands, 20 report types, 8 scheduled scripts, and multiple configuration files. Operators needed a single entry point to audit system inventory, verify safety, and confirm readiness for local operation.

## Decisions

### Why local operations bundle follows the email draft feature

Milestone 47 completed the local email digest draft, the last feature-level addition before hardening. Milestone 48 shifts focus from adding new analytical features to consolidating and auditing existing capabilities. This natural progression ensures all features are inventoried and verified before declaring release-candidate readiness.

### Why release-candidate hardening is local/report-only

The operations bundle generates inventory reports and runs static audits. It does not add new analytical features, modify existing behavior, or introduce new data pipelines. This read-only approach ensures the hardening process itself cannot introduce regressions or side effects.

### Why it audits rather than mutates

The safety audit checks for forbidden patterns (browser automation, outbound notifications, walkability fields, Quiet Score modifications) but does not automatically fix issues. Automatic fixes could introduce unintended changes. Instead, the audit reports findings and recommends actions for human review.

### Why no outbound notification is sent

Outbound notifications are explicitly excluded from the entire project scope through Milestone 48. The operations bundle follows the same local-first design as all previous milestones. No SMTP, Gmail, Outlook, webhook, SMS, or other notification channels are used.

### Why scheduled script is local/report-only

The `run_local_operations_bundle_report.bat` script runs `export-local-operations-bundle` which generates local files only. It does not perform live retrieval, run mutation commands, or send outbound notifications. The script is safe for unattended scheduled execution.

### Why candidate/watchlist/alert state is not automatically changed

The operations bundle is a reporting tool. It reads existing state for inventory purposes but does not modify candidate decisions, watchlist entries, alert statuses, or any other operational state. Operators continue to use existing triage, archive, and review workflows for state changes.

### Why Quiet Score gatekeeper is unchanged

The operations bundle does not modify Quiet Score gatekeeper logic, thresholds, or scoring. It includes a safety audit check that verifies the gatekeeper threshold has not been modified in unexpected locations.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. The operations bundle includes a safety audit check that verifies walkability fields have not been introduced in source modules.

## Consequences

- Operators have a single command to audit all system components
- Command inventory provides visibility into 45+ CLI commands with safety flags
- Report inventory shows freshness status across 20 report groups
- Script safety inventory detects live retrieval, mutation, and notification patterns
- Config inventory tracks template and local configuration files
- Safety audit runs 7 static checks against the source codebase
- Schema inventory provides database table and column counts
- Smoke test verifies basic system readiness
- Markdown and CSV exports provide shareable audit documentation
- Dashboard shows operations bundle metrics and drill-down tables
- No outbound notifications are sent
- No candidates, watchlist entries, or alert statuses are modified
- All existing workflows continue unchanged
