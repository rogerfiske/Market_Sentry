"""Tests for cross-site comparison report functionality."""

import csv
import tempfile
from pathlib import Path

import pytest

from marketsentry.cross_site_report import export_cross_site_comparison_report
from marketsentry.database import execute_insert, execute_query


class TestExportCrossSiteReport:
    """Tests for export_cross_site_comparison_report function."""

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
    def properties_with_observations(self, temp_db):
        """Create properties with cross-site observations."""
        # Create property 1
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, city, zip, beds, baths, sqft,
            current_price, displayed_dom, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        execute_insert(
            query,
            ("123 Main St", "Temecula", "92592", 3, 2.0, 1800, 500000.0, 15, 1),
            database_path=temp_db,
        )

        # Get property_id
        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE address = ?",
            ("123 Main St",),
            database_path=temp_db,
        )
        property_id_1 = result[0]["property_id"]

        # Add cross-site observations for property 1
        obs_query = """
        INSERT INTO cross_site_observations (
            property_id, source_site, price, beds, baths, sqft,
            displayed_dom, listing_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        execute_insert(
            obs_query,
            (property_id_1, "zillow", 500000.0, 3, 2.0, 1800, 15, "for_sale"),
            database_path=temp_db,
        )
        execute_insert(
            obs_query,
            (property_id_1, "realtor", 500000.0, 3, 2.0, 1800, 15, "for_sale"),
            database_path=temp_db,
        )

        # Create property 2 with discrepancies
        execute_insert(
            query,
            ("456 Oak Ave", "Temecula", "92592", 4, 3.0, 2400, 750000.0, 20, 1),
            database_path=temp_db,
        )

        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE address = ?",
            ("456 Oak Ave",),
            database_path=temp_db,
        )
        property_id_2 = result[0]["property_id"]

        # Add observation with price discrepancy
        execute_insert(
            obs_query,
            (property_id_2, "zillow", 735000.0, 4, 3.0, 2400, 20, "for_sale"),
            database_path=temp_db,
        )

        return [property_id_1, property_id_2]

    def test_export_report_csv_format(self, temp_db, properties_with_observations):
        """Test that exported report is valid CSV format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name

        try:
            count = export_cross_site_comparison_report(output_path, temp_db)

            assert count == 2

            # Verify CSV file exists and is valid
            assert Path(output_path).exists()

            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                # Should have 2 properties
                assert len(rows) == 2

                # Check column headers
                expected_columns = [
                    "property_id",
                    "address",
                    "city",
                    "zip",
                    "redfin_price",
                    "zillow_price",
                    "realtor_price",
                    "has_price_discrepancy",
                    "has_status_discrepancy",
                    "has_dom_discrepancy",
                ]
                for col in expected_columns:
                    assert col in reader.fieldnames

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_export_report_with_discrepancies(self, temp_db, properties_with_observations):
        """Test that report correctly identifies discrepancies."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name

        try:
            export_cross_site_comparison_report(output_path, temp_db)

            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                # Find the property with price discrepancy (456 Oak Ave)
                property_2 = next(r for r in rows if r["address"] == "456 Oak Ave")

                assert property_2["has_price_discrepancy"] == "True"
                assert property_2["redfin_price"] == "750000.0"
                assert property_2["zillow_price"] == "735000.0"

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_export_report_empty_database(self, temp_db):
        """Test exporting report when no properties exist."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name

        try:
            count = export_cross_site_comparison_report(output_path, temp_db)

            assert count == 0

        finally:
            # May not exist if no properties
            Path(output_path).unlink(missing_ok=True)

    def test_export_report_includes_all_sites(self, temp_db):
        """Test that report includes columns for all sites."""
        # Create property
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, city, zip, current_price, displayed_dom, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        execute_insert(
            query,
            ("999 Full St", "Temecula", "92592", 600000.0, 30, 1),
            database_path=temp_db,
        )

        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE address = ?",
            ("999 Full St",),
            database_path=temp_db,
        )
        property_id = result[0]["property_id"]

        # Add observations from all sources
        obs_query = """
        INSERT INTO cross_site_observations (
            property_id, source_site, price, displayed_dom, listing_status
        ) VALUES (?, ?, ?, ?, ?)
        """
        for site in ["zillow", "realtor", "homes", "compass"]:
            execute_insert(
                obs_query,
                (property_id, site, 600000.0, 30, "for_sale"),
                database_path=temp_db,
            )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name

        try:
            export_cross_site_comparison_report(output_path, temp_db)

            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                # Should have all site columns
                assert "zillow_price" in reader.fieldnames
                assert "realtor_price" in reader.fieldnames
                assert "homes_price" in reader.fieldnames
                assert "compass_price" in reader.fieldnames

                # Check that all sites have data
                row = rows[0]
                assert row["zillow_price"] == "600000.0"
                assert row["realtor_price"] == "600000.0"
                assert row["homes_price"] == "600000.0"
                assert row["compass_price"] == "600000.0"

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_export_report_property_info_included(self, temp_db):
        """Test that report includes property information."""
        # Create property with full details
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, city, zip, beds, baths, sqft,
            current_price, displayed_dom, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        execute_insert(
            query,
            ("777 Info Blvd", "Temecula", "92592", 3, 2.5, 2100, 550000.0, 12, 1),
            database_path=temp_db,
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name

        try:
            export_cross_site_comparison_report(output_path, temp_db)

            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                row = rows[0]
                assert row["address"] == "777 Info Blvd"
                assert row["city"] == "Temecula"
                assert row["zip"] == "92592"
                assert row["redfin_beds"] == "3"
                assert row["redfin_baths"] == "2.5"
                assert row["redfin_sqft"] == "2100"

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_export_report_discrepancy_details_included(self, temp_db):
        """Test that report includes discrepancy detail columns."""
        # Create property with discrepancy
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, city, zip, current_price, displayed_dom, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        execute_insert(
            query,
            ("888 Detail Dr", "Temecula", "92592", 500000.0, 15, 1),
            database_path=temp_db,
        )

        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE address = ?",
            ("888 Detail Dr",),
            database_path=temp_db,
        )
        property_id = result[0]["property_id"]

        # Add observation with price discrepancy
        obs_query = """
        INSERT INTO cross_site_observations (
            property_id, source_site, price, displayed_dom, listing_status
        ) VALUES (?, ?, ?, ?, ?)
        """
        execute_insert(
            obs_query,
            (property_id, "zillow", 475000.0, 15, "for_sale"),
            database_path=temp_db,
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name

        try:
            export_cross_site_comparison_report(output_path, temp_db)

            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                # Check that detail columns exist
                assert "price_discrepancy_details" in reader.fieldnames
                assert "status_discrepancy_details" in reader.fieldnames
                assert "dom_discrepancy_details" in reader.fieldnames
                assert "comparison_notes" in reader.fieldnames

                rows = list(reader)
                row = rows[0]

                # Should have price discrepancy details
                assert row["has_price_discrepancy"] == "True"
                assert row["price_discrepancy_details"]  # Should not be empty

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_export_report_returns_count(self, temp_db, properties_with_observations):
        """Test that export returns correct count of properties."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name

        try:
            count = export_cross_site_comparison_report(output_path, temp_db)

            # Should return number of properties exported
            assert count == 2
            assert isinstance(count, int)

        finally:
            Path(output_path).unlink(missing_ok=True)
