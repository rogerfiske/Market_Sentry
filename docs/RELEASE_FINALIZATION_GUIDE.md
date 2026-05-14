# Release Finalization Guide

## Overview

The release finalization module produces the final release candidate package including version metadata, artifact inventory, readiness checks, manual GitHub release commands, and final release notes. All output is local file only.

## CLI Commands

### View Release Finalization Summary

```bash
# Show finalization summary
marketsentry release-finalization-summary

# With custom version
marketsentry release-finalization-summary --version 0.1.0-rc1
```

### Export Release Finalization Report

```bash
# Export Markdown and CSV reports
marketsentry export-release-finalization-report --format both

# Export to custom directory
marketsentry export-release-finalization-report --output-dir reports/finalization --format both
```

### View Manual GitHub Release Commands

```bash
# Show exact manual commands (not executed)
marketsentry release-manual-github-commands

# With custom version
marketsentry release-manual-github-commands --version 0.1.0-rc1
```

## Release Workflow

### Step 1: Run Finalization Summary

Run `marketsentry release-finalization-summary` to check readiness status. All checks should pass or warn (no failures).

### Step 2: Export Finalization Report

Run `marketsentry export-release-finalization-report` to generate:
- `data/exports/release_finalization_YYYYMMDD_HHMMSS.md` - Markdown report
- `data/exports/release_finalization_YYYYMMDD_HHMMSS.csv` - CSV report
- `docs/RELEASE_NOTES_FINAL.md` - Final release notes

### Step 3: Review Release Notes

Review `docs/RELEASE_NOTES_FINAL.md` and edit if needed before creating the GitHub release.

### Step 4: Run Manual GitHub Commands

View the exact commands with `marketsentry release-manual-github-commands`, then execute them manually:

```bash
git status
git log -1 --oneline
git tag -a v0.1.0-rc1 -m "Market_Sentry v0.1.0-rc1"
git push origin v0.1.0-rc1
gh release create v0.1.0-rc1 --title "Market_Sentry v0.1.0-rc1" --notes-file docs/RELEASE_NOTES_FINAL.md
```

## Readiness Checks

The finalization module runs 13 readiness checks:

| Check | Description |
|-------|-------------|
| tests_command_documented | Full test command documented |
| rc_checklist_exists | Release candidate checklist present |
| release_notes_draft_exists | Draft release notes present |
| ops_bundle_docs_exist | Operations bundle docs present |
| no_force_live_in_scripts | No --force-live in scheduled scripts |
| no_live_retrieval_in_scripts | No live retrieval in scripts |
| no_notification_in_scripts | No outbound notifications in scripts |
| no_browser_automation | No browser automation dependencies |
| no_walkability_fields | No walkability fields introduced |
| quiet_gatekeeper_unchanged | Quiet Score threshold unchanged |
| no_auto_github_release | No automatic GitHub release/tag |
| version_metadata_exists | Version metadata present |
| current_commit_captured | Current git commit available |

## Artifact Inventory

The finalization module inventories 14 release-relevant files and directories including documentation, build configuration, source code, tests, and scripts.

## Export Files

Reports export to:

```
data/exports/release_finalization_YYYYMMDD_HHMMSS.md
data/exports/release_finalization_YYYYMMDD_HHMMSS.csv
```

The export also generates `docs/RELEASE_NOTES_FINAL.md`.

## Safety Limitations

- The finalization module is read-only and does not mutate candidate, watchlist, or alert state
- No GitHub release or tag is created automatically
- No outbound notifications are sent (email, SMS, webhook)
- No live retrieval is performed
- No credentials are stored or requested
- No Redfin source-of-truth fields are overwritten
- No Quiet Score gatekeeper modifications
- No walkability fields are referenced
- No browser automation is used
- Manual GitHub commands are generated but not executed
