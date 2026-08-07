# ADR 055: Workflow Stabilization, Test Isolation, and Coverage Policy

## Status

Accepted

## Context

Three issues accumulated across Milestones 53-55 and were deferred each time as
out of scope. The PM called a stabilization pass before adding more features.

**1. `exports_dir` was not honored by every refresh step.** Passing a custom
directory to `run_operator_refresh_workflow` sent some reports there and left
others in `data/exports`, so the flag was quietly misleading.

**2. The test suite dirtied three tracked release documents.** Every
`pytest` run left `RELEASE_CANDIDATE_CHECKLIST.md`, `RELEASE_NOTES_DRAFT.md`,
and `RELEASE_NOTES_FINAL.md` modified. Three milestones in a row required
reverting them by hand before committing, and a real edit to those files could
have been lost in the noise.

**3. Coverage ran without a floor.** `pyproject.toml` collected coverage but set
no `fail_under`, so the measured ~76% could slide indefinitely without failing a
build.

## Root causes

**exports_dir** turned out to be three distinct defects, not one:

- `export_candidate_analysis_report` and `export_watchlist_monitoring_report`
  accepted only `output_path`, a full file path. There was no way to pass a
  *directory*, so the workflow could not forward one and simply omitted it.
- `candidate_report.py` hardcoded `Path("data/exports")` in two functions,
  ignoring `config.data_exports_dir` entirely, so even the `DATA_EXPORTS_DIR`
  environment override never worked there.
- `export_operations_digest` takes two similarly named parameters:
  `exports_dir` (the directory it *scans* for existing reports) and `output_dir`
  (the directory it *writes* to). The workflow passed only `exports_dir`, so the
  digest read from the custom directory and wrote to the default one. The naming
  made the mistake easy to make and hard to see.

**Tracked release docs** were dirtied by CLI tests, not by the library tests.
`export_release_candidate_report` already accepted `project_root`, and the
direct-function tests passed `project_root=tmpdir` correctly. But the CLI
commands `export-release-candidate-report` and
`export-release-finalization-report` never exposed the option and never
forwarded it, so `project_root` always defaulted to `"."` and the generated docs
landed in the real repository.

## Decision

1. **Add an optional `exports_dir` to both exporters.** `output_path` continues
   to take precedence when supplied, since it already names an exact
   destination. Existing callers are unaffected because the new parameter
   defaults to `None`.

2. **Replace the hardcoded `data/exports` paths with `config.data_exports_dir`.**
   This also makes the `DATA_EXPORTS_DIR` environment override work in
   `candidate_report.py` for the first time.

3. **Pass `output_dir` as well as `exports_dir` to the operations digest**, with
   a comment at the call site explaining that the two parameters mean different
   things, so the next reader does not repeat the mistake.

4. **Expose `--project-root` on both release CLI commands**, defaulting to `"."`
   so operator behavior is unchanged, and forward it to the exporter. The two
   CLI tests now pass a temp directory.

5. **Set `fail_under = 75`** with `precision = 2`.

## On the coverage floor

The prompt suggested `fail_under = 76`. Measured coverage is 76.31%, which
displays as 76.

A floor set exactly at the current value has zero headroom: the first uncovered
line anyone adds turns the build red for a reason unrelated to their change.
Gates that fail for unrelated reasons get bypassed, and a bypassed gate is worse
than no gate because it looks like protection that is not there.

75 sits one point below the measured value. It still catches any meaningful
slide while leaving room for normal work. The prompt explicitly permitted
"another conservative floor at or below the stable measured value."

**Policy:**

- Current stabilization floor: **75%**
- Goal: **80%**
- Raise the floor as real coverage climbs. Never lower it.
- Live-network code paths are covered with fakes and mocks only.
- **Do not add tests that make real network calls to inflate coverage.**
  `source_adapters/http_client.py` sits at ~55% because its live branch is
  deliberately untested. That is correct, not a defect to fix.

## Alternatives considered

**Change the exporters' return types to report their output paths.** Rejected.
`export_watchlist_monitoring_report` returns a row count, so its path does not
appear in `output_paths`. Changing the return type would break existing callers
for a cosmetic gain, and the actual defect was file location, which is fixed.

**Rename `exports_dir`/`output_dir` on the operations digest to something less
confusable.** Tempting, and the naming genuinely caused this bug. Rejected for
this milestone because it is a public signature change across several callers,
which is more churn than a stabilization pass should carry. Recorded here as a
candidate for a future cleanup.

**Make the release exporters refuse to write outside a temp directory during
tests.** Rejected as too clever. Threading `project_root` explicitly is the
plainer fix and it also gives operators a genuinely useful CLI option.

**Set `fail_under = 80` immediately.** Rejected. It would fail today and force
either a rushed coverage push or an immediate bypass.

## Consequences

- A custom `exports_dir` is now honored by all eight refresh steps, verified by
  a test asserting nothing lands in the default directory.
- `pytest` leaves the working tree clean. A guard test fails loudly and names
  the file if a future test regenerates a tracked release doc.
- Coverage cannot slide below 75% without failing the build.
- Operators gain `--project-root` on both release commands, so a release can be
  generated into a scratch directory for review before touching the repo.
- No schema changes, no new dependencies, no product features.
- The Quiet gatekeeper remains at 7.0 and low Vibrancy still never overrides a
  Quiet failure.

## Notes

The `exports_dir`/`output_dir` naming collision on `export_operations_digest`
remains. It is documented at the call site and in this record. If a third
parameter with directory semantics ever appears on that function, rename all of
them rather than adding another.
