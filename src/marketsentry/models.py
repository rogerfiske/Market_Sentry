"""Data models for Market_Sentry."""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class CandidateProperty(BaseModel):
    """Model for a candidate property in the review queue."""

    candidate_id: Optional[int] = None
    discovery_date: Optional[date] = Field(default_factory=date.today)
    source_site: str = "redfin"
    source_search_url: str = ""
    redfin_url: str = ""
    address: str = ""
    normalized_address: Optional[str] = None
    city: str = ""
    zip: str = ""
    price: Optional[float] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    lot_size: Optional[float] = None
    displayed_dom: Optional[int] = None
    quiet_score: Optional[float] = None
    vibrancy_score: Optional[float] = None
    quiet_gatekeeper_result: Optional[str] = None
    garage_spaces: Optional[int] = None
    gas_service: Optional[bool] = None
    gas_evidence: Optional[str] = None
    effective_dom_estimate: Optional[int] = None
    listing_churn_count: Optional[int] = None
    dom_reset_count: Optional[int] = None
    sale_rent_alternation_count: Optional[int] = None
    review_status: str = Field(default="pending")
    user_decision: Optional[str] = None
    user_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class WatchedProperty(BaseModel):
    """Model for a property being actively watched."""

    property_id: Optional[int] = None
    first_saved_date: date
    active_watch_status: bool = Field(default=True)
    redfin_url: Optional[str] = None
    zillow_url: Optional[str] = None
    realtor_url: Optional[str] = None
    homes_url: Optional[str] = None
    compass_url: Optional[str] = None
    address: str
    normalized_address: Optional[str] = None
    city: str
    zip: str
    apn: Optional[str] = None
    current_price: Optional[float] = None
    original_observed_price: Optional[float] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    lot_size: Optional[float] = None
    garage_spaces: Optional[int] = None
    gas_service: Optional[bool] = None
    gas_evidence: Optional[str] = None
    quiet_score: Optional[float] = None
    vibrancy_score: Optional[float] = None
    displayed_dom: Optional[int] = None
    effective_dom: Optional[int] = None
    effective_dom_delta: Optional[int] = None
    listing_churn_count: Optional[int] = None
    dom_reset_count: Optional[int] = None
    sale_rent_alternation_count: Optional[int] = None
    county_sale_verified: Optional[bool] = None
    ownership_transfer_found: Optional[bool] = None
    last_checked_date: Optional[date] = None
    next_check_date: Optional[date] = None
    watch_priority: Optional[int] = None
    user_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ListingEvent(BaseModel):
    """Model for a listing event."""

    event_id: Optional[int] = None
    property_id: Optional[int] = None
    candidate_id: Optional[int] = None
    event_date: Optional[date] = None
    source_site: str = "redfin"
    event_type: str = "unknown"
    price: Optional[float] = None  # Price associated with the event (for price changes, listings, etc.)
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    source_listing_id: Optional[str] = None
    mls_number: Optional[str] = None
    source_mls: Optional[str] = None  # Source MLS (SDMLS, CRMLS, etc.)
    confidence: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class ObservationSnapshot(BaseModel):
    """Model for a property observation snapshot."""

    snapshot_id: Optional[int] = None
    property_id: int
    snapshot_date: datetime
    source_site: str
    listing_status: Optional[str] = None
    price: Optional[float] = None
    displayed_dom: Optional[int] = None
    effective_dom: Optional[int] = None
    effective_dom_delta: Optional[int] = None
    quiet_score: Optional[float] = None
    vibrancy_score: Optional[float] = None
    garage_spaces: Optional[int] = None
    gas_service: Optional[bool] = None
    listing_churn_count: Optional[int] = None
    dom_reset_count: Optional[int] = None
    sale_rent_alternation_count: Optional[int] = None
    cross_site_confidence_score: Optional[float] = None
    price_discrepancy_flag: bool = Field(default=False)
    status_discrepancy_flag: bool = Field(default=False)
    dom_discrepancy_flag: bool = Field(default=False)
    price_change_count: int = Field(default=0)
    listing_history_hash: Optional[str] = None
    property_detail_hash: Optional[str] = None
    raw_source_url: Optional[str] = None
    notes: Optional[str] = None


class ReviewDecision(BaseModel):
    """Model for a user review decision."""

    review_action_id: Optional[int] = None
    candidate_id: int
    action_date: datetime = Field(default_factory=datetime.now)
    user_decision: str
    user_notes: Optional[str] = None
    promoted_property_id: Optional[int] = None


class ScoreResult(BaseModel):
    """Model for scoring results."""

    property_id: Optional[int] = None
    candidate_id: Optional[int] = None
    location_fit_score: Optional[float] = None
    quiet_gatekeeper_result: Optional[str] = None
    property_fit_score: Optional[float] = None
    effective_dom_leverage_score: Optional[float] = None
    data_confidence_score: Optional[float] = None
    overall_score: Optional[float] = None
    scoring_notes: Optional[str] = None


class RedfinSearchConfig(BaseModel):
    """Model for Redfin search configuration."""

    config_id: Optional[int] = None
    config_name: str
    search_url: str
    city: str
    active: bool = Field(default=True)
    notes: Optional[str] = None


class RedfinCandidateSummary(BaseModel):
    """Model for a Redfin candidate summary extracted from search or URL."""

    redfin_url: str
    source_site: str = Field(default="redfin")
    source_search_url: Optional[str] = None
    address: Optional[str] = None
    normalized_address: Optional[str] = None
    city: Optional[str] = None
    zip: Optional[str] = None
    price: Optional[float] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    lot_size: Optional[float] = None
    displayed_dom: Optional[int] = None
    quiet_score: Optional[float] = None
    vibrancy_score: Optional[float] = None
    quiet_gatekeeper_result: Optional[str] = None
    garage_spaces: Optional[int] = None
    gas_service: Optional[bool] = None
    gas_evidence: Optional[str] = None
    basic_notes: Optional[str] = None


class RedfinParseResult(BaseModel):
    """Model for results from parsing Redfin HTML fixtures."""

    source_file: Optional[str] = None
    parse_status: str  # success, partial, failed
    candidates_found: int = Field(default=0)
    candidates: List[RedfinCandidateSummary] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class DiscoveryRunResult(BaseModel):
    """Model for results from a discovery run."""

    run_date: datetime = Field(default_factory=datetime.now)
    source_type: str  # manual_url_import, saved_fixture, live_search
    source_identifier: str  # file path or search URL
    total_rows_read: int = Field(default=0)
    candidates_inserted: int = Field(default=0)
    candidates_skipped: int = Field(default=0)
    rows_rejected: int = Field(default=0)
    parse_warnings: int = Field(default=0)
    parse_errors: int = Field(default=0)
    notes: Optional[str] = None


class RedfinLifestyleScores(BaseModel):
    """Model for Redfin lifestyle scores (Quiet/Vibrancy)."""

    quiet_score: Optional[float] = None
    quiet_label: Optional[str] = None
    quiet_raw_text: Optional[str] = None
    vibrancy_score: Optional[float] = None
    vibrancy_label: Optional[str] = None
    vibrancy_raw_text: Optional[str] = None


class RedfinPropertyFacts(BaseModel):
    """Model for Redfin property facts."""

    price: Optional[float] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    lot_size: Optional[float] = None
    year_built: Optional[int] = None
    property_type: Optional[str] = None
    garage_spaces: Optional[int] = None
    parking_features_raw: Optional[str] = None
    hoa_fee: Optional[float] = None
    property_description: Optional[str] = None
    features_raw: Optional[str] = None
    utilities_raw: Optional[str] = None


class RedfinListingHistoryEvent(BaseModel):
    """Model for a single listing history event."""

    event_date: Optional[date] = None
    event_type: str  # listed, price_changed, removed, relisted, pending, back_on_market, sold, rental_listed, rental_removed, unknown
    price: Optional[float] = None
    raw_text: str
    source_listing_id: Optional[str] = None
    mls_number: Optional[str] = None
    source_mls: Optional[str] = None
    confidence: str = Field(default="medium")  # low, medium, high


class RedfinPropertyDetail(BaseModel):
    """Model for comprehensive Redfin property detail."""

    # Property identity
    redfin_url: Optional[str] = None
    redfin_home_id: Optional[str] = None
    address: Optional[str] = None
    normalized_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    apn: Optional[str] = None
    mls_number: Optional[str] = None
    source_mls: Optional[str] = None

    # Property facts
    facts: Optional[RedfinPropertyFacts] = None

    # Lifestyle scores
    lifestyle_scores: Optional[RedfinLifestyleScores] = None

    # Gas evidence
    gas_service: Optional[bool] = None
    gas_evidence: Optional[str] = None
    gas_evidence_source: Optional[str] = None

    # Listing history
    listing_history: List[RedfinListingHistoryEvent] = Field(default_factory=list)

    # Displayed DOM (if extractable from page)
    displayed_dom: Optional[int] = None


class RedfinDetailParseResult(BaseModel):
    """Model for results from parsing a Redfin detail page."""

    source_file: Optional[str] = None
    parse_status: str  # success, partial, failed
    property_detail: Optional[RedfinPropertyDetail] = None
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class RedfinDetailEnrichmentResult(BaseModel):
    """Model for results from enriching candidates with detail data."""

    total_files_processed: int = Field(default=0)
    details_parsed: int = Field(default=0)
    candidates_matched: int = Field(default=0)
    candidates_updated: int = Field(default=0)
    listing_events_inserted: int = Field(default=0)
    listing_events_skipped: int = Field(default=0)
    parse_warnings: int = Field(default=0)
    parse_errors: int = Field(default=0)
    notes: Optional[str] = None


# Cross-Site Enrichment Models


class CrossSiteSource(str, Enum):
    """Enumeration of cross-site sources."""

    zillow = "zillow"
    realtor = "realtor"
    homes = "homes"
    compass = "compass"


class CrossSiteUrlImportRow(BaseModel):
    """Model for a row in a cross-site URL import CSV."""

    redfin_url: Optional[str] = None
    address: Optional[str] = None
    normalized_address: Optional[str] = None
    zillow_url: Optional[str] = None
    realtor_url: Optional[str] = None
    homes_url: Optional[str] = None
    compass_url: Optional[str] = None
    notes: Optional[str] = None


class CrossSiteObservation(BaseModel):
    """Model for a cross-site observation."""

    observation_id: Optional[int] = None
    candidate_id: Optional[int] = None
    property_id: Optional[int] = None
    source_site: str
    source_url: str
    normalized_source_url: Optional[str] = None
    observed_at: datetime = Field(default_factory=datetime.now)
    match_method: Optional[str] = None
    address: Optional[str] = None
    normalized_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    price: Optional[float] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    lot_size: Optional[float] = None
    listing_status: Optional[str] = None
    displayed_dom: Optional[int] = None
    garage_spaces: Optional[int] = None
    gas_service: Optional[bool] = None
    gas_evidence: Optional[str] = None
    listing_agent: Optional[str] = None
    listing_broker: Optional[str] = None
    mls_number: Optional[str] = None
    source_mls: Optional[str] = None
    property_description: Optional[str] = None
    parse_status: str = Field(default="success")
    parse_warnings: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class CrossSitePropertyFacts(BaseModel):
    """Model for cross-site property facts."""

    price: Optional[float] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    lot_size: Optional[float] = None
    listing_status: Optional[str] = None
    displayed_dom: Optional[int] = None
    garage_spaces: Optional[int] = None
    gas_service: Optional[bool] = None
    gas_evidence: Optional[str] = None
    property_description: Optional[str] = None


class CrossSiteParseResult(BaseModel):
    """Model for results from parsing a cross-site detail page."""

    source_file: Optional[str] = None
    source_site: str
    parse_status: str  # success, partial, failed
    property_facts: Optional[CrossSitePropertyFacts] = None
    source_url: Optional[str] = None
    address: Optional[str] = None
    normalized_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class CrossSiteComparisonResult(BaseModel):
    """Model for cross-site comparison results."""

    property_id: Optional[int] = None
    redfin_price: Optional[float] = None
    zillow_price: Optional[float] = None
    realtor_price: Optional[float] = None
    homes_price: Optional[float] = None
    compass_price: Optional[float] = None
    redfin_status: Optional[str] = None
    zillow_status: Optional[str] = None
    realtor_status: Optional[str] = None
    homes_status: Optional[str] = None
    compass_status: Optional[str] = None
    redfin_dom: Optional[int] = None
    zillow_dom: Optional[int] = None
    realtor_dom: Optional[int] = None
    homes_dom: Optional[int] = None
    compass_dom: Optional[int] = None
    has_price_discrepancy: bool = Field(default=False)
    has_status_discrepancy: bool = Field(default=False)
    has_dom_discrepancy: bool = Field(default=False)
    price_discrepancy_details: Optional[str] = None
    status_discrepancy_details: Optional[str] = None
    dom_discrepancy_details: Optional[str] = None
    comparison_notes: Optional[str] = None


class CrossSiteEnrichmentResult(BaseModel):
    """Model for results from cross-site enrichment."""

    total_files_processed: int = Field(default=0)
    observations_parsed: int = Field(default=0)
    observations_inserted: int = Field(default=0)
    properties_matched: int = Field(default=0)
    parse_warnings: int = Field(default=0)
    parse_errors: int = Field(default=0)
    notes: Optional[str] = None


class CrossSiteUrlImportResult(BaseModel):
    """Model for results from cross-site URL import."""

    total_rows_read: int = Field(default=0)
    properties_matched: int = Field(default=0)
    properties_updated: int = Field(default=0)
    rows_skipped: int = Field(default=0)
    errors: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


# Monitoring Models


class SnapshotChangeResult(BaseModel):
    """Model for snapshot change detection results."""

    property_id: int
    has_changes: bool = Field(default=False)
    price_changed: bool = Field(default=False)
    price_increased: bool = Field(default=False)
    price_decreased: bool = Field(default=False)
    price_change_amount: Optional[float] = None
    status_changed: bool = Field(default=False)
    displayed_dom_changed: bool = Field(default=False)
    effective_dom_changed: bool = Field(default=False)
    quiet_score_changed: bool = Field(default=False)
    vibrancy_score_changed: bool = Field(default=False)
    garage_spaces_changed: bool = Field(default=False)
    gas_service_changed: bool = Field(default=False)
    discrepancy_flag_changed: bool = Field(default=False)
    source_presence_changed: bool = Field(default=False)
    change_summary: Optional[str] = None
    change_details: List[str] = Field(default_factory=list)


class MonitoringSnapshotResult(BaseModel):
    """Model for monitoring snapshot creation result."""

    property_id: int
    snapshot_id: Optional[int] = None
    snapshot_created: bool = Field(default=False)
    snapshot_skipped: bool = Field(default=False)
    skip_reason: Optional[str] = None
    changes_detected: Optional[SnapshotChangeResult] = None
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class MonitoringRunResult(BaseModel):
    """Model for monitoring run results."""

    run_date: datetime = Field(default_factory=datetime.now)
    properties_scanned: int = Field(default=0)
    snapshots_created: int = Field(default=0)
    snapshots_skipped: int = Field(default=0)
    changes_detected_count: int = Field(default=0)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


# County Verification Models


class CountyRecordImportRow(BaseModel):
    """Model for a row in a county records CSV import."""

    source_type: str
    record_date: Optional[date] = None
    record_type: str
    apn: Optional[str] = None
    address: Optional[str] = None
    candidate_id: Optional[int] = None
    property_id: Optional[int] = None
    city: Optional[str] = None
    zip: Optional[str] = None
    document_number: Optional[str] = None
    document_title: Optional[str] = None
    grantor: Optional[str] = None
    grantee: Optional[str] = None
    sale_price: Optional[float] = None
    transfer_tax: Optional[float] = None
    assessed_value: Optional[float] = None
    owner_name: Optional[str] = None
    permit_number: Optional[str] = None
    permit_type: Optional[str] = None
    permit_status: Optional[str] = None
    notes: Optional[str] = None
    source_url: Optional[str] = None


class CountyRecordObservation(BaseModel):
    """Model for a county record observation."""

    county_record_id: Optional[int] = None
    candidate_id: Optional[int] = None
    property_id: Optional[int] = None
    source_type: str
    county_name: Optional[str] = Field(default="Riverside")
    source_url: Optional[str] = None
    record_date: Optional[date] = None
    record_type: str
    normalized_record_type: Optional[str] = None
    document_number: Optional[str] = None
    document_title: Optional[str] = None
    apn: Optional[str] = None
    normalized_apn: Optional[str] = None
    address: Optional[str] = None
    normalized_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = Field(default="CA")
    zip: Optional[str] = None
    grantor: Optional[str] = None
    grantee: Optional[str] = None
    sale_price: Optional[float] = None
    transfer_tax: Optional[float] = None
    assessed_value: Optional[float] = None
    owner_name: Optional[str] = None
    permit_number: Optional[str] = None
    permit_type: Optional[str] = None
    permit_status: Optional[str] = None
    match_method: Optional[str] = None
    confidence: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class CountyRecordParseResult(BaseModel):
    """Model for results from parsing county record HTML."""

    source_file: Optional[str] = None
    source_type: str
    parse_status: str  # success, partial, failed
    county_record: Optional[CountyRecordObservation] = None
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class CountyTransferEvent(BaseModel):
    """Model for a county-confirmed ownership transfer event."""

    county_record_id: int
    property_id: Optional[int] = None
    candidate_id: Optional[int] = None
    transfer_date: date
    record_type: str
    normalized_record_type: str
    document_number: Optional[str] = None
    sale_price: Optional[float] = None
    transfer_tax: Optional[float] = None
    grantor: Optional[str] = None
    grantee: Optional[str] = None
    confidence: str = Field(default="medium")
    notes: Optional[str] = None


class CountyVerificationResult(BaseModel):
    """Model for county verification result for a property."""

    property_id: Optional[int] = None
    candidate_id: Optional[int] = None
    cycle_start: Optional[date] = None
    cycle_end: Optional[date] = None
    county_records_seen: int = Field(default=0)
    county_transfer_found: bool = Field(default=False)
    county_transfer_date: Optional[date] = None
    county_transfer_record_type: Optional[str] = None
    county_transfer_document_number: Optional[str] = None
    county_transfer_confidence: Optional[str] = None
    county_reset_supported: bool = Field(default=False)
    assessor_seen: bool = Field(default=False)
    recorder_seen: bool = Field(default=False)
    tax_collector_seen: bool = Field(default=False)
    permit_seen: bool = Field(default=False)
    assessed_value: Optional[float] = None
    latest_permit_type: Optional[str] = None
    latest_permit_status: Optional[str] = None
    verification_notes: Optional[str] = None


class CountyRecordImportResult(BaseModel):
    """Model for results from county record CSV import."""

    total_rows_read: int = Field(default=0)
    rows_inserted: int = Field(default=0)
    rows_matched: int = Field(default=0)
    rows_unmatched: int = Field(default=0)
    rows_rejected: int = Field(default=0)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class CountyVerificationReportRow(BaseModel):
    """Model for a row in the county verification report."""

    property_id: Optional[int] = None
    candidate_id: Optional[int] = None
    address: Optional[str] = None
    city: Optional[str] = None
    zip: Optional[str] = None
    apn: Optional[str] = None
    redfin_url: Optional[str] = None
    current_price: Optional[float] = None
    effective_dom: Optional[int] = None
    displayed_dom: Optional[int] = None
    listing_churn_count: Optional[int] = None
    dom_reset_count: Optional[int] = None
    sale_rent_alternation_count: Optional[int] = None
    recent_churn_index: Optional[float] = None
    recent_churn_lookback_years: Optional[int] = Field(default=3)
    recent_churn_event_count: Optional[int] = None
    recent_dom_reset_count: Optional[int] = None
    recent_sale_rent_alternation_count: Optional[int] = None
    churn_preserved_after_transfer: bool = Field(default=True)
    county_records_seen: int = Field(default=0)
    county_transfer_found: bool = Field(default=False)
    county_transfer_date: Optional[date] = None
    county_transfer_record_type: Optional[str] = None
    county_transfer_document_number: Optional[str] = None
    county_transfer_confidence: Optional[str] = None
    county_reset_supported: bool = Field(default=False)
    assessor_seen: bool = Field(default=False)
    recorder_seen: bool = Field(default=False)
    tax_collector_seen: bool = Field(default=False)
    permit_seen: bool = Field(default=False)
    assessed_value: Optional[float] = None
    latest_permit_type: Optional[str] = None
    latest_permit_status: Optional[str] = None
    verification_notes: Optional[str] = None
    user_notes: Optional[str] = None


# Effective DOM v2 Models


class EffectiveDomResetBoundary(BaseModel):
    """Model for a county-verified reset boundary."""

    county_record_id: Optional[int] = None
    reset_date: date
    record_type: str
    normalized_record_type: str
    document_number: Optional[str] = None
    sale_price: Optional[float] = None
    confidence: str = Field(default="medium")
    notes: Optional[str] = None


class ChurnIndexMetrics(BaseModel):
    """Model for Churn Index metrics."""

    recent_churn_index: Optional[float] = None
    recent_churn_lookback_years: int = Field(default=3)
    recent_churn_event_count: int = Field(default=0)
    recent_dom_reset_count: int = Field(default=0)
    recent_sale_rent_alternation_count: int = Field(default=0)
    recent_price_change_count: int = Field(default=0)
    churn_calculation_method: str = Field(default="event_based")  # event_based or count_based
    churn_preserved_after_transfer: bool = Field(default=True)


class EffectiveDomV2Metrics(BaseModel):
    """Model for Effective DOM v2 metrics with county reset integration."""

    # Property identification
    property_id: Optional[int] = None
    candidate_id: Optional[int] = None

    # Basic DOM metrics
    displayed_dom: Optional[int] = None
    effective_dom_v1: Optional[int] = None
    effective_dom_v2: Optional[int] = None
    effective_dom_delta_v1: Optional[int] = None
    effective_dom_delta_v2: Optional[int] = None

    # County reset information
    county_reset_applied: bool = Field(default=False)
    county_reset_date: Optional[date] = None
    county_reset_record_type: Optional[str] = None
    county_reset_record_id: Optional[str] = None  # Document number or record identifier
    county_reset_confidence: Optional[str] = None

    # Pre/post reset exposure metrics
    pre_reset_calendar_exposure_dom: Optional[int] = None
    post_reset_calendar_exposure_dom: Optional[int] = None
    pre_reset_sale_cycle_dom: Optional[int] = None
    post_reset_sale_cycle_dom: Optional[int] = None
    pre_reset_rent_sale_exposure_dom: Optional[int] = None
    post_reset_rent_sale_exposure_dom: Optional[int] = None

    # Event timeline
    first_observed_event_date: Optional[date] = None
    latest_observed_event_date: Optional[date] = None
    first_post_reset_event_date: Optional[date] = None
    latest_post_reset_event_date: Optional[date] = None

    # Churn metrics (preserved separately)
    listing_churn_count: int = Field(default=0)
    dom_reset_count: int = Field(default=0)
    sale_rent_alternation_count: int = Field(default=0)
    price_change_count: int = Field(default=0)

    # Churn Index
    recent_churn_index: Optional[float] = None
    recent_churn_lookback_years: int = Field(default=3)
    recent_churn_event_count: int = Field(default=0)
    recent_dom_reset_count: int = Field(default=0)
    recent_sale_rent_alternation_count: int = Field(default=0)
    churn_preserved_after_transfer: bool = Field(default=True)


class CountyResetIntegrationResult(BaseModel):
    """Model for results from county reset integration."""

    properties_scanned: int = Field(default=0)
    county_transfers_considered: int = Field(default=0)
    county_resets_applied: int = Field(default=0)
    records_updated: int = Field(default=0)
    churn_metrics_preserved: int = Field(default=0)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class EffectiveDomComparisonRow(BaseModel):
    """Model for a row in the Effective DOM v2 comparison report."""

    property_id: Optional[int] = None
    candidate_id: Optional[int] = None
    address: Optional[str] = None
    city: Optional[str] = None
    zip: Optional[str] = None
    apn: Optional[str] = None
    redfin_url: Optional[str] = None
    current_price: Optional[float] = None
    displayed_dom: Optional[int] = None
    effective_dom_v1: Optional[int] = None
    effective_dom_v2: Optional[int] = None
    effective_dom_delta_v1: Optional[int] = None
    effective_dom_delta_v2: Optional[int] = None
    county_reset_applied: bool = Field(default=False)
    county_reset_date: Optional[date] = None
    county_reset_record_type: Optional[str] = None
    county_reset_record_id: Optional[int] = None
    county_reset_confidence: Optional[str] = None
    pre_reset_calendar_exposure_dom: Optional[int] = None
    post_reset_calendar_exposure_dom: Optional[int] = None
    pre_reset_sale_cycle_dom: Optional[int] = None
    post_reset_sale_cycle_dom: Optional[int] = None
    pre_reset_rent_sale_exposure_dom: Optional[int] = None
    post_reset_rent_sale_exposure_dom: Optional[int] = None
    listing_churn_count: int = Field(default=0)
    dom_reset_count: int = Field(default=0)
    sale_rent_alternation_count: int = Field(default=0)
    price_change_count: int = Field(default=0)
    recent_churn_index: Optional[float] = None
    recent_churn_lookback_years: int = Field(default=3)
    recent_churn_event_count: int = Field(default=0)
    recent_dom_reset_count: int = Field(default=0)
    recent_sale_rent_alternation_count: int = Field(default=0)
    churn_preserved_after_transfer: bool = Field(default=True)
    quiet_score: Optional[float] = None
    vibrancy_score: Optional[float] = None
    quiet_gatekeeper_result: Optional[str] = None
    gas_service: Optional[bool] = None
    garage_spaces: Optional[int] = None
    user_notes: Optional[str] = None
    notes: Optional[str] = None
