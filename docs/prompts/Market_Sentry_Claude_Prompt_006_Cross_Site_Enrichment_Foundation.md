 Claude Code Prompt 006 - Cross-Site Enrichment Foundation

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository:

https://github.com/rogerfiske/Market_Sentry

Local project folder:

C:\Users\Minis\CascadeProjects\Market_Sentry

Current accepted milestones:

- Milestone 1 scaffold complete at commit c8599761be1aeda80b075cf668c61970e587ebe7
- Milestone 2 candidate review queue and watchlist promotion complete at commit 5da7747a44069696189d1abb8057ee23f17d8754
- Milestone 3 Redfin discovery adapter foundation complete at commit 91eac91085609c38f150881bf35e5a22d1f6bdf0
- Milestone 4 Redfin detail parser and candidate enrichment complete at commit dafb63d
- Milestone 5 Effective DOM engine and candidate scoring report complete at commit 52ea72d

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Review the current codebase and Milestone 5 implementation.
4. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
5. Keep PRD.md and Architecture.md in the project root.
6. Use src/marketsentry/ as the Python package path.
7. Do not move PRD.md or Architecture.md into docs/.
8. Do not implement live scraping, browser automation, Playwright, Selenium, or active network retrieval in this milestone.

Important PM direction:

Milestone 6 begins cross-site enrichment, but only as a controlled foundation.

Do not attempt broad live web collection.

Do not add live Zillow, Realtor.com, Homes.com, Compass, County Recorder, or Assessor retrieval.

Use only:

- Manually supplied cross-site URLs.
- Saved/static HTML fixtures.
- Deterministic parsing.
- Existing candidate/watched property records.
- Local CSV import/export.

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
9. Redfin remains the primary discovery/detail source for now. Zillow, Realtor.com, Homes.com, and Compass are cross-check sources.

Your task for Prompt 006:

Implement Cross-Site Enrichment Foundation v0.

This milestone must make it possible to associate Zillow, Realtor.com, Homes.com, and Compass URLs with existing candidates or watched properties, parse saved/static cross-site detail fixtures, and produce a cross-site comparison report.

No live network calls.

## 1. Cross-site source scope

Supported source sites for this milestone:

- zillow
- realtor
- homes
- compass

Do not implement county recorder/assessor yet. County verification is a later milestone.

## 2. Cross-site URL import

Implement CSV import for manually supplied cross-site URLs.

Input file:

```text
data/imports/cross_site_urls.csv
```

Required columns:

- source_site
- source_url

At least one of the following identity fields is required:

- candidate_id
- property_id
- redfin_url
- address

Optional columns:

- city
- zip
- notes

Behavior:

- Validate source_site against supported values.
- Normalize source_url by removing query strings and fragments where appropriate.
- Validate that URL domain appears compatible with the source_site.
- Match to candidate_review_queue or watched_properties by:
  1. candidate_id
  2. property_id
  3. redfin_url
  4. normalized address fallback
- Insert or update a cross-site source observation/link record.
- Do not overwrite user_decision or user_notes.
- Do not promote candidates to watched_properties in this command.
- Preserve notes where practical.

Add CLI command:

```text
marketsentry import-cross-site-urls --file data/imports/cross_site_urls.csv
```

## 3. Cross-site observation model

Create typed models for:

- CrossSiteSource
- CrossSiteUrlImportRow
- CrossSiteObservation
- CrossSiteParseResult
- CrossSiteComparisonResult

Observation fields to support where available:

- observation_id
- candidate_id
- property_id
- source_site
- source_url
- normalized_source_url
- observed_at
- match_method
- address
- normalized_address
- city
- state
- zip
- price
- beds
- baths
- sqft
- lot_size
- listing_status
- displayed_dom
- garage_spaces
- gas_service
- gas_evidence
- listing_agent
- listing_broker
- mls_number
- source_mls
- property_description
- parse_status
- parse_warnings
- notes

## 4. Database support

If the existing schema is insufficient, add a simple schema migration or table creation for cross-site observations.

Preferred table name:

```text
cross_site_observations
```

Required behavior:

- SQLite init creates the new table.
- Existing databases can be upgraded without destructive changes.
- Add a uniqueness strategy to avoid duplicate observations where practical:
  - candidate_id/property_id + source_site + normalized_source_url
  - or source_site + normalized_source_url
- Preserve observation history if repeated parse values change, unless the current architecture strongly favors update-in-place.
- Document whichever behavior is implemented.

Do not break existing tables or workflows.

## 5. Saved fixture directories

Use saved fixture directories:

```text
data/raw/zillow/details/
data/raw/realtor/details/
data/raw/homes/details/
data/raw/compass/details/
```

Test fixtures should be under:

```text
tests/fixtures/cross_site/zillow/
tests/fixtures/cross_site/realtor/
tests/fixtures/cross_site/homes/
tests/fixtures/cross_site/compass/
```

At minimum include simple static fixtures for each site that include:

- Source URL or canonical URL text
- Address
- Price
- Beds/baths/sqft
- Listing status where available
- DOM or listing age text where available
- Garage evidence where available
- Gas evidence where available
- Broker/agent text where available

Fixtures should be minimal and synthetic or sanitized. No network access.

## 6. Cross-site parser foundation

Create a generic parser module, for example:

```text
src/marketsentry/cross_site_parser.py
```

Or separate simple source modules if cleaner:

```text
src/marketsentry/crosscheck_zillow.py
src/marketsentry/crosscheck_realtor.py
src/marketsentry/crosscheck_homes.py
src/marketsentry/crosscheck_compass.py
```

Required functions:

- parse_cross_site_detail_html(html: str, source_site: str, source_url: str | None = None) -> CrossSiteParseResult
- parse_cross_site_detail_file(file_path: Path, source_site: str) -> CrossSiteParseResult
- parse_cross_site_directory(directory: Path, source_site: str) -> list[CrossSiteParseResult]

Parser requirements:

- No network calls.
- No browser automation.
- Resilient to missing fields.
- Preserve warnings and raw snippets where useful.
- Extract address, price, beds, baths, sqft, listing_status, displayed_dom where feasible.
- Extract garage_spaces where feasible.
- Use the existing gas detection helper. Any mention of gas means natural gas supply/service exists.
- Ignore Walk Score, Bike Score, Transit Score, commute, walkability, and other walkability-type fields.
- Do not attempt source-specific perfection yet. This is v0 foundation parsing.

## 7. Cross-site enrichment workflow

Add workflow to parse saved cross-site detail fixtures and store observations.

CLI command:

```text
marketsentry parse-cross-site-fixtures --source zillow --dir data/raw/zillow/details
```

Support source values:

- zillow
- realtor
- homes
- compass

Behavior:

- Parse all .html/.htm files in directory.
- Match observations to candidates/watched properties by:
  1. source_url already imported
  2. normalized address
  3. redfin_url if included in CSV/import metadata
- Store parsed observations.
- Print:
  - files processed
  - observations parsed
  - observations inserted
  - duplicates skipped
  - matched candidates
  - matched watched properties
  - warnings/errors

## 8. Cross-site comparison report

Create a report module or extend candidate_report.py.

CLI command:

```text
marketsentry export-cross-site-report
```

Required report columns:

- candidate_id
- property_id
- address
- city
- zip
- redfin_url
- redfin_price
- redfin_displayed_dom
- redfin_effective_dom
- redfin_quiet_score
- redfin_vibrancy_score
- zillow_seen
- zillow_url
- zillow_price
- zillow_status
- zillow_displayed_dom
- realtor_seen
- realtor_url
- realtor_price
- realtor_status
- realtor_displayed_dom
- homes_seen
- homes_url
- homes_price
- homes_status
- homes_displayed_dom
- compass_seen
- compass_url
- compass_price
- compass_status
- compass_displayed_dom
- price_discrepancy_flag
- status_discrepancy_flag
- dom_discrepancy_flag
- gas_evidence_cross_site
- garage_spaces_cross_site
- cross_site_confidence_score
- notes

Save output by default to:

```text
data/exports/cross_site_report_YYYYMMDD_HHMMSS.csv
```

## 9. Cross-site discrepancy flags

Implement simple deterministic flags:

### price_discrepancy_flag

True if at least two sources report materially different prices.

Suggested threshold:

- Difference >= $10,000

### status_discrepancy_flag

True if sources disagree on status categories such as active, pending, sold, removed, off_market, unknown.

### dom_discrepancy_flag

True if displayed DOM differs by >= 30 days across available sources.

### cross_site_confidence_score

Simple 0-100 score based on:

- Redfin present
- At least one cross-site source present
- Address matches
- Price matches within threshold
- Status matches
- Gas/garage evidence agrees or is non-conflicting

## 10. Tests

Add or update tests for:

- Cross-site source validation.
- URL/domain validation.
- URL normalization.
- CSV import of cross-site URLs.
- Invalid source_site rejection.
- Matching by candidate_id.
- Matching by property_id.
- Matching by normalized address fallback.
- Saved Zillow fixture parsing.
- Saved Realtor fixture parsing.
- Saved Homes fixture parsing.
- Saved Compass fixture parsing.
- Gas detection from cross-site fixtures.
- Walkability-type fields ignored.
- Cross-site observation insert/deduplication.
- Cross-site report generation.
- Price discrepancy flag.
- Status discrepancy flag.
- DOM discrepancy flag.
- Cross-site confidence score.
- CLI import/parse/export commands where practical.

All tests must pass.

## 11. Documentation

Update README.md with:

- Milestone 6 status.
- How to create data/imports/cross_site_urls.csv.
- How to import cross-site URLs.
- How to save cross-site detail fixtures.
- How to parse cross-site fixtures.
- How to export the cross-site report.
- Clear statement that Milestone 6 performs no live scraping or network access.

Add design decision note:

```text
docs/decisions/005-cross-site-enrichment-foundation.md
```

Explain:

- Why cross-site enrichment starts with manual URLs and saved fixtures.
- Why Redfin remains primary for now.
- Why County Recorder/Assessor verification is deferred.
- What discrepancy flags mean and do not mean.
- That review/reporting is not a purchase recommendation.

## 12. Code standards

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

Quality gates:

- Project imports cleanly.
- CLI commands run.
- SQLite init still works.
- Existing review queue workflow still works.
- Manual Redfin URL import still works.
- Saved Redfin search fixture parsing still works.
- Saved Redfin detail fixture parsing/enrichment still works.
- Effective DOM v1 calculations still work.
- Candidate analysis report still exports.
- Cross-site URL import works.
- Cross-site saved fixture parsing works.
- Cross-site report exports.
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
9. Example CLI workflow used to verify Milestone 6.
10. Counts from cross-site URL import.
11. Counts from saved fixture parsing by source.
12. Counts from cross-site observations inserted.
13. Cross-site report output path and row count.
14. Example discrepancy flags from verification.
15. Confirmation that walkability-type fields are ignored.
16. Confirmation that no live network calls, scraping, Playwright, Selenium, or browser automation were added.
17. Recommended next implementation step.
18. Git commit hash after committing and pushing completed changes to origin/main.

Important:

After all quality gates pass, commit and push the completed story changes to origin/main and include the commit hash in your completion report.
