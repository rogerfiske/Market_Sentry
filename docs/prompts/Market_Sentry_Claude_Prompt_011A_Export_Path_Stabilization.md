# Claude Code Prompt 011A - Export Path Configuration Stabilization

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository:

https://github.com/rogerfiske/Market_Sentry

Local project folder:

C:\Users\Minis\CascadeProjects\Market_Sentry

Current accepted milestone:

- Milestone 11 End-to-End Operating Workflow and Runbook complete at commit 6cf5627

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Review the current codebase through commit 6cf5627.
4. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
5. Keep PRD.md and Architecture.md in the project root.
6. Use src/marketsentry/ as the Python package path.
7. Do not implement live scraping, browser automation, Playwright, Selenium, or active network retrieval in this prompt.
8. Do not add inaccurate Claude Sonnet co-authorship metadata. Omit co-author metadata unless it accurately reflects Claude Code Opus 4.6.

Important PM direction:

This is not a new feature milestone.

This is a stabilization prompt to fix a known configuration inconsistency discovered in Milestone 11.

The Milestone 11 completion report stated:

"config.export_path is referenced in monitoring_report.py, county_verification_report.py, and effective_dom_v2_report.py but is not defined in Config. The workflow avoids this by always passing explicit output paths."

That workaround is acceptable temporarily, but the codebase should not retain report modules that reference a missing Config attribute.

Your task:

Fix export path configuration consistency across report modules.

## 1. Identify all export path references

Search for:

- config.export_path
- export_path
- data_exports_dir
- output_path
- output_dir

Identify all report modules and workflow modules that create report files.

Expected modules to inspect include:

- src/marketsentry/config.py
- src/marketsentry/candidate_report.py
- src/marketsentry/monitoring_report.py
- src/marketsentry/county_verification_report.py
- src/marketsentry/effective_dom_v2_report.py
- src/marketsentry/cross_site_report.py
- src/marketsentry/review_export.py
- src/marketsentry/workflow.py
- src/marketsentry/cli.py

## 2. Choose one canonical export configuration

Preferred approach:

Use `config.data_exports_dir` as the canonical export directory.

If backwards compatibility requires `config.export_path`, implement it as a safe alias/property that returns `data_exports_dir`.

Do not create two competing meanings.

## 3. Fix report modules

Required behavior:

- Every report function should work when output path is explicitly passed.
- Every report function should also work when output path is omitted, using the canonical export directory.
- Export directories should be created if missing.
- Default filenames should remain timestamped and descriptive.
- Behavior should be consistent across reports.

Reports to verify:

- candidate review export
- candidate analysis report
- cross-site report
- watchlist monitoring report
- county verification report
- Effective DOM v2 report
- workflow summary
- report manifest

## 4. Tests

Add or update tests for:

- Config has canonical export directory.
- Any compatibility alias works if implemented.
- Each report function can export using default path with no explicit output path where intended.
- Each report function can export with explicit output path.
- End-to-end workflow still uses explicit paths successfully.
- No module references a missing Config attribute.
- Existing MVP 1-11 tests still pass.

All tests must pass.

## 5. Documentation

Update README.md or docs/RUNBOOK.md only if user-facing command behavior changes.

If no user-facing behavior changes, no documentation update is required beyond a short note in the completion report.

## 6. Code standards

- Python 3.11+
- PEP8 compliant.
- Type hints required.
- Docstrings required for all functions.
- Remove unused imports.
- Keep modules small and readable.
- No live scraping.
- No network calls.
- No Playwright/Selenium/browser automation.
- Preserve source URLs and timestamps for auditability.
- Avoid inaccurate Claude co-authorship metadata.

Quality gates:

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- Existing workflows still work.
- Default report export paths work.
- Explicit report export paths work.
- No missing Config attribute references remain.
- No live scraping or network calls implemented.
- Changes committed and pushed to origin/main.

Completion report required:

When finished, provide:

1. Summary of what was fixed.
2. Files created or modified.
3. Exact commands run.
4. Final test results with full pytest summary showing 100% pass.
5. Any dependency changes.
6. Any assumptions made.
7. Any blockers or risks remaining.
8. Whether `config.export_path` was removed, replaced, or added as an alias.
9. Example report exports verified with default paths.
10. Example report exports verified with explicit paths.
11. Confirmation that no live network calls, scraping, Playwright, Selenium, or browser automation were added.
12. Recommended next implementation step.
13. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark this stabilization complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
