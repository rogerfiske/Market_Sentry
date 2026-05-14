# Decision 049: Release Finalization

## Date

2026-05-14

## Status

Accepted

## Context

After 49 milestones of feature development, local operations bundle consolidation, and release candidate hardening, the project needed a finalization layer that produces the definitive release package with version metadata, artifact inventory, readiness validation, manual GitHub release commands, and final release notes.

## Decisions

### Why release finalization follows release candidate hardening

Milestone 49 completed the release candidate documentation, validation checklist, and GitHub release prep. Milestone 50 takes the final step by producing the definitive version metadata, final release notes, and exact manual commands for creating a GitHub release. This progression ensures all features are inventoried (M48), validated (M49), and finalized (M50).

### Why manual GitHub commands are generated but not executed

Creating a GitHub release and tag is an irreversible action that should require explicit operator approval and manual execution. The finalization module generates exact commands with correct version strings and paths, but the operator must copy and run them intentionally. This prevents accidental releases.

### Why no GitHub release or tag is created automatically

Automatic release creation could result in incomplete or premature releases. The finalization module produces all necessary artifacts and documentation, then provides a clear manual workflow for the operator to follow at their discretion.

### Why no outbound notification is sent

Outbound notifications are explicitly excluded from the entire project scope through Milestone 50. The finalization module follows the same local-first design as all previous milestones. No SMTP, Gmail, Outlook, webhook, SMS, or other notification channels are used.

### Why no scheduled script is added

Release finalization is an intentional, operator-driven process. Adding it to a scheduled task would create confusion about when releases occur. The operator should run finalization commands manually when ready to prepare a release.

### Why candidate/watchlist/alert state is not automatically changed

The finalization module is a documentation/reporting tool. It reads existing state for validation purposes but does not modify candidate decisions, watchlist entries, alert statuses, or any other operational state.

### Why Quiet Score gatekeeper is unchanged

The finalization module does not modify Quiet Score gatekeeper logic, thresholds, or scoring. The readiness check verifies the gatekeeper threshold has not been modified.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. The readiness check verifies walkability fields have not been introduced in source modules.

## Consequences

- Operators have a single command to view release finalization status
- Version metadata is set to 0.1.0-rc1 in `__init__.py`
- Artifact inventory validates 14 release-relevant files and directories
- 13 readiness checks verify documentation, scripts, safety, and configuration
- 5 manual GitHub release commands are generated with correct version strings
- Final release notes include major capabilities, safety guarantees, and manual checklist
- RELEASE_NOTES_FINAL.md is auto-generated for GitHub release attachment
- RELEASE_FINALIZATION_GUIDE.md provides step-by-step workflow
- Dashboard shows finalization metrics, readiness checks, and manual command preview
- No GitHub release or tag is created automatically
- No outbound notifications are sent
- No candidates, watchlist entries, or alert statuses are modified
- All existing workflows continue unchanged
