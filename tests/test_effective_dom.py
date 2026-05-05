"""Tests for Effective DOM calculation functionality."""

from datetime import date, timedelta

import pytest

from marketsentry.effective_dom import (
    calculate_dom_reset_count,
    calculate_effective_dom,
    calculate_effective_dom_delta,
    calculate_listing_churn_count,
    calculate_sale_rent_alternation_count,
)
from marketsentry.models import ListingEvent


def test_calculate_effective_dom_empty_events() -> None:
    """Test effective DOM with no events."""
    events: list[ListingEvent] = []
    dom = calculate_effective_dom(events)

    assert dom == 0


def test_calculate_effective_dom_single_listing() -> None:
    """Test effective DOM with single listing event."""
    event_date = date.today() - timedelta(days=30)
    events = [
        ListingEvent(
            event_date=event_date,
            source_site="redfin",
            event_type="listed",
        )
    ]

    dom = calculate_effective_dom(events)

    assert dom >= 29  # At least 29 days (accounting for timing)
    assert dom <= 31  # At most 31 days


def test_calculate_effective_dom_with_relist() -> None:
    """Test effective DOM with listing and relisting."""
    events = [
        ListingEvent(
            event_date=date.today() - timedelta(days=60),
            source_site="redfin",
            event_type="listed",
        ),
        ListingEvent(
            event_date=date.today() - timedelta(days=45),
            source_site="redfin",
            event_type="removed",
        ),
        ListingEvent(
            event_date=date.today() - timedelta(days=30),
            source_site="redfin",
            event_type="relisted",
        ),
    ]

    dom = calculate_effective_dom(events)

    assert dom > 0


def test_calculate_effective_dom_lookback_cap() -> None:
    """Test effective DOM with very old event (v1: no lookback cap)."""
    events = [
        ListingEvent(
            event_date=date.today() - timedelta(days=500),
            source_site="redfin",
            event_type="listed",
        )
    ]

    dom = calculate_effective_dom(events)

    # v1 doesn't cap lookback, just returns the actual days
    assert dom >= 499


def test_calculate_listing_churn_count() -> None:
    """Test listing churn count calculation."""
    events = [
        ListingEvent(
            event_date=date.today() - timedelta(days=60),
            source_site="redfin",
            event_type="listed",
        ),
        ListingEvent(
            event_date=date.today() - timedelta(days=45),
            source_site="redfin",
            event_type="removed",
        ),
        ListingEvent(
            event_date=date.today() - timedelta(days=30),
            source_site="redfin",
            event_type="relisted",
        ),
    ]

    churn_count = calculate_listing_churn_count(events)

    assert churn_count == 3  # listed + removed + relisted


def test_calculate_dom_reset_count() -> None:
    """Test DOM reset count calculation (removals followed by relisting within 90 days)."""
    events = [
        ListingEvent(
            event_date=date.today() - timedelta(days=90),
            source_site="redfin",
            event_type="listed",
        ),
        ListingEvent(
            event_date=date.today() - timedelta(days=75),
            source_site="redfin",
            event_type="removed",
        ),
        ListingEvent(
            event_date=date.today() - timedelta(days=60),
            source_site="redfin",
            event_type="relisted",
        ),
        ListingEvent(
            event_date=date.today() - timedelta(days=45),
            source_site="redfin",
            event_type="removed",
        ),
        ListingEvent(
            event_date=date.today() - timedelta(days=30),
            source_site="redfin",
            event_type="relisted",
        ),
    ]

    reset_count = calculate_dom_reset_count(events)

    assert reset_count == 2  # Two removal->relist cycles within 90 days


def test_calculate_sale_rent_alternation_count() -> None:
    """Test sale/rent alternation count calculation."""
    events = [
        ListingEvent(
            event_date=date.today() - timedelta(days=60),
            source_site="redfin",
            event_type="listed",
        ),
        ListingEvent(
            event_date=date.today() - timedelta(days=45),
            source_site="redfin",
            event_type="rental_listed",
        ),
        ListingEvent(
            event_date=date.today() - timedelta(days=30),
            source_site="redfin",
            event_type="rental_removed",
        ),
    ]

    alternation_count = calculate_sale_rent_alternation_count(events)

    # v1: only counts transitions between sale and rental (1 transition: sale→rental)
    assert alternation_count == 1


def test_calculate_effective_dom_delta() -> None:
    """Test effective DOM delta calculation."""
    delta = calculate_effective_dom_delta(displayed_dom=30, effective_dom=90)

    assert delta == 60


def test_calculate_effective_dom_delta_negative() -> None:
    """Test effective DOM delta with negative result."""
    delta = calculate_effective_dom_delta(displayed_dom=60, effective_dom=30)

    assert delta == -30


def test_calculate_effective_dom_delta_none() -> None:
    """Test effective DOM delta with None input."""
    delta = calculate_effective_dom_delta(displayed_dom=None, effective_dom=90)

    assert delta is None
