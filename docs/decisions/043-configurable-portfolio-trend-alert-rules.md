# Decision 043: Configurable Portfolio Trend Alert Rules

## Date

2026-05-13

## Status

Accepted

## Context

Milestone 43 established default portfolio trend threshold alert rules with hardcoded thresholds. Operators needed a way to tune alert thresholds, add custom rules, and disable irrelevant rules without modifying source code.

## Decisions

### Why configurable rules follow default trend alerts

Milestone 43 provides the built-in rule set and evaluation engine. Milestone 44 adds a configuration layer on top: JSON config files that define custom rules which are loaded, validated, and merged with or replace built-in rules. This layered approach preserves the default behavior while enabling operator customization.

### Why config is local JSON

A local JSON file is consistent with the existing config pattern (alert_expiration_profiles.json). JSON is human-readable, editable with any text editor, and does not require additional dependencies. The config file is optional; if absent, built-in rules are used unchanged.

### Why invalid configs fail safely

Invalid config files return clear validation errors but do not break default commands. Built-in rules continue to work regardless of config file state. Only when a user explicitly supplies an invalid config via `--rule-config` are validation errors surfaced. This prevents accidental disruption of the default alert pipeline.

### Why built-in rule override is disallowed by default

User configs must not silently override built-in rule IDs. If a custom rule uses the same rule_id as a built-in rule, the config is rejected with a clear error. This prevents confusion about which rule is active and ensures built-in rules maintain predictable behavior unless the user chooses `replace` mode to use only custom rules.

### Why no outbound notification is sent

Outbound notifications (email, SMS, webhook) are explicitly excluded from this milestone. The configurable rule system is designed for local, offline review. Future milestones may add optional notification channels, but the current design prioritizes local-first operation without external dependencies.

### Why scheduled script remains local and report-only

The `run_portfolio_review_pack_report.bat` script does not require a custom rule config. It continues to use built-in rules by default. Users may manually edit the script to add `--rule-config` if desired, but the default remains safe and self-contained.

### Why candidate/watchlist/alert state is not automatically changed

Configurable rules observe and report threshold violations. Operators use existing triage, archive, and expiration workflows to take actions. Automatic state changes from a configurable alerting tool would bypass the human-in-the-loop design.

### Why Quiet Score gatekeeper is unchanged

The configurable rule system does not modify Quiet Score gatekeeper logic, thresholds, or scoring. The quiet gatekeeper threshold remains at 70.0.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. Custom rules that reference walkability metrics are rejected during validation.

## Consequences

- Operators can customize alert thresholds without code changes.
- Merge mode adds custom rules after built-in defaults.
- Replace mode uses only custom rules.
- Disabled rules are valid in config but not evaluated.
- Validation catches invalid configs before evaluation.
- Template writer provides a starting point for custom configs.
- Dashboard shows rule configuration status (built-in count, custom config detected, validation status, active rules).
- No outbound notifications are sent.
- No alerts, candidates, or watchlist entries are modified by configurable rule operations.
- All existing alert, trend, review pack, comparison, digest, triage, archive, expiration, lifecycle, and health workflows continue unchanged.
