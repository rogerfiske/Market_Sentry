"""Tests for cross-site comparison functionality."""

import tempfile
from pathlib import Path

import pytest

from marketsentry.cross_site_comparison import (
    compare_property_cross_site,
    detect_dom_discrepancy,
    detect_price_discrepancy,
    detect_status_discrepancy,
)
from marketsentry.database import execute_insert, execute_query
from marketsentry.models import CrossSiteComparisonResult


class TestCompareCrossSite:
    """Tests for compare_property_cross_site function."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        from marketsentry.database import init_db
        init_db(db_path)

        yield db_path

        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def property_with_observations(self, temp_db):
        """Create property with cross-site observations."""
        # Create property
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, city, zip, current_price, displayed_dom, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        params = ("2026-05-01", "123 Test St", "Temecula", "92592", 500000.0, 15, 1)
        execute_insert(query, params, database_path=temp_db)

        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE address = ?",
            (params[0],),
            database_path=temp_db,
        )
        property_id = result[0]["property_id"]

        # Add Zillow observation (matching price)
        obs_query = """
        INSERT INTO cross_site_observations (
            property_id, source_site, price, displayed_dom, listing_status
        ) VALUES (?, ?, ?, ?, ?)
        """
        execute_insert(
            obs_query,
            (property_id, "zillow", 500000.0, 15, "for_sale"),
            database_path=temp_db,
        )

        # Add Realtor observation (matching price)
        execute_insert(
            obs_query,
            (property_id, "realtor", 500000.0, 15, "for_sale"),
            database_path=temp_db,
        )

        return property_id

    def test_comparison_with_matching_data(self, temp_db, property_with_observations):
        """Test comparison when all data matches."""
        comparison = compare_property_cross_site(
            property_with_observations, temp_db
        )

        assert comparison.property_id == property_with_observations
        assert comparison.redfin_price == 500000.0
        assert comparison.zillow_price == 500000.0
        assert comparison.realtor_price == 500000.0

        # No discrepancies
        assert comparison.has_price_discrepancy is False
        assert comparison.has_status_discrepancy is False
        assert comparison.has_dom_discrepancy is False

    def test_comparison_with_price_discrepancy(self, temp_db):
        """Test comparison with price discrepancy."""
        # Create property
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, city, zip, current_price, displayed_dom, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        execute_insert(
            query,
            ("456 Price St", "Temecula", "92592", 750000.0, 10, 1),
            database_path=temp_db,
        )

        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE address = ?",
            ("456 Price St",),
            database_path=temp_db,
        )
        property_id = result[0]["property_id"]

        # Add observation with different price (>$10k difference)
        obs_query = """
        INSERT INTO cross_site_observations (
            property_id, source_site, price, displayed_dom, listing_status
        ) VALUES (?, ?, ?, ?, ?)
        """
        execute_insert(
            obs_query,
            (property_id, "zillow", 735000.0, 10, "for_sale"),
            database_path=temp_db,
        )

        comparison = compare_property_cross_site(property_id, temp_db)

        # Should detect price discrepancy
        assert comparison.has_price_discrepancy is True
        assert comparison.price_discrepancy_details is not None
        assert "Zillow" in comparison.price_discrepancy_details

    def test_comparison_with_status_discrepancy(self, temp_db):
        """Test comparison with status discrepancy."""
        # Create property
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, city, zip, current_price, displayed_dom, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        execute_insert(
            query,
            ("789 Status Ave", "Temecula", "92592", 600000.0, 20, 1),
            database_path=temp_db,
        )

        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE address = ?",
            ("789 Status Ave",),
            database_path=temp_db,
        )
        property_id = result[0]["property_id"]

        # Add observation with different status
        obs_query = """
        INSERT INTO cross_site_observations (
            property_id, source_site, price, displayed_dom, listing_status
        ) VALUES (?, ?, ?, ?, ?)
        """
        execute_insert(
            obs_query,
            (property_id, "zillow", 600000.0, 20, "sold"),
            database_path=temp_db,
        )

        comparison = compare_property_cross_site(property_id, temp_db)

        # Should detect status discrepancy (active vs sold)
        assert comparison.has_status_discrepancy is True
        assert comparison.status_discrepancy_details is not None

    def test_comparison_with_dom_discrepancy(self, temp_db):
        """Test comparison with DOM discrepancy."""
        # Create property
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, city, zip, current_price, displayed_dom, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        execute_insert(
            query,
            ("101 DOM Ln", "Temecula", "92592", 550000.0, 15, 1),
            database_path=temp_db,
        )

        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE address = ?",
            ("101 DOM Ln",),
            database_path=temp_db,
        )
        property_id = result[0]["property_id"]

        # Add observation with different DOM (>30 days difference)
        obs_query = """
        INSERT INTO cross_site_observations (
            property_id, source_site, price, displayed_dom, listing_status
        ) VALUES (?, ?, ?, ?, ?)
        """
        execute_insert(
            obs_query,
            (property_id, "zillow", 550000.0, 50, "for_sale"),
            database_path=temp_db,
        )

        comparison = compare_property_cross_site(property_id, temp_db)

        # Should detect DOM discrepancy
        assert comparison.has_dom_discrepancy is True
        assert comparison.dom_discrepancy_details is not None
        assert "35 days" in comparison.dom_discrepancy_details

    def test_comparison_with_multiple_observations(self, temp_db):
        """Test comparison with observations from multiple sites."""
        # Create property
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, city, zip, current_price, displayed_dom, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        execute_insert(
            query,
            ("999 Multi St", "Temecula", "92592", 700000.0, 25, 1),
            database_path=temp_db,
        )

        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE address = ?",
            ("999 Multi St",),
            database_path=temp_db,
        )
        property_id = result[0]["property_id"]

        # Add observations from different sites
        obs_query = """
        INSERT INTO cross_site_observations (
            property_id, source_site, price, displayed_dom, listing_status
        ) VALUES (?, ?, ?, ?, ?)
        """
        execute_insert(
            obs_query,
            (property_id, "zillow", 700000.0, 25, "for_sale"),
            database_path=temp_db,
        )
        execute_insert(
            obs_query,
            (property_id, "realtor", 715000.0, 25, "for_sale"),
            database_path=temp_db,
        )
        execute_insert(
            obs_query,
            (property_id, "homes", 700000.0, 60, "for_sale"),
            database_path=temp_db,
        )

        comparison = compare_property_cross_site(property_id, temp_db)

        # Should have data from all sources
        assert comparison.zillow_price == 700000.0
        assert comparison.realtor_price == 715000.0
        assert comparison.homes_price == 700000.0

        # Should detect Realtor price discrepancy
        assert comparison.has_price_discrepancy is True
        # Should detect Homes DOM discrepancy
        assert comparison.has_dom_discrepancy is True


class TestPriceDiscrepancyDetection:
    """Tests for detect_price_discrepancy function."""

    def test_price_within_threshold(self):
        """Test that prices within $10k threshold are not flagged."""
        comparison = CrossSiteComparisonResult(property_id=1)
        comparison.redfin_price = 500000.0
        comparison.zillow_price = 509000.0  # $9k difference

        result = detect_price_discrepancy(comparison)

        assert result.has_price_discrepancy is False

    def test_price_exceeds_threshold(self):
        """Test that prices exceeding $10k threshold are flagged."""
        comparison = CrossSiteComparisonResult(property_id=1)
        comparison.redfin_price = 500000.0
        comparison.zillow_price = 485000.0  # $15k difference

        result = detect_price_discrepancy(comparison)

        assert result.has_price_discrepancy is True
        assert "$15,000" in result.price_discrepancy_details

    def test_multiple_price_discrepancies(self):
        """Test detecting discrepancies across multiple sites."""
        comparison = CrossSiteComparisonResult(property_id=1)
        comparison.redfin_price = 600000.0
        comparison.zillow_price = 585000.0  # $15k diff
        comparison.realtor_price = 625000.0  # $25k diff
        comparison.homes_price = 598000.0  # $2k diff (within threshold)

        result = detect_price_discrepancy(comparison)

        assert result.has_price_discrepancy is True
        # Should mention both Zillow and Realtor
        assert "Zillow" in result.price_discrepancy_details
        assert "Realtor" in result.price_discrepancy_details
        # Should not mention Homes (within threshold)
        assert "Homes" not in result.price_discrepancy_details

    def test_no_redfin_price(self):
        """Test that comparison without Redfin price doesn't fail."""
        comparison = CrossSiteComparisonResult(property_id=1)
        comparison.redfin_price = None
        comparison.zillow_price = 500000.0

        result = detect_price_discrepancy(comparison)

        assert result.has_price_discrepancy is False


class TestStatusDiscrepancyDetection:
    """Tests for detect_status_discrepancy function."""

    def test_active_vs_sold_discrepancy(self):
        """Test that active vs sold status is flagged."""
        comparison = CrossSiteComparisonResult(property_id=1)
        comparison.redfin_status = "active"
        comparison.zillow_status = "sold"

        result = detect_status_discrepancy(comparison)

        assert result.has_status_discrepancy is True
        assert result.status_discrepancy_details is not None

    def test_active_vs_pending_discrepancy(self):
        """Test that active vs pending status is flagged."""
        comparison = CrossSiteComparisonResult(property_id=1)
        comparison.redfin_status = "active"
        comparison.realtor_status = "pending"

        result = detect_status_discrepancy(comparison)

        assert result.has_status_discrepancy is True

    def test_matching_statuses(self):
        """Test that matching statuses don't trigger discrepancy."""
        comparison = CrossSiteComparisonResult(property_id=1)
        comparison.redfin_status = "active"
        comparison.zillow_status = "for_sale"  # Normalizes to active
        comparison.realtor_status = "active"

        result = detect_status_discrepancy(comparison)

        assert result.has_status_discrepancy is False

    def test_single_status_only(self):
        """Test that single status doesn't trigger comparison."""
        comparison = CrossSiteComparisonResult(property_id=1)
        comparison.redfin_status = "active"

        result = detect_status_discrepancy(comparison)

        assert result.has_status_discrepancy is False


class TestDOMDiscrepancyDetection:
    """Tests for detect_dom_discrepancy function."""

    def test_dom_within_threshold(self):
        """Test that DOM within 30 days is not flagged."""
        comparison = CrossSiteComparisonResult(property_id=1)
        comparison.redfin_dom = 20
        comparison.zillow_dom = 25  # 5 days difference

        result = detect_dom_discrepancy(comparison)

        assert result.has_dom_discrepancy is False

    def test_dom_exceeds_threshold(self):
        """Test that DOM exceeding 30 days is flagged."""
        comparison = CrossSiteComparisonResult(property_id=1)
        comparison.redfin_dom = 15
        comparison.zillow_dom = 50  # 35 days difference

        result = detect_dom_discrepancy(comparison)

        assert result.has_dom_discrepancy is True
        assert "35 days" in result.dom_discrepancy_details

    def test_multiple_dom_discrepancies(self):
        """Test detecting DOM discrepancies across multiple sites."""
        comparison = CrossSiteComparisonResult(property_id=1)
        comparison.redfin_dom = 10
        comparison.zillow_dom = 45  # 35 days diff
        comparison.realtor_dom = 50  # 40 days diff
        comparison.homes_dom = 15  # 5 days diff (within threshold)

        result = detect_dom_discrepancy(comparison)

        assert result.has_dom_discrepancy is True
        # Should mention both Zillow and Realtor
        assert "Zillow" in result.dom_discrepancy_details
        assert "Realtor" in result.dom_discrepancy_details

    def test_no_redfin_dom(self):
        """Test that comparison without Redfin DOM doesn't fail."""
        comparison = CrossSiteComparisonResult(property_id=1)
        comparison.redfin_dom = None
        comparison.zillow_dom = 20

        result = detect_dom_discrepancy(comparison)

        assert result.has_dom_discrepancy is False


class TestComparisonNotes:
    """Tests for comparison notes generation."""

    def test_notes_with_discrepancies(self):
        """Test that comparison notes mention discrepancies."""
        comparison = CrossSiteComparisonResult(property_id=1)
        comparison.redfin_price = 500000.0
        comparison.zillow_price = 485000.0  # Price discrepancy
        comparison.redfin_dom = 10
        comparison.zillow_dom = 45  # DOM discrepancy

        # Detect discrepancies
        comparison = detect_price_discrepancy(comparison)
        comparison = detect_dom_discrepancy(comparison)

        # Build notes (simulating what compare_property_cross_site does)
        notes = []
        if comparison.has_price_discrepancy:
            notes.append("Price discrepancy detected")
        if comparison.has_dom_discrepancy:
            notes.append("DOM discrepancy detected")

        comparison.comparison_notes = "; ".join(notes)

        assert "Price discrepancy" in comparison.comparison_notes
        assert "DOM discrepancy" in comparison.comparison_notes

    def test_no_discrepancies_no_notes(self):
        """Test that no discrepancies result in no notes."""
        comparison = CrossSiteComparisonResult(property_id=1)
        comparison.redfin_price = 500000.0
        comparison.zillow_price = 500000.0

        comparison = detect_price_discrepancy(comparison)

        assert comparison.has_price_discrepancy is False
        assert comparison.price_discrepancy_details is None
