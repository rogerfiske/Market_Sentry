# Claude Code Prompt 055A - Workflow Stabilization, Test Isolation, and Coverage Policy

You are Claude Code Opus 4.6 working in Windsurf IDE on Market_Sentry.

Repository: https://github.com/rogerfiske/Market_Sentry
Local path: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted milestone: 55
Current accepted commit: 7a514ea
Current test baseline: 3079 passed, 18 warnings

## PM decision

Before adding more features, complete a short stabilization pass.

Milestone 55A addresses three accumulated issues:

1. `run_operator_refresh_workflow` does not propagate `exports_dir` to all report steps.
2. The test suite dirties tracked release documents on every run.
3. Coverage is 76% with no `fail_under` enforcement or documented policy.

Do not implement new product features.

## Before starting

Read:

- PRD.md
- Architecture.md
- README.md
- docs/RUNBOOK.md
- docs/OPERATOR_WORKFLOW.md
- docs/LOCAL_OPERATIONS_BUNDLE.md

Review:

- src/marketsentry/operator_workflow.py
- src/marketsentry/cli.py
- src/marketsentry/release_candidate.py
- report exporters used by the refresh workflow
- tests that generate release checklist / release notes
- pyproject.toml

Confirm repo URL. Keep PRD.md and Architecture.md in root. Use src/marketsentry/ as package path.

Do not add live retrieval, scraping, browser automation, outbound notifications, credential handling, walkability fields, or bypass mechanisms. Quiet gatekeeper remains unchanged. Low Vibrancy must not override poor Quiet. Do not print, log, request, store, commit, or expose secrets.

## Current state

Milestone 55 completed the opt-in HowLoud adapter at commit 7a514ea.

Known test baseline:

```text
3079 passed, 18 warnings
```

Known issues:

- `run_operator_refresh_workflow(exports_dir=...)` does not pass that directory to every report exporter.
- Some release tests regenerate tracked docs:
  - docs/RELEASE_CANDIDATE_CHECKLIST.md
  - docs/RELEASE_NOTES_DRAFT.md
  - docs/RELEASE_NOTES_FINAL.md
- Coverage is about 76%, and pyproject runs coverage but does not enforce fail_under.

## Required work

### 1. Fix exports_dir propagation

Update `run_operator_refresh_workflow` so every report/export step honors a custom `exports_dir`.

Verify these steps:

- Recalculate candidates
- Persist Effective DOM v2
- Snapshot watchlist
- Export monitoring report
- Export candidate analysis
- Export operations digest
- Export portfolio review pack
- Export local operations bundle

Requirements:

- If `exports_dir` is supplied, report outputs should land there.
- If not supplied, current default behavior remains.
- Add regression tests using tmp_path.
- Do not add live retrieval or notifications.
- Prefer backward-compatible optional exporter parameters where needed.

### 2. Fix test-suite isolation

Fix release-document tests so they write into tmp_path or another test output directory, not tracked docs.

Tracked docs must not be modified by:

```powershell
python -m pytest --tb=short -q
```

Preserve release-generation functionality. Do not remove the real docs.

### 3. Coverage policy

Add a lightweight coverage policy.

Preferred if low risk:

```toml
[tool.coverage.report]
fail_under = 76
```

or another conservative floor at or below the stable measured value, to prevent future sliding without forcing an immediate 80% jump.

Document:

- current stabilization floor
- future goal of 80%
- live network paths must use fakes/mocks only
- do not add network tests just to inflate coverage

If enforcement is too risky, document why it is deferred.

### 4. Optional local coverage improvement

Only if practical and low risk, add local-only tests around workflow/orchestration code. Do not make this milestone large. Do not add network tests.

### 5. Documentation

Create:

- docs/decisions/055-workflow-test-coverage-stabilization.md
- docs/prompts/Market_Sentry_Claude_Prompt_055A_Workflow_Test_Coverage_Stabilization.md

Update as needed:

- README.md
- docs/RUNBOOK.md
- docs/OPERATOR_WORKFLOW.md

Document exports_dir behavior, test isolation, and coverage policy.

### 6. Tests

Add tests for:

- `run_operator_refresh_workflow(exports_dir=<tmp>)` writes report files into tmp directory.
- candidate analysis export honors custom export directory.
- monitoring report export honors custom export directory.
- operations digest, portfolio review pack, and local operations bundle still honor custom export directory.
- release checklist/notes generation can write to temp output directory.
- full test run does not dirty tracked release docs.
- coverage policy exists in docs and/or pyproject.
- no live retrieval.
- no browser automation.
- no outbound notifications.
- no credentials printed/logged/stored/requested.
- no walkability fields.
- Quiet gatekeeper unchanged.
- low Vibrancy does not override poor Quiet.
- tests perform no real network calls.

## Quality gates

- Full pytest suite passes 100%.
- Test count at least 3079.
- Working tree is clean after pytest.
- Custom `exports_dir` is honored by all refresh report outputs.
- Coverage result reported.
- Coverage policy documented and optionally enforced.
- No live retrieval/scraping/browser automation/outbound notifications/credentials/walkability.
- Quiet gatekeeper unchanged.
- Low Vibrancy does not override poor Quiet.
- Commit and push to origin/main.

## Completion report required

Provide:

1. Summary of what was fixed.
2. Files created or modified.
3. Exact commands run.
4. Final pytest result.
5. Coverage result, delta, and whether fail_under is enforced.
6. Dependency changes.
7. Assumptions made.
8. Blockers or risks remaining.
9. Schema changes, if any.
10. Root cause of exports_dir propagation defect.
11. Example `run-operator-refresh-workflow --exports-dir <tmp>` output showing report paths.
12. Confirmation all refresh report outputs honor custom exports_dir.
13. Root cause of tracked release docs being dirtied.
14. Confirmation full pytest no longer dirties tracked release docs.
15. Coverage policy summary and future coverage recommendation.
16. Safety confirmations: no live retrieval, no scraping, no browser automation or bypass, no outbound notifications, no credentials, no walkability.
17. Confirmation Redfin source-of-truth fields unchanged.
18. Confirmation Quiet gatekeeper unchanged and low Vibrancy does not override poor Quiet.
19. Confirmation tests perform no real network calls.
20. Recommended next implementation step.
21. Git commit hash after commit/push.

Do not mark Milestone 55A complete until all tests pass and the working tree is clean after tests.
