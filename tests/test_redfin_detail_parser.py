"""Tests for Redfin detail parser."""

from pathlib import Path

import pytest

from marketsentry.redfin_detail_parser import (
    parse_redfin_detail_directory,
    parse_redfin_detail_file,
)


class TestParseRedfinDetailFile:
    """Tests for parse_redfin_detail_file function."""

    def test_parse_normal_property_with_gas(self):
        """Test parsing normal property with gas evidence."""
        fixture_path = Path("tests/fixtures/redfin_detail/normal_property_with_gas.html")

        result = parse_redfin_detail_file(fixture_path)

        assert result.parse_status in ["success", "partial"]
        assert result.property_detail is not None

        detail = result.property_detail

        # Check address information
        assert detail.address == "46197 Via La Tranquila"
        assert detail.city == "Temecula"
        assert detail.zip == "92592"
        assert detail.state == "CA"

        # Check property facts
        assert detail.facts is not None
        assert detail.facts.price == 750000.0
        assert detail.facts.beds == 3
        assert detail.facts.baths == 2.5
        assert detail.facts.sqft == 2100
        assert detail.facts.lot_size == 7500.0
        assert detail.facts.year_built == 2005
        assert detail.facts.garage_spaces == 2

        # Check lifestyle scores
        assert detail.lifestyle_scores is not None
        assert detail.lifestyle_scores.quiet_score == 8.5
        assert detail.lifestyle_scores.vibrancy_score == 2.0

        # Check gas evidence
        assert detail.gas_service is True
        assert detail.gas_evidence is not None
        assert "gas" in detail.gas_evidence.lower()

        # Check MLS info
        assert detail.mls_number == "260008641"
        assert detail.source_mls == "SDMLS"

        # Check listing history
        assert len(detail.listing_history) == 4
        assert detail.listing_history[0].event_type == "listed"
        assert detail.listing_history[1].event_type == "removed"
        assert detail.listing_history[2].event_type == "price_changed"

        # Check displayed DOM
        assert detail.displayed_dom == 15

    def test_parse_high_noise_property(self):
        """Test parsing property with high noise (low quiet score)."""
        fixture_path = Path("tests/fixtures/redfin_detail/high_noise_property.html")

        result = parse_redfin_detail_file(fixture_path)

        assert result.parse_status in ["success", "partial"]
        detail = result.property_detail

        # Check quiet gatekeeper should fail
        assert detail.lifestyle_scores is not None
        assert detail.lifestyle_scores.quiet_score == 4.5
        assert detail.lifestyle_scores.quiet_score < 7.0  # Below gatekeeper threshold

        assert detail.lifestyle_scores.vibrancy_score == 7.5

        # Check no gas evidence
        assert detail.gas_service is None or detail.gas_service is False

    def test_parse_listing_churn_property(self):
        """Test parsing property with listing churn pattern."""
        fixture_path = Path("tests/fixtures/redfin_detail/listing_churn_property.html")

        result = parse_redfin_detail_file(fixture_path)

        assert result.parse_status in ["success", "partial"]
        detail = result.property_detail

        # Check extensive listing history
        assert len(detail.listing_history) >= 6

        # Check for rental events
        rental_events = [e for e in detail.listing_history if "rental" in e.event_type]
        assert len(rental_events) >= 2

        # Check for removal/relist patterns
        removed_events = [e for e in detail.listing_history if e.event_type == "removed"]
        assert len(removed_events) >= 2

        # Check gas evidence
        assert detail.gas_service is True

    def test_parse_sparse_data_property(self):
        """Test parsing property with minimal data."""
        fixture_path = Path("tests/fixtures/redfin_detail/sparse_data_property.html")

        result = parse_redfin_detail_file(fixture_path)

        # Should not fail even with sparse data
        assert result.parse_status in ["success", "partial"]
        detail = result.property_detail

        assert detail.address == "12345 Test Street"
        assert detail.city == "Temecula"

        # Missing fields should be None, not errors
        assert detail.facts.beds is None
        assert detail.facts.baths is None
        assert detail.lifestyle_scores is None or detail.lifestyle_scores.quiet_score is None

    def test_parse_nonexistent_file(self):
        """Test parsing nonexistent file."""
        result = parse_redfin_detail_file(Path("nonexistent.html"))

        assert result.parse_status == "failed"
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()


class TestParseRedfinDetailDirectory:
    """Tests for parse_redfin_detail_directory function."""

    def test_parse_fixture_directory(self):
        """Test parsing entire fixture directory."""
        fixture_dir = Path("tests/fixtures/redfin_detail")

        results = parse_redfin_detail_directory(fixture_dir)

        # Should have 4 fixture files
        assert len(results) == 4

        # All should parse without fatal errors
        success_count = sum(1 for r in results if r.parse_status in ["success", "partial"])
        assert success_count >= 3  # At least 3 should parse successfully

    def test_parse_empty_directory(self):
        """Test parsing directory with no HTML files."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            results = parse_redfin_detail_directory(Path(temp_dir))
            assert len(results) == 0

    def test_parse_nonexistent_directory(self):
        """Test parsing nonexistent directory."""
        results = parse_redfin_detail_directory(Path("nonexistent_dir"))
        assert len(results) == 0


class TestListingHistoryParsing:
    """Tests for listing history event parsing."""

    def test_listing_event_classification(self):
        """Test that listing events are classified correctly."""
        fixture_path = Path("tests/fixtures/redfin_detail/normal_property_with_gas.html")
        result = parse_redfin_detail_file(fixture_path)

        assert result.property_detail is not None
        events = result.property_detail.listing_history

        # Check event types are classified
        event_types = {e.event_type for e in events}
        assert "listed" in event_types
        assert "removed" in event_types
        assert "price_changed" in event_types

    def test_rental_event_classification(self):
        """Test that rental events are classified correctly."""
        fixture_path = Path("tests/fixtures/redfin_detail/listing_churn_property.html")
        result = parse_redfin_detail_file(fixture_path)

        events = result.property_detail.listing_history

        rental_listed = [e for e in events if e.event_type == "rental_listed"]
        rental_removed = [e for e in events if e.event_type == "rental_removed"]

        assert len(rental_listed) >= 1
        assert len(rental_removed) >= 1

    def test_event_dates_parsed(self):
        """Test that event dates are parsed correctly."""
        fixture_path = Path("tests/fixtures/redfin_detail/normal_property_with_gas.html")
        result = parse_redfin_detail_file(fixture_path)

        events = result.property_detail.listing_history

        # Check that dates are parsed
        events_with_dates = [e for e in events if e.event_date is not None]
        assert len(events_with_dates) >= 3

        # Check date format
        for event in events_with_dates:
            assert event.event_date.year >= 2025
            assert 1 <= event.event_date.month <= 12


class TestGasDetection:
    """Tests for gas evidence extraction."""

    def test_gas_detected_from_description(self):
        """Test gas service detected from property description."""
        fixture_path = Path("tests/fixtures/redfin_detail/normal_property_with_gas.html")
        result = parse_redfin_detail_file(fixture_path)

        detail = result.property_detail

        assert detail.gas_service is True
        assert detail.gas_evidence is not None
        assert any(
            keyword in detail.gas_evidence.lower()
            for keyword in ["gas range", "gas fireplace", "gas cooktop"]
        )

    def test_no_gas_when_not_mentioned(self):
        """Test gas service is None when not mentioned."""
        fixture_path = Path("tests/fixtures/redfin_detail/high_noise_property.html")
        result = parse_redfin_detail_file(fixture_path)

        detail = result.property_detail

        # Should be None or False when not mentioned
        assert detail.gas_service is None or detail.gas_service is False


class TestQuietVibrancyScores:
    """Tests for Quiet and Vibrancy score extraction."""

    def test_quiet_score_extraction(self):
        """Test Quiet score is extracted correctly."""
        fixture_path = Path("tests/fixtures/redfin_detail/normal_property_with_gas.html")
        result = parse_redfin_detail_file(fixture_path)

        scores = result.property_detail.lifestyle_scores

        assert scores is not None
        assert scores.quiet_score == 8.5
        assert scores.quiet_label == "excellent"

    def test_vibrancy_score_extraction(self):
        """Test Vibrancy score is extracted correctly."""
        fixture_path = Path("tests/fixtures/redfin_detail/normal_property_with_gas.html")
        result = parse_redfin_detail_file(fixture_path)

        scores = result.property_detail.lifestyle_scores

        assert scores is not None
        assert scores.vibrancy_score == 2.0

    def test_both_scores_together(self):
        """Test both Quiet and Vibrancy scores extracted together."""
        fixture_path = Path("tests/fixtures/redfin_detail/high_noise_property.html")
        result = parse_redfin_detail_file(fixture_path)

        scores = result.property_detail.lifestyle_scores

        assert scores is not None
        assert scores.quiet_score == 4.5
        assert scores.vibrancy_score == 7.5


class TestPropertyFactsExtraction:
    """Tests for property facts extraction."""

    def test_price_extraction(self):
        """Test price is extracted correctly."""
        fixture_path = Path("tests/fixtures/redfin_detail/normal_property_with_gas.html")
        result = parse_redfin_detail_file(fixture_path)

        facts = result.property_detail.facts

        assert facts is not None
        assert facts.price == 750000.0

    def test_beds_baths_extraction(self):
        """Test beds and baths extraction."""
        fixture_path = Path("tests/fixtures/redfin_detail/normal_property_with_gas.html")
        result = parse_redfin_detail_file(fixture_path)

        facts = result.property_detail.facts

        assert facts.beds == 3
        assert facts.baths == 2.5

    def test_sqft_extraction(self):
        """Test square footage extraction."""
        fixture_path = Path("tests/fixtures/redfin_detail/normal_property_with_gas.html")
        result = parse_redfin_detail_file(fixture_path)

        facts = result.property_detail.facts

        assert facts.sqft == 2100

    def test_garage_extraction(self):
        """Test garage spaces extraction."""
        fixture_path = Path("tests/fixtures/redfin_detail/normal_property_with_gas.html")
        result = parse_redfin_detail_file(fixture_path)

        facts = result.property_detail.facts

        assert facts.garage_spaces == 2
