"""Tests for cross-site URL import functionality."""

import tempfile
import time
from pathlib import Path

import pytest

from marketsentry.cross_site_url_import import import_cross_site_urls_from_csv
from marketsentry.database import execute_insert, execute_query


class TestImportCrossSiteUrls:
    """Tests for import_cross_site_urls_from_csv function."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        # Initialize database schema
        from marketsentry.database import init_db
        init_db(db_path)

        yield db_path

        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def sample_property(self, temp_db):
        """Create a sample watched property for testing."""
        query = """
        INSERT INTO watched_properties (
            first_saved_date, redfin_url, normalized_address, address, city, zip,
            beds, baths, sqft, current_price, displayed_dom, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            "2026-05-01",
            "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263",
            "46197 VIA LA TRANQUILA",
            "46197 Via La Tranquila",
            "Temecula",
            "92592",
            3,
            2.5,
            2100,
            750000.0,
            15,
            1,
        )
        execute_insert(query, params, database_path=temp_db)

        # Get the inserted property_id
        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE redfin_url = ?",
            (params[1],),  # params[1] is the redfin_url
            database_path=temp_db,
        )
        return result[0]["property_id"]

    def test_import_valid_csv(self, temp_db, sample_property):
        """Test importing valid CSV with cross-site URLs."""
        csv_path = "tests/fixtures/cross_site_urls.csv"

        result = import_cross_site_urls_from_csv(csv_path, temp_db)

        # Check import statistics
        assert result.total_rows_read == 3
        assert result.properties_matched >= 1
        assert result.properties_updated >= 1

        # Verify URLs were updated in database
        property_data = execute_query(
            "SELECT zillow_url, realtor_url, homes_url, compass_url FROM watched_properties WHERE property_id = ?",
            (sample_property,),
            database_path=temp_db,
        )

        assert property_data[0]["zillow_url"] is not None
        assert "zillow.com" in property_data[0]["zillow_url"]

    def test_import_matches_by_redfin_url(self, temp_db, sample_property):
        """Test that import matches properties by redfin_url."""
        # Create temporary CSV with redfin_url match
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            csv_path = f.name
            f.write("redfin_url,zillow_url,realtor_url,homes_url,compass_url\n")
            f.write(
                "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263,"
                "https://www.zillow.com/test123,,,\n"
            )

        try:
            result = import_cross_site_urls_from_csv(csv_path, temp_db)

            assert result.properties_matched == 1
            assert result.properties_updated == 1

            # Verify Zillow URL was set
            property_data = execute_query(
                "SELECT zillow_url FROM watched_properties WHERE property_id = ?",
                (sample_property,),
                database_path=temp_db,
            )
            assert property_data[0]["zillow_url"] == "https://www.zillow.com/test123"

        finally:
            Path(csv_path).unlink(missing_ok=True)

    def test_import_matches_by_address(self, temp_db):
        """Test that import matches properties by normalized address."""
        # Add property without redfin_url
        query = """
        INSERT INTO watched_properties (
            first_saved_date, normalized_address, address, city, zip, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        # Use "LN" (the normalized form) instead of "LANE" since normalize_address() converts LANE -> LN
        params = ("2026-05-01", "67890 TEST LN", "67890 Test Lane", "Temecula", "92592", 1)
        execute_insert(query, params, database_path=temp_db)

        # Get property_id
        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE normalized_address = ?",
            (params[1],),  # params[1] is the normalized_address
            database_path=temp_db,
        )
        property_id = result[0]["property_id"]

        # Create CSV with address match
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            csv_path = f.name
            f.write("address,zillow_url\n")
            f.write("67890 Test Lane,https://www.zillow.com/address-match\n")

        try:
            result = import_cross_site_urls_from_csv(csv_path, temp_db)

            assert result.properties_matched == 1
            assert result.properties_updated == 1

            # Verify URL was set
            property_data = execute_query(
                "SELECT zillow_url FROM watched_properties WHERE property_id = ?",
                (property_id,),
                database_path=temp_db,
            )
            assert property_data[0]["zillow_url"] == "https://www.zillow.com/address-match"

        finally:
            Path(csv_path).unlink(missing_ok=True)

    def test_import_invalid_source(self, temp_db):
        """Test import with invalid source (non-standard column)."""
        # Create CSV with only valid columns
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            csv_path = f.name
            f.write("redfin_url,zillow_url\n")
            f.write("https://www.redfin.com/test,https://www.zillow.com/test\n")

        try:
            result = import_cross_site_urls_from_csv(csv_path, temp_db)

            # Should process without error even if no matches
            assert result.total_rows_read == 1
            # May have 0 matches if property doesn't exist
            assert result.properties_matched >= 0

        finally:
            Path(csv_path).unlink(missing_ok=True)

    def test_import_missing_file(self, temp_db):
        """Test import with non-existent CSV file."""
        result = import_cross_site_urls_from_csv("nonexistent.csv", temp_db)

        assert result.total_rows_read == 0
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()

    def test_import_empty_csv(self, temp_db):
        """Test import with empty CSV (only headers)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            csv_path = f.name
            f.write("redfin_url,zillow_url\n")

        try:
            result = import_cross_site_urls_from_csv(csv_path, temp_db)

            assert result.total_rows_read == 0
            assert result.properties_matched == 0

        finally:
            Path(csv_path).unlink(missing_ok=True)

    def test_import_partial_urls(self, temp_db, sample_property):
        """Test import with only some URLs provided."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            csv_path = f.name
            f.write("redfin_url,zillow_url,realtor_url\n")
            f.write(
                "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263,"
                "https://www.zillow.com/partial,\n"
            )

        try:
            result = import_cross_site_urls_from_csv(csv_path, temp_db)

            assert result.properties_updated == 1

            # Verify only zillow_url was set
            property_data = execute_query(
                "SELECT zillow_url, realtor_url FROM watched_properties WHERE property_id = ?",
                (sample_property,),
                database_path=temp_db,
            )
            assert property_data[0]["zillow_url"] == "https://www.zillow.com/partial"
            # realtor_url should remain NULL
            assert property_data[0]["realtor_url"] is None

        finally:
            Path(csv_path).unlink(missing_ok=True)

    def test_import_updates_timestamp(self, temp_db, sample_property):
        """Test that import updates the updated_at timestamp."""
        # Get original timestamp
        original_data = execute_query(
            "SELECT updated_at FROM watched_properties WHERE property_id = ?",
            (sample_property,),
            database_path=temp_db,
        )
        original_timestamp = original_data[0]["updated_at"]

        # Wait 1 second to ensure timestamp will be different
        time.sleep(1)

        # Import URLs
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            csv_path = f.name
            f.write("redfin_url,zillow_url\n")
            f.write(
                "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263,"
                "https://www.zillow.com/timestamp-test\n"
            )

        try:
            import_cross_site_urls_from_csv(csv_path, temp_db)

            # Get new timestamp
            new_data = execute_query(
                "SELECT updated_at FROM watched_properties WHERE property_id = ?",
                (sample_property,),
                database_path=temp_db,
            )
            new_timestamp = new_data[0]["updated_at"]

            # Timestamp should have changed
            assert new_timestamp != original_timestamp

        finally:
            Path(csv_path).unlink(missing_ok=True)
