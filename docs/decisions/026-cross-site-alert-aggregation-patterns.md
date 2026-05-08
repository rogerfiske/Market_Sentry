# Decision 026: Cross-Site Alert Aggregation and Pattern Analysis

## Date

2026-05-08

## Status

Accepted

## Context

Milestone 26 introduced individual cross-site trend alerts with lifecycle management. Milestone 27 needs to aggregate these alerts into higher-level review insights so operators can prioritize which properties need attention based on alert burden and recurring discrepancy patterns.

## Decisions

### Why aggregation follows individual alerts

Individual alerts (Milestone 26) provide granular event-level detail. Aggregation (Milestone 27) provides property-level summary metrics. The two-layer approach lets operators drill down from high-level burden to specific alerts when needed. Aggregation was built on top of the existing alert table rather than replacing it.

### Why alert burden is neutral

Alert burden measures the cumulative weight of unresolved cross-site discrepancies. It does not indicate property quality, seller intent, or purchase suitability. Higher burden means more cross-site data discrepancies need human review, not that a property is good or bad. Burden labels (none, low, moderate, high, elevated_review) use neutral terms that describe workload, not recommendations.

### Why repeated patterns require multiple events

A single alert could be a one-time data issue (stale fixture, temporary parsing error, timing lag between sources). Requiring at least 2 matching events before flagging a pattern reduces false positives and ensures that only genuinely recurring discrepancies are highlighted. This threshold is consistent with the project's conservative, human-in-the-loop approach.

### Why watchlist state is not automatically changed

Alert analytics are read-only review aids. They do not modify active_watch_status, user_notes, watch_priority, or any other watchlist field. The human operator makes all watchlist decisions. Automatic state changes based on cross-site data would violate the project's human-in-the-loop principle and could act on incomplete or stale fixture data.

### Why Quiet Score gatekeeper is unchanged

The Quiet Score gatekeeper evaluates property stability based on listing history and churn. Cross-site alert burden measures a different dimension (data agreement across sources). Mixing these dimensions would dilute the gatekeeper's purpose. Alert burden is presented alongside Quiet Score as an independent review signal, not as an override or modifier.

### Why walkability remains excluded

Walkability scoring is explicitly excluded from the current project scope per PM direction. No walkability fields, parsing, or scoring have been added in any milestone. This decision remains unchanged.

## Consequences

- Operators can quickly identify properties with the highest alert burden for priority review.
- Repeated pattern detection surfaces recurring data quality issues that individual alerts alone might not highlight.
- Watchlist state remains fully under human control.
- The Quiet Score gatekeeper continues to operate independently of cross-site analytics.
- Future milestones could add automated triage suggestions based on burden levels, but any such feature would still require human confirmation.
