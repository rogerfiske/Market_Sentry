# Decision 048: Release Candidate Hardening

## Date

2026-05-14

## Status

Accepted

## Context

After 48 milestones of feature development and the local operations bundle consolidation, the project needed a formal release candidate documentation, validation, and GitHub release preparation layer. This milestone creates the final pre-release audit that an operator can use to verify readiness before creating a GitHub release.

## Decisions

### Why release candidate docs follow local operations bundle

Milestone 48 completed the local operations bundle, which inventories all system components and runs safety audits. Milestone 49 builds on that foundation by adding operator acceptance checklists, workflow inventories, validation results, and release preparation documentation. This progression ensures all features are inventoried (M48) before validating release readiness (M49).

### Why this milestone audits rather than mutates

The release candidate module generates documentation, validation reports, and checklists. It does not modify candidate decisions, watchlist entries, alert statuses, or any other operational state. Automatic mutations during release preparation could introduce regressions or unintended side effects.

### Why no GitHub release or tag is created automatically

Creating a GitHub release is an irreversible action that should require explicit operator approval. The release candidate module prepares the checklist and documentation but leaves the actual release creation to the operator. This prevents accidental releases and ensures human review of all release artifacts.

### Why no outbound notification is sent

Outbound notifications are explicitly excluded from the entire project scope through Milestone 49. The release candidate module follows the same local-first design as all previous milestones. No SMTP, Gmail, Outlook, webhook, SMS, or other notification channels are used.

### Why live retrieval remains disabled by default

Live retrieval requires explicit opt-in via --force-live flags and compliance configuration. The release candidate module does not change this behavior. Default-safe operation ensures operators cannot accidentally trigger network requests during release preparation.

### Why candidate/watchlist/alert state is not automatically changed

The release candidate module is a reporting tool. It reads existing state for validation purposes but does not modify candidate decisions, watchlist entries, alert statuses, or any other operational state. Operators continue to use existing triage, archive, and review workflows for state changes.

### Why Quiet Score gatekeeper is unchanged

The release candidate module does not modify Quiet Score gatekeeper logic, thresholds, or scoring. The Quiet Score threshold remains at 70.0. The release candidate validation includes a check that verifies the gatekeeper has not been modified in unexpected locations.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. The release candidate validation includes a check that verifies walkability fields have not been introduced in source modules.

## Consequences

- Operators have a single command to view release candidate status
- Operator acceptance checklist validates documentation, commands, scripts, safety, and quality
- Safe workflow inventory classifies 17 workflows by access type
- Manual approval workflow inventory identifies 10 workflows requiring operator care
- Validation runs 7 automated checks including ops bundle, smoke test, and safety audit
- Markdown and CSV reports provide shareable release candidate documentation
- RELEASE_CANDIDATE_CHECKLIST.md and RELEASE_NOTES_DRAFT.md are auto-generated
- Dashboard shows release candidate metrics and drill-down tables
- No GitHub release or tag is created automatically
- No outbound notifications are sent
- No candidates, watchlist entries, or alert statuses are modified
- All existing workflows continue unchanged
