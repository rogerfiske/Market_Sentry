# Claude Code Prompt 051 - Guided Operator Workflow and Dashboard Candidate Action Buttons

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: cb0b135 (Milestone 50 complete, v0.1.0-rc1 released)

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read README.md.
4. Read docs/RUNBOOK.md.
5. Read docs/RELEASE_NOTES_FINAL.md.
6. Read docs/RELEASE_FINALIZATION_GUIDE.md.
7. Read docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md.
8. Read docs/LOCAL_OPERATIONS_BUNDLE.md.
9. Review the current codebase through commit cb0b135.
10. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
11. Keep PRD.md and Architecture.md in the project root.
12. Use src/marketsentry/ as the Python package path.
13. Do not move PRD.md or Architecture.md into docs/.
14. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
15. Do not implement live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval in this milestone.
16. Do not implement new Redfin live retrieval behavior in this milestone.
17. Do not run any live network calls in tests.
18. Do not make scheduled tasks run live retrieval by default.
19. Do not add walkability parsing or walkability fields.
20. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

## PM direction

Milestone 51 should make Market_Sentry easier for a non-programmer operator to use.

The user successfully validated the end-to-end workflow manually:

- import Redfin URLs from CSV
- parse/enrich saved Redfin detail HTML
- manually enter Quiet/Vibrancy values
- edit review CSV decisions
- import review decisions
- promote a candidate to watchlist
- run snapshots/reports
- view dashboard

However, too many steps required copying/pasting commands and editing CSV files manually.

Milestone 51 should create a guided local operator workflow that reduces command-line burden, centralizes status, and provides dashboard action buttons/forms for common candidate actions.

This milestone must remain local-only and safe. It must not implement live scraping or browser automation.

## Critical project rules

1. Effective DOM v1 is listing-history-derived exposure without county reset integration.
2. Effective DOM v2 applies county-confirmed ownership transfer as a reset boundary when appropriate.
3. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
4. Churn Index remains reportable even when Effective DOM is reset.
5. Quiet Score is the gatekeeper and must remain unchanged.
6. Target is very high Quiet and very low Vibrancy.
7. Any mention of gas means natural gas supply/service evidence.
8. Walkability-type information is excluded.
9. Use neutral language. Do not infer seller intent.
10. Reports are analytical aids, not purchase recommendations.
11. Operator workflows are local-only.
12. No outbound notifications should be sent in this milestone.
13. No live retrieval or scraping should be added.

## Recent validated operating facts

The user tested with real candidates:

- Candidate 4: 32420 San Marco Dr, Temecula, CA 92592
  - Price: 885000
  - Quiet: 9.9
  - Vibrancy: 1.3
  - Decision: save
  - Promoted to watched property 2

- Candidate 5: 32152 Camino Nunez, Temecula, CA 92592
  - Price: 799000
  - Quiet: 6.9
  - Vibrancy: 1.1
  - Decision: maybe
  - Treated as a noise-risk control case due to local road/airport-noise concerns

Manual notes for Candidate 5 should be supported:
"Track as noise-risk control. Local knowledge suggests possible traffic/airport noise exposure despite Redfin Quiet 6.9; monitor DOM, price reductions, and final sale price."

The user also wants HowLoud (https://howloud.com) remembered for later, but do not implement HowLoud integration in Milestone 51.

## Implement

### 1. Guided operator workflow module

Create:

```text
src/marketsentry/operator_workflow.py
```

Required models:

- OperatorWorkflowStep
- OperatorWorkflowWarning
- OperatorWorkflowAction
- OperatorCandidateActionResult
- OperatorWorkflowStatus
- OperatorWorkflowRunResult

Required functions:

- build_operator_workflow_status(...)
- run_operator_refresh_workflow(...)
- apply_candidate_decision(...)
- apply_candidate_location_scores(...)
- apply_candidate_noise_notes(...)
- build_missing_data_actions(...)
- export_operator_action_summary(...)

The workflow status should summarize:

- total candidates
- pending candidates
- maybe candidates
- saved candidates
- rejected candidates
- hold_for_more_data candidates
- active watched properties
- candidates missing Quiet/Vibrancy
- candidates missing price
- candidates missing Redfin detail enrichment
- candidates needing review after enrichment
- latest key report files
- recommended next local action

### 2. One-command operator refresh workflow

Add a safe command that runs the routine local steps in the correct order:

```text
marketsentry run-operator-refresh-workflow
```

It should run local-only operations such as:

1. recalc candidates
2. persist Effective DOM v2 if available
3. snapshot watchlist
4. export watchlist monitoring report
5. export candidate analysis report
6. export portfolio review pack
7. export operations digest
8. export local operations bundle
9. return an operator-facing summary

The command must:

- not run live retrieval
- not import review decisions automatically
- not mutate candidate decisions
- not mutate alert state
- not send notifications
- not use --force-live
- tolerate empty/missing optional tables
- report warnings instead of crashing when a non-critical report cannot be generated

Note: snapshot-watchlist inserts append-only snapshots and is acceptable because it is already a safe operational snapshot workflow. This is not a candidate/watchlist/alert status mutation.

### 3. Candidate action helpers

Add safe helper functions and CLI commands to reduce CSV editing.

CLI commands:

```text
marketsentry candidate-decision --candidate-id <id> --decision <save|reject|maybe|hold_for_more_data> --notes "..."
marketsentry candidate-location-scores --candidate-id <id> --quiet-score <float> --vibrancy-score <float> --notes "..."
marketsentry candidate-noise-notes --candidate-id <id> --noise-risk <low|moderate|high|severe|unknown> --noise-sources "traffic,airport" --notes "..."
marketsentry operator-workflow-status
marketsentry export-operator-action-summary
```

Candidate decision behavior:

- save should promote to watchlist using existing promotion logic
- reject/maybe/hold_for_more_data should update review decision
- notes should be appended or stored in the existing user_notes/notes field when present
- no duplicate watchlist promotion
- all actions should record user_review_actions if existing workflow does so
- invalid candidate IDs should fail cleanly
- invalid decisions should fail cleanly

Candidate location scores behavior:

- update quiet_score and vibrancy_score on candidate_review_queue
- compute quiet_gatekeeper_result using existing gatekeeper rules
- quiet >= 7.0 should pass
- quiet < 7.0 should fail_noise_risk
- low vibrancy must not override poor Quiet
- optionally update watched property if candidate already promoted and corresponding watched property can be matched
- append notes if provided
- recalc candidate score after update when feasible

Candidate noise notes behavior:

- support manual local field knowledge
- store in notes/user_notes field if present
- if no structured noise fields exist, use notes safely
- do not add walkability fields
- do not infer seller intent
- do not make purchase recommendations
- support sources such as traffic, airport, nighttime_racing, arterial_road, topography, unknown

### 4. Dashboard action buttons/forms

Update Streamlit dashboard:

Add a new section:

```text
Operator Workflow
```

This section should include:

- workflow status metrics
- candidates needing action table
- missing Quiet/Vibrancy table
- pending/hold/maybe candidates table
- latest generated reports
- recommended next local actions

Add candidate action forms:

1. Update candidate decision
   - candidate_id input
   - decision dropdown
   - notes text area
   - Apply button

2. Update Quiet/Vibrancy
   - candidate_id input
   - quiet_score number input
   - vibrancy_score number input
   - notes text area
   - Apply button

3. Add noise notes
   - candidate_id input
   - noise_risk dropdown
   - noise_sources multiselect
   - notes text area
   - Apply button

4. Run operator refresh workflow
   - button
   - displays summary output and generated report paths

Dashboard action buttons may mutate candidate decisions or candidate score fields only when the user explicitly clicks Apply. That is acceptable for this milestone because the user is intentionally applying local operator actions.

### 5. Non-programmer command documentation

Create:

```text
docs/OPERATOR_WORKFLOW.md
```

Explain:

- how to check current status
- how to update candidate decisions without editing CSV
- how to enter Quiet/Vibrancy values without editing CSV
- how to record manual noise concerns
- how to run the operator refresh workflow
- how to use the dashboard Operator Workflow section
- what each decision means
- when to use maybe vs hold_for_more_data vs reject vs save
- how this differs from live retrieval/scraping

Use plain English.

### 6. Report export

Operator action summary export:

```text
data/exports/operator_action_summary_YYYYMMDD_HHMMSS.md
data/exports/operator_action_summary_YYYYMMDD_HHMMSS.csv
```

Include:

- candidate status counts
- missing data counts
- recent candidate actions
- latest key reports
- recommended next actions

### 7. Tests

Add tests for:

- operator workflow status builds on empty database
- operator workflow status builds with sample candidates
- missing Quiet/Vibrancy detection
- missing price detection
- apply candidate decision save promotes to watchlist
- apply candidate decision maybe/reject/hold updates decision
- duplicate save does not duplicate watched property
- invalid candidate ID handled
- invalid decision handled
- location score update writes quiet/vibrancy
- quiet gatekeeper pass when quiet >= 7.0
- quiet gatekeeper fail when quiet < 7.0
- low vibrancy does not override poor Quiet
- location score notes saved/appended
- noise notes saved/appended
- operator refresh workflow runs local report commands or functions
- operator refresh workflow does not run live retrieval
- export operator action summary CSV
- export operator action summary Markdown
- CLI operator-workflow-status
- CLI candidate-decision
- CLI candidate-location-scores
- CLI candidate-noise-notes
- CLI run-operator-refresh-workflow
- dashboard Operator Workflow section loads
- no Redfin source-of-truth overwrite beyond explicit candidate fields
- Quiet Score gatekeeper unchanged
- no walkability fields added
- no browser automation
- no live network calls in tests
- no outbound notifications

### 8. Documentation updates

Update:

- README.md
- docs/RUNBOOK.md
- docs/CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md

Create:

```text
docs/OPERATOR_WORKFLOW.md
docs/decisions/050-guided-operator-workflow.md
docs/prompts/Market_Sentry_Claude_Prompt_051_Guided_Operator_Workflow.md
```

Decision note should explain:

- why operator workflow comes after release candidate finalization
- why this milestone reduces command-line/CSV burden
- why dashboard buttons are allowed to mutate only explicit operator-selected candidate fields
- why live retrieval remains out of scope
- why Quiet Score gatekeeper is unchanged
- why walkability remains excluded
- why noise notes are treated as local buyer field knowledge, not seller-intent inference

## Code standards

- Python 3.11+
- PEP8 compliant
- type hints required
- docstrings required for all functions
- remove unused imports
- use standard library only unless existing dependencies are already used
- no browser automation
- no Playwright/Selenium
- no bypassing CAPTCHAs, paywalls, login walls, anti-bot protections, or technical access controls
- no network calls in tests
- do not import smtplib
- do not import requests/httpx/urllib.request for this feature
- preserve source file paths and timestamps for auditability
- use neutral language
- do not make purchase recommendations
- do not add walkability parsing or fields

## Quality gates

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- Dashboard Operator Workflow section loads.
- Candidate action helpers work.
- Operator refresh workflow exports expected reports.
- Save decision promotes to watchlist.
- Duplicate save does not duplicate watched property.
- Quiet gatekeeper remains unchanged.
- Low Vibrancy does not override poor Quiet.
- Manual noise notes are stored without seller-intent inference.
- No live retrieval is added.
- No browser automation is added.
- No outbound notifications are added.
- No real network calls are performed in tests.
- Scheduled scripts remain safe.
- Changes committed and pushed to origin/main.

## Completion report required

When finished, provide:

1. Summary of what you implemented.
2. Files created or modified.
3. Exact commands run.
4. Final test results with full pytest summary showing 100% pass.
5. Any dependency changes.
6. Any assumptions made.
7. Any blockers or risks remaining.
8. Example operator-workflow-status output.
9. Example candidate-decision output for save/maybe/reject/hold.
10. Example candidate-location-scores output.
11. Example candidate-noise-notes output.
12. Example run-operator-refresh-workflow output.
13. Example operator action summary report paths and row counts.
14. Dashboard Operator Workflow section added.
15. Confirmation that candidate mutations occur only through explicit operator actions.
16. Confirmation that no live retrieval or scraping was added.
17. Confirmation that no outbound notifications are sent.
18. Confirmation that no credentials are stored or requested.
19. Confirmation that Redfin source-of-truth fields are not overwritten except explicit candidate score/decision fields selected by operator.
20. Confirmation that Quiet Score gatekeeper remains unchanged.
21. Confirmation that walkability fields were not added.
22. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
23. Confirmation that tests perform no real network calls.
24. Recommended next implementation step.
25. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 51 complete until all tests pass.
