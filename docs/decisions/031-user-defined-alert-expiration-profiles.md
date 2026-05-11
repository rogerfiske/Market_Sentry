# Decision 031: User-Defined Alert Expiration Profiles

## Date

2026-05-11

## Status

Accepted

## Context

Milestone 31 established configurable alert expiration rules with three built-in profiles (conservative, standard, aggressive_review_only) and operator approval gates. As operators gain experience with the system, they may need custom age thresholds and rule combinations that do not match any built-in profile. Milestone 32 adds support for user-defined local expiration profiles loaded from a JSON config file.

## Decisions

### Why custom profiles are local config

User-defined profiles are stored in a local JSON file (`config/alert_expiration_profiles.json`) rather than in the database or a remote service. This approach:

- Keeps profiles human-editable and version-controllable
- Does not require database schema changes
- Allows operators to review and diff profile changes
- Is consistent with the fixture-first, local-config approach used throughout the project
- Does not introduce external dependencies or network calls

### Why invalid configs are rejected

Invalid profile configs (bad JSON, missing required fields, invalid values) are rejected with clear, actionable error messages rather than silently ignored or partially loaded. This prevents operators from running expiration workflows with misconfigured rules that could produce unexpected candidates. Built-in profiles remain available even when the user config is invalid.

### Why built-in profiles remain available

Built-in profiles (conservative, standard, aggressive_review_only) are always loaded regardless of user config state. This ensures:

- Operators always have known-good profiles to fall back on
- Invalid user configs do not break the system
- CLI listing and dashboard always show at least the built-in profiles

### Why user profiles cannot silently override built-ins

If a user profile has the same name as a built-in profile (e.g., "standard"), it is rejected during merge with a clear error message rather than silently replacing the built-in. This prevents accidental override of well-tested default behavior and ensures that references to built-in profile names always resolve to the expected rules.

### Why approval gates remain required

Custom profiles follow the same approval-gated workflow as built-in profiles. Preview and export generate candidates only. Mutations require the operator to:

1. Export the approval CSV
2. Review and edit approval_decision for each row
3. Import the edited CSV

This is consistent with the human-in-the-loop principle and prevents custom profiles from bypassing safety controls.

### Why watchlist state is not automatically changed

Expiration policy (both built-in and custom profiles) operates on alert state only. It does not modify active_watch_status, watch_priority, property facts, or any watchlist management fields. Alert lifecycle management and watchlist management remain separate concerns.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper evaluates property stability based on listing history and churn patterns. Expiration profiles evaluate alert lifecycle state (how long an alert has been in a given status). These are orthogonal dimensions. Custom profiles do not interact with or modify the Quiet Score gatekeeper.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields, parsing, or scoring have been added in any milestone, including this one.

## Consequences

- Operators can define custom age-based rules tailored to their review cadence.
- Custom profiles are validated before use, preventing misconfigured rules.
- Built-in profiles always remain available as safe defaults.
- User profiles cannot silently override built-in profiles.
- All expiration workflows (preview, export, import) support custom profiles via `--profile-config`.
- Dashboard shows detected custom profiles with validation status.
- No alerts are automatically modified by custom profiles or any scheduled task.
- The JSON config format is human-editable and version-controllable.
