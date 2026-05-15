# ADR 051: Redfin Screening Queue

## Status

Accepted

## Context

After Milestone 51A stabilized the operator workflow, the next usability gap was the initial screening stage. The user needs a dashboard-based queue for initial property screening with clickable Redfin links and a "Save for Analysis" action, rather than relying on CSV-heavy command-line workflows for property triage.

The desired workflow is:

```
screening list -> clickable Redfin links -> Save for Analysis -> candidate added -> dashboard/reports updated
```

## Decision

Implement a local pre-candidate screening queue (`redfin_screening_queue` table) that:

1. Accepts property imports from CSV files and saved Redfin search HTML fixtures.
2. Provides clickable Redfin URL links in dashboard and Markdown exports.
3. Supports explicit operator actions: Save for Analysis, Reject, Hold, Mark Opened.
4. Creates candidates in candidate_review_queue only via explicit "Save for Analysis" action.
5. Deduplicates by normalized Redfin URL at both import and save-for-analysis stages.
6. Does not perform live retrieval, browser automation, or outbound notifications.

The screening queue is a separate stage before the candidate review queue. Properties must be explicitly promoted.

## Consequences

- Operators can triage Redfin properties from a dashboard instead of editing CSV files.
- Properties enter the candidate pipeline only through explicit operator action.
- The existing candidate review queue, watchlist, and scoring systems remain unchanged.
- No new dependencies are introduced.
- No live retrieval or scraping is added.
- The Quiet Score gatekeeper is not modified.
- Walkability fields are not added.
