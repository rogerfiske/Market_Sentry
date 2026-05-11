# Decision 032: Profile Comparison and Last-Used Profile Preference

## Date

2026-05-11

## Status

Accepted

## Context

Milestone 32 established user-defined alert expiration profiles loaded from a local JSON config file. As operators work with multiple profiles (built-in and custom), they need tools to compare profiles side by side and a way to set a default profile so they do not have to specify `--profile` on every command. Milestone 33 adds profile comparison views and local last-used profile persistence.

## Decisions

### Why profile comparison is read-only

Profile comparison runs the preview logic for each profile to gather candidate counts and action breakdowns. It does not apply any actions, change alert status, or modify the database. This is consistent with the preview-only pattern used throughout the expiration policy workflow.

### Why comparison includes profile source tagging

Each profile in the comparison result is tagged as "built_in" or "user_config". This helps operators distinguish between system-provided profiles and their own custom profiles in comparison tables and CSV exports.

### Why two-profile diff computes deltas

The two-profile diff returns signed deltas (candidate_count_delta, archive_count_delta, etc.) and counts of alerts unique to each profile or with different proposed actions. This gives operators a precise understanding of how two profiles differ in their effect on the current alert set, rather than requiring them to mentally subtract numbers from a side-by-side table.

### Why last-used profile is a local JSON file

The last-used profile preference is stored in `config/alert_expiration_profile_preference.json` rather than in the database. This approach:

- Keeps the preference human-readable and editable
- Does not require database schema changes
- Is consistent with the local-config approach used for custom profiles
- Can be easily cleared by deleting the file
- Does not introduce external dependencies

### Why invalid preferences fall back to standard

If the preference file is missing, contains invalid JSON, references a nonexistent profile, or has an empty profile name, the system falls back to "standard" with a warning rather than failing. This ensures that a corrupted or outdated preference file never prevents commands from running.

### Why explicit --profile overrides preference

When the operator passes `--profile` explicitly on the command line, it always takes precedence over the saved preference. This ensures deterministic behavior: the operator's explicit intent is never silently overridden by a saved setting.

### Why saving an invalid profile name is rejected

The save function validates that the profile name exists in the merged profile set (built-in + loaded custom profiles) before writing the preference file. This prevents operators from saving a typo or a profile name from a config file that is no longer present.

### Why approval gates remain required

Profile comparison and last-used profile preference are convenience features. They do not bypass the approval-gated workflow. All mutations still require the operator to export an approval CSV, edit decisions, and import the CSV. This is consistent with the human-in-the-loop principle.

### Why watchlist state is not changed

Profile comparison and preference operations do not modify active_watch_status, watch_priority, property facts, or any watchlist management fields. Alert lifecycle management and watchlist management remain separate concerns.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper evaluates property stability based on listing history and churn patterns. Profile comparison evaluates alert lifecycle state across profiles. These are orthogonal dimensions. Profile comparison does not interact with or modify the Quiet Score gatekeeper.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields, parsing, or scoring have been added in any milestone, including this one.

## Consequences

- Operators can compare all profiles side by side to choose the best fit for their review cadence.
- Two-profile diffs provide precise deltas for informed profile selection.
- Profile comparison CSV exports enable offline review and sharing.
- Last-used profile preference eliminates repetitive `--profile` flags.
- Invalid preferences fail safely to "standard" without breaking commands.
- Explicit `--profile` always overrides the saved preference.
- All expiration workflows remain approval-gated.
- Dashboard shows profile comparison table and current preference.
- No alerts are automatically modified by comparison or preference operations.
- The preference JSON file is human-editable and version-controllable.
