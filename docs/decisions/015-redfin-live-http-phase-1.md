# Decision 015: Redfin Live HTTP Retrieval Phase 1

**Date:** 2026-05-07
**Status:** Accepted
**Milestone:** 16

## Context

Milestones 14-15 established a compliance-aware source adapter architecture with policy enforcement, rate limiting, robots policy, dry-run approval, fixture capture queue, and audit logging. All of these operated in preview/dry-run mode only. Milestone 16 adds the first actual HTTP retrieval capability, constrained to Redfin only.

## Decisions

### Why Redfin Is First

Redfin is the primary source for Market_Sentry candidate discovery. The existing codebase has mature Redfin fixture parsers for both search results and property detail pages. Starting with Redfin allows us to validate the live retrieval pipeline against well-tested parsing code. Other sources (Zillow, Realtor, Homes, Compass, County) will be considered in future milestones.

### Why Retrieval Saves Fixtures Instead of Directly Mutating Candidate Tables

Retrieved HTML is saved as local fixture files rather than being parsed and inserted directly into the database. This design choice provides:

1. **Auditability**: The original HTML is preserved for review.
2. **Reprocessing**: Fixtures can be re-parsed if parsers are improved.
3. **Separation of concerns**: Retrieval and parsing are independent operations.
4. **Safety**: A failed parse does not lose the retrieved data.
5. **Consistency**: The same fixture parsers work for both manually saved and live-retrieved pages.

### Why Dry-Run Approval Is Required

Requiring a recent dry-run before live retrieval ensures the user has:

1. Reviewed what will be retrieved.
2. Confirmed the URL is valid and the compliance status is understood.
3. Made a conscious decision to proceed with live retrieval.

This prevents accidental or automated live retrieval.

### Why Local Robots Policy Is Required

The system requires a locally saved robots.txt file rather than fetching it from the internet because:

1. Fetching robots.txt is itself a network call that must be audited and rate-limited.
2. A local file provides deterministic, testable behavior.
3. The user explicitly acknowledges the robots policy by saving it locally.
4. This avoids the chicken-and-egg problem of needing network access to check if network access is allowed.

### Why Live Retrieval Is Not Scheduled by Default

Scheduled tasks (Windows Task Scheduler) run local workflows on existing data only. Live retrieval is excluded because:

1. Unattended live retrieval lacks human oversight.
2. Rate limit enforcement is harder to guarantee across scheduled runs.
3. Network failures in scheduled tasks are harder to diagnose.
4. The human-in-the-loop principle requires conscious retrieval decisions.

### Why Browser Automation Is Excluded

Browser automation (Playwright, Selenium) is excluded because:

1. It adds large dependencies and complexity.
2. It implies intent to render JavaScript, which may bypass access controls.
3. Simple HTTP GET is sufficient for publicly available HTML pages.
4. The system is designed to work with saved HTML fixtures, not rendered pages.

## Consequences

- Live retrieval is available but constrained to Redfin, rate-limited, policy-checked, and audited.
- Users must manually configure environment variables, save robots.txt, and run dry-runs before live retrieval works.
- Scheduled tasks remain local-only and do not invoke live retrieval.
- Retrieved HTML follows the same fixture path conventions as manually saved pages.
- Future milestones may extend live retrieval to other sources following the same pattern.
