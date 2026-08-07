# HowLoud Noise Enrichment

## Overview

HowLoud is an optional third-party noise signal. It supplements Redfin
Quiet/Vibrancy and your own local knowledge with an independent reading, stored
in its own table and never merged into the Redfin fields.

It is entirely opt-in. Nothing calls HowLoud unless you run an explicit command
with enrichment enabled and an API key configured. Dry-run is the default.

## Why HowLoud Is Kept Separate from Redfin Quiet

Three separate reasons:

1. **They measure different things.** Redfin's Quiet Score is a lifestyle score
   on a 0-10 scale. HowLoud's SoundScore is a modelled acoustic estimate on a
   0-100 scale with its own sub-values for traffic, airports, and local sources.
   Averaging them would produce a number that means nothing.

2. **Disagreement is the useful signal.** If Redfin says quiet and HowLoud says
   busy, that contradiction is exactly what you want surfaced for manual review.
   Blending them would hide it.

3. **The gatekeeper must stay predictable.** Quiet Score is the gatekeeper at
   7.0. If a third-party API could move that threshold, the rule would depend on
   an external service's availability and model changes. HowLoud provides
   context; it never changes a pass or a fail.

## Configuring the API Key Without Committing It

The key is read from the environment only. It is never printed, logged, written
to the database, or included in any report.

Add it to your local `.env` file, which is already gitignored:

```text
MARKETSENTRY_HOWLOUD_ENABLED=true
MARKETSENTRY_HOWLOUD_API_KEY=your-key-here
MARKETSENTRY_HOWLOUD_BASE_URL=https://api.howloud.com
MARKETSENTRY_HOWLOUD_TIMEOUT_SECONDS=15
```

Or set it for a single session:

```powershell
$env:MARKETSENTRY_HOWLOUD_ENABLED = "true"
$env:MARKETSENTRY_HOWLOUD_API_KEY = "your-key-here"
```

Two settings are required on purpose. A key alone does nothing: enrichment must
also be enabled. This makes an accidental outbound call from a stray key
impossible.

**Never commit a key.** `.env` is gitignored; `.env.example` carries only an
empty placeholder.

### How the key is protected

- It is not a field on the config object, because config objects appear in logs
  and tracebacks.
- It is sent in the `x-api-key` **header**, never as a query parameter, because
  query strings end up in server and proxy logs.
- Every string headed for storage is passed through a redactor that strips any
  occurrence of the key, so even a provider that echoes it back cannot get it
  persisted.
- Status output shows only a masked form, for example `********9999`. Keys of
  eight characters or fewer are masked completely.

## Checking Configuration

```powershell
python -m marketsentry.cli howloud-config-status
```

```text
HowLoud Configuration
  Enabled:      no
  API key:      not set
  Base URL:     https://api.howloud.com
  Timeout:      15s
  Ready:        no
```

## Coordinates Are Required

The HowLoud v2 API accepts **latitude and longitude only**. It has no address
endpoint, so an address alone cannot be looked up.

Market_Sentry does not call a geocoding service, because that would add a second
outbound dependency this milestone does not authorize. Instead you supply the
coordinates once per property, and they are stored with the observation and
reused automatically on later runs.

To find coordinates: open the property location in any map application,
right-click the spot, and copy the latitude/longitude pair.

## Seeing What Needs Enrichment

```powershell
python -m marketsentry.cli list-candidates-needing-howloud
```

Shows every candidate without a successful HowLoud reading, and whether
coordinates are already known.

## Dry-Run vs Real Enrichment

**Dry-run is the default.** It builds the request, shows you the endpoint that
would be called, and stops. No network request. No database write. Not even a
schema change.

```powershell
# Preview only
python -m marketsentry.cli enrich-candidate-howloud --candidate-id 5 --lat 33.4936 --lng -117.1484

# Actually call HowLoud
python -m marketsentry.cli enrich-candidate-howloud --candidate-id 5 --lat 33.4936 --lng -117.1484 --no-dry-run
```

A real call requires all three of: `--no-dry-run`,
`MARKETSENTRY_HOWLOUD_ENABLED=true`, and a configured key. If any is missing the
command explains what is absent and exits without making a request.

Failed attempts are still recorded, with their status and a sanitized error
message, so you have an audit trail. A failed attempt does not count as a
reading: the candidate still appears in the needs-enrichment list.

## Comparing HowLoud to Redfin

```powershell
python -m marketsentry.cli compare-howloud-redfin --candidate-id 5
```

The two sources are printed side by side and never merged. The comparison
produces one of these categories:

| Category | Meaning |
|----------|---------|
| `agreement_clear` | Both sources lean the same direction |
| `possible_disagreement` | The sources point different ways; review manually |
| `missing_redfin_score` | No Redfin Quiet recorded yet |
| `missing_howloud_score` | No HowLoud reading recorded yet |
| `manual_review_needed` | HowLoud's reading was inconclusive |

Every comparison also prints a gatekeeper statement, whether or not the sources
agree, so no reader can mistake HowLoud for having changed the outcome:

```text
Redfin Quiet is below the gatekeeper threshold. HowLoud can provide supporting
context but does not change the gatekeeper result.
```

### How agreement is decided

HowLoud's own text labels (`Calm`, `Busy`, and so on) are preferred, because the
numeric scales are not consistent between the overall score and the per-source
values. The documented higher-is-quieter overall score is the fallback. When
neither is conclusive, the result is `manual_review_needed` rather than a guess.

## Exporting the Report

```powershell
python -m marketsentry.cli export-howloud-noise-report
python -m marketsentry.cli export-howloud-noise-report --format csv
```

Writes `data/exports/howloud_noise_report_YYYYMMDD_HHMMSS.{csv,md}` with the
candidate, address, clickable Redfin link, Redfin Quiet/Vibrancy and gatekeeper
result, HowLoud scores and labels, agreement category, manual-review flag,
observation status, and any error. No API key appears in either file.

## Dashboard

The **HowLoud Noise Enrichment** section shows configuration status with a
masked key, the candidates needing enrichment, a candidate selector with the
latest observation, a side-by-side Redfin/HowLoud comparison, a dry-run preview
form, an explicit enrich form with a confirmation checkbox, and an export button.

Loading the dashboard never calls HowLoud and never mutates anything. A request
happens only when you submit the enrich form with the confirmation box ticked.

## What This Does Not Do

- **No browser automation.** No Playwright, no Selenium, no headless browser.
- **No Redfin scraping.** This milestone adds no Redfin retrieval of any kind.
- **No overwriting of Redfin fields.** HowLoud values are written only to
  `howloud_observations`. Redfin Quiet, Vibrancy, and the gatekeeper result are
  never touched.
- **No change to the Quiet gatekeeper.** Still 7.0, and a low Vibrancy score
  still never rescues a Quiet score below it.
- **No outbound notifications.** No email, SMS, or webhooks.
- **No walkability fields.**
- **No purchase recommendations.** The report is analytical evidence.

## Worked Example: A Noise-Risk Control Case

Candidate 5 (32152 Camino Nunez) has Redfin Quiet 6.9 and fails the gatekeeper.
Suppose HowLoud returns a calm reading.

The comparison reports `possible_disagreement` and flags it for manual review,
and states plainly that the gatekeeper result is unchanged. The candidate still
fails. HowLoud has given you a reason to look more carefully at a contradiction
between two independent sources; it has not overridden the rule.

This is the intended use: HowLoud is evidence for your judgment, not an
automated decision.
