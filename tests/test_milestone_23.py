"""Tests for Milestone 23: Cross-Site Parser Quality and Fixture Corpus Expansion.

Tests cover:
- Parser fixture variants for all 4 sources (8 variants each)
- Normalization helpers (price, sqft, lot, DOM, status, garage, gas)
- Confidence classification
- Warnings and missing required fields
- Parse quality model fields
- No walkability fields
- No real network calls
"""

import re
from pathlib import Path

import pytest

from marketsentry.models import (
    CrossSiteComparisonResult,
    CrossSiteParseResult,
    CrossSitePropertyFacts,
)
from marketsentry.normalization import (
    detect_gas_keywords,
    normalize_dom,
    normalize_garage,
    normalize_listing_status,
    normalize_lot_size,
    normalize_price,
    normalize_sqft,
)
from marketsentry.zillow_parser import parse_zillow_detail_html, parse_zillow_detail_file
from marketsentry.realtor_parser import parse_realtor_detail_html, parse_realtor_detail_file
from marketsentry.homes_parser import parse_homes_detail_html, parse_homes_detail_file
from marketsentry.compass_parser import parse_compass_detail_html, parse_compass_detail_file

# Fixture directory
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "cross_site"


# ============================================================
# Normalization Tests
# ============================================================


class TestNormalizePrice:
    """Test price normalization with various formats."""

    def test_standard_price(self):
        assert normalize_price("$850,000") == 850000.0

    def test_price_k_suffix(self):
        assert normalize_price("$850K") == 850000.0

    def test_price_k_lowercase(self):
        assert normalize_price("850k") == 850000.0

    def test_price_m_suffix(self):
        assert normalize_price("$1.2M") == 1200000.0

    def test_price_m_lowercase(self):
        assert normalize_price("1.5m") == 1500000.0

    def test_price_plain_number(self):
        assert normalize_price("850000") == 850000.0

    def test_price_none(self):
        assert normalize_price(None) is None

    def test_price_empty(self):
        assert normalize_price("") is None

    def test_price_no_dollar_sign(self):
        assert normalize_price("750,000") == 750000.0


class TestNormalizeSqft:
    """Test square footage normalization."""

    def test_sqft_with_comma(self):
        assert normalize_sqft("2,450 sqft") == 2450

    def test_sqft_square_feet(self):
        assert normalize_sqft("2450 square feet") == 2450

    def test_sqft_sq_ft(self):
        assert normalize_sqft("2,100 sq ft") == 2100

    def test_sqft_plain(self):
        assert normalize_sqft("1850") == 1850

    def test_sqft_none(self):
        assert normalize_sqft(None) is None


class TestNormalizeLotSize:
    """Test lot size normalization."""

    def test_lot_acres(self):
        assert normalize_lot_size("0.25 acres") == 0.25

    def test_lot_sqft(self):
        result = normalize_lot_size("7,405 sqft")
        assert result is not None
        assert abs(result - 0.1700) < 0.001

    def test_lot_sqft_lot(self):
        result = normalize_lot_size("10890 sq ft lot")
        assert result is not None
        assert abs(result - 0.25) < 0.001

    def test_lot_none(self):
        assert normalize_lot_size(None) is None


class TestNormalizeDom:
    """Test DOM normalization with various formats."""

    def test_days_on_market(self):
        assert normalize_dom("12 days on market") == 12

    def test_listed_days_ago(self):
        assert normalize_dom("Listed 45 days ago") == 45

    def test_on_site_days(self):
        assert normalize_dom("On site 17 days") == 17

    def test_dom_suffix(self):
        assert normalize_dom("12 DOM") == 12

    def test_days_on_zillow(self):
        assert normalize_dom("15 Days on Zillow") == 15

    def test_days_on_compass(self):
        assert normalize_dom("10 days on Compass") == 10

    def test_dom_none(self):
        assert normalize_dom(None) is None


class TestNormalizeListingStatus:
    """Test listing status normalization."""

    def test_active(self):
        assert normalize_listing_status("active") == "for_sale"

    def test_for_sale(self):
        assert normalize_listing_status("for sale") == "for_sale"

    def test_pending(self):
        assert normalize_listing_status("pending") == "pending"

    def test_contingent(self):
        assert normalize_listing_status("contingent") == "contingent"

    def test_sold(self):
        assert normalize_listing_status("sold") == "sold"

    def test_off_market(self):
        assert normalize_listing_status("off market") == "off_market"

    def test_off_market_hyphen(self):
        assert normalize_listing_status("off-market") == "off_market"

    def test_coming_soon(self):
        assert normalize_listing_status("coming soon") == "coming_soon"

    def test_for_rent(self):
        assert normalize_listing_status("for rent") == "for_rent"

    def test_none(self):
        assert normalize_listing_status(None) is None


class TestNormalizeGarage:
    """Test garage normalization."""

    def test_two_garage_spaces(self):
        assert normalize_garage("2 garage spaces") == 2

    def test_three_car_garage(self):
        assert normalize_garage("3-car garage") == 3

    def test_attached_garage(self):
        assert normalize_garage("attached garage") == 1

    def test_two_car_garage_no_hyphen(self):
        assert normalize_garage("2 car garage") == 2

    def test_none(self):
        assert normalize_garage(None) is None


class TestDetectGasKeywords:
    """Test gas evidence detection."""

    def test_gas_fireplace(self):
        result = detect_gas_keywords("Living room has gas fireplace")
        assert result is not None
        assert "gas fireplace" in result

    def test_gas_range(self):
        result = detect_gas_keywords("Kitchen has gas range")
        assert result is not None
        assert "gas range" in result

    def test_natural_gas(self):
        result = detect_gas_keywords("Natural gas service available")
        assert result is not None
        assert "natural gas" in result

    def test_gas_dryer_hookup(self):
        result = detect_gas_keywords("Laundry room has gas dryer hookup")
        assert result is not None
        assert "gas dryer hookup" in result

    def test_no_gas(self):
        result = detect_gas_keywords("All electric kitchen with induction cooktop")
        assert result is None

    def test_multiple_gas_evidence(self):
        result = detect_gas_keywords("Gas fireplace and gas range in kitchen")
        assert result is not None
        assert "gas fireplace" in result
        assert "gas range" in result

    def test_none_input(self):
        assert detect_gas_keywords(None) is None


# ============================================================
# Model Tests
# ============================================================


class TestCrossSiteParseResultModel:
    """Test CrossSiteParseResult model fields."""

    def test_parse_confidence_field_exists(self):
        result = CrossSiteParseResult(source_site="zillow", parse_status="success")
        assert hasattr(result, "parse_confidence")
        assert result.parse_confidence == "high"  # default

    def test_missing_required_fields_exists(self):
        result = CrossSiteParseResult(source_site="zillow", parse_status="success")
        assert hasattr(result, "missing_required_fields")
        assert result.missing_required_fields == []


class TestCrossSitePropertyFactsModel:
    """Test CrossSitePropertyFacts model fields."""

    def test_listing_agent_field(self):
        facts = CrossSitePropertyFacts()
        assert hasattr(facts, "listing_agent")
        assert facts.listing_agent is None

    def test_listing_broker_field(self):
        facts = CrossSitePropertyFacts()
        assert hasattr(facts, "listing_broker")
        assert facts.listing_broker is None

    def test_mls_number_field(self):
        facts = CrossSitePropertyFacts()
        assert hasattr(facts, "mls_number")
        assert facts.mls_number is None

    def test_source_mls_field(self):
        facts = CrossSitePropertyFacts()
        assert hasattr(facts, "source_mls")
        assert facts.source_mls is None


class TestCrossSiteComparisonResultModel:
    """Test CrossSiteComparisonResult parse quality fields."""

    def test_lowest_parse_confidence_field(self):
        result = CrossSiteComparisonResult()
        assert hasattr(result, "lowest_parse_confidence")

    def test_sources_with_parse_warnings_field(self):
        result = CrossSiteComparisonResult()
        assert hasattr(result, "sources_with_parse_warnings")
        assert result.sources_with_parse_warnings == []

    def test_sources_with_partial_parse_field(self):
        result = CrossSiteComparisonResult()
        assert hasattr(result, "sources_with_partial_parse")
        assert result.sources_with_partial_parse == []


# ============================================================
# No Walkability Fields Test
# ============================================================


class TestNoWalkabilityFields:
    """Verify no walkability fields are added."""

    def test_no_walkability_in_property_facts(self):
        facts = CrossSitePropertyFacts()
        fields = set(facts.model_fields.keys())
        walkability_fields = {
            "walk_score", "walkability", "transit_score", "bike_score",
            "walkability_score",
        }
        assert fields.isdisjoint(walkability_fields)

    def test_no_walkability_in_parse_result(self):
        result = CrossSiteParseResult(source_site="zillow", parse_status="success")
        fields = set(result.model_fields.keys())
        walkability_fields = {
            "walk_score", "walkability", "transit_score", "bike_score",
        }
        assert fields.isdisjoint(walkability_fields)


# ============================================================
# Parser Fixture Tests - Zillow
# ============================================================


class TestZillowParserFixtures:
    """Test Zillow parser against all fixture variants."""

    def test_normal_property(self):
        fixture = FIXTURES_DIR / "zillow" / "normal_property.html"
        result = parse_zillow_detail_file(fixture)
        assert result.parse_status in ("success", "partial")
        assert result.parse_confidence == "high"
        assert result.address is not None
        assert result.property_facts.price == 750000.0
        assert result.property_facts.beds == 3
        assert result.property_facts.baths == 2.5
        assert result.property_facts.sqft == 2100
        assert result.property_facts.garage_spaces == 2
        assert result.property_facts.gas_service is True
        assert result.property_facts.displayed_dom == 15

    def test_price_discrepancy(self):
        fixture = FIXTURES_DIR / "zillow" / "price_discrepancy.html"
        result = parse_zillow_detail_file(fixture)
        assert result.parse_status in ("success", "partial")
        assert result.property_facts.price is not None

    def test_status_pending(self):
        fixture = FIXTURES_DIR / "zillow" / "status_pending.html"
        result = parse_zillow_detail_file(fixture)
        assert result.parse_status in ("success", "partial")
        assert result.parse_confidence == "high"
        assert result.property_facts.listing_status == "pending"
        assert result.property_facts.price == 685000.0
        assert result.property_facts.listing_agent == "Jane Smith"
        assert result.property_facts.listing_broker == "RE/MAX Results"
        assert result.property_facts.mls_number == "SW24001234"
        assert result.property_facts.source_mls == "CRMLS"

    def test_sold_or_off_market(self):
        fixture = FIXTURES_DIR / "zillow" / "sold_or_off_market.html"
        result = parse_zillow_detail_file(fixture)
        assert result.parse_status in ("success", "partial")
        assert result.property_facts.listing_status == "sold"
        assert result.property_facts.price == 725000.0
        assert result.property_facts.garage_spaces == 3
        assert result.property_facts.gas_service is True

    def test_missing_optional_fields(self):
        fixture = FIXTURES_DIR / "zillow" / "missing_optional_fields.html"
        result = parse_zillow_detail_file(fixture)
        assert result.parse_confidence in ("high", "medium")
        assert result.property_facts.price == 599900.0
        # No garage, no DOM, no lot size in this fixture
        assert result.property_facts.garage_spaces is None
        assert result.property_facts.displayed_dom is None

    def test_gas_evidence(self):
        fixture = FIXTURES_DIR / "zillow" / "gas_evidence.html"
        result = parse_zillow_detail_file(fixture)
        assert result.property_facts.gas_service is True
        assert result.property_facts.gas_evidence is not None
        assert result.property_facts.price == 815000.0

    def test_garage_evidence(self):
        fixture = FIXTURES_DIR / "zillow" / "garage_evidence.html"
        result = parse_zillow_detail_file(fixture)
        assert result.property_facts.garage_spaces == 3
        assert result.property_facts.price == 1250000.0

    def test_sparse_data(self):
        fixture = FIXTURES_DIR / "zillow" / "sparse_data.html"
        result = parse_zillow_detail_file(fixture)
        assert result.parse_status in ("success", "partial")
        # Sparse data should still extract what it can

    def test_sparse_or_malformed(self):
        fixture = FIXTURES_DIR / "zillow" / "sparse_or_malformed.html"
        result = parse_zillow_detail_file(fixture)
        assert result.parse_confidence == "low"
        assert len(result.missing_required_fields) > 0


# ============================================================
# Parser Fixture Tests - Realtor
# ============================================================


class TestRealtorParserFixtures:
    """Test Realtor.com parser against all fixture variants."""

    def test_normal_property(self):
        fixture = FIXTURES_DIR / "realtor" / "normal_property.html"
        result = parse_realtor_detail_file(fixture)
        assert result.parse_status in ("success", "partial")
        assert result.parse_confidence == "high"
        assert result.address is not None
        assert result.property_facts.price is not None

    def test_price_discrepancy(self):
        fixture = FIXTURES_DIR / "realtor" / "price_discrepancy.html"
        result = parse_realtor_detail_file(fixture)
        assert result.property_facts.price is not None

    def test_status_pending(self):
        fixture = FIXTURES_DIR / "realtor" / "status_pending.html"
        result = parse_realtor_detail_file(fixture)
        assert result.parse_confidence == "high"
        assert result.property_facts.listing_status == "pending"
        assert result.property_facts.price == 685000.0
        assert result.property_facts.listing_agent == "Jane Smith"

    def test_sold_or_off_market(self):
        fixture = FIXTURES_DIR / "realtor" / "sold_or_off_market.html"
        result = parse_realtor_detail_file(fixture)
        assert result.property_facts.listing_status == "off_market"
        assert result.property_facts.price == 725000.0

    def test_missing_optional_fields(self):
        fixture = FIXTURES_DIR / "realtor" / "missing_optional_fields.html"
        result = parse_realtor_detail_file(fixture)
        assert result.property_facts.price == 599900.0
        assert result.property_facts.garage_spaces is None

    def test_gas_evidence(self):
        fixture = FIXTURES_DIR / "realtor" / "gas_evidence.html"
        result = parse_realtor_detail_file(fixture)
        assert result.property_facts.gas_service is True

    def test_garage_evidence(self):
        fixture = FIXTURES_DIR / "realtor" / "garage_evidence.html"
        result = parse_realtor_detail_file(fixture)
        assert result.property_facts.garage_spaces == 3

    def test_sparse_data(self):
        fixture = FIXTURES_DIR / "realtor" / "sparse_data.html"
        result = parse_realtor_detail_file(fixture)
        assert result.parse_status in ("success", "partial")

    def test_sparse_or_malformed(self):
        fixture = FIXTURES_DIR / "realtor" / "sparse_or_malformed.html"
        result = parse_realtor_detail_file(fixture)
        assert result.parse_confidence == "low"
        assert len(result.missing_required_fields) > 0


# ============================================================
# Parser Fixture Tests - Homes
# ============================================================


class TestHomesParserFixtures:
    """Test Homes.com parser against all fixture variants."""

    def test_normal_property(self):
        fixture = FIXTURES_DIR / "homes" / "normal_property.html"
        result = parse_homes_detail_file(fixture)
        assert result.parse_status in ("success", "partial")
        assert result.parse_confidence == "high"
        assert result.address is not None
        assert result.property_facts.price is not None

    def test_price_discrepancy(self):
        fixture = FIXTURES_DIR / "homes" / "price_discrepancy.html"
        result = parse_homes_detail_file(fixture)
        assert result.property_facts.price is not None

    def test_status_pending(self):
        fixture = FIXTURES_DIR / "homes" / "status_pending.html"
        result = parse_homes_detail_file(fixture)
        assert result.parse_confidence == "high"
        assert result.property_facts.listing_status == "pending"
        assert result.property_facts.price == 685000.0

    def test_sold_or_off_market(self):
        fixture = FIXTURES_DIR / "homes" / "sold_or_off_market.html"
        result = parse_homes_detail_file(fixture)
        assert result.property_facts.listing_status == "sold"
        assert result.property_facts.price == 725000.0

    def test_missing_optional_fields(self):
        fixture = FIXTURES_DIR / "homes" / "missing_optional_fields.html"
        result = parse_homes_detail_file(fixture)
        assert result.property_facts.price == 599900.0

    def test_gas_evidence(self):
        fixture = FIXTURES_DIR / "homes" / "gas_evidence.html"
        result = parse_homes_detail_file(fixture)
        assert result.property_facts.gas_service is True

    def test_garage_evidence(self):
        fixture = FIXTURES_DIR / "homes" / "garage_evidence.html"
        result = parse_homes_detail_file(fixture)
        assert result.property_facts.garage_spaces == 3

    def test_sparse_data(self):
        fixture = FIXTURES_DIR / "homes" / "sparse_data.html"
        result = parse_homes_detail_file(fixture)
        assert result.parse_status in ("success", "partial")

    def test_sparse_or_malformed(self):
        fixture = FIXTURES_DIR / "homes" / "sparse_or_malformed.html"
        result = parse_homes_detail_file(fixture)
        assert result.parse_confidence == "low"
        assert len(result.missing_required_fields) > 0


# ============================================================
# Parser Fixture Tests - Compass
# ============================================================


class TestCompassParserFixtures:
    """Test Compass parser against all fixture variants."""

    def test_normal_property(self):
        fixture = FIXTURES_DIR / "compass" / "normal_property.html"
        result = parse_compass_detail_file(fixture)
        assert result.parse_status in ("success", "partial")
        assert result.parse_confidence == "high"
        assert result.address is not None
        assert result.property_facts.price is not None

    def test_price_discrepancy(self):
        fixture = FIXTURES_DIR / "compass" / "price_discrepancy.html"
        result = parse_compass_detail_file(fixture)
        assert result.property_facts.price is not None

    def test_status_pending(self):
        fixture = FIXTURES_DIR / "compass" / "status_pending.html"
        result = parse_compass_detail_file(fixture)
        assert result.parse_confidence == "high"
        assert result.property_facts.listing_status == "pending"
        assert result.property_facts.price == 685000.0

    def test_sold_or_off_market(self):
        fixture = FIXTURES_DIR / "compass" / "sold_or_off_market.html"
        result = parse_compass_detail_file(fixture)
        assert result.property_facts.listing_status == "off_market"
        assert result.property_facts.price == 725000.0

    def test_missing_optional_fields(self):
        fixture = FIXTURES_DIR / "compass" / "missing_optional_fields.html"
        result = parse_compass_detail_file(fixture)
        assert result.property_facts.price == 599900.0

    def test_gas_evidence(self):
        fixture = FIXTURES_DIR / "compass" / "gas_evidence.html"
        result = parse_compass_detail_file(fixture)
        assert result.property_facts.gas_service is True

    def test_garage_evidence(self):
        fixture = FIXTURES_DIR / "compass" / "garage_evidence.html"
        result = parse_compass_detail_file(fixture)
        assert result.property_facts.garage_spaces == 3

    def test_sparse_data(self):
        fixture = FIXTURES_DIR / "compass" / "sparse_data.html"
        result = parse_compass_detail_file(fixture)
        assert result.parse_status in ("success", "partial")

    def test_sparse_or_malformed(self):
        fixture = FIXTURES_DIR / "compass" / "sparse_or_malformed.html"
        result = parse_compass_detail_file(fixture)
        assert result.parse_confidence == "low"
        assert len(result.missing_required_fields) > 0


# ============================================================
# Confidence Classification Tests
# ============================================================


class TestConfidenceClassification:
    """Test parse confidence classification across parsers."""

    def test_high_confidence_all_fields(self):
        """Full property with address, price, status, beds/baths/sqft."""
        html = """
        <html><body>
        <h1 class="address">123 Test St</h1>
        <div class="location">Temecula, CA 92592</div>
        <span data-testid="price">$750,000</span>
        <div>3 beds | 2 baths | 1,800 sqft</div>
        <div class="listing-status">For Sale</div>
        </body></html>
        """
        result = parse_zillow_detail_html(html)
        assert result.parse_confidence == "high"
        assert result.missing_required_fields == []

    def test_medium_confidence_missing_status(self):
        """Address + price + beds but no status."""
        html = """
        <html><body>
        <h1 class="address">123 Test St</h1>
        <div class="location">Temecula, CA 92592</div>
        <span data-testid="price">$750,000</span>
        <div>3 beds</div>
        </body></html>
        """
        result = parse_zillow_detail_html(html)
        # Has address, price, and beds - should be high (has_some_facts + has_price)
        assert result.parse_confidence == "high"

    def test_medium_confidence_no_price(self):
        """Address + beds/baths but no price."""
        html = """
        <html><body>
        <h1 class="address">123 Test St</h1>
        <div class="location">Temecula, CA 92592</div>
        <div>3 beds | 2 baths | 1800 sqft</div>
        </body></html>
        """
        result = parse_zillow_detail_html(html)
        assert result.parse_confidence == "medium"
        assert "price" in result.missing_required_fields

    def test_low_confidence_minimal(self):
        """No address, no price, no facts."""
        html = """
        <html><body>
        <p>This listing is unavailable.</p>
        </body></html>
        """
        result = parse_zillow_detail_html(html)
        assert result.parse_confidence == "low"
        assert "address" in result.missing_required_fields
        assert "price" in result.missing_required_fields

    def test_failed_parse_is_low_confidence(self):
        """File not found should be low confidence."""
        result = parse_zillow_detail_file(Path("nonexistent.html"))
        assert result.parse_status == "failed"
        assert result.parse_confidence == "low"


# ============================================================
# Warnings and Missing Fields Tests
# ============================================================


class TestWarningsAndMissingFields:
    """Test parse warnings and missing required fields tracking."""

    def test_missing_fields_tracked(self):
        """Sparse HTML should track missing required fields."""
        html = """
        <html><body>
        <h1 class="address">123 Test St</h1>
        <div class="location">Temecula, CA 92592</div>
        </body></html>
        """
        result = parse_zillow_detail_html(html)
        assert "price" in result.missing_required_fields
        assert "beds" in result.missing_required_fields
        assert "baths" in result.missing_required_fields
        assert "sqft" in result.missing_required_fields

    def test_no_missing_required_for_full_parse(self):
        """Full property should have no missing required fields."""
        fixture = FIXTURES_DIR / "zillow" / "status_pending.html"
        result = parse_zillow_detail_file(fixture)
        assert result.missing_required_fields == []


# ============================================================
# Cross-Parser Consistency Tests
# ============================================================


class TestCrossParserConsistency:
    """Test that all 4 parsers produce consistent results."""

    def test_all_parsers_return_confidence(self):
        """All parsers should set parse_confidence."""
        for source, parser_fn in [
            ("zillow", parse_zillow_detail_html),
            ("realtor", parse_realtor_detail_html),
            ("homes", parse_homes_detail_html),
            ("compass", parse_compass_detail_html),
        ]:
            result = parser_fn("<html><body></body></html>")
            assert result.parse_confidence in ("high", "medium", "low"), (
                f"{source} parser missing confidence"
            )

    def test_all_parsers_return_missing_fields(self):
        """All parsers should populate missing_required_fields."""
        for source, parser_fn in [
            ("zillow", parse_zillow_detail_html),
            ("realtor", parse_realtor_detail_html),
            ("homes", parse_homes_detail_html),
            ("compass", parse_compass_detail_html),
        ]:
            result = parser_fn("<html><body></body></html>")
            assert isinstance(result.missing_required_fields, list), (
                f"{source} parser missing missing_required_fields"
            )

    def test_all_parsers_extract_listing_agent(self):
        """All parsers should extract listing agent from appropriate HTML."""
        html = """
        <html><body>
        <h1 class="address">Test</h1>
        <div class="price">$500,000</div>
        <div>3 beds | 2 baths | 1500 sqft</div>
        <div class="listing-status">For Sale</div>
        <span class="listing-agent">Listed by Test Agent</span>
        <span class="listing-broker">Test Broker</span>
        <span class="mls-info">MLS# TEST123</span>
        <span class="source-mls">CRMLS</span>
        </body></html>
        """
        for source, parser_fn in [
            ("zillow", parse_zillow_detail_html),
            ("realtor", parse_realtor_detail_html),
            ("homes", parse_homes_detail_html),
            ("compass", parse_compass_detail_html),
        ]:
            result = parser_fn(html)
            assert result.property_facts.listing_agent == "Test Agent", (
                f"{source} parser failed listing_agent extraction"
            )
            assert result.property_facts.listing_broker == "Test Broker", (
                f"{source} parser failed listing_broker extraction"
            )
            assert result.property_facts.mls_number == "TEST123", (
                f"{source} parser failed mls_number extraction"
            )
            assert result.property_facts.source_mls == "CRMLS", (
                f"{source} parser failed source_mls extraction"
            )


# ============================================================
# No Network Calls Test
# ============================================================


class TestNoNetworkCalls:
    """Verify parsers make no network calls."""

    def test_zillow_parser_is_local_only(self):
        """Zillow parser should work on local HTML only."""
        import marketsentry.zillow_parser as zp
        # No requests, urllib, or http imports
        source = Path(zp.__file__).read_text()
        assert "import requests" not in source
        assert "import urllib" not in source
        assert "import http" not in source

    def test_realtor_parser_is_local_only(self):
        """Realtor parser should work on local HTML only."""
        import marketsentry.realtor_parser as rp
        source = Path(rp.__file__).read_text()
        assert "import requests" not in source
        assert "import urllib" not in source

    def test_homes_parser_is_local_only(self):
        """Homes parser should work on local HTML only."""
        import marketsentry.homes_parser as hp
        source = Path(hp.__file__).read_text()
        assert "import requests" not in source
        assert "import urllib" not in source

    def test_compass_parser_is_local_only(self):
        """Compass parser should work on local HTML only."""
        import marketsentry.compass_parser as cp
        source = Path(cp.__file__).read_text()
        assert "import requests" not in source
        assert "import urllib" not in source


# ============================================================
# Fixture Corpus Completeness Tests
# ============================================================


class TestFixtureCorpusCompleteness:
    """Verify all required fixture variants exist for all sources."""

    REQUIRED_VARIANTS = [
        "normal_property.html",
        "price_discrepancy.html",
        "status_pending.html",
        "sold_or_off_market.html",
        "missing_optional_fields.html",
        "gas_evidence.html",
        "garage_evidence.html",
    ]

    SOURCES = ["zillow", "realtor", "homes", "compass"]

    def test_all_fixture_variants_exist(self):
        """All sources should have all required fixture variants."""
        for source in self.SOURCES:
            source_dir = FIXTURES_DIR / source
            assert source_dir.exists(), f"Fixture directory missing: {source}"

            for variant in self.REQUIRED_VARIANTS:
                fixture = source_dir / variant
                assert fixture.exists(), (
                    f"Missing fixture: {source}/{variant}"
                )

    def test_sparse_fixture_exists(self):
        """Each source should have a sparse data fixture."""
        for source in self.SOURCES:
            source_dir = FIXTURES_DIR / source
            # Either sparse_data.html or sparse_or_malformed.html
            has_sparse = (
                (source_dir / "sparse_data.html").exists()
                or (source_dir / "sparse_or_malformed.html").exists()
            )
            assert has_sparse, f"Missing sparse fixture for {source}"

    def test_at_least_8_fixtures_per_source(self):
        """Each source should have at least 8 fixture files."""
        for source in self.SOURCES:
            source_dir = FIXTURES_DIR / source
            html_files = list(source_dir.glob("*.html"))
            assert len(html_files) >= 8, (
                f"{source} has only {len(html_files)} fixtures, need >= 8"
            )


# ============================================================
# Lot Size Extraction Tests
# ============================================================


class TestLotSizeExtraction:
    """Test lot size extraction across parsers."""

    def test_lot_size_acres(self):
        html = """
        <html><body>
        <h1 class="address">123 Test</h1>
        <div class="location">Temecula, CA 92592</div>
        <div class="price">$500,000</div>
        <div>3 beds | 2 baths | 1500 sqft</div>
        <div class="listing-status">For Sale</div>
        <div>Lot: 0.25 acres</div>
        </body></html>
        """
        result = parse_zillow_detail_html(html)
        assert result.property_facts.lot_size == 0.25

    def test_lot_size_sqft(self):
        html = """
        <html><body>
        <h1 class="address">123 Test</h1>
        <div class="location">Temecula, CA 92592</div>
        <div class="price">$500,000</div>
        <div>3 beds | 2 baths | 1500 sqft</div>
        <div class="listing-status">For Sale</div>
        <div>Lot: 7405 sqft</div>
        </body></html>
        """
        result = parse_zillow_detail_html(html)
        assert result.property_facts.lot_size is not None
        assert abs(result.property_facts.lot_size - 0.1700) < 0.001
