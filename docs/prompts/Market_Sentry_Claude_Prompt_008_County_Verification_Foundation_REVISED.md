# Claude Code Prompt 008 - County Recorder and Assessor Verification Foundation

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
- Milestone 6 cross-site enrichment foundation stabilized and accepted at commit 01b6887
- Milestone 7 watchlist monitoring snapshots and change detection complete at commit 23ac2b5

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Review the current codebase and Milestone 7 implementation.
4. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
5. Keep PRD.md and Architecture.md in the project root.
6. Use src/marketsentry/ as the Python package path.
7. Do not move PRD.md or Architecture.md into docs/.
8. Do not implement live scraping, browser automation, Playwright, Selenium, or active network retrieval in this milestone.
9. Do not create any automated county website access in this milestone.

Important PM direction:

Milestone 8 should implement County Recorder and Assessor verification foundation using saved/static fixtures and manual CSV imports only.

Do not implement live Riverside County Recorder/Assessor retrieval.

The goal is to add official/public-record-style verification data to support:

- APN confirmation
- ownership transfer detection
- recorded sale/deed event detection
- county-verified Effective DOM reset logic
- discrepancy flags between listing-site sold events and county-record transfer events

Additional PM clarification on churn:

Do not discard or ignore listing churn when county records confirm an ownership transfer.

County-confirmed ownership transfer may reset Effective DOM for the current ownership cycle, but churn must remain available as a separate analytical factor.

Implement and preserve the distinction between:

1. Effective DOM:
   Current ownership-cycle market exposure, reset by confirmed ownership transfer.

2. Churn Index:
   Recent 2-3 year property/listing instability signal, not automatically erased by ownership transfer.

The Churn Index should remain reportable even when Effective DOM is reset. It may later prove useful or not useful, but it must be preserved for evaluation.

Use neutral language. Churn may indicate uncertain sellers, property issues, pricing resistance, rental/sale alternation, failed listing cycles, or other market behavior, but do not infer intent.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It starts with Redfin candidate discovery, stages homes for human review, and then monitors user-selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, cross-site validation, county sale/ownership-transfer verification, and a separate recent Churn Index.

Critical domain rules:

1. Effective DOM measures property-level market exposure across listing, removal, and relisting events within a defined lookback window, excluding periods reset by confirmed ownership transfer.
2. Confirmed ownership transfer means a county-recorded sale/deed/transfer event that supports resetting the Effective DOM cycle.
3. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
4. Churn Index measures recent 2-3 year property/listing instability and remains reportable even when Effective DOM is reset.
5. Quiet Score is the gatekeeper. Reject or heavily downgrade if Quiet Score is below threshold, even when Vibrancy is low.
6. Target is very high Quiet and very low Vibrancy.
7. Low Vibrancy alone is not sufficient.
8. Any mention of gas means the property has natural gas service/supply.
9. Walkability-type information is excluded from the initial scope.
10. Use neutral language. Do not infer seller intent.
11. The workflow is human-in-the-loop: candidate review queue first, then user-selected watched properties.
12. County data verifies resets; it should not automatically make purchase recommendations.

Your task for Prompt 008:

Implement County Recorder and Assessor Verification Foundation v0.

This milestone must allow Market_Sentry to import county-record observations from manual CSVs and saved/static HTML fixtures, match them to candidates or watched properties by APN/address, store county events, and produce a county verification report.

No live network calls.

## 1. County source scope

Supported county source types for this milestone:

- assessor
- recorder
- tax_collector
- permit

Primary target county context:

- Riverside County, California

Do not hard-code only Riverside County in a way that prevents future county adapters, but optimize initial labels and examples for Riverside County.

## 2. Manual county record CSV import

Implement CSV import for manually supplied county records.

Input file:

```text
data/imports/county_records.csv
```

Required columns:

- source_type
- record_date
- record_type

At least one identity field is required:

- apn
- address
- candidate_id
- property_id

Optional columns:

- city
- zip
- document_number
- document_title
- grantor
- grantee
- sale_price
- transfer_tax
- assessed_value
- owner_name
- permit_number
- permit_type
- permit_status
- notes
- source_url

Behavior:

- Validate source_type against supported values.
- Normalize APN where present.
- Normalize address where present.
- Parse record_date safely.
- Parse sale_price/assessed_value/transfer_tax safely.
- Match to candidate_review_queue or watched_properties by:
  1. property_id
  2. candidate_id
  3. APN
  4. normalized address fallback
- Insert county record observations/events.
- Do not overwrite user_decision, user_notes, active_watch_status, or watch_priority.
- Preserve unmatched county records if practical, or report them clearly if skipped.
- Preserve source_url and notes where available.

Add CLI command:

```text
marketsentry import-county-records --file data/imports/county_records.csv
```

## 3. County record data model

Create typed models for:

- CountyRecordImportRow
- CountyRecordObservation
- CountyRecordImportResult
- CountyTransferEvent
- CountyVerificationResult
- CountyVerificationReportRow

Fields to support where available:

- county_record_id
- candidate_id
- property_id
- source_type
- county_name
- source_url
- record_date
- record_type
- normalized_record_type
- document_number
- document_title
- apn
- normalized_apn
- address
- normalized_address
- city
- state
- zip
- grantor
- grantee
- sale_price
- transfer_tax
- assessed_value
- owner_name
- permit_number
- permit_type
- permit_status
- match_method
- confidence
- notes
- created_at

## 4. Database support

Add non-destructive schema support for county records.

Preferred table names:

```text
county_record_observations
county_verification_results
```

Minimum required table:

```text
county_record_observations
```

Required behavior:

- Fresh database init creates county_record_observations.
- Existing databases from MVP 7 can be upgraded without destructive changes.
- Index creation is idempotent.
- Add useful indexes:
  - property_id
  - candidate_id
  - normalized_apn
  - normalized_address
  - record_date
  - normalized_record_type
  - document_number
- No existing workflows break.

## 5. Saved county HTML fixture parsing

Implement parser foundation using saved/static county-like HTML fixtures.

Input directories:

```text
data/raw/county/assessor/
data/raw/county/recorder/
data/raw/county/tax_collector/
data/raw/county/permits/
```

Test fixtures:

```text
tests/fixtures/county/assessor/
tests/fixtures/county/recorder/
tests/fixtures/county/tax_collector/
tests/fixtures/county/permits/
```

At minimum include minimal/synthetic fixtures for:

1. Assessor property page with APN, address, assessed value, owner name.
2. Recorder document search result with deed/transfer/sale-style event.
3. Recorder result with no transfer found.
4. Tax collector page with APN/address/tax status.
5. Permit page with permit number/type/status.
6. Sparse/missing-field fixture that should parse without failing.

All fixtures must be static and minimal. They must not require network access.

## 6. County parser implementation

Create or update:

```text
src/marketsentry/county_parser.py
```

Required functions:

- parse_county_record_html(html: str, source_type: str, source_url: str | None = None) -> CountyRecordParseResult
- parse_county_record_file(file_path: Path, source_type: str) -> CountyRecordParseResult
- parse_county_record_directory(directory: Path, source_type: str) -> list[CountyRecordParseResult]

If CountyRecordParseResult is not in the model list above, add it.

Parser requirements:

- No network calls.
- No browser automation.
- Resilient to missing fields.
- Extract APN, address, record dates, record types, document numbers, assessed/sale values where feasible.
- Preserve parse warnings and raw snippets where useful.
- Do not treat owner/grantor/grantee names as necessary for matching if APN/address are available.
- Do not infer motive or seller intent.
- Do not store unnecessary sensitive personal data beyond fields needed for public-record verification; if grantor/grantee/owner fields are parsed, keep them optional and do not display them in default reports unless necessary.

## 7. Transfer/ownership verification logic

Create or update:

```text
src/marketsentry/county_verification.py
```

Required functions:

- normalize_county_record_type(record_type: str) -> str
- is_ownership_transfer_record(record_type: str, document_title: str | None = None) -> bool
- is_sale_or_deed_record(record_type: str, document_title: str | None = None) -> bool
- find_confirmed_transfers(property_id: int, db_path: Path | str | None = None) -> list[CountyTransferEvent]
- verify_effective_dom_reset(property_id: int, cycle_start: date, cycle_end: date, db_path: Path | str | None = None) -> CountyVerificationResult

Supported normalized record types:

- grant_deed
- quitclaim_deed
- trustee_deed
- warranty_deed
- deed_of_trust
- reconveyance
- lien
- tax_record
- assessment
- permit
- unknown

Ownership-transfer-like records:

- grant_deed
- quitclaim_deed
- trustee_deed
- warranty_deed

Not ownership-transfer reset records by default:

- deed_of_trust
- reconveyance
- lien
- assessment
- permit
- tax_record
- unknown

Important:
- Deed of trust is not the same as an ownership transfer.
- Reconveyance is not the same as a sale/ownership transfer.
- Liens are not sale resets.
- Permits are not sale resets.
- Use conservative logic.

## 8. County-verified Effective DOM reset foundation

Do not rewrite the full Effective DOM engine yet.

Add a foundation function that can be used by Effective DOM v2 later:

- Given a property_id and a date range, return whether a confirmed county ownership transfer exists inside that range.
- Return supporting record ids and dates.
- Return confidence.
- Return notes.

Add report-only flags for now:

- county_transfer_found
- county_transfer_date
- county_transfer_record_type
- county_transfer_confidence
- county_reset_supported

Do not automatically overwrite existing Effective DOM calculations in this milestone unless explicitly recomputing a report.

Also add report-only churn fields so churn remains visible even when county_reset_supported is true:

- recent_churn_index
- recent_churn_lookback_years
- recent_churn_event_count
- recent_dom_reset_count
- recent_sale_rent_alternation_count
- churn_preserved_after_transfer

For this milestone, recent_churn_index can be a simple deterministic placeholder score based on existing listing_churn_count, dom_reset_count, and sale_rent_alternation_count over a default 3-year lookback when event dates are available. If the current event model is insufficient for a date-filtered 3-year calculation, compute the fields from available current metrics and document that date-bounded Churn Index v1 is deferred to a later milestone.

Required behavior:
- county_reset_supported may support resetting Effective DOM.
- county_reset_supported must not zero out recent_churn_index.
- county_reset_supported must not erase listing_churn_count or related churn fields.
- Reports must preserve both reset-support and churn signals side-by-side.

## 9. County verification report

Create report module or extend existing reports.

CLI command:

```text
marketsentry export-county-verification-report
```

Required report columns:

- property_id
- candidate_id
- address
- city
- zip
- apn
- redfin_url
- current_price
- effective_dom
- displayed_dom
- listing_churn_count
- dom_reset_count
- sale_rent_alternation_count
- recent_churn_index
- recent_churn_lookback_years
- recent_churn_event_count
- recent_dom_reset_count
- recent_sale_rent_alternation_count
- churn_preserved_after_transfer
- county_records_seen
- county_transfer_found
- county_transfer_date
- county_transfer_record_type
- county_transfer_document_number
- county_transfer_confidence
- county_reset_supported
- assessor_seen
- recorder_seen
- tax_collector_seen
- permit_seen
- assessed_value
- latest_permit_type
- latest_permit_status
- verification_notes
- user_notes

Save output by default to:

```text
data/exports/county_verification_YYYYMMDD_HHMMSS.csv
```

## 10. CLI commands

Add or complete:

```text
marketsentry import-county-records --file data/imports/county_records.csv
marketsentry parse-county-fixtures --source assessor --dir data/raw/county/assessor
marketsentry parse-county-fixtures --source recorder --dir data/raw/county/recorder
marketsentry parse-county-fixtures --source tax_collector --dir data/raw/county/tax_collector
marketsentry parse-county-fixtures --source permit --dir data/raw/county/permits
marketsentry verify-county-records
marketsentry export-county-verification-report
```

Behavior:

### import-county-records

- Imports manual CSV county records.
- Prints rows read, inserted, matched, unmatched, rejected, warnings/errors.

### parse-county-fixtures

- Parses saved county fixtures.
- Stores county_record_observations.
- Prints files processed, observations parsed, inserted, matched, unmatched, warnings/errors.

### verify-county-records

- Evaluates watched properties for county transfer records.
- Prints properties scanned, transfers found, reset-supported cases, churn fields preserved, warnings/errors.

### export-county-verification-report

- Exports CSV report.
- Prints output path and row count.

CLI output must be ASCII-safe.

## 11. Tests

Add or update tests for:

- APN normalization.
- County source_type validation.
- County record CSV import.
- Date parsing.
- Sale price/assessed value parsing.
- Matching by property_id.
- Matching by candidate_id.
- Matching by APN.
- Matching by normalized address.
- Assessor fixture parsing.
- Recorder fixture parsing.
- Tax collector fixture parsing.
- Permit fixture parsing.
- Sparse county fixture handling.
- Record type normalization.
- Ownership transfer classification.
- Deed of trust not treated as transfer.
- Reconveyance not treated as transfer.
- Lien not treated as transfer.
- Permit not treated as transfer.
- Effective DOM reset verification foundation.
- Churn Index remains reportable when county transfer supports Effective DOM reset.
- County reset support does not zero listing_churn_count.
- County reset support does not erase dom_reset_count or sale_rent_alternation_count.
- County verification report includes Churn Index fields.
- County verification report columns.
- CLI import/parse/verify/export commands where practical.
- Existing MVP 1-7 tests still pass.

All tests must pass.

## 12. Documentation

Update README.md with:

- Milestone 8 status.
- How to create data/imports/county_records.csv.
- How to import county records.
- How to save county fixtures.
- How to parse county fixtures.
- How to run county verification.
- How to export county verification report.
- Explanation that county transfer records support Effective DOM reset validation.
- Explanation that not all county document types indicate ownership transfer.
- Explanation that county-confirmed transfers can reset Effective DOM but do not erase recent churn.
- Explanation that Churn Index remains a separate 2-3 year property/listing instability signal and may or may not prove useful over time.
- Clear statement that Milestone 8 performs no live county access, no scraping, and no network access.

Add design decision note:

```text
docs/decisions/007-county-verification-foundation.md
```

Explain:

- Why county verification is added after watchlist monitoring.
- Why only saved fixtures/manual CSVs are used.
- Which record types support ownership-transfer reset logic.
- Which record types do not.
- Why Effective DOM v2 full integration is deferred.
- Why churn is preserved separately from Effective DOM resets.
- Why county reports are verification aids, not purchase recommendations.

## 13. Code standards

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
- Be conservative when classifying ownership-transfer events.
- Preserve churn metrics separately from Effective DOM reset logic.

Quality gates:

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works for fresh database.
- Existing candidate review workflow still works.
- Existing Redfin import/fixture parsing/enrichment still works.
- Existing Effective DOM/scoring/reporting still works.
- Existing cross-site enrichment/reporting still works.
- Existing watchlist monitoring/reporting still works.
- County CSV import works.
- County fixture parsing works.
- County transfer verification works.
- County verification report exports.
- Churn Index remains reportable even when county_reset_supported is true.
- No live scraping or network calls implemented.
- Changes committed and pushed to origin/main.

Completion report required:

When finished, provide:

1. Summary of what you implemented.
2. Files created or modified.
3. Exact commands run.
4. Final test results with full pytest summary showing 100% pass.
5. Any dependency changes.
6. Any assumptions made.
7. Any blockers or risks remaining.
8. Any schema changes or migration fixes made.
9. Example CLI workflow used to verify Milestone 8.
10. Counts from county CSV import:
    - rows read
    - inserted
    - matched
    - unmatched
    - rejected
11. Counts from county fixture parsing by source:
    - assessor
    - recorder
    - tax_collector
    - permit
12. Counts from county verification:
    - properties scanned
    - county records seen
    - transfers found
    - reset-supported cases
13. County verification report output path and row count.
14. Example county verification summary for one property.
15. Example showing county_reset_supported true while recent_churn_index remains reportable.
16. Confirmation that non-transfer documents are not treated as Effective DOM reset records.
17. Confirmation that no live network calls, scraping, Playwright, Selenium, or browser automation were added.
18. Recommended next implementation step.
19. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 8 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
