"""Tests for Milestone 35: Alert Lifecycle Trend Snapshots and Throughput Metrics."""

import csv
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from marketsentry.database import execute_query, get_connection, init_db, table_exists
from marketsentry.models import (
    CrossSiteAlertLifecycleSnapshot,
    CrossSiteAlertLifecycleSnapshotRunResult,
    CrossSiteAlertLifecycleTrendChange,
    CrossSiteAlertLifecycleTrendReportRow,
    CrossSiteAlertThroughputMetrics,
    CrossSiteAlertTimeToActionMetrics,
)


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database with full schema."""
    db_path = str(tmp_path / "test_m35.db")
    init_db(db_path)
    yield db_path


@pytest.fixture
def temp_exports_dir(tmp_path):
    """Create a temporary exports directory."""
    exports = tmp_path / "exports"
    exports.mkdir()
    return str(exports)


def _insert_candidate(
    db_path, address="123 Test St", city="Testville", zip_code="92000",
):
    """Insert a candidate record and return candidate_id."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO candidate_review_queue
        (discovery_date, source_site, source_search_url, redfin_url,
         address, city, zip, review_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "2025-01-01", "redfin", "http://test.com",
            "http://redfin.com/test", address, city, zip_code, "pending",
        ),
    )
    conn.commit()
    cid = cursor.lastrowid
    conn.close()
    return cid


def _insert_watched_property(
    db_path, address="123 Test St", city="Testville", zip_code="92000",
):
    """Insert a watched property and return property_id."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO watched_properties
        (first_saved_date, address, city, zip, active_watch_status)
        VALUES (?, ?, ?, ?, ?)""",
        ("2025-01-01", address, city, zip_code, 1),
    )
    conn.commit()
    pid = cursor.lastrowid
    conn.close()
    return pid


def _insert_alert(
    db_path, property_id, alert_type="price_drop", severity="medium",
    status="open", created_at=None,
):
    """Insert a trend alert and return alert_id."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    created = created_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """INSERT INTO cross_site_trend_alerts
        (property_id, alert_type, severity, alert_status, created_at)
        VALUES (?, ?, ?, ?, ?)""",
        (property_id, alert_type, severity, status, created),
    )
    conn.commit()
    aid = cursor.lastrowid
    conn.close()
    return aid


def _insert_triage_action(
    db_path, alert_id, property_id, action, previous_status,
    new_status, triage_export_id="triage_001",
    triage_notes="", applied_at=None,
):
    """Insert a triage action record."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    applied = applied_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """INSERT INTO cross_site_alert_triage_actions
        (triage_export_id, alert_id, property_id, action, previous_status,
         new_status, triage_notes, applied_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            triage_export_id, alert_id, property_id, action,
            previous_status, new_status, triage_notes, applied,
        ),
    )
    conn.commit()
    conn.close()


# ── Schema Tests ──


class TestSchemaM35:
    """Schema migration tests for Milestone 35."""

    def test_lifecycle_snapshots_table_created(self, temp_db):
        """Table cross_site_alert_lifecycle_snapshots is created by init_db."""
        assert table_exists(
            "cross_site_alert_lifecycle_snapshots", database_path=temp_db,
        )

    def test_migration_idempotent(self, temp_db):
        """Re-running init_db does not fail."""
        init_db(temp_db)
        assert table_exists(
            "cross_site_alert_lifecycle_snapshots", database_path=temp_db,
        )

    def test_snapshot_table_columns(self, temp_db):
        """Table has all required columns."""
        query = "PRAGMA table_info(cross_site_alert_lifecycle_snapshots)"
        rows = execute_query(query, database_path=temp_db)
        col_names = {dict(r)["name"] for r in rows}
        expected = {
            "lifecycle_snapshot_id", "captured_at", "total_alerts",
            "open_alerts", "acknowledged_alerts", "resolved_alerts",
            "archived_alerts", "high_or_critical_open_alerts",
            "lifecycle_gap_count", "stale_open_alert_count",
            "needs_reparse_count", "needs_manual_review_count",
            "no_archive_count", "total_lifecycle_events",
            "triage_actions_count", "archive_actions_count",
            "expiration_actions_count",
            "avg_time_to_first_triage_days",
            "median_time_to_first_triage_days",
            "avg_time_to_resolution_days",
            "median_time_to_resolution_days",
            "avg_time_to_archive_days", "median_time_to_archive_days",
            "triage_throughput_7d", "resolution_throughput_7d",
            "archive_throughput_7d",
            "active_property_count", "property_count_with_open_alerts",
            "property_count_with_lifecycle_gaps",
            "notes", "created_at",
        }
        assert expected.issubset(col_names)


# ── Metrics Calculation Tests ──


class TestCalculateMetrics:
    """Tests for calculate_lifecycle_snapshot_metrics."""

    def test_no_alerts(self, temp_db):
        """Empty database returns zero counts."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_snapshot_metrics,
        )

        snapshot = calculate_lifecycle_snapshot_metrics(
            database_path=temp_db,
        )
        assert snapshot.total_alerts == 0
        assert snapshot.open_alerts == 0
        assert snapshot.resolved_alerts == 0
        assert snapshot.archived_alerts == 0

    def test_with_open_resolved_archived(self, temp_db):
        """Counts match inserted alert statuses."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_snapshot_metrics,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")
        _insert_alert(temp_db, pid, status="open")
        _insert_alert(temp_db, pid, status="resolved")
        _insert_alert(temp_db, pid, status="archived")
        _insert_alert(temp_db, pid, status="acknowledged")

        snapshot = calculate_lifecycle_snapshot_metrics(
            database_path=temp_db,
        )
        assert snapshot.total_alerts == 5
        assert snapshot.open_alerts == 2
        assert snapshot.resolved_alerts == 1
        assert snapshot.archived_alerts == 1
        assert snapshot.acknowledged_alerts == 1

    def test_high_critical_open(self, temp_db):
        """High/critical open alerts are counted separately."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_snapshot_metrics,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="high", status="open")
        _insert_alert(temp_db, pid, severity="critical", status="open")
        _insert_alert(temp_db, pid, severity="medium", status="open")

        snapshot = calculate_lifecycle_snapshot_metrics(
            database_path=temp_db,
        )
        assert snapshot.high_or_critical_open_alerts == 2

    def test_stale_open_alerts(self, temp_db):
        """Open alerts older than 7 days are counted as stale."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_snapshot_metrics,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (
            datetime.utcnow() - timedelta(days=10)
        ).strftime("%Y-%m-%d %H:%M:%S")
        _insert_alert(temp_db, pid, status="open", created_at=old_date)
        _insert_alert(temp_db, pid, status="open")  # Recent

        snapshot = calculate_lifecycle_snapshot_metrics(
            database_path=temp_db,
        )
        assert snapshot.stale_open_alert_count == 1

    def test_active_property_count(self, temp_db):
        """Active property count and property-with-open-alerts count."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_snapshot_metrics,
        )

        _insert_watched_property(temp_db)
        _insert_watched_property(temp_db, address="456 Test St")
        pid = _insert_watched_property(temp_db, address="789 Test St")
        _insert_alert(temp_db, pid, status="open")

        snapshot = calculate_lifecycle_snapshot_metrics(
            database_path=temp_db,
        )
        assert snapshot.active_property_count == 3
        assert snapshot.property_count_with_open_alerts == 1

    def test_lifecycle_events_counted(self, temp_db):
        """Total lifecycle events counted from triage actions."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_snapshot_metrics,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid)
        _insert_triage_action(
            temp_db, aid, pid, "acknowledge", "open", "acknowledged",
        )
        _insert_triage_action(
            temp_db, aid, pid, "resolve", "acknowledged", "resolved",
        )

        snapshot = calculate_lifecycle_snapshot_metrics(
            database_path=temp_db,
        )
        assert snapshot.total_lifecycle_events == 2


# ── Time-to-Action Tests ──


class TestTimeToAction:
    """Tests for calculate_time_to_action_metrics."""

    def test_no_actions(self, temp_db):
        """No actions returns None metrics with zero counts."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_time_to_action_metrics,
        )

        metrics = calculate_time_to_action_metrics(database_path=temp_db)
        assert metrics.avg_time_to_first_triage_days is None
        assert metrics.triage_count == 0

    def test_time_to_first_triage(self, temp_db):
        """Time-to-first-triage computed from alert creation to first action."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_time_to_action_metrics,
        )

        pid = _insert_watched_property(temp_db)
        created = (
            datetime.utcnow() - timedelta(days=3)
        ).strftime("%Y-%m-%d %H:%M:%S")
        aid = _insert_alert(
            temp_db, pid, status="acknowledged", created_at=created,
        )
        action_at = (
            datetime.utcnow() - timedelta(days=1)
        ).strftime("%Y-%m-%d %H:%M:%S")
        _insert_triage_action(
            temp_db, aid, pid, "acknowledge", "open", "acknowledged",
            applied_at=action_at,
        )

        metrics = calculate_time_to_action_metrics(database_path=temp_db)
        assert metrics.triage_count == 1
        assert metrics.avg_time_to_first_triage_days is not None
        assert metrics.avg_time_to_first_triage_days > 0

    def test_time_to_resolution(self, temp_db):
        """Time-to-resolution computed from alert creation to resolved."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_time_to_action_metrics,
        )

        pid = _insert_watched_property(temp_db)
        created = (
            datetime.utcnow() - timedelta(days=5)
        ).strftime("%Y-%m-%d %H:%M:%S")
        aid = _insert_alert(
            temp_db, pid, status="resolved", created_at=created,
        )
        resolved_at = (
            datetime.utcnow() - timedelta(days=2)
        ).strftime("%Y-%m-%d %H:%M:%S")
        _insert_triage_action(
            temp_db, aid, pid, "resolve", "open", "resolved",
            applied_at=resolved_at,
        )

        metrics = calculate_time_to_action_metrics(database_path=temp_db)
        assert metrics.resolution_count == 1
        assert metrics.avg_time_to_resolution_days is not None
        assert metrics.avg_time_to_resolution_days > 0

    def test_time_to_archive(self, temp_db):
        """Time-to-archive computed from alert creation to archived."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_time_to_action_metrics,
        )

        pid = _insert_watched_property(temp_db)
        created = (
            datetime.utcnow() - timedelta(days=7)
        ).strftime("%Y-%m-%d %H:%M:%S")
        aid = _insert_alert(
            temp_db, pid, status="archived", created_at=created,
        )
        archived_at = (
            datetime.utcnow() - timedelta(days=1)
        ).strftime("%Y-%m-%d %H:%M:%S")
        _insert_triage_action(
            temp_db, aid, pid, "archive", "resolved", "archived",
            triage_export_id="archive_001", applied_at=archived_at,
        )

        metrics = calculate_time_to_action_metrics(database_path=temp_db)
        assert metrics.archive_count == 1
        assert metrics.avg_time_to_archive_days is not None
        assert metrics.avg_time_to_archive_days > 0

    def test_skipped_count(self, temp_db):
        """Alerts without actions are counted as skipped."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_time_to_action_metrics,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")

        metrics = calculate_time_to_action_metrics(database_path=temp_db)
        assert metrics.triage_skipped == 1
        assert metrics.resolution_skipped == 1
        assert metrics.archive_skipped == 1

    def test_median_computed(self, temp_db):
        """Median is computed when multiple data points exist."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_time_to_action_metrics,
        )

        pid = _insert_watched_property(temp_db)
        for days_ago in [10, 8, 6]:
            created = (
                datetime.utcnow() - timedelta(days=days_ago)
            ).strftime("%Y-%m-%d %H:%M:%S")
            aid = _insert_alert(
                temp_db, pid, status="acknowledged", created_at=created,
            )
            action_at = (
                datetime.utcnow() - timedelta(days=days_ago - 2)
            ).strftime("%Y-%m-%d %H:%M:%S")
            _insert_triage_action(
                temp_db, aid, pid, "acknowledge", "open", "acknowledged",
                applied_at=action_at,
            )

        metrics = calculate_time_to_action_metrics(database_path=temp_db)
        assert metrics.triage_count == 3
        assert metrics.median_time_to_first_triage_days is not None


# ── Throughput Tests ──


class TestThroughput:
    """Tests for calculate_throughput_metrics."""

    def test_no_actions(self, temp_db):
        """No actions returns zero throughput."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_throughput_metrics,
        )

        metrics = calculate_throughput_metrics(database_path=temp_db)
        assert metrics.triage_throughput_7d == 0
        assert metrics.resolution_throughput_7d == 0
        assert metrics.archive_throughput_7d == 0

    def test_7d_throughput(self, temp_db):
        """Recent actions are counted in 7-day throughput."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_throughput_metrics,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid)

        recent = (
            datetime.utcnow() - timedelta(days=2)
        ).strftime("%Y-%m-%d %H:%M:%S")
        _insert_triage_action(
            temp_db, aid, pid, "acknowledge", "open", "acknowledged",
            triage_export_id="triage_001", applied_at=recent,
        )
        _insert_triage_action(
            temp_db, aid, pid, "resolve", "acknowledged", "resolved",
            triage_export_id="triage_002", applied_at=recent,
        )
        _insert_triage_action(
            temp_db, aid, pid, "archive", "resolved", "archived",
            triage_export_id="archive_001", applied_at=recent,
        )

        metrics = calculate_throughput_metrics(database_path=temp_db)
        assert metrics.triage_throughput_7d == 2  # Both triage_ prefixed
        assert metrics.resolution_throughput_7d == 1
        assert metrics.archive_throughput_7d == 1

    def test_old_actions_not_counted(self, temp_db):
        """Actions older than 7 days are not counted."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_throughput_metrics,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid)

        old = (
            datetime.utcnow() - timedelta(days=10)
        ).strftime("%Y-%m-%d %H:%M:%S")
        _insert_triage_action(
            temp_db, aid, pid, "acknowledge", "open", "acknowledged",
            triage_export_id="triage_001", applied_at=old,
        )

        metrics = calculate_throughput_metrics(database_path=temp_db)
        assert metrics.triage_throughput_7d == 0

    def test_30d_throughput(self, temp_db):
        """Actions within 30 days are counted for 30d throughput."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_throughput_metrics,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid)

        recent_15d = (
            datetime.utcnow() - timedelta(days=15)
        ).strftime("%Y-%m-%d %H:%M:%S")
        _insert_triage_action(
            temp_db, aid, pid, "acknowledge", "open", "acknowledged",
            triage_export_id="triage_001", applied_at=recent_15d,
        )

        metrics = calculate_throughput_metrics(database_path=temp_db)
        assert metrics.triage_throughput_7d == 0
        assert metrics.triage_throughput_30d == 1


# ── Snapshot Creation Tests ──


class TestSnapshotCreation:
    """Tests for create_alert_lifecycle_snapshot."""

    def test_create_snapshot(self, temp_db):
        """Snapshot is created and returns valid result."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            create_alert_lifecycle_snapshot,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")

        result = create_alert_lifecycle_snapshot(database_path=temp_db)
        assert not result.was_skipped
        assert result.snapshot_id > 0
        assert result.snapshot is not None
        assert result.snapshot.total_alerts == 1

    def test_same_day_no_change_skip(self, temp_db):
        """Same-day snapshot with no material change is skipped."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            create_alert_lifecycle_snapshot,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")

        r1 = create_alert_lifecycle_snapshot(database_path=temp_db)
        assert not r1.was_skipped

        r2 = create_alert_lifecycle_snapshot(database_path=temp_db)
        assert r2.was_skipped
        assert "no material change" in r2.skip_reason.lower()

    def test_force_creates_new_row(self, temp_db):
        """Force flag creates new snapshot even on same day."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            create_alert_lifecycle_snapshot,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")

        r1 = create_alert_lifecycle_snapshot(database_path=temp_db)
        r2 = create_alert_lifecycle_snapshot(
            database_path=temp_db, force=True,
        )
        assert not r2.was_skipped
        assert r2.snapshot_id > r1.snapshot_id

    def test_material_change_creates_new_row(self, temp_db):
        """Material change allows same-day snapshot creation."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            create_alert_lifecycle_snapshot,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")

        r1 = create_alert_lifecycle_snapshot(database_path=temp_db)
        assert not r1.was_skipped

        _insert_alert(temp_db, pid, status="open")

        r2 = create_alert_lifecycle_snapshot(database_path=temp_db)
        assert not r2.was_skipped
        assert r2.snapshot_id > r1.snapshot_id

    def test_snapshot_persisted(self, temp_db):
        """Snapshot data is persisted in the database."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            create_alert_lifecycle_snapshot,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")
        _insert_alert(temp_db, pid, status="resolved")

        create_alert_lifecycle_snapshot(database_path=temp_db)

        rows = execute_query(
            "SELECT * FROM cross_site_alert_lifecycle_snapshots",
            database_path=temp_db,
        )
        assert len(rows) == 1
        d = dict(rows[0])
        assert d["total_alerts"] == 2
        assert d["open_alerts"] == 1
        assert d["resolved_alerts"] == 1


# ── Snapshot Retrieval Tests ──


class TestSnapshotRetrieval:
    """Tests for get_latest/previous_lifecycle_snapshot."""

    def test_latest_snapshot(self, temp_db):
        """Latest snapshot is returned after creation."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            create_alert_lifecycle_snapshot,
            get_latest_lifecycle_snapshot,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")
        create_alert_lifecycle_snapshot(database_path=temp_db)

        latest = get_latest_lifecycle_snapshot(database_path=temp_db)
        assert latest is not None
        assert latest.lifecycle_snapshot_id > 0

    def test_previous_snapshot(self, temp_db):
        """Previous snapshot is the second-most-recent."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            create_alert_lifecycle_snapshot,
            get_previous_lifecycle_snapshot,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")

        create_alert_lifecycle_snapshot(
            database_path=temp_db, force=True,
        )
        _insert_alert(temp_db, pid, status="resolved")
        create_alert_lifecycle_snapshot(
            database_path=temp_db, force=True,
        )

        prev = get_previous_lifecycle_snapshot(database_path=temp_db)
        assert prev is not None

    def test_no_previous_when_single(self, temp_db):
        """No previous snapshot when only one exists."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            create_alert_lifecycle_snapshot,
            get_previous_lifecycle_snapshot,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")
        create_alert_lifecycle_snapshot(database_path=temp_db)

        prev = get_previous_lifecycle_snapshot(database_path=temp_db)
        assert prev is None

    def test_latest_none_when_empty(self, temp_db):
        """Latest returns None when no snapshots exist."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            get_latest_lifecycle_snapshot,
        )

        latest = get_latest_lifecycle_snapshot(database_path=temp_db)
        assert latest is None


# ── Trend Change Tests ──


class TestTrendChange:
    """Tests for calculate_lifecycle_trend_change."""

    def test_trend_improving(self):
        """Decreasing bad metrics signals improving trend."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_trend_change,
        )

        current = CrossSiteAlertLifecycleSnapshot(
            lifecycle_snapshot_id=2, open_alerts=3,
            lifecycle_gap_count=1, stale_open_alert_count=0,
            total_alerts=10,
        )
        previous = CrossSiteAlertLifecycleSnapshot(
            lifecycle_snapshot_id=1, open_alerts=5,
            lifecycle_gap_count=3, stale_open_alert_count=2,
            total_alerts=10,
        )
        change = calculate_lifecycle_trend_change(current, previous)
        assert change.trend_direction == "improving"
        assert change.open_alerts_delta == -2

    def test_trend_worsening(self):
        """Increasing bad metrics signals worsening trend."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_trend_change,
        )

        current = CrossSiteAlertLifecycleSnapshot(
            lifecycle_snapshot_id=2, open_alerts=8,
            lifecycle_gap_count=5, stale_open_alert_count=4,
            total_alerts=15,
        )
        previous = CrossSiteAlertLifecycleSnapshot(
            lifecycle_snapshot_id=1, open_alerts=3,
            lifecycle_gap_count=1, stale_open_alert_count=0,
            total_alerts=10,
        )
        change = calculate_lifecycle_trend_change(current, previous)
        assert change.trend_direction == "worsening"

    def test_trend_stable(self):
        """No change signals stable trend."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_trend_change,
        )

        current = CrossSiteAlertLifecycleSnapshot(
            lifecycle_snapshot_id=2, open_alerts=3,
            lifecycle_gap_count=1, stale_open_alert_count=1,
            total_alerts=10,
        )
        previous = CrossSiteAlertLifecycleSnapshot(
            lifecycle_snapshot_id=1, open_alerts=3,
            lifecycle_gap_count=1, stale_open_alert_count=1,
            total_alerts=10,
        )
        change = calculate_lifecycle_trend_change(current, previous)
        assert change.trend_direction == "stable"

    def test_trend_summary_generated(self):
        """Trend summary text is generated on change."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_trend_change,
        )

        current = CrossSiteAlertLifecycleSnapshot(
            lifecycle_snapshot_id=2, open_alerts=5, total_alerts=10,
        )
        previous = CrossSiteAlertLifecycleSnapshot(
            lifecycle_snapshot_id=1, open_alerts=3, total_alerts=10,
        )
        change = calculate_lifecycle_trend_change(current, previous)
        assert "Open alerts" in change.trend_summary

    def test_recommended_action_on_worsening(self):
        """Worsening trend recommends review."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_trend_change,
        )

        current = CrossSiteAlertLifecycleSnapshot(
            lifecycle_snapshot_id=2, open_alerts=10,
            lifecycle_gap_count=5, stale_open_alert_count=5,
            total_alerts=20,
        )
        previous = CrossSiteAlertLifecycleSnapshot(
            lifecycle_snapshot_id=1, open_alerts=3,
            lifecycle_gap_count=1, stale_open_alert_count=0,
            total_alerts=10,
        )
        change = calculate_lifecycle_trend_change(current, previous)
        assert "Review" in change.recommended_review_action


# ── Trend Report Export Tests ──


class TestTrendReport:
    """Tests for export_alert_lifecycle_trend_report."""

    def test_export_with_two_snapshots(self, temp_db, temp_exports_dir):
        """Export with two snapshots produces valid CSV."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            create_alert_lifecycle_snapshot,
            export_alert_lifecycle_trend_report,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")
        create_alert_lifecycle_snapshot(
            database_path=temp_db, force=True,
        )
        _insert_alert(temp_db, pid, status="resolved")
        create_alert_lifecycle_snapshot(
            database_path=temp_db, force=True,
        )

        path = export_alert_lifecycle_trend_report(
            database_path=temp_db, output_dir=temp_exports_dir,
        )
        assert path is not None
        assert Path(path).exists()
        assert "cross_site_alert_lifecycle_trends_" in path

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert "trend_direction" in rows[0]

    def test_export_no_snapshots(self, temp_db, temp_exports_dir):
        """Export returns None when no snapshots exist."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            export_alert_lifecycle_trend_report,
        )

        path = export_alert_lifecycle_trend_report(
            database_path=temp_db, output_dir=temp_exports_dir,
        )
        assert path is None

    def test_export_single_snapshot(self, temp_db, temp_exports_dir):
        """Export with single snapshot uses baseline direction."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            create_alert_lifecycle_snapshot,
            export_alert_lifecycle_trend_report,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")
        create_alert_lifecycle_snapshot(database_path=temp_db)

        path = export_alert_lifecycle_trend_report(
            database_path=temp_db, output_dir=temp_exports_dir,
        )
        assert path is not None
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["trend_direction"] == "baseline"

    def test_export_csv_has_required_columns(self, temp_db, temp_exports_dir):
        """Exported CSV contains all required column headers."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            TREND_REPORT_FIELDNAMES,
            create_alert_lifecycle_snapshot,
            export_alert_lifecycle_trend_report,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")
        create_alert_lifecycle_snapshot(database_path=temp_db)

        path = export_alert_lifecycle_trend_report(
            database_path=temp_db, output_dir=temp_exports_dir,
        )
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)
        for field in TREND_REPORT_FIELDNAMES:
            assert field in row


# ── CLI Tests ──


class TestCLI:
    """Tests for CLI commands."""

    def test_snapshot_cli(self, temp_db):
        """CLI snapshot command runs successfully."""
        from typer.testing import CliRunner

        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "snapshot-cross-site-alert-lifecycle", "--db", temp_db,
        ])
        assert result.exit_code == 0

    def test_snapshot_cli_force(self, temp_db):
        """CLI snapshot with --force runs successfully twice."""
        from typer.testing import CliRunner

        from marketsentry.cli import app

        runner = CliRunner()
        r1 = runner.invoke(app, [
            "snapshot-cross-site-alert-lifecycle", "--db", temp_db,
        ])
        assert r1.exit_code == 0

        r2 = runner.invoke(app, [
            "snapshot-cross-site-alert-lifecycle", "--db", temp_db,
            "--force",
        ])
        assert r2.exit_code == 0

    def test_export_trend_report_cli(self, temp_db, temp_exports_dir):
        """CLI export command runs after snapshot creation."""
        from typer.testing import CliRunner

        from marketsentry.cli import app

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")

        runner = CliRunner()
        runner.invoke(app, [
            "snapshot-cross-site-alert-lifecycle", "--db", temp_db,
        ])

        result = runner.invoke(app, [
            "export-cross-site-alert-lifecycle-trend-report",
            "--db", temp_db,
            "--output-dir", temp_exports_dir,
        ])
        assert result.exit_code == 0

    def test_snapshot_cli_shows_skipped(self, temp_db):
        """CLI shows skipped message on same-day no-change."""
        from typer.testing import CliRunner

        from marketsentry.cli import app

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")

        runner = CliRunner()
        runner.invoke(app, [
            "snapshot-cross-site-alert-lifecycle", "--db", temp_db,
        ])
        r2 = runner.invoke(app, [
            "snapshot-cross-site-alert-lifecycle", "--db", temp_db,
        ])
        assert r2.exit_code == 0
        assert "Skipped" in r2.output or "skipped" in r2.output.lower()


# ── Dashboard Tests ──


class TestDashboard:
    """Tests for dashboard lifecycle trends integration."""

    def test_dashboard_lifecycle_trends_section(self):
        """Dashboard module contains lifecycle trends section."""
        import marketsentry.dashboard_app as dash_mod

        source = Path(dash_mod.__file__).read_text(encoding="utf-8")
        assert "Lifecycle Trends" in source

    def test_dashboard_imports_metrics(self):
        """Dashboard imports from lifecycle metrics module."""
        import marketsentry.dashboard_app as dash_mod

        source = Path(dash_mod.__file__).read_text(encoding="utf-8")
        assert "get_latest_lifecycle_snapshot" in source


# ── Scheduled Script Tests ──


class TestScheduledScript:
    """Tests for scheduled script safety."""

    def test_script_exists(self):
        """Scheduled script file exists."""
        script = Path("scripts/run_alert_lifecycle_trend_report.bat")
        assert script.exists()

    def test_script_no_live_retrieval(self):
        """Script does not contain live retrieval commands."""
        script = Path("scripts/run_alert_lifecycle_trend_report.bat")
        content = script.read_text(encoding="utf-8").lower()
        assert "--force-live" not in content
        assert "force_live" not in content
        assert "live_retrieval" not in content
        assert "selenium" not in content
        assert "playwright" not in content

    def test_script_no_mutation_commands(self):
        """Script does not contain alert mutation commands."""
        script = Path("scripts/run_alert_lifecycle_trend_report.bat")
        content = script.read_text(encoding="utf-8").lower()
        assert "apply-triage" not in content
        assert "apply-archive" not in content
        assert "apply-expiration" not in content

    def test_script_writes_logs(self):
        """Script writes to logs/scheduled directory."""
        script = Path("scripts/run_alert_lifecycle_trend_report.bat")
        content = script.read_text(encoding="utf-8")
        assert "logs\\scheduled" in content or "logs/scheduled" in content


# ── Safety Tests ──


class TestSafety:
    """Tests verifying no mutations or rule violations."""

    def test_no_alert_mutation(self, temp_db):
        """Snapshot creation does not change alert status."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            create_alert_lifecycle_snapshot,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, status="open")
        create_alert_lifecycle_snapshot(database_path=temp_db)

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert dict(rows[0])["alert_status"] == "open"

    def test_no_watchlist_mutation(self, temp_db):
        """Snapshot creation does not change watchlist status."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            create_alert_lifecycle_snapshot,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, status="open")
        create_alert_lifecycle_snapshot(database_path=temp_db)

        rows = execute_query(
            "SELECT active_watch_status FROM watched_properties "
            "WHERE property_id = ?",
            (pid,), database_path=temp_db,
        )
        assert dict(rows[0])["active_watch_status"] == 1

    def test_no_redfin_overwrite(self):
        """Module does not overwrite Redfin source-of-truth fields."""
        import marketsentry.cross_site_alert_lifecycle_metrics as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "UPDATE watched_properties" not in source
        assert "UPDATE candidate_review_queue" not in source

    def test_quiet_gatekeeper_unchanged(self):
        """Module does not reference Quiet Score."""
        import marketsentry.cross_site_alert_lifecycle_metrics as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "quiet_score" not in source.lower()
        assert "vibrancy_score" not in source.lower()

    def test_no_walkability(self):
        """No walkability fields added."""
        import marketsentry.cross_site_alert_lifecycle_metrics as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "walkability" not in source.lower()
        assert "walk_score" not in source.lower()

    def test_no_network_calls(self):
        """Module does not make network calls."""
        import marketsentry.cross_site_alert_lifecycle_metrics as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "requests.get" not in source
        assert "requests.post" not in source
        assert "urllib.request" not in source
        assert "httpx" not in source

    def test_no_browser_automation(self):
        """Module does not use browser automation."""
        import marketsentry.cross_site_alert_lifecycle_metrics as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "selenium" not in source.lower()
        assert "playwright" not in source.lower()
        assert "captcha" not in source.lower()


# ── Model Tests ──


class TestModels:
    """Tests for Milestone 35 model classes."""

    def test_snapshot_model(self):
        """Snapshot model has correct defaults."""
        s = CrossSiteAlertLifecycleSnapshot()
        assert s.total_alerts == 0
        assert s.avg_time_to_resolution_days is None

    def test_throughput_model(self):
        """Throughput model has correct defaults."""
        t = CrossSiteAlertThroughputMetrics()
        assert t.triage_throughput_7d == 0
        assert t.triage_throughput_30d == 0

    def test_time_to_action_model(self):
        """TimeToAction model has correct defaults."""
        t = CrossSiteAlertTimeToActionMetrics()
        assert t.avg_time_to_first_triage_days is None
        assert t.triage_count == 0

    def test_trend_change_model(self):
        """TrendChange model has correct defaults."""
        t = CrossSiteAlertLifecycleTrendChange()
        assert t.trend_direction == "stable"
        assert t.total_alerts_delta == 0

    def test_trend_report_row_model(self):
        """TrendReportRow model has correct defaults."""
        t = CrossSiteAlertLifecycleTrendReportRow()
        assert t.trend_direction == "stable"

    def test_run_result_model(self):
        """RunResult model has correct defaults."""
        r = CrossSiteAlertLifecycleSnapshotRunResult()
        assert r.was_skipped is False
        assert r.snapshot is None


# ── Needs Reparse / Manual Review Tests ──


class TestBacklogCounts:
    """Tests for backlog marker counting."""

    def test_needs_reparse_counted(self, temp_db):
        """Alerts with needs_reparse notes are counted."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_snapshot_metrics,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, status="open")
        _insert_triage_action(
            temp_db, aid, pid, "acknowledge", "open", "acknowledged",
            triage_notes="needs_reparse: parser v2 needed",
        )

        snapshot = calculate_lifecycle_snapshot_metrics(
            database_path=temp_db,
        )
        assert snapshot.needs_reparse_count == 1

    def test_needs_manual_review_counted(self, temp_db):
        """Alerts with manual_review notes are counted."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_snapshot_metrics,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, status="open")
        _insert_triage_action(
            temp_db, aid, pid, "acknowledge", "open", "acknowledged",
            triage_notes="manual_review required",
        )

        snapshot = calculate_lifecycle_snapshot_metrics(
            database_path=temp_db,
        )
        assert snapshot.needs_manual_review_count == 1

    def test_no_archive_counted(self, temp_db):
        """Alerts with no_archive notes are counted."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_snapshot_metrics,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, status="open")
        _insert_triage_action(
            temp_db, aid, pid, "acknowledge", "open", "acknowledged",
            triage_notes="no_archive: keep for reference",
        )

        snapshot = calculate_lifecycle_snapshot_metrics(
            database_path=temp_db,
        )
        assert snapshot.no_archive_count == 1

    def test_action_counts_by_workflow(self, temp_db):
        """Actions counted by workflow prefix."""
        from marketsentry.cross_site_alert_lifecycle_metrics import (
            calculate_lifecycle_snapshot_metrics,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid)
        _insert_triage_action(
            temp_db, aid, pid, "acknowledge", "open", "acknowledged",
            triage_export_id="triage_001",
        )
        _insert_triage_action(
            temp_db, aid, pid, "archive", "resolved", "archived",
            triage_export_id="archive_001",
        )
        _insert_triage_action(
            temp_db, aid, pid, "expire", "open", "expired",
            triage_export_id="expiration_001",
        )

        snapshot = calculate_lifecycle_snapshot_metrics(
            database_path=temp_db,
        )
        assert snapshot.triage_actions_count == 1
        assert snapshot.archive_actions_count == 1
        assert snapshot.expiration_actions_count == 1
        assert snapshot.total_lifecycle_events == 3
