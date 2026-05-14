# Claude Code Prompt 051A - Operator Workflow Stabilization Patch

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry
Local project folder: C:\Users\Minis\CascadeProjects\Market_Sentry
Current accepted commit: 0d74182 (Milestone 51 complete, but stabilization needed)

## Purpose

Milestone 51 was accepted functionally, but live operator testing found stabilization issues:

1. New M51 CLI commands default to the wrong database path:
   - Current wrong default: `data/market_sentry.db`
   - Correct project database: `db/marketsentry.db`

2. `run-operator-refresh-workflow --db db\marketsentry.db` runs, but most workflow steps warn/fail because it imports nonexistent function names or calls existing functions with wrong keyword arguments.

3. The following operator action commands work only when `--db db\marketsentry.db` is explicitly provided:
   - `operator-workflow-status`
   - `candidate-location-scores`
   - `candidate-noise-notes`

The goal of this patch is to make Milestone 51 operator workflow commands work cleanly with the same default database path and function APIs as the rest of the project.

## Before starting

1. Read PRD.md.
2. Read Architecture.md.
3. Read README.md.
4. Read docs/RUNBOOK.md.
5. Read docs/OPERATOR_WORKFLOW.md.
6. Review src/marketsentry/operator_workflow.py.
7. Review src/marketsentry/config.py.
8. Review src/marketsentry/cli.py.
9. Review existing functions in:
   - src/marketsentry/candidate_recalc.py
   - src/marketsentry/monitoring.py
   - src/marketsentry/monitoring_report.py
   - src/marketsentry/candidate_report.py
   - src/marketsentry/operations_digest.py
   - src/marketsentry/portfolio_review_pack.py
   - src/marketsentry/local_operations_bundle.py
10. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
11. Keep PRD.md and Architecture.md in the project root.
12. Use src/marketsentry/ as the Python package path.
13. Do not move PRD.md or Architecture.md into docs/.
14. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
15. Do not implement live retrieval or scraping.
16. Do not run any live network calls in tests.
17. Do not add walkability parsing or walkability fields.
18. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

## Observed user test output

The following succeeded only when `--db db\marketsentry.db` was passed:

```powershell
python -m marketsentry.cli operator-workflow-status --db db\marketsentry.db
python -m marketsentry.cli candidate-location-scores --candidate-id 5 --quiet-score 6.9 --vibrancy-score 1.1 --notes "Manual Redfin visual score capture" --db db\marketsentry.db
python -m marketsentry.cli candidate-noise-notes --candidate-id 5 --noise-risk high --noise-sources "traffic,airport,nighttime_racing" --notes "Track as noise-risk control. Local knowledge suggests traffic/airport noise exposure despite Redfin Quiet 6.9; monitor DOM, price reductions, and final sale price." --db db\marketsentry.db
```

Without `--db`, the command used the wrong default and failed:

```text
Failed: Score update failed: no such table: candidate_review_queue
```

Help output showed:

```text
--db TEXT Path to the SQLite database [default: data/market_sentry.db]
```

Correct default should be:

```text
db/marketsentry.db
```

The refresh workflow produced warnings:

```text
WARN Recalculate candidates: Recalc skipped: cannot import name 'recalc_all_candidates' from 'marketsentry.candidate_recalc'
WARN Snapshot watchlist: Snapshot skipped: cannot import name 'snapshot_watchlist_observations' from 'marketsentry.monitoring'
WARN Export monitoring report: Monitoring report skipped: cannot import name 'export_monitoring_report' from 'marketsentry.monitoring'
WARN Export candidate analysis: Candidate analysis skipped: export_candidate_analysis_report() got an unexpected keyword argument 'output_dir'
WARN Export operations digest: Operations digest skipped: export_operations_digest() got an unexpected keyword argument 'database_path'
WARN Export portfolio review pack: Portfolio review pack skipped: export_portfolio_review_pack() got an unexpected keyword argument 'database_path'
PASS Export local operations bundle: Operations bundle exported
```

## Required fixes

### 1. Fix default database path for M51 commands

Update all new M51 CLI commands so the default DB path matches the rest of the project:

```text
db/marketsentry.db
```

Affected commands likely include:

- operator-workflow-status
- candidate-decision
- candidate-location-scores
- candidate-noise-notes
- run-operator-refresh-workflow
- export-operator-action-summary

Prefer using the canonical Config default if available, rather than hardcoding a divergent path.

Tests must verify help/default behavior or direct execution without `--db` uses the populated project default path pattern.

### 2. Fix operator refresh workflow function calls

Update `run_operator_refresh_workflow()` so each step calls real existing functions with the correct names and signatures.

Do not invent wrappers with misleading names. Use actual functions from the codebase.

Expected local-only steps:

1. candidate recalculation
2. Effective DOM v2 persistence if available
3. watchlist snapshot
4. watchlist monitoring report export
5. candidate analysis report export
6. portfolio review pack export
7. operations digest export
8. local operations bundle export

If a step is genuinely optional or unavailable, handle it cleanly with a warning, but all core report steps that already work from CLI must work inside refresh workflow.

Use existing CLI behavior as the reference.

### 3. Avoid wrong temporary DB initialization

The operator refresh output showed:

```text
INFO: Initializing database at C:\Users\Minis\AppData\Local\Temp\tmp7d7mxgrm.db
```

Ensure operator refresh does not accidentally initialize/report against a temporary DB unless a test intentionally passes a temp DB.

When run against the real project, it should use:

```text
db/marketsentry.db
```

### 4. Add regression tests

Add or update tests to cover:

- M51 commands default to `db/marketsentry.db` or canonical Config default.
- `operator-workflow-status` without `--db` does not use `data/market_sentry.db`.
- `candidate-location-scores` without `--db` uses canonical default path.
- `run-operator-refresh-workflow --db <temp_db>` uses the provided temp DB, not another temp DB.
- `run-operator-refresh-workflow` no longer imports nonexistent names:
  - no `recalc_all_candidates`
  - no `snapshot_watchlist_observations`
  - no `export_monitoring_report` from wrong module
- refresh workflow report export calls match actual function signatures.
- refresh workflow produces expected report outputs when data exists.
- refresh workflow handles empty DB gracefully.
- no live retrieval.
- no browser automation.
- no outbound notifications.
- no walkability fields.
- Quiet gatekeeper unchanged.
- candidate/watchlist/alert state is not mutated except append-only snapshots/report files and explicit operator actions.

### 5. Update documentation

Update:

- docs/OPERATOR_WORKFLOW.md
- docs/RUNBOOK.md
- README.md

Clarify that users can now run commands without manually adding:

```text
--db db\marketsentry.db
```

except when intentionally using a custom database.

Add a short troubleshooting note:

```text
If status shows zero candidates unexpectedly, run `python -m marketsentry.cli status` and confirm database path.
```

### 6. Quality gates

- Full pytest suite passes 100%.
- CLI commands run without requiring `--db` for the normal project database.
- `operator-workflow-status` shows existing project data when run from project root.
- `candidate-location-scores` works without `--db` from project root.
- `candidate-noise-notes` works without `--db` from project root.
- `run-operator-refresh-workflow` no longer reports import/signature warnings for normal core report functions.
- No live retrieval or scraping added.
- No browser automation added.
- No outbound notifications added.
- No walkability fields added.
- Quiet Score gatekeeper unchanged.
- Changes committed and pushed to origin/main.

## Completion report required

When finished, provide:

1. Summary of what was fixed.
2. Root cause of wrong database default.
3. Root cause of refresh workflow import/signature warnings.
4. Files created or modified.
5. Exact commands run.
6. Final test results with full pytest summary showing 100% pass.
7. Dependency changes, if any.
8. Example `operator-workflow-status` output without `--db`.
9. Example `candidate-location-scores` output without `--db`.
10. Example `candidate-noise-notes` output without `--db`.
11. Example `run-operator-refresh-workflow` output showing core steps pass or only valid non-critical warnings.
12. Confirmation that commands still support custom `--db` when explicitly provided.
13. Confirmation that no live retrieval or scraping was added.
14. Confirmation that no outbound notifications are sent.
15. Confirmation that no credentials are stored or requested.
16. Confirmation that Redfin source-of-truth fields are not overwritten except explicit operator-selected candidate fields.
17. Confirmation that Quiet Score gatekeeper remains unchanged.
18. Confirmation that walkability fields were not added.
19. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
20. Confirmation that tests perform no real network calls.
21. Recommended next implementation step.
22. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 51A complete until all tests pass.
