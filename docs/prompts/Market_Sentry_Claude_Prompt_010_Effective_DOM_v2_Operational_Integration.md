# Claude Code Prompt 010 - Effective DOM v2 Operational Integration

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
- Milestone 8 county recorder and assessor verification foundation complete at commit 89ce91a
- Milestone 9 Effective DOM v2 county-verified reset integration complete at commit 0e83285

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Review the current codebase and Milestone 9 implementation.
4. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
5. Keep PRD.md and Architecture.md in the project root.
6. Use src/marketsentry/ as the Python package path.
7. Do not move PRD.md or Architecture.md into docs/.
8. Do not implement live scraping, browser automation, Playwright, Selenium, or active network retrieval in this milestone.
9. Do not implement live County Recorder/Assessor access in this milestone.
10. Avoid inaccurate commit metadata. Do not add a Claude Sonnet co-authorship tag. If adding co-author metadata, it must accurately reflect Claude Code Opus 4.6, or omit the co-author line.

Important PM direction:

Milestone 10 should operationalize Effective DOM v2.

Milestone 9 implemented v2 as a report-only workflow. Milestone 10 should integrate v2 into the recurring watchlist monitoring and candidate review workflow so the user sees v2 and Churn Index in the normal operating reports.

Do not create live data retrieval.

Do not remove Effective DOM v1. Preserve v1/v2 comparison.

Do not erase churn metrics.

Project mission reminder:

Market_Sentry is a buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties. It starts with Redfin candidate discovery, stages homes for human review, and then monitors user-selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, cross-site validation, county sale/ownership-transfer verification, and a separate recent Churn Index.

Critical domain rules:

1. Effective DOM measures property-level market exposure across listing, removal, and relisting events within a defined lookback window, excluding periods reset by confirmed ownership transfer.
2. Effective DOM v1 is listing-history-derived exposure without county reset integration.
3. Effective DOM v2 applies county-confirmed ownership transfer as a reset boundary when appropriate.
4. Confirmed ownership transfer resets Effective DOM only; it does not erase recent churn history.
5. Churn Index measures recent 2-3 year property/listing instability and remains reportable even when Effective DOM is reset.
6. Quiet Score is the gatekeeper. Reject or heavily downgrade if Quiet Score is below threshold, even when Vibrancy is low.
7. Target is very high Quiet and very low Vibrancy.
8. Low Vibrancy alone is not sufficient.
9. Any mention of gas means the property has natural gas service/supply.
10. Walkability-type information is excluded from the initial scope.
11. Use neutral language. Do not infer seller intent.
12. The workflow is human-in-the-loop: candidate review queue first, then user-selected watched properties.
13. Reports are analytical aids, not purchase recommendations.

Your task for Prompt 010:

Implement Effective DOM v2 Operational Integration.

This milestone must add Effective DOM v2 and Churn Index values into:

- watched_properties where appropriate
- property_observation_snapshots
- watchlist monitoring reports
- candidate analysis reports
- scoring/review recommendations where appropriate
- CLI workflows

No live network calls.

## 1. Schema integration

Add non-destructive schema support for operational v2 fields.

Tables to consider:

```text
watched_properties
candidate_review_queue
property_observation_snapshots
```

Prefer explicit columns for core operational metrics:

- effective_dom_v1
- effective_dom_v2
- effective_dom_delta_v1
- effective_dom_delta_v2
- county_reset_applied
- county_reset_date
- county_reset_record_type
- county_reset_confidence
- recent_churn_index
- recent_churn_lookback_years
- recent_churn_event_count
- recent_dom_reset_count
- recent_sale_rent_alternation_count
- churn_preserved_after_transfer

If adding all fields to all tables is excessive, prioritize:

1. property_observation_snapshots
2. watched_properties
3. candidate_review_queue

Use safe migrations:

- column_exists checks
- ALTER TABLE ADD COLUMN only when missing
- idempotent migration
- no destructive changes
- no data loss

## 2. Recalculation persistence workflow

Enhance or create a workflow that persists v2 metrics.

Suggested module:

```text
src/marketsentry/effective_dom_v2_persistence.py
```

Required behavior:

- Read watched_properties.
- Read candidates where linked.
- Read listing_events.
- Read county_record_observations.
- Compute Effective DOM v2 metrics.
- Persist v2 fields to watched_properties and/or candidate_review_queue where schema supports it.
- Preserve user_decision and user_notes.
- Preserve active_watch_status and watch_priority.
- Do not delete or rewrite listing history.
- Do not zero churn metrics when county reset applies.
- Be idempotent.

CLI command:

```text
marketsentry persist-effective-dom-v2
```

Output:

- properties scanned
- candidates scanned
- v2 metrics computed
- records updated
- county resets applied
- churn metrics preserved
- warnings/errors

## 3. Watchlist monitoring integration

Update Milestone 7 snapshot creation to include Effective DOM v2 fields.

When `marketsentry snapshot-watchlist` runs, snapshots should include:

- effective_dom_v1
- effective_dom_v2
- effective_dom_delta_v1
- effective_dom_delta_v2
- county_reset_applied
- county_reset_date
- county_reset_record_type
- county_reset_confidence
- recent_churn_index
- recent_churn_lookback_years
- recent_churn_event_count
- recent_dom_reset_count
- recent_sale_rent_alternation_count
- churn_preserved_after_transfer

Change detection should detect:

- effective_dom_v2_changed
- recent_churn_index_changed
- county_reset_applied_changed

Do not treat churn change as bad intent. Use neutral wording.

## 4. Watchlist monitoring report integration

Update watchlist monitoring report to include v2 fields.

Required additional report columns:

- effective_dom_v1
- effective_dom_v2
- effective_dom_delta_v1
- effective_dom_delta_v2
- previous_effective_dom_v2
- effective_dom_v2_change
- county_reset_applied
- county_reset_date
- county_reset_record_type
- county_reset_confidence
- recent_churn_index
- previous_recent_churn_index
- recent_churn_index_change
- recent_churn_lookback_years
- recent_churn_event_count
- recent_dom_reset_count
- recent_sale_rent_alternation_count
- churn_preserved_after_transfer

Keep existing report columns.

## 5. Candidate analysis report integration

Update candidate analysis report to include v2 and Churn Index where available.

Required additional columns:

- effective_dom_v1
- effective_dom_v2
- effective_dom_delta_v1
- effective_dom_delta_v2
- county_reset_applied
- county_reset_date
- county_reset_record_type
- recent_churn_index
- recent_churn_lookback_years
- churn_preserved_after_transfer

## 6. Scoring integration

Enhance scoring carefully.

Current review recommendation should still respect Quiet Score as the gatekeeper.

Add v2-aware leverage factors:

Positive buyer-review signals may include:

- effective_dom_delta_v2 >= 90
- county_reset_applied true but recent_churn_index >= 5
- recent_churn_index >= 6
- dom_reset_count >= 1
- sale_rent_alternation_count >= 1
- price_change_count >= 1

Important:
- High Churn Index should not automatically reject a property.
- High Churn Index should add a review flag or leverage flag.
- Use neutral language:
  - "high_recent_churn"
  - "county_reset_with_preserved_churn"
  - "review_listing_history"
- Do not use words like spoofing, manipulation, fraud, deception, or bad actor.

Update scoring output with:

- churn_review_flag
- county_reset_with_churn_flag
- v2_leverage_flag

If changing model structures, keep backwards compatibility with existing tests where practical.

## 7. CLI commands

Add or update:

```text
marketsentry persist-effective-dom-v2
marketsentry snapshot-watchlist
marketsentry export-watchlist-monitoring-report
marketsentry export-analysis-report
marketsentry export-effective-dom-v2-report
```

All commands should remain ASCII-safe.

## 8. Tests

Add or update tests for:

- schema migration adds v2 fields safely
- migration is idempotent
- persist-effective-dom-v2 updates watched_properties
- persist-effective-dom-v2 preserves user_notes and active_watch_status
- county reset applied persists correctly
- Churn Index persists and is not zeroed by county reset
- snapshot-watchlist captures v2 fields
- snapshot change detection detects effective_dom_v2 changes
- snapshot change detection detects recent_churn_index changes
- monitoring report includes v2 fields
- candidate analysis report includes v2 fields
- scoring flags high recent churn neutrally
- scoring does not let churn override Quiet gatekeeper
- existing MVP 1-9 tests still pass

All tests must pass.

## 9. Documentation

Update README.md with:

- Milestone 10 status.
- Explanation that Effective DOM v2 is now operational, not only report-only.
- How to run persist-effective-dom-v2.
- How v2 appears in watchlist monitoring snapshots.
- How Churn Index appears in monitoring reports.
- Explanation that Churn Index is not erased by county reset.
- Explanation that high churn is a review signal, not a seller-intent accusation.
- Clear statement that Milestone 10 performs no live scraping or network access.

Add design decision note:

```text
docs/decisions/009-effective-dom-v2-operational-integration.md
```

Explain:

- Why v2 metrics are persisted after Milestone 9 report-only validation.
- Which tables receive v2 fields and why.
- Why v1 is preserved.
- Why Churn Index remains separate.
- Why churn is treated as a review/leverage signal, not a rejection or accusation.

## 10. Code standards

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
- Be conservative when applying county reset boundaries.
- Preserve churn metrics separately from Effective DOM reset logic.
- Use neutral language.

Quality gates:

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works for fresh database.
- Existing candidate review workflow still works.
- Existing Redfin import/fixture parsing/enrichment still works.
- Existing Effective DOM v1/scoring/reporting still works.
- Existing cross-site enrichment/reporting still works.
- Existing watchlist monitoring/reporting still works.
- Existing county import/fixture parsing/verification still works.
- Existing Effective DOM v2 report-only workflow still works.
- Effective DOM v2 persisted workflow works.
- Watchlist monitoring snapshots include v2 fields.
- Monitoring reports include v2 fields.
- Churn Index remains reportable even when county_reset_applied is true.
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
9. Example CLI workflow used to verify Milestone 10.
10. Counts from persist-effective-dom-v2:
    - watched properties scanned
    - candidates scanned
    - v2 metrics computed
    - records updated
    - county resets applied
    - churn metrics preserved
11. Example snapshot output showing v2 fields.
12. Watchlist monitoring report output path and row count.
13. Candidate analysis report output path and row count.
14. Example scoring output showing high churn as neutral review flag.
15. Example proving Quiet gatekeeper still overrides all other signals.
16. Confirmation that churn metrics are not zeroed or erased by county reset.
17. Confirmation that no live network calls, scraping, Playwright, Selenium, or browser automation were added.
18. Recommended next implementation step.
19. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 10 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
