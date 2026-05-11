# Market_Sentry

Buyer-side real-estate market observation and watchlist system for Temecula/Murrieta residential properties.

## Project Mission

Market_Sentry is a disciplined market observation tool that helps buyers identify residential properties with significant market exposure patterns. The system begins with candidate discovery, stages candidates for user review, and monitors selected properties using Effective DOM, Quiet/Vibrancy scoring, garage spaces, gas-service evidence, listing churn, and cross-site validation.

## Current Milestone: Scheduled Triage Reminder and Alert Hygiene Reports (MVP 29)

This milestone adds alert hygiene checks and scheduled report generation for cross-site trend alerts.

- Identify stale open alerts (7+ days), old acknowledged alerts (14+ days), resolved archive candidates (30+ days)
- Detect pending needs_reparse and needs_manual_review alerts
- Identify high-burden properties and repeated unresolved alert patterns
- Configurable thresholds via `CrossSiteAlertHygieneConfig`
- CSV and Markdown report export: `data/exports/cross_site_alert_hygiene_YYYYMMDD_HHMMSS.csv`
- New CLI: `marketsentry cross-site-alert-hygiene-check`
- New CLI: `marketsentry export-cross-site-alert-hygiene-report`
- Scheduled batch script: `scripts/run_alert_hygiene_report.bat`
- Dashboard: Cross-Site Alert Hygiene subsection with severity/category counts and filters
- Hygiene reports are review aids only: they do not auto-archive alerts or change watchlist status
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
├── README.md
├── PRD.md                      # Product Requirements Document
├── Architecture.md             # Architecture documentation
├── requirements.txt            # Python dependencies
├── .env.example               # Example configuration
├── .gitignore
├── pyproject.toml             # Project metadata and build config
├── scripts/                   # Automation scripts
│   ├── run_watchlist_refresh_workflow.bat
│   ├── run_initial_review_workflow.bat
│   ├── run_dashboard_summary.bat
│   ├── run_fixture_demo_workflow.bat
│   ├── run_marketsentry_task.ps1
│   ├── install_task_scheduler_watchlist_refresh.ps1
│   └── uninstall_task_scheduler_watchlist_refresh.ps1
├── data/                      # Data directories
│   ├── raw/
│   ├── processed/
│   ├── exports/
│   └── imports/
├── db/                        # SQLite database location
├── logs/                      # Application logs
│   └── scheduled/             # Scheduled task logs
├── docs/                      # Documentation
│   ├── prompts/
│   ├── decisions/
│   └── examples/
├── src/
│   └── marketsentry/          # Main Python package
│       ├── __init__.py
│       ├── cli.py             # CLI entry point
│       ├── config.py          # Configuration management
│       ├── logging_config.py  # Logging setup
│       ├── models.py          # Data models
│       ├── database.py        # Database operations
│       ├── schema.py          # Database schema
│       ├── normalization.py   # Address/data normalization
│       ├── gas_detection.py   # Gas service detection
│       ├── quiet_vibrancy.py  # Location scoring
│       ├── effective_dom.py            # Effective DOM calculation
│       ├── scoring.py                  # Property scoring engine
│       ├── review_export.py            # Review queue export
│       ├── review_import.py            # Review decision import
│       ├── redfin_url_utils.py         # Redfin URL validation and normalization
│       ├── redfin_url_import.py        # Manual Redfin URL import
│       ├── redfin_fixture_parser.py    # Saved HTML fixture parsing
│       ├── redfin_detail_parser.py     # Redfin detail page parser
│       ├── redfin_detail_enrichment.py # Candidate enrichment workflow
│       ├── candidate_recalc.py         # Candidate metrics recalculation
│       ├── candidate_report.py         # Candidate analysis report generation
│       ├── cross_site_url_import.py    # Cross-site URL import
│       ├── cross_site_enrichment.py    # Cross-site fixture parsing
│       ├── cross_site_comparison.py    # Cross-site data comparison
│       ├── cross_site_report.py        # Cross-site comparison report
│       ├── zillow_parser.py            # Zillow detail page parser
│       ├── realtor_parser.py           # Realtor.com detail page parser
│       ├── homes_parser.py             # Homes.com detail page parser
│       ├── compass_parser.py           # Compass detail page parser
│       ├── watchlist.py                # Watchlist promotion logic
│       ├── monitoring.py               # Watchlist monitoring snapshots
│       ├── monitoring_report.py        # Monitoring report generation
│       ├── effective_dom_v2_persistence.py  # v2 operational persistence
│       ├── workflow.py                    # End-to-end workflow orchestration
│       ├── dashboard.py                   # Dashboard data loading and preparation
│       ├── dashboard_app.py               # Streamlit dashboard application
│       ├── automation.py                  # Windows Task Scheduler automation helpers
│       ├── source_adapters/               # Live retrieval strategy
│       │   ├── __init__.py
│       │   ├── base.py                    # Base abstractions
│       │   ├── compliance.py              # Compliance guardrails
│       │   ├── registry.py                # Adapter registry
│       │   ├── redfin_adapter.py          # Redfin adapter with dry-run
│       │   ├── zillow_adapter.py          # Zillow stub
│       │   ├── realtor_adapter.py         # Realtor.com stub
│       │   ├── homes_adapter.py           # Homes.com stub
│       │   ├── compass_adapter.py         # Compass stub
│       │   ├── county_adapter.py          # County stub
│       │   ├── policy.py                  # Retrieval policy engine
│       │   ├── robots_policy.py           # Offline robots.txt parser
│       │   ├── rate_limiter.py            # Deterministic rate limiter
│       │   ├── dry_run_approval.py        # Dry-run approval gate
│       │   └── audit_report.py            # Retrieval audit reporting
│       ├── fixture_capture_queue.py       # Fixture capture queue
│       └── sample_data.py              # Sample data generation
└── tests/                              # Unit tests
    ├── fixtures/                       # Test fixtures
    │   ├── redfin_urls_valid.csv
    │   ├── redfin_urls_mixed_invalid.csv
    │   ├── redfin_search_fixture.html
    │   ├── redfin_detail/              # Redfin detail page fixtures
    │   │   ├── normal_property_with_gas.html
    │   │   ├── high_noise_property.html
    │   │   ├── listing_churn_property.html
    │   │   └── sparse_data_property.html
    │   └── cross_site_urls.csv         # Cross-site URL import fixture
    ├── test_database.py
    ├── test_effective_dom.py
    ├── test_effective_dom_v1.py       # Comprehensive v1 tests
    ├── test_scoring.py
    ├── test_scoring_v1.py             # Comprehensive v1 tests
    ├── test_gas_detection.py
    ├── test_quiet_vibrancy.py
    ├── test_review_workflow.py
    ├── test_redfin_url_utils.py
    ├── test_redfin_url_import.py
    ├── test_redfin_fixture_parser.py
    ├── test_redfin_detail_parser.py
    ├── test_cross_site_url_import.py
    ├── test_cross_site_enrichment.py
    ├── test_cross_site_comparison.py
    ├── test_cross_site_report.py
    ├── test_monitoring.py
    ├── test_milestone_10.py           # v2 operational integration tests
    ├── test_milestone_11.py           # End-to-end workflow tests
    ├── test_milestone_12.py           # Dashboard and report viewer tests
    ├── test_milestone_13.py           # Windows Task Scheduler automation tests
    ├── test_milestone_14.py           # Live retrieval strategy tests
    ├── test_milestone_15.py           # Retrieval safety and fixture capture queue tests
    ├── test_milestone_23.py           # Cross-site parser quality and fixture corpus tests
    └── test_milestone_24.py           # Confidence-weighted cross-site analytics tests
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

## Next Planned Milestone

### MVP 25: (To Be Determined)

Milestones 1-24 are complete. Future milestones may include live cross-site retrieval integration, enhanced analytical workflows, or additional data source adapters.

**Note:** Milestone 24 (Confidence-Weighted Cross-Site Analytics) is now complete.

## Repository

https://github.com/rogerfiske/Market_Sentry

## License

MIT

## Documentation

- [PRD.md](PRD.md) - Product Requirements Document
- [Architecture.md](Architecture.md) - System Architecture
- [docs/RUNBOOK.md](docs/RUNBOOK.md) - Operating Runbook
- [docs/prompts/](docs/prompts/) - Implementation prompts
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
- The system is designed for disciplined market observation, not automatic purchasing decisions.
- All scoring and filtering logic is deterministic and unit-tested.
- The review workflow is human-in-the-loop: candidates must be reviewed before watchlist promotion.
- Review recommendations (strong_review, review, maybe_review, reject_location_noise, needs_more_data) are NOT purchase recommendations. They only determine how candidates should be treated in the user review queue.
