"""Tests for watchlist monitoring snapshots and change detection."""

import csv
import tempfile
import time
from pathlib import Path

import pytest

from marketsentry.database import execute_insert, execute_query, execute_update, init_db, migrate_schema
from marketsentry.monitoring import (
    compare_snapshots,
    create_snapshot_for_property,
    create_snapshots_for_all_watched,
    get_latest_snapshot,
)
from marketsentry.monitoring_report import export_watchlist_monitoring_report
from marketsentry.models import ObservationSnapshot


class TestMonitoringSnapshots:
    """Tests for monitoring snapshot creation and change detection."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        # Initialize database schema
        init_db(db_path)
        migrate_schema(db_path)

        yield db_path

        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def sample_watched_property(self, temp_db):
        """Create a sample watched property for testing."""
        query = """
        INSERT INTO watched_properties (
            first_saved_date, redfin_url, normalized_address, address, city, zip,
            beds, baths, sqft, current_price, displayed_dom, effective_dom,
            effective_dom_delta, quiet_score, vibrancy_score, garage_spaces,
            gas_service, listing_churn_count, dom_reset_count,
            sale_rent_alternation_count, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            "2026-05-01",
            "https://www.redfin.com/CA/Temecula/12345-Test-St-92592/home/123456",
            "12345 TEST ST",
            "12345 Test St",
            "Temecula",
            "92592",
            3,
            2.5,
            2100,
            750000.0,
            15,
            45,
            30,
            8.5,
            2.0,
            2,
            True,
            2,
            1,
            0,
            1,
        )
        execute_insert(query, params, database_path=temp_db)

        # Get property_id
        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE address = ?",
            ("12345 Test St",),
            database_path=temp_db,
        )
        return result[0]["property_id"]

    def test_create_snapshot_for_single_property(self, temp_db, sample_watched_property):
        """Test creating a snapshot for a single watched property."""
        result = create_snapshot_for_property(sample_watched_property, temp_db)

        assert result.snapshot_created is True
        assert result.snapshot_id is not None
        assert result.snapshot_skipped is False
        assert result.property_id == sample_watched_property

    def test_get_latest_snapshot(self, temp_db, sample_watched_property):
        """Test retrieving the latest snapshot."""
        # Create first snapshot
        result1 = create_snapshot_for_property(sample_watched_property, temp_db)
        assert result1.snapshot_created is True

        # Get latest snapshot
        latest = get_latest_snapshot(sample_watched_property, temp_db)

        assert latest is not None
        assert latest.snapshot_id == result1.snapshot_id
        assert latest.property_id == sample_watched_property
        assert latest.price == 750000.0

    def test_snapshot_creation_for_all_watched(self, temp_db, sample_watched_property):
        """Test creating snapshots for all watched properties."""
        # Add a second watched property
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, city, zip, current_price, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        execute_insert(
            query,
            ("2026-05-01", "99999 Second St", "Temecula", "92592", 500000.0, 1),
            database_path=temp_db,
        )

        # Create snapshots for all
        result = create_snapshots_for_all_watched(temp_db)

        assert result.properties_scanned == 2
        assert result.snapshots_created == 2
        assert result.snapshots_skipped == 0

    def test_snapshot_creation_with_sparse_data(self, temp_db):
        """Test creating a snapshot when property data is sparse."""
        # Create watched property with minimal data
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, city, zip, active_watch_status
        ) VALUES (?, ?, ?, ?, ?)
        """
        execute_insert(
            query,
            ("2026-05-01", "11111 Sparse St", "Temecula", "92592", 1),
            database_path=temp_db,
        )

        # Get property_id
        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE address = ?",
            ("11111 Sparse St",),
            database_path=temp_db,
        )
        property_id = result[0]["property_id"]

        # Create snapshot
        snapshot_result = create_snapshot_for_property(property_id, temp_db)

        assert snapshot_result.snapshot_created is True
        assert snapshot_result.snapshot_id is not None

        # Verify snapshot has null values for missing data
        latest = get_latest_snapshot(property_id, temp_db)
        assert latest.price is None
        assert latest.quiet_score is None

    def test_price_change_detection(self, temp_db, sample_watched_property):
        """Test detecting price changes between snapshots."""
        # Create initial snapshot
        result1 = create_snapshot_for_property(sample_watched_property, temp_db)
        assert result1.snapshot_created is True

        # Update property price
        execute_update(
            "UPDATE watched_properties SET current_price = ? WHERE property_id = ?",
            (725000.0, sample_watched_property),
            database_path=temp_db,
        )

        # Wait a moment to ensure different timestamp
        time.sleep(0.1)

        # Create second snapshot
        result2 = create_snapshot_for_property(sample_watched_property, temp_db)

        assert result2.snapshot_created is True
        assert result2.changes_detected is not None
        assert result2.changes_detected.price_changed is True
        assert result2.changes_detected.price_decreased is True
        assert result2.changes_detected.price_change_amount == -25000.0

    def test_status_change_detection(self, temp_db, sample_watched_property):
        """Test detecting listing status changes."""
        # Create initial snapshot
        create_snapshot_for_property(sample_watched_property, temp_db)

        # Wait briefly
        time.sleep(0.1)

        # Manually create a second snapshot with different status
        # (simulating a status change)
        query = """
        INSERT INTO property_observation_snapshots (
            property_id, snapshot_date, source_site, listing_status, price
        ) VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?)
        """
        execute_insert(
            query,
            (sample_watched_property, "redfin", "pending", 750000.0),
            database_path=temp_db,
        )

        # Get latest two snapshots
        query_snaps = """
        SELECT * FROM property_observation_snapshots
        WHERE property_id = ?
        ORDER BY snapshot_date DESC
        LIMIT 2
        """
        results = execute_query(query_snaps, (sample_watched_property,), database_path=temp_db)

        current = ObservationSnapshot(**dict(results[0]))
        previous = ObservationSnapshot(**dict(results[1]))

        # Compare
        changes = compare_snapshots(previous, current)

        assert changes.status_changed is True
        assert changes.has_changes is True

    def test_effective_dom_change_detection(self, temp_db, sample_watched_property):
        """Test detecting Effective DOM changes."""
        # Create initial snapshot
        create_snapshot_for_property(sample_watched_property, temp_db)

        # Update effective DOM
        execute_update(
            "UPDATE watched_properties SET effective_dom = ? WHERE property_id = ?",
            (60, sample_watched_property),
            database_path=temp_db,
        )

        time.sleep(0.1)

        # Create second snapshot
        result = create_snapshot_for_property(sample_watched_property, temp_db)

        assert result.changes_detected.effective_dom_changed is True

    def test_quiet_vibrancy_change_detection(self, temp_db, sample_watched_property):
        """Test detecting Quiet/Vibrancy score changes."""
        # Create initial snapshot
        create_snapshot_for_property(sample_watched_property, temp_db)

        # Update Quiet score significantly (>= 0.5 threshold)
        execute_update(
            "UPDATE watched_properties SET quiet_score = ? WHERE property_id = ?",
            (7.8, sample_watched_property),  # Changed from 8.5 to 7.8 (delta 0.7)
            database_path=temp_db,
        )

        time.sleep(0.1)

        # Create second snapshot
        result = create_snapshot_for_property(sample_watched_property, temp_db)

        assert result.changes_detected.quiet_score_changed is True

    def test_discrepancy_flag_change_detection(self, temp_db, sample_watched_property):
        """Test detecting discrepancy flag changes."""
        # Create initial snapshot (no discrepancies)
        create_snapshot_for_property(sample_watched_property, temp_db)

        # Manually create cross-site observation with discrepancy
        # First, get property and create observation with different price
        query_obs = """
        INSERT INTO cross_site_observations (
            property_id, source_site, source_url, price, observed_at
        ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        execute_insert(
            query_obs,
            (sample_watched_property, "zillow", "https://zillow.com/test", 700000.0),
            database_path=temp_db,
        )

        time.sleep(0.1)

        # Create second snapshot (should detect cross-site discrepancy)
        result = create_snapshot_for_property(sample_watched_property, temp_db)

        # The second snapshot should have price_discrepancy_flag = True
        latest = get_latest_snapshot(sample_watched_property, temp_db)
        assert latest.price_discrepancy_flag is True

    def test_no_material_change_behavior(self, temp_db, sample_watched_property):
        """Test that no material changes are correctly identified."""
        # Create initial snapshot
        result1 = create_snapshot_for_property(sample_watched_property, temp_db)
        assert result1.snapshot_created is True

        time.sleep(0.1)

        # Create second snapshot without changing any material fields
        result2 = create_snapshot_for_property(sample_watched_property, temp_db)

        # Should be skipped due to no material changes on same day
        assert result2.snapshot_skipped is True
        assert result2.skip_reason == "No material changes since last snapshot today"

    def test_idempotency_duplicate_handling(self, temp_db, sample_watched_property):
        """Test idempotency: same-day duplicates without material changes are skipped."""
        # Create first snapshot
        result1 = create_snapshot_for_property(sample_watched_property, temp_db)
        assert result1.snapshot_created is True

        # Try creating second snapshot on same day without changes
        result2 = create_snapshot_for_property(sample_watched_property, temp_db)

        assert result2.snapshot_skipped is True
        assert "No material changes" in result2.skip_reason

    def test_idempotency_with_material_change(self, temp_db, sample_watched_property):
        """Test that material changes override idempotency."""
        # Create first snapshot
        result1 = create_snapshot_for_property(sample_watched_property, temp_db)
        assert result1.snapshot_created is True

        # Make a material change (price)
        execute_update(
            "UPDATE watched_properties SET current_price = ? WHERE property_id = ?",
            (800000.0, sample_watched_property),
            database_path=temp_db,
        )

        time.sleep(0.1)

        # Try creating second snapshot on same day with material change
        result2 = create_snapshot_for_property(sample_watched_property, temp_db)

        assert result2.snapshot_created is True
        assert result2.snapshot_skipped is False

    def test_monitoring_report_csv_columns(self, temp_db, sample_watched_property):
        """Test that monitoring report CSV has all required columns."""
        # Create a snapshot first
        create_snapshot_for_property(sample_watched_property, temp_db)

        # Export report
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name

        try:
            export_watchlist_monitoring_report(output_path, temp_db)

            # Read CSV and check columns
            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames

                # Check for required columns
                required_columns = [
                    "property_id",
                    "watch_priority",
                    "active_watch_status",
                    "address",
                    "city",
                    "zip",
                    "redfin_url",
                    "current_price",
                    "previous_price",
                    "price_change",
                    "price_change_direction",
                    "listing_status",
                    "previous_listing_status",
                    "status_changed",
                    "displayed_dom",
                    "previous_displayed_dom",
                    "effective_dom",
                    "previous_effective_dom",
                    "effective_dom_delta",
                    "quiet_score",
                    "vibrancy_score",
                    "quiet_gatekeeper_result",
                    "garage_spaces",
                    "gas_service",
                    "listing_churn_count",
                    "dom_reset_count",
                    "sale_rent_alternation_count",
                    "price_discrepancy_flag",
                    "status_discrepancy_flag",
                    "dom_discrepancy_flag",
                    "cross_site_confidence_score",
                    "change_summary",
                    "warning_flags",
                    "positive_flags",
                    "user_notes",
                    "last_checked_date",
                    "snapshot_date",
                ]

                for col in required_columns:
                    assert col in fieldnames, f"Missing column: {col}"

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_monitoring_report_row_count(self, temp_db, sample_watched_property):
        """Test that monitoring report has correct row count."""
        # Create snapshot for property
        create_snapshot_for_property(sample_watched_property, temp_db)

        # Add second property
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, city, zip, current_price, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        property_id_2 = execute_insert(
            query,
            ("2026-05-01", "22222 Second St", "Temecula", "92592", 600000.0, 1),
            database_path=temp_db,
        )

        # Create snapshot for second property
        create_snapshot_for_property(property_id_2, temp_db)

        # Export report
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name

        try:
            row_count = export_watchlist_monitoring_report(output_path, temp_db)

            # Should have 2 rows (2 active watched properties)
            assert row_count == 2

            # Verify by reading CSV
            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 2

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_snapshot_for_inactive_property(self, temp_db):
        """Test that snapshots are not created for inactive properties."""
        # Create inactive property
        query = """
        INSERT INTO watched_properties (
            first_saved_date, address, city, zip, current_price, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        property_id = execute_insert(
            query,
            ("2026-05-01", "33333 Inactive St", "Temecula", "92592", 500000.0, 0),
            database_path=temp_db,
        )

        # Try to create snapshot
        result = create_snapshot_for_property(property_id, temp_db)

        assert result.snapshot_skipped is True
        assert "inactive" in result.skip_reason.lower()

    def test_compare_snapshots_with_none_previous(self, temp_db, sample_watched_property):
        """Test comparing when previous snapshot is None (initial snapshot)."""
        # Create a snapshot
        snapshot_result = create_snapshot_for_property(sample_watched_property, temp_db)
        latest = get_latest_snapshot(sample_watched_property, temp_db)

        # Compare with None previous
        changes = compare_snapshots(None, latest)

        assert changes.has_changes is False
        assert changes.change_summary == "Initial snapshot"

    def test_multiple_snapshots_over_time(self, temp_db, sample_watched_property):
        """Test creating multiple snapshots and tracking changes over time."""
        # Create initial snapshot
        result1 = create_snapshot_for_property(sample_watched_property, temp_db)
        assert result1.snapshot_created is True

        # Change price
        execute_update(
            "UPDATE watched_properties SET current_price = ? WHERE property_id = ?",
            (725000.0, sample_watched_property),
            database_path=temp_db,
        )
        time.sleep(0.1)

        # Create second snapshot
        result2 = create_snapshot_for_property(sample_watched_property, temp_db)
        assert result2.snapshot_created is True
        assert result2.changes_detected.price_decreased is True

        # Change price again
        execute_update(
            "UPDATE watched_properties SET current_price = ? WHERE property_id = ?",
            (750000.0, sample_watched_property),
            database_path=temp_db,
        )
        time.sleep(0.1)

        # Create third snapshot
        result3 = create_snapshot_for_property(sample_watched_property, temp_db)
        assert result3.snapshot_created is True
        assert result3.changes_detected.price_increased is True

        # Verify we have 3 snapshots
        query = """
        SELECT COUNT(*) as count
        FROM property_observation_snapshots
        WHERE property_id = ?
        """
        count_result = execute_query(query, (sample_watched_property,), database_path=temp_db)
        assert count_result[0]["count"] == 3
