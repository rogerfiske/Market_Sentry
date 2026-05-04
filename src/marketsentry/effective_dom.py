"""Effective DOM calculation utilities."""

from datetime import date, timedelta
from typing import List, Optional

from marketsentry.config import config
from marketsentry.models import ListingEvent


def calculate_effective_dom(
    listing_events: List[ListingEvent],
    current_date: Optional[date] = None,
    lookback_days: Optional[int] = None,
) -> int:
    """
    Calculate Effective DOM for a property.

    Effective DOM measures property-level market exposure across listing,
    removal, and relisting events within a defined lookback window,
    excluding periods reset by confirmed ownership transfer.

    This is a placeholder implementation for Milestone 1.
    Full implementation will be in Milestone 5.

    Args:
        listing_events: List of listing events for the property
        current_date: Reference date for calculation (defaults to today)
        lookback_days: Lookback window in days (defaults to config value)

    Returns:
        Effective DOM in days
    """
    if not listing_events:
        return 0

    current_date = current_date or date.today()
    lookback_days = lookback_days or config.effective_dom_lookback_days

    # Placeholder: Count days from earliest listing event to current date
    # within lookback window, excluding confirmed ownership transfers

    earliest_listing_date = None
    ownership_transfer_found = False

    for event in listing_events:
        # Check for ownership transfer events that reset DOM
        if event.event_type in ["sold", "county_sale_found", "ownership_transfer_found"]:
            ownership_transfer_found = True
            # In full implementation, we'd reset DOM after this date
            continue

        # Track earliest listing event
        if event.event_type in ["listed", "relisted", "back_on_market"]:
            if earliest_listing_date is None or event.event_date < earliest_listing_date:
                earliest_listing_date = event.event_date

    if earliest_listing_date is None:
        return 0

    # Calculate days since earliest listing
    days_on_market = (current_date - earliest_listing_date).days

    # Cap at lookback window
    effective_dom = min(days_on_market, lookback_days)

    return max(0, effective_dom)


def calculate_listing_churn_count(listing_events: List[ListingEvent]) -> int:
    """
    Count listing removal and relisting events.

    Args:
        listing_events: List of listing events for the property

    Returns:
        Count of listing churn events
    """
    churn_event_types = ["removed", "relisted", "back_on_market"]
    return sum(1 for event in listing_events if event.event_type in churn_event_types)


def calculate_dom_reset_count(listing_events: List[ListingEvent]) -> int:
    """
    Count DOM reset events (removals followed by relisting).

    Args:
        listing_events: List of listing events for the property

    Returns:
        Count of DOM reset events
    """
    # Placeholder: Count removal events that might trigger DOM reset
    return sum(1 for event in listing_events if event.event_type == "removed")


def calculate_sale_rent_alternation_count(listing_events: List[ListingEvent]) -> int:
    """
    Count sale/rent alternation events.

    Args:
        listing_events: List of listing events for the property

    Returns:
        Count of sale/rent alternation events
    """
    # Placeholder: Count rental-related events
    rental_event_types = ["rental_listed", "rental_removed"]
    return sum(1 for event in listing_events if event.event_type in rental_event_types)


def calculate_effective_dom_delta(
    displayed_dom: Optional[int], effective_dom: Optional[int]
) -> Optional[int]:
    """
    Calculate the delta between displayed DOM and effective DOM.

    A large positive delta suggests the property has been on the market
    longer than the displayed DOM indicates (due to listing churn).

    Args:
        displayed_dom: DOM displayed on listing site
        effective_dom: Calculated effective DOM

    Returns:
        Delta (effective_dom - displayed_dom) or None if data unavailable
    """
    if displayed_dom is None or effective_dom is None:
        return None

    return effective_dom - displayed_dom
