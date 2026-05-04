# Claude Code Prompt 002 - Candidate Review Queue and Watchlist Promotion

You are Claude Code Opus 4.6 working in the Windsurf IDE as the dedicated development team for the Market_Sentry project.

Repository:

https://github.com/rogerfiske/Market_Sentry

Local project folder:

C:\Users\Minis\CascadeProjects\Market_Sentry

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Review the current scaffold from commit c8599761be1aeda80b075cf668c61970e587ebe7.
4. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
5. Keep PRD.md and Architecture.md in the project root.
6. Use src/marketsentry/ as the Python package path.
7. Do not implement live scraping or network calls in this milestone.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It begins with Redfin candidate discovery, stages candidates for user review, and later monitors selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, and cross-site/county validation.

Critical domain rules:

1. Effective DOM measures property-level market exposure across listing, removal, and relisting events within a defined lookback window, excluding periods reset by confirmed ownership transfer.
2. Quiet Score is the gatekeeper. Reject or heavily downgrade if Quiet Score is below threshold, even when Vibrancy is low.
3. Target is very high Quiet and very low Vibrancy.
4. Low Vibrancy alone is not sufficient.
5. Any mention of gas means the property has natural gas service/supply.
6. Walkability-type information is excluded from the initial scope.
7. Use neutral language. Do not infer seller intent.
8. The workflow is human-in-the-loop: candidate review queue first, then user-selected watched properties.

Your task for Prompt 002:

Implement the Candidate Review Queue workflow and Watchlist Promotion workflow.

This milestone should make the non-scraping, human-in-the-loop review process fully usable.

Required deliverables:

## 1. Candidate data insertion

Add functionality to insert candidate properties into candidate_review_queue.

Required behavior:

- Insert one candidate property.
- Insert multiple candidate properties.
- Deduplicate by Redfin URL and/or normalized address where practical.
- Preserve existing rows when duplicate candidates are inserted.
- Update selected mutable fields only when appropriate and documented.
- Store discovery_date and created_at/updated_at timestamps.

Candidate fields should include, where available:

- source_site
- source_search_url
- redfin_url
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
- effective_dom_estimate
- listing_churn_count
- dom_reset_count
- sale_rent_alternation_count
- review_status
- user_decision
- user_notes

## 2. Manual seed-data support

Create a small sample/manual seed mechanism for testing the review workflow without scraping.

Accept seed data from either:

- A CSV file in data/imports/
- A Python fixture/helper
- A CLI command that writes sample candidates

At minimum, include 3 sample candidates:

1. A strong Quiet/Vibrancy match.
2. A low-Quiet fail case.
3. A Maybe/review-needed case with missing Quiet/Vibrancy.

Use clearly fake/sample data or clearly labeled example records. Do not perform live website access.

## 3. Review export workflow

Implement or complete review_export.py.

Required behavior:

- Export candidate_review_queue to CSV.
- Prefer CSV for this milestone.
- Excel export is optional only if dependencies are already in place.
- Include a user-editable decision column.
- Include user_notes.
- Include enough property fields to support manual review.

Required export columns:

- candidate_id
- user_decision
- user_notes
- review_status
- address
- city
- zip
- price
- beds
- baths
- sqft
- lot_size
- displayed_dom
- effective_dom_estimate
- effective_dom_delta if available
- quiet_score
- vibrancy_score
- quiet_gatekeeper_result
- garage_spaces
- gas_service
- gas_evidence
- listing_churn_count
- dom_reset_count
- sale_rent_alternation_count
- redfin_url
- source_site
- source_search_url

Allowed user_decision values:

- save
- reject
- maybe
- hold_for_more_data

## 4. Review import workflow

Implement or complete review_import.py.

Required behavior:

- Read a reviewed CSV file.
- Validate user_decision values.
- Update candidate_review_queue with user_decision and user_notes.
- Normalize blank decisions safely.
- Preserve rejected and maybe records in candidate_review_queue.
- Promote only rows with user_decision = save into watched_properties.
- Avoid duplicate watched_properties rows when importing the same reviewed CSV multiple times.
- Record user review actions in user_review_actions if that table exists.

## 5. Watchlist promotion

Implement promotion from candidate_review_queue to watched_properties.

Required behavior:

- Create watched_properties row for each saved candidate.
- Preserve original observed values.
- Set first_saved_date.
- Set active_watch_status = active.
- Set watch_priority based on simple initial rules:
  - high if Quiet passes strongly and Effective DOM/listing churn suggests leverage.
  - medium for normal saved candidates.
  - low if missing important data.
- Preserve user_notes.
- Preserve Redfin URL.
- Preserve gas_service/gas_evidence.
- Preserve Quiet/Vibrancy scores.
- Do not promote rejected or maybe candidates.

## 6. CLI commands

Add or complete CLI commands for:

```text
marketsentry seed-sample-candidates
marketsentry export-review
marketsentry import-review --file data/imports/reviewed_candidates.csv
marketsentry list-candidates
marketsentry list-watched
```

CLI behavior:

- Commands should have helpful descriptions.
- Commands should print clear ASCII-safe output.
- Commands should return nonzero or show a clear error message on invalid input.
- Commands should use configured database path.

## 7. Tests

Add or update tests for:

- Candidate insertion.
- Candidate deduplication.
- Review CSV export.
- Review CSV import.
- Decision validation.
- Promotion of save rows to watched_properties.
- Non-promotion of reject/maybe rows.
- Idempotent repeated import.
- CLI command behavior where practical.
- Gas-service and Quiet/Vibrancy preservation during promotion.

All tests must pass.

## 8. Documentation

Update README.md with:

- Milestone 2 status.
- How to seed sample candidates.
- How to export the review queue.
- How to edit the CSV decisions.
- How to import reviewed candidates.
- How to list watched properties.

Add a short note to docs/decisions/ explaining the human-in-the-loop review queue design.

## 9. Code standards

- Python 3.11+
- PEP8 compliant.
- Type hints required.
- Docstrings required for all functions.
- Remove unused imports.
- Keep modules small and readable.
- No live scraping.
- No network calls.
- No bypassing bot protections.
- Preserve source URLs and timestamps for future auditability.

Quality gates:

- Project imports cleanly.
- CLI commands run.
- SQLite init still works.
- Candidate seed/export/import workflow works locally.
- Unit tests pass.
- No scraping or network calls implemented.
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
9. Example CLI workflow used to verify Milestone 2.
10. Recommended next implementation step.
11. Git commit hash after committing and pushing completed changes to origin/main.

Important:

After all quality gates pass, commit and push the completed story changes to origin/main and include the commit hash in your completion report.
