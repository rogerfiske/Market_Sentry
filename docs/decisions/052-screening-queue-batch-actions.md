# ADR 052: Screening Queue Batch Actions and Operator Refresh Integration

## Status

Accepted

## Context

Milestone 52 delivered the Redfin screening queue with single-item actions, and Milestone 52A stabilized database defaults and removed demo noise. Operating the queue then exposed the remaining friction: every decision required its own command or dashboard form submission.

For a non-programmer operator reviewing a page of Redfin links in one sitting, the one-at-a-time pattern is the dominant cost. The decisions are already made by the time the operator returns to the console; only recording them is slow.

A second gap was direction. After saving items for analysis, nothing told the operator what to do next. The required sequence (save detail HTML, run enrichment, capture Quiet/Vibrancy, record a decision, refresh reports) was documented but not surfaced where the work happens.

## Decision

Add batch actions and next-step guidance to the screening queue.

1. **Batch actions.** Four functions and matching CLI commands accept a comma-separated ID list: batch save for analysis, batch reject, batch hold, batch mark opened. Each item is processed independently and reports its own success or failure. A missing, invalid, or duplicate ID never prevents the remaining items from being actioned.

2. **ID parsing is explicit and lossless.** `parse_screening_id_list` returns valid IDs, invalid entries, and duplicates as three separate lists so the operator sees exactly what was ignored and why, rather than silently dropping input.

3. **Batch save reuses the single-item path.** `batch_save_screening_items_for_analysis` calls the existing `save_screening_item_for_analysis` per item rather than reimplementing insertion. Deduplication, candidate linking, note preservation, and source-of-truth protection therefore behave identically in single and batch mode by construction.

4. **Next-step guidance.** `build_screening_next_steps` derives an ordered list of required data-gathering actions from screening status and candidate state. It is surfaced through `screening-next-steps`, a dashboard panel, and the Markdown export. Steps describe data collection only and never recommend buying, offering on, or valuing a property.

5. **Optional refresh, defaulting to off.** Both single and batch Save for Analysis accept `--refresh/--no-refresh`, defaulting to `--no-refresh`. The refresh workflow regenerates every local report and is far slower than the save; making it opt-in keeps the common path fast. A refresh failure is reported but never rolls back saves that already succeeded.

6. **Export enrichment.** The screening export gains candidate enrichment, scoring, and watchlist status plus a per-item next step, reusing existing tables rather than adding an action-history schema.

## Alternatives considered

**Multi-select checkboxes in the dashboard.** Rejected for this milestone. Streamlit's rerun model makes per-row selection state fragile, and reliability matters more than interaction polish for the target operator. A comma-separated ID list is stable and works identically in the CLI and the dashboard.

**A dedicated batch action history table.** Rejected as premature. Notes, timestamps, and the existing review-action audit trail already record what happened, and a new table would need migration and cleanup support for little added value.

**Refresh on by default after save.** Rejected. It would make the fast, common action slow and surprising, and would couple a cheap state change to an expensive report regeneration.

## Consequences

- Operators can record several screening decisions in one command or one form submission.
- Partial failures are visible per item instead of aborting the batch.
- The system now tells the operator what to do next in the console, dashboard, and exports.
- Save for Analysis remains the single explicit transition point from screening to candidate; imports still never create candidates.
- Existing single-item commands, the candidate review queue, the watchlist, and scoring are unchanged.
- No new dependencies.
- No live retrieval, scraping, browser automation, outbound notifications, or credential handling is added.
- The Quiet Score gatekeeper remains at 7.0, and low Vibrancy still does not override a poor Quiet score.
- Walkability fields are not added.

## Notes

`redfin_screening_queue.py` module-level database defaults were switched from the literal `"db/marketsentry.db"` to `config.database_path`. The resolved value is identical, but the `DATABASE_PATH` environment override now works consistently in this module, matching the canonical pattern established in Milestone 52A.
