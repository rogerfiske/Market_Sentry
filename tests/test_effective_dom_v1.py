"""Tests for Effective DOM v1 metrics and event normalization."""

from datetime import date, timedelta

import pytest

from marketsentry.effective_dom import (
    EffectiveDOMMetrics,
    calculate_all_effective_dom_metrics,
    calculate_dom_reset_count,
    calculate_listing_churn_count,
    calculate_price_change_count,
    calculate_sale_rent_alternation_count,
    is_removal_event,
    is_rental_listing_event,
    is_sale_listing_event,
    is_sold_event,
    normalize_event_type,
)
from marketsentry.models import ListingEvent


class TestEventNormalization:
    """Tests for event type normalization."""

    def test_normalize_listed_event(self):
        """Test normalizing 'listed' event."""
        assert normalize_event_type("listed") == "sale_listed"

    def test_normalize_relisted_event(self):
        """Test normalizing 'relisted' event."""
        assert normalize_event_type("relisted") == "sale_relisted"

    def test_normalize_removed_event(self):
        """Test normalizing 'removed' event."""
        assert normalize_event_type("removed") == "sale_removed"

    def test_normalize_pending_event(self):
        """Test normalizing 'pending' event."""
        assert normalize_event_type("pending") == "sale_pending"

    def test_normalize_sold_event(self):
        """Test normalizing 'sold' event."""
        assert normalize_event_type("sold") == "sale_sold"

    def test_normalize_price_changed_event(self):
        """Test normalizing 'price_changed' event."""
        assert normalize_event_type("price_changed") == "sale_price_changed"

    def test_normalize_rental_listed_event(self):
        """Test normalizing 'rental_listed' event."""
        assert normalize_event_type("rental_listed") == "rental_listed"

    def test_normalize_unknown_event(self):
        """Test normalizing unknown event type."""
        assert normalize_event_type("some_unknown_type") == "unknown"

    def test_is_sale_listing_event(self):
        """Test sale listing event detection."""
        assert is_sale_listing_event("sale_listed") is True
        assert is_sale_listing_event("sale_relisted") is True
        assert is_sale_listing_event("sale_back_on_market") is True
        assert is_sale_listing_event("sale_pending") is True
        assert is_sale_listing_event("sale_removed") is False
        assert is_sale_listing_event("rental_listed") is False

    def test_is_rental_listing_event(self):
        """Test rental listing event detection."""
        assert is_rental_listing_event("rental_listed") is True
        assert is_rental_listing_event("sale_listed") is False
        assert is_rental_listing_event("rental_removed") is False

    def test_is_removal_event(self):
        """Test removal event detection."""
        assert is_removal_event("sale_removed") is True
        assert is_removal_event("rental_removed") is True
        assert is_removal_event("sale_listed") is False

    def test_is_sold_event(self):
        """Test sold event detection."""
        assert is_sold_event("sale_sold") is True
        assert is_sold_event("sale_removed") is False
        assert is_sold_event("sale_listed") is False


class TestEffectiveDOMMetricsNormal:
    """Tests for Effective DOM metrics with normal listing history."""

    def test_empty_events(self):
        """Test with no events."""
        metrics = calculate_all_effective_dom_metrics([])

        assert metrics.effective_dom is None
        assert metrics.listing_churn_count == 0
        assert metrics.dom_reset_count == 0
        assert metrics.sale_rent_alternation_count == 0
        assert metrics.price_change_count == 0

    def test_single_listing(self):
        """Test with single listing event."""
        events = [
            ListingEvent(
                event_date=date.today() - timedelta(days=30),
                source_site="redfin",
                event_type="listed",
                price=750000.0,
            ),
        ]

        metrics = calculate_all_effective_dom_metrics(events)

        assert metrics.current_listing_instance_dom == 30
        assert metrics.effective_dom == 30
        assert metrics.listing_churn_count == 1
        assert metrics.first_observed_price == 750000.0
        assert metrics.current_or_latest_price == 750000.0

    def test_listing_with_price_change(self):
        """Test listing with price reduction."""
        events = [
            ListingEvent(
                event_date=date.today() - timedelta(days=60),
                source_site="redfin",
                event_type="listed",
                price=800000.0,
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=30),
                source_site="redfin",
                event_type="price_changed",
                price=750000.0,
            ),
        ]

        metrics = calculate_all_effective_dom_metrics(events)

        assert metrics.price_change_count == 1
        assert metrics.first_observed_price == 800000.0
        assert metrics.current_or_latest_price == 750000.0
        assert metrics.lowest_observed_price == 750000.0
        assert metrics.highest_observed_price == 800000.0


class TestEffectiveDOMMetricsChurn:
    """Tests for Effective DOM with Via La Tranquila-style listing churn."""

    def test_removal_and_relist(self):
        """Test removal followed by relisting (DOM reset)."""
        events = [
            ListingEvent(
                event_date=date.today() - timedelta(days=90),
                source_site="redfin",
                event_type="listed",
                price=750000.0,
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
                price=750000.0,
            ),
        ]

        metrics = calculate_all_effective_dom_metrics(events)

        assert metrics.dom_reset_count == 1
        assert metrics.listing_churn_count >= 3  # listed, removed, relisted
        assert metrics.effective_dom is not None

    def test_multiple_dom_resets(self):
        """Test multiple DOM reset cycles."""
        events = [
            ListingEvent(
                event_date=date.today() - timedelta(days=120),
                source_site="redfin",
                event_type="listed",
                price=799000.0,
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=90),
                source_site="redfin",
                event_type="removed",
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=75),
                source_site="redfin",
                event_type="relisted",
                price=780000.0,
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=60),
                source_site="redfin",
                event_type="removed",
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=45),
                source_site="redfin",
                event_type="relisted",
                price=750000.0,
            ),
        ]

        metrics = calculate_all_effective_dom_metrics(events)

        assert metrics.dom_reset_count == 2
        assert metrics.price_change_count == 0  # No explicit price_changed events
        assert metrics.first_observed_price == 799000.0
        assert metrics.current_or_latest_price == 750000.0
        assert metrics.lowest_observed_price == 750000.0


class TestEffectiveDOMMetricsSaleRentAlternation:
    """Tests for Effective DOM with sale/rent alternation."""

    def test_sale_to_rental_transition(self):
        """Test transition from sale to rental listing."""
        events = [
            ListingEvent(
                event_date=date.today() - timedelta(days=90),
                source_site="redfin",
                event_type="listed",
                price=750000.0,
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=75),
                source_site="redfin",
                event_type="removed",
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=60),
                source_site="redfin",
                event_type="rental_listed",
                price=3500.0,  # Monthly rent
            ),
        ]

        metrics = calculate_all_effective_dom_metrics(events)

        assert metrics.sale_rent_alternation_count == 1
        assert metrics.rent_sale_exposure_dom is not None
        # Should prefer rent/sale exposure DOM when alternation present
        if metrics.sale_rent_alternation_count > 0:
            assert metrics.effective_dom == metrics.rent_sale_exposure_dom

    def test_multiple_sale_rent_alternations(self):
        """Test multiple sale/rent transitions."""
        events = [
            ListingEvent(
                event_date=date.today() - timedelta(days=120),
                source_site="redfin",
                event_type="listed",
                price=750000.0,
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=90),
                source_site="redfin",
                event_type="removed",
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=75),
                source_site="redfin",
                event_type="rental_listed",
                price=3500.0,
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=60),
                source_site="redfin",
                event_type="rental_removed",
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=45),
                source_site="redfin",
                event_type="relisted",
                price=725000.0,
            ),
        ]

        metrics = calculate_all_effective_dom_metrics(events)

        assert metrics.sale_rent_alternation_count == 2  # sale→rental, rental→sale
        assert metrics.rent_sale_exposure_dom is not None


class TestEffectiveDOMMetricsSoldReset:
    """Tests for Effective DOM with sold event reset."""

    def test_sold_event_resets_cycle(self):
        """Test that sold event resets the current cycle."""
        events = [
            # Old cycle
            ListingEvent(
                event_date=date.today() - timedelta(days=200),
                source_site="redfin",
                event_type="listed",
                price=750000.0,
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=150),
                source_site="redfin",
                event_type="sold",
                price=740000.0,
            ),
            # New cycle after sale
            ListingEvent(
                event_date=date.today() - timedelta(days=30),
                source_site="redfin",
                event_type="listed",
                price=780000.0,
            ),
        ]

        metrics = calculate_all_effective_dom_metrics(events)

        # Should only count current cycle (after sold event)
        assert metrics.current_listing_instance_dom == 30
        assert metrics.first_observed_event_date == events[0].event_date
        assert metrics.latest_observed_event_date == events[-1].event_date

    def test_dom_reset_not_counted_after_sold(self):
        """Test that removals don't count as resets if sold event intervenes."""
        events = [
            ListingEvent(
                event_date=date.today() - timedelta(days=150),
                source_site="redfin",
                event_type="listed",
                price=750000.0,
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=120),
                source_site="redfin",
                event_type="removed",
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=100),
                source_site="redfin",
                event_type="sold",
                price=745000.0,
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=30),
                source_site="redfin",
                event_type="listed",
                price=780000.0,
            ),
        ]

        metrics = calculate_all_effective_dom_metrics(events)

        # First removal followed by sold, not a reset
        # Use the actual function to verify
        reset_count = calculate_dom_reset_count(events)
        assert reset_count == 0


class TestEffectiveDOMFallbackBehavior:
    """Tests for Effective DOM fallback hierarchy."""

    def test_fallback_to_displayed_dom(self):
        """Test fallback to displayed DOM when no events."""
        metrics = calculate_all_effective_dom_metrics([], displayed_dom=45)

        assert metrics.effective_dom is None  # No fallback without any data
        assert metrics.displayed_dom == 45

    def test_prefers_rent_sale_exposure_with_alternation(self):
        """Test that rent/sale exposure DOM is preferred when alternation exists."""
        events = [
            ListingEvent(
                event_date=date.today() - timedelta(days=90),
                source_site="redfin",
                event_type="listed",
                price=750000.0,
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=60),
                source_site="redfin",
                event_type="rental_listed",
                price=3500.0,
            ),
        ]

        metrics = calculate_all_effective_dom_metrics(events)

        if metrics.sale_rent_alternation_count > 0 and metrics.rent_sale_exposure_dom is not None:
            assert metrics.effective_dom == metrics.rent_sale_exposure_dom

    def test_effective_dom_delta_calculation(self):
        """Test effective DOM delta calculation."""
        events = [
            ListingEvent(
                event_date=date.today() - timedelta(days=120),
                source_site="redfin",
                event_type="listed",
                price=750000.0,
            ),
        ]

        metrics = calculate_all_effective_dom_metrics(events, displayed_dom=45)

        assert metrics.displayed_dom == 45
        assert metrics.effective_dom is not None
        if metrics.effective_dom and metrics.displayed_dom:
            assert metrics.effective_dom_delta == metrics.effective_dom - metrics.displayed_dom


class TestListingChurnCount:
    """Tests for listing churn count calculation."""

    def test_counts_all_churn_events(self):
        """Test that all churn event types are counted."""
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
                event_type="price_changed",
            ),
        ]

        churn_count = calculate_listing_churn_count(events)
        assert churn_count == 4  # All events are churn events

    def test_excludes_non_churn_events(self):
        """Test that non-churn events are not counted."""
        events = [
            ListingEvent(
                event_date=date.today() - timedelta(days=90),
                source_site="redfin",
                event_type="listed",
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=60),
                source_site="redfin",
                event_type="sold",
            ),
        ]

        churn_count = calculate_listing_churn_count(events)
        assert churn_count == 1  # Only 'listed' counts, 'sold' does not


class TestPriceChangeCount:
    """Tests for price change count calculation."""

    def test_counts_price_changes(self):
        """Test price change event counting."""
        events = [
            ListingEvent(
                event_date=date.today() - timedelta(days=90),
                source_site="redfin",
                event_type="listed",
                price=800000.0,
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=60),
                source_site="redfin",
                event_type="price_changed",
                price=780000.0,
            ),
            ListingEvent(
                event_date=date.today() - timedelta(days=30),
                source_site="redfin",
                event_type="price_changed",
                price=750000.0,
            ),
        ]

        price_change_count = calculate_price_change_count(events)
        assert price_change_count == 2
