# Market_Sentry

Buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties.

## Project Mission

Market_Sentry is a disciplined market observation tool that helps buyers identify residential properties with significant market exposure patterns. The system begins with candidate discovery, stages candidates for user review, and monitors selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, and cross-site validation.

## Current Milestone: Screening Queue Batch Actions (MVP 53)

Batch actions and next-step guidance for the Redfin screening queue, so a whole
review pass can be recorded in one command instead of one command per property.

- 4 batch actions: save for analysis, reject, hold, mark opened
- Comma-separated ID input (`--screening-ids 4,5,6`); invalid, duplicate, and missing IDs are reported and skipped without stopping the batch
- Per-item success/failure reporting
- New `screening-next-steps` command and dashboard panel showing the next required data-gathering step
- Optional `--refresh` on single and batch Save for Analysis, defaulting to `--no-refresh`
- A refresh failure never rolls back saves that already succeeded
- Screening export now carries candidate enrichment, scoring, watchlist status, and a per-item next step
- Dashboard batch forms with notes and a refresh checkbox
- Save for Analysis remains the single explicit screening-to-candidate transition; imports still never create candidates
- No live retrieval, browser automation, outbound notifications, or credential storage
- Quiet Score gatekeeper unchanged at 7.0. Walkability remains excluded.

See [docs/SCREENING_QUEUE_BATCH_ACTIONS.md](docs/SCREENING_QUEUE_BATCH_ACTIONS.md).

### MVP 52A: Global Database Default Stabilization

This stabilization milestone completes the MVP 51A database-default fix across
the whole codebase and adds safe demo/sample cleanup.

- All live code now resolves the database from `config.database_path` (`db/marketsentry.db`)
- Fixed 9 CLI command defaults that pointed at the legacy `data/market_sentry.db` path
- Fixed module-level defaults in `dashboard_app.py`, `release_candidate.py`, `local_operations_bundle.py`
- Corrected 9 stale `--db` examples in the RUNBOOK and feature docs
- New command: `marketsentry cleanup-demo-data` (dry-run by default, `--confirm` to apply)
- Demo cleanup protects real user properties with an explicit denylist checked before every deletion
- Stray artifact detection for `nul`, `dbmarketsentry.db`, `data/market_sentry.db` (never deleted without `--confirm-stray-files`)
- No live retrieval, browser automation, outbound notifications, or credential storage added
- Quiet Score gatekeeper unchanged. Walkability remains excluded.

See [Troubleshooting: Database Paths and Stray Files](#troubleshooting-database-paths-and-stray-files).

### MVP 52: Initial Redfin Screening Queue

Clickable Redfin screening queue with Save for Analysis promotion to the candidate review queue.

### MVP 51A: Operator Workflow Stabilization

Operator workflow commands default to `db/marketsentry.db`; refresh workflow function calls stabilized.

### MVP 51: Guided Operator Workflow

Guided operator workflow commands and dashboard candidate action buttons.

### MVP 44: Configurable Portfolio Trend Alert Rules

This milestone makes Milestone 43 threshold rules configurable without code changes.

- JSON config file: `config/portfolio_trend_alert_rules.json` (optional)
- Example template: `config/portfolio_trend_alert_rules.example.json`
- Merge mode: custom rules appended after built-in defaults
- Replace mode: only custom rules are used
- Validation: rule_id uniqueness, scope/comparison/severity allowed values, forbidden walkability/live_retrieval metrics, built-in override prevention
- Disabled rules: valid in config but not evaluated
- Comparison operators: >=, >, <=, <, ==, !=, delta>=, delta<=
- CLI: `marketsentry list-portfolio-trend-alert-rules`, `marketsentry write-portfolio-trend-alert-rule-template`, `marketsentry validate-portfolio-trend-alert-rules`
- CLI updates: `portfolio-trend-alerts` and `export-portfolio-trend-alert-digest` now accept `--rule-config`
- Dashboard: rule configuration visibility with built-in count, custom config status, active rule count
- Configurable rules are entirely read-only: no mutations to candidate, watchlist, alert, or property state
- No outbound notifications sent. No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 43: Portfolio Trend Threshold Alerts

- Aggregate review burden threshold alerts (score >= 60 warning, >= 80 high)
- Aggregate burden increase alerts (delta >= 15)
- Burden label worsening alerts (to elevated_burden or high_burden)
- Degraded property trend alerts
- Rising immediate/high review backlog alerts
- Rising high/critical alert burden alerts
- Rising lifecycle attention/needs_review burden alerts
- Worsening cross-site confidence trend alerts
- High churn trend alerts
- Lifecycle health score drop and label worsening alerts
- Open alert count increase and Effective DOM v2 increase alerts
- Local notification-style Markdown and CSV digest export
- CLI: `marketsentry portfolio-trend-alerts`, `marketsentry export-portfolio-trend-alert-digest`
- Dashboard: Portfolio Trend Alerts subsection with severity counts, aggregate alerts table, property alerts table
- Scheduled script updated: `scripts/run_portfolio_review_pack_report.bat` now runs pack, comparison, trends, and alert digest
- Trend alerts are entirely read-only: no mutations to candidate, watchlist, alert, or property state
- No outbound notifications sent. No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 42: Portfolio Review Pack Trend Visualization

- Discover and load all portfolio review pack CSV exports chronologically
- Portfolio-level trend series: property counts, priority counts, lifecycle health, alert burden, DOM/churn/confidence averages per pack
- Per-property trend series: first/latest seen, label changes, metric deltas (health score, alerts, DOM v2, churn, confidence), trend direction
- Aggregate review burden score (0-100): low_burden, moderate_burden, elevated_burden, high_burden
- Trend directions: improved, degraded, stable, new, insufficient_data
- Export trend reports to CSV and/or Markdown with portfolio_summary and property_trend row types
- CLI: `marketsentry portfolio-review-trends`, `marketsentry export-portfolio-review-trends`
- Dashboard: Portfolio Review Trends subsection with burden metrics, portfolio trend table, property trend table
- Trends are entirely read-only: no mutations to candidate, watchlist, alert, or property state
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 41: Portfolio Review Pack Comparison

- Compare current review pack CSV to previous review pack CSV
- Detect per-property changes: added, removed, priority change, lifecycle health change, alert burden change, Effective DOM movement, Churn Index movement, cross-site confidence change
- Material change thresholds: score >= 5, DOM >= 14 days, churn >= 1.0, confidence >= 10
- Trend labels: improved, degraded, changed, unchanged, new, removed
- Summary metrics with aggregate counts for all change categories
- Export comparison report to CSV and/or Markdown
- CLI: `marketsentry compare-portfolio-review-packs`, `marketsentry export-portfolio-review-comparison`
- Dashboard: Portfolio Review Comparison subsection with change metrics and property changes table
- Comparison is entirely read-only: no mutations to candidate, watchlist, alert, or property state
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 40: Portfolio Review Pack

- Portfolio-level summary with watched property counts, Quiet gatekeeper pass/fail, gas/garage evidence, county reset, churn, DOM delta, cross-site, and alert/lifecycle metrics
- Per-property briefs with Quiet/Vibrancy scores, Effective DOM v1/v2, Churn Index, cross-site confidence, alert burden, lifecycle health, and review priority
- Review priority ranking: immediate_review, high_review, normal_review, monitor, low_current_activity
- Local next action generation from brief metrics
- Export to Markdown and/or CSV
- CLI: `marketsentry portfolio-review-pack`, `marketsentry export-portfolio-review-pack`
- Dashboard: Portfolio Review Pack subsection with summary metrics, priority table, and property brief table
- Scheduled script: `scripts/run_portfolio_review_pack_report.bat`
- Review pack is entirely read-only: no mutations to candidate, watchlist, alert, or property state
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 39: Operations Digest Historical Snapshots

- Append-only `operations_digest_snapshots` table with 34 metric columns
- Digest score (0-100) and status labels: clear, light_review, active_review, heavy_review, backlog_attention
- Material change detection with same-day/no-change skip and --force override
- Snapshot-over-snapshot comparison report export to CSV and/or Markdown
- CLI: `marketsentry snapshot-operations-digest`, `marketsentry export-operations-digest-comparison-report`, `marketsentry operations-digest-history-summary`
- Dashboard: Operations Digest History subsection with score metrics, trend deltas, and comparison report link
- Scheduled script updated: `scripts/run_operations_digest_report.bat` now runs digest export, snapshot, and comparison report
- Digest history is append-only and read-only: no mutations to candidate, watchlist, alert, or property state
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 38: Watchlist Operations Digest

- Consolidates candidate review, watchlist, Effective DOM, cross-site, alert/hygiene, lifecycle health, and retrieval metrics into one digest
- Property review priority ranking: immediate_review, high_review, normal_review, monitor
- Recommended next local actions generated from digest metrics
- Export to Markdown and/or CSV
- CLI: `marketsentry operations-digest`, `marketsentry export-operations-digest`
- Dashboard: Operations Digest subsection with section expanders, priority table, and next actions
- Scheduled script: `scripts/run_operations_digest_report.bat`
- Operations digest is entirely read-only: no mutations to candidate, watchlist, alert, or property state
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 37: Lifecycle Health Trend Snapshots and Scheduled Health Reports

- Append-only lifecycle health snapshots with material change detection
- Trend change analysis: improved, degraded, stable, new
- Lifecycle health trend report export to CSV
- CLI: `marketsentry snapshot-cross-site-lifecycle-health`, `marketsentry export-cross-site-lifecycle-health-trend-report`, `marketsentry cross-site-lifecycle-health-trend-summary`
- Scheduled script: `scripts/run_lifecycle_health_report.bat`
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 33: Profile Comparison and Last-Used Profile Preference

- Side-by-side profile comparison views with candidate/action counts per profile
- Two-profile diff with deltas
- Last-used profile preference persisted locally
- Existing commands auto-resolve to last-used profile when --profile omitted
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 32: User-Defined Alert Expiration Profiles

- User-defined local expiration profiles loaded from JSON config file
- Built-in profiles (conservative, standard, aggressive_review_only) always available
- Config validated: profile_name required/unique, rule_name unique within profile, valid statuses/severities/actions
- User profiles cannot silently override built-in profiles
- Invalid configs rejected with clear errors; built-in profiles remain usable
- New CLI: `marketsentry write-alert-expiration-profile-template`
- Updated CLI: `--profile-config` option on list-profiles, preview, export, summary commands
- Dashboard shows built-in and detected custom profiles with validation status
- Example config: `config/alert_expiration_profiles.example.json`
- Custom profiles do not auto-apply: all mutations require operator-reviewed approval import
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 31: Configurable Alert Expiration Rules and Operator Approval Gates

- 3 built-in profiles: conservative, standard, aggressive_review_only
- Age-based rules identify resolved (archive candidate), acknowledged (review), open info/warning (review) alerts
- High/critical open alerts are review-only (never auto-archive candidates)
- Export approval CSV: `data/exports/cross_site_alert_expiration_approval_YYYYMMDD_HHMMSS.csv`
- 7 approval decisions: approve_action, keep_current, mark_no_archive, reopen, acknowledge, resolve, archive
- Default approval_decision is keep_current (no change without explicit operator decision)
- `[no_archive]` marked alerts excluded from archive proposals
- Actions recorded in triage actions table for audit trail
- Expiration policy does not auto-apply: all mutations require operator-reviewed approval import
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 30: Opt-In Resolved Alert Archive Policy Workflow

- Opt-in archive policy for old resolved cross-site alerts
- 4 archive decisions: keep_resolved, archive, reopen, no_archive
- Export/import CSV workflow with action history
- No auto-archive. No watchlist status change.
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 29: Scheduled Triage Reminder and Alert Hygiene Reports

- Alert hygiene checks and scheduled report generation for cross-site trend alerts
- Identify stale open alerts, old acknowledged alerts, resolved archive candidates
- Configurable thresholds, CSV and Markdown report export
- Scheduled batch script: `scripts/run_alert_hygiene_report.bat`
- Dashboard: Cross-Site Alert Hygiene subsection
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 28: Cross-Site Alert Triage Workflow

- CSV-based triage workflow for managing accumulated cross-site trend alerts
- 6 triage decisions: keep_open, acknowledge, resolve, archive, needs_reparse, needs_manual_review
- Only acknowledge/resolve/archive change alert status; others record notes only
- Triage history table for audit trail
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 27: Cross-Site Alert Aggregation and Historical Pattern Analysis

- Property-level alert burden scoring and labels (none/low/moderate/high/elevated_review)
- 8 repeated pattern types, patterns require 2+ events
- CLI: `marketsentry cross-site-alert-analytics-summary`, `export-cross-site-alert-analytics-report`
- Dashboard: Cross-Site Alert Analytics subsection
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 26: Cross-Site Trend Alerts and Watchlist Monitoring Integration

- Cross-site trend alerts with alert lifecycle (open/acknowledged/resolved/archived)
- 12 alert types, 4 severity levels, centralized rules, deduplication
- Alert lifecycle management: acknowledge and resolve with notes
- CLI: `marketsentry generate-cross-site-trend-alerts`, `list-cross-site-trend-alerts`, `acknowledge-cross-site-trend-alert`, `resolve-cross-site-trend-alert`, `export-cross-site-trend-alerts-report`
- Dashboard: Cross-Site Trend Alerts subsection
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 25: Cross-Site Analytics Trend Snapshots

- Point-in-time snapshot persistence and trend tracking for cross-site analytics
- Material change detection, trend direction classification, recommended next actions
- CLI: `marketsentry snapshot-cross-site-analytics`, `marketsentry export-cross-site-trend-report`
- Dashboard trends subsection

### MVP 24: Confidence-Weighted Cross-Site Analytics

- Confidence-weighted agreement scores for price, status, DOM, garage, and gas
- Source freshness scoring (observations age out: 0-7d=1.0, 8-30d=0.8, 31-90d=0.5, >90d=0.2)
- Source completeness scoring based on field availability
- Overall cross-site confidence score (25% freshness + 25% completeness + 50% agreement)
- Discrepancy severity scoring (none/low/medium/high/critical) with neutral language
- Low-confidence sources are downweighted, not exaggerated
- Manual review priority (none/low/medium/high) based on severity and confidence
- New CLI: `marketsentry export-cross-site-analytics-report`
- New report: `data/exports/cross_site_analytics_YYYYMMDD_HHMMSS.csv`
- Dashboard: Cross-Site Analytics subsection with confidence and severity display
- No live retrieval. No Redfin overwrite. Quiet Score gatekeeper unchanged.

### MVP 23: Cross-Site Parser Quality and Fixture Corpus Expansion

- All 4 parsers extract 19 fields including listing agent, listing broker, MLS number, source MLS, lot size
- Parse confidence model (high/medium/low) indicates extraction reliability
- Missing required field tracking for diagnostic purposes
- Normalization helpers for price, sqft, lot size, DOM, status, garage, gas evidence
- 32+ synthetic fixture files providing comprehensive parser test coverage

### MVP 22: Cross-Site Adapter Parity and Manual Fixtures

- Cross-site adapters with dry-run preview, URL validation, fixture capture queue integration, and audit logging
- Cross-site fixture processor with content-hash deduplication and append-only manifest
- CLI: `marketsentry dry-run-cross-site-property --source <source> --url <url>`
- CLI: `marketsentry process-cross-site-fixtures`
- CLI: `marketsentry process-cross-site-source-fixtures --source <source>`
- Dashboard: Cross-Site Fixtures tab in Retrieval Operations section
- Health checks: unprocessed cross-site fixtures, stale cross-site capture requests, missing parsers
- No live retrieval for non-Redfin sources. Redfin remains the only Live HTTP Phase 1 source.

### MVP 21: Retrieval Health Checks

- Health check module: `retrieval_health.py` with configurable thresholds
- Checks: stale capture requests, stale approval packages, unprocessed fixtures, missing policy files, audit anomalies, repeated blocks
- Severity levels: info, warning, error, critical
- Next actions: prioritized operator guidance
- CLI: `marketsentry retrieval-health-check`
- CLI: `marketsentry export-retrieval-health-report`
- Dashboard: Health Checks tab in Retrieval Operations section
- Read-only. No scheduled live retrieval.

### MVP 20: Retrieval Operations Dashboard

- Dashboard section: Retrieval Operations with Overview, Fixture Capture Queue, Approval Packages, Batch Retrieval Runs, Per-Item Results, Retrieval Audit, Retrieved Fixtures
- CLI: `marketsentry retrieval-operations-summary`
- CLI: `marketsentry export-retrieval-operations-report`
- Safety indicators: live retrieval enabled/disabled, allowed sources, User-Agent, rate limits
- Read-only. No retrieval actions from the dashboard.

### MVP 19: Redfin Batch Retrieval Approval Workflow

- Two-step approval workflow for Redfin batch live retrieval
- Prepare approval CSV: `marketsentry prepare-redfin-retrieval-approval`
- Retrieve approved items: `marketsentry retrieve-approved-redfin-batch --approval-file <path> --force-live`
- `approved_for_live` defaults to `false`; `--force-live` required
- No scheduled tasks invoke approved retrieval

### MVP 18: Redfin Pending Capture Batch Retrieval

This milestone adds a controlled batch orchestrator for pending Redfin fixture capture requests. The orchestrator processes capture queue items one at a time with full policy enforcement, rate limiting, and audit logging. Default mode is dry-run only.

**Status:** ✅ Complete

See [docs/REDFIN_PENDING_CAPTURE_BATCH_RETRIEVAL.md](docs/REDFIN_PENDING_CAPTURE_BATCH_RETRIEVAL.md) for the batch retrieval guide.

See [docs/REDFIN_RETRIEVED_FIXTURE_PROCESSING.md](docs/REDFIN_RETRIEVED_FIXTURE_PROCESSING.md) for the fixture processing guide.

See [docs/REDFIN_LIVE_HTTP_PHASE_1.md](docs/REDFIN_LIVE_HTTP_PHASE_1.md) for the Redfin Live HTTP Phase 1 guide.

See [docs/FIXTURE_CAPTURE_QUEUE.md](docs/FIXTURE_CAPTURE_QUEUE.md) for the fixture capture queue guide.

See [docs/LIVE_RETRIEVAL_STRATEGY.md](docs/LIVE_RETRIEVAL_STRATEGY.md) for the complete retrieval strategy guide.

See [docs/RUNBOOK.md](docs/RUNBOOK.md) for the complete operating guide.

- ✅ Batch orchestrator processes pending capture queue items one at a time
- ✅ Three modes: dry_run_only (default), retrieve_only, retrieve_and_process
- ✅ Full policy enforcement per item (compliance, robots, rate limit, dry-run approval)
- ✅ Batch and per-item manifests for audit trail
- ✅ CLI: dry-run-pending-redfin-fixtures, retrieve-pending-redfin-fixtures
- ✅ Post-retrieval processing via Milestone 17 pipeline
- ✅ Queue items marked captured only after successful retrieval/processing
- ✅ Live retrieval disabled by default; --force-live required
- ✅ No scheduled tasks invoke batch retrieval
- ✅ No browser automation or bypass mechanisms

### MVP 17: Redfin Retrieved Fixture Processing Pipeline

- ✅ Fixture metadata loader with sidecar JSON support
- ✅ Content-hash-based processing manifest for idempotency
- ✅ Search fixture processing (candidate insertion with deduplication)
- ✅ Detail fixture processing (candidate enrichment with listing events)
- ✅ Integrated processing workflow (parse, recalc, export reports)
- ✅ Fixture capture queue integration (auto-mark captured on match)
- ✅ CLI: process-redfin-retrieved-fixtures, process-redfin-search-fixtures, process-redfin-detail-fixtures
- ✅ CLI: retrieve-and-process-redfin-property (convenience command)
- ✅ No live retrieval in processing step

### MVP 16: Redfin Live HTTP Retrieval Phase 1

- ✅ HTTP client abstraction (HttpRequest, HttpResponse, HttpClient, StandardLibraryHttpClient, FakeHttpClient)
- ✅ Redfin live retrieval methods (retrieve_search, retrieve_property_detail, save_retrieved_fixture)
- ✅ Full policy enforcement pipeline (compliance, robots, rate limit, dry-run approval)
- ✅ Fixture output with sidecar metadata JSON
- ✅ CLI commands: retrieve-redfin-search, retrieve-redfin-property
- ✅ Policy engine updated: ALLOWED decision when all checks pass
- ✅ Live retrieval disabled by default
- ✅ No scheduled tasks invoke live retrieval
- ✅ No browser automation or bypass mechanisms
- ✅ Comprehensive tests with FakeHttpClient (no real network calls)

### MVP 1: Project Scaffold

- ✅ Project folder structure
- ✅ SQLite database schema
- ✅ Configuration files
- ✅ CLI entry point with database management
- ✅ Logging system
- ✅ Core data models
- ✅ Basic domain logic functions
- ✅ Comprehensive unit tests (46 tests)

### MVP 2: Review Workflow

- ✅ Candidate insertion with deduplication (by URL and normalized address)
- ✅ Sample seed data generation (3 test candidates)
- ✅ Review queue export to CSV
- ✅ Review decision import with validation
- ✅ Watchlist promotion for 'save' decisions
- ✅ Watch priority calculation (high/medium/low)
- ✅ Gas service and Quiet/Vibrancy preservation
- ✅ Idempotent import workflow
- ✅ New CLI commands: seed-sample-candidates, export-review, import-review, list-candidates, list-watched
- ✅ Complete workflow tests (62 tests total, all passing)

### MVP 3: Redfin Discovery Adapter Foundation

- ✅ Manual Redfin URL import from CSV
- ✅ Saved/static HTML fixture parsing
- ✅ Redfin URL validation and normalization
- ✅ Address, city, and ZIP extraction from URLs
- ✅ Candidate insertion with deduplication
- ✅ Source page audit tracking
- ✅ New CLI commands: import-redfin-urls, parse-redfin-fixtures
- ✅ Comprehensive tests for all new functionality (110 tests total, all passing)

**Important:** No live scraping or network calls are implemented yet. Milestone 3 uses manual URL import and saved HTML fixtures to validate the discovery→review→watchlist pipeline before adding live site access.

### MVP 4: Redfin Detail Parser and Candidate Enrichment

- ✅ Parse saved Redfin property detail page HTML files
- ✅ Extract property facts: price, beds, baths, sqft, lot size, year built, garage spaces
- ✅ Extract Quiet and Vibrancy lifestyle scores with semantic labels
- ✅ Detect gas service evidence from property descriptions
- ✅ Parse listing history events with date, type, price, and MLS information
- ✅ Calculate preliminary Effective DOM metrics (listing churn, DOM resets, sale/rent alternation)
- ✅ Enrich candidate records with parsed detail data
- ✅ Apply Quiet Gatekeeper logic during enrichment
- ✅ Preserve user decisions during enrichment updates
- ✅ New CLI commands: parse-redfin-details, enrich-redfin-details
- ✅ Comprehensive tests for all new functionality (130 tests total, all passing)

**Important:** Continues the saved HTML approach from Milestone 3. No live scraping. Users manually save Redfin detail pages and run enrichment commands.

### MVP 5: Effective DOM Engine and Candidate Scoring Report

- ✅ Effective DOM v1 metrics engine (displayed_dom, current_listing_instance_dom, sale_cycle_dom, rent_sale_exposure_dom, calendar_exposure_dom, effective_dom, effective_dom_delta)
- ✅ Event normalization for listing history (sale_listed, sale_removed, sale_relisted, sale_pending, sale_back_on_market, sale_sold, sale_price_changed, rental_listed, rental_removed, unknown)
- ✅ DOM reset counting (removals followed by relisting within 90 days without intervening sold event)
- ✅ Listing churn indicators
- ✅ Sale/rent alternation detection
- ✅ Comprehensive candidate scoring v1 (quiet_gatekeeper_result, location_fit_label, location_fit_score, property_fit_score, effective_dom_leverage_score, data_confidence_score, overall_review_score)
- ✅ Review recommendations (strong_review, review, maybe_review, reject_location_noise, needs_more_data)
- ✅ Warning flags and positive flags collection
- ✅ Candidate analysis report generation (CSV and Markdown formats)
- ✅ Database recalculation workflow for Effective DOM metrics
- ✅ New CLI commands: recalc-candidates, export-analysis-report
- ✅ Comprehensive tests for event normalization, DOM metrics, scoring, and critical domain rules (188 tests total, all passing)

**Important:** No live scraping or network calls. Milestone 5 performs deterministic analysis on existing parsed Redfin data from Milestone 4.

### MVP 6: Cross-Site Enrichment Foundation

- ✅ Manual cross-site URL import from CSV (Zillow, Realtor.com, Homes.com, Compass)
- ✅ Saved/static HTML fixture parsing for 4 real estate sites
- ✅ Cross-site observation storage in dedicated table (preserves Redfin as source of truth)
- ✅ Property matching by URL and normalized address
- ✅ Cross-site data comparison and discrepancy detection
- ✅ Discrepancy flags: price differences >$10k, listing status conflicts, DOM differences >30 days
- ✅ Cross-site comparison report generation (CSV format)
- ✅ New CLI commands: import-cross-site-urls, parse-cross-site-fixtures, export-cross-site-report
- ✅ Comprehensive tests for all parsers and cross-site logic (partial passing - parsers implemented)

**Important:** Continues the saved HTML approach from Milestones 3-5. No live scraping. Users manually save property detail pages from multiple sites and run enrichment commands. Cross-site observations are stored separately from the primary Redfin data to maintain single source of truth.

**Cross-Site Parsers (19 fields each, improved in MVP 23):**
- **Zillow**: Price, beds, baths, sqft, lot size, listing status, DOM, garage spaces, gas evidence, listing agent, listing broker, MLS number, source MLS, property description, parse confidence, parse warnings
- **Realtor.com**: Price, beds, baths, sqft, lot size, listing status, DOM, garage spaces, gas evidence, listing agent, listing broker, MLS number, source MLS, property description, parse confidence, parse warnings
- **Homes.com**: Price, beds, baths, sqft, lot size, listing status, DOM, garage spaces, gas evidence, listing agent, listing broker, MLS number, source MLS, property description, parse confidence, parse warnings
- **Compass**: Price, beds, baths, sqft, lot size, listing status, DOM, garage spaces, gas evidence, listing agent, listing broker, MLS number, source MLS, property description, parse confidence, parse warnings

**Discrepancy Detection:**
- **Price Discrepancy**: Flagged when any site's price differs from Redfin by more than $10,000
- **Status Discrepancy**: Flagged when listing status conflicts across sites (e.g., "active" vs "pending" vs "off-market")
- **DOM Discrepancy**: Flagged when displayed DOM differs by more than 30 days across sites

**Important Note:** Discrepancy flags are data quality indicators, NOT purchase recommendations. They highlight properties where cross-site data conflicts suggest the need for additional verification or closer inspection.

### MVP 7: Watchlist Monitoring Snapshots

- ✅ Observation snapshot creation for all watched properties
- ✅ Automated change detection between snapshots
- ✅ Price change tracking (amount, direction)
- ✅ Listing status change detection
- ✅ Displayed DOM and Effective DOM change tracking
- ✅ Quiet/Vibrancy score change monitoring (>= 0.5 threshold)
- ✅ Cross-site discrepancy flag change detection
- ✅ Idempotency handling (same-day duplicate prevention without material changes)
- ✅ Watchlist monitoring report generation (CSV format)
- ✅ Change summary generation for each property
- ✅ Warning flags (discrepancies, low quiet score) and positive flags (gas service, garage, excellent location)
- ✅ New CLI commands: snapshot-watchlist, list-snapshots, export-watchlist-monitoring-report
- ✅ Comprehensive tests for all monitoring functionality (251 tests total, all passing)

**Important:** This milestone performs no live network calls or scraping. It creates snapshots from existing database data (watched_properties, listing_events, cross_site_observations) to track changes over time for watchlist monitoring.

**Change Detection Thresholds:**
- **Price Change**: Any price difference
- **Significant Price Change**: >= $10,000
- **Status Change**: Any listing status difference
- **DOM Change**: Any displayed or effective DOM difference
- **Quiet/Vibrancy Change**: >= 0.5 score difference
- **Discrepancy Flag Change**: Any boolean flag change (price, status, DOM discrepancies)

**Idempotency Rule:** One snapshot per property per run timestamp. If you run snapshot-watchlist twice on the same day, the second run creates a new snapshot only if material fields changed (price, status, displayed DOM, effective DOM, or discrepancy flags). Otherwise, the snapshot is skipped with "no material changes" message.

**Watched Property Status:** active_watch_status is not automatically changed based on cross-site status disagreements. Status changes remain under user/system review.

### MVP 8: County Recorder and Assessor Verification Foundation

- ✅ Manual county record CSV import (Riverside County optimized, multi-county capable)
- ✅ Saved/static county HTML fixture parsing (assessor, recorder, tax_collector, permits)
- ✅ County record normalization and classification
- ✅ Ownership transfer verification logic (Grant Deed, Quitclaim Deed, Trustee Deed, Warranty Deed)
- ✅ Conservative non-transfer classification (Deed of Trust, Reconveyance, Lien, Assessment, Permit)
- ✅ Property and candidate matching by property_id, candidate_id, APN, and normalized address
- ✅ County-verified Effective DOM reset foundation (verification API for future Effective DOM v2 integration)
- ✅ Churn Index placeholder calculation (3-year lookback placeholder, weighted by churn type)
- ✅ Churn preservation guarantee: county_reset_supported does NOT erase churn metrics
- ✅ County verification report generation with all metrics side-by-side (CSV format)
- ✅ New CLI commands: import-county-records, parse-county-fixtures, verify-county-records, export-county-verification-report
- ✅ Comprehensive tests for all county functionality (298 tests total, all passing)

**Important:** This milestone performs NO live network calls, NO scraping, NO browser automation. All county data comes from manual CSV imports or saved/static HTML fixtures.

**County Source Types Supported:**
- **assessor**: Property ownership, APN confirmation, assessed value
- **recorder**: Deed and transfer events, document numbers, sale prices
- **tax_collector**: Property tax status
- **permit**: Building permits and construction history

**Ownership Transfer Classification:**

Ownership transfer records (support Effective DOM reset):
- **Grant Deed**: Standard ownership transfer
- **Quitclaim Deed**: Ownership transfer without warranty
- **Trustee Deed**: Foreclosure or trust sale transfer
- **Warranty Deed**: Guaranteed ownership transfer

NOT ownership transfer (do NOT support reset):
- **Deed of Trust**: Loan/financing document, not transfer
- **Reconveyance**: Loan payoff/release, not transfer
- **Lien**: Encumbrance, not transfer
- **Assessment**: Valuation record, not transfer
- **Permit**: Construction authorization, not transfer
- **Tax Record**: Tax payment/delinquency, not transfer

**Effective DOM vs Churn Index:**

**CRITICAL DISTINCTION:** County-confirmed ownership transfer may reset Effective DOM for the current ownership cycle, but churn metrics are preserved separately and remain reportable:

- **Effective DOM**: Current ownership-cycle market exposure, reset by confirmed ownership transfer
- **Churn Index**: Recent 2-3 year property/listing instability signal, NOT automatically erased by ownership transfer

The `churn_preserved_after_transfer` field is always `True` in the county verification report. This ensures churn remains available for analysis even when `county_reset_supported` is `True`.

**Churn Index Placeholder:** Current implementation uses a simple weighted sum of existing churn metrics (listing_churn_count * 1.0, dom_reset_count * 1.5, sale_rent_alternation_count * 2.0) normalized to 0-10 scale. This is a placeholder pending date-bounded Churn Index v1 in a future milestone.

**Manual County Record CSV Format:**

Required columns:
- `source_type` (assessor, recorder, tax_collector, permit)
- `record_date` (YYYY-MM-DD)
- `record_type` (Grant Deed, Quitclaim Deed, etc.)

At least one identity field:
- `property_id`, `candidate_id`, `apn`, or `address`

Optional columns:
- `city`, `zip`, `document_number`, `document_title`, `grantor`, `grantee`, `sale_price`, `transfer_tax`, `assessed_value`, `owner_name`, `permit_number`, `permit_type`, `permit_status`, `notes`, `source_url`

**County Verification Report Columns (35 total):**
- Property identification (property_id, address, city, zip, apn, redfin_url)
- Current metrics (current_price, effective_dom, displayed_dom)
- Churn metrics (listing_churn_count, dom_reset_count, sale_rent_alternation_count)
- Churn Index (recent_churn_index, recent_churn_lookback_years, recent_churn_event_count, churn_preserved_after_transfer)
- County verification (county_records_seen, county_transfer_found, county_transfer_date, county_transfer_record_type, county_reset_supported)
- Source presence (assessor_seen, recorder_seen, tax_collector_seen, permit_seen)
- Additional data (assessed_value, latest_permit_type, latest_permit_status)

**Saved County HTML Fixtures:**

Test fixtures provided:
- Assessor: APN, address, assessed value, owner name
- Recorder: Grant deed with sale price, grantor, grantee
- Recorder: Deed of trust (financing document)
- Recorder: No transfer found
- Tax Collector: APN, address, tax status
- Permit: Building permit number, type, status

**Important Note:** County verification reports are for assessment purposes, NOT purchase recommendations. Churn Index remains reportable even when county_reset_supported is true, ensuring all analytical signals are preserved.

### MVP 9: Effective DOM v2 County-Verified Reset Integration

- ✅ Effective DOM v2 calculation engine with county-confirmed reset boundaries
- ✅ County transfer detection inside listing history window
- ✅ Conservative reset logic (transfer must be inside listing window, not before first event or after latest event)
- ✅ Churn Index v1 with date-bounded 3-year lookback
- ✅ Separate churn preservation guarantee (churn metrics NEVER erased by county reset)
- ✅ Pre-reset and post-reset exposure metrics for comprehensive reporting
- ✅ v1 vs v2 comparison with effective_dom_delta_v1 and effective_dom_delta_v2
- ✅ Effective DOM v2 recalculation workflow (report-only, non-destructive)
- ✅ Effective DOM v2 comparison report generation (CSV format with 41 columns)
- ✅ New CLI commands: recalc-effective-dom-v2, export-effective-dom-v2-report
- ✅ Comprehensive tests for all 5 scenarios (A-E) and churn preservation (319+ tests total, all passing)

**Important:** This milestone performs NO live network calls, NO scraping, NO browser automation. All county data comes from Milestone 8 county_record_observations table.

**Effective DOM v2 vs v1:**

**Effective DOM v1** (Milestone 5): Property-level market exposure across listing events within lookback window, no county reset support.

**Effective DOM v2** (Milestone 9): Enhanced calculation using county-confirmed ownership transfer as reset boundary:
- If no county transfer exists: v2 equals v1
- If county transfer before all listing events: v2 equals v1 (no reset needed)
- If county transfer inside listing window: v2 excludes pre-transfer exposure, pre-reset metrics remain reportable
- If county transfer after latest event: v2 equals v1 (no historical reset)

**Churn Index v1:**

Churn Index measures recent 2-3 year property/listing instability using date-bounded event filtering and weighted scoring:

**Default Lookback:** 3 years from analysis date

**Weighted Scoring:**
- listing_churn_count: 1.0 weight (baseline instability)
- dom_reset_count: 1.5 weight (removal→relist cycles)
- sale_rent_alternation_count: 2.0 weight (strongest churn signal)
- price_change_count: 0.5 weight (moderate signal)

**Formula:** weighted_sum = (listing_churn * 1.0) + (dom_reset * 1.5) + (sale_rent_alternation * 2.0) + (price_change * 0.5)

**Normalization:** churn_index = min(10.0, (weighted_sum / 20.0) * 10.0)

**CRITICAL:** Churn Index is computed from ALL events within the 3-year lookback window, regardless of county reset. When county_reset_applied is true, Effective DOM v2 may be low (new ownership, recent transfer) while Churn Index remains high (property had unstable listing history before transfer). This separation enables four analytical scenarios:
1. Low Effective DOM + Low Churn: Stable property, new ownership, clean history
2. Low Effective DOM + High Churn: New ownership, but property had unstable listing history before sale
3. High Effective DOM + Low Churn: Long market exposure, but stable listing behavior
4. High Effective DOM + High Churn: Long exposure AND unstable listing behavior

**County Reset Scenarios:**

**Scenario A: No county transfer**
- effective_dom_v2 = effective_dom_v1
- county_reset_applied = false
- Churn Index computed from all events

**Scenario B: County transfer before all listing events**
- effective_dom_v2 = effective_dom_v1 (no reset applied)
- county_reset_applied = false
- Churn Index computed from all events

**Scenario C: County transfer inside listing-history window**
- effective_dom_v2 < effective_dom_v1 (excludes pre-transfer exposure)
- county_reset_applied = true
- pre_reset_calendar_exposure_dom, post_reset_calendar_exposure_dom remain reportable
- Churn Index computed from ALL events (pre and post reset)
- churn_preserved_after_transfer = true

**Scenario D: County transfer after latest listing event**
- effective_dom_v2 = effective_dom_v1 (no historical reset)
- county_reset_applied = false
- Churn Index computed from all events

**Scenario E: Non-transfer county record inside listing-history window**
- Deed of Trust, Reconveyance, Lien, Permit, Assessment, Tax Record do NOT reset Effective DOM
- effective_dom_v2 = effective_dom_v1
- county_reset_applied = false
- Churn Index computed from all events

**Effective DOM v2 Report Columns (41 total):**

Property identification: property_id, candidate_id, address, city, zip, apn, redfin_url

Current metrics: current_price, displayed_dom

Effective DOM v1 vs v2: effective_dom_v1, effective_dom_v2, effective_dom_delta_v1, effective_dom_delta_v2

County reset: county_reset_applied, county_reset_date, county_reset_record_type, county_reset_record_id, county_reset_confidence

Pre/post reset exposure: pre_reset_calendar_exposure_dom, post_reset_calendar_exposure_dom, pre_reset_sale_cycle_dom, post_reset_sale_cycle_dom, pre_reset_rent_sale_exposure_dom, post_reset_rent_sale_exposure_dom

Listing activity: listing_churn_count, dom_reset_count, sale_rent_alternation_count, price_change_count

Churn Index: recent_churn_index, recent_churn_lookback_years, recent_churn_event_count, recent_dom_reset_count, recent_sale_rent_alternation_count, churn_preserved_after_transfer

Quiet/Vibrancy: quiet_score, vibrancy_score, quiet_gatekeeper_result

Property characteristics: gas_service, garage_spaces

User data: user_notes, notes

**Important Note:** Effective DOM v2 report is an analytical tool, NOT a purchase recommendation. County reset affects Effective DOM only. Churn Index remains preserved separately to enable comprehensive property analysis across different time horizons.

### MVP 10: Effective DOM v2 Operational Integration

- ✅ v2 schema integration: 14 columns added to watched_properties, property_observation_snapshots, and candidate_review_queue
- ✅ Safe idempotent migrations (column_exists checks, ALTER TABLE ADD COLUMN)
- ✅ v2 persistence workflow (`persist-effective-dom-v2` CLI command)
- ✅ Watchlist monitoring snapshots include v2 fields and change detection (effective_dom_v2, churn_index, county_reset)
- ✅ Watchlist monitoring report includes 18 additional v2/churn columns
- ✅ Candidate analysis report includes v2, county reset, and Churn Index columns
- ✅ v2-aware scoring flags: churn_review_flag, county_reset_with_churn_flag, v2_leverage_flag
- ✅ Scoring uses neutral language (no seller-intent accusations)
- ✅ Quiet Score gatekeeper preserved: rejects properties with quiet_score < 7.0 regardless of v2 signals
- ✅ Churn Index NOT erased by county reset (churn_preserved_after_transfer always true)
- ✅ v1 metrics fully preserved alongside v2
- ✅ CandidateProperty and WatchedProperty models updated with v2 fields
- ✅ Comprehensive tests (342 tests total, all passing)

**Important:** This milestone performs NO live network calls, NO scraping, NO browser automation. v2 metrics are calculated from existing database data (listing events, county records) and persisted to operational tables.

**Effective DOM v2 is now operational, not report-only.** After running `persist-effective-dom-v2`, v2 metrics appear in:

- Watchlist monitoring snapshots (`snapshot-watchlist`)
- Watchlist monitoring reports (`export-watchlist-monitoring-report`)
- Candidate analysis reports (`export-analysis-report`)
- Scoring recommendations (v2 leverage flags)

**Churn Index in monitoring:** The Churn Index appears in monitoring reports as `recent_churn_index`, tracking changes over time via `previous_recent_churn_index` and `recent_churn_index_change`. High churn (>= 6.0) adds a neutral review flag ("high_recent_churn") to positive_flags. It is a buyer-review signal, not a seller-intent accusation.

**Churn preservation:** When `county_reset_applied` is true, Effective DOM v2 may show lower exposure (post-transfer only), but Churn Index remains unchanged. The `churn_preserved_after_transfer` field is always true, ensuring churn metrics are never erased by county reset.

### MVP 11: End-to-End Operating Workflow and Runbook

- ✅ Workflow orchestration module (`workflow.py`) with three end-to-end workflows
- ✅ `run_initial_review_workflow`: Import, parse, enrich, recalculate, export review CSV
- ✅ `run_watchlist_refresh_workflow`: Enrich, cross-site, county, v2, snapshot, all reports
- ✅ `run_full_fixture_demo_workflow`: Deterministic demo with sample data
- ✅ Typed workflow result models (WorkflowStepResult, WorkflowRunResult, WorkflowOutputFile, WorkflowWarning, WorkflowError)
- ✅ Report manifest (`data/exports/report_manifest.csv`) appended after each workflow run
- ✅ Workflow summary markdown files (`data/exports/workflow_summary_YYYYMMDD_HHMMSS.md`)
- ✅ New CLI commands: `run-initial-review-workflow`, `run-watchlist-refresh-workflow`, `run-fixture-demo-workflow`, `workflow-status`
- ✅ User-facing runbook at `docs/RUNBOOK.md`
- ✅ Workflow status command showing table counts and latest reports

**Important:** All workflows operate on locally saved HTML fixtures and manual CSV imports. No live scraping, browser automation, or network calls are implemented. Workflows orchestrate existing modules without duplicating business logic.

**Workflow CLI Commands:**

```bash
# Run initial review workflow (import, parse, enrich, export review CSV)
marketsentry run-initial-review-workflow \
  --redfin-urls-file data/imports/redfin_urls.csv \
  --redfin-search-dir data/raw/redfin/search \
  --redfin-details-dir data/raw/redfin/details \
  --output-dir data/exports

# Run watchlist refresh workflow (enrich, cross-site, county, snapshot, reports)
marketsentry run-watchlist-refresh-workflow \
  --redfin-details-dir data/raw/redfin/details \
  --cross-site-root-dir data/raw/cross_site \
  --county-records-file data/imports/county_records.csv \
  --output-dir data/exports

# Run fixture demo workflow (uses sample data, no real data needed)
marketsentry run-fixture-demo-workflow --reset-demo-db

# Check workflow status (table counts and latest reports)
marketsentry workflow-status
```

### MVP 12: Local Review Dashboard and Report Viewer

- ✅ Streamlit-based local dashboard for browser-based review
- ✅ Dashboard data loading module (`dashboard.py`) with typed models
- ✅ Dashboard sections: Overview, Candidate Review, Watchlist, Monitoring, Effective DOM v2, County Verification, Cross-Site Review, Reports, Workflow Summaries
- ✅ Interactive sidebar filters for candidates and watchlist
- ✅ CLI commands: `launch-dashboard`, `dashboard-summary`
- ✅ Report manifest viewer and workflow summary preview
- ✅ No live network calls - reads local SQLite and CSV only
- ✅ Not a purchase recommendation tool

**Dashboard reads local files/database only.** No scraping, fetching, or purchase recommendations.

**Dashboard CLI Commands:**

```bash
# Launch the local Streamlit dashboard in a browser
marketsentry launch-dashboard

# Or run directly with Streamlit
streamlit run src/marketsentry/dashboard_app.py

# Print ASCII-safe dashboard summary (no browser needed)
marketsentry dashboard-summary
```

**Dashboard Sections:**

- **Overview**: Summary counts (candidates, watched, snapshots, county resets, churn, quiet failures)
- **Candidate Review**: Filterable table with scoring, gatekeeper, gas, DOM, churn columns
- **Watchlist**: Filterable table with priority, active status, v1/v2, churn filters
- **Monitoring**: Latest monitoring report with price/status/DOM changes
- **Effective DOM v2**: v1 vs v2 comparison with county reset and churn preservation
- **County Verification**: County transfer evidence and reset support
- **Cross-Site Review**: Price/status/DOM discrepancy flags across sites
- **Reports**: Report manifest with timestamps and row counts
- **Workflow Summaries**: Preview of workflow summary markdown files

### MVP 13: Windows Task Scheduler Automation

- ✅ Python automation helper module (`automation.py`) with path detection, command building, and status reporting
- ✅ Windows batch scripts for all workflows (`run_watchlist_refresh_workflow.bat`, `run_initial_review_workflow.bat`, `run_dashboard_summary.bat`, `run_fixture_demo_workflow.bat`)
- ✅ PowerShell scheduled task installer (`install_task_scheduler_watchlist_refresh.ps1`)
- ✅ PowerShell scheduled task uninstaller (`uninstall_task_scheduler_watchlist_refresh.ps1`)
- ✅ Generic PowerShell task wrapper (`run_marketsentry_task.ps1`)
- ✅ CLI commands: `automation-status`, `write-scheduler-scripts`
- ✅ Timestamped scheduled log files under `logs/scheduled/`
- ✅ Default schedule: weekly Saturday 9:00 AM (configurable)
- ✅ No live scraping or network calls - all tasks run local workflows only

**Automation reads local files/database only.** No scraping, fetching, or purchase recommendations.

**Automation CLI Commands:**

```bash
# Check automation environment and script status
marketsentry automation-status

# Validate that all scheduler scripts exist
marketsentry write-scheduler-scripts
```

**Manual Script Execution:**

```cmd
REM Run watchlist refresh manually
scripts\run_watchlist_refresh_workflow.bat

REM Run dashboard summary
scripts\run_dashboard_summary.bat
```

**Scheduled Task Installation:**

```powershell
# Install weekly watchlist refresh (Saturday 9:00 AM)
powershell -ExecutionPolicy Bypass -File scripts\install_task_scheduler_watchlist_refresh.ps1

# Custom schedule (Monday 8:00 AM)
powershell -ExecutionPolicy Bypass -File scripts\install_task_scheduler_watchlist_refresh.ps1 -DayOfWeek Monday -Time "08:00"

# Remove scheduled task
powershell -ExecutionPolicy Bypass -File scripts\uninstall_task_scheduler_watchlist_refresh.ps1
```

See [docs/WINDOWS_TASK_SCHEDULER.md](docs/WINDOWS_TASK_SCHEDULER.md) for the complete automation guide.

### MVP 14: Live Retrieval Strategy and Compliance Adapters

- ✅ Source adapter architecture (`source_adapters/` package) with base abstractions
- ✅ Compliance guardrails module with retrieval blocking, domain allowlisting, rate limit validation
- ✅ Redfin adapter skeleton with dry-run search and property detail previews
- ✅ Stub adapters for Zillow, Realtor.com, Homes.com, Compass, and County
- ✅ Source adapter registry with lookup by name
- ✅ Retrieval audit logging to `logs/retrieval_audit/` (CSV format)
- ✅ CLI commands: `source-adapters`, `retrieval-compliance-status`, `dry-run-redfin-search`, `dry-run-redfin-property`
- ✅ Environment variable configuration for live retrieval settings
- ✅ Live retrieval disabled by default — requires explicit opt-in
- ✅ All audit records have `network_call_performed=False`
- ✅ No active scraping, network calls, or browser automation

**Live retrieval is disabled by default.** Manual fixtures remain the default safe workflow.

**Retrieval CLI Commands:**

```bash
# List registered source adapters
marketsentry source-adapters

# Check compliance configuration
marketsentry retrieval-compliance-status

# Preview a Redfin search retrieval (no network call)
marketsentry dry-run-redfin-search --url "https://www.redfin.com/city/19701/CA/Temecula/filter/..."

# Preview a Redfin property retrieval (no network call)
marketsentry dry-run-redfin-property --url "https://www.redfin.com/CA/Temecula/.../home/6574263"
```

See [docs/LIVE_RETRIEVAL_STRATEGY.md](docs/LIVE_RETRIEVAL_STRATEGY.md) for the complete retrieval strategy guide.

### MVP 15: Retrieval Safety Enforcement and Fixture Capture Queue

- ✅ Retrieval policy engine combining compliance, robots, rate limiting, and dry-run approval
- ✅ Offline robots.txt policy parser (local fixture files only, no network calls)
- ✅ Deterministic rate limiter with injectable state (no sleeping in tests)
- ✅ Dry-run approval/history gate with CSV-based approval records
- ✅ Fixture capture queue (SQLite-backed) as primary safe fallback workflow
- ✅ Redfin adapter integration with policy engine and fixture capture queue
- ✅ Retrieval audit report summarizer
- ✅ Robots test fixtures (redfin, zillow, empty, block-all)
- ✅ CLI commands: `retrieval-policy-check`, `list-fixture-capture-queue`, `export-fixture-capture-queue`, `mark-fixture-captured`, `retrieval-audit-report`
- ✅ No active scraping, network calls, or browser automation
- ✅ Live retrieval remains disabled by default

**Fixture capture queue is the primary safe fallback.** When live retrieval is blocked, the system adds URLs to a local queue and tells you exactly which pages to save manually and where to put them.

**Safety CLI Commands:**

```bash
# Check retrieval policy for a URL
marketsentry retrieval-policy-check --source redfin --url "https://www.redfin.com/..." --mode live_http

# List pending fixture capture requests
marketsentry list-fixture-capture-queue

# Export fixture capture queue to CSV
marketsentry export-fixture-capture-queue

# Mark a capture request as done
marketsentry mark-fixture-captured --capture-request-id 1 --fixture-path "data/raw/redfin/details/my_property.html"

# View retrieval audit report
marketsentry retrieval-audit-report
```

See [docs/FIXTURE_CAPTURE_QUEUE.md](docs/FIXTURE_CAPTURE_QUEUE.md) for the complete fixture capture queue guide.

### Effective DOM v1 Metrics

**Effective DOM** measures property-level market exposure across listing, removal, and relisting events. Milestone 5 implements multiple DOM variants with a fallback hierarchy:

1. **displayed_dom**: DOM shown on the source page (e.g., Redfin)
2. **current_listing_instance_dom**: Days from latest listing/relisting event to analysis date
3. **sale_cycle_dom**: Total active sale-listing exposure days within current no-sale cycle
4. **rent_sale_exposure_dom**: Total exposure days across sale and rental listing periods
5. **calendar_exposure_dom**: Calendar days from earliest observed event to analysis date
6. **effective_dom**: Best available property-level market exposure estimate using fallback hierarchy:
   - Prefer rent_sale_exposure_dom if sale/rent alternation present
   - Else prefer sale_cycle_dom
   - Else prefer calendar_exposure_dom
   - Else fallback to current_listing_instance_dom
   - Else fallback to displayed_dom
7. **effective_dom_delta**: effective_dom - displayed_dom (reveals hidden market exposure)

**Additional Metrics:**
- **listing_churn_count**: Count of all listing activity events (listed, removed, relisted, price_changed)
- **dom_reset_count**: Count of removal→relist cycles within 90 days (without intervening sold event)
- **sale_rent_alternation_count**: Count of transitions between sale and rental exposure categories
- **price_change_count**: Count of price_changed events
- **first_observed_event_date**, **latest_observed_event_date**: Event date range
- **first_observed_price**, **current_or_latest_price**, **lowest_observed_price**, **highest_observed_price**: Price tracking

**Current Cycle Detection:** Events are analyzed within the current "no-sale cycle" (events after the last sold event). If a sold event is present in the listing history, it resets the cycle, and only subsequent events are counted.

### Candidate Scoring Labels

The scoring system uses the following review recommendation labels:

- **strong_review**: High overall score (>= 80). Excellent location fit, good property fit, or high Effective DOM leverage signals. Top priority for human review.
- **review**: Good overall score (>= 60). Target location fit and acceptable property characteristics. Recommended for review.
- **maybe_review**: Moderate overall score (>= 40). Some positive signals but missing key data or borderline fit. Low priority review.
- **reject_location_noise**: Failed Quiet gatekeeper (quiet_score < 7.0). Location does not meet noise risk threshold regardless of other factors.
- **needs_more_data**: Low data confidence score. Missing critical fields (Quiet score, address, price, etc.). Requires enrichment before review.

**Location Fit Labels:**
- **excellent_location_fit**: quiet_score >= 9.0 and vibrancy_score <= 2.0 (location_fit_score: 100)
- **target_location_fit**: quiet_score >= 8.0 and vibrancy_score <= 2.5 (location_fit_score: 85)
- **quiet_but_review_vibrancy**: quiet_score >= 7.5 but vibrancy_score > 2.5 (location_fit_score: 70)
- **borderline_quiet**: quiet_score >= 7.0 but below target thresholds (location_fit_score: 50)
- **fail_noise_risk**: quiet_score < 7.0 (location_fit_score: 0)
- **needs_manual_location_review**: Missing Quiet score (location_fit_score: 40)

**Critical Domain Rule:** Low Vibrancy alone is NOT sufficient. The Quiet gatekeeper rejects properties with quiet_score < 7.0 even if vibrancy_score is very low. The target is very high Quiet AND very low Vibrancy.

**Warning Flags:**
- low_quiet_score, fail_quiet_gatekeeper, missing_quiet_score
- no_gas_service, insufficient_garage_spaces
- price_outside_range, missing_property_facts
- no_listing_history, low_data_confidence

**Positive Flags:**
- excellent_location, target_location
- has_gas_service, good_garage_spaces
- high_dom_delta (effective_dom_delta >= 90)
- has_dom_resets, high_listing_churn, sale_rent_alternation, multiple_price_changes

## Key Features (Planned)

1. **Effective DOM Calculation**: Measures property-level market exposure across listing, removal, and relisting events
2. **Quiet/Vibrancy Gatekeeper**: Filters properties based on location noise/activity proxy scores
3. **Gas Service Detection**: Identifies properties with natural gas service
4. **Human-in-the-Loop Workflow**: User reviews candidates before promotion to watchlist
5. **Multi-Source Enrichment**: Cross-references Redfin, Zillow, Realtor.com, and other sources
6. **County Verification**: Validates ownership transfers via county records

## Critical Domain Rules

1. **Effective DOM** measures property-level market exposure across listing, removal, and relisting events within a defined lookback window, excluding periods reset by confirmed ownership transfer.

2. **Quiet Score is the gatekeeper**: Reject or heavily downgrade if Quiet Score is below threshold, even when Vibrancy is low.

3. **Target is very high Quiet AND very low Vibrancy**: Low Vibrancy alone is not sufficient.

4. **Gas detection rule**: Any mention of gas means the property has natural gas service/supply.

5. **Neutral language**: The system does not infer seller intent. It uses neutral terms such as listing churn, non-closing relist cycle, DOM reset pattern, and pre-portal exposure.

6. **Human-in-the-loop**: The workflow stages candidates for user review before promotion to the active watchlist.

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- pip or your preferred Python package manager

### Installation

1. Clone the repository:

```bash
git clone https://github.com/rogerfiske/Market_Sentry.git
cd Market_Sentry
```

2. Create and activate a virtual environment:

```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Install the package in development mode:

```bash
pip install -e .
```

5. Create your local configuration:

```bash
cp .env.example .env
# Edit .env with your preferred settings
```

6. Initialize the database:

```bash
marketsentry init-database
```

## CLI Usage

### Initialize Database

```bash
marketsentry init-database
```

Creates the SQLite database and all required tables.

### Check Status

```bash
marketsentry status
```

Shows database status and record counts.

### View Configuration

```bash
marketsentry config-show
```

Displays current configuration settings.

### Show Version

```bash
marketsentry version
```

### Redfin Discovery Commands (MVP 3)

#### Import Redfin URLs from CSV

```bash
marketsentry import-redfin-urls --file data/imports/redfin_urls.csv
```

Imports Redfin property URLs from a CSV file. The CSV must contain a `redfin_url` column and can optionally include `address`, `city`, `zip`, `price`, `beds`, `baths`, `sqft`, and `notes`.

**Example CSV format:**

```csv
redfin_url,address,city,zip,price,beds,baths,sqft,notes
https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263,46197 Via La Tranquila,Temecula,92592,750000,3,2.5,2100,Looks promising
https://www.redfin.com/CA/Murrieta/25678-Via-Viejo-92563/home/7123456,,,,,,,Test this one
```

If address, city, or ZIP are not provided, the system will attempt to extract them from the URL.

#### Parse Redfin HTML Fixtures

```bash
marketsentry parse-redfin-fixtures --dir data/raw/redfin
```

Parses saved/static Redfin HTML files from a directory and extracts candidate property URLs. This allows testing the parser logic without live network calls.

Place `.html` or `.htm` files in `data/raw/redfin/` and run this command to extract candidates.

### Redfin Detail Parser Commands (MVP 4)

#### Parse Redfin Detail Pages

```bash
marketsentry parse-redfin-details --dir data/detail_pages/
```

Parses saved Redfin property detail page HTML files and displays a summary of extracted data including:

- Property facts (price, beds, baths, sqft, lot size, year built, garage spaces)
- Quiet and Vibrancy lifestyle scores
- Gas service detection
- Listing history events
- MLS information

This command does not modify the database - it only displays parsed information for verification.

#### Enrich Candidates with Detail Data

```bash
marketsentry enrich-redfin-details --dir data/detail_pages/ --db db/market_sentry.db
```

Parses saved detail page HTML files and enriches matching candidates in the database with:

- Property facts and lifestyle scores
- Gas service evidence
- Quiet Gatekeeper evaluation
- Listing history events (with duplicate detection)
- Preliminary Effective DOM metrics (listing churn, DOM resets, sale/rent alternation)

Candidates are matched by Redfin URL or normalized address. User decisions and notes are preserved during enrichment.

**Workflow:**

1. Browse Redfin and save detail pages to `data/detail_pages/` (right-click → Save As → Web Page, Complete)
2. Run `parse-redfin-details` to verify extraction
3. Run `enrich-redfin-details` to update candidates in the database

### Effective DOM and Scoring Commands (MVP 5)

#### Recalculate Candidate Metrics

```bash
marketsentry recalc-candidates
# Or specify database path:
marketsentry recalc-candidates --database db/market_sentry.db
```

Recalculates Effective DOM metrics and scoring-related fields for all candidates in the review queue. This command:

- Reads candidates and listing_events from database
- Recalculates all Effective DOM v1 metrics
- Updates candidate_review_queue with effective_dom_estimate, listing_churn_count, dom_reset_count, sale_rent_alternation_count, quiet_gatekeeper_result
- Preserves user_decision and user_notes
- Is idempotent (safe to run multiple times)

Prints: candidates scanned, candidates updated, listing events used, warnings/errors.

#### Export Candidate Analysis Report

```bash
marketsentry export-analysis-report
# Or specify output path and database:
marketsentry export-analysis-report --output data/exports/my_analysis.csv --database db/market_sentry.db
# Or export as Markdown:
marketsentry export-analysis-report --markdown
```

Exports comprehensive candidate analysis report to CSV (or Markdown). The report includes:

- Review recommendation and overall review score
- Location fit label and Quiet gatekeeper result
- Quiet/Vibrancy scores
- Property facts (price, beds, baths, sqft, garage spaces, gas service)
- Effective DOM metrics (displayed_dom, effective_dom, effective_dom_delta)
- Listing activity indicators (listing_churn_count, dom_reset_count, sale_rent_alternation_count, price_change_count)
- Data confidence score
- Warning flags and positive flags
- Address, city, ZIP, Redfin URL
- User decision and notes (preserved from review queue)

Default output: `data/exports/candidate_analysis_YYYYMMDD_HHMMSS.csv`

**How to Use the Analysis Report:**

1. Run `recalc-candidates` to ensure all metrics are current
2. Run `export-analysis-report` to generate the CSV
3. Open the CSV in Excel or your preferred spreadsheet tool
4. Sort by review_recommendation and overall_review_score
5. Focus on `strong_review` and `review` candidates first
6. Review warning_flags and positive_flags for each candidate
7. Use effective_dom_delta to identify properties with hidden market exposure
8. Set user_decision column to: save, reject, maybe, or hold_for_more_data
9. Import decisions with `import-review` command
10. Candidates marked as `save` are promoted to watchlist

### Cross-Site Enrichment Commands (MVP 6)

#### Import Cross-Site URLs from CSV

```bash
marketsentry import-cross-site-urls --file data/imports/cross_site_urls.csv
```

Imports cross-site property URLs from a CSV file and updates the `watched_properties` table with URLs for Zillow, Realtor.com, Homes.com, and Compass.

**CSV Format:**

```csv
redfin_url,address,zillow_url,realtor_url,homes_url,compass_url,notes
https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263,46197 Via La Tranquila,https://www.zillow.com/homedetails/...,https://www.realtor.com/realestateandhomes-detail/...,https://www.homes.com/property/...,https://www.compass.com/listing/...,Cross-check this one
```

**Columns:**
- `redfin_url` (required): Redfin URL to match watched property
- `address` (optional): Property address (used if redfin_url not provided or no match)
- `zillow_url`, `realtor_url`, `homes_url`, `compass_url` (optional): URLs for each site
- `notes` (optional): User notes

Properties are matched by Redfin URL or normalized address. At least one cross-site URL must be provided.

#### Parse Cross-Site HTML Fixtures

```bash
# Parse Zillow fixtures
marketsentry parse-cross-site-fixtures --dir data/cross_site/zillow --source zillow

# Parse Realtor.com fixtures
marketsentry parse-cross-site-fixtures --dir data/cross_site/realtor --source realtor

# Parse Homes.com fixtures
marketsentry parse-cross-site-fixtures --dir data/cross_site/homes --source homes

# Parse Compass fixtures
marketsentry parse-cross-site-fixtures --dir data/cross_site/compass --source compass
```

Parses saved cross-site property detail page HTML files and creates observations in the `cross_site_observations` table. Properties are matched to the watchlist by:
1. Cross-site URL (if property has zillow_url, realtor_url, etc.)
2. Normalized address

**Workflow:**
1. Ensure property is in watchlist (promoted from candidate review)
2. Use `import-cross-site-urls` to add cross-site URLs to watched property
3. Manually save detail pages from each site to separate directories
4. Run `parse-cross-site-fixtures` for each site
5. Observations are inserted into `cross_site_observations` table
6. Run `export-cross-site-report` to generate comparison report

**Important:** Redfin data in `watched_properties` remains the single source of truth. Cross-site observations are stored separately for comparison and data quality validation only.

#### Export Cross-Site Comparison Report

```bash
marketsentry export-cross-site-report
# Or specify output path and database:
marketsentry export-cross-site-report --output data/exports/cross_site_comparison.csv --database db/market_sentry.db
```

Exports cross-site comparison report to CSV. The report includes:

- Property identification (address, city, ZIP, Redfin URL)
- Redfin data (price, DOM, status)
- Cross-site data (price, DOM, status from Zillow, Realtor.com, Homes.com, Compass)
- Discrepancy flags (price, status, DOM)
- Comparison notes and warnings

**Discrepancy Flags:**
- `has_price_discrepancy`: Any site's price differs from Redfin by >$10,000
- `has_status_discrepancy`: Listing status conflicts across sites (active vs pending vs off-market)
- `has_dom_discrepancy`: DOM differs by >30 days across sites

Default output: `data/exports/cross_site_report_YYYYMMDD_HHMMSS.csv`

**Important:** Discrepancy flags are data quality indicators, NOT purchase recommendations. They highlight properties requiring additional verification or manual inspection due to conflicting data across sites.

### Watchlist Monitoring Commands (MVP 7)

#### Create Monitoring Snapshots

```bash
marketsentry snapshot-watchlist
# Or specify database path:
marketsentry snapshot-watchlist --db db/market_sentry.db
```

Creates monitoring snapshots for all active watched properties. This command:

- Reads current property data from watched_properties, listing_events, and cross_site_observations
- Creates a new snapshot in property_observation_snapshots table
- Detects changes from the previous snapshot (price, status, DOM, discrepancies)
- Updates last_checked_date for each property
- Implements idempotency: skips same-day duplicate snapshots without material changes

Prints: properties scanned, snapshots created, snapshots skipped, changes detected, warnings/errors.

**Material Changes:** Price, listing status, displayed DOM, effective DOM, or discrepancy flag changes. If none of these changed since the last snapshot today, the new snapshot is skipped.

#### List Recent Snapshots

```bash
marketsentry list-snapshots
# Or filter by property:
marketsentry list-snapshots --property-id 5
# Or limit results:
marketsentry list-snapshots --limit 20
```

Lists recent observation snapshots from the property_observation_snapshots table. Shows:

- Snapshot ID and property ID
- Address and city
- Snapshot date
- Price, Effective DOM, listing status
- Notes/change summary

#### Export Watchlist Monitoring Report

```bash
marketsentry export-watchlist-monitoring-report
# Or specify output path and database:
marketsentry export-watchlist-monitoring-report --output data/exports/watchlist_monitoring.csv --db db/market_sentry.db
```

Exports comprehensive watchlist monitoring report to CSV. The report includes:

- Property identification (address, city, ZIP, Redfin URL)
- Current and previous values (price, status, DOM)
- Change indicators (price change amount/direction, status changed)
- Effective DOM metrics and delta
- Quiet/Vibrancy scores and gatekeeper result
- Property characteristics (garage spaces, gas service)
- Listing activity indicators (churn count, DOM resets, sale/rent alternation)
- Cross-site data quality (discrepancy flags, confidence score)
- Change summary and warning/positive flags
- User notes, last checked date, snapshot date

Default output: `data/exports/watchlist_monitoring_YYYYMMDD_HHMMSS.csv`

**Important:** This is a watchlist monitoring report, NOT a purchase recommendation. It tracks changes and data quality for properties you're monitoring over time.

**Warning Flags:**
- Price/status/DOM discrepancies across sites
- Quiet score below threshold

**Positive Flags:**
- Gas service, 2+ car garage
- Excellent quiet/vibrancy (quiet >= 8.0, vibrancy <= 2.5)

### Effective DOM v2 Commands (MVP 9)

#### Recalculate Effective DOM v2

```bash
marketsentry recalc-effective-dom-v2
# Or specify database path:
marketsentry recalc-effective-dom-v2 --db db/market_sentry.db
```

Recalculates Effective DOM v2 for all active watched properties using county-confirmed transfer records as reset boundaries. This command:

- Reads watched_properties, listing_events, and county_record_observations from database
- Computes Effective DOM v2 metrics for each property
- Identifies county-confirmed ownership transfers inside listing windows
- Calculates pre-reset and post-reset exposure metrics
- Computes Churn Index v1 from ALL events (3-year lookback)
- Preserves churn metrics separately from Effective DOM reset
- Report-only operation (does not modify database)

Prints: properties scanned, county transfers considered, county resets applied, records updated, churn metrics preserved, warnings/errors.

**Important:** This is a report-only operation. County reset affects Effective DOM calculation only. Churn Index is preserved separately and computed from all events within the 3-year lookback window regardless of county reset.

#### Export Effective DOM v2 Report

```bash
marketsentry export-effective-dom-v2-report
# Or specify output path and database:
marketsentry export-effective-dom-v2-report --output data/exports/edom_v2_comparison.csv --db db/market_sentry.db
```

Exports comprehensive Effective DOM v1 vs v2 comparison report to CSV. The report includes:

- Property identification (property_id, candidate_id, address, city, ZIP, APN, Redfin URL)
- Current metrics (current_price, displayed_dom)
- Effective DOM v1 vs v2 (effective_dom_v1, effective_dom_v2, effective_dom_delta_v1, effective_dom_delta_v2)
- County reset information (county_reset_applied, county_reset_date, county_reset_record_type, county_reset_record_id, county_reset_confidence)
- Pre-reset exposure metrics (pre_reset_calendar_exposure_dom, pre_reset_sale_cycle_dom, pre_reset_rent_sale_exposure_dom)
- Post-reset exposure metrics (post_reset_calendar_exposure_dom, post_reset_sale_cycle_dom, post_reset_rent_sale_exposure_dom)
- Listing activity (listing_churn_count, dom_reset_count, sale_rent_alternation_count, price_change_count)
- Churn Index v1 (recent_churn_index, recent_churn_lookback_years, recent_churn_event_count, recent_dom_reset_count, recent_sale_rent_alternation_count, churn_preserved_after_transfer)
- Quiet/Vibrancy scores and gatekeeper result
- Property characteristics (gas_service, garage_spaces)
- User notes

Default output: `data/exports/effective_dom_v2_YYYYMMDD_HHMMSS.csv`

**How to Use the v1 vs v2 Comparison Report:**

1. Run `recalc-effective-dom-v2` to compute v2 metrics
2. Run `export-effective-dom-v2-report` to generate the CSV
3. Open the CSV in Excel or your preferred spreadsheet tool
4. Compare effective_dom_v1 vs effective_dom_v2 to see county reset impact
5. Review county_reset_applied column to identify properties with verified ownership transfers
6. Check recent_churn_index alongside effective_dom_v2 for comprehensive analysis
7. Look for Low Effective DOM + High Churn scenarios (new ownership but unstable history)
8. Review pre_reset and post_reset exposure metrics for full property timeline

**Important:** This report is an analytical tool, NOT a purchase recommendation. County reset affects Effective DOM only. Churn Index (recent_churn_index) remains preserved separately to enable analysis across different time horizons.

### Effective DOM v2 Operational Commands (MVP 10)

#### Persist Effective DOM v2 Metrics

```bash
marketsentry persist-effective-dom-v2
# Or specify database path:
marketsentry persist-effective-dom-v2 --db db/market_sentry.db
```

Computes Effective DOM v2 and Churn Index for all watched properties and candidates, then persists the results to the database. This command:

- Reads watched_properties, candidates, listing_events, and county_record_observations
- Computes Effective DOM v2 with county-confirmed reset boundaries
- Computes Churn Index v1 from all events within 3-year lookback
- Updates watched_properties and candidate_review_queue with v2 metrics
- Preserves user_notes, user_decision, active_watch_status, and watch_priority
- Never zeros or erases churn metrics when county reset applies
- Is idempotent (safe to run multiple times)

Prints: properties scanned, county transfers considered, county resets applied, records updated, churn metrics preserved.

**Important:** Run this command before `snapshot-watchlist` or `export-analysis-report` to ensure v2 metrics are current. This command performs no live network calls.

### Review Workflow Commands (MVP 2-5)

#### Seed Sample Candidates

```bash
marketsentry seed-sample-candidates
```

Seeds the database with 3 sample candidates for testing the review workflow.

#### Export Review Queue

```bash
marketsentry export-review
# Or specify output file:
marketsentry export-review --output data/exports/my_review.csv
```

Exports all candidates from the review queue to CSV for human review.

#### Import Review Decisions

```bash
marketsentry import-review --file data/imports/reviewed_candidates.csv
```

Imports reviewed decisions from CSV. Valid decisions: `save`, `reject`, `maybe`, `hold_for_more_data`.

Properties marked as `save` are promoted to the watchlist.

#### List Candidates

```bash
marketsentry list-candidates
# Or limit results:
marketsentry list-candidates --limit 20
```

Lists candidates in the review queue.

#### List Watched Properties

```bash
marketsentry list-watched
# Or limit results:
marketsentry list-watched --limit 20
```

Lists properties in the active watchlist.

### Complete Workflow Example (MVP 3)

```bash
# 1. Initialize database
marketsentry init-database

# 2. Create a CSV file with Redfin URLs (data/imports/redfin_urls.csv)
#    Required column: redfin_url
#    Optional columns: address, city, zip, price, beds, baths, sqft, notes

# 3. Import Redfin URLs from CSV
marketsentry import-redfin-urls --file data/imports/redfin_urls.csv

# OR: Parse saved Redfin HTML fixtures
marketsentry parse-redfin-fixtures --dir data/raw/redfin

# 4. List imported candidates
marketsentry list-candidates

# 5. Export candidates for review
marketsentry export-review

# 6. Edit the exported CSV file (data/exports/review_queue_*.csv)
#    Set user_decision column to: save, reject, maybe, or hold_for_more_data

# 7. Import reviewed decisions
marketsentry import-review --file data/exports/review_queue_20260505_123456.csv

# 8. View watched properties
marketsentry list-watched
```

**Note:** You can still use `marketsentry seed-sample-candidates` to seed test data if you don't have real Redfin URLs yet.

### Complete Workflow Example with Cross-Site Enrichment (MVP 3-6)

```bash
# Phase 1: Candidate Discovery and Review (MVP 3-5)
# ====================================================

# 1. Initialize database
marketsentry init-database

# 2. Import Redfin URLs
marketsentry import-redfin-urls --file data/imports/redfin_urls.csv

# 3. Enrich candidates with Redfin detail data
marketsentry enrich-redfin-details --dir data/detail_pages/

# 4. Recalculate Effective DOM metrics and scoring
marketsentry recalc-candidates

# 5. Export analysis report
marketsentry export-analysis-report

# 6. Review candidates in CSV, set user_decision to 'save' for properties to watch

# 7. Import review decisions (promotes 'save' to watchlist)
marketsentry import-review --file data/exports/candidate_analysis_20260505_120000.csv

# Phase 2: Cross-Site Enrichment for Watched Properties (MVP 6)
# ===============================================================

# 8. Create CSV with cross-site URLs (data/imports/cross_site_urls.csv)
#    Columns: redfin_url, address, zillow_url, realtor_url, homes_url, compass_url

# 9. Import cross-site URLs to link watched properties to other sites
marketsentry import-cross-site-urls --file data/imports/cross_site_urls.csv

# 10. Manually save detail pages from each site:
#     - Zillow: Save to data/cross_site/zillow/
#     - Realtor.com: Save to data/cross_site/realtor/
#     - Homes.com: Save to data/cross_site/homes/
#     - Compass: Save to data/cross_site/compass/

# 11. Parse cross-site fixtures (creates observations in database)
marketsentry parse-cross-site-fixtures --dir data/cross_site/zillow --source zillow
marketsentry parse-cross-site-fixtures --dir data/cross_site/realtor --source realtor
marketsentry parse-cross-site-fixtures --dir data/cross_site/homes --source homes
marketsentry parse-cross-site-fixtures --dir data/cross_site/compass --source compass

# 12. Export cross-site comparison report
marketsentry export-cross-site-report

# 13. Review comparison report for discrepancies:
#     - Price differences >$10k
#     - Status conflicts (active vs pending)
#     - DOM differences >30 days
```

**Important Notes:**
- Cross-site observations are stored separately from Redfin data (single source of truth)
- Discrepancy flags are data quality indicators, not purchase recommendations
- All cross-site data uses saved HTML approach (no live scraping)
- Properties must be in watchlist before cross-site enrichment

### Complete Workflow Example with Watchlist Monitoring (MVP 3-7)

```bash
# Phase 1: Candidate Discovery and Review (MVP 3-5)
# ====================================================

# 1. Initialize database
marketsentry init-database

# 2. Import Redfin URLs
marketsentry import-redfin-urls --file data/imports/redfin_urls.csv

# 3. Enrich candidates with Redfin detail data
marketsentry enrich-redfin-details --dir data/detail_pages/

# 4. Recalculate Effective DOM metrics and scoring
marketsentry recalc-candidates

# 5. Export analysis report
marketsentry export-analysis-report

# 6. Review candidates in CSV, set user_decision to 'save' for properties to watch

# 7. Import review decisions (promotes 'save' to watchlist)
marketsentry import-review --file data/exports/candidate_analysis_20260505_120000.csv

# Phase 2: Cross-Site Enrichment for Watched Properties (MVP 6)
# ===============================================================

# 8. Import cross-site URLs to link watched properties to other sites
marketsentry import-cross-site-urls --file data/imports/cross_site_urls.csv

# 9. Parse cross-site fixtures (creates observations in database)
marketsentry parse-cross-site-fixtures --dir data/cross_site/zillow --source zillow
marketsentry parse-cross-site-fixtures --dir data/cross_site/realtor --source realtor
marketsentry parse-cross-site-fixtures --dir data/cross_site/homes --source homes
marketsentry parse-cross-site-fixtures --dir data/cross_site/compass --source compass

# 10. Export cross-site comparison report
marketsentry export-cross-site-report

# Phase 3: Watchlist Monitoring (MVP 7)
# ========================================

# 11. Create initial monitoring snapshots for all watched properties
marketsentry snapshot-watchlist

# 12. List recent snapshots
marketsentry list-snapshots

# 13. Export initial watchlist monitoring report
marketsentry export-watchlist-monitoring-report

# (Later: After some time has passed, property data has changed)

# 14. Create new snapshots to detect changes
marketsentry snapshot-watchlist

# 15. Export updated monitoring report to see changes
marketsentry export-watchlist-monitoring-report

# 16. Review monitoring report for:
#     - Price changes (increases/decreases)
#     - Status changes (active -> pending, etc.)
#     - DOM changes
#     - Cross-site discrepancies
#     - Warning flags (data quality issues)
```

**Monitoring Workflow Notes:**
- Run `snapshot-watchlist` periodically (daily, weekly, etc.) to track changes
- Each run creates new snapshots and detects changes from previous snapshots
- Same-day duplicates without material changes are automatically skipped
- Monitoring report shows current vs previous values and change summaries
- Changes are informational only - no automatic actions are taken
- Watched property status is not automatically changed based on cross-site disagreements

## Project Structure

```
Market_Sentry/
├── .claude/                                   # Local Claude Code settings (untracked)
│   └── settings.local.json
├── config/                                    # Configuration templates
│   ├── alert_expiration_profiles.example.json          # Example alert expiration profiles
│   └── portfolio_alert_highlight_preferences.example.json  # Example highlight preferences
├── data/                                      # Runtime data (generated, gitignored)
│   ├── market_sentry.db                       # Stray DB from a mistyped --db path (untracked)
│   ├── exports/                               # Report and export output
│   │   ├── .gitkeep
│   │   ├── archive_pre_operations_cleanup/    # 198 archived pre-cleanup exports
│   │   │   ├── candidate_analysis_<timestamp>.csv          (70 files)
│   │   │   ├── cross_site_alert_hygiene_<timestamp>.csv    (66 files)
│   │   │   ├── cross_site_alert_hygiene_<timestamp>.md     (51 files)
│   │   │   ├── demo_candidate_analysis.csv
│   │   │   ├── demo_candidate_review.csv
│   │   │   ├── demo_county_verification.csv
│   │   │   ├── demo_effective_dom_v2.csv
│   │   │   ├── demo_reviewed.csv
│   │   │   ├── demo_watchlist_monitoring.csv
│   │   │   ├── file_list.bat
│   │   │   ├── file_list.md
│   │   │   ├── file_list.md.pdf
│   │   │   ├── file_list.zip
│   │   │   └── review_queue.csv
│   │   ├── quiet_search.txt                   # Ad-hoc quiet-area search notes
│   │   ├── quiet_vibrancy_search.txt          # Ad-hoc quiet/vibrancy search notes
│   │   ├── vibrancy_search.txt                # Ad-hoc vibrancy search notes
│   │   ├── report_manifest.csv                # Stable manifest of generated reports
│   │   └── <130 timestamped exports>          # One file per run, named
│   │       #   candidate_analysis_<timestamp>.csv
│   │       #   cross_site_alert_hygiene_<timestamp>.{csv,md}
│   │       #   fixture_capture_queue_<timestamp>.csv
│   │       #   local_operations_bundle_<timestamp>.{csv,md}
│   │       #   operations_digest_<timestamp>.{csv,md}
│   │       #   portfolio_alert_email_digest_<timestamp>.{eml,md,txt}
│   │       #   portfolio_review_pack_<timestamp>.{csv,md}
│   │       #   redfin_screening_queue_<timestamp>.{csv,md}
│   │       #   release_candidate_report_<timestamp>.{csv,md}
│   │       #   release_finalization_<timestamp>.{csv,md}
│   │       #   review_queue_<timestamp>.csv
│   │       #   watchlist_monitoring_<timestamp>.csv
│   │       #   workflow_summary_<timestamp>.md
│   ├── imports/                               # Operator-supplied input files
│   │   ├── .gitkeep
│   │   ├── redfin_screening_urls.csv          # Screening queue URL input
│   │   ├── redfin_urls.csv                    # Manual Redfin URL import
│   │   ├── redfin_urls_valid.csv              # Validated Redfin URL import
│   │   └── reviewed_candidates.csv            # Review decision import
│   ├── policies/                              # Cached retrieval policy artifacts
│   │   └── robots/                            # Cached robots.txt files (empty)
│   ├── processed/                             # Intermediate retrieval manifests
│   │   ├── .gitkeep
│   │   ├── redfin_batch_retrieval_manifest.csv
│   │   └── redfin_retrieval_approval_manifest.csv
│   └── raw/                                   # Raw captured HTML/JSON payloads
│       ├── .gitkeep
│       └── redfin/
│           ├── redfin_search_fixture.html     # Saved search page capture
│           ├── details/                       # Saved detail page captures
│           │   ├── 32152_camino_nunez.html
│           │   ├── 32420_san_marco_dr.html
│           │   ├── effective_dom_agent_next_steps_and_persona.md
│           │   ├── redfin_property_6574263_20260507_100758.html
│           │   └── redfin_property_6574263_20260507_100758.json
│           └── search/                        # 130 files: redfin_search_<timestamp>.html
│                                              #   plus matching .json metadata sidecars
├── db/                                        # SQLite database location
│   ├── .gitkeep
│   ├── demo_marketsentry.db                   # Fixture/demo database
│   └── marketsentry.db                        # Primary operating database
├── docs/                                      # Documentation
│   ├── ALERT_EXPIRATION_PROFILES.md
│   ├── CROSS_SITE_MANUAL_FIXTURE_WORKFLOW.md
│   ├── FIXTURE_CAPTURE_QUEUE.md
│   ├── How I use Obsidian.md                  # Operator notes (untracked)
│   ├── HowLoud openapi.json                   # HowLoud noise API spec (untracked)
│   ├── LIVE_RETRIEVAL_STRATEGY.md
│   ├── LOCAL_OPERATIONS_BUNDLE.md
│   ├── OPERATOR_WORKFLOW.md
│   ├── PORTFOLIO_ALERT_EMAIL_DIGEST.md
│   ├── PORTFOLIO_ALERT_FOCUS_PREFERENCES.md
│   ├── PORTFOLIO_TREND_ALERT_RULES.md
│   ├── REDFIN_LIVE_HTTP_PHASE_1.md
│   ├── REDFIN_PENDING_CAPTURE_BATCH_RETRIEVAL.md
│   ├── REDFIN_RETRIEVAL_APPROVAL_WORKFLOW.md
│   ├── REDFIN_RETRIEVED_FIXTURE_PROCESSING.md
│   ├── REDFIN_SCREENING_QUEUE.md
│   ├── SCREENING_QUEUE_BATCH_ACTIONS.md
│   ├── RELEASE_CANDIDATE_CHECKLIST.md
│   ├── RELEASE_FINALIZATION_GUIDE.md
│   ├── RELEASE_NOTES_DRAFT.md
│   ├── RELEASE_NOTES_FINAL.md
│   ├── Restart the dashboard.md               # Operator notes (untracked)
│   ├── RUNBOOK.md
│   ├── WINDOWS_TASK_SCHEDULER.md
│   ├── decisions/                             # Architecture Decision Records (51)
│   │   ├── 001-human-in-the-loop-review-queue.md
│   │   ├── 002-redfin-discovery-adapter-foundation.md
│   │   ├── 003-redfin-detail-parser-saved-fixtures.md
│   │   ├── 004-effective-dom-v1-and-review-scoring.md
│   │   ├── 005-cross-site-enrichment-foundation.md
│   │   ├── 006-watchlist-monitoring-snapshots.md
│   │   ├── 007-county-verification-foundation.md
│   │   ├── 008-effective-dom-v2-county-reset-and-churn-index.md
│   │   ├── 009-effective-dom-v2-operational-integration.md
│   │   ├── 010-end-to-end-operating-workflow.md
│   │   ├── 011-local-dashboard-report-viewer.md
│   │   ├── 012-windows-task-scheduler-automation.md
│   │   ├── 013-live-retrieval-strategy-and-compliance-adapters.md
│   │   ├── 014-retrieval-safety-and-fixture-capture-queue.md
│   │   ├── 015-redfin-live-http-phase-1.md
│   │   ├── 016-redfin-retrieved-fixture-processing.md
│   │   ├── 017-redfin-pending-capture-batch-retrieval.md
│   │   ├── 018-redfin-retrieval-approval-workflow.md
│   │   ├── 019-retrieval-operations-dashboard.md
│   │   ├── 020-retrieval-health-checks.md
│   │   ├── 021-cross-site-adapter-parity-manual-fixtures.md
│   │   ├── 022-cross-site-parser-quality-fixture-corpus.md
│   │   ├── 023-confidence-weighted-cross-site-analytics.md
│   │   ├── 024-cross-site-analytics-trend-snapshots.md
│   │   ├── 025-cross-site-trend-alerts-watchlist-monitoring.md
│   │   ├── 026-cross-site-alert-aggregation-patterns.md
│   │   ├── 027-cross-site-alert-triage-workflow.md
│   │   ├── 028-cross-site-alert-hygiene-scheduled-reminders.md
│   │   ├── 029-cross-site-alert-archive-policy.md
│   │   ├── 030-cross-site-alert-expiration-policy.md
│   │   ├── 031-user-defined-alert-expiration-profiles.md
│   │   ├── 032-alert-expiration-profile-comparison-preferences.md
│   │   ├── 033-alert-lifecycle-audit-trail.md
│   │   ├── 034-alert-lifecycle-trend-snapshots.md
│   │   ├── 035-lifecycle-health-scoring.md
│   │   ├── 036-lifecycle-health-trend-snapshots.md
│   │   ├── 037-operations-digest.md
│   │   ├── 038-operations-digest-history.md
│   │   ├── 039-portfolio-review-pack.md
│   │   ├── 040-portfolio-review-comparison.md
│   │   ├── 041-portfolio-review-trends.md
│   │   ├── 042-portfolio-trend-alerts.md
│   │   ├── 043-configurable-portfolio-trend-alert-rules.md
│   │   ├── 044-portfolio-trend-alert-history.md
│   │   ├── 045-portfolio-alert-focus-preferences.md
│   │   ├── 046-local-email-digest-draft.md
│   │   ├── 047-local-operations-bundle.md
│   │   ├── 048-release-candidate-hardening.md
│   │   ├── 049-release-finalization.md
│   │   ├── 050-guided-operator-workflow.md
│   │   ├── 051-redfin-screening-queue.md
│   │   └── 052-screening-queue-batch-actions.md
│   ├── examples/                              # Example artifacts (empty)
│   └── prompts/                               # Milestone build prompts (53)
│       ├── Market_Sentry_Claude_Prompt_001_Project_Scaffold.md
│       ├── Market_Sentry_Claude_Prompt_002_Candidate_Review_Workflow.md
│       ├── Market_Sentry_Claude_Prompt_003_Redfin_Discovery_Adapter_Foundation.md
│       ├── Market_Sentry_Claude_Prompt_004_Redfin_Detail_Parser.md
│       ├── Market_Sentry_Claude_Prompt_005_Effective_DOM_Scoring_Report.md
│       ├── Market_Sentry_Claude_Prompt_006_Cross_Site_Enrichment_Foundation.md
│       ├── Market_Sentry_Claude_Prompt_006A_Cross_Site_Stabilization.md
│       ├── Market_Sentry_Claude_Prompt_007_Watchlist_Monitoring_Snapshots.md
│       ├── Market_Sentry_Claude_Prompt_008_County_Verification_Foundation_REVISED.md
│       ├── Market_Sentry_Claude_Prompt_009_Effective_DOM_v2_County_Reset.md
│       ├── Market_Sentry_Claude_Prompt_010_Effective_DOM_v2_Operational_Integration.md
│       ├── Market_Sentry_Claude_Prompt_011_End_to_End_Workflow_Runbook.md
│       ├── Market_Sentry_Claude_Prompt_011A_Export_Path_Stabilization.md
│       ├── Market_Sentry_Claude_Prompt_012_Local_Dashboard_Report_Viewer.md
│       ├── Market_Sentry_Claude_Prompt_013_Windows_Task_Scheduler_Automation.md
│       ├── Market_Sentry_Claude_Prompt_014_Live_Retrieval_Strategy_Compliance_Adapters.md
│       ├── Market_Sentry_Claude_Prompt_015_Retrieval_Safety_Fixture_Capture_Queue.md
│       ├── Market_Sentry_Claude_Prompt_016_Redfin_Live_HTTP_Phase_1.md
│       ├── Market_Sentry_Claude_Prompt_017_Redfin_Retrieved_Fixture_Processing.md
│       ├── Market_Sentry_Claude_Prompt_018_Redfin_Pending_Capture_Batch_Retrieval.md
│       ├── Market_Sentry_Claude_Prompt_019_Redfin_Batch_Retrieval_Approval_Workflow.md
│       ├── Market_Sentry_Claude_Prompt_020_Retrieval_Operations_Dashboard.md
│       ├── Market_Sentry_Claude_Prompt_021_Retrieval_Health_Checks.md
│       ├── Market_Sentry_Claude_Prompt_022_Cross_Site_Adapter_Parity_Manual_Fixtures.md
│       ├── Market_Sentry_Claude_Prompt_023_Cross_Site_Parser_Quality_Fixture_Corpus.md
│       ├── Market_Sentry_Claude_Prompt_024_Confidence_Weighted_Cross_Site_Analytics.md
│       ├── Market_Sentry_Claude_Prompt_025_Cross_Site_Analytics_Trend_Snapshots.md
│       ├── Market_Sentry_Claude_Prompt_026_Cross_Site_Trend_Alerts.md
│       ├── Market_Sentry_Claude_Prompt_027_Cross_Site_Alert_Analytics.md
│       ├── Market_Sentry_Claude_Prompt_028_Cross_Site_Alert_Triage_Workflow.md
│       ├── Market_Sentry_Claude_Prompt_029_Alert_Hygiene_Reports.md
│       ├── Market_Sentry_Claude_Prompt_030_Alert_Archive_Policy.md
│       ├── Market_Sentry_Claude_Prompt_031_Alert_Expiration_Policy.md
│       ├── Market_Sentry_Claude_Prompt_032_User_Defined_Alert_Expiration_Profiles.md
│       ├── Market_Sentry_Claude_Prompt_033_Profile_Comparison_Last_Used_Profile.md
│       ├── Market_Sentry_Claude_Prompt_034_Alert_Lifecycle_Audit_Trail.md
│       ├── Market_Sentry_Claude_Prompt_035_Alert_Lifecycle_Trends.md
│       ├── Market_Sentry_Claude_Prompt_036_Lifecycle_Health_Scoring.md
│       ├── Market_Sentry_Claude_Prompt_037_Lifecycle_Health_Trends.md
│       ├── Market_Sentry_Claude_Prompt_038_Operations_Digest.md
│       ├── Market_Sentry_Claude_Prompt_039_Operations_Digest_History.md
│       ├── Market_Sentry_Claude_Prompt_040_Portfolio_Review_Pack.md
│       ├── Market_Sentry_Claude_Prompt_041_Portfolio_Review_Comparison.md
│       ├── Market_Sentry_Claude_Prompt_042_Portfolio_Review_Trends.md
│       ├── Market_Sentry_Claude_Prompt_043_Portfolio_Trend_Alerts.md
│       ├── Market_Sentry_Claude_Prompt_044_Configurable_Portfolio_Trend_Alert_Rules.md
│       ├── Market_Sentry_Claude_Prompt_045_Portfolio_Trend_Alert_History.md
│       ├── Market_Sentry_Claude_Prompt_046_Alert_Focus_Preferences.md
│       ├── Market_Sentry_Claude_Prompt_047_Local_Email_Digest_Draft.md
│       ├── Market_Sentry_Claude_Prompt_048_Local_Operations_Bundle.md
│       ├── Market_Sentry_Claude_Prompt_051_Guided_Operator_Workflow.md
│       ├── Market_Sentry_Claude_Prompt_051A_Operator_Workflow_Stabilization.md
│       ├── Market_Sentry_Claude_Prompt_052_Redfin_Screening_Queue.md
│       ├── Market_Sentry_Claude_Prompt_052A_Global_DB_Default_Stabilization.md
│       └── Market_Sentry_Claude_Prompt_053_Screening_Queue_Batch_Actions.md
├── logs/                                      # Application logs
│   ├── .gitkeep
│   ├── marketsentry.log
│   └── retrieval_audit/                       # Retrieval compliance audit logs
│       ├── dry_run_approvals_20260514.csv     # One file per retrieval day
│       └── retrieval_audit_20260514.csv       # One file per retrieval day
├── scripts/                                   # Automation scripts
│   ├── install_task_scheduler_watchlist_refresh.ps1   # Register scheduled task
│   ├── uninstall_task_scheduler_watchlist_refresh.ps1 # Remove scheduled task
│   ├── run_marketsentry_task.ps1              # Scheduled task wrapper
│   ├── run_alert_hygiene_report.bat
│   ├── run_alert_lifecycle_trend_report.bat
│   ├── run_dashboard_summary.bat
│   ├── run_fixture_demo_workflow.bat
│   ├── run_initial_review_workflow.bat
│   ├── run_lifecycle_health_report.bat
│   ├── run_local_operations_bundle_report.bat
│   ├── run_operations_digest_report.bat
│   ├── run_portfolio_review_pack_report.bat
│   └── run_watchlist_refresh_workflow.bat
├── src/
│   ├── marketsentry.egg-info/                 # Editable-install metadata (generated)
│   │   ├── PKG-INFO
│   │   ├── SOURCES.txt
│   │   ├── dependency_links.txt
│   │   ├── entry_points.txt
│   │   ├── requires.txt
│   │   └── top_level.txt
│   └── marketsentry/                          # Main Python package
│       ├── __init__.py
│       ├── cli.py                             # CLI entry point
│       ├── config.py                          # Configuration management
│       ├── logging_config.py                  # Logging setup
│       ├── models.py                          # Data models
│       ├── database.py                        # Database operations
│       ├── schema.py                          # Database schema
│       ├── normalization.py                   # Address/data normalization
│       ├── sample_data.py                     # Sample data generation
│       ├── demo_data_cleanup.py               # Demo/sample cleanup and stray detection
│       ├── gas_detection.py                   # Gas service detection
│       ├── quiet_vibrancy.py                  # Location scoring
│       ├── scoring.py                         # Property scoring engine
│       ├── effective_dom.py                   # Effective DOM v1 calculation
│       ├── effective_dom_v2_calculator.py     # Effective DOM v2 calculation
│       ├── effective_dom_v2_persistence.py    # v2 operational persistence
│       ├── effective_dom_v2_recalc.py         # v2 recalculation workflow
│       ├── effective_dom_v2_report.py         # v2 report generation
│       ├── churn_index.py                     # Listing churn index
│       ├── review_export.py                   # Review queue export
│       ├── review_import.py                   # Review decision import
│       ├── redfin_url_utils.py                # Redfin URL validation/normalization
│       ├── redfin_url_import.py               # Manual Redfin URL import
│       ├── redfin_fixture_parser.py           # Saved HTML fixture parsing
│       ├── redfin_detail_parser.py            # Redfin detail page parser
│       ├── redfin_detail_enrichment.py        # Candidate enrichment workflow
│       ├── redfin_batch_retrieval.py          # Pending-capture batch retrieval
│       ├── redfin_screening_queue.py          # Redfin screening queue + batch actions
│       ├── retrieval_approval.py              # Batch retrieval approval workflow
│       ├── retrieval_dashboard.py             # Retrieval operations dashboard data
│       ├── retrieval_health.py                # Retrieval health checks
│       ├── retrieved_fixture_processor.py     # Retrieved fixture processing
│       ├── fixture_capture_queue.py           # Fixture capture queue
│       ├── candidate_recalc.py                # Candidate metrics recalculation
│       ├── candidate_report.py                # Candidate analysis report generation
│       ├── county_import.py                   # County record import
│       ├── county_parser.py                   # County record parsers
│       ├── county_verification.py             # County verification logic
│       ├── county_verification_report.py      # County verification report
│       ├── cross_site_url_import.py           # Cross-site URL import
│       ├── cross_site_enrichment.py           # Cross-site fixture parsing
│       ├── cross_site_fixture_processor.py    # Cross-site fixture processing
│       ├── cross_site_comparison.py           # Cross-site data comparison
│       ├── cross_site_report.py               # Cross-site comparison report
│       ├── cross_site_analytics.py            # Confidence-weighted analytics
│       ├── cross_site_analytics_report.py     # Analytics report generation
│       ├── cross_site_trends.py               # Analytics trend snapshots
│       ├── cross_site_trend_alerts.py         # Trend alert generation
│       ├── cross_site_alert_analytics.py      # Alert aggregation patterns
│       ├── cross_site_alert_triage.py         # Alert triage workflow
│       ├── cross_site_alert_hygiene.py        # Alert hygiene reminders
│       ├── cross_site_alert_archive_policy.py # Archive policy workflow
│       ├── cross_site_alert_expiration_policy.py            # Expiration policy workflow
│       ├── cross_site_alert_expiration_profile_comparison.py # Profile comparison
│       ├── cross_site_alert_lifecycle.py      # Alert lifecycle audit trail
│       ├── cross_site_alert_lifecycle_metrics.py    # Lifecycle trend snapshots
│       ├── cross_site_alert_lifecycle_health.py     # Lifecycle health scoring
│       ├── cross_site_lifecycle_health_trends.py    # Lifecycle health trends
│       ├── zillow_parser.py                   # Zillow detail page parser
│       ├── realtor_parser.py                  # Realtor.com detail page parser
│       ├── homes_parser.py                    # Homes.com detail page parser
│       ├── compass_parser.py                  # Compass detail page parser
│       ├── watchlist.py                       # Watchlist promotion logic
│       ├── monitoring.py                      # Watchlist monitoring snapshots
│       ├── monitoring_report.py               # Monitoring report generation
│       ├── operations_digest.py               # Watchlist operations digest
│       ├── operations_digest_history.py       # Operations digest history
│       ├── operator_workflow.py               # Guided operator workflow
│       ├── portfolio_review_pack.py           # Portfolio review pack
│       ├── portfolio_review_comparison.py     # Portfolio review comparison
│       ├── portfolio_review_trends.py         # Portfolio review trends
│       ├── portfolio_trend_alerts.py          # Portfolio trend alerts
│       ├── portfolio_trend_alert_history.py   # Trend alert history
│       ├── portfolio_alert_focus.py           # Alert focus preferences
│       ├── portfolio_alert_email_digest.py    # Local email digest draft
│       ├── local_operations_bundle.py         # Local operations bundle
│       ├── release_candidate.py               # Release candidate hardening checks
│       ├── release_finalization.py            # Release finalization workflow
│       ├── workflow.py                        # End-to-end workflow orchestration
│       ├── dashboard.py                       # Dashboard data loading and preparation
│       ├── dashboard_app.py                   # Streamlit dashboard application
│       ├── automation.py                      # Windows Task Scheduler automation helpers
│       └── source_adapters/                   # Live retrieval strategy
│           ├── __init__.py
│           ├── base.py                        # Base abstractions
│           ├── compliance.py                  # Compliance guardrails
│           ├── registry.py                    # Adapter registry
│           ├── http_client.py                 # Rate-limited HTTP client
│           ├── policy.py                      # Retrieval policy engine
│           ├── robots_policy.py               # Offline robots.txt parser
│           ├── rate_limiter.py                # Deterministic rate limiter
│           ├── dry_run_approval.py            # Dry-run approval gate
│           ├── audit_report.py                # Retrieval audit reporting
│           ├── redfin_adapter.py              # Redfin adapter with dry-run
│           ├── zillow_adapter.py              # Zillow stub
│           ├── realtor_adapter.py             # Realtor.com stub
│           ├── homes_adapter.py               # Homes.com stub
│           ├── compass_adapter.py             # Compass stub
│           └── county_adapter.py              # County stub
├── tests/                                     # Unit and integration tests
│   ├── __init__.py
│   ├── fixtures/                              # Test fixtures
│   │   ├── cross_site_urls.csv                # Cross-site URL import fixture
│   │   ├── redfin_search_fixture.html
│   │   ├── redfin_urls_mixed_invalid.csv
│   │   ├── redfin_urls_valid.csv
│   │   ├── county/                            # County record fixtures
│   │   │   ├── assessor/
│   │   │   │   ├── property_001.html
│   │   │   │   └── property_002_sparse.html
│   │   │   ├── permits/
│   │   │   │   └── building_permit_001.html
│   │   │   ├── recorder/
│   │   │   │   ├── deed_of_trust_001.html
│   │   │   │   ├── grant_deed_001.html
│   │   │   │   └── no_transfer_found.html
│   │   │   └── tax_collector/
│   │   │       └── property_001.html
│   │   ├── cross_site/                        # Cross-site parser corpus
│   │   │   ├── compass/
│   │   │   │   ├── garage_evidence.html
│   │   │   │   ├── gas_evidence.html
│   │   │   │   ├── missing_optional_fields.html
│   │   │   │   ├── normal_property.html
│   │   │   │   ├── price_discrepancy.html
│   │   │   │   ├── sold_or_off_market.html
│   │   │   │   ├── sparse_data.html
│   │   │   │   ├── sparse_or_malformed.html
│   │   │   │   └── status_pending.html
│   │   │   ├── homes/                         # same 9 scenario files as compass/
│   │   │   ├── realtor/                       # same 9 scenario files as compass/
│   │   │   └── zillow/                        # same 9 scenario files as compass/
│   │   ├── redfin_detail/                     # Redfin detail page fixtures
│   │   │   ├── high_noise_property.html
│   │   │   ├── listing_churn_property.html
│   │   │   ├── normal_property_with_gas.html
│   │   │   └── sparse_data_property.html
│   │   └── robots/                            # robots.txt parser fixtures
│   │       ├── block_all_robots.txt
│   │       ├── empty_robots.txt
│   │       ├── redfin_robots.txt
│   │       └── zillow_robots.txt
│   ├── logs/                                  # Test log output
│   │   └── marketsentry.log
│   ├── test_county.py
│   ├── test_cross_site_comparison.py
│   ├── test_cross_site_enrichment.py
│   ├── test_cross_site_report.py
│   ├── test_cross_site_url_import.py
│   ├── test_database.py
│   ├── test_effective_dom.py
│   ├── test_effective_dom_v1.py               # Comprehensive v1 tests
│   ├── test_effective_dom_v2.py               # Comprehensive v2 tests
│   ├── test_export_path_stabilization.py
│   ├── test_gas_detection.py
│   ├── test_monitoring.py
│   ├── test_quiet_vibrancy.py
│   ├── test_redfin_detail_parser.py
│   ├── test_redfin_fixture_parser.py
│   ├── test_redfin_url_import.py
│   ├── test_redfin_url_utils.py
│   ├── test_review_workflow.py
│   ├── test_scoring.py
│   ├── test_scoring_v1.py                     # Comprehensive v1 tests
│   ├── test_zillow_parser.py
│   ├── test_milestone_10.py                   # v2 operational integration tests
│   ├── test_milestone_11.py                   # End-to-end workflow tests
│   ├── test_milestone_12.py                   # Dashboard and report viewer tests
│   ├── test_milestone_13.py                   # Windows Task Scheduler automation tests
│   ├── test_milestone_14.py                   # Live retrieval strategy tests
│   ├── test_milestone_15.py                   # Retrieval safety / capture queue tests
│   ├── test_milestone_16.py                   # Redfin live HTTP phase 1 tests
│   ├── test_milestone_17.py                   # Retrieved fixture processing tests
│   ├── test_milestone_18.py                   # Pending-capture batch retrieval tests
│   ├── test_milestone_19.py                   # Batch retrieval approval workflow tests
│   ├── test_milestone_20.py                   # Retrieval operations dashboard tests
│   ├── test_milestone_21.py                   # Retrieval health check tests
│   ├── test_milestone_22.py                   # Cross-site adapter parity tests
│   ├── test_milestone_23.py                   # Cross-site parser quality corpus tests
│   ├── test_milestone_24.py                   # Confidence-weighted analytics tests
│   ├── test_milestone_25.py                   # Analytics trend snapshot tests
│   ├── test_milestone_26.py                   # Cross-site trend alert tests
│   ├── test_milestone_27.py                   # Alert aggregation pattern tests
│   ├── test_milestone_28.py                   # Alert triage workflow tests
│   ├── test_milestone_29.py                   # Alert hygiene reminder tests
│   ├── test_milestone_30.py                   # Opt-in alert archive policy tests
│   ├── test_milestone_31.py                   # Alert expiration policy tests
│   ├── test_milestone_32.py                   # User-defined expiration profile tests
│   ├── test_milestone_33.py                   # Profile comparison / last-used tests
│   ├── test_milestone_34.py                   # Alert lifecycle audit trail tests
│   ├── test_milestone_35.py                   # Alert lifecycle trend snapshot tests
│   ├── test_milestone_36.py                   # Lifecycle health scoring tests
│   ├── test_milestone_37.py                   # Lifecycle health trend snapshot tests
│   ├── test_milestone_38.py                   # Watchlist operations digest tests
│   ├── test_milestone_39.py                   # Operations digest history tests
│   ├── test_milestone_40.py                   # Portfolio review pack tests
│   ├── test_milestone_41.py                   # Portfolio review comparison tests
│   ├── test_milestone_42.py                   # Portfolio review trends tests
│   ├── test_milestone_43.py                   # Portfolio trend alerts tests
│   ├── test_milestone_44.py                   # Configurable trend alert rules tests
│   ├── test_milestone_45.py                   # Portfolio trend alert history tests
│   ├── test_milestone_46.py                   # Alert focus preference tests
│   ├── test_milestone_47.py                   # Local email digest draft tests
│   ├── test_milestone_48.py                   # Local operations bundle tests
│   ├── test_milestone_49.py                   # Release candidate hardening tests
│   ├── test_milestone_50.py                   # Release finalization tests
│   ├── test_milestone_51.py                   # Guided operator workflow tests
│   ├── test_milestone_52.py                   # Redfin screening queue tests
│   ├── test_milestone_52a.py                  # Database default stabilization tests
│   └── test_milestone_53.py                   # Screening batch action tests
├── .coverage                                  # Coverage data (generated)
├── .env.example                               # Example configuration
├── .gitignore
├── Architecture.md                            # Architecture documentation
├── PRD.md                                     # Product Requirements Document
├── README.md
├── dbmarketsentry.db                          # Stray DB from a mistyped --db path (untracked)
├── nul                                        # Stray Windows redirect artifact (untracked)
├── pyproject.toml                             # Project metadata and build config
└── requirements.txt                           # Python dependencies

Generated caches not shown above (all gitignored): .mypy_cache/, .pytest_cache/,
and __pycache__/ directories under src/marketsentry/, src/marketsentry/source_adapters/,
and tests/.
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=marketsentry

# Run specific test file
pytest tests/test_gas_detection.py

# Run with verbose output
pytest -v
```

## Development

### Code Quality

This project follows Python best practices:

- **Python 3.11+** required
- **PEP8** compliant code style
- **Type hints** required for all functions
- **Docstrings** required for all functions
- **Black** for code formatting
- **Ruff** for linting
- **MyPy** for type checking

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type check
mypy src/
```

### MVP 46: Local Alert Highlight Preferences and Dashboard Focus Views

- Local highlight preferences config (config/portfolio_alert_highlight_preferences.json)
- 5 models: PortfolioAlertHighlightPreferences, PortfolioAlertFocusItem, PortfolioAlertFocusSummary, PortfolioAlertFocusDigest, PortfolioAlertFocusRunResult
- 6 functions: load/validate/write_template/build_items/summarize/export_digest
- Severity, alert type, persistence, and scope filtering
- 4 sort orders: severity_then_persistence, persistence_then_severity, newest_first, property_then_severity
- Dashboard Portfolio Alert Focus View subsection
- 4 new CLI commands: portfolio-alert-focus, export-portfolio-alert-focus-digest, write-portfolio-alert-focus-template, validate-portfolio-alert-focus-config
- Scheduled script updated with focus digest export
- Focus preferences are display-only and do not mutate candidate/watchlist/alert state

### MVP 47: Local Email Digest Draft Export for Portfolio Focus Alerts

- Local email-style digest draft from focus alert items (no email sent)
- 5 models: PortfolioAlertEmailDigestDraft, PortfolioAlertEmailDigestSection, PortfolioAlertEmailDigestExportResult, PortfolioAlertEmailDigestSummary, PortfolioAlertEmailDigestRunResult
- 6 functions: build_digest/build_subject/build_plain_text/build_markdown/export/summarize
- Subject line suggestion, plain-text body, Markdown body
- Optional .eml file generation (Python standard library only, no sending)
- Safety note and manual copy/paste instructions in every draft
- sent_status always "not_sent"
- 2 new CLI commands: portfolio-alert-email-digest, export-portfolio-alert-email-digest
- Dashboard Portfolio Alert Email Draft subsection
- Scheduled script updated with email digest export
- No SMTP, Gmail, Outlook, webhooks, SMS, or outbound notifications
- No credentials stored or requested

### MVP 48: Local Operations Bundle and Release Candidate Hardening

- Command inventory with 45+ CLI commands categorized by purpose and safety flags
- Report inventory scanning data/exports/ for 20 report groups with freshness labels
- Scheduled script safety inventory with live retrieval, mutation, and notification detection
- Configuration inventory for templates and local config files
- Local safety audit with 7 static checks (browser automation, notifications, walkability, etc.)
- Database schema inventory via SQLite introspection
- Local smoke test verifying imports, config, DB init, and export directories
- Markdown and CSV bundle export
- 3 new CLI commands: local-operations-bundle, export-local-operations-bundle, local-operations-smoke-test
- Dashboard Local Operations Bundle subsection
- Dedicated scheduled script: run_local_operations_bundle_report.bat
- Read-only audit module; no mutations, no outbound notifications

### MVP 49: Release Candidate Documentation, Validation Checklist, and GitHub Release Prep

- Release candidate metadata with git info, test count, and safety status fields
- Operator acceptance checklist with documentation, command, script, safety, and quality checks
- Safe workflow inventory (17 workflows) with access type classification
- Manual approval / caution workflow inventory (10 workflows) for operations requiring operator care
- Release candidate validation with 7 automated checks (files, ops bundle, smoke test, safety audit, configs, release docs, module safety)
- Markdown and CSV release candidate report export
- Auto-generated docs/RELEASE_CANDIDATE_CHECKLIST.md and docs/RELEASE_NOTES_DRAFT.md
- 3 new CLI commands: release-candidate-summary, export-release-candidate-report, release-candidate-checklist
- Dashboard Release Candidate subsection with checklist/validation metrics
- No GitHub release or tag created automatically
- Read-only documentation/reporting milestone; no mutations, no outbound notifications

### MVP 50: Release Candidate Finalization and GitHub Release Prep

- Final release version metadata (0.1.0-rc1) with `__version__` in `__init__.py`
- Release artifact inventory (14 files/directories with existence checks)
- 13 release readiness checks (docs, scripts, safety, versioning, git)
- Manual GitHub release commands generated (tag, push, gh release) but not executed
- Final release notes (docs/RELEASE_NOTES_FINAL.md) with capabilities and safety guarantees
- Release finalization guide (docs/RELEASE_FINALIZATION_GUIDE.md)
- Markdown and CSV finalization report export
- 3 new CLI commands: release-finalization-summary, export-release-finalization-report, release-manual-github-commands
- Dashboard Release Finalization subsection with readiness/artifact metrics and command preview
- No GitHub release or tag created automatically
- No scheduled script added for finalization
- Read-only documentation/reporting milestone; no mutations, no outbound notifications

### MVP 51: Guided Operator Workflow and Dashboard Candidate Action Buttons

- Guided operator workflow module reducing command-line and CSV-editing burden
- Workflow status command showing candidate counts, missing data, and recommended actions
- One-command operator refresh workflow (recalc, Effective DOM v2, snapshot, all reports) with no live retrieval
- Candidate decision helper (save/reject/maybe/hold_for_more_data) with automatic watchlist promotion
- Candidate location scores helper (Quiet/Vibrancy with gatekeeper computation)
- Candidate noise notes helper (local field knowledge with risk levels and sources)
- Operator action summary export (Markdown and CSV)
- Dashboard Operator Workflow section with status metrics, action tables, and 4 action forms
- Dashboard candidate decision form, Quiet/Vibrancy form, noise notes form, refresh workflow button
- Non-programmer operator documentation (docs/OPERATOR_WORKFLOW.md)
- 7 new CLI commands: operator-workflow-status, candidate-decision, candidate-location-scores, candidate-noise-notes, run-operator-refresh-workflow, export-operator-action-summary
- Candidate mutations occur only through explicit operator actions
- No live retrieval, no browser automation, no outbound notifications

### MVP 52: Initial Redfin Screening Queue with Clickable Links and Save for Analysis

- Pre-candidate screening queue for initial property triage before full candidate analysis
- CSV import of Redfin URLs with optional summary fields (address, city, price, beds, baths, sqft, notes)
- Saved Redfin search HTML fixture import with local-only parsing
- Clickable Redfin URL links in dashboard table and Markdown export
- Save for Analysis action creates/links candidate in candidate_review_queue without duplication
- Reject, Hold, Mark Opened screening actions
- Screening queue status summary and item listing
- Export screening queue to CSV and Markdown with timestamps
- Dashboard Initial Redfin Screening section with metrics, table, action forms, import instructions, export button
- 9 new CLI commands: import-redfin-screening-urls, import-redfin-screening-fixture, redfin-screening-status, list-redfin-screening-items, save-screening-item-for-analysis, reject-screening-item, hold-screening-item, mark-screening-item-opened, export-redfin-screening-queue
- Operator documentation (docs/REDFIN_SCREENING_QUEUE.md)
- Screening items become candidates only through explicit Save for Analysis action
- No live retrieval, no browser automation, no outbound notifications

## Troubleshooting: Database Paths and Stray Files

### The canonical database

There is exactly one project database:

```text
db/marketsentry.db
```

Every command resolves this path from `config.database_path`. You do **not** need
to pass `--db` when running from the project root. Custom databases are still
supported with an explicit `--db <path>`.

Override the default for a whole session with the `DATABASE_PATH` environment
variable, or by setting `DATABASE_PATH` in your `.env` file.

### Known stray file artifacts

If you see any of these files, they are artifacts and contain no real data:

| File | Cause | Safe to delete |
| --- | --- | --- |
| `data/market_sentry.db` | Legacy wrong default, fixed in MVP 52A | Yes, if it holds no real data |
| `dbmarketsentry.db` | `--db db\marketsentry.db` where the backslash was consumed as a shell escape | Yes, if it holds no real data |
| `nul` | A Windows-style `2>nul` redirect run under a POSIX shell (Git Bash) | Yes |

To quote a Windows path safely, use forward slashes or quote the argument:

```powershell
python -m marketsentry.cli status --db "db\marketsentry.db"
python -m marketsentry.cli status --db db/marketsentry.db
```

### Detecting and removing strays

The cleanup command reports stray files without deleting them:

```powershell
python -m marketsentry.cli cleanup-demo-data
```

Deleting stray files requires two explicit flags together:

```powershell
python -m marketsentry.cli cleanup-demo-data --confirm --confirm-stray-files
```

### Symptom: a command reports zero data

If a report or summary shows no records unexpectedly:

1. Confirm you are running from the project root.
2. Run `python -m marketsentry.cli status` and check the reported database path.
3. Confirm `db/marketsentry.db` exists and is non-empty.
4. Check whether you passed a `--db` value pointing somewhere else.

## Demo and Sample Data Cleanup

Sample records seeded for testing make the operator console noisy. The
`cleanup-demo-data` command removes them safely.

```powershell
# Preview only. This is the default; nothing is changed.
python -m marketsentry.cli cleanup-demo-data

# Apply the cleanup
python -m marketsentry.cli cleanup-demo-data --confirm

# Apply cleanup and also delete detected stray files
python -m marketsentry.cli cleanup-demo-data --confirm --confirm-stray-files
```

### Safety model

- **Dry-run is the default.** Nothing is removed without `--confirm`.
- An explicit `--dry-run` always wins, even when combined with `--confirm`.
- Only records matching a fixed allowlist of demo marker addresses are selected.
- Real user properties are protected by an explicit denylist that is re-checked
  immediately before every deletion, independent of how the plan was built.
- Stray files are never deleted without the separate `--confirm-stray-files` flag.

### What counts as demo data

| Category | Marker addresses |
| --- | --- |
| `seeded_sample` (from `sample_data.py`) | `12345 Sample St`, `67890 Busy Ave`, `11111 Unknown Rd` |
| `screening_demo` (MVP 52 validation) | `40000 Example St`, `30000 Sample Ave`, `55555 Fixture Ln` |

Protected real properties, never removed: `31801 Valone Ct`, `31457 Britton Cir`,
`41451 Royal Dornoch Ct`, `32420 San Marco Dr`, `32152 Camino Nunez`.

## Milestone Status

Milestones 1-53, including stabilization milestone 52A, are complete. The project
is at release candidate v0.1.0-rc1.

**Note:** Milestone 51A (Operator Workflow Stabilization) fixed the operator
workflow commands. Milestone 52A completed that fix across the entire codebase:
all live code now resolves the database from `config.database_path`.

## Repository

https://github.com/rogerfiske/Market_Sentry

## License

MIT

## Documentation

- [PRD.md](PRD.md) - Product Requirements Document
- [Architecture.md](Architecture.md) - System Architecture
- [docs/RUNBOOK.md](docs/RUNBOOK.md) - Operating Runbook
- [docs/prompts/](docs/prompts/) - Implementation prompts
- [docs/SCREENING_QUEUE_BATCH_ACTIONS.md](docs/SCREENING_QUEUE_BATCH_ACTIONS.md) - Screening batch actions guide
- [docs/decisions/](docs/decisions/) - Architecture decision records

## Notes

- This is a local-first application. All data is stored in a local SQLite database.
- **No live scraping or network calls are implemented.** Milestones 3-6 use manual URL import and saved HTML fixtures.
- See design decisions for rationale:
  - [Decision 002: Redfin Discovery Adapter Foundation](docs/decisions/002-redfin-discovery-adapter-foundation.md)
  - [Decision 003: Redfin Detail Parser and Candidate Enrichment](docs/decisions/003-redfin-detail-parser-saved-fixtures.md)
  - [Decision 004: Effective DOM v1 and Review Scoring](docs/decisions/004-effective-dom-v1-and-review-scoring.md)
  - [Decision 005: Cross-Site Enrichment Foundation](docs/decisions/005-cross-site-enrichment-foundation.md)
  - [Decision 006: Watchlist Monitoring Snapshots](docs/decisions/006-watchlist-monitoring-snapshots.md)
  - [Decision 009: Effective DOM v2 Operational Integration](docs/decisions/009-effective-dom-v2-operational-integration.md)
  - [Decision 010: End-to-End Operating Workflow](docs/decisions/010-end-to-end-operating-workflow.md)
  - [Decision 011: Local Dashboard and Report Viewer](docs/decisions/011-local-dashboard-report-viewer.md)
  - [Decision 012: Windows Task Scheduler Automation](docs/decisions/012-windows-task-scheduler-automation.md)
  - [Decision 013: Live Retrieval Strategy and Compliance Adapters](docs/decisions/013-live-retrieval-strategy-and-compliance-adapters.md)
  - [Decision 014: Retrieval Safety and Fixture Capture Queue](docs/decisions/014-retrieval-safety-and-fixture-capture-queue.md)
  - [Decision 022: Cross-Site Parser Quality and Fixture Corpus](docs/decisions/022-cross-site-parser-quality-fixture-corpus.md)
  - [Decision 023: Confidence-Weighted Cross-Site Analytics](docs/decisions/023-confidence-weighted-cross-site-analytics.md)
  - [Decision 029: Cross-Site Alert Archive Policy](docs/decisions/029-cross-site-alert-archive-policy.md)
  - [Decision 030: Cross-Site Alert Expiration Policy](docs/decisions/030-cross-site-alert-expiration-policy.md)
  - [Decision 031: User-Defined Alert Expiration Profiles](docs/decisions/031-user-defined-alert-expiration-profiles.md)
  - [Decision 032: Profile Comparison and Last-Used Profile Preference](docs/decisions/032-alert-expiration-profile-comparison-preferences.md)
  - [Decision 033: Alert Lifecycle Audit Trail](docs/decisions/033-alert-lifecycle-audit-trail.md)
  - [Decision 034: Alert Lifecycle Trend Snapshots](docs/decisions/034-alert-lifecycle-trend-snapshots.md)
  - [Decision 035: Property-Level Lifecycle Health Scoring](docs/decisions/035-lifecycle-health-scoring.md)
  - [Decision 036: Lifecycle Health Trend Snapshots](docs/decisions/036-lifecycle-health-trend-snapshots.md)
  - [Decision 037: Watchlist Operations Digest](docs/decisions/037-operations-digest.md)
  - [Decision 038: Operations Digest History](docs/decisions/038-operations-digest-history.md)
  - [Decision 039: Portfolio Review Pack](docs/decisions/039-portfolio-review-pack.md)
  - [Decision 040: Portfolio Review Comparison](docs/decisions/040-portfolio-review-comparison.md)
  - [Decision 041: Portfolio Review Trends](docs/decisions/041-portfolio-review-trends.md)
  - [Decision 042: Portfolio Trend Alerts](docs/decisions/042-portfolio-trend-alerts.md)
  - [Decision 043: Configurable Portfolio Trend Alert Rules](docs/decisions/043-configurable-portfolio-trend-alert-rules.md)
- The system is designed for disciplined market observation, not automatic purchasing decisions.
- All scoring and filtering logic is deterministic and unit-tested.
- The review workflow is human-in-the-loop: candidates must be reviewed before watchlist promotion.
- Review recommendations (strong_review, review, maybe_review, reject_location_noise, needs_more_data) are NOT purchase recommendations. They only determine how candidates should be treated in the user review queue.
