# Claude Code Prompt 007 - Watchlist Monitoring Snapshots and Change Detection

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

Before starting implementation:

1. Read PRD.md.
2. Read Architecture.md.
3. Review the current codebase and Milestone 6 stabilization.
4. Confirm the repository URL is https://github.com/rogerfiske/Market_Sentry.
5. Keep PRD.md and Architecture.md in the project root.
6. Use src/marketsentry/ as the Python package path.
7. Do not move PRD.md or Architecture.md into docs/.
8. Do not implement live scraping, browser automation, Playwright, Selenium, or active network retrieval in this milestone.
9. Do not implement County Recorder/Assessor integration in this milestone.

Important PM direction:

Milestone 7 should implement watchlist monitoring snapshots and change detection before County Recorder integration.

Do not implement County Recorder/Assessor parsing yet.

The goal is to make watched properties useful over time by storing repeated observations and detecting changes in:

- price
- listing status
- displayed DOM
- Effective DOM
- Quiet/Vibrancy if changed or newly observed
- garage/gas evidence
- Redfin/cross-site source presence
- discrepancy flags
- listing churn indicators

This milestone still uses only existing database data, saved fixtures, and local CSV/report workflows. No live data collection.

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

Your task for Prompt 007:

Implement Watchlist Monitoring Snapshots and Change Detection v1.

This milestone must allow Market_Sentry to take a local “snapshot” of each watched property using the best current data already available in the database, store that snapshot in property_observation_snapshots, detect changes from the prior snapshot, and export monitoring reports.

No live network calls.

## 1. Snapshot data model

Use or enhance existing:

```text
property_observation_snapshots
```

If the existing schema is insufficient, prefer adding non-destructive columns or using JSON/text notes rather than destructive migrations.

Snapshot should capture where available:

- snapshot_id
- property_id
- snapshot_date
- source_site
- listing_status
- price
- displayed_dom
- effective_dom
- effective_dom_delta
- quiet_score
- vibrancy_score
- garage_spaces
- gas_service
- listing_churn_count
- dom_reset_count
- sale_rent_alternation_count
- price_change_count
- cross_site_confidence_score
- price_discrepancy_flag
- status_discrepancy_flag
- dom_discrepancy_flag
- listing_history_hash
- property_detail_hash
- raw_source_url
- notes

If the existing table does not include all fields, either:

1. Add a simple migration with documentation, or
2. Store extra computed values in notes as structured JSON.

Prefer explicit columns for core monitoring fields if practical.

## 2. Snapshot creation workflow

Create a new module, for example:

```text
src/marketsentry/monitoring.py
```

Required functions:

- create_snapshot_for_property(property_id: int, db_path: Path | str | None = None) -> MonitoringSnapshotResult
- create_snapshots_for_all_watched(db_path: Path | str | None = None) -> MonitoringRunResult
- get_latest_snapshot(property_id: int, db_path: Path | str | None = None) -> ObservationSnapshot | None
- compare_snapshots(previous: ObservationSnapshot | None, current: ObservationSnapshot) -> SnapshotChangeResult

Behavior:

- Read watched_properties.
- Read linked candidate_review_queue where applicable.
- Read listing_events.
- Read cross_site_observations.
- Recalculate current Effective DOM/scoring where practical.
- Store one new snapshot per active watched property per run unless idempotency rules say a same-day duplicate should be skipped.
- Do not overwrite watched property user_notes.
- Do not modify user_decision.
- Do not require live data.
- If a watched property lacks current data, create a snapshot with available fields and warnings.

## 3. Change detection

Detect and store/report changes from the previous snapshot.

Change types:

- price_changed
- price_increased
- price_decreased
- status_changed
- displayed_dom_changed
- effective_dom_changed
- quiet_score_changed
- vibrancy_score_changed
- garage_spaces_changed
- gas_service_changed
- discrepancy_flag_changed
- source_presence_changed
- no_material_change

Suggested thresholds:

- price_changed: any price difference
- significant_price_change: >= $10,000
- displayed_dom_changed: any difference
- effective_dom_changed: any difference
- quiet/vibrancy changed: >= 0.5 difference
- discrepancy_flag_changed: boolean change

Create or update listing_events if appropriate for changes such as price_changed/status_changed, but do not duplicate events already parsed from source history.

## 4. Monitoring reports

Create report functions and CLI command to export:

```text
data/exports/watchlist_monitoring_YYYYMMDD_HHMMSS.csv
```

Required report columns:

- property_id
- watch_priority
- active_watch_status
- address
- city
- zip
- redfin_url
- current_price
- previous_price
- price_change
- price_change_direction
- listing_status
- previous_listing_status
- status_changed
- displayed_dom
- previous_displayed_dom
- effective_dom
- previous_effective_dom
- effective_dom_delta
- quiet_score
- vibrancy_score
- quiet_gatekeeper_result
- garage_spaces
- gas_service
- listing_churn_count
- dom_reset_count
- sale_rent_alternation_count
- price_discrepancy_flag
- status_discrepancy_flag
- dom_discrepancy_flag
- cross_site_confidence_score
- change_summary
- warning_flags
- positive_flags
- user_notes
- last_checked_date
- snapshot_date

The report is a watchlist monitoring report, not a purchase recommendation.

## 5. CLI commands

Add or complete:

```text
marketsentry snapshot-watchlist
marketsentry list-snapshots
marketsentry export-watchlist-monitoring-report
```

Behavior:

### snapshot-watchlist

- Creates snapshots for active watched properties.
- Prints:
  - watched properties scanned
  - snapshots created
  - snapshots skipped
  - changes detected
  - warnings/errors

### list-snapshots

- Lists recent snapshots, optionally filtered by property_id.
- Include basic columns:
  - snapshot_id
  - property_id
  - snapshot_date
  - price
  - effective_dom
  - listing_status
  - notes/change summary

### export-watchlist-monitoring-report

- Exports monitoring report CSV.
- Prints output path and row count.

CLI output must be ASCII-safe.

## 6. Idempotency and duplicate handling

Define and implement one clear rule:

Recommended rule:

- Allow one snapshot per property per run timestamp.
- If a user runs snapshot-watchlist twice on the same day, create a second snapshot only if material fields changed; otherwise skip and report as duplicate/no material change.

Alternative acceptable rule:

- Always create append-only snapshots and report duplicate/no-material-change.

Choose one, document it, and test it.

## 7. Watch status updates

Do not automatically mark properties sold/removed based only on cross-site disagreement.

But allow status signals in snapshots and reports:

- active
- pending
- sold
- removed
- off_market
- unknown

Watched property active_watch_status should remain under user/system review unless an explicit rule is implemented and documented.

## 8. Tests

Add or update tests for:

- Snapshot creation for one watched property.
- Snapshot creation for all watched properties.
- Snapshot creation when data is sparse.
- Latest snapshot retrieval.
- Price change detection.
- Status change detection.
- Effective DOM change detection.
- Quiet/Vibrancy change detection.
- Discrepancy flag change detection.
- No-material-change behavior.
- Idempotency/duplicate handling.
- Monitoring report CSV columns.
- Monitoring report row count.
- CLI snapshot/list/export commands where practical.
- Existing MVP 1-6 tests still pass.

All tests must pass.

## 9. Documentation

Update README.md with:

- Milestone 7 status.
- How to run snapshot-watchlist.
- How to list snapshots.
- How to export watchlist monitoring report.
- Explanation of change detection.
- Explanation that reports are for watchlist monitoring, not purchase recommendations.
- Clear statement that Milestone 7 performs no live scraping or network access.
- Clear statement that County Recorder/Assessor verification remains deferred.

Add design decision note:

```text
docs/decisions/006-watchlist-monitoring-snapshots.md
```

Explain:

- Why watchlist monitoring precedes county verification.
- How snapshots are created.
- How duplicate/no-material-change runs are handled.
- How change detection is interpreted.
- Why watched property status is not automatically changed based only on cross-site disagreement.

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

Quality gates:

- Full pytest suite passes 100%.
- Project imports cleanly.
- CLI commands run.
- SQLite init works.
- Existing candidate review workflow still works.
- Existing Redfin URL import and fixture parsing still work.
- Existing Redfin detail enrichment still works.
- Existing Effective DOM/scoring/reporting still work.
- Existing cross-site enrichment/reporting still works.
- Snapshot creation works.
- Change detection works.
- Watchlist monitoring report exports.
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
9. Example CLI workflow used to verify Milestone 7.
10. Counts from snapshot-watchlist verification:
    - watched properties scanned
    - snapshots created
    - snapshots skipped
    - changes detected
11. Monitoring report output path and row count.
12. Example change summary for one property.
13. Explanation of duplicate/no-material-change handling.
14. Confirmation that watched property status is not automatically changed based only on cross-site disagreement.
15. Confirmation that no live network calls, scraping, Playwright, Selenium, or browser automation were added.
16. Recommended next implementation step.
17. Git commit hash after committing and pushing completed changes to origin/main.

Important:

Do not mark Milestone 7 complete until all tests pass.

After all quality gates pass, commit and push completed changes to origin/main and include the commit hash in your completion report.
