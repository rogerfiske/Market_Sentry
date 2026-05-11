# Decision 030: Cross-Site Alert Expiration Policy

## Date

2026-05-11

## Status

Accepted

## Context

Milestones 26-30 built a comprehensive alert lifecycle: trend alerts (M26), alert aggregation and burden scoring (M27), CSV-based triage (M28), hygiene reports (M29), and opt-in archive policy for resolved alerts (M30). As the alert system matures, operators need configurable rules to systematically identify alerts eligible for review or archive based on age thresholds, rather than manually checking each alert. Milestone 31 adds configurable local expiration rule profiles with operator approval gates.

## Decisions

### Why expiration policy follows archive policy

Archive policy (M30) handles a single use case: resolved alerts older than a threshold are candidates for archive. Expiration policy generalizes this pattern to cover multiple alert statuses (resolved, acknowledged, open) with different age thresholds and proposed actions. It provides a unified framework for age-based alert lifecycle management while preserving the archive policy as a simpler, focused tool.

### Why profiles are local heuristics

Expiration profiles define local age-based rules. They are not machine learning models, external service calls, or dynamic scoring systems. They are simple threshold-based heuristics that operators can understand and predict. Three built-in profiles (conservative, standard, aggressive_review_only) provide reasonable defaults without requiring configuration files or database storage.

### Why approval gates are required

Expiration rules generate preview and approval rows only. They never apply actions automatically. This preserves the human-in-the-loop principle established throughout the project. The operator must:

1. Preview or export candidates
2. Review the approval CSV
3. Edit approval_decision for each row
4. Import the edited CSV

This prevents accidental data loss from misconfigured rules or edge cases.

### Why high/critical alerts are review-only

High and critical open alerts represent significant cross-site discrepancies that need active attention. Automatically proposing them for archive would risk hiding important data quality issues. All profiles restrict high/critical open alerts to review-only, ensuring they are never proposed for archive regardless of age.

### Why no auto-apply is implemented

No scheduled task, background process, or automated workflow applies expiration decisions. The import command is the only way to apply decisions, and it requires an explicit file path. This is consistent with the project principle that state-changing operations happen through explicit CLI commands, not background automation.

### Why watchlist state is not automatically changed

Expiration policy operates on alert state only. It does not modify active_watch_status, watch_priority, property facts, or any watchlist management fields. Alert lifecycle management and watchlist management are separate concerns.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper evaluates property stability based on listing history and churn patterns. Expiration policy evaluates alert lifecycle state (how long an alert has been in a given status). These are different dimensions of analysis. The gatekeeper remains unchanged by expiration operations.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields, parsing, or scoring have been added in any milestone.

## Consequences

- Operators have configurable age-based rules for systematic alert lifecycle management.
- Three built-in profiles provide reasonable defaults for different operational styles.
- Approval gates prevent accidental mutations from misconfigured rules.
- High/critical open alerts are always review-only across all profiles.
- Expiration policy complements archive policy (M30) and triage (M28) without replacing them.
- No alerts are automatically modified by any scheduled task or background process.
- Hygiene reports (M29) now recommend both archive and expiration workflows for resolved candidates.
