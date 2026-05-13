# Decision 040: Portfolio Review Comparison

## Date

2026-05-13

## Status

Accepted

## Context

Milestone 40 established the Portfolio Review Pack with per-property briefs exported to CSV and Markdown. Operators needed a way to compare review packs over time to see which properties improved, degraded, or had material changes in priority, lifecycle health, alert burden, Effective DOM, Churn Index, or cross-site confidence.

## Decisions

### Why comparison follows print-ready review packs

The portfolio review pack (Milestone 40) established a stable CSV export format with 35 columns covering all key property metrics. Comparison builds on this stable interface by reading two CSV exports and detecting per-property changes. This approach avoids coupling comparison logic to database queries or internal model changes.

### Why comparisons use exported CSVs as the stable interface

Using CSV exports as the comparison source provides several benefits: (1) CSVs are timestamped and immutable once written, providing a reliable historical record. (2) The CSV schema is well-defined with 35 columns. (3) Comparisons work without database access, enabling offline review. (4) Schema drift is handled gracefully with missing column fallbacks.

### Why it is read-only

The comparison module reads CSV files and produces output reports. It does not INSERT, UPDATE, or DELETE any database rows. It does not modify any candidate, watchlist, alert, cross-site, or property state. This ensures that comparing review packs never accidentally changes property state.

### Why scheduled script is local and report-only

The updated `run_portfolio_review_pack_report.bat` script runs two commands: review pack export and comparison export. Neither command invokes live retrieval, alert mutation, or watchlist changes. All output goes to `logs/scheduled/`.

### Why candidate/watchlist/alert state is not automatically changed

The comparison report observes and reports changes. Operators use existing triage, archive, and expiration workflows to take actions based on comparison observations. Automatic state changes from a reporting tool would bypass the human-in-the-loop design.

### Why Quiet Score gatekeeper is unchanged

The comparison module reads and compares Quiet Score gatekeeper results from CSV exports but does not modify the gatekeeper logic, thresholds, or scoring.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields have been added in any milestone.

## Consequences

- Operators can compare two review pack exports to see property-level changes over time.
- Material change detection uses neutral thresholds (score >= 5, DOM >= 14 days, churn >= 1.0, confidence >= 10).
- Trend labels (improved, degraded, changed, unchanged, new, removed) provide neutral characterization.
- Export to CSV and Markdown supports both spreadsheet analysis and printed review.
- The scheduled script automates both pack generation and comparison.
- Dashboard integration provides interactive comparison exploration.
- No alerts, candidates, or watchlist entries are modified by comparison operations.
- All existing review pack, digest, triage, archive, expiration, lifecycle, and health workflows continue unchanged.
