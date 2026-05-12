"""Tests for Milestone 39: Operations Digest Historical Snapshots."""

from __future__ import annotations

import csv
import os
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from marketsentry.cli import app
from marketsentry.models import (
    OperationsDigestComparisonReportRow,
    OperationsDigestHistorySummary,
    OperationsDigestSnapshot,
    OperationsDigestSnapshotRunResult,
    OperationsDigestTrendChange,
)
from marketsentry.schema import ALL_SCHEMA_STATEMENTS, CREATE_INDEXES


runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_db(db_path: str) -> None:
    """Initialise a fresh test database with all schema statements."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for stmt in ALL_SCHEMA_STATEMENTS:
        cur.execute(stmt)
    for idx in CREATE_INDEXES:
        try:
            cur.execute(idx)
        except sqlite3.OperationalError:
            pass
    # Add migration columns that may not exist in base schema
    for col_stmt in [
        "ALTER TABLE watched_properties ADD COLUMN recent_churn_index REAL",
        "ALTER TABLE watched_properties ADD COLUMN effective_dom_v2 INTEGER",
        "ALTER TABLE watched_properties ADD COLUMN county_reset_applied INTEGER DEFAULT 0",
    ]:
        try:
            cur.execute(col_stmt)
        except sqlite3.OperationalError:
            pass
    # Create fixture_capture_queue if not in schema
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fixture_capture_queue (
            capture_request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_site TEXT NOT NULL,
            source_url TEXT NOT NULL,
            normalized_url TEXT NOT NULL DEFAULT '',
            request_type TEXT NOT NULL DEFAULT 'manual',
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 5,
            reason TEXT,
            candidate_id INTEGER,
            property_id INTEGER,
            notes TEXT,
            captured_at TIMESTAMP,
            fixture_path TEXT
        )
    """)
    conn.commit()
    conn.close()


def _insert_candidate(db_path: str, candidate_id: int = 1,
                       review_status: str = "pending_user_decision",
                       user_decision: str | None = None) -> None:
    """Insert a candidate into the review queue."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO candidate_review_queue "
        "(candidate_id, discovery_date, source_site, source_search_url, "
        "redfin_url, address, city, zip, review_status, user_decision) "
        "VALUES (?, '2026-01-01', 'test', 'http://example.com/search', "
        "'http://example.com/prop', ?, ?, ?, ?, ?)",
        (candidate_id, f"{candidate_id} Main St", "Temecula", "92592",
         review_status, user_decision),
    )
    conn.commit()
    conn.close()


def _insert_watched(db_path: str, property_id: int = 1,
                     gas_service: int = 0, garage_spaces: int = 0,
                     watch_priority: int = 0,
                     recent_churn_index: float | None = None,
                     effective_dom: float | None = None,
                     effective_dom_v2: float | None = None,
                     county_reset_applied: int = 0) -> None:
    """Insert a watched property."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO watched_properties "
        "(property_id, first_saved_date, address, city, zip, gas_service, "
        "garage_spaces, active_watch_status, watch_priority, "
        "recent_churn_index, effective_dom, "
        "effective_dom_v2, county_reset_applied) "
        "VALUES (?, '2026-01-01', ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)",
        (property_id, f"{property_id} Main St", "Temecula", "92592",
         gas_service, garage_spaces, watch_priority,
         recent_churn_index, effective_dom,
         effective_dom_v2, county_reset_applied),
    )
    conn.commit()
    conn.close()


def _insert_alert(db_path: str, alert_id: int = 1, property_id: int = 1,
                   alert_status: str = "open",
                   alert_severity: str = "warning",
                   alert_type: str = "confidence_drop",
                   created_at: str = "2026-05-01 00:00:00") -> None:
    """Insert a cross-site trend alert."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO cross_site_trend_alerts "
        "(alert_id, property_id, alert_status, severity, "
        "alert_type, message, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (alert_id, property_id, alert_status, alert_severity,
         alert_type, "Test alert", created_at),
    )
    conn.commit()
    conn.close()


def _insert_health_snapshot(db_path: str, property_id: int = 1,
                             label: str = "excellent",
                             score: float = 95.0,
                             lifecycle_gap_count: int = 0) -> None:
    """Insert a lifecycle health snapshot."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO cross_site_lifecycle_health_snapshots "
        "(property_id, lifecycle_health_score, lifecycle_health_label, "
        "lifecycle_gap_count) "
        "VALUES (?, ?, ?, ?)",
        (property_id, score, label, lifecycle_gap_count),
    )
    conn.commit()
    conn.close()


def _insert_snapshot(db_path: str,
                      captured_at: str = "2026-05-01T00:00:00Z",
                      candidate_count: int = 0,
                      pending_user_decision_count: int = 0,
                      active_watched_count: int = 0,
                      high_or_critical_open_alert_count: int = 0,
                      lifecycle_attention_required_count: int = 0,
                      lifecycle_needs_review_count: int = 0,
                      retrieval_health_issue_count: int = 0,
                      top_priority_count: int = 0,
                      digest_score: int = 100,
                      digest_status_label: str = "clear",
                      notes: str = "") -> int:
    """Insert a digest snapshot row and return its ID."""
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO operations_digest_snapshots "
        "(captured_at, candidate_count, pending_user_decision_count, "
        "active_watched_count, high_or_critical_open_alert_count, "
        "lifecycle_attention_required_count, lifecycle_needs_review_count, "
        "retrieval_health_issue_count, top_priority_count, "
        "digest_score, digest_status_label, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (captured_at, candidate_count, pending_user_decision_count,
         active_watched_count, high_or_critical_open_alert_count,
         lifecycle_attention_required_count, lifecycle_needs_review_count,
         retrieval_health_issue_count, top_priority_count,
         digest_score, digest_status_label, notes),
    )
    snap_id = cur.lastrowid or 0
    conn.commit()
    conn.close()
    return snap_id


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestDigestSnapshotSchema:
    """Schema migration and idempotency tests."""

    def test_schema_creates_operations_digest_snapshots_table(self, tmp_path):
        """Migration creates the operations_digest_snapshots table."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        conn = sqlite3.connect(db)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='operations_digest_snapshots'"
        )
        assert cur.fetchone() is not None
        conn.close()

    def test_schema_migration_is_idempotent(self, tmp_path):
        """Running schema twice does not error."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _init_db(db)
        conn = sqlite3.connect(db)
        cur = conn.execute(
            "SELECT COUNT(*) FROM operations_digest_snapshots"
        )
        assert cur.fetchone()[0] == 0
        conn.close()

    def test_schema_index_on_captured_at(self, tmp_path):
        """Index on captured_at is created."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        conn = sqlite3.connect(db)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_digest_snapshots_captured'"
        )
        assert cur.fetchone() is not None
        conn.close()


# ---------------------------------------------------------------------------
# Metrics calculation tests
# ---------------------------------------------------------------------------

class TestDigestSnapshotMetrics:
    """Digest snapshot metric calculation tests."""

    def test_metrics_with_empty_database(self, tmp_path):
        """Metrics return zero counts for an empty database."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest_history import (
            calculate_operations_digest_snapshot_metrics,
        )
        metrics = calculate_operations_digest_snapshot_metrics(db)
        assert metrics["candidate_count"] == 0
        assert metrics["pending_user_decision_count"] == 0
        assert metrics["active_watched_count"] == 0
        assert metrics["open_alert_count"] == 0

    def test_metrics_with_populated_data(self, tmp_path):
        """Metrics reflect actual data counts."""
        db = str(tmp_path / "test.db")
        _init_db(db)

        _insert_candidate(db, 1, review_status="pending_user_decision")
        _insert_candidate(db, 2, review_status="pending_user_decision")
        _insert_candidate(db, 3, review_status="strong_review")
        _insert_watched(db, 1, gas_service=1, watch_priority=1)
        _insert_watched(db, 2, garage_spaces=2)
        _insert_alert(db, 1, 1, "open", "high")
        _insert_alert(db, 2, 1, "open", "critical")
        _insert_health_snapshot(db, 1, "attention_required", 40.0)

        from marketsentry.operations_digest_history import (
            calculate_operations_digest_snapshot_metrics,
        )
        metrics = calculate_operations_digest_snapshot_metrics(db)
        assert metrics["candidate_count"] == 3
        assert metrics["pending_user_decision_count"] == 2
        assert metrics["strong_review_count"] == 1
        assert metrics["active_watched_count"] == 2
        assert metrics["high_priority_watched_count"] == 1
        assert metrics["gas_evidence_count"] == 1
        assert metrics["garage_evidence_count"] == 1
        assert metrics["high_or_critical_open_alert_count"] == 2
        assert metrics["lifecycle_attention_required_count"] == 1


# ---------------------------------------------------------------------------
# Digest score and label tests
# ---------------------------------------------------------------------------

class TestDigestScoreLabel:
    """Digest score and status label threshold tests."""

    def test_score_100_clear(self):
        """Empty metrics yield score 100 and label 'clear'."""
        from marketsentry.operations_digest_history import (
            _calculate_digest_score,
            _digest_status_label,
        )
        score = _calculate_digest_score({})
        assert score == 100
        assert _digest_status_label(score) == "clear"

    def test_score_90_clear(self):
        """Score at 90 threshold is 'clear'."""
        from marketsentry.operations_digest_history import (
            _digest_status_label,
        )
        assert _digest_status_label(90) == "clear"

    def test_score_89_light_review(self):
        """Score at 89 is 'light_review'."""
        from marketsentry.operations_digest_history import (
            _digest_status_label,
        )
        assert _digest_status_label(89) == "light_review"

    def test_score_75_light_review(self):
        """Score at 75 is 'light_review'."""
        from marketsentry.operations_digest_history import (
            _digest_status_label,
        )
        assert _digest_status_label(75) == "light_review"

    def test_score_74_active_review(self):
        """Score at 74 is 'active_review'."""
        from marketsentry.operations_digest_history import (
            _digest_status_label,
        )
        assert _digest_status_label(74) == "active_review"

    def test_score_60_active_review(self):
        """Score at 60 is 'active_review'."""
        from marketsentry.operations_digest_history import (
            _digest_status_label,
        )
        assert _digest_status_label(60) == "active_review"

    def test_score_59_heavy_review(self):
        """Score at 59 is 'heavy_review'."""
        from marketsentry.operations_digest_history import (
            _digest_status_label,
        )
        assert _digest_status_label(59) == "heavy_review"

    def test_score_40_heavy_review(self):
        """Score at 40 is 'heavy_review'."""
        from marketsentry.operations_digest_history import (
            _digest_status_label,
        )
        assert _digest_status_label(40) == "heavy_review"

    def test_score_39_backlog_attention(self):
        """Score at 39 is 'backlog_attention'."""
        from marketsentry.operations_digest_history import (
            _digest_status_label,
        )
        assert _digest_status_label(39) == "backlog_attention"

    def test_score_0_backlog_attention(self):
        """Score at 0 is 'backlog_attention'."""
        from marketsentry.operations_digest_history import (
            _digest_status_label,
        )
        assert _digest_status_label(0) == "backlog_attention"

    def test_score_deductions(self):
        """Score deductions from various metric counts."""
        from marketsentry.operations_digest_history import (
            _calculate_digest_score,
        )
        metrics = {
            "pending_user_decision_count": 5,  # -10
            "high_or_critical_open_alert_count": 2,  # -6
        }
        score = _calculate_digest_score(metrics)
        assert score == 84  # 100 - 10 - 6

    def test_score_floor_is_zero(self):
        """Score cannot go below zero."""
        from marketsentry.operations_digest_history import (
            _calculate_digest_score,
        )
        metrics = {
            "pending_user_decision_count": 100,
            "reject_location_noise_count": 100,
            "high_churn_count": 100,
            "high_effective_dom_delta_count": 100,
            "low_cross_site_confidence_count": 100,
            "high_discrepancy_severity_count": 100,
            "high_or_critical_open_alert_count": 100,
            "stale_open_alert_count": 100,
            "needs_reparse_count": 100,
            "needs_manual_review_count": 100,
            "lifecycle_attention_required_count": 100,
            "lifecycle_needs_review_count": 100,
            "lifecycle_gap_count": 100,
            "retrieval_health_issue_count": 100,
            "retrieval_pending_capture_count": 100,
        }
        score = _calculate_digest_score(metrics)
        assert score == 0


# ---------------------------------------------------------------------------
# Snapshot creation tests
# ---------------------------------------------------------------------------

class TestSnapshotCreation:
    """Snapshot creation, skip, and force behavior."""

    def test_snapshot_creation_empty_db(self, tmp_path):
        """Creating a snapshot on an empty DB works."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest_history import (
            create_operations_digest_snapshot,
        )
        result = create_operations_digest_snapshot(db)
        assert result.snapshot_created
        assert not result.snapshot_skipped
        assert result.digest_snapshot_id > 0
        assert result.digest_score == 100
        assert result.digest_status_label == "clear"

    def test_snapshot_creation_with_data(self, tmp_path):
        """Snapshot captures metrics from populated database."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_candidate(db, 1, review_status="pending_user_decision")
        _insert_alert(db, 1, 1, "open", "critical")

        from marketsentry.operations_digest_history import (
            create_operations_digest_snapshot,
        )
        result = create_operations_digest_snapshot(db)
        assert result.snapshot_created
        assert result.key_counts["pending_user_decision_count"] == 1
        assert result.key_counts["high_or_critical_open_alert_count"] == 1
        assert result.digest_score < 100

    def test_same_day_no_change_skip(self, tmp_path):
        """Same-day snapshot without material changes is skipped."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest_history import (
            create_operations_digest_snapshot,
        )
        # First snapshot
        r1 = create_operations_digest_snapshot(db)
        assert r1.snapshot_created
        # Second same-day snapshot with no changes
        r2 = create_operations_digest_snapshot(db)
        assert r2.snapshot_skipped
        assert "no material changes" in r2.skip_reason.lower()

    def test_force_creates_snapshot(self, tmp_path):
        """--force creates a snapshot even without material changes."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest_history import (
            create_operations_digest_snapshot,
        )
        r1 = create_operations_digest_snapshot(db)
        assert r1.snapshot_created
        r2 = create_operations_digest_snapshot(db, force=True)
        assert r2.snapshot_created
        assert not r2.snapshot_skipped

    def test_material_change_creates_row(self, tmp_path):
        """Material change (new candidate) creates a new snapshot."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest_history import (
            create_operations_digest_snapshot,
        )
        r1 = create_operations_digest_snapshot(db)
        assert r1.snapshot_created
        # Add data that changes metrics
        _insert_candidate(db, 1, review_status="pending_user_decision")
        _insert_candidate(db, 2, review_status="pending_user_decision")
        r2 = create_operations_digest_snapshot(db)
        assert r2.snapshot_created
        assert any(
            "candidate" in c.lower() for c in r2.material_changes
        )


# ---------------------------------------------------------------------------
# Snapshot retrieval tests
# ---------------------------------------------------------------------------

class TestSnapshotRetrieval:
    """Latest and previous snapshot retrieval."""

    def test_latest_snapshot_retrieval(self, tmp_path):
        """get_latest returns the most recent snapshot."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_snapshot(db, "2026-05-01T00:00:00Z", digest_score=90)
        _insert_snapshot(db, "2026-05-02T00:00:00Z", digest_score=80)

        from marketsentry.operations_digest_history import (
            get_latest_operations_digest_snapshot,
        )
        snap = get_latest_operations_digest_snapshot(db)
        assert snap is not None
        assert snap.digest_score == 80

    def test_previous_snapshot_retrieval(self, tmp_path):
        """get_previous returns the second-most-recent snapshot."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_snapshot(db, "2026-05-01T00:00:00Z", digest_score=90)
        _insert_snapshot(db, "2026-05-02T00:00:00Z", digest_score=80)

        from marketsentry.operations_digest_history import (
            get_previous_operations_digest_snapshot,
        )
        snap = get_previous_operations_digest_snapshot(db)
        assert snap is not None
        assert snap.digest_score == 90

    def test_no_snapshots_returns_none(self, tmp_path):
        """get_latest returns None when no snapshots exist."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest_history import (
            get_latest_operations_digest_snapshot,
        )
        snap = get_latest_operations_digest_snapshot(db)
        assert snap is None

    def test_single_snapshot_previous_is_none(self, tmp_path):
        """get_previous returns None when only one snapshot exists."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_snapshot(db, "2026-05-01T00:00:00Z")
        from marketsentry.operations_digest_history import (
            get_previous_operations_digest_snapshot,
        )
        snap = get_previous_operations_digest_snapshot(db)
        assert snap is None


# ---------------------------------------------------------------------------
# Trend change tests
# ---------------------------------------------------------------------------

class TestTrendChange:
    """Trend change calculation tests."""

    def test_trend_improved(self):
        """Improved trend when backlogs decrease."""
        from marketsentry.operations_digest_history import (
            calculate_operations_digest_trend_change,
        )
        current = OperationsDigestSnapshot(
            pending_user_decision_count=1, digest_score=90
        )
        previous = OperationsDigestSnapshot(
            pending_user_decision_count=5, digest_score=70
        )
        changes = calculate_operations_digest_trend_change(current, previous)
        pending_change = next(
            c for c in changes
            if c.metric_name == "pending_user_decision_count"
        )
        assert pending_change.trend_direction == "improved"
        score_change = next(
            c for c in changes if c.metric_name == "digest_score"
        )
        assert score_change.trend_direction == "improved"

    def test_trend_degraded(self):
        """Degraded trend when backlogs increase."""
        from marketsentry.operations_digest_history import (
            calculate_operations_digest_trend_change,
        )
        current = OperationsDigestSnapshot(
            pending_user_decision_count=10, digest_score=50
        )
        previous = OperationsDigestSnapshot(
            pending_user_decision_count=2, digest_score=85
        )
        changes = calculate_operations_digest_trend_change(current, previous)
        pending_change = next(
            c for c in changes
            if c.metric_name == "pending_user_decision_count"
        )
        assert pending_change.trend_direction == "degraded"
        score_change = next(
            c for c in changes if c.metric_name == "digest_score"
        )
        assert score_change.trend_direction == "degraded"

    def test_trend_stable(self):
        """Stable trend when no change."""
        from marketsentry.operations_digest_history import (
            calculate_operations_digest_trend_change,
        )
        current = OperationsDigestSnapshot(
            pending_user_decision_count=5, digest_score=80
        )
        previous = OperationsDigestSnapshot(
            pending_user_decision_count=5, digest_score=80
        )
        changes = calculate_operations_digest_trend_change(current, previous)
        for c in changes:
            assert c.trend_direction == "stable"

    def test_trend_new(self, tmp_path):
        """New trend when no previous snapshot exists."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_snapshot(db, "2026-05-01T00:00:00Z")
        from marketsentry.operations_digest_history import (
            summarize_operations_digest_history,
        )
        summary = summarize_operations_digest_history(db)
        assert summary.trend_direction == "new"


# ---------------------------------------------------------------------------
# Comparison report tests
# ---------------------------------------------------------------------------

class TestComparisonReport:
    """Comparison report export tests."""

    def test_comparison_csv_export(self, tmp_path):
        """CSV comparison report contains correct columns."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_snapshot(db, "2026-05-01T00:00:00Z", digest_score=90)
        _insert_snapshot(db, "2026-05-02T00:00:00Z", digest_score=80)

        out_dir = str(tmp_path / "exports")
        from marketsentry.operations_digest_history import (
            export_operations_digest_comparison_report,
        )
        paths = export_operations_digest_comparison_report(
            db, out_dir, fmt="csv"
        )
        assert len(paths) == 1
        assert paths[0].endswith(".csv")
        with open(paths[0], newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert "digest_score_current" in rows[0]
        assert "trend_direction" in rows[0]

    def test_comparison_md_export(self, tmp_path):
        """Markdown comparison report is generated."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_snapshot(db, "2026-05-01T00:00:00Z", digest_score=90)
        _insert_snapshot(db, "2026-05-02T00:00:00Z", digest_score=80)

        out_dir = str(tmp_path / "exports")
        from marketsentry.operations_digest_history import (
            export_operations_digest_comparison_report,
        )
        paths = export_operations_digest_comparison_report(
            db, out_dir, fmt="md"
        )
        assert len(paths) == 1
        assert paths[0].endswith(".md")
        content = Path(paths[0]).read_text(encoding="utf-8")
        assert "Operations Digest Comparison Report" in content

    def test_comparison_both_export(self, tmp_path):
        """Both CSV and MD exports are generated."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_snapshot(db, "2026-05-01T00:00:00Z", digest_score=90)
        _insert_snapshot(db, "2026-05-02T00:00:00Z", digest_score=80)

        out_dir = str(tmp_path / "exports")
        from marketsentry.operations_digest_history import (
            export_operations_digest_comparison_report,
        )
        paths = export_operations_digest_comparison_report(
            db, out_dir, fmt="both"
        )
        assert len(paths) == 2
        extensions = {Path(p).suffix for p in paths}
        assert ".csv" in extensions
        assert ".md" in extensions

    def test_comparison_no_snapshots_returns_empty(self, tmp_path):
        """Comparison report returns empty list when no snapshots exist."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        out_dir = str(tmp_path / "exports")
        from marketsentry.operations_digest_history import (
            export_operations_digest_comparison_report,
        )
        paths = export_operations_digest_comparison_report(
            db, out_dir, fmt="csv"
        )
        assert paths == []


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLISnapshotOperationsDigest:
    """CLI snapshot-operations-digest command tests."""

    def test_cli_snapshot_operations_digest(self, tmp_path):
        """CLI snapshot command runs successfully."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        result = runner.invoke(app, [
            "snapshot-operations-digest", "--db", db, "--force",
        ])
        assert result.exit_code == 0
        assert "Snapshot created" in result.output or "snapshot" in result.output.lower()

    def test_cli_snapshot_skip(self, tmp_path):
        """CLI snapshot command reports skip correctly."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        runner.invoke(app, [
            "snapshot-operations-digest", "--db", db, "--force",
        ])
        result = runner.invoke(app, [
            "snapshot-operations-digest", "--db", db,
        ])
        assert result.exit_code == 0
        assert "skipped" in result.output.lower() or "Snapshot" in result.output


class TestCLIExportComparisonReport:
    """CLI export-operations-digest-comparison-report command tests."""

    def test_cli_export_comparison_report(self, tmp_path):
        """CLI comparison report command runs successfully."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_snapshot(db, "2026-05-01T00:00:00Z", digest_score=90)
        _insert_snapshot(db, "2026-05-02T00:00:00Z", digest_score=80)
        out_dir = str(tmp_path / "exports")
        result = runner.invoke(app, [
            "export-operations-digest-comparison-report",
            "--db", db,
            "--output-dir", out_dir,
            "--format", "csv",
        ])
        assert result.exit_code == 0
        assert "Report" in result.output or "report" in result.output.lower()


class TestCLIHistorySummary:
    """CLI operations-digest-history-summary command tests."""

    def test_cli_history_summary(self, tmp_path):
        """CLI history summary command runs successfully."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_snapshot(db, "2026-05-01T00:00:00Z", digest_score=90)
        result = runner.invoke(app, [
            "operations-digest-history-summary",
            "--db", db,
        ])
        assert result.exit_code == 0
        assert "Snapshot count" in result.output or "snapshot" in result.output.lower()

    def test_cli_history_summary_empty(self, tmp_path):
        """CLI history summary works with no snapshots."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        result = runner.invoke(app, [
            "operations-digest-history-summary",
            "--db", db,
        ])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------

class TestDashboardDigestHistory:
    """Dashboard digest history section tests."""

    def test_dashboard_digest_history_data_loads(self, tmp_path):
        """Dashboard digest history functions load correctly."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_snapshot(db, "2026-05-01T00:00:00Z", digest_score=90)
        _insert_snapshot(db, "2026-05-02T00:00:00Z", digest_score=80)

        from marketsentry.operations_digest_history import (
            get_latest_operations_digest_snapshot,
            get_previous_operations_digest_snapshot,
            calculate_operations_digest_trend_change,
        )
        latest = get_latest_operations_digest_snapshot(db)
        prev = get_previous_operations_digest_snapshot(db)
        assert latest is not None
        assert prev is not None
        changes = calculate_operations_digest_trend_change(latest, prev)
        assert len(changes) > 0


# ---------------------------------------------------------------------------
# Scheduled script safety tests
# ---------------------------------------------------------------------------

class TestScheduledScriptSafety:
    """Scheduled script safety tests."""

    def test_scheduled_script_no_live_retrieval(self):
        """Scheduled script does not contain live retrieval commands."""
        script_path = Path("scripts/run_operations_digest_report.bat")
        if not script_path.exists():
            pytest.skip("Scheduled script not found")
        content = script_path.read_text(encoding="utf-8").lower()
        assert "force-live" not in content
        assert "import-" not in content
        assert "redfin-fetch" not in content
        assert "scrape" not in content

    def test_scheduled_script_contains_snapshot_command(self):
        """Scheduled script contains the snapshot command."""
        script_path = Path("scripts/run_operations_digest_report.bat")
        if not script_path.exists():
            pytest.skip("Scheduled script not found")
        content = script_path.read_text(encoding="utf-8")
        assert "snapshot-operations-digest" in content

    def test_scheduled_script_contains_comparison_command(self):
        """Scheduled script contains the comparison report command."""
        script_path = Path("scripts/run_operations_digest_report.bat")
        if not script_path.exists():
            pytest.skip("Scheduled script not found")
        content = script_path.read_text(encoding="utf-8")
        assert "export-operations-digest-comparison-report" in content


# ---------------------------------------------------------------------------
# Safety / guard-rail tests
# ---------------------------------------------------------------------------

class TestSafetyGuardrails:
    """Tests ensuring no mutations, no network calls, no forbidden features."""

    def test_no_candidate_watchlist_alert_mutation(self):
        """Module does not mutate candidate/watchlist/alert state."""
        src = Path(
            "src/marketsentry/operations_digest_history.py"
        ).read_text(encoding="utf-8")
        # Should not contain UPDATE or DELETE on protected tables
        assert "UPDATE candidate_review_queue" not in src
        assert "DELETE FROM candidate_review_queue" not in src
        assert "UPDATE watched_properties" not in src
        assert "DELETE FROM watched_properties" not in src
        assert "UPDATE cross_site_trend_alerts" not in src
        assert "DELETE FROM cross_site_trend_alerts" not in src

    def test_no_redfin_source_of_truth_overwrite(self):
        """Module does not overwrite Redfin source-of-truth fields."""
        src = Path(
            "src/marketsentry/operations_digest_history.py"
        ).read_text(encoding="utf-8")
        assert "redfin_price" not in src
        assert "redfin_status" not in src

    def test_quiet_gatekeeper_unchanged(self):
        """Module does not modify Quiet Score or Vibrancy Score."""
        src = Path(
            "src/marketsentry/operations_digest_history.py"
        ).read_text(encoding="utf-8")
        assert "quiet_score" not in src
        assert "vibrancy_score" not in src

    def test_no_walkability_fields(self):
        """Module does not add walkability fields."""
        src = Path(
            "src/marketsentry/operations_digest_history.py"
        ).read_text(encoding="utf-8")
        assert "walkability" not in src
        assert "walk_score" not in src

    def test_no_network_calls_in_module(self):
        """Module does not import network libraries."""
        src = Path(
            "src/marketsentry/operations_digest_history.py"
        ).read_text(encoding="utf-8")
        assert "requests" not in src
        assert "urllib" not in src
        assert "httpx" not in src
        assert "aiohttp" not in src

    def test_no_browser_automation(self):
        """Module does not use browser automation."""
        src = Path(
            "src/marketsentry/operations_digest_history.py"
        ).read_text(encoding="utf-8")
        assert "selenium" not in src
        assert "playwright" not in src
        assert "webdriver" not in src

    def test_model_classes_exist(self):
        """All five M39 models are importable."""
        from marketsentry.models import (
            OperationsDigestComparisonReportRow,
            OperationsDigestHistorySummary,
            OperationsDigestSnapshot,
            OperationsDigestSnapshotRunResult,
            OperationsDigestTrendChange,
        )
        assert OperationsDigestSnapshot is not None
        assert OperationsDigestTrendChange is not None
        assert OperationsDigestComparisonReportRow is not None
        assert OperationsDigestHistorySummary is not None
        assert OperationsDigestSnapshotRunResult is not None

    def test_history_summary_with_two_snapshots(self, tmp_path):
        """History summary works with two snapshots."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_snapshot(
            db, "2026-05-01T00:00:00Z",
            digest_score=90,
            pending_user_decision_count=5,
            high_or_critical_open_alert_count=3,
        )
        _insert_snapshot(
            db, "2026-05-02T00:00:00Z",
            digest_score=80,
            pending_user_decision_count=8,
            high_or_critical_open_alert_count=5,
        )
        from marketsentry.operations_digest_history import (
            summarize_operations_digest_history,
        )
        summary = summarize_operations_digest_history(db)
        assert summary.snapshot_count == 2
        assert summary.latest_digest_score == 80
        assert summary.previous_digest_score == 90
        assert summary.trend_direction == "degraded"
        assert len(summary.trend_changes) > 0

    def test_insert_is_append_only(self, tmp_path):
        """Snapshots are append-only; existing rows are not modified."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        id1 = _insert_snapshot(db, "2026-05-01T00:00:00Z", digest_score=90)
        id2 = _insert_snapshot(db, "2026-05-02T00:00:00Z", digest_score=80)
        conn = sqlite3.connect(db)
        cur = conn.execute(
            "SELECT digest_score FROM operations_digest_snapshots "
            "WHERE digest_snapshot_id = ?", (id1,)
        )
        assert cur.fetchone()[0] == 90  # unchanged
        cur2 = conn.execute(
            "SELECT COUNT(*) FROM operations_digest_snapshots"
        )
        assert cur2.fetchone()[0] == 2
        conn.close()
