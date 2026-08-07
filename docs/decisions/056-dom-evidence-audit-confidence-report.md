# ADR 056: Effective DOM Evidence Audit and Confidence Report

## Status

Accepted

## Context

Effective DOM is the metric the PRD names as this system's differentiator, but
it was presented as a bare integer. A property with three years of listing
events plus a county-confirmed transfer produced a number; so did one with a
single scraped figure and no history behind it. Nothing in the output
distinguished them.

The operator had no way to answer a question that matters more than the value
itself: how much should this number be trusted? The evidence existed in
`listing_events`, `county_record_observations`, and `source_pages`, but it was
never surfaced or assessed.

## Decision

Add `dom_evidence_audit.py`, a read-only evidence and confidence layer.

1. **Recompute rather than read stored values.** The audit calls
   `calculate_effective_dom_v2` and `calculate_churn_index` on the underlying
   events instead of reading the persisted `effective_dom_v1`/`v2` columns. This
   costs a little work per audit and buys something important: when the stored
   values disagree with what the evidence supports, that disagreement surfaces
   as the `conflicting_dom_values` gap rather than being silently trusted.

2. **Reuse the existing calculators; add no new DOM logic.** The audit explains
   and rates; it does not compute exposure itself. This is what keeps the
   separation guarantee structural rather than a promise: Effective DOM comes
   from the DOM calculator, Churn Index comes from the churn calculator, and the
   audit only places them in adjacent fields.

3. **Deterministic, itemized confidence scoring.** Six positive factors summing
   to 100, three penalties, clamped to 0-100. Every factor is returned as a
   `DomEvidenceItem` carrying its weight, whether it was present, and why. A
   score that cannot be explained is not worth reporting, and one that varies
   between runs cannot be acted on.

4. **`insufficient` is a distinct state, not just a low score.** When there are
   no listing events *and* no displayed DOM, there is no exposure evidence at
   all. That is qualitatively different from thin evidence and is categorized
   separately regardless of the numeric score.

5. **Penalties are smaller than the positive weights.** A single stale
   observation should not drag a fully evidenced property to `insufficient`. The
   largest penalty is 20 against a 100-point positive scale.

6. **The gatekeeper statement is unconditional.** Every reset explanation states
   what the reset does and does not affect, whether or not a reset applied, so
   no reader can infer that a county transfer erased churn history.

## On the separation of Effective DOM and Churn Index

This is the rule most at risk from a report that shows both numbers together,
so the separation is enforced in three independent ways:

- **Different sources.** They come from different functions operating on
  different windows. The audit never derives one from the other.
- **Different fields.** `DomChurnEvidence` holds churn; the DOM values sit on
  the audit root. A test asserts `DomChurnEvidence` has no `effective_dom_v1`
  attribute.
- **Different columns.** CSV and Markdown exports keep them in separate columns
  with the Churn Index explicitly labelled "separate measure".

A test also scans the module for arithmetic combining the two.

## A note on test design

The first version of `test_v2_excludes_pre_transfer_exposure` asserted
`v2 <= v1` against a fixture whose current listing began *after* the transfer.
Both values were 61 and the test passed, proving nothing: the reset had excluded
no exposure at all.

The fixture was changed to a listing that starts in 2024 and remains active
across a 2025-11-18 transfer, which produces v1=822 against v2=30, and the
assertion tightened to require a strict reduction and a positive delta. A
companion test asserts the fixture's listing start precedes the reset date, so
the shape that makes the test meaningful cannot be edited away unnoticed.

This is recorded because the failure mode is easy to reproduce: with a
`<=` assertion and the wrong event shape, a reset feature can appear tested
while never being exercised.

## Alternatives considered

**Read the persisted v1/v2 columns.** Faster, and it would have avoided
recomputation. Rejected because the audit's purpose is to check the evidence,
and trusting the values under audit defeats that.

**Weight confidence by a machine-learned or tuned model.** Rejected. An
operator needs to see why a number is what it is. A fixed, itemized point scale
is explainable and testable; a tuned one is neither.

**Fold the Churn Index into a single "exposure quality" score.** Rejected, and
explicitly forbidden by the domain rules. The two measure different things and
the whole value of the pair is that they can disagree.

**Add a `dom_evidence_audits` table to persist results.** Rejected as premature.
The audit is cheap to recompute and always reflects current evidence; a stored
copy would immediately risk being stale, which is precisely the failure this
milestone exists to expose.

## Consequences

- The operator can see how much evidence supports each DOM figure and what is
  missing.
- Disagreement between stored and recomputed values is now visible rather than
  silent.
- No schema changes, no migration, no new dependencies.
- Recomputing per audit costs more than reading a column. Acceptable at this
  scale (single-digit subjects); if the watchlist grows into the hundreds this
  is the first thing to profile.
- The Quiet gatekeeper is untouched. A test asserts the audit module never
  references it.
- No live retrieval, scraping, browser automation, outbound notification,
  credential handling, or walkability field is added.

## Notes

The `stale_observation` threshold is 90 days, chosen as roughly one listing
cycle. It is a module constant so it can be tuned without touching logic.
