# Claude Code Prompt 054 - Manual Quiet/Vibrancy and Noise Risk Form v2

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry  
Local project folder: `C:\Users\Minis\CascadeProjects\Market_Sentry`  
Current accepted milestone: Milestone 53  
Current accepted commit: `e71d0e5`  
Current known test baseline: `2865 passed, 18 warnings`  
Current branch: `main`

## Purpose

Milestone 54 should improve the most manual part of the current operator workflow: entering Redfin Quiet/Vibrancy scores and local noise-risk notes after the user visually inspects a Redfin property page.

The goal is to provide a safer, clearer, dashboard-first form workflow for:

```text
Candidate selected for deeper analysis
→ user visually reads Redfin Quiet/Vibrancy scores
→ user enters Quiet and Vibrancy
→ system applies Quiet gatekeeper
→ user records local noise knowledge
→ candidate next step is clear
→ reports/dashboard refresh cleanly
```

This is not a scraping milestone. Do not automate reading Redfin pages in this milestone.

---

## Before starting

1. Read `PRD.md`.
2. Read `Architecture.md`.
3. Read `README.md`.
4. Read `docs/RUNBOOK.md`.
5. Read `docs/OPERATOR_WORKFLOW.md`.
6. Read `docs/REDFIN_SCREENING_QUEUE.md`.
7. Read `docs/SCREENING_QUEUE_BATCH_ACTIONS.md`.
8. Review `src/marketsentry/config.py`.
9. Review `src/marketsentry/cli.py`.
10. Review `src/marketsentry/dashboard_app.py`.
11. Review `src/marketsentry/operator_workflow.py`.
12. Review `src/marketsentry/redfin_screening_queue.py`.
13. Review `src/marketsentry/scoring.py`.
14. Review existing candidate action functions:
    - `apply_candidate_location_scores`
    - `apply_candidate_noise_notes`
    - `apply_candidate_decision`
15. Run or inspect:
    - `python -m marketsentry.cli status`
    - `python -m marketsentry.cli redfin-screening-status`
    - `python -m marketsentry.cli screening-next-steps`
    - `python -m marketsentry.cli operator-workflow-status`
16. Confirm the repository URL is `https://github.com/rogerfiske/Market_Sentry`.
17. Keep `PRD.md` and `Architecture.md` in the project root.
18. Use `src/marketsentry/` as the Python package path.
19. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
20. Do not implement new live retrieval or scraping.
21. Do not run live network calls in tests.
22. Do not add outbound notifications or credential storage.
23. Quiet Score gatekeeper must remain unchanged.
24. Low Vibrancy must not override poor Quiet.
25. Do not add walkability parsing or walkability fields.
26. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

---

## Current state and context

Milestone 53 completed:

- screening queue batch actions
- `screening-next-steps`
- optional refresh after Save for Analysis
- dashboard batch forms
- demo data cleanup applied
- current real screening queue contains the three real Temecula items:
  - `31801 Valone Ct`
  - `31457 Britton Cir`
  - `41451 Royal Dornoch Ct`
- real candidates retained:
  - candidate 4: `32420 San Marco Dr`
  - candidate 5: `32152 Camino Nunez`
- watched real property:
  - San Marco
- test baseline: `2865 passed, 18 warnings`

Known live next-step signals from M53:

```text
2 candidate(s) are missing Quiet/Vibrancy scores.
1 candidate fails the Quiet gatekeeper.
```

Known real examples:

```text
Candidate 4: 32420 San Marco Dr
Quiet 9.9
Vibrancy 1.3
Gatekeeper pass
Promoted/watchlisted

Candidate 5: 32152 Camino Nunez
Quiet 6.9
Vibrancy 1.1
Gatekeeper fail_noise_risk
Noise-risk control case
Local concern: Meadows Pkwy, Butterfield Stage Rd, Pauba Rd, nighttime traffic/racing, possible French Valley Airport pattern noise
```

---

## Critical project rules

1. Quiet Score is the gatekeeper.
2. Quiet threshold remains `>= 7.0`.
3. Low Vibrancy never overrides poor Quiet.
4. A property with Quiet 6.9 fails even if Vibrancy is 1.1.
5. Manual local knowledge must be preserved.
6. Use neutral language.
7. Do not infer seller intent.
8. Do not make purchase recommendations.
9. Walkability is excluded.
10. Screening imports must not automatically create candidates.
11. Save for Analysis must remain explicit.
12. This milestone must not scrape Redfin or automate a browser.

---

## Required implementation

### 1. Candidate score-entry status model

Add or extend models in `operator_workflow.py` or a new module if cleaner.

Create a clear candidate score-entry status object with fields such as:

```text
candidate_id
address
redfin_url
quiet_score
vibrancy_score
quiet_gatekeeper_result
noise_risk
noise_sources
user_notes
needs_quiet_vibrancy
needs_noise_notes
is_gatekeeper_fail
is_watchlisted
recommended_next_step
```

Use existing database fields where possible. Do not add schema unless necessary.

### 2. Score validation helpers

Add reusable validation functions for manual score entry:

```text
validate_lifestyle_score(value)
validate_noise_risk(value)
parse_noise_sources(value)
build_gatekeeper_explanation(quiet_score, vibrancy_score)
```

Requirements:

- score must be numeric
- score must be 0.0 to 10.0 inclusive
- allow one decimal precision, but do not reject valid floats unless project conventions require it
- produce operator-friendly error messages
- preserve Quiet threshold 7.0
- explain that Vibrancy does not override Quiet failure

Example explanation:

```text
Quiet 6.9 is below the 7.0 gatekeeper threshold, so this candidate is marked fail_noise_risk even though Vibrancy is low.
```

### 3. CLI improvements

Current commands exist:

```text
candidate-location-scores
candidate-noise-notes
```

Keep them backward compatible.

Add optional/companion commands if useful:

```text
candidate-score-status --candidate-id <id>
list-candidates-needing-scores
candidate-score-and-noise-notes --candidate-id <id> --quiet-score <value> --vibrancy-score <value> --noise-risk <level> --noise-sources "..." --notes "..."
```

At minimum, implement:

```text
candidate-score-status
list-candidates-needing-scores
```

If adding the combined command is low risk, add it too because it reduces operator burden.

All commands must:

- use canonical DB default
- support explicit `--db`
- never perform live retrieval
- produce clear next-step guidance

### 4. Dashboard Manual Score Entry v2

Update dashboard section `Operator Workflow` or add a dedicated section:

```text
Manual Quiet/Vibrancy Entry
```

It should include:

- table of candidates needing Quiet/Vibrancy
- candidate ID input
- address display after selecting candidate if practical
- Redfin URL clickable link
- Quiet score input
- Vibrancy score input
- automatic gatekeeper preview
- noise risk dropdown:
  - unknown
  - low
  - moderate
  - high
  - severe
- noise source checklist or text field:
  - traffic
  - airport
  - road
  - freeway
  - nighttime_racing
  - school
  - commercial
  - unknown
  - other
- notes text area
- Save Scores button
- Save Noise Notes button
- Save Scores + Noise Notes button if practical
- optional Run local refresh checkbox
- no mutation on page load
- clear success/failure messages
- warning for Quiet < 7.0
- explicit note that low Vibrancy does not override Quiet failure

Reliability is more important than fancy UI.

### 5. Next-step integration

Update `screening-next-steps` and/or `operator-workflow-status` so manual score actions are clearer.

Examples:

```text
Candidates missing Quiet/Vibrancy:
  Candidate 7 - 31801 Valone Ct
  Candidate 8 - 31457 Britton Cir

Next:
  Open the Redfin page, visually read Quiet and Vibrancy, then run:
  python -m marketsentry.cli candidate-location-scores --candidate-id <id> --quiet-score <value> --vibrancy-score <value>
```

For gatekeeper failures:

```text
Candidate 5 fails Quiet gatekeeper. Add local noise notes or hold/reject as a noise-risk control.
```

### 6. Report/export improvements

Add or enhance a local export:

```text
data/exports/manual_score_entry_queue_YYYYMMDD_HHMMSS.csv
data/exports/manual_score_entry_queue_YYYYMMDD_HHMMSS.md
```

Report fields:

- candidate ID
- address
- city/state/zip if available
- Redfin URL clickable in Markdown
- current Quiet/Vibrancy
- gatekeeper result
- noise risk
- noise sources
- missing fields
- recommended next step
- notes

Add CLI:

```text
python -m marketsentry.cli export-manual-score-entry-queue
```

### 7. Documentation

Create:

```text
docs/MANUAL_SCORE_ENTRY.md
docs/decisions/053-manual-score-entry-v2.md
docs/prompts/Market_Sentry_Claude_Prompt_054_Manual_Score_Entry_v2.md
```

Update:

```text
README.md
docs/RUNBOOK.md
docs/OPERATOR_WORKFLOW.md
docs/REDFIN_SCREENING_QUEUE.md
docs/SCREENING_QUEUE_BATCH_ACTIONS.md
```

Docs should explain:

- where to find Quiet/Vibrancy on Redfin
- how to enter scores
- why Quiet is gatekeeper
- why low Vibrancy does not rescue poor Quiet
- how to enter local noise knowledge
- how to treat a noise-risk control case
- how to export the manual score queue
- how to refresh reports after score entry
- that this is manual and local-only, not scraping

### 8. Tests

Add tests for:

- score validation accepts 0, 7.0, 9.9, 10.0
- score validation rejects negative values, >10, nonnumeric values
- Quiet 7.0 passes
- Quiet 6.9 fails
- low Vibrancy does not override Quiet 6.9
- gatekeeper explanation text
- parse noise sources
- invalid noise risk
- candidate score status for candidate with no scores
- candidate score status for candidate with passing scores
- candidate score status for candidate with failing scores
- list candidates needing scores
- combined score/noise command if implemented
- existing candidate-location-scores remains backward compatible
- existing candidate-noise-notes remains backward compatible
- export manual score entry queue CSV
- export manual score entry queue Markdown
- dashboard Manual Quiet/Vibrancy Entry section loads
- no mutation on dashboard load
- canonical DB default is used
- explicit custom `--db` works
- no live retrieval
- no browser automation
- no outbound notifications
- no credentials stored/requested
- no walkability fields
- tests perform no real network calls

### 9. Code standards

- Python 3.11+
- type hints
- docstrings for public functions
- PEP8 compliant
- no unused imports
- keep functions small and testable
- use existing project patterns
- no network calls
- no browser automation
- no outbound notifications
- no credential handling
- no walkability fields

---

## Quality gates

- Full pytest suite passes 100%.
- Test count must be at least current baseline `2865`.
- CLI commands import and run.
- Dashboard loads.
- Manual Quiet/Vibrancy Entry section loads.
- Existing M51/M53 commands remain backward compatible.
- Score validation works.
- Quiet gatekeeper unchanged.
- Low Vibrancy does not override Quiet failure.
- Export manual score entry queue works.
- No live retrieval or scraping added.
- No browser automation added.
- No outbound notifications added.
- No credentials stored/requested.
- Walkability remains excluded.
- Custom `--db` still works.
- README and docs updated.
- Changes committed and pushed to origin/main.

---

## Completion report required

When finished, provide:

1. Summary of what was implemented.
2. Files created or modified.
3. Exact commands run.
4. Final test results with full pytest summary showing 100% pass.
5. Coverage result and whether coverage changed.
6. Dependency changes, if any.
7. Assumptions made.
8. Blockers or risks remaining.
9. Schema changes, if any.
10. Example `candidate-score-status` output.
11. Example `list-candidates-needing-scores` output.
12. Example combined score/noise command output if implemented.
13. Example `export-manual-score-entry-queue` output.
14. Example dashboard behavior added.
15. Confirmation that existing `candidate-location-scores` remains backward compatible.
16. Confirmation that existing `candidate-noise-notes` remains backward compatible.
17. Confirmation that score entry is manual and local-only.
18. Confirmation that no live retrieval or scraping was added.
19. Confirmation that no outbound notifications are sent.
20. Confirmation that no credentials are stored or requested.
21. Confirmation that Redfin source-of-truth fields are not overwritten outside explicit operator-selected fields.
22. Confirmation that Quiet Score gatekeeper remains unchanged.
23. Confirmation that low Vibrancy does not override poor Quiet.
24. Confirmation that walkability fields were not added.
25. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
26. Confirmation that tests perform no real network calls.
27. Recommended next implementation step.
28. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 54 complete until all tests pass.
