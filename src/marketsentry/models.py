"""Data models for Market_Sentry."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class CandidateProperty(BaseModel):
    """Model for a candidate property in the review queue."""

    candidate_id: Optional[int] = None
    discovery_date: date
    source_site: str
    source_search_url: str
    redfin_url: str
    address: str
    normalized_address: Optional[str] = None
    city: str
    zip: str
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
    event_date: date
    source_site: str
    event_type: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    source_listing_id: Optional[str] = None
    mls_number: Optional[str] = None
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
    quiet_score: Optional[float] = None
    vibrancy_score: Optional[float] = None
    garage_spaces: Optional[int] = None
    gas_service: Optional[bool] = None
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
