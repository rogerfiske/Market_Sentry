# Decision 039: Portfolio Review Pack

## Date

2026-05-12

## Status

Accepted

## Context

Milestones 38 and 39 established the operations digest and digest history for tracking operational metrics. However, operators still lack a consolidated, printable document that combines property-level details from Quiet/Vibrancy scoring, Effective DOM, Churn Index, cross-site analytics, alert burden, and lifecycle health into a single review packet suitable for offline property review sessions.

## Decisions

### Why review pack follows operations digest history

The operations digest (Milestone 38) and digest history (Milestone 39) established aggregate operational metric tracking. The portfolio review pack builds on that foundation by providing property-level detail briefs that complement the aggregate view. The review pack uses existing database tables and scoring results without introducing new metric categories or changing how metrics are calculated.

### Why it is read-only

The review pack is a reporting tool that reads from existing database tables and produces output files. It does not INSERT, UPDATE, or DELETE any rows in candidate, watchlist, alert, cross-site, or property tables. This ensures that generating a review pack never accidentally changes property state or alert status.

### Why it consolidates property-level details without replacing detailed reports

The review pack provides a summary-level brief for each property that includes key fields from multiple subsystems (Quiet/Vibrancy, DOM, churn, cross-site, alerts, lifecycle). It does not replace the detailed reports from individual subsystems (e.g., cross-site analytics reports, lifecycle health reports, DOM reports). Operators who need deeper investigation on a specific property can use the existing detailed commands.

### Why scheduled script is local and report-only

The `run_portfolio_review_pack_report.bat` script runs a single export command. It does not invoke live retrieval, alert mutation, or watchlist status changes. All output goes to `logs/scheduled/`. This matches the pattern established by other scheduled scripts.

### Why candidate/watchlist/alert state is not automatically changed

The review pack observes and reports. Operators use existing triage, archive, and expiration workflows to take actions based on review pack observations. Automatic state changes from a reporting tool would bypass the human-in-the-loop design that the system enforces.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper evaluates property stability based on listing history and churn patterns. The review pack reads and displays gatekeeper results (pass/fail/unknown) but does not modify the gatekeeper logic, thresholds, or scoring. The gatekeeper remains in its original module without modification.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields, parsing, or scoring have been added in any milestone, including this one.

## Consequences

- Operators can generate a consolidated, printable review packet for offline property review.
- Per-property briefs include key metrics from all subsystems in one document.
- Review priority ranking provides a neutral ordering for review sessions.
- Local next actions suggest which properties to investigate further.
- Export to Markdown and CSV supports both printed and spreadsheet workflows.
- The scheduled script automates review pack generation.
- Dashboard integration provides interactive review pack exploration.
- No alerts, candidates, or watchlist entries are modified by review pack operations.
- All existing digest, triage, archive, expiration, lifecycle, and health workflows continue unchanged.
