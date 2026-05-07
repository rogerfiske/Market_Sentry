# Market_Sentry Live Retrieval Strategy

This document explains the compliance-aware source adapter architecture and live retrieval strategy for Market_Sentry.

## Current Status

**Live retrieval is disabled by default.** The current implementation provides:

- Source adapter architecture with compliance guardrails
- Dry-run preview commands (no network calls)
- Compliance configuration via environment variables
- Retrieval audit logging
- Adapter stubs for all supported sources

**No active live scraping, browser automation, or network calls are implemented.**

## Design Principles

1. **Safe by default.** Live retrieval is disabled unless explicitly enabled.
2. **Dry-run first.** Preview what would happen before any live access.
3. **Compliance-aware.** Every retrieval decision is checked against compliance rules.
4. **Auditable.** All retrieval decisions are logged to `logs/retrieval_audit/`.
5. **Swappable.** Adapters can be replaced with authorized API/feed implementations.
6. **No bypass.** Never bypass robots.txt, paywalls, login walls, anti-bot protections, CAPTCHAs, or technical access controls.
7. **No browser automation.** No Playwright, Selenium, or headless browser usage.

## Manual Fixtures: The Default Safe Workflow

The default and recommended workflow uses manually saved HTML fixtures:

1. User browses a real estate site in their browser.
2. User saves the page as HTML (File > Save As > Web Page, Complete).
3. User places the saved HTML file in the appropriate fixture directory.
4. Market_Sentry parses the saved HTML using existing fixture parsers.

This approach:

- Respects site terms of service (user is browsing normally)
- Does not require any automated access
- Provides deterministic, repeatable parsing
- Works offline after saving

## Retrieval Modes

| Mode | Network Calls | Description |
|------|--------------|-------------|
| `disabled` | None | All retrieval blocked |
| `dry_run` | None | Preview what would be retrieved |
| `manual_fixture` | None | Read from locally saved HTML files |
| `authorized_api` | Future | Use an authorized API or data feed |
| `live_http` | Future | Direct HTTP retrieval (requires explicit opt-in) |

## Compliance Configuration

Live retrieval is controlled by environment variables in `.env`:

```ini
# Master switch (must be "true" to enable any live retrieval)
MARKETSENTRY_LIVE_RETRIEVAL_ENABLED=false

# Comma-separated list of sources allowed for live retrieval
MARKETSENTRY_ALLOWED_LIVE_SOURCES=

# User-Agent string (required for live retrieval)
MARKETSENTRY_LIVE_USER_AGENT=

# Contact email for responsible disclosure
MARKETSENTRY_LIVE_CONTACT_EMAIL=

# Maximum requests per minute (conservative default)
MARKETSENTRY_MAX_REQUESTS_PER_MINUTE=6

# Require dry-run before any live retrieval
MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE=true
```

### Compliance Rules

A live retrieval request is **blocked** if any of these conditions are true:

1. `MARKETSENTRY_LIVE_RETRIEVAL_ENABLED` is not `true`
2. The source is not in `MARKETSENTRY_ALLOWED_LIVE_SOURCES`
3. `MARKETSENTRY_MAX_REQUESTS_PER_MINUTE` is 0
4. `MARKETSENTRY_LIVE_USER_AGENT` is not set

### Checking Compliance Status

```bash
marketsentry retrieval-compliance-status
```

This command shows all compliance settings, warnings, and whether live retrieval is blocked or potentially allowed. No network calls are performed.

## Dry-Run Commands

### Preview Redfin Search Retrieval

```bash
marketsentry dry-run-redfin-search --url "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house,min-price=550k,max-price=990k"
```

Shows:
- URL validation result
- What would be retrieved
- Whether it would be blocked in live mode and why
- No network call performed

### Preview Redfin Property Retrieval

```bash
marketsentry dry-run-redfin-property --url "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
```

Shows:
- URL validation result
- What data would be extracted
- Whether it would be blocked in live mode and why
- No network call performed

### List Source Adapters

```bash
marketsentry source-adapters
```

Shows all registered adapters, their current modes, and capabilities.

## Retrieval Audit Logs

All retrieval decisions are logged to `logs/retrieval_audit/` as CSV files:

```text
logs/retrieval_audit/retrieval_audit_20260506.csv
```

Each record contains:

| Field | Description |
|-------|-------------|
| `timestamp` | ISO 8601 timestamp |
| `source_site` | Adapter name (e.g., "redfin") |
| `retrieval_mode` | Mode used (e.g., "dry_run") |
| `url` | URL being accessed |
| `domain` | Domain being accessed |
| `allowed` | Whether the request was allowed |
| `blocked` | Whether the request was blocked |
| `reason` | Reason for the decision |
| `dry_run` | Whether this was a dry-run |
| `network_call_performed` | Whether a network call was made |

**In the current milestone, all records have `network_call_performed=False`.**

## Redfin Live HTTP Phase 1 (Milestone 16)

Milestone 16 adds the first actual HTTP retrieval capability, constrained to Redfin only.

### Scope

- **Redfin only.** No other sources are supported for live retrieval in this phase.
- **Disabled by default.** All environment variables must be explicitly configured.
- **Fixture-output only.** Retrieved HTML is saved as local fixtures, not parsed directly.
- **Rate-limited.** Enforced by the Milestone 15 rate limiter.
- **Robots-checked.** Local robots policy must be available and allow the path.
- **Dry-run-gated.** A recent dry-run approval is required before live retrieval.
- **Audited.** All retrieval decisions logged to `logs/retrieval_audit/`.
- **Never scheduled.** No scheduled task invokes live retrieval by default.

### Required Environment Variables

```ini
MARKETSENTRY_LIVE_RETRIEVAL_ENABLED=true
MARKETSENTRY_ALLOWED_LIVE_SOURCES=redfin
MARKETSENTRY_LIVE_USER_AGENT=MarketSentry/1.0
MARKETSENTRY_LIVE_CONTACT_EMAIL=user@example.com
MARKETSENTRY_MAX_REQUESTS_PER_MINUTE=6
MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE=true
```

### Local Robots Policy Requirement

Save Redfin's robots.txt locally before live retrieval:

```text
data/policies/robots/redfin_robots.txt
```

The system does NOT fetch robots.txt from the internet.

### Dry-Run Approval Requirement

Run a dry-run command first:

```bash
marketsentry dry-run-redfin-search --url "https://www.redfin.com/city/..."
marketsentry dry-run-redfin-property --url "https://www.redfin.com/CA/..."
```

### Rate Limit Requirement

The rate limiter enforces `MARKETSENTRY_MAX_REQUESTS_PER_MINUTE` (default: 6) and a minimum delay between requests (default: 10 seconds).

### Fixture Output Behavior

Retrieved HTML is saved to:

- Search: `data/raw/redfin/search/redfin_search_YYYYMMDD_HHMMSS.html`
- Detail: `data/raw/redfin/details/redfin_property_<id>_YYYYMMDD_HHMMSS.html`

Each fixture has a sidecar JSON metadata file with source URL, timestamps, and content length.

### Audit Logging

All retrieval decisions (blocked or allowed, dry-run or live) are logged to `logs/retrieval_audit/`.

For live retrievals, `network_call_performed=true` appears in audit records.

### How to Run Retrieve Commands

```bash
# Dry-run only (no network call)
marketsentry retrieve-redfin-search --url "..." --dry-run-only

# Live retrieval (requires full config + --force-live)
marketsentry retrieve-redfin-search --url "..." --force-live
marketsentry retrieve-redfin-property --url "..." --force-live
```

### How to Keep Using Manual Fixtures Instead

Manual fixtures remain the default and recommended workflow. Simply continue saving HTML pages manually to `data/raw/redfin/search/` and `data/raw/redfin/details/`, then parse them with existing commands.

See [REDFIN_LIVE_HTTP_PHASE_1.md](REDFIN_LIVE_HTTP_PHASE_1.md) for the complete Phase 1 guide.

## Future Live Retrieval Requirements

Before extending live retrieval to other sources, the following must be satisfied:

1. **robots.txt compliance.** Check and respect robots.txt for each domain.
2. **Rate limiting.** Enforce configured request rate limits.
3. **User-Agent identification.** Use a descriptive User-Agent string.
4. **Contact information.** Provide contact email for site operators.
5. **No bypass mechanisms.** Never bypass CAPTCHAs, login walls, paywalls, or anti-bot protections.
6. **Graceful degradation.** Handle HTTP errors, timeouts, and blocked responses gracefully.
7. **Audit trail.** Log all retrieval attempts with full details.
8. **Opt-in only.** Live retrieval must never be enabled by default.
9. **Authorized APIs preferred.** Use official APIs or data feeds when available.

## Why Authorized APIs/Feeds Are Preferred

For production use, authorized APIs and data feeds are preferred over HTTP scraping because they:

- Provide stable, documented interfaces
- Come with explicit permission to access data
- Offer structured data without HTML parsing
- Include rate limit guidelines
- Reduce legal and compliance risk

The source adapter architecture supports swapping between `manual_fixture`, `authorized_api`, and `live_http` modes without changing downstream code.

## Why Task Scheduler Should Not Run Live Retrieval by Default

Windows Task Scheduler automation (Milestone 13) runs existing local workflows. Scheduled tasks should **not** run live retrieval by default because:

1. Unattended live retrieval increases compliance risk
2. Scheduled tasks may run at unexpected times or frequencies
3. The user should explicitly enable and monitor live retrieval
4. Manual fixture workflows are sufficient for current monitoring needs

If live retrieval is implemented and enabled in a future milestone, scheduled tasks may optionally support it with additional safeguards (explicit opt-in, lower rate limits, extended logging).

## Retrieval Safety Enforcement (Milestone 15)

Milestone 15 hardens the compliance foundation from Milestone 14 with additional safety layers:

### Retrieval Policy Engine

Combines compliance checks, robots policy, rate limiting, and dry-run approval into a single policy decision. Use `marketsentry retrieval-policy-check` to evaluate.

### Offline Robots Policy

Parses locally saved robots.txt files from `data/policies/robots/`. Does NOT fetch robots.txt from the internet. Save a site's robots.txt to `data/policies/robots/{source}_robots.txt` for offline checking.

### Rate Limiter

Deterministic local rate limiter enforcing max requests per minute and minimum delay between requests. State is injectable and testable. No sleeping occurs in tests.

### Dry-Run Approval Gate

Requires a successful dry-run before any live retrieval attempt. Approval records are stored in `logs/retrieval_audit/dry_run_approvals_*.csv`.

### Fixture Capture Queue

When live retrieval is blocked (default), the system adds URLs to a local queue with suggested fixture paths. The user saves HTML manually and marks the request as captured.

See [FIXTURE_CAPTURE_QUEUE.md](FIXTURE_CAPTURE_QUEUE.md) for the complete guide.

### Retrieval Audit Report

```bash
marketsentry retrieval-audit-report
```

Summarizes all retrieval decisions from `logs/retrieval_audit/` including counts of allowed/blocked decisions, sources, modes, and reasons.
