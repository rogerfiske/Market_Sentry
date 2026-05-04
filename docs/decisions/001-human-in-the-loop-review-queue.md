# ADR 001: Human-in-the-Loop Review Queue Design

**Date:** 2026-05-04
**Status:** Accepted
**Decision Makers:** Market_Sentry Development Team

## Context

Market_Sentry is designed to help buyers observe the Temecula/Murrieta real estate market over an extended period (approximately 12 months). The system discovers candidate properties and monitors selected properties for market exposure patterns.

A key architectural decision is whether to:

1. Automatically add all discovered properties to the active watchlist
2. Stage discovered properties in a review queue for human approval before watchlist promotion

## Decision

**We will implement a human-in-the-loop review queue workflow.**

All discovered candidate properties are staged in a `candidate_review_queue` table. The user reviews candidates via CSV export/import and manually decides which properties to promote to the `watched_properties` table.

## Rationale

### Why Human Review is Essential

1. **Disciplined Observation Over Automation**
   - The user's objective is disciplined market observation over 12 months, not automated purchasing decisions
   - Automatic watchlist population could lead to information overload and reduced focus
   - Manual review ensures the user actively engages with each candidate

2. **Quality Over Quantity**
   - Not all properties meeting basic filters are worth long-term monitoring
   - Human judgment can evaluate factors beyond algorithmic scoring
   - The user can apply subjective criteria (neighborhood feel, specific location preferences, visual appeal from photos)

3. **Data Quality Awareness**
   - Some candidates may have incomplete data (missing Quiet/Vibrancy scores, unclear gas service)
   - Human review allows the user to mark properties as "needs more review" or "hold for more data"
   - The user can decide whether to investigate further or reject based on incomplete information

4. **Resource Efficiency**
   - Cross-site enrichment (Zillow, Realtor.com, county records) is resource-intensive
   - Only user-approved properties move to the watchlist where monitoring and enrichment occur
   - This prevents wasting resources on properties the user has no interest in

5. **User Control and Trust**
   - The user maintains full control over what enters the watchlist
   - No "black box" automatic decisions
   - The user can see exactly what was discovered and why certain properties were or weren't promoted

## Implementation

### Workflow Steps

1. **Discovery → Review Queue**
   - Candidates discovered from Redfin are inserted into `candidate_review_queue`
   - Deduplication occurs by Redfin URL and normalized address
   - All candidates start with `review_status = 'pending'`

2. **Export for Review**
   - User runs `marketsentry export-review`
   - Candidates are exported to CSV with all scoring and property data
   - CSV includes `user_decision` and `user_notes` columns for user input

3. **User Review**
   - User opens CSV in Excel or any spreadsheet application
   - User sets `user_decision` for each candidate:
     - `save` - Promote to watchlist
     - `reject` - Not interested
     - `maybe` - Undecided, keep in review queue
     - `hold_for_more_data` - Need more information before deciding
   - User can add notes explaining their decision

4. **Import Decisions**
   - User runs `marketsentry import-review --file <path>`
   - System validates decisions
   - Properties marked `save` are promoted to `watched_properties`
   - Properties marked `reject`, `maybe`, or `hold_for_more_data` remain in review queue

5. **Watchlist Monitoring**
   - Only promoted properties are actively monitored
   - Cross-site enrichment and county verification apply only to watchlist properties
   - Observation snapshots are recorded for watchlist properties

### Database Design

```
candidate_review_queue
- Staging table for all discovered candidates
- Preserved indefinitely for historical reference
- User can re-review rejected candidates if needed

watched_properties
- Long-term monitoring table
- Only contains user-approved properties
- Enriched with cross-site data and county verification
```

### Decision Validation

Valid `user_decision` values:
- `save` - Promote to watchlist (most important)
- `reject` - Explicitly not interested
- `maybe` - Undecided, leave in review queue
- `hold_for_more_data` - Waiting for more information

Invalid decisions are logged and skipped during import.

### Idempotency

- Importing the same reviewed CSV multiple times is safe
- Promotion to watchlist checks for existing entries by normalized address
- No duplicate watched properties are created

## Consequences

### Positive

- **User maintains full control** over what is monitored
- **Reduces noise** by focusing monitoring resources on user-selected properties
- **Enables thoughtful decision-making** rather than automated bulk processing
- **Preserves rejected candidates** for potential future reconsideration
- **CSV export/import is simple** and works with familiar tools (Excel, Google Sheets)
- **Supports iterative review** - user can mark "maybe" and come back later

### Negative

- **Requires manual effort** - user must review each batch of candidates
- **Not real-time** - there is a delay between discovery and watchlist promotion
- **User must remember to check** for new candidates periodically

### Mitigations

- Sample seed data allows testing the workflow without live scraping
- CSV export is fast and includes all relevant data for decision-making
- Quiet/Vibrancy gatekeeper pre-filters obviously unsuitable properties
- Export includes scoring to help prioritize review (sort by Quiet score, DOM delta, etc.)

## Alternatives Considered

### Alternative 1: Automatic Watchlist Population

**Rejected because:**
- Violates the "disciplined observation" goal
- Would require very aggressive filtering to avoid overload
- Removes user agency and control
- Could lead to monitoring hundreds of properties unnecessarily

### Alternative 2: Web UI for Review

**Rejected for MVP because:**
- Adds significant complexity (web framework, frontend, deployment)
- CSV workflow is simpler and uses familiar tools
- Most users comfortable with real estate search are comfortable with spreadsheets
- Can be added later if CSV workflow proves insufficient

### Alternative 3: In-CLI Review (Interactive Prompts)

**Rejected because:**
- Tedious for reviewing multiple properties
- Hard to compare candidates side-by-side
- Doesn't allow user to review at their own pace offline
- CSV export allows sorting, filtering, and batch operations

## Future Considerations

- Could add a "priority" field to candidates to help users sort review queue
- Could implement automatic "maybe" → "save" conversion after a certain time period if user doesn't reject
- Could add a web UI for review in future milestones (but CSV remains primary)
- Could send notifications when new high-priority candidates appear

## References

- [PRD.md](../../PRD.md) - Section 7: Human-in-the-loop workflow
- [Architecture.md](../../Architecture.md) - Section 8: Review workflow design
- Database schema: `candidate_review_queue` and `watched_properties` tables
