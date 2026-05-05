"""Tests for county verification functionality."""

import csv
import sqlite3
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from marketsentry.county_import import import_county_records_csv
from marketsentry.county_parser import (
    parse_county_record_directory,
    parse_county_record_file,
    parse_county_record_html,
)
from marketsentry.county_verification import (
    find_confirmed_transfers,
    is_ownership_transfer_record,
    is_sale_or_deed_record,
    normalize_county_record_type,
    verify_effective_dom_reset,
)
from marketsentry.county_verification_report import export_county_verification_report
from marketsentry.database import execute_query, execute_update, get_connection, init_db
from marketsentry.normalization import normalize_apn


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name

    # Initialize database
    init_db(db_path)

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sample_watched_property(temp_db):
    """Create a sample watched property for testing."""
    query = """
    INSERT INTO watched_properties (
        first_saved_date, active_watch_status, address, city, zip, apn,
        current_price, effective_dom, displayed_dom,
        listing_churn_count, dom_reset_count, sale_rent_alternation_count
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    execute_update(
        query,
        (
            date.today(),
            1,
            "29867 Corte Savona",
            "Temecula",
            "92591",
            "123-456-789",
            750000.0,
            45,
            30,
            2,
            1,
            0,
        ),
        database_path=temp_db,
    )

    # Get the inserted property_id
    result = execute_query(
        "SELECT property_id FROM watched_properties ORDER BY property_id DESC LIMIT 1",
        database_path=temp_db,
    )

    return result[0]["property_id"]


class TestCountyRecordTypeNormalization:
    """Tests for county record type normalization."""

    def test_normalize_grant_deed(self):
        assert normalize_county_record_type("Grant Deed") == "grant_deed"
        assert normalize_county_record_type("GRANT DEED") == "grant_deed"
        assert normalize_county_record_type("GrantDeed") == "grant_deed"

    def test_normalize_quitclaim_deed(self):
        assert normalize_county_record_type("Quitclaim Deed") == "quitclaim_deed"
        assert normalize_county_record_type("Quit Claim Deed") == "quitclaim_deed"

    def test_normalize_deed_of_trust(self):
        assert normalize_county_record_type("Deed of Trust") == "deed_of_trust"
        assert normalize_county_record_type("Trust Deed") == "deed_of_trust"

    def test_normalize_reconveyance(self):
        assert normalize_county_record_type("Reconveyance") == "reconveyance"

    def test_normalize_lien(self):
        assert normalize_county_record_type("Lien") == "lien"

    def test_normalize_unknown(self):
        assert normalize_county_record_type("Unknown Type") == "unknown"
        assert normalize_county_record_type("") == "unknown"


class TestOwnershipTransferClassification:
    """Tests for ownership transfer classification."""

    def test_grant_deed_is_transfer(self):
        assert is_ownership_transfer_record("Grant Deed")
        assert is_ownership_transfer_record("grant_deed")

    def test_quitclaim_deed_is_transfer(self):
        assert is_ownership_transfer_record("Quitclaim Deed")

    def test_trustee_deed_is_transfer(self):
        assert is_ownership_transfer_record("Trustee Deed")

    def test_warranty_deed_is_transfer(self):
        assert is_ownership_transfer_record("Warranty Deed")

    def test_deed_of_trust_not_transfer(self):
        """Deed of trust is financing, not ownership transfer."""
        assert not is_ownership_transfer_record("Deed of Trust")

    def test_reconveyance_not_transfer(self):
        """Reconveyance is loan payoff, not ownership transfer."""
        assert not is_ownership_transfer_record("Reconveyance")

    def test_lien_not_transfer(self):
        """Lien is encumbrance, not ownership transfer."""
        assert not is_ownership_transfer_record("Lien")

    def test_permit_not_transfer(self):
        """Permit is construction authorization, not ownership transfer."""
        assert not is_ownership_transfer_record("Permit")

    def test_assessment_not_transfer(self):
        """Assessment is valuation, not ownership transfer."""
        assert not is_ownership_transfer_record("Assessment")


class TestCountyParser:
    """Tests for county HTML fixture parsing."""

    def test_parse_assessor_fixture(self):
        fixture_path = Path("tests/fixtures/county/assessor/property_001.html")

        if not fixture_path.exists():
            pytest.skip("Assessor fixture not found")

        result = parse_county_record_file(fixture_path, "assessor")

        assert result.parse_status == "success"
        assert result.county_record is not None
        assert result.county_record.source_type == "assessor"
        assert result.county_record.apn == "123-456-789"
        assert "29867" in result.county_record.address
        assert result.county_record.assessed_value == 725000.0

    def test_parse_recorder_grant_deed_fixture(self):
        fixture_path = Path("tests/fixtures/county/recorder/grant_deed_001.html")

        if not fixture_path.exists():
            pytest.skip("Recorder grant deed fixture not found")

        result = parse_county_record_file(fixture_path, "recorder")

        assert result.parse_status == "success"
        assert result.county_record is not None
        assert result.county_record.source_type == "recorder"
        assert result.county_record.document_number == "2023-0012345"
        assert result.county_record.record_type == "Grant Deed"
        assert result.county_record.sale_price == 710000.0

    def test_parse_recorder_deed_of_trust_fixture(self):
        fixture_path = Path("tests/fixtures/county/recorder/deed_of_trust_001.html")

        if not fixture_path.exists():
            pytest.skip("Recorder deed of trust fixture not found")

        result = parse_county_record_file(fixture_path, "recorder")

        assert result.parse_status in ["success", "partial"]
        assert result.county_record is not None
        assert result.county_record.record_type == "Deed of Trust"
        # Verify deed of trust is NOT classified as ownership transfer
        assert result.county_record.normalized_record_type == "deed_of_trust"

    def test_parse_tax_collector_fixture(self):
        fixture_path = Path("tests/fixtures/county/tax_collector/property_001.html")

        if not fixture_path.exists():
            pytest.skip("Tax collector fixture not found")

        result = parse_county_record_file(fixture_path, "tax_collector")

        assert result.parse_status == "success"
        assert result.county_record is not None
        assert result.county_record.source_type == "tax_collector"

    def test_parse_permit_fixture(self):
        fixture_path = Path("tests/fixtures/county/permits/building_permit_001.html")

        if not fixture_path.exists():
            pytest.skip("Permit fixture not found")

        result = parse_county_record_file(fixture_path, "permit")

        assert result.parse_status == "success"
        assert result.county_record is not None
        assert result.county_record.source_type == "permit"
        assert result.county_record.permit_number == "BP-2024-12345"

    def test_parse_sparse_fixture(self):
        """Test that sparse fixtures parse without failing."""
        fixture_path = Path("tests/fixtures/county/assessor/property_002_sparse.html")

        if not fixture_path.exists():
            pytest.skip("Sparse fixture not found")

        result = parse_county_record_file(fixture_path, "assessor")

        # Should not fail even with missing fields
        assert result.parse_status in ["success", "partial", "failed"]

    def test_parse_invalid_source_type(self):
        html = "<html><body>Test</body></html>"
        result = parse_county_record_html(html, "invalid_type")

        assert result.parse_status == "failed"
        assert len(result.errors) > 0


class TestCountyCSVImport:
    """Tests for county record CSV import."""

    def test_import_county_records_csv_with_property_id(self, temp_db, sample_watched_property):
        """Test CSV import with explicit property_id."""
        # Create CSV file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "source_type",
                    "record_date",
                    "record_type",
                    "property_id",
                    "document_number",
                    "sale_price",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "source_type": "recorder",
                    "record_date": "2023-03-15",
                    "record_type": "Grant Deed",
                    "property_id": sample_watched_property,
                    "document_number": "2023-0012345",
                    "sale_price": "710000",
                }
            )
            csv_path = f.name

        try:
            result = import_county_records_csv(csv_path, temp_db)

            assert result.total_rows_read == 1
            assert result.rows_inserted == 1
            assert result.rows_matched == 1
            assert result.rows_rejected == 0

            # Verify county record was inserted
            query = "SELECT * FROM county_record_observations WHERE property_id = ?"
            records = execute_query(query, (sample_watched_property,), database_path=temp_db)

            assert len(records) == 1
            assert records[0]["source_type"] == "recorder"
            assert records[0]["normalized_record_type"] == "grant_deed"
            assert records[0]["sale_price"] == 710000.0

        finally:
            Path(csv_path).unlink(missing_ok=True)

    def test_import_county_records_csv_with_apn_match(self, temp_db, sample_watched_property):
        """Test CSV import with APN matching."""
        # Create CSV file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["source_type", "record_date", "record_type", "apn", "assessed_value"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "source_type": "assessor",
                    "record_date": "2024-01-01",
                    "record_type": "assessment",
                    "apn": "123-456-789",
                    "assessed_value": "725000",
                }
            )
            csv_path = f.name

        try:
            result = import_county_records_csv(csv_path, temp_db)

            assert result.total_rows_read == 1
            assert result.rows_inserted == 1
            assert result.rows_matched == 1

            # Verify match method
            query = "SELECT * FROM county_record_observations WHERE property_id = ?"
            records = execute_query(query, (sample_watched_property,), database_path=temp_db)

            assert len(records) == 1
            assert records[0]["match_method"] == "apn"

        finally:
            Path(csv_path).unlink(missing_ok=True)

    def test_import_county_records_invalid_source_type(self, temp_db):
        """Test CSV import with invalid source_type."""
        # Create CSV file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["source_type", "record_date", "record_type", "apn"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "source_type": "invalid_type",
                    "record_date": "2024-01-01",
                    "record_type": "test",
                    "apn": "123-456-789",
                }
            )
            csv_path = f.name

        try:
            result = import_county_records_csv(csv_path, temp_db)

            assert result.total_rows_read == 1
            assert result.rows_rejected == 1
            assert len(result.errors) > 0

        finally:
            Path(csv_path).unlink(missing_ok=True)


class TestCountyVerification:
    """Tests for county verification logic."""

    def test_verify_effective_dom_reset_with_transfer(self, temp_db, sample_watched_property):
        """Test verification when transfer exists."""
        # Insert a grant deed county record
        query = """
        INSERT INTO county_record_observations (
            property_id, source_type, record_date, record_type, normalized_record_type,
            document_number, sale_price
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        transfer_date = date.today() - timedelta(days=365)

        execute_update(
            query,
            (
                sample_watched_property,
                "recorder",
                transfer_date,
                "Grant Deed",
                "grant_deed",
                "2023-0012345",
                710000.0,
            ),
            database_path=temp_db,
        )

        # Verify reset
        cycle_start = transfer_date - timedelta(days=30)
        cycle_end = date.today()

        verification_result = verify_effective_dom_reset(
            sample_watched_property, cycle_start, cycle_end, temp_db
        )

        assert verification_result.county_transfer_found is True
        assert verification_result.county_reset_supported is True
        assert verification_result.county_transfer_record_type == "grant_deed"

    def test_verify_effective_dom_reset_no_transfer(self, temp_db, sample_watched_property):
        """Test verification when no transfer exists."""
        cycle_start = date.today() - timedelta(days=365)
        cycle_end = date.today()

        verification_result = verify_effective_dom_reset(
            sample_watched_property, cycle_start, cycle_end, temp_db
        )

        assert verification_result.county_transfer_found is False
        assert verification_result.county_reset_supported is False

    def test_churn_preserved_after_transfer(self, temp_db, sample_watched_property):
        """Test that churn metrics are preserved even when county_reset_supported is true."""
        # Insert a grant deed county record
        query = """
        INSERT INTO county_record_observations (
            property_id, source_type, record_date, record_type, normalized_record_type,
            document_number
        ) VALUES (?, ?, ?, ?, ?, ?)
        """

        transfer_date = date.today() - timedelta(days=365)

        execute_update(
            query,
            (
                sample_watched_property,
                "recorder",
                transfer_date,
                "Grant Deed",
                "grant_deed",
                "2023-0012345",
            ),
            database_path=temp_db,
        )

        # Verify reset
        cycle_start = transfer_date - timedelta(days=30)
        cycle_end = date.today()

        verification_result = verify_effective_dom_reset(
            sample_watched_property, cycle_start, cycle_end, temp_db
        )

        # Verify county_reset_supported is true
        assert verification_result.county_reset_supported is True

        # Get property data
        property_query = "SELECT * FROM watched_properties WHERE property_id = ?"
        property_results = execute_query(
            property_query, (sample_watched_property,), database_path=temp_db
        )

        # Verify churn metrics are NOT erased
        assert property_results[0]["listing_churn_count"] == 2
        assert property_results[0]["dom_reset_count"] == 1
        assert property_results[0]["sale_rent_alternation_count"] == 0


class TestCountyVerificationReport:
    """Tests for county verification report generation."""

    def test_export_county_verification_report(self, temp_db, sample_watched_property):
        """Test county verification report export."""
        # Create temporary output file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as f:
            output_path = f.name

        try:
            row_count = export_county_verification_report(output_path, temp_db)

            assert row_count > 0

            # Verify CSV was created and has correct columns
            with open(output_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                assert len(rows) == row_count

                # Verify required columns
                fieldnames = reader.fieldnames
                assert "property_id" in fieldnames
                assert "recent_churn_index" in fieldnames
                assert "churn_preserved_after_transfer" in fieldnames
                assert "county_transfer_found" in fieldnames
                assert "county_reset_supported" in fieldnames

                # Verify churn_preserved_after_transfer is always True
                for row in rows:
                    assert row["churn_preserved_after_transfer"] == "True"

        finally:
            Path(output_path).unlink(missing_ok=True)


class TestAPNNormalization:
    """Tests for APN normalization."""

    def test_normalize_apn(self):
        assert normalize_apn("123-456-789") == "123456789"
        assert normalize_apn("123 456 789") == "123456789"
        assert normalize_apn("123456789") == "123456789"
