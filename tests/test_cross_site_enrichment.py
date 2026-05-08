"""Tests for cross-site enrichment functionality."""

import tempfile
from pathlib import Path

import pytest

from marketsentry.cross_site_enrichment import (
    insert_cross_site_observation,
    parse_cross_site_directory,
)
from marketsentry.database import execute_insert, execute_query
from marketsentry.models import CrossSiteParseResult, CrossSitePropertyFacts


class TestParseCrossSiteDirectory:
    """Tests for parse_cross_site_directory function."""

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
    def sample_property(self, temp_db):
        """Create a sample watched property."""
        query = """
        INSERT INTO watched_properties (
            first_saved_date, normalized_address, address, city, zip,
            zillow_url, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            "2026-05-01",
            "46197 VIA LA TRANQUILA",
            "46197 Via La Tranquila",
            "Temecula",
            "92592",
            "https://www.zillow.com/homedetails/46197-Via-La-Tranquila-Temecula-CA-92592/12345678_zpid/",
            1,
        )
        execute_insert(query, params, database_path=temp_db)

        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE normalized_address = ?",
            (params[1],),
            database_path=temp_db,
        )
        return result[0]["property_id"]

    def test_parse_directory_zillow(self, temp_db, sample_property):
        """Test parsing Zillow directory."""
        directory = "tests/fixtures/cross_site/zillow"

        result = parse_cross_site_directory(directory, "zillow", temp_db)

        # Should process all files (3 original + 6 new fixture variants)
        assert result.total_files_processed >= 3
        assert result.observations_parsed >= 1
        # At least one should match our sample property
        assert result.properties_matched >= 1
        assert result.observations_inserted >= 1

    def test_parse_directory_all_sources(self, temp_db, sample_property):
        """Test parsing directories for all sources."""
        sources = ["zillow", "realtor", "homes", "compass"]
        results = []

        for source in sources:
            directory = f"tests/fixtures/cross_site/{source}"
            result = parse_cross_site_directory(directory, source, temp_db)
            results.append(result)

        # All should process successfully
        assert len(results) == 4
        for result in results:
            assert result.total_files_processed >= 3

    def test_parse_directory_nonexistent(self, temp_db):
        """Test parsing nonexistent directory."""
        with pytest.raises(FileNotFoundError):
            parse_cross_site_directory("nonexistent_dir", "zillow", temp_db)

    def test_parse_directory_invalid_source(self, temp_db):
        """Test parsing with invalid source site."""
        directory = "tests/fixtures/cross_site/zillow"

        # Should handle gracefully (log warning)
        result = parse_cross_site_directory(directory, "invalid_source", temp_db)

        # Files processed but nothing parsed
        assert result.total_files_processed >= 0
        assert result.observations_parsed == 0

    def test_parse_directory_updates_statistics(self, temp_db, sample_property):
        """Test that enrichment result has accurate statistics."""
        directory = "tests/fixtures/cross_site/zillow"

        result = parse_cross_site_directory(directory, "zillow", temp_db)

        # Check all statistics are set
        assert result.total_files_processed >= 0
        assert result.observations_parsed >= 0
        assert result.properties_matched >= 0
        assert result.observations_inserted >= 0
        assert result.notes is not None


class TestInsertCrossSiteObservation:
    """Tests for insert_cross_site_observation function."""

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
    def sample_property(self, temp_db):
        """Create a sample watched property."""
        query = """
        INSERT INTO watched_properties (
            first_saved_date, normalized_address, address, city, zip, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        params = ("2026-05-01", "12345 TEST ST", "12345 Test St", "Temecula", "92592", 1)
        execute_insert(query, params, database_path=temp_db)

        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE normalized_address = ?",
            (params[1],),
            database_path=temp_db,
        )
        return result[0]["property_id"]

    @pytest.fixture
    def parse_result(self):
        """Create a sample parse result."""
        facts = CrossSitePropertyFacts(
            price=500000.0,
            beds=3,
            baths=2.0,
            sqft=1800,
            listing_status="for_sale",
            displayed_dom=10,
            garage_spaces=2,
            gas_service=True,
            gas_evidence="Gas range and gas fireplace",
            property_description="Nice home with gas appliances",
        )

        result = CrossSiteParseResult(
            source_site="zillow",
            source_url="https://www.zillow.com/test",
            parse_status="success",
            address="12345 Test St",
            normalized_address="12345testst",
            city="Temecula",
            state="CA",
            zip="92592",
            property_facts=facts,
        )

        return result

    def test_insert_observation(self, temp_db, sample_property, parse_result):
        """Test inserting cross-site observation."""
        inserted = insert_cross_site_observation(
            sample_property, parse_result, temp_db
        )

        assert inserted is True

        # Verify observation in database
        obs = execute_query(
            "SELECT * FROM cross_site_observations WHERE property_id = ?",
            (sample_property,),
            database_path=temp_db,
        )

        assert len(obs) == 1
        assert obs[0]["source_site"] == "zillow"
        assert obs[0]["price"] == 500000.0
        assert obs[0]["beds"] == 3
        assert obs[0]["baths"] == 2.0

    def test_duplicate_detection(self, temp_db, sample_property, parse_result):
        """Test that duplicate observations are not inserted."""
        # Insert first observation
        inserted1 = insert_cross_site_observation(
            sample_property, parse_result, temp_db
        )
        assert inserted1 is True

        # Try to insert again (within 24 hours)
        inserted2 = insert_cross_site_observation(
            sample_property, parse_result, temp_db
        )
        assert inserted2 is False

        # Verify only one observation exists
        obs = execute_query(
            "SELECT COUNT(*) as count FROM cross_site_observations WHERE property_id = ?",
            (sample_property,),
            database_path=temp_db,
        )
        assert obs[0]["count"] == 1

    def test_insert_multiple_sources(self, temp_db, sample_property, parse_result):
        """Test inserting observations from multiple sources."""
        # Insert Zillow observation
        inserted1 = insert_cross_site_observation(
            sample_property, parse_result, temp_db
        )
        assert inserted1 is True

        # Create Realtor observation
        parse_result.source_site = "realtor"
        parse_result.source_url = "https://www.realtor.com/test"
        inserted2 = insert_cross_site_observation(
            sample_property, parse_result, temp_db
        )
        assert inserted2 is True

        # Should have 2 observations
        obs = execute_query(
            "SELECT COUNT(*) as count FROM cross_site_observations WHERE property_id = ?",
            (sample_property,),
            database_path=temp_db,
        )
        assert obs[0]["count"] == 2

    def test_insert_with_warnings(self, temp_db, sample_property, parse_result):
        """Test inserting observation with parse warnings."""
        parse_result.warnings = [
            "Warning 1: Missing field",
            "Warning 2: Invalid format",
            "Warning 3: Unknown value",
        ]
        parse_result.parse_status = "partial"

        inserted = insert_cross_site_observation(
            sample_property, parse_result, temp_db
        )

        assert inserted is True

        # Verify warnings are stored
        obs = execute_query(
            "SELECT parse_warnings, parse_status FROM cross_site_observations WHERE property_id = ?",
            (sample_property,),
            database_path=temp_db,
        )

        assert obs[0]["parse_status"] == "partial"
        assert obs[0]["parse_warnings"] is not None


class TestPropertyMatching:
    """Tests for property matching logic."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        from marketsentry.database import init_db
        init_db(db_path)

        yield db_path

        Path(db_path).unlink(missing_ok=True)

    def test_match_by_zillow_url(self, temp_db):
        """Test matching property by zillow_url."""
        # Create property with zillow_url
        query = """
        INSERT INTO watched_properties (
            first_saved_date, normalized_address, address, city, zip,
            zillow_url, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            "2026-05-01",
            "46197 VIA LA TRANQUILA",
            "46197 Via La Tranquila",
            "Temecula",
            "92592",
            "https://www.zillow.com/homedetails/46197-Via-La-Tranquila-Temecula-CA-92592/12345678_zpid/",
            1,
        )
        execute_insert(query, params, database_path=temp_db)

        # Parse directory
        directory = "tests/fixtures/cross_site/zillow"
        result = parse_cross_site_directory(directory, "zillow", temp_db)

        # Should match by URL
        assert result.properties_matched >= 1

    def test_match_by_normalized_address(self, temp_db):
        """Test matching property by normalized address."""
        # Create property without zillow_url
        query = """
        INSERT INTO watched_properties (
            first_saved_date, normalized_address, address, city, zip, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            "2026-05-01",
            "46197 VIA LA TRANQUILA",
            "46197 Via La Tranquila",
            "Temecula",
            "92592",
            1,
        )
        execute_insert(query, params, database_path=temp_db)

        # Parse directory
        directory = "tests/fixtures/cross_site/zillow"
        result = parse_cross_site_directory(directory, "zillow", temp_db)

        # Should match by normalized address
        assert result.properties_matched >= 1

    def test_no_match_inactive_property(self, temp_db):
        """Test that inactive properties are not matched."""
        # Create inactive property
        query = """
        INSERT INTO watched_properties (
            first_saved_date, normalized_address, address, city, zip,
            zillow_url, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            "2026-05-01",
            "46197 VIA LA TRANQUILA",
            "46197 Via La Tranquila",
            "Temecula",
            "92592",
            "https://www.zillow.com/homedetails/46197-Via-La-Tranquila-Temecula-CA-92592/12345678_zpid/",
            0,  # inactive
        )
        execute_insert(query, params, database_path=temp_db)

        # Parse directory
        directory = "tests/fixtures/cross_site/zillow"
        result = parse_cross_site_directory(directory, "zillow", temp_db)

        # Should not match inactive property
        assert result.properties_matched == 0
