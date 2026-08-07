# ADR 054: HowLoud Noise Enrichment Adapter

## Status

Accepted

## Context

The originally sequenced next milestone was a Redfin Rendered Lifestyle Score
Capture Agent. The PM deferred it: it would require browser automation, which
every milestone to date has explicitly excluded, and it needs its own compliance
scoping.

HowLoud was chosen instead. It improves the noise analysis that is central to
this project while preserving the current compliance posture: an authenticated,
documented, first-party API the operator already has access to, called only on
explicit request.

Two findings from the local OpenAPI specification shaped the design and differ
from what the milestone prompt assumed.

**The v2 API is coordinate-only.** `GET /v2/score` takes `lat` and `lng`. There
is no address endpoint. The prompt assumed address-based lookup and suggested
address/city/state/zip request columns. Candidates in this project store
addresses, not coordinates.

**The response shape is documented one way and used another.** The schema
declares `result` as an object, while the provider's own Python code sample
reads `res['result'][0]['score']`, implying a list.

A third issue emerged from the field semantics. The example response pairs
`score: 80` with `scoretext: "Active"`, but `local: 0` with `localtext: "Calm"`
and `traffic: 18` with `traffictext: "Active"`. The overall score is
higher-is-quieter; the per-source values are intensity readings where higher
means more noise. The two are not on a common scale.

## Decision

Implement `howloud_adapter.py` as an opt-in, separately stored evidence source.

1. **The API key is never a stored value.** It is deliberately not a field on
   the `Config` model, because config objects are printed in logs and
   tracebacks. `get_howloud_api_key()` reads it from the environment on demand.
   It is sent in the `x-api-key` header rather than the query string, since
   query strings are logged by servers and proxies. Every string headed for
   persistence passes through a redactor that strips the key, so even a provider
   that echoes it back cannot cause it to be written.

2. **Two independent switches are required for any outbound call.**
   `MARKETSENTRY_HOWLOUD_ENABLED` and a configured key. A key alone does
   nothing. This makes an accidental call from a stray environment variable
   impossible.

3. **Dry-run is the default and is strictly non-mutating.** It performs no
   request, writes no rows, and does not even create the observations table.
   Read paths use `howloud_table_exists()` rather than `ensure_howloud_schema()`
   so that previewing cannot alter the database in any way.

4. **Coordinates are supplied by the operator.** Given the coordinate-only API,
   the alternatives were to add a geocoding service or to ask the operator. A
   geocoder would be a second outbound dependency this milestone does not
   authorize, so the operator supplies `--lat`/`--lng` once per property and the
   values are stored with the observation and reused automatically.

5. **Both response shapes are accepted.** `_extract_result_block` handles
   `result` as either an object or a list rather than trusting one source over
   the other.

6. **Comparison prefers the provider's own words.** Because the numeric scales
   are inconsistent, agreement is decided from HowLoud's text labels first, with
   the documented higher-is-quieter overall score as a fallback. When neither is
   conclusive the result is `manual_review_needed`, not a guess.

7. **HowLoud never touches the gatekeeper.** Values live only in
   `howloud_observations`. Every comparison emits a gatekeeper statement whether
   or not the sources agree, so no reader can conclude HowLoud changed an
   outcome. A test asserts the string "howloud" does not appear anywhere in
   `quiet_vibrancy.py`.

## Alternatives considered

**Add a geocoding service to resolve addresses to coordinates.** Rejected. It
adds a second outbound dependency, a second key to manage, and a second failure
mode, all outside this milestone's authorized scope. Manual coordinate entry
matches the project's existing manual-entry philosophy for Quiet/Vibrancy.

**Normalize HowLoud onto the 0-10 Redfin Quiet scale.** Rejected, and explicitly
forbidden by the milestone. The scales measure different things, and a converted
number would invite exactly the blending the design is meant to prevent.

**Let a HowLoud reading influence the gatekeeper.** Rejected. It would make a
core domain rule depend on an external service's availability and model
revisions.

**Store the key in the Config model for convenience.** Rejected. Config objects
are rendered in logs and tracebacks; a field there is a leak waiting to happen.

**Use `requests`.** Rejected. The project already has an audited
`HttpClient`/`FakeHttpClient` abstraction with timeouts and no cookies or
sessions. Reusing it keeps every outbound call mockable, which is what lets the
whole test suite run with zero network access.

## Consequences

- The operator gains an independent noise signal, and disagreement between
  sources is surfaced rather than averaged away.
- Coordinates must be entered once per property. This is real added friction and
  is the direct cost of not adding a geocoder.
- The comparison is deliberately conservative: ambiguous readings return
  `manual_review_needed` rather than a confident category.
- No schema change to any existing table. `howloud_observations` is new and
  additive.
- No new dependencies.
- The Quiet gatekeeper remains at 7.0, and low Vibrancy still never overrides a
  Quiet failure.
- No browser automation, Redfin scraping, outbound notifications, credential
  storage, or walkability fields are added.

## Notes

The deferred Redfin Rendered Lifestyle Score Capture Agent remains unimplemented
and unscoped. If it is revived it must be approved on its own terms as a
browser-automation change, not inherited from this sequence.
