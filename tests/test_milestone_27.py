"""Tests for Milestone 27: Cross-Site Alert Aggregation and Historical Pattern Analysis.

Tests cover:
- Alert burden calculation with no alerts
- Alert burden calculation with low open alerts
- Alert burden calculation with high/critical alerts
- Oldest open alert age calculation
- Most common alert type/severity
- Repeated confidence drop pattern
- Repeated status discrepancy pattern
- Repeated price agreement degraded pattern
- Repeated DOM agreement degraded pattern
- Improving source quality pattern
- Property-level history summary
- All-property aggregation summary
- Alert analytics report export
- cross-site-alert-analytics-summary CLI
- export-cross-site-alert-analytics-report CLI
- Dashboard alert analytics table loads
- Watchlist monitoring report includes alert aggregation fields
- No Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- No walkability fields added
- No real network calls
- Existing MVP 1-26 tests still pass (run with full suite)
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
    CrossSiteAlertAggregationResult,
    CrossSiteAlertAnalyticsReportRow,
    CrossSiteAlertBurdenMetrics,
    CrossSiteAlertHistorySummary,
    CrossSiteAlertPattern,
)


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
def temp_exports_dir():
    """Create a temporary exports directory."""
    with tempfile.TemporaryDirectory() as d:
        yield d


def _insert_watched_property(db_path: str, address: str = "123 Test St") -> int:
    """Insert a watched property and return its ID."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO watched_properties (
            first_saved_date, active_watch_status, address, city, zip,
            current_price, displayed_dom, garage_spaces, gas_service
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-01-01", 1, address, "Temecula", "92592", 750000, 45, 2, 1),
    )
    pid = cursor.lastrowid
    conn.commit()
    conn.close()
    return pid


def _insert_alert(
    db_path: str,
    property_id: int,
    alert_type: str = "confidence_drop",
    severity: str = "warning",
    alert_status: str = "open",
    snapshot_id: int = 1,
    created_at: str = "",
) -> int:
    """Insert a trend alert and return its ID."""
    if not created_at:
        created_at = datetime.now().isoformat()

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO cross_site_trend_alerts (
            property_id, alert_type, severity, alert_status,
            snapshot_id, created_at, message, recommended_action
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            property_id, alert_type, severity, alert_status,
            snapshot_id, created_at,
            f"Test {alert_type} alert",
            "Review cross-site data",
        ),
    )
    aid = cursor.lastrowid
    conn.commit()
    conn.close()
    return aid


# ---------------------------------------------------------------------------
# Test: Alert burden with no alerts
# ---------------------------------------------------------------------------


class TestAlertBurdenNoAlerts:
    """Test burden calculation when no alerts exist."""

    def test_no_alerts_returns_none_burden(self, temp_db):
        """Property with no alerts should have 'none' burden."""
        from marketsentry.cross_site_alert_analytics import (
            calculate_alert_burden_for_property,
        )

        pid = _insert_watched_property(temp_db)
        burden = calculate_alert_burden_for_property(pid, temp_db)

        assert burden.total_alert_count == 0
        assert burden.open_alert_count == 0
        assert burden.alert_burden_label == "none"
        assert burden.alert_burden_score == 0.0

    def test_empty_db_returns_none_burden(self, temp_db):
        """Empty database should return none burden."""
        from marketsentry.cross_site_alert_analytics import (
            calculate_alert_burden_for_property,
        )

        burden = calculate_alert_burden_for_property(99999, temp_db)
        assert burden.alert_burden_label == "none"


# ---------------------------------------------------------------------------
# Test: Alert burden with low open alerts
# ---------------------------------------------------------------------------


class TestAlertBurdenLow:
    """Test burden calculation with 1-2 low/warning open alerts."""

    def test_single_warning_is_low(self, temp_db):
        """Single warning alert should result in low burden."""
        from marketsentry.cross_site_alert_analytics import (
            calculate_alert_burden_for_property,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="warning")

        burden = calculate_alert_burden_for_property(pid, temp_db)
        assert burden.open_alert_count == 1
        assert burden.alert_burden_label == "low"

    def test_two_info_alerts_is_low(self, temp_db):
        """Two info alerts should result in low burden."""
        from marketsentry.cross_site_alert_analytics import (
            calculate_alert_burden_for_property,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="info")
        _insert_alert(temp_db, pid, severity="info", alert_type="confidence_improvement")

        burden = calculate_alert_burden_for_property(pid, temp_db)
        assert burden.open_alert_count == 2
        assert burden.alert_burden_label == "low"


# ---------------------------------------------------------------------------
# Test: Alert burden with high/critical alerts
# ---------------------------------------------------------------------------


class TestAlertBurdenHighCritical:
    """Test burden calculation with high/critical alerts."""

    def test_single_high_is_moderate(self, temp_db):
        """Single high alert should result in moderate burden."""
        from marketsentry.cross_site_alert_analytics import (
            calculate_alert_burden_for_property,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="high")

        burden = calculate_alert_burden_for_property(pid, temp_db)
        assert burden.high_or_critical_open_alert_count >= 1
        assert burden.alert_burden_label == "moderate"

    def test_two_high_is_high_burden(self, temp_db):
        """Two high alerts should result in high burden."""
        from marketsentry.cross_site_alert_analytics import (
            calculate_alert_burden_for_property,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="high", snapshot_id=1)
        _insert_alert(temp_db, pid, severity="high", alert_type="severity_increase", snapshot_id=2)

        burden = calculate_alert_burden_for_property(pid, temp_db)
        assert burden.high_or_critical_open_alert_count >= 2
        # With repeated high/critical from different snapshots => elevated_review
        assert burden.alert_burden_label in ("high", "elevated_review")

    def test_critical_alert_is_high_burden(self, temp_db):
        """Critical alert should result in high burden."""
        from marketsentry.cross_site_alert_analytics import (
            calculate_alert_burden_for_property,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="critical")

        burden = calculate_alert_burden_for_property(pid, temp_db)
        assert burden.alert_burden_label == "high"

    def test_three_warnings_is_moderate(self, temp_db):
        """Three warning alerts should result in moderate burden."""
        from marketsentry.cross_site_alert_analytics import (
            calculate_alert_burden_for_property,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="warning", alert_type="confidence_drop")
        _insert_alert(temp_db, pid, severity="warning", alert_type="stale_sources_increased")
        _insert_alert(temp_db, pid, severity="warning", alert_type="dom_agreement_degraded")

        burden = calculate_alert_burden_for_property(pid, temp_db)
        assert burden.open_alert_count == 3
        assert burden.alert_burden_label == "moderate"


# ---------------------------------------------------------------------------
# Test: Oldest open alert age
# ---------------------------------------------------------------------------


class TestOldestOpenAlertAge:
    """Test oldest open alert age calculation."""

    def test_age_calculation(self, temp_db):
        """Oldest alert age should be calculated correctly."""
        from marketsentry.cross_site_alert_analytics import (
            calculate_alert_age_days,
            calculate_alert_burden_for_property,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        burden = calculate_alert_burden_for_property(pid, temp_db)
        assert burden.oldest_open_alert_age_days is not None
        assert burden.oldest_open_alert_age_days >= 9  # Allow for timing

    def test_age_none_for_no_alerts(self):
        """Null input should return None."""
        from marketsentry.cross_site_alert_analytics import calculate_alert_age_days

        assert calculate_alert_age_days(None) is None
        assert calculate_alert_age_days("") is None

    def test_age_today(self):
        """Alert created now should have age 0."""
        from marketsentry.cross_site_alert_analytics import calculate_alert_age_days

        now = datetime.now().isoformat()
        age = calculate_alert_age_days(now)
        assert age is not None
        assert age == 0


# ---------------------------------------------------------------------------
# Test: Most common alert type/severity
# ---------------------------------------------------------------------------


class TestMostCommon:
    """Test most common alert type and severity."""

    def test_most_common_type(self, temp_db):
        """Most common type should be the one with most occurrences."""
        from marketsentry.cross_site_alert_analytics import (
            calculate_alert_burden_for_property,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_type="confidence_drop")
        _insert_alert(temp_db, pid, alert_type="confidence_drop")
        _insert_alert(temp_db, pid, alert_type="stale_sources_increased")

        burden = calculate_alert_burden_for_property(pid, temp_db)
        assert burden.most_common_alert_type == "confidence_drop"

    def test_most_common_severity(self, temp_db):
        """Most common severity should be the one with most occurrences."""
        from marketsentry.cross_site_alert_analytics import (
            calculate_alert_burden_for_property,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="warning")
        _insert_alert(temp_db, pid, severity="warning")
        _insert_alert(temp_db, pid, severity="high")

        burden = calculate_alert_burden_for_property(pid, temp_db)
        assert burden.most_common_severity == "warning"


# ---------------------------------------------------------------------------
# Test: Repeated confidence drop pattern
# ---------------------------------------------------------------------------


class TestRepeatedConfidenceDrop:
    """Test repeated confidence drop pattern detection."""

    def test_two_confidence_drops_detected(self, temp_db):
        """Two confidence_drop alerts should trigger repeated pattern."""
        from marketsentry.cross_site_alert_analytics import (
            identify_repeated_alert_patterns,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_type="confidence_drop")
        _insert_alert(temp_db, pid, alert_type="confidence_drop")

        patterns = identify_repeated_alert_patterns(pid, temp_db)
        types = [p.pattern_type for p in patterns]
        assert "repeated_confidence_drop" in types

    def test_single_confidence_drop_not_pattern(self, temp_db):
        """Single confidence_drop should not trigger pattern."""
        from marketsentry.cross_site_alert_analytics import (
            identify_repeated_alert_patterns,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_type="confidence_drop")

        patterns = identify_repeated_alert_patterns(pid, temp_db)
        types = [p.pattern_type for p in patterns]
        assert "repeated_confidence_drop" not in types


# ---------------------------------------------------------------------------
# Test: Repeated status discrepancy pattern
# ---------------------------------------------------------------------------


class TestRepeatedStatusDiscrepancy:
    """Test repeated status discrepancy pattern detection."""

    def test_two_status_degraded_detected(self, temp_db):
        """Two status_agreement_degraded should trigger pattern."""
        from marketsentry.cross_site_alert_analytics import (
            identify_repeated_alert_patterns,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_type="status_agreement_degraded")
        _insert_alert(temp_db, pid, alert_type="status_agreement_degraded")

        patterns = identify_repeated_alert_patterns(pid, temp_db)
        types = [p.pattern_type for p in patterns]
        assert "repeated_status_discrepancy" in types


# ---------------------------------------------------------------------------
# Test: Repeated price agreement degraded pattern
# ---------------------------------------------------------------------------


class TestRepeatedPriceAgreement:
    """Test repeated price agreement degraded pattern detection."""

    def test_two_price_degraded_detected(self, temp_db):
        """Two price_agreement_degraded should trigger pattern."""
        from marketsentry.cross_site_alert_analytics import (
            identify_repeated_alert_patterns,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_type="price_agreement_degraded")
        _insert_alert(temp_db, pid, alert_type="price_agreement_degraded")

        patterns = identify_repeated_alert_patterns(pid, temp_db)
        types = [p.pattern_type for p in patterns]
        assert "repeated_price_agreement_degraded" in types


# ---------------------------------------------------------------------------
# Test: Repeated DOM agreement degraded pattern
# ---------------------------------------------------------------------------


class TestRepeatedDomAgreement:
    """Test repeated DOM agreement degraded pattern detection."""

    def test_two_dom_degraded_detected(self, temp_db):
        """Two dom_agreement_degraded should trigger pattern."""
        from marketsentry.cross_site_alert_analytics import (
            identify_repeated_alert_patterns,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_type="dom_agreement_degraded")
        _insert_alert(temp_db, pid, alert_type="dom_agreement_degraded")

        patterns = identify_repeated_alert_patterns(pid, temp_db)
        types = [p.pattern_type for p in patterns]
        assert "repeated_dom_agreement_degraded" in types


# ---------------------------------------------------------------------------
# Test: Improving source quality pattern
# ---------------------------------------------------------------------------


class TestImprovingSourceQuality:
    """Test improving source quality pattern detection."""

    def test_two_improvements_detected(self, temp_db):
        """Two source_quality_improved should trigger pattern."""
        from marketsentry.cross_site_alert_analytics import (
            identify_repeated_alert_patterns,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_type="source_quality_improved", severity="info")
        _insert_alert(temp_db, pid, alert_type="source_quality_improved", severity="info")

        patterns = identify_repeated_alert_patterns(pid, temp_db)
        types = [p.pattern_type for p in patterns]
        assert "improving_source_quality_pattern" in types


# ---------------------------------------------------------------------------
# Test: Property-level history summary
# ---------------------------------------------------------------------------


class TestPropertyHistorySummary:
    """Test property-level alert history summary."""

    def test_summary_has_burden_and_patterns(self, temp_db):
        """Summary should contain both burden metrics and patterns."""
        from marketsentry.cross_site_alert_analytics import (
            summarize_alert_history_for_property,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_type="confidence_drop", severity="warning")
        _insert_alert(temp_db, pid, alert_type="confidence_drop", severity="high")

        prop = {"address": "123 Test St", "city": "Temecula", "zip": "92592"}
        summary = summarize_alert_history_for_property(pid, prop, temp_db)

        assert summary.property_id == pid
        assert summary.address == "123 Test St"
        assert summary.burden.total_alert_count == 2
        assert summary.burden.open_alert_count == 2
        assert len(summary.patterns) > 0
        assert summary.recommended_review_action is not None

    def test_summary_no_alerts(self, temp_db):
        """Summary with no alerts should have none burden."""
        from marketsentry.cross_site_alert_analytics import (
            summarize_alert_history_for_property,
        )

        pid = _insert_watched_property(temp_db)
        summary = summarize_alert_history_for_property(pid, None, temp_db)

        assert summary.burden.alert_burden_label == "none"
        assert len(summary.patterns) == 0


# ---------------------------------------------------------------------------
# Test: All-property aggregation summary
# ---------------------------------------------------------------------------


class TestAllPropertyAggregation:
    """Test aggregation across all properties."""

    def test_aggregation_with_multiple_properties(self, temp_db):
        """Aggregation should cover all properties with alerts."""
        from marketsentry.cross_site_alert_analytics import (
            summarize_alert_history_for_all_properties,
        )

        pid1 = _insert_watched_property(temp_db, "100 First Ave")
        pid2 = _insert_watched_property(temp_db, "200 Second Ave")

        _insert_alert(temp_db, pid1, severity="high")
        _insert_alert(temp_db, pid2, severity="warning")

        agg = summarize_alert_history_for_all_properties(temp_db)
        assert agg.total_properties_with_alerts == 2
        assert agg.properties_with_open_alerts == 2
        assert len(agg.summaries) == 2

    def test_aggregation_empty_db(self, temp_db):
        """Aggregation with no alerts should return zero counts."""
        from marketsentry.cross_site_alert_analytics import (
            summarize_alert_history_for_all_properties,
        )

        agg = summarize_alert_history_for_all_properties(temp_db)
        assert agg.total_properties_with_alerts == 0
        assert len(agg.summaries) == 0

    def test_aggregation_top_types(self, temp_db):
        """Top alert types should be populated."""
        from marketsentry.cross_site_alert_analytics import (
            summarize_alert_history_for_all_properties,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_type="confidence_drop")
        _insert_alert(temp_db, pid, alert_type="confidence_drop")
        _insert_alert(temp_db, pid, alert_type="stale_sources_increased")

        agg = summarize_alert_history_for_all_properties(temp_db)
        assert "confidence_drop" in agg.top_alert_types

    def test_aggregation_oldest_alert(self, temp_db):
        """Aggregation should track oldest open alert."""
        from marketsentry.cross_site_alert_analytics import (
            summarize_alert_history_for_all_properties,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=15)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        agg = summarize_alert_history_for_all_properties(temp_db)
        assert agg.oldest_open_alert_age_days is not None
        assert agg.oldest_open_alert_age_days >= 14


# ---------------------------------------------------------------------------
# Test: Alert analytics report export
# ---------------------------------------------------------------------------


class TestAlertAnalyticsReport:
    """Test alert analytics report export."""

    def test_export_report(self, temp_db, temp_exports_dir):
        """Export should create CSV with correct columns."""
        from marketsentry.cross_site_alert_analytics import (
            export_cross_site_alert_analytics_report,
            REPORT_FIELDNAMES,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="high")
        _insert_alert(temp_db, pid, alert_type="confidence_drop")

        output_path = str(Path(temp_exports_dir) / "test_analytics.csv")
        csv_path = export_cross_site_alert_analytics_report(
            database_path=temp_db, output_path=output_path
        )

        assert Path(csv_path).exists()
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) >= 1
            assert set(REPORT_FIELDNAMES).issubset(set(reader.fieldnames or []))

    def test_export_empty_db(self, temp_db, temp_exports_dir):
        """Export from empty database should create CSV with headers only."""
        from marketsentry.cross_site_alert_analytics import (
            export_cross_site_alert_analytics_report,
        )

        output_path = str(Path(temp_exports_dir) / "test_empty.csv")
        csv_path = export_cross_site_alert_analytics_report(
            database_path=temp_db, output_path=output_path
        )

        assert Path(csv_path).exists()
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 0

    def test_report_has_burden_fields(self, temp_db, temp_exports_dir):
        """Report should include burden score and label."""
        from marketsentry.cross_site_alert_analytics import (
            export_cross_site_alert_analytics_report,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="warning")

        output_path = str(Path(temp_exports_dir) / "test_burden.csv")
        csv_path = export_cross_site_alert_analytics_report(
            database_path=temp_db, output_path=output_path
        )

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) >= 1
            row = rows[0]
            assert "alert_burden_label" in row
            assert "alert_burden_score" in row
            assert row["alert_burden_label"] != ""


# ---------------------------------------------------------------------------
# Test: CLI commands
# ---------------------------------------------------------------------------


class TestCLICommands:
    """Test CLI command registration and invocation."""

    def test_summary_command_registered(self):
        """cross-site-alert-analytics-summary command should be registered."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(app, ["cross-site-alert-analytics-summary", "--help"])
        assert result.exit_code == 0
        assert "analytics" in result.output.lower()

    def test_export_command_registered(self):
        """export-cross-site-alert-analytics-report command should be registered."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(app, ["export-cross-site-alert-analytics-report", "--help"])
        assert result.exit_code == 0

    def test_summary_command_runs(self, temp_db):
        """Summary command should run successfully."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="warning")

        runner = CliRunner()
        result = runner.invoke(
            app, ["cross-site-alert-analytics-summary", "--db", temp_db]
        )
        assert result.exit_code == 0
        assert "alert" in result.output.lower()

    def test_export_command_runs(self, temp_db, temp_exports_dir):
        """Export command should run successfully."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="warning")

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "export-cross-site-alert-analytics-report",
                "--db", temp_db,
                "--output-dir", temp_exports_dir,
            ],
        )
        assert result.exit_code == 0
        assert "exported" in result.output.lower() or "success" in result.output.lower()


# ---------------------------------------------------------------------------
# Test: Dashboard alert analytics table loads
# ---------------------------------------------------------------------------


class TestDashboardAlertAnalytics:
    """Test dashboard alert analytics table loading."""

    def test_build_analytics_table_from_csv(self, temp_db, temp_exports_dir):
        """build_cross_site_alert_analytics_table loads CSV report."""
        from marketsentry.cross_site_alert_analytics import (
            export_cross_site_alert_analytics_report,
        )
        from marketsentry.dashboard import build_cross_site_alert_analytics_table

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="warning")

        output_path = str(
            Path(temp_exports_dir)
            / "cross_site_alert_analytics_20260508_120000.csv"
        )
        export_cross_site_alert_analytics_report(
            database_path=temp_db, output_path=output_path
        )

        df = build_cross_site_alert_analytics_table(temp_exports_dir)
        assert not df.empty
        assert "alert_burden_label" in df.columns

    def test_find_latest_analytics_report(self, temp_db, temp_exports_dir):
        """find_latest_report should find alert analytics report."""
        from marketsentry.cross_site_alert_analytics import (
            export_cross_site_alert_analytics_report,
        )
        from marketsentry.dashboard import find_latest_report

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        output_path = str(
            Path(temp_exports_dir)
            / "cross_site_alert_analytics_20260508_120000.csv"
        )
        export_cross_site_alert_analytics_report(
            database_path=temp_db, output_path=output_path
        )

        report = find_latest_report("cross_site_alert_analytics", temp_exports_dir)
        assert report is not None
        assert "cross_site_alert_analytics" in report.name


# ---------------------------------------------------------------------------
# Test: Watchlist monitoring integration
# ---------------------------------------------------------------------------


class TestWatchlistMonitoringIntegration:
    """Test watchlist monitoring alert aggregation fields."""

    def test_analytics_fields_present(self, temp_db):
        """Alert analytics for property should include expected fields."""
        from marketsentry.cross_site_alert_analytics import (
            get_alert_analytics_for_property,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="warning")

        analytics = get_alert_analytics_for_property(pid, temp_db)

        assert "cross_site_alert_burden_label" in analytics
        assert "cross_site_alert_burden_score" in analytics
        assert "cross_site_repeated_patterns" in analytics
        assert "cross_site_oldest_open_alert_age_days" in analytics

    def test_analytics_with_burden(self, temp_db):
        """Analytics for property with alerts should have nonzero burden."""
        from marketsentry.cross_site_alert_analytics import (
            get_alert_analytics_for_property,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="high")

        analytics = get_alert_analytics_for_property(pid, temp_db)
        assert analytics["cross_site_alert_burden_label"] != "none"
        assert analytics["cross_site_alert_burden_score"] > 0

    def test_analytics_no_alerts(self, temp_db):
        """Analytics for property with no alerts should have none burden."""
        from marketsentry.cross_site_alert_analytics import (
            get_alert_analytics_for_property,
        )

        pid = _insert_watched_property(temp_db)
        analytics = get_alert_analytics_for_property(pid, temp_db)
        assert analytics["cross_site_alert_burden_label"] == "none"
        assert analytics["cross_site_alert_burden_score"] == 0.0


# ---------------------------------------------------------------------------
# Test: No Redfin source-of-truth overwrite
# ---------------------------------------------------------------------------


class TestNoRedfinOverwrite:
    """Verify analytics do not overwrite Redfin source-of-truth fields."""

    def test_watched_properties_unchanged(self, temp_db):
        """Running analytics should not modify watched_properties."""
        from marketsentry.cross_site_alert_analytics import (
            summarize_alert_history_for_all_properties,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="high")

        before = execute_query(
            "SELECT * FROM watched_properties WHERE property_id = ?",
            (pid,), database_path=temp_db,
        )
        before_dict = dict(before[0])

        summarize_alert_history_for_all_properties(temp_db)

        after = execute_query(
            "SELECT * FROM watched_properties WHERE property_id = ?",
            (pid,), database_path=temp_db,
        )
        after_dict = dict(after[0])

        for field in [
            "current_price", "displayed_dom", "garage_spaces",
            "gas_service", "active_watch_status", "user_notes",
            "watch_priority",
        ]:
            assert before_dict.get(field) == after_dict.get(field)

    def test_no_write_to_properties(self):
        """Analytics module should not write to watched_properties."""
        import inspect
        import marketsentry.cross_site_alert_analytics as mod

        source = inspect.getsource(mod)
        assert "UPDATE watched_properties" not in source
        assert "INSERT INTO watched_properties" not in source


# ---------------------------------------------------------------------------
# Test: Quiet gatekeeper remains unchanged
# ---------------------------------------------------------------------------


class TestQuietGatekeeperUnchanged:
    """Verify analytics module does not modify Quiet Score gatekeeper."""

    def test_no_quiet_gatekeeper_import(self):
        """Analytics module should not import or call quiet gatekeeper."""
        import inspect
        import marketsentry.cross_site_alert_analytics as mod

        source = inspect.getsource(mod)
        assert "apply_quiet_gatekeeper" not in source
        assert "quiet_vibrancy" not in source


# ---------------------------------------------------------------------------
# Test: No walkability fields
# ---------------------------------------------------------------------------


class TestNoWalkabilityFields:
    """Verify no walkability fields are added."""

    def test_no_walkability_in_module(self):
        """Analytics module should not reference walkability."""
        import inspect
        import marketsentry.cross_site_alert_analytics as mod

        source = inspect.getsource(mod)
        assert "walkability" not in source.lower()
        assert "walk_score" not in source.lower()

    def test_no_walkability_in_models(self):
        """New models should not include walkability fields."""
        for model_cls in [
            CrossSiteAlertBurdenMetrics,
            CrossSiteAlertPattern,
            CrossSiteAlertHistorySummary,
            CrossSiteAlertAggregationResult,
            CrossSiteAlertAnalyticsReportRow,
        ]:
            for field_name in model_cls.model_fields:
                assert "walkability" not in field_name.lower()
                assert "walk_score" not in field_name.lower()


# ---------------------------------------------------------------------------
# Test: No real network calls
# ---------------------------------------------------------------------------


class TestNoNetworkCalls:
    """Verify no real network calls are made."""

    def test_no_network_in_analytics(self, temp_db):
        """Analytics should not make network calls."""
        from marketsentry.cross_site_alert_analytics import (
            summarize_alert_history_for_all_properties,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch("http.client.HTTPConnection") as mock_http:
            summarize_alert_history_for_all_properties(temp_db)
            mock_urlopen.assert_not_called()
            mock_http.assert_not_called()

    def test_no_requests_import(self):
        """Analytics module should not import requests or urllib."""
        import inspect
        import marketsentry.cross_site_alert_analytics as mod

        source = inspect.getsource(mod)
        assert "import requests" not in source
        assert "import urllib" not in source
        assert "import httpx" not in source


# ---------------------------------------------------------------------------
# Test: Pattern fields
# ---------------------------------------------------------------------------


class TestPatternFields:
    """Test pattern model fields are populated correctly."""

    def test_pattern_has_all_fields(self, temp_db):
        """Pattern should include count, first_seen, latest_seen, etc."""
        from marketsentry.cross_site_alert_analytics import (
            identify_repeated_alert_patterns,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=5)).isoformat()
        new_date = datetime.now().isoformat()
        _insert_alert(temp_db, pid, alert_type="confidence_drop", created_at=old_date)
        _insert_alert(temp_db, pid, alert_type="confidence_drop", created_at=new_date)

        patterns = identify_repeated_alert_patterns(pid, temp_db)
        conf_pattern = next(
            (p for p in patterns if p.pattern_type == "repeated_confidence_drop"),
            None,
        )
        assert conf_pattern is not None
        assert conf_pattern.count == 2
        assert conf_pattern.first_seen is not None
        assert conf_pattern.latest_seen is not None
        assert conf_pattern.severity_summary is not None
        assert conf_pattern.message is not None
        assert conf_pattern.recommended_review_action is not None


# ---------------------------------------------------------------------------
# Test: Models
# ---------------------------------------------------------------------------


class TestModels:
    """Test Milestone 27 models."""

    def test_burden_metrics_model(self):
        """CrossSiteAlertBurdenMetrics should have all expected fields."""
        metrics = CrossSiteAlertBurdenMetrics(property_id=1)
        assert metrics.property_id == 1
        assert metrics.alert_burden_label == "none"
        assert metrics.alert_burden_score == 0.0

    def test_pattern_model(self):
        """CrossSiteAlertPattern should have all expected fields."""
        pattern = CrossSiteAlertPattern(
            property_id=1, pattern_type="repeated_confidence_drop"
        )
        assert pattern.pattern_type == "repeated_confidence_drop"
        assert pattern.count == 0

    def test_history_summary_model(self):
        """CrossSiteAlertHistorySummary should have all expected fields."""
        summary = CrossSiteAlertHistorySummary(property_id=1)
        assert summary.property_id == 1
        assert summary.burden.property_id == 0  # default

    def test_aggregation_result_model(self):
        """CrossSiteAlertAggregationResult should have all expected fields."""
        result = CrossSiteAlertAggregationResult()
        assert result.total_properties_with_alerts == 0

    def test_report_row_model(self):
        """CrossSiteAlertAnalyticsReportRow should have all expected fields."""
        row = CrossSiteAlertAnalyticsReportRow(
            property_id=1, alert_burden_label="low"
        )
        assert row.alert_burden_label == "low"

    def test_recurring_high_severity_pattern(self, temp_db):
        """Two high/critical alerts from different snapshots should trigger recurring pattern."""
        from marketsentry.cross_site_alert_analytics import (
            identify_repeated_alert_patterns,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="high", snapshot_id=1)
        _insert_alert(temp_db, pid, severity="critical", alert_type="severity_increase", snapshot_id=2)

        patterns = identify_repeated_alert_patterns(pid, temp_db)
        types = [p.pattern_type for p in patterns]
        assert "recurring_high_severity_alerts" in types
