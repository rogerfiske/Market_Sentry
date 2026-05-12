"""Tests for Milestone 37: Lifecycle Health Trend Snapshots.

Validates health snapshot storage, trend change detection,
trend report export, CLI commands, dashboard integration,
scheduled script safety, and constraint enforcement.
"""

import csv
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from marketsentry.database import init_db, table_exists
from marketsentry.models import (
    CrossSiteLifecycleHealthSnapshot,
    CrossSiteLifecycleHealthSnapshotRunResult,
    CrossSiteLifecycleHealthTrendChange,
    CrossSiteLifecycleHealthTrendReportRow,
    CrossSiteLifecycleHealthTrendSummary,
)


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = str(tmp_path / "test_m37.db")
    init_db(db_path)
    yield db_path


@pytest.fixture
def temp_exports_dir(tmp_path):
    """Create a temporary exports directory."""
    exports = tmp_path / "exports"
    exports.mkdir()
    return str(exports)


def _insert_watched_property(db_path, property_id, address="123 Main St",
                              city="TestCity", zip_code="12345"):
    """Insert a test watched property."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO watched_properties "
        "(property_id, address, city, zip, active_watch_status) "
        "VALUES (?, ?, ?, ?, 1)",
        (property_id, address, city, zip_code),
    )
    conn.commit()
    conn.close()


def _insert_alert(db_path, alert_id, property_id, candidate_id=None,
                   alert_type="price_change", severity="medium",
                   status="open", created_at=None, notes=""):
    """Insert a test alert."""
    if created_at is None:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO cross_site_trend_alerts "
        "(alert_id, property_id, candidate_id, alert_type, severity, "
        "alert_status, created_at, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (alert_id, property_id, candidate_id, alert_type, severity,
         status, created_at, notes),
    )
    conn.commit()
    conn.close()


def _insert_health_snapshot(db_path, property_id, score=100.0,
                             label="excellent", open_alerts=0,
                             hc_alerts=0, gaps=0, reparse=0,
                             manual_review=0, captured_at=None):
    """Insert a test health snapshot directly."""
    if captured_at is None:
        captured_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO cross_site_lifecycle_health_snapshots "
        "(property_id, captured_at, lifecycle_health_score, "
        "lifecycle_health_label, open_alert_count, "
        "high_or_critical_open_alert_count, lifecycle_gap_count, "
        "needs_reparse_count, needs_manual_review_count, "
        "component_summary, recommended_review_action) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (property_id, captured_at, score, label, open_alerts,
         hc_alerts, gaps, reparse, manual_review,
         "no deductions", "No action needed."),
    )
    conn.commit()
    conn.close()


# ── Schema ──

class TestSchemaM37:
    """Schema creation and idempotency tests."""

    def test_table_created(self, temp_db):
        """Health snapshots table is created by init_db."""
        assert table_exists(
            "cross_site_lifecycle_health_snapshots", temp_db,
        )

    def test_table_creation_idempotent(self, temp_db):
        """Running init_db again does not fail."""
        init_db(temp_db)
        assert table_exists(
            "cross_site_lifecycle_health_snapshots", temp_db,
        )

    def test_indexes_created(self, temp_db):
        """Indexes for health snapshots table exist."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        conn.close()
        assert "idx_cs_health_snapshots_property" in indexes
        assert "idx_cs_health_snapshots_captured" in indexes


# ── Snapshot Creation ──

class TestSnapshotCreation:
    """Health snapshot creation tests."""

    def test_creates_snapshots(self, temp_db):
        """Snapshots are created for properties with alerts."""
        from marketsentry.cross_site_lifecycle_health_trends import (
            create_lifecycle_health_snapshots,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        result = create_lifecycle_health_snapshots(
            database_path=temp_db, force=True,
        )
        assert result.properties_scanned >= 1
        assert result.snapshots_created >= 1

    def test_label_counts_populated(self, temp_db):
        """Label counts are populated in result."""
        from marketsentry.cross_site_lifecycle_health_trends import (
            create_lifecycle_health_snapshots,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="resolved")

        result = create_lifecycle_health_snapshots(
            database_path=temp_db, force=True,
        )
        total = sum(result.label_counts.values())
        assert total >= 1


# ── Same-day / No-change Skip ──

class TestSameDaySkip:
    """Same-day/no-change skip behavior."""

    def test_same_day_no_change_skips(self, temp_db):
        """Second snapshot on same day with no change is skipped."""
        from marketsentry.cross_site_lifecycle_health_trends import (
            create_lifecycle_health_snapshots,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="resolved")

        result1 = create_lifecycle_health_snapshots(
            database_path=temp_db, force=True,
        )
        assert result1.snapshots_created >= 1

        result2 = create_lifecycle_health_snapshots(
            database_path=temp_db, force=False,
        )
        assert result2.snapshots_skipped >= 1


# ── Force Snapshot ──

class TestForceSnapshot:
    """Force flag creates snapshots regardless."""

    def test_force_creates_rows(self, temp_db):
        """Force flag creates snapshots even on same day."""
        from marketsentry.cross_site_lifecycle_health_trends import (
            create_lifecycle_health_snapshots,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="resolved")

        create_lifecycle_health_snapshots(
            database_path=temp_db, force=True,
        )
        result = create_lifecycle_health_snapshots(
            database_path=temp_db, force=True,
        )
        assert result.snapshots_created >= 1
        assert result.snapshots_skipped == 0


# ── Material Change Detection ──

class TestMaterialChange:
    """Material change creates new snapshot row."""

    def test_score_delta_creates_row(self, temp_db):
        """Health score change >= 5 creates a new snapshot."""
        from marketsentry.cross_site_lifecycle_health_trends import (
            create_lifecycle_health_snapshots,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="resolved")

        # Create first snapshot
        create_lifecycle_health_snapshots(
            database_path=temp_db, force=True,
        )

        # Add a high alert to change score significantly
        old = (datetime.now() - timedelta(days=10)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        _insert_alert(
            temp_db, 2, 1, severity="high", status="open",
            created_at=old,
        )

        result = create_lifecycle_health_snapshots(
            database_path=temp_db, force=False,
        )
        assert result.snapshots_created >= 1
        assert result.material_changes_detected >= 1

    def test_label_change_creates_row(self, temp_db):
        """Label change creates a new snapshot."""
        from marketsentry.cross_site_lifecycle_health_trends import (
            create_lifecycle_health_snapshots,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="resolved")

        create_lifecycle_health_snapshots(
            database_path=temp_db, force=True,
        )

        # Add many critical alerts to drop label
        for i in range(2, 15):
            old = (datetime.now() - timedelta(days=20)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            _insert_alert(
                temp_db, i, 1, severity="critical", status="open",
                created_at=old,
            )

        result = create_lifecycle_health_snapshots(
            database_path=temp_db, force=False,
        )
        assert result.snapshots_created >= 1

    def test_alert_count_change_creates_row(self, temp_db):
        """Open alert count change creates a new snapshot."""
        from marketsentry.cross_site_lifecycle_health_trends import (
            create_lifecycle_health_snapshots,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        create_lifecycle_health_snapshots(
            database_path=temp_db, force=True,
        )

        _insert_alert(temp_db, 2, 1, status="open")

        result = create_lifecycle_health_snapshots(
            database_path=temp_db, force=False,
        )
        assert result.snapshots_created >= 1


# ── Latest / Previous Snapshot Retrieval ──

class TestSnapshotRetrieval:
    """Snapshot retrieval tests."""

    def test_get_latest(self, temp_db):
        """Latest snapshot is retrievable."""
        from marketsentry.cross_site_lifecycle_health_trends import (
            create_lifecycle_health_snapshots,
            get_latest_lifecycle_health_snapshot,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")
        create_lifecycle_health_snapshots(
            database_path=temp_db, force=True,
        )

        snap = get_latest_lifecycle_health_snapshot(1, temp_db)
        assert snap is not None
        assert snap.property_id == 1

    def test_get_previous(self, temp_db):
        """Previous snapshot is retrievable after two snapshots."""
        from marketsentry.cross_site_lifecycle_health_trends import (
            create_lifecycle_health_snapshots,
            get_previous_lifecycle_health_snapshot,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")
        create_lifecycle_health_snapshots(
            database_path=temp_db, force=True,
        )
        create_lifecycle_health_snapshots(
            database_path=temp_db, force=True,
        )

        prev = get_previous_lifecycle_health_snapshot(1, temp_db)
        assert prev is not None

    def test_no_snapshot_returns_none(self, temp_db):
        """No snapshot returns None."""
        from marketsentry.cross_site_lifecycle_health_trends import (
            get_latest_lifecycle_health_snapshot,
        )

        snap = get_latest_lifecycle_health_snapshot(999, temp_db)
        assert snap is None


# ── Trend Change ──

class TestTrendChange:
    """Trend change detection tests."""

    def test_trend_improved(self, temp_db):
        """Improved trend is detected when score increases."""
        # Insert two snapshots with improving score
        yesterday = (datetime.now() - timedelta(days=1)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        _insert_watched_property(temp_db, 1)
        _insert_health_snapshot(
            temp_db, 1, score=60.0, label="watch",
            open_alerts=5, captured_at=yesterday,
        )
        _insert_health_snapshot(
            temp_db, 1, score=85.0, label="good",
            open_alerts=1,
        )

        from marketsentry.cross_site_lifecycle_health_trends import (
            calculate_lifecycle_health_trend_change,
        )

        change = calculate_lifecycle_health_trend_change(1, temp_db)
        assert change is not None
        assert change.trend_direction == "improved"
        assert change.health_score_delta > 0

    def test_trend_degraded(self, temp_db):
        """Degraded trend is detected when score decreases."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        _insert_watched_property(temp_db, 1)
        _insert_health_snapshot(
            temp_db, 1, score=90.0, label="excellent",
            open_alerts=0, captured_at=yesterday,
        )
        _insert_health_snapshot(
            temp_db, 1, score=50.0, label="needs_review",
            open_alerts=5,
        )

        from marketsentry.cross_site_lifecycle_health_trends import (
            calculate_lifecycle_health_trend_change,
        )

        change = calculate_lifecycle_health_trend_change(1, temp_db)
        assert change is not None
        assert change.trend_direction == "degraded"
        assert change.health_score_delta < 0

    def test_trend_stable(self, temp_db):
        """Stable trend when no material changes."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        _insert_watched_property(temp_db, 1)
        _insert_health_snapshot(
            temp_db, 1, score=90.0, label="excellent",
            open_alerts=0, captured_at=yesterday,
        )
        _insert_health_snapshot(
            temp_db, 1, score=90.0, label="excellent",
            open_alerts=0,
        )

        from marketsentry.cross_site_lifecycle_health_trends import (
            calculate_lifecycle_health_trend_change,
        )

        change = calculate_lifecycle_health_trend_change(1, temp_db)
        assert change is not None
        assert change.trend_direction == "stable"

    def test_trend_new(self, temp_db):
        """New trend for first snapshot."""
        _insert_watched_property(temp_db, 1)
        _insert_health_snapshot(temp_db, 1, score=100.0)

        from marketsentry.cross_site_lifecycle_health_trends import (
            calculate_lifecycle_health_trend_change,
        )

        change = calculate_lifecycle_health_trend_change(1, temp_db)
        assert change is not None
        assert change.trend_direction == "new"


# ── Trend Report Export ──

class TestTrendReport:
    """Trend report export tests."""

    def test_export_creates_file(self, temp_db, temp_exports_dir):
        """Export creates a CSV file."""
        _insert_watched_property(temp_db, 1)
        _insert_health_snapshot(temp_db, 1, score=100.0)

        from marketsentry.cross_site_lifecycle_health_trends import (
            export_lifecycle_health_trend_report,
        )

        path = export_lifecycle_health_trend_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
        )
        assert path is not None
        assert os.path.exists(path)

    def test_export_has_required_columns(self, temp_db, temp_exports_dir):
        """CSV file contains all required columns."""
        _insert_watched_property(temp_db, 1)
        _insert_health_snapshot(temp_db, 1, score=100.0)

        from marketsentry.cross_site_lifecycle_health_trends import (
            export_lifecycle_health_trend_report,
            HEALTH_TREND_CSV_FIELDNAMES,
        )

        path = export_lifecycle_health_trend_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
        )
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            for field in HEALTH_TREND_CSV_FIELDNAMES:
                assert field in headers, f"Missing column: {field}"

    def test_export_filename_pattern(self, temp_db, temp_exports_dir):
        """CSV filename follows expected pattern."""
        _insert_watched_property(temp_db, 1)
        _insert_health_snapshot(temp_db, 1, score=100.0)

        from marketsentry.cross_site_lifecycle_health_trends import (
            export_lifecycle_health_trend_report,
        )

        path = export_lifecycle_health_trend_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
        )
        filename = Path(path).name
        assert filename.startswith(
            "cross_site_lifecycle_health_trends_"
        )
        assert filename.endswith(".csv")

    def test_export_no_data(self, temp_db, temp_exports_dir):
        """Export returns None with no snapshots."""
        from marketsentry.cross_site_lifecycle_health_trends import (
            export_lifecycle_health_trend_report,
        )

        path = export_lifecycle_health_trend_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
        )
        assert path is None


# ── Trend Summary ──

class TestTrendSummary:
    """Trend summary tests."""

    def test_summary_counts(self, temp_db):
        """Summary counts are correct."""
        _insert_watched_property(temp_db, 1)
        _insert_watched_property(temp_db, 2, address="456 Oak Ave")

        yesterday = (datetime.now() - timedelta(days=1)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        # Property 1: improved
        _insert_health_snapshot(
            temp_db, 1, score=60.0, label="watch",
            open_alerts=3, captured_at=yesterday,
        )
        _insert_health_snapshot(
            temp_db, 1, score=90.0, label="excellent",
            open_alerts=0,
        )

        # Property 2: new (single snapshot)
        _insert_health_snapshot(
            temp_db, 2, score=80.0, label="good",
        )

        from marketsentry.cross_site_lifecycle_health_trends import (
            summarize_lifecycle_health_trends,
        )

        summary = summarize_lifecycle_health_trends(temp_db)
        assert summary.properties_with_snapshots == 2
        assert summary.improved_count >= 1
        assert summary.new_count >= 1

    def test_empty_summary(self, temp_db):
        """Empty database returns valid summary."""
        from marketsentry.cross_site_lifecycle_health_trends import (
            summarize_lifecycle_health_trends,
        )

        summary = summarize_lifecycle_health_trends(temp_db)
        assert summary.properties_with_snapshots == 0


# ── CLI Commands ──

class TestCLISnapshot:
    """CLI snapshot-cross-site-lifecycle-health tests."""

    def test_cli_snapshot_runs(self, temp_db):
        """Snapshot CLI command runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        runner = CliRunner()
        result = runner.invoke(
            app, [
                "snapshot-cross-site-lifecycle-health",
                "--db", temp_db,
                "--force",
            ],
        )
        assert result.exit_code == 0
        assert "Properties scanned" in result.output
        assert "Snapshots created" in result.output


class TestCLITrendReport:
    """CLI export-cross-site-lifecycle-health-trend-report tests."""

    def test_cli_trend_report_runs(self, temp_db, temp_exports_dir):
        """Trend report CLI command runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        _insert_watched_property(temp_db, 1)
        _insert_health_snapshot(temp_db, 1, score=100.0)

        runner = CliRunner()
        result = runner.invoke(
            app, [
                "export-cross-site-lifecycle-health-trend-report",
                "--db", temp_db,
                "--output-dir", temp_exports_dir,
            ],
        )
        assert result.exit_code == 0


class TestCLITrendSummary:
    """CLI cross-site-lifecycle-health-trend-summary tests."""

    def test_cli_trend_summary_runs(self, temp_db):
        """Trend summary CLI command runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        _insert_watched_property(temp_db, 1)
        _insert_health_snapshot(temp_db, 1, score=100.0)

        runner = CliRunner()
        result = runner.invoke(
            app, [
                "cross-site-lifecycle-health-trend-summary",
                "--db", temp_db,
            ],
        )
        assert result.exit_code == 0
        assert "Properties with health snapshots" in result.output


# ── Dashboard ──

class TestDashboard:
    """Dashboard lifecycle health trends section tests."""

    def test_dashboard_imports(self):
        """Dashboard module imports without error."""
        import marketsentry.dashboard_app  # noqa: F401

    def test_dashboard_health_trends_section(self):
        """Dashboard source contains health trends section."""
        src = Path(
            "src/marketsentry/dashboard_app.py"
        ).read_text(encoding="utf-8")
        assert "Lifecycle Health Trends" in src
        assert "summarize_lifecycle_health_trends" in src


# ── Scheduled Script ──

class TestScheduledScript:
    """Scheduled script safety tests."""

    def test_script_exists(self):
        """Scheduled script file exists."""
        assert Path(
            "scripts/run_lifecycle_health_report.bat"
        ).exists()

    def test_script_no_live_retrieval(self):
        """Script does not contain live retrieval commands."""
        content = Path(
            "scripts/run_lifecycle_health_report.bat"
        ).read_text(encoding="utf-8").lower()
        assert "redfin" not in content
        assert "zillow" not in content
        assert "realtor" not in content
        assert "compass" not in content
        assert "homes.com" not in content

    def test_script_no_mutation(self):
        """Script does not contain mutation commands."""
        content = Path(
            "scripts/run_lifecycle_health_report.bat"
        ).read_text(encoding="utf-8").lower()
        assert "apply-triage" not in content
        assert "archive-alerts" not in content
        assert "import-triage" not in content


# ── No Alert/Watchlist Mutation ──

class TestNoMutation:
    """Health trend operations must not mutate state."""

    def test_no_alert_mutation(self, temp_db):
        """Creating health snapshots does not change alert status."""
        from marketsentry.cross_site_lifecycle_health_trends import (
            create_lifecycle_health_snapshots,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, severity="high", status="open")

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        before = [dict(r) for r in conn.execute(
            "SELECT * FROM cross_site_trend_alerts"
        ).fetchall()]
        conn.close()

        create_lifecycle_health_snapshots(
            database_path=temp_db, force=True,
        )

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        after = [dict(r) for r in conn.execute(
            "SELECT * FROM cross_site_trend_alerts"
        ).fetchall()]
        conn.close()

        assert before == after

    def test_no_watchlist_mutation(self, temp_db):
        """Creating health snapshots does not change watchlist state."""
        from marketsentry.cross_site_lifecycle_health_trends import (
            create_lifecycle_health_snapshots,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        before = [dict(r) for r in conn.execute(
            "SELECT * FROM watched_properties"
        ).fetchall()]
        conn.close()

        create_lifecycle_health_snapshots(
            database_path=temp_db, force=True,
        )

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        after = [dict(r) for r in conn.execute(
            "SELECT * FROM watched_properties"
        ).fetchall()]
        conn.close()

        assert before == after


# ── No Redfin Source-of-Truth Overwrite ──

class TestNoRedfin:
    """Module must not overwrite Redfin source-of-truth fields."""

    def test_no_redfin_overwrite(self):
        """Module source does not update candidate/watchlist tables."""
        src = Path(
            "src/marketsentry/cross_site_lifecycle_health_trends.py"
        ).read_text(encoding="utf-8").lower()
        assert "update candidates" not in src
        assert "update watched_properties" not in src


# ── Quiet Gatekeeper Unchanged ──

class TestQuietGatekeeper:
    """Quiet Score gatekeeper must remain unchanged."""

    def test_no_quiet_score_reference(self):
        """Module does not reference quiet_score."""
        src = Path(
            "src/marketsentry/cross_site_lifecycle_health_trends.py"
        ).read_text(encoding="utf-8").lower()
        assert "quiet_score" not in src
        assert "vibrancy_score" not in src


# ── No Walkability ──

class TestNoWalkability:
    """No walkability fields added."""

    def test_no_walkability_in_module(self):
        """Module does not contain walkability references."""
        src = Path(
            "src/marketsentry/cross_site_lifecycle_health_trends.py"
        ).read_text(encoding="utf-8").lower()
        assert "walkability" not in src
        assert "walk_score" not in src

    def test_no_walkability_in_models(self):
        """M37 models do not contain walkability fields."""
        src = Path("src/marketsentry/models.py").read_text(
            encoding="utf-8",
        )
        m37_start = src.find("Milestone 37")
        if m37_start > 0:
            m37_section = src[m37_start:].lower()
            assert "walkability" not in m37_section


# ── No Real Network Calls ──

class TestNoNetworkCalls:
    """Tests must not make real network calls."""

    def test_no_requests_in_module(self):
        """Module does not import requests."""
        src = Path(
            "src/marketsentry/cross_site_lifecycle_health_trends.py"
        ).read_text(encoding="utf-8")
        assert "import requests" not in src
        assert "requests.get" not in src

    def test_no_urllib_in_module(self):
        """Module does not use urllib for HTTP calls."""
        src = Path(
            "src/marketsentry/cross_site_lifecycle_health_trends.py"
        ).read_text(encoding="utf-8")
        assert "urllib.request" not in src


# ── No Browser Automation ──

class TestNoBrowserAutomation:
    """Module must not contain browser automation references."""

    def test_no_browser_automation(self):
        """Module has no browser automation imports."""
        src = Path(
            "src/marketsentry/cross_site_lifecycle_health_trends.py"
        ).read_text(encoding="utf-8").lower()
        assert "from playwright" not in src
        assert "from selenium" not in src
        assert "import playwright" not in src
        assert "import selenium" not in src
        assert "captcha" not in src


# ── Models ──

class TestModels:
    """M37 model validation."""

    def test_health_snapshot_model(self):
        """CrossSiteLifecycleHealthSnapshot initializes with defaults."""
        snap = CrossSiteLifecycleHealthSnapshot()
        assert snap.lifecycle_health_score == 100.0
        assert snap.lifecycle_health_label == "excellent"
        assert snap.property_id == 0

    def test_trend_change_model(self):
        """CrossSiteLifecycleHealthTrendChange initializes correctly."""
        tc = CrossSiteLifecycleHealthTrendChange(
            property_id=1,
            current_health_score=80.0,
            previous_health_score=60.0,
            health_score_delta=20.0,
            trend_direction="improved",
        )
        assert tc.health_score_delta == 20.0
        assert tc.trend_direction == "improved"

    def test_trend_report_row_model(self):
        """CrossSiteLifecycleHealthTrendReportRow has expected fields."""
        row = CrossSiteLifecycleHealthTrendReportRow()
        assert row.property_id == 0
        assert row.trend_direction == "stable"

    def test_trend_summary_model(self):
        """CrossSiteLifecycleHealthTrendSummary has expected fields."""
        s = CrossSiteLifecycleHealthTrendSummary()
        assert s.improved_count == 0
        assert s.degraded_count == 0

    def test_snapshot_run_result_model(self):
        """CrossSiteLifecycleHealthSnapshotRunResult has expected fields."""
        r = CrossSiteLifecycleHealthSnapshotRunResult()
        assert r.properties_scanned == 0
        assert r.snapshots_created == 0
        assert r.snapshots_skipped == 0


# ── Multiple Properties ──

class TestMultipleProperties:
    """Multiple property trend tracking."""

    def test_multiple_properties_trend(self, temp_db):
        """Trends tracked for multiple properties."""
        _insert_watched_property(temp_db, 1)
        _insert_watched_property(temp_db, 2, address="456 Oak Ave")

        yesterday = (datetime.now() - timedelta(days=1)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        _insert_health_snapshot(
            temp_db, 1, score=80.0, captured_at=yesterday,
        )
        _insert_health_snapshot(temp_db, 1, score=90.0)
        _insert_health_snapshot(
            temp_db, 2, score=70.0, captured_at=yesterday,
        )
        _insert_health_snapshot(temp_db, 2, score=50.0)

        from marketsentry.cross_site_lifecycle_health_trends import (
            summarize_lifecycle_health_trends,
        )

        summary = summarize_lifecycle_health_trends(temp_db)
        assert summary.properties_with_snapshots == 2
        assert summary.improved_count + summary.degraded_count == 2


# ── Trend Report Row Count ──

class TestTrendReportRows:
    """Trend report has correct row count."""

    def test_report_row_count(self, temp_db, temp_exports_dir):
        """Report has one row per property with snapshots."""
        _insert_watched_property(temp_db, 1)
        _insert_watched_property(temp_db, 2, address="456 Oak Ave")
        _insert_health_snapshot(temp_db, 1, score=90.0)
        _insert_health_snapshot(temp_db, 2, score=80.0)

        from marketsentry.cross_site_lifecycle_health_trends import (
            export_lifecycle_health_trend_report,
        )

        path = export_lifecycle_health_trend_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
        )
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
