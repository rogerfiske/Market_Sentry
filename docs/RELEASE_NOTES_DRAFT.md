# Market Sentry - Release Notes Draft

Generated: 2026-05-14 17:22:49
Commit: f36600f

## Overview

Market Sentry is a local-first property monitoring and analytics platform for the Puget Sound real estate market. All operations run locally with no outbound notifications and no live retrieval by default.

## Key Features (Milestones 1-49)

- Redfin fixture processing and candidate scoring
- Cross-site fixture processing and comparison
- County verification and Effective DOM v2
- Quiet Score / Vibrancy scoring system
- Monitoring snapshots and trend analysis
- Candidate review workflow with CSV import/export
- Alert lifecycle management (hygiene, triage, archive, expiration)
- Operations digest with history and comparison
- Portfolio review pack with trend visualization
- Portfolio trend alerts with configurable rules
- Alert history persistence and run comparison
- Alert focus preferences and dashboard focus views
- Local email digest draft export (no email sent)
- Local operations bundle and release candidate hardening
- Streamlit dashboard for local analytical review
- Windows Task Scheduler integration for automated reports

## Safety Guarantees

- No outbound notifications (email, SMS, webhook)
- No live retrieval by default
- No credentials stored or requested
- No browser automation
- Quiet Score gatekeeper unchanged (threshold 70.0)
- Walkability information excluded
- Reports are analytical aids, not purchase recommendations
- All exports are local files only

## Release Candidate Status

- Checklist: 18 pass, 0 warn, 0 fail
- Validation: 6 pass, 1 warn, 0 fail
- Safe workflows: 17
- Caution workflows: 10

## Getting Started

```bash
# Initialize database
marketsentry init-db

# Run smoke test
marketsentry local-operations-smoke-test

# View operations bundle
marketsentry local-operations-bundle

# View release candidate status
marketsentry release-candidate-summary

# Launch dashboard
marketsentry dashboard
```

See `docs/RUNBOOK.md` for complete usage instructions.

## License

See LICENSE file in repository.
