# Decision 021: Cross-Site Adapter Parity and Manual Fixtures

## Date

2026-05-08

## Status

Accepted

## Context

Milestones 14-21 built a complete retrieval operations ecosystem for Redfin: compliance adapters, safety enforcement, fixture capture queue, live HTTP retrieval, fixture processing pipeline, batch orchestration, approval workflow, dashboard, and health checks.

Non-Redfin cross-site sources (Zillow, Realtor.com, Homes.com, Compass) had stub adapters from Milestone 14 but lacked the same operational parity: no dry-run preview, no fixture capture queue integration, no processing manifest, no dashboard/health visibility.

Milestone 6 implemented cross-site fixture parsing and enrichment, but the workflow for managing, processing, and tracking cross-site fixtures was not operationally complete.

## Decision

### Cross-site sources get manual fixture parity before live retrieval

Each non-Redfin source adapter now provides:

- URL validation and domain checking
- Request type inference (property_detail, search, unknown)
- Dry-run preview with fixture capture queue integration
- Retrieval audit logging with `network_call_performed=false`
- Structured `RetrievalResult` responses
- Live retrieval methods that return blocked/not_implemented

This brings all sources to the same safe local workflow pattern without implementing live HTTP retrieval.

### Redfin remains the only live HTTP Phase 1 source

Live HTTP retrieval is complex and requires per-source compliance review. Redfin was the first source because it is the primary discovery source. Extending live retrieval to other sources would require:

- Per-source robots.txt review
- Per-source rate limit configuration
- Per-source URL pattern validation at live retrieval depth
- Additional compliance review

These are future milestones. The current milestone ensures all sources have a working manual fixture workflow.

### Search fixture support may be limited

Not all sources have well-defined search URL patterns. Search fixture parsing is not yet implemented for non-Redfin sources. Property detail fixtures are the primary cross-site enrichment mechanism.

### Cross-site data does not overwrite Redfin source-of-truth fields

Redfin is the primary discovery and source-of-truth source. Cross-site observations provide supplementary validation data. Cross-site processing:

- Does not overwrite `user_decision`, `user_notes`, `active_watch_status`, or `watch_priority`
- Does not replace Redfin-sourced property facts
- Inserts `cross_site_observations` for comparison and discrepancy detection
- Deduplicates observations using existing logic

## Consequences

### Positive

- All sources now have consistent dry-run and fixture capture workflow
- Operators can manage cross-site fixtures through the same queue system
- Dashboard and health checks cover cross-site processing status
- Processing manifest tracks what has been processed with content-hash deduplication
- Force-reprocess option available when needed

### Negative

- Search fixture support is limited for non-Redfin sources
- No live retrieval for cross-site sources in this milestone
- Parser quality depends on Milestone 6 implementations

## Related

- Milestone 6: Cross-site enrichment foundation
- Milestone 14: Live retrieval strategy and compliance adapters
- Milestone 15: Retrieval safety enforcement and fixture capture queue
- Milestone 16: Redfin Live HTTP Phase 1
