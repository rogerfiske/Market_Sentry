"""Data models for Market_Sentry."""

from datetime import date, datetime
from typing import Optional

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
