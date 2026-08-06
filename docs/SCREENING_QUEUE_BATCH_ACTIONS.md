# Screening Queue Batch Actions

## Overview

Batch actions let you act on several screening items at once instead of running one command per property. They exist to reduce repetitive work when you have reviewed a page of Redfin links and already know what you want to do with each one.

Everything here is local-only. No live retrieval, no browser automation, no outbound notifications, no credential storage.

## When to Use Single vs Batch Actions

| Situation | Use |
|-----------|-----|
| Acting on one property | Single action (`save-screening-item-for-analysis`, `reject-screening-item`, `hold-screening-item`) |
| You reviewed several links and want the same outcome for all of them | Batch action |
| You want different outcomes per property | One batch per outcome: batch-save some, batch-reject others |
| You are unsure about a property | Hold it, single or batch |

Batch actions are not faster at deciding. They are faster at recording decisions you have already made.

## Finding Screening IDs

The ID is the first column in every screening view:

- Dashboard: the **ID** column of the `Initial Redfin Screening` table
- CLI: `marketsentry list-redfin-screening-items`
- Exports: the `screening_id` column in the CSV, or the `ID` column in the Markdown

## Entering Comma-Separated IDs

All batch commands take `--screening-ids` with a comma-separated list:

```powershell
python -m marketsentry.cli batch-save-screening-items --screening-ids 4,5,6
```

Spaces are tolerated, so `4, 5, 6` works the same way.

Input handling:

| Input | Behavior |
|-------|----------|
| `4,5,6` | All three are actioned |
| `4, 5, 6` | Same; whitespace is ignored |
| `4,5,4` | `4` is actioned once; the repeat is reported as a duplicate |
| `4,abc,6` | `4` and `6` are actioned; `abc` is reported as invalid |
| `4,999` | `4` is actioned; `999` is reported as not found |
| empty | Command exits with an error and changes nothing |

One bad ID never stops the rest. Every item gets its own success or failure line.

## The Four Batch Commands

```powershell
# Mark several links as opened after you clicked through them
python -m marketsentry.cli batch-mark-screening-items-opened --screening-ids 4,5,6

# Promote several items to the candidate review queue
python -m marketsentry.cli batch-save-screening-items --screening-ids 4,5 --notes "Batch save after visual review"

# Reject several items
python -m marketsentry.cli batch-reject-screening-items --screening-ids 7,8 --notes "Does not fit screening criteria"

# Hold several items for later
python -m marketsentry.cli batch-hold-screening-items --screening-ids 9,10 --notes "Needs more review"
```

Notes are appended to any existing notes on each item, never overwritten. Your local field knowledge is preserved.

## What Save for Analysis Does

`Save for Analysis` is the single transition point from screening to candidate:

1. Creates a candidate in `candidate_review_queue`, or links to an existing candidate when the Redfin URL already exists.
2. Marks the screening item as `saved_for_analysis`.
3. Records the linked `candidate_id` on the screening item.
4. Appends any notes you supplied.

## What Save for Analysis Does Not Do

- It does **not** fetch anything from Redfin.
- It does **not** duplicate a candidate that already exists for the same URL.
- It does **not** overwrite enrichment, Quiet/Vibrancy, or other source-of-truth fields on an existing candidate.
- It does **not** promote anything to the watchlist. That still requires an explicit `candidate-decision --decision save`.
- It does **not** happen automatically. Importing URLs never creates candidates; only this explicit action does.

## Seeing What To Do Next

```powershell
python -m marketsentry.cli screening-next-steps
```

This reads the screening queue and the candidate queue and tells you the next data-gathering step. It never recommends buying, offering on, or valuing a property.

Typical progression:

```text
New screening items          -> open the Redfin link and visually inspect
Opened but undecided         -> Save for Analysis, Hold, or Reject
Saved but no detail HTML     -> save the Redfin detail page and run enrichment
Candidate missing scores     -> capture and enter Quiet/Vibrancy
Candidate fails Quiet gate   -> add local noise notes, or hold/reject as noise-risk control
Watchlist ready              -> run the operator refresh workflow
```

The same panel appears in the dashboard under `Initial Redfin Screening`, along with warnings about missing enrichment, missing scores, leftover demo records, and stray database files.

Next-step messages name the specific candidates behind each count, so you know
which property to open rather than only how many are outstanding.

## After Saving: Entering Scores

Batch Save for Analysis creates candidates but does not score them. Quiet and
Vibrancy are read visually from the Redfin page by you and typed in:

```powershell
python -m marketsentry.cli list-candidates-needing-scores
python -m marketsentry.cli candidate-score-and-noise-notes --candidate-id 7 --quiet-score 9.9 --vibrancy-score 1.3
```

See `docs/MANUAL_SCORE_ENTRY.md` for the full guide, including where the scores
appear on the Redfin page and why a low Vibrancy score never rescues a Quiet
score below 7.0.

## Refreshing Reports After Saving

Both the single and batch Save for Analysis commands accept an optional refresh:

```powershell
# Default: no refresh
python -m marketsentry.cli batch-save-screening-items --screening-ids 4,5

# Save, then regenerate all local reports
python -m marketsentry.cli batch-save-screening-items --screening-ids 4,5 --refresh
```

The default is `--no-refresh` because the refresh workflow regenerates every local report and is noticeably slower than the save itself. Use `--refresh` when you are done with a screening pass and want the dashboard and reports current.

If the refresh fails, the saves that already succeeded are **not** rolled back. The command reports the refresh error separately so you can rerun `run-operator-refresh-workflow` on its own.

In the dashboard, the same option is the **Run local refresh after Save for Analysis** checkbox on the Batch Save form.

## Dashboard Batch Forms

The `Initial Redfin Screening` section has four batch forms:

- Batch Save for Analysis (with notes and the refresh checkbox)
- Batch Reject (with notes)
- Batch Hold (with notes)
- Batch Mark Opened

Each takes the same comma-separated ID list and reports per-item results. Loading the dashboard never mutates anything; only submitting a form does.

## Cleaning Demo Data First

Sample records seeded for testing make the queue and next-step counts noisier. Clear them before an operator session:

```powershell
python -m marketsentry.cli cleanup-demo-data            # preview
python -m marketsentry.cli cleanup-demo-data --confirm  # apply
```

Real properties are protected by an explicit denylist and cannot be removed by this command. See the README troubleshooting section for details.

## Why No Live Scraping Is Involved

Batch actions only read and write the local SQLite database. Property data still comes from:

- CSV files you create manually
- Redfin HTML pages you save manually from your browser

Marking an item as "opened" records that *you* clicked the link. It does not open a browser, drive one, or fetch the page. No HTTP request is made to Redfin or any other site, and no CAPTCHA, login, paywall, or anti-bot protection is bypassed.

## Safety Summary

- All operations read and write only the local database
- No network connections
- No credentials stored or requested
- No notifications sent
- No browser automation
- Quiet Score gatekeeper unchanged at 7.0
- Low Vibrancy never overrides a poor Quiet score
- Walkability fields are not added
- Next steps are analytical guidance, not purchase recommendations
