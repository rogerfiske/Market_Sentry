# Claude Code Prompt 052A - Global Database Default Stabilization and Demo Noise Cleanup

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository: https://github.com/rogerfiske/Market_Sentry  
Local project folder: `C:\Users\Minis\CascadeProjects\Market_Sentry`  
Current accepted milestone: Milestone 52  
Current accepted commit: `9bf7648`  
Current known test baseline: `2717 passed, 18 warnings`  
Current branch: `main`

## Purpose

Milestone 52A is a small stabilization milestone that must happen before Milestone 53.

Claude Code reconnected to the project and verified that the M51A database-default fix was incomplete. M51A fixed the operator workflow commands, but the same defect remains in the portfolio-alert/focus/email-digest family and a few module-level defaults.

The problem is that several commands still default to:

```text
data/market_sentry.db
```

instead of the canonical project database:

```text
db/marketsentry.db
```

Impact: these commands can silently read or create an empty database and appear to succeed while reporting on no real data.

This milestone fixes that defect class globally, updates stale docs/status headings, and provides a safe cleanup option for demo/sample records and stray database artifacts.

Do not start Milestone 53 until this stabilization is complete.

---

## Before starting

1. Read `PRD.md`.
2. Read `Architecture.md`.
3. Read `README.md`.
4. Read `docs/RUNBOOK.md`.
5. Read `docs/OPERATOR_WORKFLOW.md`.
6. Read `docs/REDFIN_SCREENING_QUEUE.md`.
7. Review `src/marketsentry/config.py`.
8. Review `src/marketsentry/cli.py`.
9. Review `src/marketsentry/dashboard_app.py`.
10. Review `src/marketsentry/release_candidate.py`.
11. Review `src/marketsentry/local_operations_bundle.py`.
12. Search the repo for every occurrence of:

```text
data/market_sentry.db
```

13. Confirm the repository URL is `https://github.com/rogerfiske/Market_Sentry`.
14. Keep `PRD.md` and `Architecture.md` in the project root.
15. Use `src/marketsentry/` as the Python package path.
16. Do not implement browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass.
17. Do not implement new live retrieval or scraping.
18. Do not run live network calls in tests.
19. Do not add outbound notifications or credential storage.
20. Quiet Score gatekeeper must remain unchanged.
21. Do not add walkability parsing or walkability fields.
22. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

---

## Verified current state

Claude Code previously verified:

```text
HEAD: 9bf7648
Tag v0.1.0-rc1 resolves to cb0b135
Branch main is in sync with origin/main
Full test suite: 2717 passed, 18 warnings
Coverage: 76%, currently not fail-gated
```

Claude also found:

```text
15 hardcoded data/market_sentry.db defaults across 4 modules
9 of those are live CLI command defaults
```

Affected CLI commands reported:

```text
persist-portfolio-trend-alerts
compare-portfolio-trend-alert-runs
portfolio-trend-alert-history-summary
export-portfolio-trend-alert-history-report
export-portfolio-trend-alert-run-comparison
portfolio-alert-focus
export-portfolio-alert-focus-digest
portfolio-alert-email-digest
export-portfolio-alert-email-digest
```

Other affected locations:

```text
dashboard_app.py around line 1874
release_candidate.py around lines 197 and 657
local_operations_bundle.py around line 1323
```

Re-search; do not rely only on line numbers.

---

## Required work

### 1. Replace all wrong hardcoded DB defaults

Replace all remaining `data/market_sentry.db` defaults with the canonical database path from config.

Preferred pattern:

```python
from marketsentry.config import get_config
db_path = db or get_config().database_path
```

or whatever canonical pattern the rest of the project uses.

Do not introduce a second canonical default.

The correct normal project DB is:

```text
db/marketsentry.db
```

### 2. Fix the 9 CLI command defaults

Ensure the following commands run against the real project DB when launched from the project root without `--db`:

```text
persist-portfolio-trend-alerts
compare-portfolio-trend-alert-runs
portfolio-trend-alert-history-summary
export-portfolio-trend-alert-history-report
export-portfolio-trend-alert-run-comparison
portfolio-alert-focus
export-portfolio-alert-focus-digest
portfolio-alert-email-digest
export-portfolio-alert-email-digest
```

They must still support explicit custom `--db`.

### 3. Fix module-level defaults

Fix remaining hardcoded defaults in:

```text
dashboard_app.py
release_candidate.py
local_operations_bundle.py
```

and anywhere else found by search.

After the patch, a repo-wide search for `data/market_sentry.db` should return zero live code defaults. It is acceptable for historical docs or changelogs to mention it only if they explicitly identify it as the old wrong default.

### 4. Add regression tests

Add tests that verify:

- No CLI command default uses `data/market_sentry.db`.
- The 9 listed CLI commands use `config.database_path` or `db/marketsentry.db` by default.
- The 9 listed CLI commands still accept explicit `--db`.
- `dashboard_app.py` does not default to `data/market_sentry.db`.
- `release_candidate.py` does not default to `data/market_sentry.db`.
- `local_operations_bundle.py` does not default to `data/market_sentry.db`.
- Running portfolio alert/focus/digest commands without `--db` does not create or read `data/market_sentry.db`.
- No live retrieval.
- No browser automation.
- No outbound notifications.
- No credentials stored/requested.
- No walkability fields added.
- Quiet Score gatekeeper unchanged.
- Tests perform no real network calls.

### 5. README status cleanup

The current README has a stale heading near the top:

```text
Current Milestone: Configurable Portfolio Trend Alert Rules (MVP 44)
```

Update this to the current accepted project status:

```text
Current Milestone: Initial Redfin Screening Queue (MVP 52)
```

or an equivalent accurate heading.

Keep the rebuilt project structure tree that was already added. The README was reportedly modified but uncommitted; include that update in this milestone commit if it is correct.

### 6. Demo/sample data pollution handling

The real database currently includes sample/demo records from M52 validation:

```text
Screening ID 1: 40000 Example St, Murrieta -> saved_for_analysis -> candidate 6
Screening ID 2: 30000 Sample Ave, Temecula -> rejected
Screening ID 3: 55555 Fixture Ln, Murrieta -> new fixture item
```

These make the operator console noisier for the non-programmer user.

Do not silently delete records.

Implement one of these safe options:

#### Preferred option A — add an explicit local cleanup command

Add a CLI command:

```text
python -m marketsentry.cli cleanup-demo-data --dry-run
python -m marketsentry.cli cleanup-demo-data --confirm
```

Behavior:

- Dry-run by default.
- Clearly lists demo/sample records that would be removed or archived.
- Requires `--confirm` to mutate the DB.
- Targets only known sample/demo records by unmistakable values:
  - `40000 Example St`
  - `30000 Sample Ave`
  - `55555 Fixture Ln`
  - sample fixture URLs/notes if present
- Must not remove real user records:
  - `31801 Valone Ct`
  - `31457 Britton Cir`
  - `41451 Royal Dornoch Ct`
  - `32420 San Marco Dr`
  - `32152 Camino Nunez`
- Should remove or archive linked candidate 6 only if it is clearly tied to `40000 Example St`.
- Must report every planned/removal action.

#### Option B — document manual SQL cleanup only

If a cleanup command is too much for a stabilization patch, create a clear documented manual cleanup procedure and do not mutate data.

Preferred is Option A because it improves operator usability and avoids hand-editing SQLite.

### 7. Stray database artifact handling

Do not delete without explicit user command, but add documentation and/or dry-run detection for likely strays:

```text
nul
dbmarketsentry.db
data/market_sentry.db
```

Add a troubleshooting note explaining:

- correct DB: `db/marketsentry.db`
- wrong/legacy DB: `data/market_sentry.db`
- likely shell artifact: `dbmarketsentry.db`
- likely Windows redirect artifact: `nul`

A cleanup command may report these as “detected stray files” and print deletion instructions, but it should not delete files unless `--confirm-stray-files` or a similar explicit flag is provided.

### 8. Coverage policy note

The test suite currently passes but coverage is 76%, below the user's general 80% standard. Do not block this stabilization milestone on raising total coverage to 80% unless it is practical and low risk.

Do add a short note in the completion report:

- whether coverage changed,
- whether coverage enforcement exists,
- recommended future coverage milestone if needed.

Do not add network tests to cover live retrieval code.

---

## Quality gates

- Full pytest suite passes 100%.
- Test count must be at least the current baseline of 2717.
- No live code default remains for `data/market_sentry.db`.
- The 9 affected CLI commands work without `--db` against the canonical database.
- The 9 affected CLI commands still support explicit custom `--db`.
- README current milestone heading is accurate.
- README rebuilt file tree is either committed or deliberately reverted with explanation.
- Demo/sample cleanup is either implemented as explicit dry-run/confirm command or documented clearly.
- No real user data is deleted automatically.
- No live retrieval or scraping added.
- No browser automation added.
- No outbound notifications added.
- No credentials stored/requested.
- Quiet gatekeeper remains unchanged.
- Walkability remains excluded.
- Changes committed and pushed to origin/main.

---

## Completion report required

When finished, provide:

1. Summary of what was fixed.
2. Root cause of the remaining database default defect.
3. Files created or modified.
4. Exact repo search command used to find `data/market_sentry.db`.
5. Final count of remaining `data/market_sentry.db` occurrences and whether any are historical docs only.
6. Exact commands run.
7. Final test results with full pytest summary showing 100% pass.
8. Coverage result and whether coverage enforcement exists.
9. Dependency changes, if any.
10. README status/tree decision: committed or reverted.
11. Demo/sample cleanup approach implemented or documented.
12. Example output of the demo cleanup dry-run, if implemented.
13. Example output of one affected CLI command without `--db`.
14. Example output of one affected CLI command with explicit `--db`.
15. Confirmation that the 9 affected CLI commands no longer default to `data/market_sentry.db`.
16. Confirmation that custom `--db` still works.
17. Confirmation that no real user data was deleted automatically.
18. Confirmation that no live retrieval or scraping was added.
19. Confirmation that no outbound notifications are sent.
20. Confirmation that no credentials are stored or requested.
21. Confirmation that Redfin source-of-truth fields are not overwritten.
22. Confirmation that Quiet Score gatekeeper remains unchanged.
23. Confirmation that walkability fields were not added.
24. Confirmation that no browser automation, Playwright, Selenium, CAPTCHA bypass, login bypass, paywall bypass, anti-bot bypass, or technical access-control bypass was added.
25. Confirmation that tests perform no real network calls.
26. Recommended next implementation step.
27. Git commit hash after committing and pushing completed changes to origin/main.

Do not mark Milestone 52A complete until all tests pass.
