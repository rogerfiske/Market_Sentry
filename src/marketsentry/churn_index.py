"""Churn Index calculation for property/listing instability metrics.

Churn Index measures recent 2-3 year property/listing instability and remains
reportable even when Effective DOM is reset by county-confirmed ownership transfer.

CRITICAL: Churn metrics are NEVER zeroed by county reset. They are preserved
separately to provide historical context on property listing behavior.
"""

from datetime import date, timedelta
from typing import List, Optional

from marketsentry.logging_config import logger
from marketsentry.models import ChurnIndexMetrics, ListingEvent


def calculate_churn_index(
    events: List[ListingEvent],
    lookback_years: int = 3,
    analysis_date: Optional[date] = None,
) -> ChurnIndexMetrics:
    """
    Calculate Churn Index from listing events with date-based filtering.

    Churn Index measures recent property/listing instability using:
    - Listing churn (removals/relists): 1.0 weight
    - DOM resets: 1.5 weight
    - Sale/rent alternation: 2.0 weight
    - Price changes: 0.5 weight

    Normalized to 0-10 scale.

    Args:
        events: List of listing events
        lookback_years: Years to look back (default 3)
        analysis_date: Analysis date (default today)

    Returns:
        ChurnIndexMetrics with calculated churn index and component counts
    """
    if analysis_date is None:
        analysis_date = date.today()

    lookback_start = analysis_date - timedelta(days=365 * lookback_years)

    # Filter events to lookback window
    filtered_events = [
        e for e in events if e.event_date and e.event_date >= lookback_start
    ]

    if not filtered_events:
        # No events in lookback window - try fallback to all events
        logger.debug(f"No events in {lookback_years}-year lookback, using all events")
        filtered_events = events

    # Count churn indicators
    listing_churn_count = 0
    dom_reset_count = 0
    sale_rent_alternation_count = 0
    price_change_count = 0

    # Track event types
    removal_count = 0
    relist_count = 0
    listing_count = 0
    sale_events = []
    rental_events = []

    for event in filtered_events:
        event_type = event.event_type.lower() if event.event_type else ""

        # Price changes
        if "price_changed" in event_type or "price" in event_type:
            price_change_count += 1

        # Removals and relists
        if "removed" in event_type:
            removal_count += 1
        elif "relisted" in event_type or "back_on_market" in event_type:
            relist_count += 1
        elif "listed" in event_type:
            # Count "listed" events after first one as potential relists
            listing_count += 1

        # Sale vs rental tracking
        if "sale" in event_type and "rental" not in event_type:
            sale_events.append(event)
        elif "rental" in event_type:
            rental_events.append(event)

    # Listing churn = removal followed by relist (or new listing after first)
    # If we have relists, use those. Otherwise, use listing_count - 1 (excluding first listing)
    effective_relist_count = relist_count if relist_count > 0 else max(0, listing_count - 1)
    listing_churn_count = min(removal_count, effective_relist_count)

    # DOM resets = relists after removal (same as churn for now)
    dom_reset_count = listing_churn_count

    # Sale/rent alternation = switches between sale and rental listings
    if sale_events and rental_events:
        # Conservative: count alternations based on event sequence
        sale_rent_alternation_count = min(len(sale_events), len(rental_events))

    # Calculate weighted churn index
    churn_index = calculate_churn_index_from_counts(
        listing_churn_count, dom_reset_count, sale_rent_alternation_count, price_change_count
    )

    return ChurnIndexMetrics(
        recent_churn_index=churn_index,
        recent_churn_lookback_years=lookback_years,
        recent_churn_event_count=len(filtered_events),
        recent_dom_reset_count=dom_reset_count,
        recent_sale_rent_alternation_count=sale_rent_alternation_count,
        recent_price_change_count=price_change_count,
        churn_calculation_method="event_based",
        churn_preserved_after_transfer=True,
    )


def calculate_churn_index_from_counts(
    listing_churn_count: int,
    dom_reset_count: int,
    sale_rent_alternation_count: int,
    price_change_count: int = 0,
) -> float:
    """
    Calculate Churn Index from raw counts.

    Fallback method when event dates are unavailable.

    Weights:
    - listing_churn_count: 1.0 each
    - dom_reset_count: 1.5 each
    - sale_rent_alternation_count: 2.0 each
    - price_change_count: 0.5 each

    Normalized to 0-10 scale (capped at 20 weighted points).

    Args:
        listing_churn_count: Number of listing churn events
        dom_reset_count: Number of DOM reset events
        sale_rent_alternation_count: Number of sale/rent alternations
        price_change_count: Number of price changes (optional)

    Returns:
        Churn index (0.0-10.0)
    """
    # Weights
    listing_churn_weight = 1.0
    dom_reset_weight = 1.5
    sale_rent_alternation_weight = 2.0
    price_change_weight = 0.5

    # Calculate weighted sum
    weighted_churn = (
        listing_churn_count * listing_churn_weight
        + dom_reset_count * dom_reset_weight
        + sale_rent_alternation_count * sale_rent_alternation_weight
        + price_change_count * price_change_weight
    )

    # Normalize to 0-10 scale (20 weighted points = 10.0)
    max_weighted_points = 20.0
    churn_index = min(10.0, (weighted_churn / max_weighted_points) * 10.0)

    return round(churn_index, 2) if churn_index > 0 else 0.0
