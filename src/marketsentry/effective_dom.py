"""Effective DOM calculation utilities - Version 1."""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from marketsentry.config import config
from marketsentry.models import ListingEvent


# Event normalization mapping
EVENT_NORMALIZATION_MAP = {
    "listed": "sale_listed",
    "relisted": "sale_relisted",
    "removed": "sale_removed",
    "pending": "sale_pending",
    "back_on_market": "sale_back_on_market",
    "sold": "sale_sold",
    "price_changed": "sale_price_changed",
    "rental_listed": "rental_listed",
    "rental_removed": "rental_removed",
    "unknown": "unknown",
}


def normalize_event_type(event_type: str) -> str:
    """
    Normalize event types to standard categories.

    Args:
        event_type: Raw event type

    Returns:
        Normalized event category
    """
    return EVENT_NORMALIZATION_MAP.get(event_type, "unknown")


def is_sale_listing_event(normalized_event: str) -> bool:
    """Check if event is a sale listing event."""
    return normalized_event in [
        "sale_listed",
        "sale_relisted",
        "sale_back_on_market",
        "sale_pending",
    ]


def is_rental_listing_event(normalized_event: str) -> bool:
    """Check if event is a rental listing event."""
    return normalized_event == "rental_listed"


def is_removal_event(normalized_event: str) -> bool:
    """Check if event is a removal event."""
    return normalized_event in ["sale_removed", "rental_removed"]


def is_sold_event(normalized_event: str) -> bool:
    """Check if event is a sold/ownership transfer event."""
    return normalized_event == "sale_sold"


class EffectiveDOMMetrics:
    """Container for all Effective DOM v1 metrics."""

    def __init__(self):
        """Initialize all metrics to None."""
        self.displayed_dom: Optional[int] = None
        self.current_listing_instance_dom: Optional[int] = None
        self.sale_cycle_dom: Optional[int] = None
        self.rent_sale_exposure_dom: Optional[int] = None
        self.calendar_exposure_dom: Optional[int] = None
        self.effective_dom: Optional[int] = None
        self.effective_dom_delta: Optional[int] = None
        self.listing_churn_count: int = 0
        self.dom_reset_count: int = 0
        self.sale_rent_alternation_count: int = 0
        self.price_change_count: int = 0
        self.first_observed_event_date: Optional[date] = None
        self.latest_observed_event_date: Optional[date] = None
        self.first_observed_price: Optional[float] = None
        self.current_or_latest_price: Optional[float] = None
        self.lowest_observed_price: Optional[float] = None
        self.highest_observed_price: Optional[float] = None


def calculate_all_effective_dom_metrics(
    listing_events: List[ListingEvent],
    displayed_dom: Optional[int] = None,
    current_date: Optional[date] = None,
) -> EffectiveDOMMetrics:
    """
    Calculate all Effective DOM v1 metrics for a property.

    Args:
        listing_events: List of listing events for the property
        displayed_dom: DOM displayed on source page (if available)
        current_date: Reference date for calculation (defaults to today)

    Returns:
        EffectiveDOMMetrics object with all calculated metrics
    """
    metrics = EffectiveDOMMetrics()
    current_date = current_date or date.today()

    if not listing_events:
        metrics.displayed_dom = displayed_dom
        return metrics

    # Sort events by date
    sorted_events = sorted(
        [e for e in listing_events if e.event_date],
        key=lambda e: e.event_date
    )

    if not sorted_events:
        metrics.displayed_dom = displayed_dom
        return metrics

    # Set displayed DOM
    metrics.displayed_dom = displayed_dom

    # Calculate date and price metrics
    metrics.first_observed_event_date = sorted_events[0].event_date
    metrics.latest_observed_event_date = sorted_events[-1].event_date

    prices = [e.price for e in sorted_events if e.price is not None]
    if prices:
        metrics.first_observed_price = prices[0]
        metrics.current_or_latest_price = prices[-1]
        metrics.lowest_observed_price = min(prices)
        metrics.highest_observed_price = max(prices)

    # Calculate churn metrics
    metrics.listing_churn_count = calculate_listing_churn_count(listing_events)
    metrics.dom_reset_count = calculate_dom_reset_count(listing_events)
    metrics.sale_rent_alternation_count = calculate_sale_rent_alternation_count(listing_events)
    metrics.price_change_count = calculate_price_change_count(listing_events)

    # Find current cycle (events after last sold event)
    current_cycle_events = _get_current_cycle_events(sorted_events)

    # Calculate DOM variants
    metrics.current_listing_instance_dom = _calculate_current_listing_instance_dom(
        current_cycle_events, current_date
    )
    metrics.sale_cycle_dom = _calculate_sale_cycle_dom(current_cycle_events, current_date)
    metrics.rent_sale_exposure_dom = _calculate_rent_sale_exposure_dom(
        current_cycle_events, current_date
    )
    metrics.calendar_exposure_dom = _calculate_calendar_exposure_dom(
        current_cycle_events, current_date
    )

    # Calculate effective DOM using fallback hierarchy
    metrics.effective_dom = _calculate_effective_dom(metrics)

    # Calculate effective DOM delta
    if metrics.effective_dom is not None and displayed_dom is not None:
        metrics.effective_dom_delta = metrics.effective_dom - displayed_dom

    return metrics


def _get_current_cycle_events(sorted_events: List[ListingEvent]) -> List[ListingEvent]:
    """
    Get events in the current no-sale cycle.

    Args:
        sorted_events: List of events sorted by date

    Returns:
        List of events after the last sold event, or all events if no sold event
    """
    # Find the last sold event
    last_sold_index = None
    for i in range(len(sorted_events) - 1, -1, -1):
        if is_sold_event(normalize_event_type(sorted_events[i].event_type)):
            last_sold_index = i
            break

    # Return events after last sold, or all events if no sold event
    if last_sold_index is not None:
        return sorted_events[last_sold_index + 1:]
    return sorted_events


def _calculate_current_listing_instance_dom(
    events: List[ListingEvent], current_date: date
) -> Optional[int]:
    """
    Calculate days from latest listing/relisting to current date.

    Args:
        events: Current cycle events
        current_date: Reference date

    Returns:
        Current listing instance DOM or None
    """
    if not events:
        return None

    # Find latest listing/relisting event
    latest_listing_date = None
    for event in reversed(events):
        normalized = normalize_event_type(event.event_type)
        if is_sale_listing_event(normalized) or is_rental_listing_event(normalized):
            latest_listing_date = event.event_date
            break

    if latest_listing_date is None:
        return None

    # Check if there's a removal after this listing
    for event in reversed(events):
        if event.event_date > latest_listing_date:
            if is_removal_event(normalize_event_type(event.event_type)):
                # Listing is no longer active
                return None

    return (current_date - latest_listing_date).days


def _calculate_sale_cycle_dom(
    events: List[ListingEvent], current_date: date
) -> Optional[int]:
    """
    Calculate total active sale-listing exposure days.

    Args:
        events: Current cycle events
        current_date: Reference date

    Returns:
        Sale cycle DOM or None
    """
    if not events:
        return None

    total_days = 0
    active_listing_start = None

    for event in events:
        normalized = normalize_event_type(event.event_type)

        # Start tracking when sale listing begins
        if is_sale_listing_event(normalized) and active_listing_start is None:
            active_listing_start = event.event_date

        # Stop tracking when sale is removed
        elif is_removal_event(normalized) and active_listing_start is not None:
            if event.event_date and active_listing_start:
                total_days += (event.event_date - active_listing_start).days
            active_listing_start = None

    # Add remaining active period if still listed
    if active_listing_start is not None:
        total_days += (current_date - active_listing_start).days

    return total_days if total_days > 0 else None


def _calculate_rent_sale_exposure_dom(
    events: List[ListingEvent], current_date: date
) -> Optional[int]:
    """
    Calculate total exposure days across sale and rental listings.

    Args:
        events: Current cycle events
        current_date: Reference date

    Returns:
        Rent/sale exposure DOM or None
    """
    if not events:
        return None

    # Check if there's any rental activity
    has_rental = any(
        is_rental_listing_event(normalize_event_type(e.event_type)) for e in events
    )

    if not has_rental:
        return None  # No sale/rent alternation

    total_days = 0
    active_listing_start = None

    for event in events:
        normalized = normalize_event_type(event.event_type)

        # Start tracking for any listing (sale or rental)
        if (is_sale_listing_event(normalized) or is_rental_listing_event(normalized)) and active_listing_start is None:
            active_listing_start = event.event_date

        # Stop tracking on removal
        elif is_removal_event(normalized) and active_listing_start is not None:
            if event.event_date and active_listing_start:
                total_days += (event.event_date - active_listing_start).days
            active_listing_start = None

    # Add remaining active period
    if active_listing_start is not None:
        total_days += (current_date - active_listing_start).days

    return total_days if total_days > 0 else None


def _calculate_calendar_exposure_dom(
    events: List[ListingEvent], current_date: date
) -> Optional[int]:
    """
    Calculate calendar days from earliest event to current date.

    Args:
        events: Current cycle events
        current_date: Reference date

    Returns:
        Calendar exposure DOM or None
    """
    if not events:
        return None

    # Find earliest non-sold listing event
    earliest_date = None
    for event in events:
        normalized = normalize_event_type(event.event_type)
        if is_sale_listing_event(normalized) or is_rental_listing_event(normalized):
            if earliest_date is None or event.event_date < earliest_date:
                earliest_date = event.event_date

    if earliest_date is None:
        return None

    return (current_date - earliest_date).days


def _calculate_effective_dom(metrics: EffectiveDOMMetrics) -> Optional[int]:
    """
    Calculate effective DOM using fallback hierarchy.

    Preference order:
    1. rent_sale_exposure_dom (if sale/rent alternation present)
    2. sale_cycle_dom
    3. calendar_exposure_dom
    4. current_listing_instance_dom
    5. displayed_dom

    Args:
        metrics: EffectiveDOMMetrics object with calculated values

    Returns:
        Effective DOM or None
    """
    # 1. Prefer rent/sale exposure if alternation present
    if metrics.sale_rent_alternation_count > 0 and metrics.rent_sale_exposure_dom is not None:
        return metrics.rent_sale_exposure_dom

    # 2. Prefer sale cycle DOM
    if metrics.sale_cycle_dom is not None:
        return metrics.sale_cycle_dom

    # 3. Prefer calendar exposure DOM
    if metrics.calendar_exposure_dom is not None:
        return metrics.calendar_exposure_dom

    # 4. Fallback to current listing instance
    if metrics.current_listing_instance_dom is not None:
        return metrics.current_listing_instance_dom

    # 5. Final fallback to displayed DOM
    return metrics.displayed_dom


def calculate_listing_churn_count(listing_events: List[ListingEvent]) -> int:
    """
    Count listing churn events (removals, relists, price changes, listings).

    Args:
        listing_events: List of listing events for the property

    Returns:
        Count of listing churn events
    """
    churn_event_types = ["removed", "relisted", "back_on_market", "price_changed", "listed"]
    return sum(
        1 for event in listing_events
        if event.event_type in churn_event_types
    )


def calculate_dom_reset_count(listing_events: List[ListingEvent]) -> int:
    """
    Count DOM reset events (removals followed by relisting within 90 days).

    Args:
        listing_events: List of listing events for the property

    Returns:
        Count of DOM reset events
    """
    if not listing_events:
        return 0

    sorted_events = sorted(
        [e for e in listing_events if e.event_date],
        key=lambda e: e.event_date
    )

    reset_count = 0
    for i, event in enumerate(sorted_events):
        if event.event_type == "removed":
            # Look for relisting within 90 days without intervening sold
            for j in range(i + 1, len(sorted_events)):
                next_event = sorted_events[j]

                # Stop if sold event found
                if is_sold_event(normalize_event_type(next_event.event_type)):
                    break

                # Count if relisting within 90 days
                if next_event.event_type in ["relisted", "listed", "back_on_market"]:
                    days_diff = (next_event.event_date - event.event_date).days
                    if days_diff <= 90:
                        reset_count += 1
                    break

    return reset_count


def calculate_sale_rent_alternation_count(listing_events: List[ListingEvent]) -> int:
    """
    Count transitions between sale and rental listing periods.

    Args:
        listing_events: List of listing events for the property

    Returns:
        Count of sale/rent alternations
    """
    if not listing_events:
        return 0

    sorted_events = sorted(
        [e for e in listing_events if e.event_date],
        key=lambda e: e.event_date
    )

    alternation_count = 0
    last_listing_type = None  # 'sale' or 'rental'

    for event in sorted_events:
        normalized = normalize_event_type(event.event_type)

        current_type = None
        if is_sale_listing_event(normalized):
            current_type = "sale"
        elif is_rental_listing_event(normalized):
            current_type = "rental"

        # Count transition if listing type changes
        if current_type and last_listing_type and current_type != last_listing_type:
            alternation_count += 1

        if current_type:
            last_listing_type = current_type

    return alternation_count


def calculate_price_change_count(listing_events: List[ListingEvent]) -> int:
    """
    Count price change events.

    Args:
        listing_events: List of listing events for the property

    Returns:
        Count of price change events
    """
    return sum(
        1 for event in listing_events
        if event.event_type == "price_changed"
    )


# Legacy function for backwards compatibility
def calculate_effective_dom(
    listing_events: List[ListingEvent],
    current_date: Optional[date] = None,
    lookback_days: Optional[int] = None,
) -> int:
    """
    Calculate Effective DOM for a property (legacy function).

    This function is maintained for backwards compatibility.
    Use calculate_all_effective_dom_metrics() for full v1 metrics.

    Args:
        listing_events: List of listing events for the property
        current_date: Reference date for calculation (defaults to today)
        lookback_days: Lookback window in days (defaults to config value)

    Returns:
        Effective DOM in days
    """
    metrics = calculate_all_effective_dom_metrics(listing_events, None, current_date)
    return metrics.effective_dom or 0


def calculate_effective_dom_delta(
    displayed_dom: Optional[int], effective_dom: Optional[int]
) -> Optional[int]:
    """
    Calculate the delta between displayed DOM and effective DOM.

    Args:
        displayed_dom: DOM displayed on listing site
        effective_dom: Calculated effective DOM

    Returns:
        Delta (effective_dom - displayed_dom) or None if data unavailable
    """
    if displayed_dom is None or effective_dom is None:
        return None

    return effective_dom - displayed_dom
