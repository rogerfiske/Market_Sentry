"""Tests for Effective DOM v2 with county reset integration."""

from datetime import date, timedelta
from typing import List

import pytest

from marketsentry.churn_index import calculate_churn_index, calculate_churn_index_from_counts
from marketsentry.effective_dom_v2_calculator import calculate_effective_dom_v2
from marketsentry.models import CountyRecordObservation, ListingEvent


class TestChurnIndexCalculation:
    """Tests for Churn Index calculation."""

    def test_churn_index_from_counts_zero(self):
        """Test churn index with all zeros."""
        result = calculate_churn_index_from_counts(0, 0, 0, 0)
        assert result == 0.0

    def test_churn_index_from_counts_listing_churn(self):
        """Test churn index with listing churn only."""
        # 2 listing churns * 1.0 weight = 2.0 weighted
        # (2.0 / 20.0) * 10.0 = 1.0
        result = calculate_churn_index_from_counts(2, 0, 0, 0)
        assert result == 1.0

    def test_churn_index_from_counts_dom_reset(self):
        """Test churn index with DOM resets."""
        # 2 dom resets * 1.5 weight = 3.0 weighted
        # (3.0 / 20.0) * 10.0 = 1.5
        result = calculate_churn_index_from_counts(0, 2, 0, 0)
        assert result == 1.5

    def test_churn_index_from_counts_sale_rent_alternation(self):
        """Test churn index with sale/rent alternation."""
        # 2 sale/rent alternations * 2.0 weight = 4.0 weighted
        # (4.0 / 20.0) * 10.0 = 2.0
        result = calculate_churn_index_from_counts(0, 0, 2, 0)
        assert result == 2.0

    def test_churn_index_from_counts_price_changes(self):
        """Test churn index with price changes."""
        # 4 price changes * 0.5 weight = 2.0 weighted
        # (2.0 / 20.0) * 10.0 = 1.0
        result = calculate_churn_index_from_counts(0, 0, 0, 4)
        assert result == 1.0

    def test_churn_index_from_counts_mixed(self):
        """Test churn index with mixed events."""
        # (2 * 1.0) + (1 * 1.5) + (1 * 2.0) + (2 * 0.5) = 6.5 weighted
        # (6.5 / 20.0) * 10.0 = 3.25
        result = calculate_churn_index_from_counts(2, 1, 1, 2)
        assert result == 3.25

    def test_churn_index_from_counts_capped_at_10(self):
        """Test churn index caps at 10.0."""
        # Extreme values should cap at 10.0
        result = calculate_churn_index_from_counts(100, 100, 100, 100)
        assert result == 10.0

    def test_churn_index_date_filtered(self):
        """Test churn index with date filtering."""
        today = date.today()
        lookback_3_years = today - timedelta(days=365 * 3)

        events: List[ListingEvent] = [
            # Inside 3-year window
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=365),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=730),
                event_type="removed",
            ),
            # Outside 3-year window (should be excluded)
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=365 * 4),
                event_type="listed",
            ),
        ]

        result = calculate_churn_index(events, lookback_years=3, analysis_date=today)

        # Should only count the 2 events inside window
        assert result.recent_churn_event_count == 2
        assert result.recent_churn_lookback_years == 3
        assert result.churn_preserved_after_transfer is True


class TestEffectiveDomV2ScenarioA:
    """Scenario A: No county transfer."""

    def test_no_county_transfer_v2_equals_v1(self):
        """Test that v2 equals v1 when no county transfer exists."""
        today = date.today()

        events: List[ListingEvent] = [
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=60),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=30),
                event_type="price_change",
            ),
        ]

        county_records: List[CountyRecordObservation] = []

        result = calculate_effective_dom_v2(events, county_records, displayed_dom=30)

        # v2 should equal v1
        assert result.effective_dom_v2 == result.effective_dom_v1

        # No reset applied
        assert result.county_reset_applied is False
        assert result.county_reset_date is None

        # Churn index should still be computed
        assert result.recent_churn_index is not None
        assert result.churn_preserved_after_transfer is True


class TestEffectiveDomV2ScenarioB:
    """Scenario B: County transfer before all listing events."""

    def test_county_transfer_before_all_events(self):
        """Test that transfer before all events does not affect v2."""
        today = date.today()

        events: List[ListingEvent] = [
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=60),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=30),
                event_type="price_change",
            ),
        ]

        # Transfer before all listing events
        county_records: List[CountyRecordObservation] = [
            CountyRecordObservation(
                property_id=1,
                source_type="recorder",
                record_date=today - timedelta(days=120),
                record_type="Grant Deed",
                normalized_record_type="grant_deed",
                sale_price=700000.0,
            )
        ]

        result = calculate_effective_dom_v2(events, county_records, displayed_dom=30)

        # v2 should equal v1 (no reset applied because transfer is before all events)
        assert result.effective_dom_v2 == result.effective_dom_v1

        # Reset should not be applied
        assert result.county_reset_applied is False

        # Churn index should still be computed
        assert result.recent_churn_index is not None
        assert result.churn_preserved_after_transfer is True


class TestEffectiveDomV2ScenarioC:
    """Scenario C: County transfer inside listing-history window."""

    def test_county_transfer_inside_window(self):
        """Test that transfer inside window resets v2."""
        today = date.today()

        events: List[ListingEvent] = [
            # Pre-reset events
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=120),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=100),
                event_type="price_change",
            ),
            # Transfer happens at day 80
            # Post-reset events
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=60),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=30),
                event_type="price_change",
            ),
        ]

        # Transfer inside listing window
        county_records: List[CountyRecordObservation] = [
            CountyRecordObservation(
                property_id=1,
                source_type="recorder",
                record_date=today - timedelta(days=80),
                record_type="Grant Deed",
                normalized_record_type="grant_deed",
                document_number="2024-0012345",
                sale_price=700000.0,
            )
        ]

        result = calculate_effective_dom_v2(events, county_records, displayed_dom=30)

        # v2 should be less than v1 (excludes pre-reset exposure)
        assert result.effective_dom_v2 < result.effective_dom_v1

        # Reset should be applied
        assert result.county_reset_applied is True
        assert result.county_reset_date == today - timedelta(days=80)
        assert result.county_reset_record_type == "grant_deed"
        assert result.county_reset_record_id == "2024-0012345"

        # Pre-reset metrics should be reportable
        assert result.pre_reset_calendar_exposure_dom is not None
        assert result.pre_reset_calendar_exposure_dom > 0

        # Post-reset metrics should be used for v2
        assert result.post_reset_calendar_exposure_dom is not None

        # Churn index should be computed from ALL events (not just post-reset)
        assert result.recent_churn_index is not None
        assert result.recent_churn_event_count >= 4  # All 4 events counted
        assert result.churn_preserved_after_transfer is True

    def test_quitclaim_deed_resets_dom(self):
        """Test that quitclaim deed is treated as ownership transfer."""
        today = date.today()

        events: List[ListingEvent] = [
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=120),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=60),
                event_type="listed",
            ),
        ]

        county_records: List[CountyRecordObservation] = [
            CountyRecordObservation(
                property_id=1,
                source_type="recorder",
                record_date=today - timedelta(days=90),
                record_type="Quitclaim Deed",
                normalized_record_type="quitclaim_deed",
            )
        ]

        result = calculate_effective_dom_v2(events, county_records, displayed_dom=30)

        # Reset should be applied for quitclaim deed
        assert result.county_reset_applied is True
        assert result.county_reset_record_type == "quitclaim_deed"


class TestEffectiveDomV2ScenarioD:
    """Scenario D: County transfer after latest listing event."""

    def test_county_transfer_after_latest_event(self):
        """Test that transfer after latest event does not reset v2."""
        today = date.today()

        events: List[ListingEvent] = [
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=120),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=60),
                event_type="removed",
            ),
        ]

        # Transfer AFTER all listing events
        county_records: List[CountyRecordObservation] = [
            CountyRecordObservation(
                property_id=1,
                source_type="recorder",
                record_date=today - timedelta(days=30),
                record_type="Grant Deed",
                normalized_record_type="grant_deed",
            )
        ]

        result = calculate_effective_dom_v2(events, county_records, displayed_dom=30)

        # v2 should equal v1 (no historical reset)
        assert result.effective_dom_v2 == result.effective_dom_v1

        # Reset should not be applied
        assert result.county_reset_applied is False

        # Churn index should still be computed
        assert result.recent_churn_index is not None
        assert result.churn_preserved_after_transfer is True


class TestEffectiveDomV2ScenarioE:
    """Scenario E: Non-transfer county records do not reset."""

    def test_deed_of_trust_does_not_reset(self):
        """Test that deed of trust does not reset Effective DOM."""
        today = date.today()

        events: List[ListingEvent] = [
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=120),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=60),
                event_type="listed",
            ),
        ]

        # Deed of Trust is NOT an ownership transfer
        county_records: List[CountyRecordObservation] = [
            CountyRecordObservation(
                property_id=1,
                source_type="recorder",
                record_date=today - timedelta(days=90),
                record_type="Deed of Trust",
                normalized_record_type="deed_of_trust",
            )
        ]

        result = calculate_effective_dom_v2(events, county_records, displayed_dom=30)

        # v2 should equal v1 (deed of trust does not reset)
        assert result.effective_dom_v2 == result.effective_dom_v1

        # Reset should not be applied
        assert result.county_reset_applied is False

        # Churn index should still be computed
        assert result.recent_churn_index is not None
        assert result.churn_preserved_after_transfer is True

    def test_reconveyance_does_not_reset(self):
        """Test that reconveyance does not reset Effective DOM."""
        today = date.today()

        events: List[ListingEvent] = [
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=120),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=60),
                event_type="listed",
            ),
        ]

        county_records: List[CountyRecordObservation] = [
            CountyRecordObservation(
                property_id=1,
                source_type="recorder",
                record_date=today - timedelta(days=90),
                record_type="Reconveyance",
                normalized_record_type="reconveyance",
            )
        ]

        result = calculate_effective_dom_v2(events, county_records, displayed_dom=30)

        assert result.effective_dom_v2 == result.effective_dom_v1
        assert result.county_reset_applied is False
        assert result.churn_preserved_after_transfer is True

    def test_lien_does_not_reset(self):
        """Test that lien does not reset Effective DOM."""
        today = date.today()

        events: List[ListingEvent] = [
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=120),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=60),
                event_type="listed",
            ),
        ]

        county_records: List[CountyRecordObservation] = [
            CountyRecordObservation(
                property_id=1,
                source_type="recorder",
                record_date=today - timedelta(days=90),
                record_type="Lien",
                normalized_record_type="lien",
            )
        ]

        result = calculate_effective_dom_v2(events, county_records, displayed_dom=30)

        assert result.effective_dom_v2 == result.effective_dom_v1
        assert result.county_reset_applied is False
        assert result.churn_preserved_after_transfer is True

    def test_permit_does_not_reset(self):
        """Test that permit does not reset Effective DOM."""
        today = date.today()

        events: List[ListingEvent] = [
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=120),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=60),
                event_type="listed",
            ),
        ]

        county_records: List[CountyRecordObservation] = [
            CountyRecordObservation(
                property_id=1,
                source_type="permit",
                record_date=today - timedelta(days=90),
                record_type="Building Permit",
                normalized_record_type="permit",
                permit_number="BP-2024-12345",
            )
        ]

        result = calculate_effective_dom_v2(events, county_records, displayed_dom=30)

        assert result.effective_dom_v2 == result.effective_dom_v1
        assert result.county_reset_applied is False
        assert result.churn_preserved_after_transfer is True

    def test_assessment_does_not_reset(self):
        """Test that assessment does not reset Effective DOM."""
        today = date.today()

        events: List[ListingEvent] = [
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=120),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=60),
                event_type="listed",
            ),
        ]

        county_records: List[CountyRecordObservation] = [
            CountyRecordObservation(
                property_id=1,
                source_type="assessor",
                record_date=today - timedelta(days=90),
                record_type="assessment",
                normalized_record_type="assessment",
                assessed_value=725000.0,
            )
        ]

        result = calculate_effective_dom_v2(events, county_records, displayed_dom=30)

        assert result.effective_dom_v2 == result.effective_dom_v1
        assert result.county_reset_applied is False
        assert result.churn_preserved_after_transfer is True

    def test_tax_record_does_not_reset(self):
        """Test that tax record does not reset Effective DOM."""
        today = date.today()

        events: List[ListingEvent] = [
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=120),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=60),
                event_type="listed",
            ),
        ]

        county_records: List[CountyRecordObservation] = [
            CountyRecordObservation(
                property_id=1,
                source_type="tax_collector",
                record_date=today - timedelta(days=90),
                record_type="tax_record",
                normalized_record_type="tax_record",
            )
        ]

        result = calculate_effective_dom_v2(events, county_records, displayed_dom=30)

        assert result.effective_dom_v2 == result.effective_dom_v1
        assert result.county_reset_applied is False
        assert result.churn_preserved_after_transfer is True


class TestChurnPreservation:
    """Tests to ensure churn metrics are preserved after county reset."""

    def test_churn_preserved_with_reset(self):
        """Test that churn is preserved even when county reset is applied."""
        today = date.today()

        events: List[ListingEvent] = [
            # Pre-reset churn
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=365 * 2),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=365 * 2 - 30),
                event_type="removed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=365 * 2 - 60),
                event_type="listed",
            ),
            # Transfer happens
            # Post-reset events
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=60),
                event_type="listed",
            ),
        ]

        # Transfer inside window
        county_records: List[CountyRecordObservation] = [
            CountyRecordObservation(
                property_id=1,
                source_type="recorder",
                record_date=today - timedelta(days=365),
                record_type="Grant Deed",
                normalized_record_type="grant_deed",
            )
        ]

        result = calculate_effective_dom_v2(events, county_records, displayed_dom=30)

        # Reset should be applied
        assert result.county_reset_applied is True

        # Churn index should include ALL events (pre and post reset)
        assert result.recent_churn_index is not None
        assert result.recent_churn_index > 0.0  # Should have churn from multiple events

        # Churn should be explicitly preserved
        assert result.churn_preserved_after_transfer is True

        # Churn event count should include pre-reset events
        assert result.recent_churn_event_count >= 3

    def test_churn_nonzero_with_high_pre_reset_activity(self):
        """Test that high pre-reset churn remains visible after transfer."""
        today = date.today()

        events: List[ListingEvent] = [
            # High pre-reset churn
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=365 * 2),
                event_type="listed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=365 * 2 - 10),
                event_type="price_change",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=365 * 2 - 20),
                event_type="price_change",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=365 * 2 - 30),
                event_type="removed",
            ),
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=365 * 2 - 60),
                event_type="listed",
            ),
            # Transfer happens
            # Clean post-reset (just one listing)
            ListingEvent(
                property_id=1,
                event_date=today - timedelta(days=30),
                event_type="listed",
            ),
        ]

        county_records: List[CountyRecordObservation] = [
            CountyRecordObservation(
                property_id=1,
                source_type="recorder",
                record_date=today - timedelta(days=365),
                record_type="Grant Deed",
                normalized_record_type="grant_deed",
            )
        ]

        result = calculate_effective_dom_v2(events, county_records, displayed_dom=30)

        # Reset should be applied
        assert result.county_reset_applied is True

        # Effective DOM v2 should be low (only post-reset exposure)
        assert result.effective_dom_v2 < result.effective_dom_v1

        # But churn index should be HIGH (from all the pre-reset activity)
        assert result.recent_churn_index > 0.0
        assert result.recent_churn_event_count >= 5  # All events counted

        # This demonstrates: Low Effective DOM + High Churn scenario
        assert result.churn_preserved_after_transfer is True
