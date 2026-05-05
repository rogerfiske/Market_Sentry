"""Effective DOM v2 calculator with county-verified reset boundary support.

Effective DOM v2 uses county-confirmed ownership transfer records as reset boundaries,
excluding pre-transfer exposure from the DOM calculation while preserving all churn metrics.

CRITICAL: County reset affects Effective DOM only. Churn metrics are NEVER erased.
"""

from datetime import date, timedelta
from typing import List, Optional

from marketsentry.churn_index import calculate_churn_index, calculate_churn_index_from_counts
from marketsentry.county_verification import is_ownership_transfer_record
from marketsentry.effective_dom import calculate_all_effective_dom_metrics
from marketsentry.logging_config import logger
from marketsentry.models import (
    CountyRecordObservation,
    EffectiveDomResetBoundary,
    EffectiveDomV2Metrics,
    ListingEvent,
)


def calculate_effective_dom_v2(
    events: List[ListingEvent],
    county_records: List[CountyRecordObservation],
    displayed_dom: Optional[int] = None,
    analysis_date: Optional[date] = None,
) -> EffectiveDomV2Metrics:
    """
    Calculate Effective DOM v2 with county-verified reset boundaries.

    If a county-confirmed ownership transfer exists within the listing history window,
    it serves as a reset boundary. Pre-transfer exposure is excluded from effective_dom_v2.

    Args:
        events: List of listing events
        county_records: List of county record observations
        displayed_dom: Displayed DOM from listing site
        analysis_date: Analysis date (default today)

    Returns:
        EffectiveDomV2Metrics with v1, v2, churn, and reset information
    """
    if analysis_date is None:
        analysis_date = date.today()

    # Calculate v1 metrics (baseline)
    v1_result = calculate_all_effective_dom_metrics(events, displayed_dom, analysis_date)

    # Initialize v2 metrics with v1 values
    v2_metrics = EffectiveDomV2Metrics(
        displayed_dom=displayed_dom,
        effective_dom_v1=v1_result.effective_dom,
        effective_dom_v2=v1_result.effective_dom,  # Default to v1
        effective_dom_delta_v1=v1_result.effective_dom_delta,
        effective_dom_delta_v2=v1_result.effective_dom_delta,  # Default to v1
        county_reset_applied=False,
        listing_churn_count=v1_result.listing_churn_count,
        dom_reset_count=v1_result.dom_reset_count,
        sale_rent_alternation_count=v1_result.sale_rent_alternation_count,
        price_change_count=v1_result.price_change_count,
        churn_preserved_after_transfer=True,  # Always true
    )

    # Find event timeline
    if events:
        event_dates = [e.event_date for e in events if e.event_date]
        if event_dates:
            v2_metrics.first_observed_event_date = min(event_dates)
            v2_metrics.latest_observed_event_date = max(event_dates)

    # Find most recent county-confirmed ownership transfer
    reset_boundary = _find_reset_boundary(county_records, events, analysis_date)

    if not reset_boundary:
        # No county reset - v2 equals v1
        # Calculate churn index
        churn_metrics = calculate_churn_index(events, lookback_years=3, analysis_date=analysis_date)
        v2_metrics.recent_churn_index = churn_metrics.recent_churn_index
        v2_metrics.recent_churn_lookback_years = churn_metrics.recent_churn_lookback_years
        v2_metrics.recent_churn_event_count = churn_metrics.recent_churn_event_count
        v2_metrics.recent_dom_reset_count = churn_metrics.recent_dom_reset_count
        v2_metrics.recent_sale_rent_alternation_count = churn_metrics.recent_sale_rent_alternation_count

        return v2_metrics

    # County reset found - apply reset boundary
    v2_metrics.county_reset_applied = True
    v2_metrics.county_reset_date = reset_boundary.reset_date
    v2_metrics.county_reset_record_type = reset_boundary.normalized_record_type
    v2_metrics.county_reset_record_id = reset_boundary.document_number  # Use document_number as record identifier
    v2_metrics.county_reset_confidence = reset_boundary.confidence

    # Split events into pre-reset and post-reset
    pre_reset_events = [
        e for e in events if e.event_date and e.event_date < reset_boundary.reset_date
    ]
    post_reset_events = [
        e for e in events if e.event_date and e.event_date >= reset_boundary.reset_date
    ]

    # Calculate pre-reset exposure metrics (for reporting only)
    if pre_reset_events:
        pre_reset_v1 = calculate_all_effective_dom_metrics(pre_reset_events, None, reset_boundary.reset_date)
        v2_metrics.pre_reset_calendar_exposure_dom = pre_reset_v1.calendar_exposure_dom
        v2_metrics.pre_reset_sale_cycle_dom = pre_reset_v1.sale_cycle_dom
        v2_metrics.pre_reset_rent_sale_exposure_dom = pre_reset_v1.rent_sale_exposure_dom

    # Calculate post-reset exposure metrics (used for v2)
    if post_reset_events:
        post_reset_v1 = calculate_all_effective_dom_metrics(post_reset_events, displayed_dom, analysis_date)
        v2_metrics.effective_dom_v2 = post_reset_v1.effective_dom
        v2_metrics.effective_dom_delta_v2 = post_reset_v1.effective_dom_delta
        v2_metrics.post_reset_calendar_exposure_dom = post_reset_v1.calendar_exposure_dom
        v2_metrics.post_reset_sale_cycle_dom = post_reset_v1.sale_cycle_dom
        v2_metrics.post_reset_rent_sale_exposure_dom = post_reset_v1.rent_sale_exposure_dom

        post_event_dates = [e.event_date for e in post_reset_events if e.event_date]
        if post_event_dates:
            v2_metrics.first_post_reset_event_date = min(post_event_dates)
            v2_metrics.latest_post_reset_event_date = max(post_event_dates)
    else:
        # No post-reset events - v2 is 0 or minimal
        v2_metrics.effective_dom_v2 = 0
        v2_metrics.effective_dom_delta_v2 = 0 if displayed_dom is None else -displayed_dom
        v2_metrics.post_reset_calendar_exposure_dom = 0
        v2_metrics.post_reset_sale_cycle_dom = 0
        v2_metrics.post_reset_rent_sale_exposure_dom = 0

    # Calculate churn index from ALL events (not affected by reset)
    churn_metrics = calculate_churn_index(events, lookback_years=3, analysis_date=analysis_date)
    v2_metrics.recent_churn_index = churn_metrics.recent_churn_index
    v2_metrics.recent_churn_lookback_years = churn_metrics.recent_churn_lookback_years
    v2_metrics.recent_churn_event_count = churn_metrics.recent_churn_event_count
    v2_metrics.recent_dom_reset_count = churn_metrics.recent_dom_reset_count
    v2_metrics.recent_sale_rent_alternation_count = churn_metrics.recent_sale_rent_alternation_count

    return v2_metrics


def _find_reset_boundary(
    county_records: List[CountyRecordObservation],
    events: List[ListingEvent],
    analysis_date: date,
) -> Optional[EffectiveDomResetBoundary]:
    """
    Find the most recent county-confirmed ownership transfer that serves as a reset boundary.

    Reset boundary logic:
    - Must be an ownership transfer record (grant_deed, quitclaim_deed, trustee_deed, warranty_deed)
    - Must occur within or before the listing history window
    - Must not occur after the latest listing event (no future resets)
    - Most recent transfer is used if multiple exist

    Args:
        county_records: List of county record observations
        events: List of listing events
        analysis_date: Analysis date

    Returns:
        EffectiveDomResetBoundary or None if no valid reset boundary exists
    """
    if not county_records:
        return None

    # Get event date range
    event_dates = [e.event_date for e in events if e.event_date]
    if not event_dates:
        return None

    first_event_date = min(event_dates)
    latest_event_date = max(event_dates)

    # Find ownership transfer records
    transfer_records = []
    for record in county_records:
        if not record.record_date:
            continue

        # Must be ownership transfer
        if not is_ownership_transfer_record(record.record_type or "", record.document_title):
            continue

        # Must not be after latest event (no future resets)
        if record.record_date > latest_event_date:
            logger.debug(
                f"Skipping county transfer on {record.record_date} - after latest event {latest_event_date}"
            )
            continue

        # Valid transfer record
        transfer_records.append(record)

    if not transfer_records:
        return None

    # Use most recent transfer
    most_recent_transfer = max(transfer_records, key=lambda r: r.record_date)

    # If transfer is before all events, it doesn't reset the listing history we're analyzing
    # (the listing history already started after the transfer)
    if most_recent_transfer.record_date < first_event_date:
        logger.debug(
            f"County transfer on {most_recent_transfer.record_date} is before first event {first_event_date} - no reset needed"
        )
        return None

    # Transfer is inside listing window - use as reset boundary
    return EffectiveDomResetBoundary(
        county_record_id=most_recent_transfer.county_record_id,
        reset_date=most_recent_transfer.record_date,
        record_type=most_recent_transfer.record_type,
        normalized_record_type=most_recent_transfer.normalized_record_type,
        document_number=most_recent_transfer.document_number,
        sale_price=most_recent_transfer.sale_price,
        confidence=most_recent_transfer.confidence or "medium",
        notes=most_recent_transfer.notes,
    )
