# Decision 042: Portfolio Trend Alerts

## Date

2026-05-13

## Status

Accepted

## Context

Milestone 42 established portfolio review trend analysis with aggregate burden scoring and per-property trend directions. Operators needed a way to convert trend observations into actionable local alerts with threshold rules, so that significant changes are surfaced automatically without requiring manual review of the full trend report.

## Decisions

### Why trend alerts follow portfolio trends

Portfolio trends (Milestone 42) provide the data foundation: aggregate burden scores, per-property trend directions, and metric deltas. Trend alerts apply threshold rules to this data to flag significant changes. This layered approach keeps trend analysis and alerting concerns separate while reusing the same CSV-based data pipeline.

### Why alerts are local and report-only

Trend alerts are generated as local Markdown and CSV digest files. They are not stored in the database, do not create cross-site alert records, and do not trigger any automated actions. This ensures that the alerting layer remains a passive reporting tool that operators review at their discretion.

### Why no outbound notification is sent

Outbound notifications (email, SMS, webhook) are explicitly excluded from this milestone. The system is designed for local, offline review. Future milestones may add optional notification channels, but the current design prioritizes local-first operation without external dependencies.

### Why scheduled script is local and report-only

The updated `run_portfolio_review_pack_report.bat` script runs four commands: review pack export, comparison export, trend export, and alert digest export. None of these commands invoke live retrieval, alert mutation, watchlist changes, or outbound notifications. All output goes to `logs/scheduled/`.

### Why candidate/watchlist/alert state is not automatically changed

Trend alerts observe and report threshold violations. Operators use existing triage, archive, and expiration workflows to take actions. Automatic state changes from an alerting tool would bypass the human-in-the-loop design and could act on incomplete or transient data.

### Why Quiet Score gatekeeper is unchanged

The trend alerts module reads Quiet Score gatekeeper results indirectly through trend data but does not modify the gatekeeper logic, thresholds, or scoring. The quiet gatekeeper threshold remains at 70.0.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields have been added in any milestone.

## Consequences

- Operators receive local alert digests highlighting portfolio and property metrics that crossed threshold rules.
- Severity levels (info, warning, high) provide neutral prioritization guidance.
- Default rules cover burden thresholds, burden increases, property degradation, backlog growth, lifecycle health changes, cross-site confidence drops, churn increases, and DOM v2 increases.
- Export to CSV and Markdown supports both spreadsheet analysis and printed review.
- The scheduled script automates pack generation, comparison, trend analysis, and alert digest.
- Dashboard integration provides interactive alert exploration.
- No outbound notifications are sent.
- No alerts, candidates, or watchlist entries are modified by alert operations.
- All existing review pack, comparison, trend, digest, triage, archive, expiration, lifecycle, and health workflows continue unchanged.
