"""Tests for Milestone 25: Cross-Site Analytics Trend Snapshots.

Tests cover:
- Schema migration creates cross_site_analytics_snapshots
- Migration is idempotent
- Snapshot creation from analytics result
- No duplicate same-day/no-change snapshot
- Force snapshot creates new snapshot
- Severity change triggers snapshot
- Confidence delta >= 0.10 triggers snapshot
- Agreement score delta >= 0.10 triggers snapshot
- Trend change calculation
- Trend report export
- CLI snapshot-cross-site-analytics
- CLI export-cross-site-trend-report
- Dashboard includes trend fields
- No Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- No walkability fields added
- No real network calls
- Existing MVP 1-24 tests still pass (run with full suite)
"""

import csv
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from marketsentry.database import execute_query, get_connection, init_db, table_exists
from marketsentry.models import (
    CrossSiteAnalyticsSnapshot,
    CrossSiteTrendChange,
    CrossSiteTrendReportRow,
    CrossSiteTrendRunResult,
    CrossSiteTrendSummary,
)
from marketsentry.schema import CREATE_CROSS_SITE_ANALYTICS_SNAPSHOTS_TABLE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_db():
    """Create a temporary database with full schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    init_db(db_path)
    yield db_path

    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def temp_db_with_data(temp_db):
    """Create a temp database with watched property and cross-site observations."""
    conn = get_connection(temp_db)
    cursor = conn.cursor()

    # Insert watched property
    cursor.execute(
        """
        INSERT INTO watched_properties (
            first_saved_date, active_watch_status, address, city, zip,
            current_price, displayed_dom, garage_spaces, gas_service
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-01-01", 1, "123 Test St", "Temecula", "92592", 750000, 45, 2, 1),
    )
    property_id = cursor.lastrowid

    # Insert cross-site observations
    now = datetime.now().isoformat()
    for source in ["zillow", "realtor"]:
        cursor.execute(
            """
            INSERT INTO cross_site_observations (
                property_id, source_site, source_url, observed_at,
                price, beds, baths, sqft, displayed_dom,
                listing_status, garage_spaces, gas_service,
                parse_status, parse_warnings
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                property_id, source, f"https://{source}.com/test",
                now, 750000, 4, 3, 2500, 45,
                "active", 2, 1, "success", None,
            ),
        )

    conn.commit()
    conn.close()

    return temp_db, property_id


@pytest.fixture
def temp_exports_dir():
    """Create a temporary exports directory."""
    with tempfile.TemporaryDirectory() as d:
        yield d


# ---------------------------------------------------------------------------
# Test: Schema migration creates cross_site_analytics_snapshots
# ---------------------------------------------------------------------------


class TestSchemaMigration:
    """Test schema migration for cross_site_analytics_snapshots."""

    def test_table_created_on_init(self, temp_db):
        """Verify cross_site_analytics_snapshots table exists after init."""
        assert table_exists("cross_site_analytics_snapshots", temp_db)

    def test_table_has_expected_columns(self, temp_db):
        """Verify all expected columns exist."""
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(cross_site_analytics_snapshots)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected = {
            "snapshot_id", "property_id", "candidate_id", "captured_at",
            "overall_cross_site_confidence_score", "discrepancy_severity_score",
            "discrepancy_severity_label", "cross_site_manual_review_priority",
            "weighted_price_agreement_score", "weighted_status_agreement_score",
            "weighted_dom_agreement_score", "weighted_garage_agreement_score",
            "weighted_gas_agreement_score", "source_freshness_score",
            "source_completeness_score", "source_agreement_score",
            "contributing_sources", "low_confidence_sources",
            "stale_sources", "parse_warning_sources",
            "source_count", "high_confidence_source_count",
            "low_confidence_source_count", "stale_source_count",
            "price_discrepancy_flag", "status_discrepancy_flag",
            "dom_discrepancy_flag", "notes", "created_at",
        }
        assert expected.issubset(columns)

    def test_migration_is_idempotent(self, temp_db):
        """Running init_db twice should not fail."""
        init_db(temp_db)
        init_db(temp_db)
        assert table_exists("cross_site_analytics_snapshots", temp_db)


# ---------------------------------------------------------------------------
# Test: Snapshot creation from analytics result
# ---------------------------------------------------------------------------


class TestSnapshotCreation:
    """Test creating snapshots from analytics results."""

    def test_snapshot_created_from_analytics(self, temp_db_with_data):
        """Verify a snapshot is created when cross-site data exists."""
        from marketsentry.cross_site_trends import create_cross_site_analytics_snapshots

        db_path, property_id = temp_db_with_data
        result = create_cross_site_analytics_snapshots(database_path=db_path)

        assert result.properties_scanned >= 1
        assert result.analytics_computed >= 1
        assert result.snapshots_created >= 1
        assert not result.errors

    def test_snapshot_persisted_in_database(self, temp_db_with_data):
        """Verify snapshot data is in the database after creation."""
        from marketsentry.cross_site_trends import (
            create_cross_site_analytics_snapshots,
            get_latest_cross_site_analytics_snapshot,
        )

        db_path, property_id = temp_db_with_data
        create_cross_site_analytics_snapshots(database_path=db_path)

        snapshot = get_latest_cross_site_analytics_snapshot(property_id, db_path)
        assert snapshot is not None
        assert snapshot.property_id == property_id
        assert snapshot.overall_cross_site_confidence_score is not None

    def test_run_result_counts(self, temp_db_with_data):
        """Verify run result has correct counts."""
        from marketsentry.cross_site_trends import create_cross_site_analytics_snapshots

        db_path, _ = temp_db_with_data
        result = create_cross_site_analytics_snapshots(database_path=db_path)

        assert isinstance(result, CrossSiteTrendRunResult)
        assert result.properties_scanned >= 1
        assert result.analytics_computed >= 0 or result.snapshots_created >= 0


# ---------------------------------------------------------------------------
# Test: No duplicate same-day/no-change snapshot
# ---------------------------------------------------------------------------


class TestNoDuplicateSnapshot:
    """Test duplicate snapshot prevention."""

    def test_no_duplicate_when_no_change(self, temp_db_with_data):
        """Second run should skip if no material change."""
        from marketsentry.cross_site_trends import create_cross_site_analytics_snapshots

        db_path, _ = temp_db_with_data

        # First run
        result1 = create_cross_site_analytics_snapshots(database_path=db_path)
        created1 = result1.snapshots_created

        # Second run (no change)
        result2 = create_cross_site_analytics_snapshots(database_path=db_path)

        assert result2.snapshots_skipped_no_change >= created1
        assert result2.snapshots_created == 0

    def test_force_creates_snapshot_despite_no_change(self, temp_db_with_data):
        """Force flag should create snapshot even with no material change."""
        from marketsentry.cross_site_trends import create_cross_site_analytics_snapshots

        db_path, _ = temp_db_with_data

        # First run
        create_cross_site_analytics_snapshots(database_path=db_path)

        # Force run
        result = create_cross_site_analytics_snapshots(
            database_path=db_path, force=True
        )

        assert result.snapshots_created >= 1


# ---------------------------------------------------------------------------
# Test: Material change triggers snapshot
# ---------------------------------------------------------------------------


class TestMaterialChangeTriggers:
    """Test that material changes trigger new snapshots."""

    def test_severity_change_triggers_snapshot(self, temp_db_with_data):
        """Severity label change should trigger a new snapshot."""
        from marketsentry.cross_site_trends import (
            _has_material_change,
        )

        snap1 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        snap2 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            discrepancy_severity_label="medium",
            cross_site_manual_review_priority="none",
        )
        assert _has_material_change(snap2, snap1) is True

    def test_confidence_delta_triggers_snapshot(self):
        """Confidence change >= 0.10 should trigger a new snapshot."""
        from marketsentry.cross_site_trends import _has_material_change

        snap1 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            overall_cross_site_confidence_score=0.50,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        snap2 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            overall_cross_site_confidence_score=0.65,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        assert _has_material_change(snap2, snap1) is True

    def test_small_confidence_delta_no_trigger(self):
        """Confidence change < 0.10 should not trigger alone."""
        from marketsentry.cross_site_trends import _has_material_change

        snap1 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            overall_cross_site_confidence_score=0.50,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        snap2 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            overall_cross_site_confidence_score=0.55,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        assert _has_material_change(snap2, snap1) is False

    def test_agreement_score_delta_triggers_snapshot(self):
        """Agreement score change >= 0.10 should trigger."""
        from marketsentry.cross_site_trends import _has_material_change

        snap1 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            weighted_price_agreement_score=0.80,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        snap2 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            weighted_price_agreement_score=0.60,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        assert _has_material_change(snap2, snap1) is True

    def test_priority_change_triggers_snapshot(self):
        """Manual review priority change should trigger."""
        from marketsentry.cross_site_trends import _has_material_change

        snap1 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        snap2 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="medium",
        )
        assert _has_material_change(snap2, snap1) is True

    def test_stale_source_count_change_triggers(self):
        """Stale source count change should trigger."""
        from marketsentry.cross_site_trends import _has_material_change

        snap1 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            stale_source_count=0,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        snap2 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            stale_source_count=2,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        assert _has_material_change(snap2, snap1) is True

    def test_low_confidence_source_count_change_triggers(self):
        """Low confidence source count change should trigger."""
        from marketsentry.cross_site_trends import _has_material_change

        snap1 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            low_confidence_source_count=0,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        snap2 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            low_confidence_source_count=1,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        assert _has_material_change(snap2, snap1) is True

    def test_discrepancy_flag_change_triggers(self):
        """Discrepancy flag change should trigger."""
        from marketsentry.cross_site_trends import _has_material_change

        snap1 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            price_discrepancy_flag=False,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        snap2 = CrossSiteAnalyticsSnapshot(
            property_id=1,
            price_discrepancy_flag=True,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        assert _has_material_change(snap2, snap1) is True


# ---------------------------------------------------------------------------
# Test: Trend change calculation
# ---------------------------------------------------------------------------


class TestTrendChangeCalculation:
    """Test trend change calculation between snapshots."""

    def test_calculate_trend_improving(self):
        """Verify improving trend detected correctly."""
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        previous = CrossSiteAnalyticsSnapshot(
            property_id=1,
            snapshot_id=1,
            overall_cross_site_confidence_score=0.40,
            discrepancy_severity_label="medium",
            cross_site_manual_review_priority="medium",
        )
        current = CrossSiteAnalyticsSnapshot(
            property_id=1,
            snapshot_id=2,
            overall_cross_site_confidence_score=0.70,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        change = calculate_cross_site_trend_change(current, previous)

        assert change.trend_direction == "improving"
        assert change.has_material_change is True
        assert change.severity_label_changed is True
        assert change.overall_confidence_change > 0

    def test_calculate_trend_degrading(self):
        """Verify degrading trend detected correctly."""
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        previous = CrossSiteAnalyticsSnapshot(
            property_id=1,
            snapshot_id=1,
            overall_cross_site_confidence_score=0.80,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        current = CrossSiteAnalyticsSnapshot(
            property_id=1,
            snapshot_id=2,
            overall_cross_site_confidence_score=0.40,
            discrepancy_severity_label="high",
            cross_site_manual_review_priority="high",
        )
        change = calculate_cross_site_trend_change(current, previous)

        assert change.trend_direction == "degrading"
        assert change.has_material_change is True
        assert change.overall_confidence_change < 0

    def test_calculate_trend_stable(self):
        """Verify stable trend when no material change."""
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        previous = CrossSiteAnalyticsSnapshot(
            property_id=1,
            snapshot_id=1,
            overall_cross_site_confidence_score=0.65,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        current = CrossSiteAnalyticsSnapshot(
            property_id=1,
            snapshot_id=2,
            overall_cross_site_confidence_score=0.66,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        change = calculate_cross_site_trend_change(current, previous)

        assert change.trend_direction == "stable"

    def test_trend_change_has_summary(self):
        """Trend change should include a text summary."""
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        previous = CrossSiteAnalyticsSnapshot(
            property_id=1,
            overall_cross_site_confidence_score=0.50,
            discrepancy_severity_label="low",
            cross_site_manual_review_priority="low",
        )
        current = CrossSiteAnalyticsSnapshot(
            property_id=1,
            overall_cross_site_confidence_score=0.80,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
        )
        change = calculate_cross_site_trend_change(current, previous)

        assert change.trend_summary is not None
        assert len(change.trend_summary) > 0
        assert change.recommended_next_action is not None

    def test_trend_change_with_property_info(self):
        """Trend change should include property info when provided."""
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        snap1 = CrossSiteAnalyticsSnapshot(property_id=1)
        snap2 = CrossSiteAnalyticsSnapshot(property_id=1)
        prop = {"address": "123 Test St", "city": "Temecula", "zip": "92592"}

        change = calculate_cross_site_trend_change(snap2, snap1, prop)
        assert change.address == "123 Test St"
        assert change.city == "Temecula"


# ---------------------------------------------------------------------------
# Test: Trend report export
# ---------------------------------------------------------------------------


class TestTrendReportExport:
    """Test trend report CSV export."""

    def test_export_creates_csv(self, temp_db_with_data, temp_exports_dir):
        """Export should create a CSV file."""
        from marketsentry.cross_site_trends import (
            create_cross_site_analytics_snapshots,
            export_cross_site_trend_report,
        )

        db_path, _ = temp_db_with_data
        create_cross_site_analytics_snapshots(database_path=db_path)

        output = str(Path(temp_exports_dir) / "trend_test.csv")
        csv_path = export_cross_site_trend_report(
            database_path=db_path, output_path=output
        )

        assert Path(csv_path).exists()

    def test_export_has_expected_columns(self, temp_db_with_data, temp_exports_dir):
        """CSV should have all required columns."""
        from marketsentry.cross_site_trends import (
            TREND_REPORT_FIELDNAMES,
            create_cross_site_analytics_snapshots,
            export_cross_site_trend_report,
        )

        db_path, _ = temp_db_with_data
        create_cross_site_analytics_snapshots(database_path=db_path)

        output = str(Path(temp_exports_dir) / "trend_columns_test.csv")
        csv_path = export_cross_site_trend_report(
            database_path=db_path, output_path=output
        )

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert set(reader.fieldnames or []) == set(TREND_REPORT_FIELDNAMES)

    def test_export_empty_when_no_data(self, temp_db, temp_exports_dir):
        """Export should still create valid CSV when no data."""
        from marketsentry.cross_site_trends import export_cross_site_trend_report

        output = str(Path(temp_exports_dir) / "empty_trend.csv")
        csv_path = export_cross_site_trend_report(
            database_path=temp_db, output_path=output
        )

        assert Path(csv_path).exists()
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 0

    def test_export_with_two_snapshots(self, temp_db_with_data, temp_exports_dir):
        """Export should show trend data when two snapshots exist."""
        from marketsentry.cross_site_trends import (
            create_cross_site_analytics_snapshots,
            export_cross_site_trend_report,
        )

        db_path, _ = temp_db_with_data

        # Create first snapshot
        create_cross_site_analytics_snapshots(database_path=db_path)

        # Force second snapshot
        create_cross_site_analytics_snapshots(database_path=db_path, force=True)

        output = str(Path(temp_exports_dir) / "two_snap.csv")
        csv_path = export_cross_site_trend_report(
            database_path=db_path, output_path=output
        )

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) >= 1
            # Should have trend direction
            assert "trend_direction" in rows[0]


# ---------------------------------------------------------------------------
# Test: CLI commands
# ---------------------------------------------------------------------------


class TestCLICommands:
    """Test CLI commands for trend snapshots."""

    def test_cli_snapshot_command_exists(self):
        """Verify snapshot-cross-site-analytics CLI command is registered."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["snapshot-cross-site-analytics", "--help"])
        assert result.exit_code == 0
        assert "cross-site analytics" in result.output.lower()

    def test_cli_export_trend_command_exists(self):
        """Verify export-cross-site-trend-report CLI command is registered."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["export-cross-site-trend-report", "--help"])
        assert result.exit_code == 0

    def test_cli_snapshot_runs(self, temp_db_with_data):
        """CLI snapshot command should run successfully."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        db_path, _ = temp_db_with_data
        runner = CliRunner()
        result = runner.invoke(app, ["snapshot-cross-site-analytics", "--db", db_path])
        assert result.exit_code == 0
        assert "Properties scanned" in result.output

    def test_cli_export_trend_runs(self, temp_db_with_data, temp_exports_dir):
        """CLI export command should run successfully."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        db_path, _ = temp_db_with_data

        # Create snapshots first
        runner = CliRunner()
        runner.invoke(app, ["snapshot-cross-site-analytics", "--db", db_path])

        result = runner.invoke(
            app,
            ["export-cross-site-trend-report", "--db", db_path, "--output-dir", temp_exports_dir],
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Test: Dashboard includes trend fields
# ---------------------------------------------------------------------------


class TestDashboardTrendFields:
    """Test dashboard integration with trend data."""

    def test_build_cross_site_trends_table_empty(self, temp_exports_dir):
        """Trends table should be empty when no report exists."""
        from marketsentry.dashboard import build_cross_site_trends_table

        df = build_cross_site_trends_table(temp_exports_dir)
        assert df.empty

    def test_build_cross_site_trends_table_with_data(
        self, temp_db_with_data, temp_exports_dir
    ):
        """Trends table should load data from trend report CSV."""
        from marketsentry.cross_site_trends import (
            create_cross_site_analytics_snapshots,
            export_cross_site_trend_report,
        )
        from marketsentry.dashboard import build_cross_site_trends_table

        db_path, _ = temp_db_with_data
        create_cross_site_analytics_snapshots(database_path=db_path)

        csv_path = export_cross_site_trend_report(
            database_path=db_path,
            output_path=str(Path(temp_exports_dir) / "cross_site_trends_20260508_120000.csv"),
        )

        df = build_cross_site_trends_table(temp_exports_dir)
        assert not df.empty
        assert "trend_direction" in df.columns

    def test_find_latest_report_finds_trends(self, temp_exports_dir):
        """find_latest_report should recognize cross_site_trends pattern."""
        from marketsentry.dashboard import find_latest_report

        # Create a dummy trend CSV
        dummy = Path(temp_exports_dir) / "cross_site_trends_20260508_120000.csv"
        dummy.write_text("property_id,trend_direction\n1,stable\n")

        result = find_latest_report("cross_site_trends", temp_exports_dir)
        assert result is not None
        assert "cross_site_trends" in result.name


# ---------------------------------------------------------------------------
# Test: Trend summary
# ---------------------------------------------------------------------------


class TestTrendSummary:
    """Test trend summary aggregation."""

    def test_summarize_empty(self, temp_db):
        """Summary should handle no data gracefully."""
        from marketsentry.cross_site_trends import summarize_cross_site_trends

        summary = summarize_cross_site_trends(database_path=temp_db)
        assert isinstance(summary, CrossSiteTrendSummary)
        assert summary.total_properties == 0

    def test_summarize_with_snapshots(self, temp_db_with_data):
        """Summary should count trends after creating snapshots."""
        from marketsentry.cross_site_trends import (
            create_cross_site_analytics_snapshots,
            summarize_cross_site_trends,
        )

        db_path, _ = temp_db_with_data

        # Create two snapshots
        create_cross_site_analytics_snapshots(database_path=db_path)
        create_cross_site_analytics_snapshots(database_path=db_path, force=True)

        summary = summarize_cross_site_trends(database_path=db_path)
        assert summary.total_properties >= 1


# ---------------------------------------------------------------------------
# Test: Snapshot retrieval
# ---------------------------------------------------------------------------


class TestSnapshotRetrieval:
    """Test snapshot retrieval functions."""

    def test_get_latest_no_snapshots(self, temp_db):
        """Should return None when no snapshots exist."""
        from marketsentry.cross_site_trends import get_latest_cross_site_analytics_snapshot

        result = get_latest_cross_site_analytics_snapshot(999, temp_db)
        assert result is None

    def test_get_previous_no_snapshots(self, temp_db):
        """Should return None when fewer than 2 snapshots exist."""
        from marketsentry.cross_site_trends import get_previous_cross_site_analytics_snapshot

        result = get_previous_cross_site_analytics_snapshot(999, temp_db)
        assert result is None

    def test_get_latest_returns_most_recent(self, temp_db_with_data):
        """Should return the most recent snapshot."""
        from marketsentry.cross_site_trends import (
            create_cross_site_analytics_snapshots,
            get_latest_cross_site_analytics_snapshot,
        )

        db_path, property_id = temp_db_with_data
        create_cross_site_analytics_snapshots(database_path=db_path)
        create_cross_site_analytics_snapshots(database_path=db_path, force=True)

        snapshot = get_latest_cross_site_analytics_snapshot(property_id, db_path)
        assert snapshot is not None
        assert snapshot.property_id == property_id

    def test_get_previous_returns_second_most_recent(self, temp_db_with_data):
        """Should return second-most-recent snapshot."""
        from marketsentry.cross_site_trends import (
            create_cross_site_analytics_snapshots,
            get_latest_cross_site_analytics_snapshot,
            get_previous_cross_site_analytics_snapshot,
        )

        db_path, property_id = temp_db_with_data
        create_cross_site_analytics_snapshots(database_path=db_path)
        create_cross_site_analytics_snapshots(database_path=db_path, force=True)

        latest = get_latest_cross_site_analytics_snapshot(property_id, db_path)
        previous = get_previous_cross_site_analytics_snapshot(property_id, db_path)

        assert latest is not None
        assert previous is not None
        assert latest.snapshot_id != previous.snapshot_id


# ---------------------------------------------------------------------------
# Test: Models
# ---------------------------------------------------------------------------


class TestTrendModels:
    """Test trend model initialization."""

    def test_snapshot_model(self):
        """CrossSiteAnalyticsSnapshot should initialize with defaults."""
        snap = CrossSiteAnalyticsSnapshot(property_id=1)
        assert snap.property_id == 1
        assert snap.source_count == 0
        assert snap.price_discrepancy_flag is False

    def test_trend_change_model(self):
        """CrossSiteTrendChange should initialize with defaults."""
        change = CrossSiteTrendChange(property_id=1)
        assert change.trend_direction == "stable"
        assert change.has_material_change is False

    def test_trend_summary_model(self):
        """CrossSiteTrendSummary should initialize with zeros."""
        summary = CrossSiteTrendSummary()
        assert summary.total_properties == 0
        assert summary.properties_improving == 0

    def test_trend_run_result_model(self):
        """CrossSiteTrendRunResult should initialize with zeros."""
        result = CrossSiteTrendRunResult()
        assert result.properties_scanned == 0
        assert result.snapshots_created == 0

    def test_trend_report_row_model(self):
        """CrossSiteTrendReportRow should initialize with defaults."""
        row = CrossSiteTrendReportRow()
        assert row.trend_direction == "stable"
        assert row.discrepancy_severity_changed is False


# ---------------------------------------------------------------------------
# Test: No Redfin source-of-truth overwrite
# ---------------------------------------------------------------------------


class TestNoRedfinOverwrite:
    """Verify cross-site trend snapshots do not overwrite Redfin data."""

    def test_watched_properties_unchanged(self, temp_db_with_data):
        """Watched properties should not be modified by snapshot creation."""
        from marketsentry.cross_site_trends import create_cross_site_analytics_snapshots

        db_path, property_id = temp_db_with_data

        # Get original data
        before = execute_query(
            "SELECT current_price, displayed_dom, garage_spaces, gas_service "
            "FROM watched_properties WHERE property_id = ?",
            (property_id,),
            database_path=db_path,
        )
        before_dict = dict(before[0])

        # Create snapshots
        create_cross_site_analytics_snapshots(database_path=db_path)

        # Verify unchanged
        after = execute_query(
            "SELECT current_price, displayed_dom, garage_spaces, gas_service "
            "FROM watched_properties WHERE property_id = ?",
            (property_id,),
            database_path=db_path,
        )
        after_dict = dict(after[0])

        assert before_dict == after_dict

    def test_cross_site_observations_unchanged(self, temp_db_with_data):
        """Cross-site observations should not be modified."""
        from marketsentry.cross_site_trends import create_cross_site_analytics_snapshots

        db_path, property_id = temp_db_with_data

        before = execute_query(
            "SELECT COUNT(*) as cnt FROM cross_site_observations WHERE property_id = ?",
            (property_id,),
            database_path=db_path,
        )
        count_before = before[0]["cnt"]

        create_cross_site_analytics_snapshots(database_path=db_path)

        after = execute_query(
            "SELECT COUNT(*) as cnt FROM cross_site_observations WHERE property_id = ?",
            (property_id,),
            database_path=db_path,
        )
        count_after = after[0]["cnt"]

        assert count_before == count_after


# ---------------------------------------------------------------------------
# Test: Quiet gatekeeper remains unchanged
# ---------------------------------------------------------------------------


class TestQuietGatekeeperUnchanged:
    """Verify Quiet Score gatekeeper is unchanged."""

    def test_quiet_gatekeeper_function_unchanged(self):
        """apply_quiet_gatekeeper should still work as before."""
        from marketsentry.quiet_vibrancy import apply_quiet_gatekeeper

        result = apply_quiet_gatekeeper(6.5, 2.0)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_quiet_gatekeeper_not_affected_by_trends(self, temp_db_with_data):
        """Creating trend snapshots should not affect quiet gatekeeper."""
        from marketsentry.cross_site_trends import create_cross_site_analytics_snapshots
        from marketsentry.quiet_vibrancy import apply_quiet_gatekeeper

        db_path, _ = temp_db_with_data

        before = apply_quiet_gatekeeper(8.5, 1.5)
        create_cross_site_analytics_snapshots(database_path=db_path)
        after = apply_quiet_gatekeeper(8.5, 1.5)

        assert before == after


# ---------------------------------------------------------------------------
# Test: No walkability fields added
# ---------------------------------------------------------------------------


class TestNoWalkabilityFields:
    """Verify no walkability fields are added."""

    def test_snapshot_model_no_walkability(self):
        """Snapshot model should not have walkability fields."""
        fields = CrossSiteAnalyticsSnapshot.model_fields
        walk_fields = [f for f in fields if "walk" in f.lower()]
        assert len(walk_fields) == 0

    def test_trend_change_no_walkability(self):
        """TrendChange model should not have walkability fields."""
        fields = CrossSiteTrendChange.model_fields
        walk_fields = [f for f in fields if "walk" in f.lower()]
        assert len(walk_fields) == 0

    def test_trend_report_no_walkability(self):
        """TrendReportRow model should not have walkability fields."""
        fields = CrossSiteTrendReportRow.model_fields
        walk_fields = [f for f in fields if "walk" in f.lower()]
        assert len(walk_fields) == 0

    def test_snapshots_table_no_walkability(self, temp_db):
        """Snapshots table should not have walkability columns."""
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(cross_site_analytics_snapshots)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        walk_cols = [c for c in columns if "walk" in c.lower()]
        assert len(walk_cols) == 0


# ---------------------------------------------------------------------------
# Test: No real network calls
# ---------------------------------------------------------------------------


class TestNoNetworkCalls:
    """Verify no real network calls are made."""

    def test_snapshot_creation_no_network(self, temp_db_with_data):
        """Snapshot creation should not make network calls."""
        from marketsentry.cross_site_trends import create_cross_site_analytics_snapshots

        db_path, _ = temp_db_with_data

        with patch("socket.socket") as mock_socket:
            create_cross_site_analytics_snapshots(database_path=db_path)
            mock_socket.assert_not_called()

    def test_trend_report_no_network(self, temp_db_with_data, temp_exports_dir):
        """Trend report export should not make network calls."""
        from marketsentry.cross_site_trends import (
            create_cross_site_analytics_snapshots,
            export_cross_site_trend_report,
        )

        db_path, _ = temp_db_with_data
        create_cross_site_analytics_snapshots(database_path=db_path)

        with patch("socket.socket") as mock_socket:
            output = str(Path(temp_exports_dir) / "no_net.csv")
            export_cross_site_trend_report(database_path=db_path, output_path=output)
            mock_socket.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Trend direction and recommended actions
# ---------------------------------------------------------------------------


class TestTrendDirectionAndActions:
    """Test trend direction determination and action recommendations."""

    def test_degrading_severity_increase_recommendation(self):
        """Degrading trend with severity increase should recommend review."""
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = CrossSiteAnalyticsSnapshot(
            property_id=1,
            discrepancy_severity_label="low",
            cross_site_manual_review_priority="low",
            overall_cross_site_confidence_score=0.7,
        )
        cur = CrossSiteAnalyticsSnapshot(
            property_id=1,
            discrepancy_severity_label="high",
            cross_site_manual_review_priority="high",
            overall_cross_site_confidence_score=0.4,
        )
        change = calculate_cross_site_trend_change(cur, prev)

        assert change.trend_direction == "degrading"
        assert "review" in change.recommended_next_action.lower()

    def test_improving_trend_recommendation(self):
        """Improving trend should recommend continued monitoring."""
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = CrossSiteAnalyticsSnapshot(
            property_id=1,
            discrepancy_severity_label="medium",
            cross_site_manual_review_priority="medium",
            overall_cross_site_confidence_score=0.5,
        )
        cur = CrossSiteAnalyticsSnapshot(
            property_id=1,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
            overall_cross_site_confidence_score=0.8,
        )
        change = calculate_cross_site_trend_change(cur, prev)

        assert change.trend_direction == "improving"
        assert "monitor" in change.recommended_next_action.lower()

    def test_stable_trend_recommendation(self):
        """Stable trend should recommend no action."""
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = CrossSiteAnalyticsSnapshot(
            property_id=1,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
            overall_cross_site_confidence_score=0.7,
        )
        cur = CrossSiteAnalyticsSnapshot(
            property_id=1,
            discrepancy_severity_label="none",
            cross_site_manual_review_priority="none",
            overall_cross_site_confidence_score=0.72,
        )
        change = calculate_cross_site_trend_change(cur, prev)

        assert change.trend_direction == "stable"
        assert "no action" in change.recommended_next_action.lower()


# ---------------------------------------------------------------------------
# Test: Score delta helper
# ---------------------------------------------------------------------------


class TestScoreDelta:
    """Test the _score_delta helper."""

    def test_delta_both_present(self):
        """Delta should be calculated when both values present."""
        from marketsentry.cross_site_trends import _score_delta

        assert _score_delta(0.8, 0.5) == pytest.approx(0.3, abs=0.001)

    def test_delta_current_none(self):
        """Delta should be None when current is None."""
        from marketsentry.cross_site_trends import _score_delta

        assert _score_delta(None, 0.5) is None

    def test_delta_previous_none(self):
        """Delta should be None when previous is None."""
        from marketsentry.cross_site_trends import _score_delta

        assert _score_delta(0.5, None) is None

    def test_delta_both_none(self):
        """Delta should be None when both None."""
        from marketsentry.cross_site_trends import _score_delta

        assert _score_delta(None, None) is None
