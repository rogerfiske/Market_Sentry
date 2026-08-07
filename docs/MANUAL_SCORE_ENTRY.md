# Manual Quiet/Vibrancy and Noise Risk Entry

## Overview

Quiet and Vibrancy scores come from you, not from the software. You open the
Redfin property page in your browser, read the two lifestyle scores with your
own eyes, and type them in. Market_Sentry then applies the Quiet gatekeeper and
tells you what to do next.

Nothing in this workflow reads Redfin. There is no HTTP client, no browser
automation, and no page parsing involved in score entry.

## Where to Find Quiet and Vibrancy on Redfin

1. Open the property's Redfin page in your normal browser.
2. Scroll to the neighborhood or lifestyle section of the listing.
3. Redfin shows lifestyle score cards. The **Quiet** card is marked with a
   mute/speaker icon; the **Vibrancy** card uses a waveform/equalizer icon.
4. Each card shows a number from 0 to 10, for example `9.9`.

Read both numbers. If a score is not shown for that property, leave it out and
record what you do know in the notes instead.

## Why Quiet Is the Gatekeeper

Quiet Score decides whether a candidate proceeds:

```text
Quiet >= 7.0  -> pass
Quiet <  7.0  -> fail_noise_risk
```

The gatekeeper threshold is 7.0 and does not change.

## Why Low Vibrancy Does Not Rescue Poor Quiet

Vibrancy is recorded for location fit, but it is **not** a gatekeeper. A very
calm, low-Vibrancy area can still sit next to an arterial road or under a flight
path.

Real example from the watchlist:

```text
32152 Camino Nunez
Quiet 6.9, Vibrancy 1.1
Result: fail_noise_risk
```

Vibrancy 1.1 is excellent, and it changes nothing. Quiet 6.9 is below 7.0, so the
candidate fails. The system says so explicitly:

```text
Quiet 6.9 is below the 7.0 gatekeeper threshold, so this candidate is marked
fail_noise_risk even though Vibrancy is 1.1.
Vibrancy 1.1 is low, but low Vibrancy does not override a Quiet failure.
Quiet is the gatekeeper.
```

## Seeing What Needs Scores

```powershell
# Which candidates are missing scores, and which fail the gatekeeper
python -m marketsentry.cli list-candidates-needing-scores

# Also include candidates that have scores but no noise observation
python -m marketsentry.cli list-candidates-needing-scores --include-noise

# Everything known about one candidate
python -m marketsentry.cli candidate-score-status --candidate-id 5
```

## Entering Scores

The original single-purpose commands still work exactly as before:

```powershell
python -m marketsentry.cli candidate-location-scores --candidate-id 7 --quiet-score 9.9 --vibrancy-score 1.3
python -m marketsentry.cli candidate-noise-notes --candidate-id 7 --noise-risk high --noise-sources "traffic,airport"
```

The combined command does both in one step and validates everything first:

```powershell
python -m marketsentry.cli candidate-score-and-noise-notes `
  --candidate-id 7 `
  --quiet-score 9.9 `
  --vibrancy-score 1.3 `
  --noise-risk low `
  --noise-sources "traffic" `
  --notes "Quiet cul-de-sac, verified on site"
```

### Validation

| Input | Result |
|-------|--------|
| `0`, `7.0`, `9.9`, `10` | Accepted |
| `-1`, `10.5`, `100` | Rejected: outside the 0-10 range |
| `abc`, blank | Rejected: not a number |
| Quiet without Vibrancy | Rejected: enter both so the gatekeeper sees a complete pair |
| `--noise-risk extreme` | Rejected: not a valid level |

The combined command validates **before** writing anything. If any value is
invalid, nothing at all is applied, so a typo cannot leave a candidate half
updated.

## Recording Local Noise Knowledge

Your field knowledge matters more than a platform score. If you know a road, a
flight path, or a nighttime traffic pattern, record it.

Noise risk levels: `unknown`, `low`, `moderate`, `high`, `severe`.

Suggested sources: `traffic`, `airport`, `road`, `arterial_road`, `freeway`,
`nighttime_racing`, `school`, `commercial`, `topography`, `unknown`, `other`.

Unrecognized sources are preserved rather than rejected, so you can record
something specific like `quarry_blasting` without losing it.

Notes use neutral, observational language. They do not infer seller intent and
do not make purchase recommendations.

## Handling a Noise-Risk Control Case

A candidate that fails the gatekeeper is not automatically deleted. Keeping it
as a tracked control case is useful: you learn how the market treats a property
you believe is noisy.

```powershell
# 1. Record what you know
python -m marketsentry.cli candidate-noise-notes --candidate-id 5 `
  --noise-risk high `
  --noise-sources "traffic,airport,nighttime_racing" `
  --notes "Track as noise-risk control. Monitor DOM, price reductions, final sale price."

# 2. Then hold or reject it
python -m marketsentry.cli candidate-decision --candidate-id 5 --decision maybe --notes "Noise-risk control"
```

## Dashboard: Manual Quiet/Vibrancy Entry

The dashboard has a dedicated **Manual Quiet/Vibrancy Entry** section with:

- Counts of candidates missing scores, missing noise notes, and failing the gatekeeper
- A table of candidates needing attention, with the next step per candidate
- A candidate selector showing the current values and a clickable Redfin link
- A **gatekeeper preview** that shows pass/fail as you type, before you save
- A combined save form: Quiet, Vibrancy, noise risk, noise sources, notes
- An optional **Run local refresh after saving** checkbox
- An export button for the manual score entry queue

Rendering the section never writes to the database. Only submitting a form does.

Launch it with:

```powershell
python -m marketsentry.cli launch-dashboard
```

## Exporting the Manual Score Queue

```powershell
python -m marketsentry.cli export-manual-score-entry-queue
python -m marketsentry.cli export-manual-score-entry-queue --format csv
python -m marketsentry.cli export-manual-score-entry-queue --include-complete
```

Writes to `data/exports/manual_score_entry_queue_YYYYMMDD_HHMMSS.{csv,md}` with
candidate ID, address, city/ZIP, clickable Redfin URL, current Quiet/Vibrancy,
gatekeeper result, noise risk and sources, which fields are missing, the
recommended next step, and the full notes.

By default only candidates with outstanding work are listed. Add
`--include-complete` to list every candidate.

## Refreshing Reports After Score Entry

Score entry changes the gatekeeper result, which feeds the reports. Regenerate
them when you finish a scoring pass:

```powershell
python -m marketsentry.cli run-operator-refresh-workflow
```

Or add `--refresh` to the combined command, or tick the refresh checkbox in the
dashboard. A refresh failure never undoes the scores you just saved.

## Optional: Cross-Checking with HowLoud

Redfin Quiet is one opinion. HowLoud is an optional independent noise estimate
you can record alongside it:

```powershell
python -m marketsentry.cli enrich-candidate-howloud --candidate-id 5 --lat 33.4936 --lng -117.1484 --no-dry-run
python -m marketsentry.cli compare-howloud-redfin --candidate-id 5
```

HowLoud values are stored in their own table and are **never** blended into
Redfin Quiet/Vibrancy. They do not change the gatekeeper: a candidate failing at
Quiet 6.9 still fails whatever HowLoud reports. Where the two sources disagree,
the comparison flags it for your manual review, which is exactly the case where
your own local knowledge matters most.

See `docs/HOWLOUD_NOISE_ENRICHMENT.md`.

## Why This Is Manual and Local-Only

- Scores are typed by the operator after reading the Redfin page visually.
- No HTTP request is made to Redfin or any other site.
- No browser is launched or driven.
- No CAPTCHA, login, paywall, or anti-bot protection is bypassed.
- No credentials are stored or requested.
- No notifications are sent.
- Walkability fields are not added.
- The Quiet Score gatekeeper is unchanged at 7.0.
- Reports are analytical aids, not purchase recommendations.

Automating the reading of Redfin lifestyle scores would be a separate,
compliance-reviewed milestone. It is deliberately not part of this one.
