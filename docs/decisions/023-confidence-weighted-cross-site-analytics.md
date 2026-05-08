# Decision 023: Confidence-Weighted Cross-Site Comparison Analytics

## Date

2026-05-08

## Status

Accepted

## Context

Milestone 23 added parse confidence scoring (high/medium/low), missing required field tracking, and parse warnings to all four non-Redfin parsers. However, the cross-site comparison system treated all observations equally regardless of parse quality, data freshness, or field completeness. A low-confidence, stale observation had the same analytical weight as a high-confidence, recent one.

## Decision

### Add confidence weighting after parser quality

Parser quality (Milestone 23) must exist before confidence weighting is meaningful. Weighting builds on the parse_confidence, parse_status, and parse_warnings fields established in Milestone 23.

### Downweight low-confidence sources

Low-confidence sources reduce the certainty of discrepancy assessments rather than exaggerating them. A price discrepancy reported by a low-confidence source should not trigger the same severity as one from a high-confidence source.

Initial weight mappings:

- parse_confidence high = 1.0
- parse_confidence medium = 0.7
- parse_confidence low = 0.4
- parse_status failed = 0.0 (excluded)

### Downweight stale sources

Observations age out over time:

- 0-7 days = 1.0
- 8-30 days = 0.8
- 31-90 days = 0.5
- >90 days = 0.2

### Use neutral discrepancy severity

Severity levels (none, low, medium, high, critical) describe the magnitude of data disagreement, not seller intent. Language remains neutral: "price_discrepancy", "status_discrepancy", "dom_discrepancy", "gas_disagreement", "garage_disagreement".

### Cross-site data remains validation-only

Analytics produce scores and flags for human review. They do not overwrite user_decision, user_notes, active_watch_status, watch_priority, or any Redfin-sourced property facts.

### Quiet Score gatekeeper is unchanged

Cross-site confidence scores do not influence or override the Quiet Score gatekeeper. Quiet Score remains the independent location quality gatekeeper.

### Walkability remains excluded

Walkability-type information (walk score, transit score, bike score) is not part of the cross-site analytics scope.

## Consequences

### Positive

- Source observations are weighted by confidence, freshness, and completeness
- Discrepancy severity accounts for source reliability
- Manual review priority helps operators focus on high-value data conflicts
- New CLI command and CSV report for analytics export
- Dashboard shows analytics summary alongside existing cross-site data

### Negative

- Weight values are initial heuristics that may need tuning with real data
- Overall confidence formula (25% freshness + 25% completeness + 50% agreement) is a reasonable starting point but may not be optimal
- Analytics rely on parse_confidence which is itself heuristic-based

## Related

- Milestone 23: Cross-site parser quality and fixture corpus expansion
- Milestone 6: Cross-site enrichment foundation
- Milestone 22: Cross-site adapter parity and manual fixture workflow
