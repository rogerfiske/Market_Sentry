# Claude Code Prompt 006A - Cross-Site Enrichment Stabilization and Test Remediation

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository:

https://github.com/rogerfiske/Market_Sentry

Local project folder:

C:\Users\Minis\CascadeProjects\Market_Sentry

Current implementation state:

Milestone 6 Cross-Site Enrichment Foundation was implemented at commit:

a6b3f7e

However, Milestone 6 is NOT accepted yet because the completion report showed:

- 231/251 tests passing
- 9 failing tests
- 11 test errors

This violates the quality gate requiring all unit tests to pass.

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Review Milestone 6 implementation at commit a6b3f7e.
4. Review the failing and erroring tests from the latest pytest run.
5. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
6. Keep PRD.md and Architecture.md in the project root.
7. Use src/marketsentry/ as the Python package path.
8. Do not move PRD.md or Architecture.md into docs/.
9. Do not implement live scraping, browser automation, Playwright, Selenium, or active network retrieval.

Important PM direction:

This is not a new feature milestone.

This is a stabilization/remediation prompt for Milestone 6.

Your only goals are:

- Fix all failing tests.
- Fix all test errors.
- Ensure all pre-existing MVP 1-5 tests still pass.
- Ensure Milestone 6 functionality is actually verified by tests, not merely demonstrated manually.
- Improve reliability of the cross-site enrichment foundation.
- Correct documentation/claims so they accurately reflect tested behavior.

Do not start Milestone 7.
Do not implement County Recorder/Assessor integration.
Do not add live retrieval.

## 1. Required first action: run full test suite

Run:

```text
python -m pytest tests/ -v
```

Capture:

- failing test names
- erroring test names
- stack traces
- root causes

Do not proceed by weakening tests unless a test expectation is demonstrably wrong relative to PRD.md, Architecture.md, and Prompt 006.

## 2. Fix all failing/erroring tests

Required result:

```text
100% tests passing
```

The final report must include the exact final pytest output.

Failures to investigate likely involve:

- cross-site URL import
- cross-site enrichment matching
- cross-site observation insert/deduplication
- cross-site comparison
- cross-site report generation
- schema/table creation or migration handling
- fixture parse assumptions
- CLI argument naming mismatches
- incorrect report paths
- mismatch between test DB and configured DB
- inconsistent source_site naming
- normalized URL/domain validation issues
- match-method edge cases

Fix root causes in implementation when possible.

If a test is invalid, explain precisely why and adjust it to match the PRD/Architecture/prompt requirements. Do not delete meaningful tests simply to pass.

## 3. Tighten schema initialization and migration behavior

Verify:

- Fresh database init creates cross_site_observations.
- Existing database from MVP 5 can be upgraded without destructive changes.
- Index creation is idempotent.
- Existing tables and workflows still function.
- No schema change breaks candidate_review_queue, watched_properties, listing_events, source_pages, or user_review_actions.

Add or update tests if needed.

## 4. Verify cross-site URL import behavior

Ensure tests pass for:

- valid source_site values:
  - zillow
  - realtor
  - homes
  - compass
- invalid source_site rejection
- URL/domain validation
- query string and fragment removal
- matching by candidate_id
- matching by property_id
- matching by redfin_url
- matching by normalized address fallback
- unmatched row handling
- no destructive overwrites of user_decision or user_notes
- accurate import counts

## 5. Verify cross-site parser behavior

Ensure tests pass for all four sources:

- Zillow
- Realtor.com
- Homes.com
- Compass

Parser behavior must be:

- no network calls
- no browser automation
- resilient to missing fields
- extracts address, price, beds, baths, sqft, listing_status, displayed_dom where feasible
- extracts garage_spaces where feasible
- detects gas evidence using existing gas detection helper
- ignores walkability-type fields

## 6. Verify cross-site enrichment behavior

Ensure tests pass for:

- parse saved fixture directory
- insert observations
- deduplicate observations consistently
- match to candidate_id/property_id where possible
- preserve unmatched observations if the design allows, or report them clearly if rejected
- counts are accurate and deterministic
- repeated parse/import is idempotent or preserves observation history according to documented design

The current report mentioned "24-hour duplicate detection." Make sure this is tested and deterministic. Avoid tests that depend on wall-clock instability. Use injectable timestamps or controlled comparison logic where appropriate.

## 7. Verify cross-site comparison/report behavior

Ensure tests pass for:

- report generation
- required report columns
- price_discrepancy_flag
- status_discrepancy_flag
- dom_discrepancy_flag
- cross_site_confidence_score
- missing source handling
- no crash when only Redfin exists
- no crash when only one cross-site source exists
- output path exists
- row count is correct

Required report default path should remain under:

```text
data/exports/
```

Unless the project already intentionally uses a different configured export path. If documentation says reports/, align either code or docs so they are consistent.

## 8. Correct completion-report and README claims

The previous completion report said:

"All quality gates passed"

This was incorrect because tests were failing.

Update README or decision docs if they imply that Milestone 6 is accepted with failing tests.

Accurately document:

- Milestone 6 is accepted only when all tests pass.
- Cross-site enrichment uses saved fixtures only.
- No live scraping/network/browser automation.
- County verification remains deferred.

## 9. Add targeted regression tests

Add tests for any root causes found during remediation.

Do not add excessive broad tests, but make sure future regressions are caught.

At minimum, include tests that validate:

- all four cross-site source parsers can parse their fixtures
- URL import counts are deterministic
- enrichment insert/dedup is deterministic
- report export includes all required columns
- discrepancy flags behave as intended

## 10. CLI verification

Run a realistic local CLI verification after tests pass.

At minimum:

```text
marketsentry init-database
marketsentry import-cross-site-urls --file tests/fixtures/cross_site_urls.csv
marketsentry parse-cross-site-fixtures --source zillow --dir tests/fixtures/cross_site/zillow
marketsentry parse-cross-site-fixtures --source realtor --dir tests/fixtures/cross_site/realtor
marketsentry parse-cross-site-fixtures --source homes --dir tests/fixtures/cross_site/homes
marketsentry parse-cross-site-fixtures --source compass --dir tests/fixtures/cross_site/compass
marketsentry export-cross-site-report
```

If the CLI uses different parameter names, use the actual CLI syntax and document it clearly.

## 11. Code standards

- Python 3.11+
- PEP8 compliant.
- Type hints required.
- Docstrings required for all functions.
- Remove unused imports.
- Keep modules small and readable.
- No live scraping.
- No network calls.
- No Playwright/Selenium/browser automation.
- No bypassing bot protections.
- Preserve source URLs and timestamps for future auditability.
- Avoid inaccurate Claude co-authorship metadata.

Quality gates for 006A:

- Full pytest suite passes 100%.
- Cross-site URL import tests pass.
- Cross-site parser tests pass.
- Cross-site enrichment tests pass.
- Cross-site comparison/report tests pass.
- Existing MVP 1-5 tests still pass.
- CLI commands run.
- SQLite init works for fresh database.
- Existing database upgrade path works or is documented/tested.
- No live scraping or network calls added.
- Changes committed and pushed to origin/main.

Completion report required:

When finished, provide:

1. Summary of what was fixed.
2. Root cause list for the previous 9 failing tests and 11 errors.
3. Files created or modified.
4. Exact commands run.
5. Final test results with full pytest summary showing 100% pass.
6. Any dependency changes.
7. Any assumptions made.
8. Any blockers or risks remaining.
9. Any schema changes or migration fixes made.
10. Example CLI workflow used to verify remediation.
11. Counts from cross-site URL import after remediation.
12. Counts from saved fixture parsing by source after remediation.
13. Counts from cross-site observations inserted after remediation.
14. Cross-site report output path and row count.
15. Example discrepancy flags from verification.
16. Confirmation that walkability-type fields are ignored.
17. Confirmation that no live network calls, scraping, Playwright, Selenium, or browser automation were added.
18. Recommended next implementation step after Milestone 6 is fully accepted.
19. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 6 complete until all tests pass.

After all quality gates pass, commit and push the remediation changes to origin/main and include the commit hash in your completion report.
