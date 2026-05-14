# Decision 050: Guided Operator Workflow

## Date

2026-05-14

## Status

Accepted

## Context

After 50 milestones of feature development, release candidate hardening, and release finalization, the operator workflow required too many manual steps: copying commands, editing CSV files, and running multiple CLI commands in the correct order. Milestone 51 reduces this burden by providing guided operator workflow commands, candidate action helpers, and dashboard action forms.

## Decisions

### Why operator workflow comes after release candidate finalization

Milestone 50 completed the release finalization package with version metadata, artifact inventory, readiness validation, and manual GitHub release commands. With the release candidate fully documented and validated, Milestone 51 focuses on operator usability without risk to the release process. The operator workflow is a quality-of-life improvement that builds on the stable foundation established through Milestones 48-50.

### Why this milestone reduces command-line and CSV burden

The user validated the end-to-end workflow manually (import URLs, parse HTML, enter scores, edit CSV decisions, import decisions, promote candidates, run reports, view dashboard) but found too many steps required copying/pasting commands and editing CSV files. Direct CLI commands for candidate decisions, location scores, and noise notes eliminate the need to edit and re-import CSV files for common actions.

### Why dashboard buttons are allowed to mutate only explicit operator-selected candidate fields

Dashboard action forms (update decision, update scores, add noise notes) mutate candidate data only when the operator explicitly clicks "Apply" with specific values. This is acceptable because the operator is intentionally selecting which candidate to modify and what values to set. The dashboard does not make autonomous changes, does not batch-update multiple candidates, and does not modify fields the operator did not explicitly select.

### Why live retrieval remains out of scope

The operator workflow is a local management tool. Adding live retrieval would change the safety profile of the module and introduce network dependencies. Live retrieval remains a separate concern handled by existing import and enrichment commands when the operator chooses to run them.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper threshold (7.0) and scoring logic remain exactly as implemented in previous milestones. The operator workflow uses the existing `apply_quiet_gatekeeper` function to compute gatekeeper results when scores are entered. No threshold modifications, scoring changes, or gatekeeper bypass logic is added.

### Why walkability remains excluded

Walkability-type information is explicitly excluded from the project scope per PM direction. The operator workflow does not add walkability fields, parse walkability data, or reference walkability scores. Noise notes record local field knowledge about specific noise sources (traffic, airport, etc.) without walkability scoring.

### Why noise notes are treated as local buyer field knowledge, not seller-intent inference

Noise notes record the operator's direct knowledge or observations about noise conditions at a property location. They use neutral language (e.g., "possible traffic noise exposure") and do not infer why a seller listed the property, whether the seller is aware of noise issues, or whether noise affects the property's value. This follows the project's rule of using neutral language and not inferring seller intent.

## Consequences

- Operators can check workflow status with a single command
- Candidate decisions can be applied directly without CSV editing
- Quiet/Vibrancy scores can be entered directly without CSV editing
- Noise observations can be recorded with structured risk levels and sources
- All local reports can be refreshed with a single command
- Dashboard provides point-and-click forms for all candidate actions
- No live retrieval or scraping is added
- No outbound notifications are sent
- No walkability fields are introduced
- Quiet Score gatekeeper remains unchanged at threshold 7.0
- All candidate mutations require explicit operator action
- Review actions are logged for audit tracking
- Existing workflows continue unchanged
