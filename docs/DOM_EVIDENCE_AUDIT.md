# Effective DOM Evidence Audit

## Overview

Effective DOM is the metric this system is built around, but until now it
rendered as a bare number. A property with three years of listing events and a
county-confirmed transfer produced an integer; so did one with a single scraped
figure and nothing behind it. The two looked identical and deserved very
different weight.

The evidence audit answers the missing question: **how much should you trust
this number?** It shows Effective DOM v1 and v2 side by side, reports the Churn
Index separately, explains any reset boundary, names every piece of missing
evidence, and rates confidence.

It is read-only and local-only. It describes evidence. It does not infer seller
intent and it is not a purchase recommendation.

## Effective DOM v1 vs v2

**Effective DOM v1** measures property-level market exposure from listing
history alone: listings, removals, relists, and price changes within the
lookback window. It knows nothing about ownership.

**Effective DOM v2** adds one thing: a county-confirmed ownership transfer acts
as a reset boundary. Exposure before that boundary is excluded from v2.

The reasoning is that a genuine sale ends the previous owner's marketing story.
Exposure accumulated by a prior owner is not the current owner's exposure.

**When they differ:** only when the current listing began *before* the transfer.
If a property sold and was relisted afterwards, the current listing is already
entirely post-transfer and v1 and v2 agree.

Worked example from the test suite:

```text
Listed          2024-03-01
Price change    2025-06-01
County transfer 2025-11-18   <- reset boundary
Price change    2026-01-05
Price change    2026-05-15

Effective DOM v1: 822    (exposure from 2024-03-01)
Effective DOM v2:  30    (post-transfer exposure only)
v1 - v2 delta:    792
Churn Index:      0.5    (unchanged by the reset)
```

## County Reset and Churn Preservation

**A county-confirmed transfer may reset Effective DOM v2. It never erases the
Churn Index.**

These are different measures answering different questions:

| Measure | Question | Effect of a transfer |
|---------|----------|---------------------|
| Effective DOM v2 | How long has the *current* owner been marketing? | Exposure before the transfer is excluded |
| Churn Index | How unstable has this *property's* listing history been? | Unchanged; the full history still counts |

Churn is computed over its own lookback window from the complete event history,
independent of any reset boundary. A property that was listed, delisted, and
relisted repeatedly before changing hands still carries that churn record. The
transfer explains a clean DOM; it does not erase the instability that preceded
it.

The audit states this explicitly on every reset:

```text
Effective DOM v2 applies a county-confirmed transfer reset on 2025-11-18
(grant_deed). Exposure before that boundary is excluded from Effective DOM v2,
but listing churn remains separately reported in the Churn Index.
```

And when there is no reset evidence:

```text
No county-confirmed transfer reset evidence is available. Effective DOM v2 does
not apply a reset.
```

## Confidence Categories

| Category | Meaning |
|----------|---------|
| `high` | Score 75-100. Multiple listing events, known listing start, corroborating records |
| `moderate` | Score 50-74. Usable history with some evidence missing |
| `low` | Score 25-49. Thin evidence; treat the numbers cautiously |
| `insufficient` | Score under 25, **or** no listing events and no displayed DOM at all |

`insufficient` is not merely "scored badly". It specifically means there was no
exposure evidence to work with, so the DOM figures cannot be relied on.

### How the score is built

Deterministic and fully itemized. The same inputs always produce the same score,
and every factor is reported with its weight so the number can be explained.

**Factors that raise confidence** (100 points total):

| Factor | Weight |
|--------|--------|
| Multiple listing events (2 or more) | 25 |
| Current listing start date known | 20 |
| County transfer evidence supports the reset | 20 |
| Redfin detail enrichment present | 15 |
| Saved source page present | 10 |
| County records available for corroboration | 10 |

**Penalties**:

| Penalty | Weight |
|---------|--------|
| Displayed DOM only, no event history | −20 |
| v1 and v2 differ without reset evidence | −20 |
| Most recent event is stale (over 90 days) | −10 |

Penalties are deliberately smaller than the positive weights, so one gap cannot
drag a well-evidenced property down to `insufficient`.

## Evidence Gaps

Every missing or contradictory piece of evidence is named:

| Gap | Meaning |
|-----|---------|
| `missing_listing_events` | No listing events; exposure cannot be reconstructed |
| `missing_current_listing_start` | Current listing start unknown; exposure is estimated |
| `missing_displayed_dom` | No displayed DOM captured for comparison |
| `missing_county_transfer_evidence` | No county-confirmed transfer, so no reset applies |
| `missing_source_page` | No saved capture backs these values |
| `conflicting_dom_values` | v1 and v2 differ with no reset boundary to explain it |
| `stale_observation` | Most recent event is older than 90 days |

`conflicting_dom_values` is the one to look at first. A v1/v2 difference is
normal *with* a reset; without one it means the stored values disagree with what
the evidence supports.

## CLI Usage

```powershell
# Audit one candidate
python -m marketsentry.cli dom-evidence-audit --candidate-id 4

# Audit one watched property
python -m marketsentry.cli dom-evidence-audit --watched-property-id 2

# Every evidence gap across all subjects
python -m marketsentry.cli list-dom-evidence-gaps
python -m marketsentry.cli list-dom-evidence-gaps --gap conflicting_dom_values

# Export the full report
python -m marketsentry.cli export-dom-evidence-audit-report
python -m marketsentry.cli export-dom-evidence-audit-report --format csv
python -m marketsentry.cli export-dom-evidence-audit-report --candidate-id 4
```

All commands default to `db/marketsentry.db` and accept an explicit `--db`.
Everything is read-only apart from writing report files.

## Export

Writes `data/exports/dom_evidence_audit_YYYYMMDD_HHMMSS.{csv,md}` containing the
candidate and property IDs, address, clickable Redfin link, displayed DOM,
Effective DOM v1 and v2, the v1/v2 delta, whether a reset applied and on what
date and evidence, the Churn Index and its event counts, the confidence category
and score, every evidence gap, and the neutral explanation.

## Dashboard

The **Effective DOM Evidence Audit** section shows confidence counts across all
subjects, how many carry evidence gaps, how many have v2 reset evidence, and how
many have churn preserved. Selecting a subject shows v1 and v2 side by side with
the Churn Index in its own column, the reset explanation, each evidence gap, the
confidence breakdown, and a clickable Redfin link.

Loading the page never changes anything. Only the export button writes.

## Boundaries

- **No live retrieval or scraping.** Every value is computed from locally stored
  listing events and county records.
- **No browser automation.**
- **No outbound notifications.**
- **No credentials.**
- **No walkability fields.**
- **No seller intent.** The report describes exposure and evidence quality. It
  never characterizes why a property was listed, relisted, or repriced.
- **No purchase recommendations.** Confidence rates the *evidence*, not the
  property.
- **The Quiet Score gatekeeper is untouched.** The audit does not read or affect
  it; low Vibrancy still never overrides a poor Quiet score.
