# Decision 041: Portfolio Review Trends

## Date

2026-05-13

## Status

Accepted

## Context

Milestones 40 and 41 established the Portfolio Review Pack and Pack Comparison, providing snapshot and two-point comparison reports from exported CSV files. Operators needed a way to analyze trends across multiple sequential review pack exports to see aggregate burden over time, per-property trend directions, and metric deltas across the full history of pack exports.

## Decisions

### Why trends follow review pack comparison

The review pack (Milestone 40) established a stable CSV export format, and the comparison module (Milestone 41) demonstrated that CSV-based analysis is reliable for detecting per-property changes between two points. Trends extend this to the full series of exports, providing time-series analysis without introducing new data sources or coupling to internal model changes.

### Why trends use exported CSVs as a stable interface

Exported CSV files are timestamped, immutable once written, and have a well-defined 35-column schema. Using CSVs as the trend data source provides: (1) offline analysis without database access, (2) reproducibility from stable historical exports, (3) graceful handling of schema drift through missing column fallbacks, (4) no coupling to internal model or database changes.

### Why aggregate burden is operational, not a property desirability score

The aggregate review burden score (0-100) measures how much operational review work the portfolio demands. It is not a property quality, investment, or desirability score. It reflects the count and severity of properties needing immediate/high review, lifecycle attention, high/critical alerts, quiet gatekeeper failures, high churn, and large DOM deltas. Burden labels (low_burden, moderate_burden, elevated_burden, high_burden) use neutral operational language.

### Why this is read-only

The trends module reads CSV files and produces output reports. It does not INSERT, UPDATE, or DELETE any database rows. It does not modify any candidate, watchlist, alert, cross-site, or property state. Trend analysis is purely observational.

### Why scheduled script is local and report-only

The updated `run_portfolio_review_pack_report.bat` script runs three commands: review pack export, comparison export, and trend export. None of these commands invoke live retrieval, alert mutation, or watchlist changes. All output goes to `logs/scheduled/`.

### Why candidate/watchlist/alert state is not automatically changed

Trend reports observe and report changes over time. Operators use existing triage, archive, and expiration workflows to take actions. Automatic state changes from a trend analysis tool would bypass the human-in-the-loop design and could act on incomplete information.

### Why Quiet Score gatekeeper is unchanged

The trends module reads and reports Quiet Score gatekeeper results from CSV exports but does not modify the gatekeeper logic, thresholds, or scoring. The quiet gatekeeper threshold remains at 70.0.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields have been added in any milestone.

## Consequences

- Operators can analyze portfolio review trends across all historical pack exports.
- Aggregate review burden score provides a neutral operational metric for portfolio-level review demand.
- Per-property trend direction (improved, degraded, stable, new, insufficient_data) provides neutral characterization of property-level changes.
- Export to CSV and Markdown supports both spreadsheet analysis and printed review.
- The scheduled script automates pack generation, comparison, and trend analysis.
- Dashboard integration provides interactive trend exploration.
- No alerts, candidates, or watchlist entries are modified by trend operations.
- All existing review pack, comparison, digest, triage, archive, expiration, lifecycle, and health workflows continue unchanged.
