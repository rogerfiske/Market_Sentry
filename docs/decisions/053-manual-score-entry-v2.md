# ADR 053: Manual Quiet/Vibrancy and Noise Risk Entry v2

## Status

Accepted

## Context

Milestone 53 removed the batch friction from the screening queue. What remained
as the slowest, most error-prone step was manual score entry: after visually
reading Quiet and Vibrancy on a Redfin page, the operator typed them into
`candidate-location-scores`, then separately ran `candidate-noise-notes`.

Three specific problems:

1. **No validation.** `apply_candidate_location_scores` accepted any float. A
   typo such as `99` instead of `9.9` was written straight to the database and
   silently produced a passing gatekeeper result.

2. **No explanation.** The gatekeeper returned `fail_noise_risk` with no
   statement of why. The rule that matters most to this operator, that a low
   Vibrancy score does not rescue a Quiet score below 7.0, was documented but
   never surfaced at the moment of entry.

3. **Counts without names.** Next-step output said "2 candidates missing
   Quiet/Vibrancy" without saying which, so the operator had to run another
   query to find out which property to open.

Redfin does render the lifestyle scores in the browser DOM, so automating this
is technically conceivable. That is explicitly out of scope here: it would need
its own compliance-reviewed milestone.

## Decision

Add a manual score entry layer in a new `manual_score_entry.py` module.

1. **Validation helpers.** `validate_lifestyle_score` accepts 0.0-10.0
   inclusive and rejects out-of-range, non-numeric, boolean, NaN, and infinite
   input with operator-facing messages. `validate_noise_risk` and
   `parse_noise_sources` normalize the noise fields.

2. **Gatekeeper explanations.** `build_gatekeeper_explanation` delegates the
   decision to the existing `apply_quiet_gatekeeper` and only describes the
   result, so the explanation cannot drift from the rule. It always states the
   Vibrancy relationship explicitly.

3. **Per-candidate score-entry status.** `CandidateScoreEntryStatus` reports
   what a candidate still needs and the recommended next step, derived from
   existing columns. No schema change.

4. **Noise data parsed from notes, not new columns.** `apply_candidate_noise_notes`
   already writes tagged text (`[Noise observation: risk=high]`,
   `[Sources: traffic,airport]`) into `user_notes`. The status model parses those
   tags back out rather than adding `noise_risk` and `noise_sources` columns.

5. **Validate-then-write for the combined command.**
   `apply_scores_and_noise_notes` validates every supplied value before
   performing any write, so a rejected entry leaves the candidate untouched. It
   delegates the writes themselves to the existing M51 actions.

6. **Named candidates in next steps.** Screening next-step messages now name the
   specific candidates behind each count.

7. **Dashboard section with live gatekeeper preview.** A dedicated
   "Manual Quiet/Vibrancy Entry" section shows pass/fail as the operator types,
   before saving.

## Alternatives considered

**Add `noise_risk` and `noise_sources` columns.** Rejected. It would need a
migration and a backfill parser for existing notes, and would create two sources
of truth for the same fact. Parsing the existing tags reads the real history
correctly, which was verified against the live database: candidate 5's risk and
sources, written months earlier by the M51 workflow, parse correctly today.

**Add validation inside `apply_candidate_location_scores`.** Rejected for this
milestone to preserve exact backward compatibility of the M51 function for
programmatic callers. Validation lives in the new layer, which the new command
and the dashboard use.

**Automate reading the Redfin lifestyle score cards.** Rejected as out of scope.
The prompt for this milestone excludes it, and it needs its own compliance
review.

**Multi-field dashboard form without a preview.** Rejected. The preview is the
cheapest way to prevent a wrong entry, because the operator sees the gatekeeper
consequence before committing.

## Consequences

- A mistyped score is now rejected with a clear message instead of silently
  corrupting a candidate's gatekeeper result.
- The operator sees why a candidate failed, in the terms that matter, at the
  moment of entry.
- Next steps name the property to open rather than only counting them.
- Existing M51 commands and functions are unchanged and remain fully supported.
- No schema changes, no migration, no new dependencies.
- Score entry remains entirely manual. No live retrieval, scraping, browser
  automation, outbound notification, or credential handling is added.
- The Quiet gatekeeper remains at 7.0 and low Vibrancy still never overrides a
  Quiet failure.
- Walkability fields are not added.

## Notes

A follow-on milestone could add a Redfin rendered lifestyle score capture agent.
That would be a browser-automation change and must be scoped, reviewed for
compliance, and approved on its own terms. Nothing in this milestone assumes it.
