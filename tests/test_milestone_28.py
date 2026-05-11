"""Tests for Milestone 28: Cross-Site Alert Triage Workflow.

Tests cover:
- Triage export creates CSV
- Exported rows include required columns
- Default triage_decision is keep_open
- Filtering by status/severity/property_id
- Import validates triage_export_id
- Import validates alert_id exists
- Import validates current_status mismatch
- Force status mismatch allows apply
- Acknowledge decision updates status
- Resolve decision updates status
- Archive decision updates status
- Keep_open does not change status
- Needs_reparse does not change status but notes recorded
- Needs_manual_review does not change status but notes recorded
- Invalid triage decision rejected
- Triage history rows recorded
- CLI export-cross-site-alert-triage
- CLI import-cross-site-alert-triage
- Dashboard triage summary loads
- No Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- No walkability fields added
- No real network calls
- Existing MVP 1-27 tests still pass (run with full suite)
"""

import csv
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from marketsentry.database import execute_query, get_connection, init_db, table_exists
from marketsentry.models import (
    CrossSiteAlertTriageDecision,
    CrossSiteAlertTriageExportResult,
    CrossSiteAlertTriageImportResult,
    CrossSiteAlertTriageRow,
    CrossSiteAlertTriageSummary,
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


def _create_triage_csv(
    temp_exports_dir: str,
    rows: list,
    triage_export_id: str = "triage_test123",
) -> str:
    """Create a triage CSV file for import testing."""
    from marketsentry.cross_site_alert_triage import TRIAGE_CSV_FIELDNAMES

    path = str(Path(temp_exports_dir) / "test_triage.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRIAGE_CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            full_row = {k: "" for k in TRIAGE_CSV_FIELDNAMES}
            full_row["triage_export_id"] = triage_export_id
            full_row.update(row)
            writer.writerow(full_row)
    return path


# ---------------------------------------------------------------------------
# Test: Triage export creates CSV
# ---------------------------------------------------------------------------


class TestTriageExportCSV:
    """Test triage CSV export."""

    def test_export_creates_csv(self, temp_db, temp_exports_dir):
        """Export should create a CSV file."""
        from marketsentry.cross_site_alert_triage import (
            export_cross_site_alert_triage_csv,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="warning")

        output_path = str(Path(temp_exports_dir) / "test_triage.csv")
        result = export_cross_site_alert_triage_csv(
            database_path=temp_db, output_path=output_path,
        )

        assert Path(result.output_path).exists()
        assert result.row_count >= 1
        assert result.triage_export_id.startswith("triage_")

    def test_export_empty_db(self, temp_db, temp_exports_dir):
        """Export from empty database should create CSV with headers only."""
        from marketsentry.cross_site_alert_triage import (
            export_cross_site_alert_triage_csv,
        )

        output_path = str(Path(temp_exports_dir) / "test_empty.csv")
        result = export_cross_site_alert_triage_csv(
            database_path=temp_db, output_path=output_path,
        )

        assert Path(result.output_path).exists()
        assert result.row_count == 0


# ---------------------------------------------------------------------------
# Test: Exported rows include required columns
# ---------------------------------------------------------------------------


class TestTriageExportColumns:
    """Test exported CSV has all required columns."""

    def test_columns_present(self, temp_db, temp_exports_dir):
        """CSV should contain all required columns."""
        from marketsentry.cross_site_alert_triage import (
            TRIAGE_CSV_FIELDNAMES,
            export_cross_site_alert_triage_csv,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        output_path = str(Path(temp_exports_dir) / "test_cols.csv")
        result = export_cross_site_alert_triage_csv(
            database_path=temp_db, output_path=output_path,
        )

        with open(result.output_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert set(TRIAGE_CSV_FIELDNAMES).issubset(set(reader.fieldnames or []))


# ---------------------------------------------------------------------------
# Test: Default triage_decision is keep_open
# ---------------------------------------------------------------------------


class TestDefaultTriageDecision:
    """Test default triage_decision value."""

    def test_default_is_keep_open(self, temp_db, temp_exports_dir):
        """Default triage_decision should be keep_open."""
        from marketsentry.cross_site_alert_triage import (
            export_cross_site_alert_triage_csv,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        output_path = str(Path(temp_exports_dir) / "test_default.csv")
        result = export_cross_site_alert_triage_csv(
            database_path=temp_db, output_path=output_path,
        )

        with open(result.output_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) >= 1
            assert rows[0]["triage_decision"] == "keep_open"


# ---------------------------------------------------------------------------
# Test: Filtering by status/severity/property_id
# ---------------------------------------------------------------------------


class TestTriageFiltering:
    """Test alert filtering for triage export."""

    def test_filter_by_status(self, temp_db):
        """Filter by status should return matching alerts."""
        from marketsentry.cross_site_alert_triage import filter_alerts_for_triage

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_status="open")
        _insert_alert(temp_db, pid, alert_status="resolved",
                       alert_type="confidence_improvement")

        alerts = filter_alerts_for_triage(temp_db, status_filter="open")
        assert len(alerts) == 1
        assert alerts[0]["alert_status"] == "open"

    def test_filter_by_severity(self, temp_db):
        """Filter by severity should return matching alerts."""
        from marketsentry.cross_site_alert_triage import filter_alerts_for_triage

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="warning")
        _insert_alert(temp_db, pid, severity="high",
                       alert_type="severity_increase")

        alerts = filter_alerts_for_triage(
            temp_db, status_filter=None, severity_filter="high",
        )
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "high"

    def test_filter_by_property_id(self, temp_db):
        """Filter by property_id should return matching alerts."""
        from marketsentry.cross_site_alert_triage import filter_alerts_for_triage

        pid1 = _insert_watched_property(temp_db, "100 First Ave")
        pid2 = _insert_watched_property(temp_db, "200 Second Ave")
        _insert_alert(temp_db, pid1)
        _insert_alert(temp_db, pid2)

        alerts = filter_alerts_for_triage(
            temp_db, status_filter=None, property_id=pid1,
        )
        assert len(alerts) == 1
        assert alerts[0]["property_id"] == pid1

    def test_include_acknowledged(self, temp_db):
        """Include acknowledged should return both open and acknowledged."""
        from marketsentry.cross_site_alert_triage import filter_alerts_for_triage

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_status="open")
        _insert_alert(temp_db, pid, alert_status="acknowledged",
                       alert_type="severity_increase")

        alerts = filter_alerts_for_triage(
            temp_db, status_filter="open", include_acknowledged=True,
        )
        assert len(alerts) == 2


# ---------------------------------------------------------------------------
# Test: Import validates triage_export_id
# ---------------------------------------------------------------------------


class TestImportValidation:
    """Test triage import validation."""

    def test_import_validates_alert_id_exists(self, temp_db, temp_exports_dir):
        """Import should skip rows with nonexistent alert_id."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": "99999", "triage_decision": "acknowledge",
             "current_status": "open"},
        ])

        result = apply_cross_site_alert_triage_decisions(csv_path, temp_db)
        assert result.invalid_rows >= 1

    def test_import_validates_triage_decision(self, temp_db, temp_exports_dir):
        """Import should reject invalid triage_decision values."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid)

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid), "triage_decision": "invalid_action",
             "current_status": "open"},
        ])

        result = apply_cross_site_alert_triage_decisions(csv_path, temp_db)
        assert result.invalid_rows >= 1

    def test_import_validates_status_mismatch(self, temp_db, temp_exports_dir):
        """Import should skip rows where current_status doesn't match."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="open")

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid), "triage_decision": "acknowledge",
             "current_status": "resolved"},
        ])

        result = apply_cross_site_alert_triage_decisions(csv_path, temp_db)
        assert result.skipped_status_mismatch >= 1

    def test_force_status_mismatch(self, temp_db, temp_exports_dir):
        """Force flag should allow applying despite status mismatch."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="open")

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid), "triage_decision": "acknowledge",
             "current_status": "resolved"},
        ])

        result = apply_cross_site_alert_triage_decisions(
            csv_path, temp_db, force_status_mismatch=True,
        )
        assert result.acknowledged >= 1
        assert result.skipped_status_mismatch == 0


# ---------------------------------------------------------------------------
# Test: Status-changing decisions
# ---------------------------------------------------------------------------


class TestStatusChangingDecisions:
    """Test acknowledge/resolve/archive update alert status."""

    def test_acknowledge_updates_status(self, temp_db, temp_exports_dir):
        """Acknowledge decision should update alert_status to acknowledged."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="open")

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid), "triage_decision": "acknowledge",
             "current_status": "open", "triage_notes": "Reviewed"},
        ])

        result = apply_cross_site_alert_triage_decisions(csv_path, temp_db)
        assert result.acknowledged == 1

        rows = execute_query(
            "SELECT alert_status, notes FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "acknowledged"
        assert "Reviewed" in (rows[0]["notes"] or "")

    def test_resolve_updates_status(self, temp_db, temp_exports_dir):
        """Resolve decision should update alert_status to resolved."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="open")

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid), "triage_decision": "resolve",
             "current_status": "open"},
        ])

        result = apply_cross_site_alert_triage_decisions(csv_path, temp_db)
        assert result.resolved == 1

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "resolved"

    def test_archive_updates_status(self, temp_db, temp_exports_dir):
        """Archive decision should update alert_status to archived."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="open")

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid), "triage_decision": "archive",
             "current_status": "open"},
        ])

        result = apply_cross_site_alert_triage_decisions(csv_path, temp_db)
        assert result.archived == 1

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "archived"


# ---------------------------------------------------------------------------
# Test: Non-status-changing decisions
# ---------------------------------------------------------------------------


class TestNonStatusChangingDecisions:
    """Test keep_open/needs_reparse/needs_manual_review."""

    def test_keep_open_does_not_change_status(self, temp_db, temp_exports_dir):
        """Keep_open should not change alert status."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="open")

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid), "triage_decision": "keep_open",
             "current_status": "open"},
        ])

        result = apply_cross_site_alert_triage_decisions(csv_path, temp_db)
        assert result.kept_open == 1

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "open"

    def test_needs_reparse_records_notes(self, temp_db, temp_exports_dir):
        """Needs_reparse should not change status but record notes."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="open")

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid), "triage_decision": "needs_reparse",
             "current_status": "open", "triage_notes": "Fixtures stale"},
        ])

        result = apply_cross_site_alert_triage_decisions(csv_path, temp_db)
        assert result.needs_reparse == 1

        rows = execute_query(
            "SELECT alert_status, notes FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "open"
        assert "[triage:needs_reparse]" in (rows[0]["notes"] or "")

    def test_needs_manual_review_records_notes(self, temp_db, temp_exports_dir):
        """Needs_manual_review should not change status but record notes."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="open")

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid), "triage_decision": "needs_manual_review",
             "current_status": "open", "triage_notes": "Check manually"},
        ])

        result = apply_cross_site_alert_triage_decisions(csv_path, temp_db)
        assert result.needs_manual_review == 1

        rows = execute_query(
            "SELECT alert_status, notes FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "open"
        assert "[triage:needs_manual_review]" in (rows[0]["notes"] or "")


# ---------------------------------------------------------------------------
# Test: Triage history rows recorded
# ---------------------------------------------------------------------------


class TestTriageHistory:
    """Test triage history table records actions."""

    def test_triage_action_recorded(self, temp_db, temp_exports_dir):
        """Triage actions should be recorded in history table."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="open")

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid), "triage_decision": "acknowledge",
             "current_status": "open", "triage_notes": "Triage test"},
        ])

        apply_cross_site_alert_triage_decisions(csv_path, temp_db)

        actions = execute_query(
            "SELECT * FROM cross_site_alert_triage_actions WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert len(actions) >= 1
        action = dict(actions[0])
        assert action["alert_id"] == aid
        assert action["previous_status"] == "open"
        assert action["new_status"] == "acknowledged"

    def test_keep_open_recorded_in_history(self, temp_db, temp_exports_dir):
        """Keep_open decisions should also be recorded in history."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="open")

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid), "triage_decision": "keep_open",
             "current_status": "open"},
        ])

        apply_cross_site_alert_triage_decisions(csv_path, temp_db)

        actions = execute_query(
            "SELECT * FROM cross_site_alert_triage_actions WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert len(actions) >= 1
        assert dict(actions[0])["action"] == "keep_open"


# ---------------------------------------------------------------------------
# Test: Triage summary
# ---------------------------------------------------------------------------


class TestTriageSummary:
    """Test triage summary."""

    def test_summary_counts(self, temp_db, temp_exports_dir):
        """Summary should have correct status counts."""
        from marketsentry.cross_site_alert_triage import (
            summarize_cross_site_alert_triage,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_status="open")
        _insert_alert(temp_db, pid, alert_status="open",
                       alert_type="severity_increase")
        _insert_alert(temp_db, pid, alert_status="acknowledged",
                       alert_type="dom_agreement_degraded")
        _insert_alert(temp_db, pid, alert_status="resolved",
                       alert_type="confidence_improvement")

        summary = summarize_cross_site_alert_triage(temp_db, temp_exports_dir)
        assert summary.total_alerts == 4
        assert summary.open_alerts == 2
        assert summary.acknowledged_alerts == 1
        assert summary.resolved_alerts == 1

    def test_summary_needs_reparse_count(self, temp_db, temp_exports_dir):
        """Summary should count needs_reparse from notes."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
            summarize_cross_site_alert_triage,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="open")

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid), "triage_decision": "needs_reparse",
             "current_status": "open"},
        ])
        apply_cross_site_alert_triage_decisions(csv_path, temp_db)

        summary = summarize_cross_site_alert_triage(temp_db, temp_exports_dir)
        assert summary.needs_reparse_count >= 1


# ---------------------------------------------------------------------------
# Test: CLI commands
# ---------------------------------------------------------------------------


class TestCLICommands:
    """Test CLI command registration and invocation."""

    def test_export_command_registered(self):
        """export-cross-site-alert-triage command should be registered."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(app, ["export-cross-site-alert-triage", "--help"])
        assert result.exit_code == 0
        assert "triage" in result.output.lower()

    def test_import_command_registered(self):
        """import-cross-site-alert-triage command should be registered."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(app, ["import-cross-site-alert-triage", "--help"])
        assert result.exit_code == 0

    def test_export_command_runs(self, temp_db, temp_exports_dir):
        """Export command should run successfully."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="warning")

        runner = CliRunner()
        result = runner.invoke(
            app, [
                "export-cross-site-alert-triage",
                "--db", temp_db,
                "--output-dir", temp_exports_dir,
            ]
        )
        assert result.exit_code == 0
        assert "success" in result.output.lower()

    def test_import_command_runs(self, temp_db, temp_exports_dir):
        """Import command should run successfully."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="open")

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid), "triage_decision": "acknowledge",
             "current_status": "open"},
        ])

        runner = CliRunner()
        result = runner.invoke(
            app, [
                "import-cross-site-alert-triage",
                "--file", csv_path,
                "--db", temp_db,
            ]
        )
        assert result.exit_code == 0
        assert "success" in result.output.lower()


# ---------------------------------------------------------------------------
# Test: Dashboard triage summary loads
# ---------------------------------------------------------------------------


class TestDashboardTriageSummary:
    """Test dashboard triage integration."""

    def test_build_triage_table_from_csv(self, temp_db, temp_exports_dir):
        """build_cross_site_alert_triage_table loads triage CSV."""
        from marketsentry.cross_site_alert_triage import (
            export_cross_site_alert_triage_csv,
        )
        from marketsentry.dashboard import build_cross_site_alert_triage_table

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="warning")

        output_path = str(
            Path(temp_exports_dir)
            / "cross_site_alert_triage_20260508_120000.csv"
        )
        export_cross_site_alert_triage_csv(
            database_path=temp_db, output_path=output_path,
        )

        df = build_cross_site_alert_triage_table(temp_exports_dir)
        assert not df.empty
        assert "triage_decision" in df.columns

    def test_find_latest_triage_report(self, temp_db, temp_exports_dir):
        """find_latest_report should find triage report."""
        from marketsentry.cross_site_alert_triage import (
            export_cross_site_alert_triage_csv,
        )
        from marketsentry.dashboard import find_latest_report

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        output_path = str(
            Path(temp_exports_dir)
            / "cross_site_alert_triage_20260508_120000.csv"
        )
        export_cross_site_alert_triage_csv(
            database_path=temp_db, output_path=output_path,
        )

        report = find_latest_report("cross_site_alert_triage", temp_exports_dir)
        assert report is not None
        assert "cross_site_alert_triage" in report.name


# ---------------------------------------------------------------------------
# Test: No Redfin source-of-truth overwrite
# ---------------------------------------------------------------------------


class TestNoRedfinOverwrite:
    """Verify triage does not overwrite Redfin source-of-truth fields."""

    def test_watched_properties_unchanged(self, temp_db, temp_exports_dir):
        """Running triage should not modify watched_properties."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, severity="high")

        before = execute_query(
            "SELECT * FROM watched_properties WHERE property_id = ?",
            (pid,), database_path=temp_db,
        )
        before_dict = dict(before[0])

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid), "triage_decision": "acknowledge",
             "current_status": "open"},
        ])
        apply_cross_site_alert_triage_decisions(csv_path, temp_db)

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
        """Triage module should not write to watched_properties."""
        import inspect
        import marketsentry.cross_site_alert_triage as mod

        source = inspect.getsource(mod)
        assert "UPDATE watched_properties" not in source
        assert "INSERT INTO watched_properties" not in source


# ---------------------------------------------------------------------------
# Test: Quiet gatekeeper remains unchanged
# ---------------------------------------------------------------------------


class TestQuietGatekeeperUnchanged:
    """Verify triage module does not modify Quiet Score gatekeeper."""

    def test_no_quiet_gatekeeper_import(self):
        """Triage module should not import or call quiet gatekeeper."""
        import inspect
        import marketsentry.cross_site_alert_triage as mod

        source = inspect.getsource(mod)
        assert "apply_quiet_gatekeeper" not in source
        assert "quiet_vibrancy" not in source


# ---------------------------------------------------------------------------
# Test: No walkability fields
# ---------------------------------------------------------------------------


class TestNoWalkabilityFields:
    """Verify no walkability fields are added."""

    def test_no_walkability_in_module(self):
        """Triage module should not reference walkability."""
        import inspect
        import marketsentry.cross_site_alert_triage as mod

        source = inspect.getsource(mod)
        assert "walkability" not in source.lower()
        assert "walk_score" not in source.lower()

    def test_no_walkability_in_models(self):
        """New models should not include walkability fields."""
        for model_cls in [
            CrossSiteAlertTriageRow,
            CrossSiteAlertTriageExportResult,
            CrossSiteAlertTriageImportResult,
            CrossSiteAlertTriageDecision,
            CrossSiteAlertTriageSummary,
        ]:
            for field_name in model_cls.model_fields:
                assert "walkability" not in field_name.lower()
                assert "walk_score" not in field_name.lower()


# ---------------------------------------------------------------------------
# Test: No real network calls
# ---------------------------------------------------------------------------


class TestNoNetworkCalls:
    """Verify no real network calls are made."""

    def test_no_network_in_triage(self, temp_db, temp_exports_dir):
        """Triage should not make network calls."""
        from marketsentry.cross_site_alert_triage import (
            export_cross_site_alert_triage_csv,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        output_path = str(Path(temp_exports_dir) / "test_no_net.csv")

        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch("http.client.HTTPConnection") as mock_http:
            export_cross_site_alert_triage_csv(
                database_path=temp_db, output_path=output_path,
            )
            mock_urlopen.assert_not_called()
            mock_http.assert_not_called()

    def test_no_requests_import(self):
        """Triage module should not import requests or urllib."""
        import inspect
        import marketsentry.cross_site_alert_triage as mod

        source = inspect.getsource(mod)
        assert "import requests" not in source
        assert "import urllib" not in source
        assert "import httpx" not in source


# ---------------------------------------------------------------------------
# Test: Models
# ---------------------------------------------------------------------------


class TestModels:
    """Test Milestone 28 models."""

    def test_triage_row_model(self):
        """CrossSiteAlertTriageRow should have all expected fields."""
        row = CrossSiteAlertTriageRow(alert_id=1, property_id=1)
        assert row.triage_decision == "keep_open"

    def test_export_result_model(self):
        """CrossSiteAlertTriageExportResult should have all expected fields."""
        result = CrossSiteAlertTriageExportResult(
            triage_export_id="test", output_path="/tmp/test.csv",
        )
        assert result.row_count == 0

    def test_import_result_model(self):
        """CrossSiteAlertTriageImportResult should have all expected fields."""
        result = CrossSiteAlertTriageImportResult()
        assert result.rows_read == 0
        assert result.valid_decisions == 0
        assert result.invalid_rows == 0

    def test_decision_model(self):
        """CrossSiteAlertTriageDecision should have all expected fields."""
        decision = CrossSiteAlertTriageDecision(alert_id=1)
        assert decision.triage_decision == "keep_open"

    def test_summary_model(self):
        """CrossSiteAlertTriageSummary should have all expected fields."""
        summary = CrossSiteAlertTriageSummary()
        assert summary.total_alerts == 0
        assert summary.open_alerts == 0


# ---------------------------------------------------------------------------
# Test: Schema
# ---------------------------------------------------------------------------


class TestSchema:
    """Test schema additions for Milestone 28."""

    def test_triage_actions_table_created(self, temp_db):
        """Triage actions table should exist after init_db."""
        assert table_exists("cross_site_alert_triage_actions", temp_db)

    def test_triage_actions_table_idempotent(self, temp_db):
        """Running init_db twice should not fail."""
        init_db(temp_db)
        assert table_exists("cross_site_alert_triage_actions", temp_db)


# ---------------------------------------------------------------------------
# Test: Batch triage with multiple decisions
# ---------------------------------------------------------------------------


class TestBatchTriage:
    """Test batch triage with multiple rows."""

    def test_mixed_decisions(self, temp_db, temp_exports_dir):
        """Import with mixed decisions should apply correctly."""
        from marketsentry.cross_site_alert_triage import (
            apply_cross_site_alert_triage_decisions,
        )

        pid = _insert_watched_property(temp_db)
        aid1 = _insert_alert(temp_db, pid, alert_status="open",
                              alert_type="confidence_drop")
        aid2 = _insert_alert(temp_db, pid, alert_status="open",
                              alert_type="severity_increase")
        aid3 = _insert_alert(temp_db, pid, alert_status="open",
                              alert_type="stale_sources_increased")

        csv_path = _create_triage_csv(temp_exports_dir, [
            {"alert_id": str(aid1), "triage_decision": "acknowledge",
             "current_status": "open"},
            {"alert_id": str(aid2), "triage_decision": "resolve",
             "current_status": "open"},
            {"alert_id": str(aid3), "triage_decision": "keep_open",
             "current_status": "open"},
        ])

        result = apply_cross_site_alert_triage_decisions(csv_path, temp_db)
        assert result.acknowledged == 1
        assert result.resolved == 1
        assert result.kept_open == 1
        assert result.valid_decisions == 3

        # Verify actual statuses
        r1 = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid1,), database_path=temp_db,
        )
        assert r1[0]["alert_status"] == "acknowledged"

        r2 = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid2,), database_path=temp_db,
        )
        assert r2[0]["alert_status"] == "resolved"

        r3 = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid3,), database_path=temp_db,
        )
        assert r3[0]["alert_status"] == "open"
