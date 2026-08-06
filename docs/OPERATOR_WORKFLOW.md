# Operator Workflow Guide

## Overview

The operator workflow provides a simplified way to manage candidate properties without editing CSV files or copying complex commands. All operations are local-only and do not perform live retrieval, send notifications, or access external services.

## Checking Current Status

To see a summary of all candidates, missing data, and recommended next actions:

```bash
marketsentry operator-workflow-status
```

This shows:

- Total candidates and their review status counts
- How many candidates are missing Quiet or Vibrancy scores
- How many candidates are missing price data
- How many candidates need a review decision
- Active watched properties count
- Latest generated report paths
- Recommended next actions with example commands

## Updating Candidate Decisions

Instead of editing a CSV file and importing decisions, you can apply decisions directly:

```bash
# Save a candidate (promotes to watchlist automatically)
marketsentry candidate-decision --candidate-id 4 --decision save --notes "Good Quiet/Vibrancy profile"

# Mark as maybe (keep for further evaluation)
marketsentry candidate-decision --candidate-id 5 --decision maybe --notes "Need more noise data"

# Reject a candidate
marketsentry candidate-decision --candidate-id 3 --decision reject --notes "Price too high for area"

# Hold for more data
marketsentry candidate-decision --candidate-id 6 --decision hold_for_more_data --notes "Waiting for Redfin detail enrichment"
```

### What Each Decision Means

| Decision | What Happens | When to Use |
|----------|-------------|-------------|
| **save** | Marks as saved and promotes to the watchlist for ongoing monitoring | You want to actively track this property |
| **reject** | Marks as rejected, no further action | Property does not meet your criteria |
| **maybe** | Marks as maybe, stays in candidate queue | Interested but need more information or time |
| **hold_for_more_data** | Marks as hold, stays in candidate queue | Missing key data like Quiet/Vibrancy scores or enrichment |

### Important Notes

- **save** automatically promotes the candidate to the watchlist. If the candidate is already on the watchlist, it will not create a duplicate.
- Notes are appended to any existing notes, not overwritten.
- All actions are logged in the review actions table for audit tracking.

## Entering Quiet and Vibrancy Scores

Instead of editing a CSV, enter scores directly from the command line:

```bash
marketsentry candidate-location-scores --candidate-id 4 --quiet-score 9.9 --vibrancy-score 1.3 --notes "Verified from Redfin detail page"
```

### How Scores Work

- **Quiet Score**: 0 to 10 scale. Higher is quieter (better). The gatekeeper threshold is 7.0.
- **Vibrancy Score**: 0 to 10 scale. Lower is less vibrant (better for quiet neighborhoods).
- Scores of Quiet >= 7.0 pass the gatekeeper. Scores below 7.0 are flagged as noise risk.
- A low Vibrancy score does NOT override a poor Quiet score. Both are evaluated independently.
- If the candidate has already been promoted to the watchlist, the watched property scores are also updated.

## Recording Noise Concerns

If you have local knowledge about noise at a property (traffic, airport flight paths, racing, etc.), record it:

```bash
marketsentry candidate-noise-notes --candidate-id 5 --noise-risk moderate --noise-sources "traffic,airport" --notes "Local knowledge suggests possible traffic/airport noise exposure despite Redfin Quiet 6.9"
```

### Noise Risk Levels

| Level | Meaning |
|-------|---------|
| **low** | Minimal noise concerns |
| **moderate** | Some noise indicators present |
| **high** | Significant noise concerns |
| **severe** | Major noise issues identified |
| **unknown** | Not enough data to assess |

### Supported Noise Sources

- traffic
- airport
- nighttime_racing
- arterial_road
- topography
- unknown

Noise notes are stored in the candidate's notes field. They do not add walkability fields or make purchase recommendations. They record your local field knowledge as an analytical observation, not a seller-intent inference.

## Running the Refresh Workflow

To update all local reports in the correct order with a single command:

```bash
marketsentry run-operator-refresh-workflow
```

This runs:

1. Recalculate candidate scores
2. Persist Effective DOM v2 if available
3. Snapshot watchlist observations
4. Export watchlist monitoring report
5. Export candidate analysis report
6. Export operations digest
7. Export portfolio review pack
8. Export local operations bundle

The command:

- Does NOT run live retrieval or scraping
- Does NOT import review decisions automatically
- Does NOT change candidate decisions
- Does NOT send notifications
- Reports warnings instead of crashing when a non-critical step fails
- Tolerates empty or missing optional tables

All commands default to the project database at `db/marketsentry.db`. You do not need to add `--db db\marketsentry.db` unless you are intentionally using a custom database.

## Exporting an Action Summary

To export a summary of current status, missing data, and recommended actions:

```bash
# Export both Markdown and CSV
marketsentry export-operator-action-summary --format both

# Export to a custom directory
marketsentry export-operator-action-summary --output-dir reports/workflow --format both
```

Reports are saved to `data/exports/` by default.

## Using the Dashboard

The Streamlit dashboard includes an **Operator Workflow** section with:

- Status metrics (total, pending, maybe, saved, rejected, hold, watched, missing scores)
- Tables showing candidates needing action, missing Quiet/Vibrancy, and pending/hold/maybe candidates
- Latest generated reports list
- Recommended actions with commands

### Dashboard Action Forms

The dashboard provides four action forms so you can manage candidates without using the command line:

1. **Update Candidate Decision** - Select a candidate ID, choose a decision, add optional notes, and click Apply.
2. **Update Quiet/Vibrancy** - Enter scores for a candidate and click Apply.
3. **Add Noise Notes** - Record noise observations with risk level and sources.
4. **Run Refresh Workflow** - Click one button to regenerate all local reports.

To launch the dashboard:

```bash
streamlit run src/marketsentry/dashboard_app.py
```

## How This Differs from Live Retrieval

The operator workflow is entirely local. It:

- Reads and writes only to the local SQLite database
- Does not connect to Redfin, Zillow, or any external website
- Does not use a browser or web scraper
- Does not send emails, SMS, or webhook notifications
- Does not bypass any access controls

All data displayed comes from previously saved local files and database records. To add new properties, you can use the Redfin Screening Queue (see below) or import Redfin URLs from CSV and parse saved HTML detail pages using the existing import and enrichment commands.

## Redfin Screening Queue

Before adding properties as full candidates, you can triage them through the screening queue. See `docs/REDFIN_SCREENING_QUEUE.md` for the full guide.

The screening queue workflow:

1. Import Redfin URLs via CSV or saved search fixture HTML.
2. Review properties in the dashboard or CLI with clickable Redfin links.
3. Save promising properties for analysis (creates candidates).
4. Reject or hold properties that do not meet criteria.

Quick screening commands:

| Task | Command |
|------|---------|
| Import screening URLs | `marketsentry import-redfin-screening-urls --file <csv>` |
| Import search fixture | `marketsentry import-redfin-screening-fixture --file <html>` |
| Screening status | `marketsentry redfin-screening-status` |
| List screening items | `marketsentry list-redfin-screening-items` |
| Save for analysis | `marketsentry save-screening-item-for-analysis --screening-id <id>` |
| Reject | `marketsentry reject-screening-item --screening-id <id>` |
| Hold | `marketsentry hold-screening-item --screening-id <id>` |
| Mark opened | `marketsentry mark-screening-item-opened --screening-id <id>` |
| Export queue | `marketsentry export-redfin-screening-queue` |

## Batch Screening Actions

When you have reviewed several Redfin links at once, record all the decisions
together instead of running one command per property:

```bash
marketsentry batch-mark-screening-items-opened --screening-ids 4,5,6
marketsentry batch-save-screening-items --screening-ids 4,5 --notes "Batch save after visual review"
marketsentry batch-reject-screening-items --screening-ids 7,8 --notes "Does not fit criteria"
marketsentry batch-hold-screening-items --screening-ids 9,10 --notes "Needs more review"
```

Find the IDs in the **ID** column of the dashboard screening table or in
`marketsentry list-redfin-screening-items`.

Each item reports its own result. An invalid, duplicate, or missing ID is
reported and skipped without stopping the rest of the batch. Notes are appended
to existing notes, never overwritten.

| Task | Command |
|------|---------|
| Batch save for analysis | `marketsentry batch-save-screening-items --screening-ids 4,5,6` |
| Batch reject | `marketsentry batch-reject-screening-items --screening-ids 4,5,6` |
| Batch hold | `marketsentry batch-hold-screening-items --screening-ids 4,5,6` |
| Batch mark opened | `marketsentry batch-mark-screening-items-opened --screening-ids 4,5,6` |
| What to do next | `marketsentry screening-next-steps` |

The dashboard exposes the same four actions as forms in the
**Initial Redfin Screening** section, plus a **Next Steps** panel.

See `docs/SCREENING_QUEUE_BATCH_ACTIONS.md` for the full guide.

## Knowing What To Do Next

```bash
marketsentry screening-next-steps
```

Reads the screening and candidate queues and reports the next data-gathering
step: inspect new links, decide on opened items, save Redfin detail HTML and run
enrichment, enter Quiet/Vibrancy scores, address noise-risk candidates, or run
the refresh workflow. It also warns about leftover demo records and stray
database files.

This is read-only guidance for gathering data. It never makes purchase
recommendations and never mutates state.

## Refreshing Reports After Saving

Both the single and batch Save for Analysis commands accept an optional refresh:

```bash
# Default: fast, no report regeneration
marketsentry batch-save-screening-items --screening-ids 4,5

# Save, then regenerate all local reports
marketsentry batch-save-screening-items --screening-ids 4,5 --refresh
```

The default is `--no-refresh` because the refresh regenerates every local report
and is much slower than the save itself. If a refresh fails, the saves that
already succeeded are **not** rolled back; rerun
`marketsentry run-operator-refresh-workflow` on its own.

## Quick Reference

| Task | Command |
|------|---------|
| Check status | `marketsentry operator-workflow-status` |
| Save a candidate | `marketsentry candidate-decision --candidate-id <id> --decision save` |
| Reject a candidate | `marketsentry candidate-decision --candidate-id <id> --decision reject` |
| Maybe a candidate | `marketsentry candidate-decision --candidate-id <id> --decision maybe` |
| Hold for data | `marketsentry candidate-decision --candidate-id <id> --decision hold_for_more_data` |
| Enter scores | `marketsentry candidate-location-scores --candidate-id <id> --quiet-score <q> --vibrancy-score <v>` |
| Add noise notes | `marketsentry candidate-noise-notes --candidate-id <id> --noise-risk <level> --noise-sources "<sources>"` |
| Refresh all reports | `marketsentry run-operator-refresh-workflow` |
| Export summary | `marketsentry export-operator-action-summary --format both` |

## Cleaning Up Demo and Sample Data

Sample records seeded for testing appear alongside your real properties and make
the status screens noisier. Remove them safely:

```bash
# Preview only. This is the default; nothing is changed.
marketsentry cleanup-demo-data

# Apply the cleanup
marketsentry cleanup-demo-data --confirm
```

The command is dry-run by default. It only selects records matching a fixed list
of demo marker addresses (`12345 Sample St`, `67890 Busy Ave`, `11111 Unknown Rd`,
`40000 Example St`, `30000 Sample Ave`, `55555 Fixture Ln`). Your real properties
are protected by an explicit denylist that is checked again immediately before
every deletion, so they cannot be removed even by accident.

Stray files are reported but never deleted unless you add `--confirm-stray-files`.

## Troubleshooting

If status shows zero candidates unexpectedly, run `python -m marketsentry.cli status` and confirm database path.

All commands default to `db/marketsentry.db`, resolved from `config.database_path`.
As of Milestone 52A this applies to every command in the project, not just the
operator workflow commands. If you see errors about missing tables, verify you are
running from the project root directory and that the database file exists at
`db/marketsentry.db`.

### Stray database files

If you see `data/market_sentry.db`, `dbmarketsentry.db`, or `nul` in the project
folder, these are artifacts and hold no real data:

| File | Cause |
|------|-------|
| `data/market_sentry.db` | Legacy wrong default, corrected in Milestone 52A |
| `dbmarketsentry.db` | `--db db\marketsentry.db` where the backslash was consumed as a shell escape |
| `nul` | A Windows-style `2>nul` redirect run under a POSIX shell such as Git Bash |

Run `marketsentry cleanup-demo-data` to see which are present. To avoid recreating
them, quote Windows paths or use forward slashes:

```powershell
python -m marketsentry.cli status --db "db\marketsentry.db"
python -m marketsentry.cli status --db db/marketsentry.db
```
