# Claude Code Prompt 003 - Redfin Discovery Adapter Foundation

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository:

https://github.com/rogerfiske/Market_Sentry

Local project folder:

C:\Users\Minis\CascadeProjects\Market_Sentry

Current accepted milestones:

- Milestone 1 scaffold complete at commit c8599761be1aeda80b075cf668c61970e587ebe7
- Milestone 2 candidate review queue and watchlist promotion complete at commit 5da7747a44069696189d1abb8057ee23f17d8754

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Review the current codebase and Milestone 2 implementation.
4. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
5. Keep PRD.md and Architecture.md in the project root.
6. Use src/marketsentry/ as the Python package path.
7. Do not move PRD.md or Architecture.md into docs/.
8. Do not implement live scraping, browser automation, Playwright, Selenium, or active network retrieval in this milestone.

Important PM direction:

Do not jump directly to live Redfin scraping in this milestone.

Milestone 3 must build the Redfin Discovery Adapter foundation using:

- Manual Redfin URL list import
- Saved/static HTML fixture parsing where available
- Parser interfaces that can later support compliant live retrieval
- Candidate insertion into the existing candidate_review_queue

This is intentional. The goal is to prove the discovery/parsing/storage path before adding live site access.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It starts with Redfin candidate discovery, stages homes for human review, and then monitors user-selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, and cross-site/county validation.

Critical domain rules:

1. Effective DOM measures property-level market exposure across listing, removal, and relisting events within a defined lookback window, excluding periods reset by confirmed ownership transfer.
2. Quiet Score is the gatekeeper. Reject or heavily downgrade if Quiet Score is below threshold, even when Vibrancy is low.
3. Target is very high Quiet and very low Vibrancy.
4. Low Vibrancy alone is not sufficient.
5. Any mention of gas means the property has natural gas service/supply.
6. Walkability-type information is excluded from the initial scope.
7. Use neutral language. Do not infer seller intent.
8. The workflow is human-in-the-loop: candidate review queue first, then user-selected watched properties.

Active Redfin start paths to preserve in configuration:

Murrieta path:

```text
https://www.redfin.com/city/12866/CA/Murrieta/filter/property-type=house,min-price=550k,max-price=990k,min-beds=2,min-baths=2,min-parking=2,pool-type=no-private,mr=6:19701
```

Temecula path:

```text
https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house,min-price=550k,max-price=990k,min-beds=2,min-baths=2,min-parking=2,pool-type=no-private,mr=6:12866
```

Your task for Prompt 003:

Implement Redfin Discovery Adapter Foundation v0.

This milestone must make it possible to add candidate properties from manually supplied Redfin property URLs and from saved/static Redfin-like HTML fixtures, then insert those candidates into the existing candidate_review_queue.

No live network calls.

## 1. Create Redfin discovery models

Create or update appropriate models for:

- RedfinSearchConfig
- RedfinCandidateSummary
- RedfinParseResult
- DiscoveryRunResult

Required fields for RedfinCandidateSummary:

- redfin_url
- source_site
- source_search_url
- address
- normalized_address
- city
- zip
- price
- beds
- baths
- sqft
- lot_size
- displayed_dom
- quiet_score
- vibrancy_score
- quiet_gatekeeper_result
- garage_spaces
- gas_service
- gas_evidence
- basic_notes

Not every field is required to be present. Missing fields should be represented safely as None or empty strings, not parser failures.

## 2. Manual Redfin URL import

Implement a manual URL import workflow.

Input file:

```text
data/imports/redfin_urls.csv
```

Required columns:

- redfin_url

Optional columns:

- address
- city
- zip
- price
- beds
- baths
- sqft
- notes

Behavior:

- Read the CSV.
- Normalize and validate Redfin URLs.
- Reject clearly invalid URLs with a useful error or warning.
- Insert valid rows into candidate_review_queue using the existing insertion functions.
- Deduplicate against existing candidates.
- Preserve source_site = redfin.
- Preserve source_search_url when supplied or use blank/None.
- Preserve notes as basic_notes or user_notes only if the existing schema supports it.

Add CLI command:

```text
marketsentry import-redfin-urls --file data/imports/redfin_urls.csv
```

## 3. Redfin-like saved HTML fixture parsing

Implement parser foundation using saved HTML files.

Input directory:

```text
data/raw/redfin/
```

Expected file types:

- .html
- .htm

Behavior:

- Parse saved/static Redfin-like HTML fixtures.
- Extract candidate property URLs from anchor tags where URLs match Redfin property page patterns.
- Extract visible summary text where feasible.
- Return RedfinCandidateSummary records.
- Insert parsed candidates into candidate_review_queue.
- Do not require perfect Redfin parsing yet.
- Parser should be resilient to missing fields.
- Parser should not perform any network calls.

Add CLI command:

```text
marketsentry parse-redfin-fixtures --dir data/raw/redfin
```

## 4. Redfin URL and address normalization

Implement or update helper functions for:

- is_redfin_url
- normalize_redfin_url
- extract_redfin_home_id if feasible from URL
- extract_address_from_redfin_url if feasible
- normalize_address if current normalization is insufficient

Expected Redfin property URL examples:

```text
https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263
https://www.redfin.com/CA/Temecula/43511-Calle-Nacido-92592/home/6199187
```

Normalization requirements:

- Remove query string tracking parameters.
- Remove fragments.
- Preserve canonical path.
- Handle trailing slashes consistently.
- Preserve original URL in source_pages or notes if existing schema supports it.

## 5. Candidate insertion integration

Use the existing candidate_review_queue insertion functions from Milestone 2.

Required behavior:

- Manual URL import inserts into candidate_review_queue.
- Fixture parsing inserts into candidate_review_queue.
- Duplicate imported URLs do not create duplicate candidates.
- Duplicate normalized addresses do not create duplicate candidates where address is available.
- Existing user_decision values should not be overwritten by re-import.

## 6. Source audit table usage

If source_pages is already present and practical to use, record fixture parsing provenance:

- source_site = redfin
- source_url = local fixture path or discovered Redfin URL
- retrieval_method = manual_url_import or saved_fixture
- parse_status = success, partial, or failed
- content_hash where feasible

Do not overcomplicate this. Candidate insertion is more important than audit perfection for this milestone.

## 7. CLI commands

Add or complete these commands:

```text
marketsentry import-redfin-urls --file data/imports/redfin_urls.csv
marketsentry parse-redfin-fixtures --dir data/raw/redfin
marketsentry list-candidates
marketsentry export-review
```

The existing list/export commands should still work.

CLI output requirements:

- ASCII-safe output.
- Clear counts:
  - rows read
  - candidates inserted
  - candidates skipped as duplicates
  - rows rejected
  - parse warnings
- Helpful error messages for missing files or invalid columns.

## 8. Tests

Add or update tests for:

- Redfin URL validation.
- Redfin URL normalization.
- Redfin URL import from CSV.
- Duplicate Redfin URL import.
- Invalid URL handling.
- HTML fixture parsing.
- Missing fields in fixture parsing.
- Candidate insertion from parsed fixture.
- Preservation of existing user_decision on duplicate import.
- CLI command behavior where practical.

Add test fixtures under:

```text
tests/fixtures/
```

At minimum include:

- redfin_urls_valid.csv
- redfin_urls_mixed_invalid.csv
- redfin_search_fixture.html

The HTML fixture must be static and minimal. It should not require network access.

## 9. Clean up minor Milestone 2 issues

Address these if practical without distracting from Milestone 3:

1. Fix the pandas FutureWarning from CSV decision simulation or import path if it appears in tests.
2. Add targeted CLI tests for the new import/parse commands if feasible.
3. Keep future commit metadata accurate for Claude Code Opus 4.6. Do not add an inaccurate Claude Sonnet co-authorship tag.

## 10. Documentation

Update README.md with:

- Milestone 3 status.
- How to create data/imports/redfin_urls.csv.
- How to import Redfin URLs manually.
- How to place saved Redfin HTML fixtures in data/raw/redfin/.
- How to parse fixtures.
- How to export candidates for review after import.
- Clear statement that Milestone 3 performs no live scraping or network access.

Add a design decision note:

```text
docs/decisions/002-redfin-discovery-adapter-foundation.md
```

Explain:

- Why live scraping is intentionally deferred.
- Why manual URL import and saved fixtures are used first.
- How this supports later compliant source adapters.

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

Quality gates:

- Project imports cleanly.
- CLI commands run.
- SQLite init still works.
- Existing review queue workflow still works.
- Manual Redfin URL import works.
- Saved fixture parsing works.
- Unit tests pass.
- No live scraping or network calls implemented.
- Changes committed and pushed to origin/main.

Completion report required:

When finished, provide:

1. Summary of what you implemented.
2. Files created or modified.
3. Exact commands run.
4. Test results.
5. Any dependency changes.
6. Any assumptions made.
7. Any blockers or risks.
8. Any schema changes made.
9. Example CLI workflow used to verify Milestone 3.
10. Counts from sample/manual Redfin URL import test.
11. Counts from HTML fixture parsing test.
12. Confirmation that no live network calls, scraping, Playwright, Selenium, or browser automation were added.
13. Recommended next implementation step.
14. Git commit hash after committing and pushing completed changes to origin/main.

Important:

After all quality gates pass, commit and push the completed story changes to origin/main and include the commit hash in your completion report.
