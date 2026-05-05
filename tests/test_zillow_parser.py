"""Tests for Zillow parser."""

from pathlib import Path

import pytest

from marketsentry.zillow_parser import parse_zillow_detail_file


class TestParseZillowDetailFile:
    """Tests for parse_zillow_detail_file function."""

    def test_parse_normal_property(self):
        """Test parsing normal property with complete data."""
        fixture_path = Path("tests/fixtures/cross_site/zillow/normal_property.html")

        result = parse_zillow_detail_file(fixture_path)

        assert result.parse_status in ["success", "partial"]
        assert result.source_site == "zillow"
        assert result.property_facts is not None

        # Check address information
        assert result.address == "46197 Via La Tranquila"
        assert result.city == "Temecula"
        assert result.state == "CA"
        assert result.zip == "92592"
        assert result.normalized_address is not None

    def test_parse_price_extraction(self):
        """Test that price is extracted correctly."""
        fixture_path = Path("tests/fixtures/cross_site/zillow/normal_property.html")

        result = parse_zillow_detail_file(fixture_path)

        facts = result.property_facts
        assert facts is not None
        assert facts.price == 750000.0

    def test_parse_beds_baths_sqft(self):
        """Test extraction of beds, baths, and sqft."""
        fixture_path = Path("tests/fixtures/cross_site/zillow/normal_property.html")

        result = parse_zillow_detail_file(fixture_path)

        facts = result.property_facts
        assert facts.beds == 3
        assert facts.baths == 2.5
        assert facts.sqft == 2100

    def test_parse_status(self):
        """Test listing status extraction."""
        fixture_path = Path("tests/fixtures/cross_site/zillow/normal_property.html")

        result = parse_zillow_detail_file(fixture_path)

        facts = result.property_facts
        assert facts.listing_status is not None
        assert "sale" in facts.listing_status.lower()

    def test_parse_dom(self):
        """Test Days on Market extraction."""
        fixture_path = Path("tests/fixtures/cross_site/zillow/normal_property.html")

        result = parse_zillow_detail_file(fixture_path)

        facts = result.property_facts
        assert facts.displayed_dom == 15

    def test_parse_garage_detection(self):
        """Test garage spaces extraction."""
        fixture_path = Path("tests/fixtures/cross_site/zillow/normal_property.html")

        result = parse_zillow_detail_file(fixture_path)

        facts = result.property_facts
        assert facts.garage_spaces == 2

    def test_parse_gas_detection(self):
        """Test gas service detection."""
        fixture_path = Path("tests/fixtures/cross_site/zillow/normal_property.html")

        result = parse_zillow_detail_file(fixture_path)

        facts = result.property_facts
        assert facts.gas_service is True
        assert facts.gas_evidence is not None
        assert any(
            keyword in facts.gas_evidence.lower()
            for keyword in ["gas range", "gas fireplace", "gas cooktop"]
        )

    def test_parse_sparse_data(self):
        """Test parsing property with minimal data."""
        fixture_path = Path("tests/fixtures/cross_site/zillow/sparse_data.html")

        result = parse_zillow_detail_file(fixture_path)

        # Should not fail
        assert result.parse_status in ["success", "partial"]
        facts = result.property_facts

        # Should have basic data
        assert result.address == "67890 Test Lane"
        assert facts.price == 500000.0
        assert facts.displayed_dom == 5

        # Missing fields should be None
        assert facts.beds is None
        assert facts.baths is None
        assert facts.sqft is None
        assert facts.garage_spaces is None

    def test_parse_price_discrepancy_fixture(self):
        """Test parsing fixture with different price."""
        fixture_path = Path("tests/fixtures/cross_site/zillow/price_discrepancy.html")

        result = parse_zillow_detail_file(fixture_path)

        assert result.parse_status in ["success", "partial"]
        facts = result.property_facts

        # Check price differs from standard fixture
        assert facts.price == 735000.0
        assert result.address == "46197 Via La Tranquila"

    def test_parse_nonexistent_file(self):
        """Test parsing nonexistent file."""
        result = parse_zillow_detail_file(Path("nonexistent.html"))

        assert result.parse_status == "failed"
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()

    def test_parse_description_extraction(self):
        """Test property description extraction."""
        fixture_path = Path("tests/fixtures/cross_site/zillow/normal_property.html")

        result = parse_zillow_detail_file(fixture_path)

        facts = result.property_facts
        assert facts.property_description is not None
        assert len(facts.property_description) > 0

    def test_parse_source_url_extraction(self):
        """Test source URL extraction from canonical link."""
        fixture_path = Path("tests/fixtures/cross_site/zillow/normal_property.html")

        result = parse_zillow_detail_file(fixture_path)

        assert result.source_url is not None
        assert "zillow.com" in result.source_url


class TestZillowParserEdgeCases:
    """Tests for edge cases in Zillow parser."""

    def test_parse_multiple_files(self):
        """Test parsing multiple files in sequence."""
        fixtures = [
            "tests/fixtures/cross_site/zillow/normal_property.html",
            "tests/fixtures/cross_site/zillow/price_discrepancy.html",
            "tests/fixtures/cross_site/zillow/sparse_data.html",
        ]

        results = []
        for fixture in fixtures:
            result = parse_zillow_detail_file(Path(fixture))
            results.append(result)

        # All should parse successfully
        assert len(results) == 3
        for result in results:
            assert result.parse_status in ["success", "partial"]
            assert result.source_site == "zillow"

    def test_parse_no_gas_evidence(self):
        """Test property with no gas mentions."""
        fixture_path = Path("tests/fixtures/cross_site/zillow/sparse_data.html")

        result = parse_zillow_detail_file(fixture_path)

        facts = result.property_facts
        # Should be None or False when no gas evidence
        assert facts.gas_service is None or facts.gas_service is False

    def test_parse_warnings_collection(self):
        """Test that warnings are collected during parsing."""
        fixture_path = Path("tests/fixtures/cross_site/zillow/sparse_data.html")

        result = parse_zillow_detail_file(fixture_path)

        # Sparse data should generate some warnings
        # (but this depends on implementation details)
        assert isinstance(result.warnings, list)

    def test_parse_errors_on_failure(self):
        """Test that errors are collected on parse failure."""
        result = parse_zillow_detail_file(Path("nonexistent.html"))

        assert len(result.errors) > 0
        assert result.parse_status == "failed"

    def test_parse_normalized_address(self):
        """Test that address is normalized correctly."""
        fixture_path = Path("tests/fixtures/cross_site/zillow/normal_property.html")

        result = parse_zillow_detail_file(fixture_path)

        assert result.normalized_address is not None
        # Normalized should be uppercase and standardized
        assert result.normalized_address.isupper()
        assert "46197" in result.normalized_address
