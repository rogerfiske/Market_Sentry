# Market_Sentry 0.1.0-rc1

**Release type:** Local-only Release Candidate
**Generated:** 2026-05-14 17:22:54
**Commit:** f36600f

## Summary

Market_Sentry is a local-first property monitoring and analytics platform for the Puget Sound real estate market. This release candidate packages 50 milestones of development into a documented, validated, and audited local-only release.

## Major Capabilities

- Redfin fixture processing and candidate scoring
- Cross-site fixture processing and comparison (Zillow, Realtor.com, Homes.com, Compass)
- County verification and Effective DOM v2 with ownership transfer reset
- Quiet Score / Vibrancy scoring system (gatekeeper threshold 70.0)
- Monitoring snapshots and trend analysis
- Candidate review workflow with CSV import/export
- Alert lifecycle management (hygiene, triage, archive, expiration)
- Operations digest with history and comparison
- Portfolio review pack with trend visualization
- Portfolio trend alerts with configurable rules
- Alert history persistence and run comparison
- Alert focus preferences and dashboard focus views
- Local email digest draft export (no email sent)
- Local operations bundle and safety audit
- Release candidate documentation and validation
- Release finalization and GitHub release prep
- Streamlit dashboard for local analytical review
- Windows Task Scheduler integration for automated local reports

## Safety Guarantees

- **No outbound notifications**: No email, SMS, webhooks, or other outbound channels
- **No live retrieval by default**: Live HTTP retrieval requires explicit --force-live opt-in
- **No credentials stored**: No API keys, passwords, or tokens
- **No browser automation**: No Playwright, Selenium, or headless browser
- **Quiet Score gatekeeper unchanged**: Threshold remains at 70.0
- **Walkability excluded**: No walkability scoring per PM direction
- **Reports are analytical aids**: Not purchase recommendations
- **All exports are local files only**

## Local-Only Data Workflow

All property data enters the system through manually saved HTML fixtures or CSV imports. No automatic web scraping or browser automation occurs by default. Live Redfin retrieval is available but disabled by default and requires explicit opt-in with compliance configuration.

## No Live Retrieval Defaults

Scheduled scripts export local reports only. No scheduled task performs live retrieval, runs mutation commands, or sends outbound notifications unless explicitly configured by the operator.

## Effective DOM v2 and Churn Index

- **Effective DOM v1**: Listing-history-derived exposure without county reset integration
- **Effective DOM v2**: Applies county-confirmed ownership transfer as a reset boundary when appropriate
- **Churn Index**: Remains reportable even when Effective DOM is reset by ownership transfer

## Dashboard and Reporting Features

- Streamlit dashboard with candidate review, monitoring, alerts, portfolio, operations, and release status sections
- 20+ report types with CSV and Markdown export
- Operations digest with trend comparison
- Portfolio review pack with alert focus views
- Release candidate and finalization status

## Scheduled Local Reports

Windows Task Scheduler scripts for automated local-only report generation:

- Watchlist refresh and monitoring snapshots
- Alert lifecycle and trend reports
- Operations digest with comparison
- Portfolio review pack with alert focus
- Local operations bundle audit

All scripts write logs to `logs/scheduled/` and export to `data/exports/`.

## Known Limitations

- Live retrieval is disabled by default
- Email digest generates local draft files only; no email is sent
- No outbound notifications of any kind
- Walkability information is excluded per PM direction
- Reports are analytical aids, not purchase recommendations
- Cross-site fixture processing requires manually saved HTML files
- No automated testing against live websites

## Manual Release Checklist

- [ ] All tests pass (python -m pytest --tb=short --no-cov -q)
- [ ] README.md is up to date
- [ ] RUNBOOK.md reflects current commands
- [ ] Local operations bundle runs cleanly
- [ ] Smoke test passes
- [ ] Release candidate checklist reviewed
- [ ] Release notes reviewed and finalized
- [ ] No --force-live in scheduled scripts
- [ ] No outbound notification code present
- [ ] Create annotated tag: `git tag -a v0.1.0-rc1 -m "Market_Sentry v0.1.0-rc1"`
- [ ] Push tag: `git push origin v0.1.0-rc1`
- [ ] Create GitHub release with RELEASE_NOTES_FINAL.md

## License

See LICENSE file in repository.
