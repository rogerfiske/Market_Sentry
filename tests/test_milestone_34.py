"""Tests for Milestone 34: Alert Lifecycle Audit Trail and Operations Summary.

Tests cover:
- Lifecycle events load with no data
- Alert creation event generated
- Triage action event loaded
- Archive action event loaded
- Expiration action event loaded
- no_archive marker parsed
- needs_reparse marker parsed
- needs_manual_review marker parsed
- Chronological event order
- Property summary metrics
- Lifecycle labels
- Open alert gap detection
- needs_reparse unresolved gap
- needs_manual_review unresolved gap
- Acknowledged stale gap
- Resolved archive candidate gap
- Reopened stale gap
- Lifecycle CSV report export
- Lifecycle Markdown report export
- CLI lifecycle summary
- CLI export lifecycle report
- CLI show alert lifecycle
- Dashboard lifecycle table loads
- No mutation behavior
- No Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- No walkability fields added
- No real network calls
- Existing MVP 1-33 tests still pass (run with full suite)
"""

import csv
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from marketsentry.database import (
    execute_query,
    get_connection,
    init_db,
    table_exists,
)
from marketsentry.models import (
    CrossSiteAlertLifecycleEvent,
    CrossSiteAlertLifecyclePropertySummary,
    CrossSiteAlertLifecycleReportRow,
    CrossSiteAlertLifecycleRunResult,
    CrossSiteAlertLifecycleSummary,
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


def _insert_candidate(db_path: str, address: str = "123 Test St") -> int:
    """Insert a candidate and return its ID."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO candidates (
            source_url, address, city, state, zip,
            current_price, quiet_score, vibrancy_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "https://www.redfin.com/test",
            address, "Temecula", "CA", "92592",
            750000, 9.0, 1.0,
        ),
    )
    cid = cursor.lastrowid
    conn.commit()
    conn.close()
    return cid


def _insert_watched_property(
    db_path: str, address: str = "123 Test St",
) -> int:
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
    created_at: str = "",
    notes: str = "",
    candidate_id: int = None,
) -> int:
    """Insert a trend alert and return its ID."""
    if not created_at:
        created_at = datetime.now().isoformat()

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO cross_site_trend_alerts (
            property_id, candidate_id, alert_type, severity,
            alert_status, snapshot_id, created_at,
            message, recommended_action, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            property_id, candidate_id, alert_type, severity,
            alert_status, 1, created_at,
            f"Test {alert_type} alert",
            "Review cross-site data",
            notes,
        ),
    )
    aid = cursor.lastrowid
    conn.commit()
    conn.close()
    return aid


def _insert_triage_action(
    db_path: str,
    alert_id: int,
    property_id: int,
    action: str,
    previous_status: str,
    new_status: str,
    triage_export_id: str = "triage_abc123def456",
    triage_notes: str = "",
    applied_at: str = "",
) -> None:
    """Insert a triage action record."""
    if not applied_at:
        applied_at = datetime.now().isoformat()

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO cross_site_alert_triage_actions (
            triage_export_id, alert_id, property_id, action,
            previous_status, new_status, triage_notes, applied_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            triage_export_id, alert_id, property_id, action,
            previous_status, new_status, triage_notes, applied_at,
        ),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Test: Lifecycle events load with no data
# ---------------------------------------------------------------------------


class TestLoadEventsNoData:
    def test_empty_db(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            load_alert_lifecycle_events,
        )
        events = load_alert_lifecycle_events(database_path=temp_db)
        assert events == []

    def test_no_alerts_table(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            load_alert_lifecycle_events,
        )
        # Should not crash even if table is empty
        events = load_alert_lifecycle_events(database_path=temp_db)
        assert isinstance(events, list)


# ---------------------------------------------------------------------------
# Test: Alert creation event generated
# ---------------------------------------------------------------------------


class TestAlertCreationEvent:
    def test_alert_creation_event(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            load_alert_lifecycle_events,
        )
        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid)
        events = load_alert_lifecycle_events(database_path=temp_db)
        assert len(events) == 1
        assert events[0].event_type == "alert_created"
        assert events[0].alert_id == aid
        assert events[0].property_id == pid
        assert events[0].new_status == "open"
        assert events[0].source_table == "cross_site_trend_alerts"

    def test_creation_event_has_id(self, temp_db):
        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)
        from marketsentry.cross_site_alert_lifecycle import (
            load_alert_lifecycle_events,
        )
        events = load_alert_lifecycle_events(database_path=temp_db)
        assert events[0].event_id != ""


# ---------------------------------------------------------------------------
# Test: Triage action event loaded
# ---------------------------------------------------------------------------


class TestTriageActionEvent:
    def test_triage_event(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            load_alert_lifecycle_events,
        )
        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid)
        _insert_triage_action(
            temp_db, aid, pid, "acknowledge",
            "open", "acknowledged",
            triage_export_id="triage_abc123def456",
        )
        events = load_alert_lifecycle_events(database_path=temp_db)
        # Should have creation + triage action
        assert len(events) == 2
        triage_ev = [e for e in events if e.event_type == "acknowledged"]
        assert len(triage_ev) == 1
        assert triage_ev[0].source_workflow == "triage"


# ---------------------------------------------------------------------------
# Test: Archive action event loaded
# ---------------------------------------------------------------------------


class TestArchiveActionEvent:
    def test_archive_event(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            load_alert_lifecycle_events,
        )
        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved",
        )
        _insert_triage_action(
            temp_db, aid, pid, "archive",
            "resolved", "archived",
            triage_export_id="archive_abc123def456",
        )
        events = load_alert_lifecycle_events(database_path=temp_db)
        archive_ev = [e for e in events if e.event_type == "archived"]
        assert len(archive_ev) == 1
        assert archive_ev[0].source_workflow == "archive_policy"


# ---------------------------------------------------------------------------
# Test: Expiration action event loaded
# ---------------------------------------------------------------------------


class TestExpirationActionEvent:
    def test_expiration_event(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            load_alert_lifecycle_events,
        )
        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="resolved")
        _insert_triage_action(
            temp_db, aid, pid, "approve_action",
            "resolved", "archived",
            triage_export_id="expiration_abc123def456",
        )
        events = load_alert_lifecycle_events(database_path=temp_db)
        exp_ev = [
            e for e in events if e.event_type == "expiration_approved"
        ]
        assert len(exp_ev) == 1
        assert exp_ev[0].source_workflow == "expiration_policy"


# ---------------------------------------------------------------------------
# Test: Note markers parsed
# ---------------------------------------------------------------------------


class TestNoteMarkers:
    def test_no_archive_marker(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            _parse_notes_markers,
        )
        counts = _parse_notes_markers("[no_archive] some note")
        assert counts["no_archive"] == 1

    def test_needs_reparse_marker(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            _parse_notes_markers,
        )
        counts = _parse_notes_markers("[triage:needs_reparse] fix it")
        assert counts["needs_reparse"] == 1

    def test_needs_manual_review_marker(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            _parse_notes_markers,
        )
        counts = _parse_notes_markers(
            "[triage:needs_manual_review] check",
        )
        assert counts["needs_manual_review"] == 1

    def test_no_markers(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            _parse_notes_markers,
        )
        counts = _parse_notes_markers("plain note")
        assert all(v == 0 for v in counts.values())

    def test_none_notes(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            _parse_notes_markers,
        )
        counts = _parse_notes_markers(None)
        assert all(v == 0 for v in counts.values())


# ---------------------------------------------------------------------------
# Test: Chronological event order
# ---------------------------------------------------------------------------


class TestChronologicalOrder:
    def test_events_sorted_by_time(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            load_alert_lifecycle_events,
        )
        pid = _insert_watched_property(temp_db)
        t1 = "2026-01-01T10:00:00"
        t2 = "2026-01-02T10:00:00"
        t3 = "2026-01-03T10:00:00"
        aid = _insert_alert(temp_db, pid, created_at=t1)
        _insert_triage_action(
            temp_db, aid, pid, "acknowledge", "open", "acknowledged",
            applied_at=t2,
        )
        _insert_triage_action(
            temp_db, aid, pid, "resolve", "acknowledged", "resolved",
            triage_export_id="triage_def789000000",
            applied_at=t3,
        )
        events = load_alert_lifecycle_events(database_path=temp_db)
        times = [e.event_at for e in events]
        assert times == sorted(times)


# ---------------------------------------------------------------------------
# Test: Property summary metrics
# ---------------------------------------------------------------------------


class TestPropertySummary:
    def test_summary_counts(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_property,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_status="open")
        _insert_alert(temp_db, pid, alert_status="acknowledged")
        _insert_alert(temp_db, pid, alert_status="resolved")
        _insert_alert(temp_db, pid, alert_status="archived")

        summary = summarize_alert_lifecycle_for_property(
            property_id=pid, database_path=temp_db,
        )
        assert summary.total_alerts == 4
        assert summary.open_alerts == 1
        assert summary.acknowledged_alerts == 1
        assert summary.resolved_alerts == 1
        assert summary.archived_alerts == 1

    def test_no_alerts_summary(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_property,
        )
        pid = _insert_watched_property(temp_db)
        summary = summarize_alert_lifecycle_for_property(
            property_id=pid, database_path=temp_db,
        )
        assert summary.total_alerts == 0
        assert summary.lifecycle_summary_label == "no_alerts"

    def test_unresolved_high_critical(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_property,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(
            temp_db, pid, severity="high", alert_status="open",
        )
        _insert_alert(
            temp_db, pid, severity="critical", alert_status="acknowledged",
        )

        summary = summarize_alert_lifecycle_for_property(
            property_id=pid, database_path=temp_db,
        )
        assert summary.unresolved_high_or_critical_count == 2

    def test_note_markers_counted(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_property,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(
            temp_db, pid, notes="[no_archive] keep",
        )
        _insert_alert(
            temp_db, pid, notes="[triage:needs_reparse]",
        )
        _insert_alert(
            temp_db, pid, notes="[triage:needs_manual_review]",
        )
        summary = summarize_alert_lifecycle_for_property(
            property_id=pid, database_path=temp_db,
        )
        assert summary.no_archive_count == 1
        assert summary.needs_reparse_count == 1
        assert summary.needs_manual_review_count == 1


# ---------------------------------------------------------------------------
# Test: Lifecycle labels
# ---------------------------------------------------------------------------


class TestLifecycleLabels:
    def test_active_label(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_property,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(
            temp_db, pid, alert_status="open",
            created_at=datetime.now().isoformat(),
        )
        summary = summarize_alert_lifecycle_for_property(
            property_id=pid, database_path=temp_db,
        )
        assert summary.lifecycle_summary_label == "active_alerts"

    def test_under_review_label(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_property,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(
            temp_db, pid, alert_status="acknowledged",
            created_at=datetime.now().isoformat(),
        )
        summary = summarize_alert_lifecycle_for_property(
            property_id=pid, database_path=temp_db,
        )
        assert summary.lifecycle_summary_label == "under_review"

    def test_mostly_resolved_label(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_property,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(
            temp_db, pid, alert_status="resolved",
            created_at=datetime.now().isoformat(),
        )
        summary = summarize_alert_lifecycle_for_property(
            property_id=pid, database_path=temp_db,
        )
        assert summary.lifecycle_summary_label == "mostly_resolved"

    def test_archived_history_label(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_property,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(
            temp_db, pid, alert_status="archived",
            created_at=datetime.now().isoformat(),
        )
        summary = summarize_alert_lifecycle_for_property(
            property_id=pid, database_path=temp_db,
        )
        assert summary.lifecycle_summary_label == "archived_history"

    def test_needs_attention_label(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_property,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(
            temp_db, pid, severity="high", alert_status="open",
            created_at=datetime.now().isoformat(),
        )
        summary = summarize_alert_lifecycle_for_property(
            property_id=pid, database_path=temp_db,
        )
        assert summary.lifecycle_summary_label == "needs_attention"


# ---------------------------------------------------------------------------
# Test: Gap detection
# ---------------------------------------------------------------------------


class TestOpenAlertGap:
    def test_open_no_triage_gap(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            detect_alert_lifecycle_gaps,
        )
        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="open", created_at=old_date,
        )
        gaps = detect_alert_lifecycle_gaps(
            database_path=temp_db, open_stale_days=7,
        )
        assert len(gaps) >= 1
        cats = [g["gap_category"] for g in gaps]
        assert "open_no_triage" in cats


class TestNeedsReparseGap:
    def test_needs_reparse_unresolved(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            detect_alert_lifecycle_gaps,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(
            temp_db, pid, alert_status="open",
            notes="[triage:needs_reparse]",
        )
        gaps = detect_alert_lifecycle_gaps(database_path=temp_db)
        cats = [g["gap_category"] for g in gaps]
        assert "needs_reparse_unresolved" in cats


class TestNeedsManualReviewGap:
    def test_needs_manual_review_unresolved(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            detect_alert_lifecycle_gaps,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(
            temp_db, pid, alert_status="open",
            notes="[triage:needs_manual_review]",
        )
        gaps = detect_alert_lifecycle_gaps(database_path=temp_db)
        cats = [g["gap_category"] for g in gaps]
        assert "needs_manual_review_unresolved" in cats


class TestAcknowledgedStaleGap:
    def test_acknowledged_stale(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            detect_alert_lifecycle_gaps,
        )
        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=20)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="acknowledged",
            created_at=old_date,
        )
        gaps = detect_alert_lifecycle_gaps(
            database_path=temp_db, ack_stale_days=14,
        )
        cats = [g["gap_category"] for g in gaps]
        assert "acknowledged_stale" in cats


class TestResolvedArchiveCandidateGap:
    def test_resolved_archive_candidate(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            detect_alert_lifecycle_gaps,
        )
        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=35)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="resolved",
            created_at=old_date,
        )
        gaps = detect_alert_lifecycle_gaps(
            database_path=temp_db, resolved_archive_days=30,
        )
        cats = [g["gap_category"] for g in gaps]
        assert "resolved_archive_candidate" in cats

    def test_no_archive_excludes_gap(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            detect_alert_lifecycle_gaps,
        )
        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=35)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="resolved",
            created_at=old_date, notes="[no_archive]",
        )
        gaps = detect_alert_lifecycle_gaps(
            database_path=temp_db, resolved_archive_days=30,
        )
        cats = [g["gap_category"] for g in gaps]
        assert "resolved_archive_candidate" not in cats


class TestReopenedStaleGap:
    def test_reopened_stale(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            detect_alert_lifecycle_gaps,
        )
        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="open", created_at=old_date,
        )
        _insert_triage_action(
            temp_db, aid, pid, "reopen", "resolved", "open",
        )
        gaps = detect_alert_lifecycle_gaps(
            database_path=temp_db, reopened_stale_days=7,
        )
        cats = [g["gap_category"] for g in gaps]
        assert "reopened_stale" in cats


# ---------------------------------------------------------------------------
# Test: CSV report export
# ---------------------------------------------------------------------------


class TestCSVReportExport:
    def test_csv_export_creates_file(self, temp_db, temp_exports_dir):
        from marketsentry.cross_site_alert_lifecycle import (
            export_cross_site_alert_lifecycle_report,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        result = export_cross_site_alert_lifecycle_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
            format="csv",
        )
        assert result.export_path is not None
        assert Path(result.export_path).exists()
        assert len(result.report_rows) == 1

    def test_csv_has_required_columns(self, temp_db, temp_exports_dir):
        from marketsentry.cross_site_alert_lifecycle import (
            export_cross_site_alert_lifecycle_report,
            LIFECYCLE_CSV_FIELDNAMES,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        result = export_cross_site_alert_lifecycle_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
            format="csv",
        )
        with open(result.export_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames
            for col in LIFECYCLE_CSV_FIELDNAMES:
                assert col in columns


# ---------------------------------------------------------------------------
# Test: Markdown report export
# ---------------------------------------------------------------------------


class TestMarkdownReportExport:
    def test_md_export_creates_file(self, temp_db, temp_exports_dir):
        from marketsentry.cross_site_alert_lifecycle import (
            export_cross_site_alert_lifecycle_report,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        result = export_cross_site_alert_lifecycle_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
            format="md",
        )
        assert result.export_path is not None
        assert result.export_path.endswith(".md")
        content = Path(result.export_path).read_text(encoding="utf-8")
        assert "Lifecycle Audit Report" in content

    def test_both_format(self, temp_db, temp_exports_dir):
        from marketsentry.cross_site_alert_lifecycle import (
            export_cross_site_alert_lifecycle_report,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        result = export_cross_site_alert_lifecycle_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
            format="both",
        )
        # Should have export_path set (CSV takes precedence)
        assert result.export_path is not None
        # Check both files exist
        csv_files = list(
            Path(temp_exports_dir).glob("cross_site_alert_lifecycle_*.csv")
        )
        md_files = list(
            Path(temp_exports_dir).glob("cross_site_alert_lifecycle_*.md")
        )
        assert len(csv_files) == 1
        assert len(md_files) == 1


# ---------------------------------------------------------------------------
# Test: CLI lifecycle summary
# ---------------------------------------------------------------------------


class TestCLILifecycleSummary:
    def test_cli_summary(self, temp_db):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["cross-site-alert-lifecycle-summary", "--db", temp_db],
        )
        assert result.exit_code == 0
        assert "Lifecycle Summary" in result.output

    def test_cli_summary_empty(self, temp_db):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["cross-site-alert-lifecycle-summary", "--db", temp_db],
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Test: CLI export lifecycle report
# ---------------------------------------------------------------------------


class TestCLIExportLifecycleReport:
    def test_cli_export(self, temp_db, temp_exports_dir):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "export-cross-site-alert-lifecycle-report",
                "--db", temp_db,
                "--output-dir", temp_exports_dir,
            ],
        )
        assert result.exit_code == 0
        assert "Report saved to" in result.output


# ---------------------------------------------------------------------------
# Test: CLI show alert lifecycle
# ---------------------------------------------------------------------------


class TestCLIShowAlertLifecycle:
    def test_cli_show(self, temp_db):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid)

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "show-cross-site-alert-lifecycle",
                "--alert-id", str(aid),
                "--db", temp_db,
            ],
        )
        assert result.exit_code == 0
        assert "alert_created" in result.output

    def test_cli_show_nonexistent(self, temp_db):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "show-cross-site-alert-lifecycle",
                "--alert-id", "99999",
                "--db", temp_db,
            ],
        )
        assert result.exit_code == 0
        assert "No lifecycle events" in result.output


# ---------------------------------------------------------------------------
# Test: Dashboard lifecycle table loads
# ---------------------------------------------------------------------------


class TestDashboardLifecycle:
    def test_imports(self):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_all_properties,
            detect_alert_lifecycle_gaps,
        )
        assert callable(summarize_alert_lifecycle_for_all_properties)
        assert callable(detect_alert_lifecycle_gaps)

    def test_summary_types(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_all_properties,
        )
        summary = summarize_alert_lifecycle_for_all_properties(
            database_path=temp_db,
        )
        assert isinstance(summary, CrossSiteAlertLifecycleSummary)
        assert isinstance(summary.property_summaries, list)


# ---------------------------------------------------------------------------
# Test: All properties summary
# ---------------------------------------------------------------------------


class TestAllPropertiesSummary:
    def test_aggregates_properties(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_all_properties,
        )
        pid1 = _insert_watched_property(temp_db, "111 A St")
        pid2 = _insert_watched_property(temp_db, "222 B St")
        _insert_alert(temp_db, pid1)
        _insert_alert(temp_db, pid2)
        _insert_alert(temp_db, pid2)

        summary = summarize_alert_lifecycle_for_all_properties(
            database_path=temp_db,
        )
        assert summary.total_properties_with_alerts == 2
        assert summary.total_alerts == 3

    def test_recommended_actions(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_all_properties,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_status="open")
        summary = summarize_alert_lifecycle_for_all_properties(
            database_path=temp_db,
        )
        assert len(summary.recommended_actions) > 0


# ---------------------------------------------------------------------------
# Test: Build alert lifecycle
# ---------------------------------------------------------------------------


class TestBuildAlertLifecycle:
    def test_single_alert(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            build_alert_lifecycle_for_alert,
        )
        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid)
        events = build_alert_lifecycle_for_alert(
            alert_id=aid, database_path=temp_db,
        )
        assert len(events) == 1
        assert events[0].event_type == "alert_created"

    def test_with_actions(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            build_alert_lifecycle_for_alert,
        )
        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid)
        _insert_triage_action(
            temp_db, aid, pid, "acknowledge", "open", "acknowledged",
        )
        events = build_alert_lifecycle_for_alert(
            alert_id=aid, database_path=temp_db,
        )
        assert len(events) == 2


# ---------------------------------------------------------------------------
# Test: Format lifecycle summary
# ---------------------------------------------------------------------------


class TestFormatSummary:
    def test_format_output(self):
        from marketsentry.cross_site_alert_lifecycle import (
            format_alert_lifecycle_summary,
        )
        summary = CrossSiteAlertLifecycleSummary(
            total_properties_with_alerts=2,
            total_alerts=5,
            open_alerts=2,
            acknowledged_alerts=1,
            resolved_alerts=1,
            archived_alerts=1,
        )
        text = format_alert_lifecycle_summary(summary)
        assert "Lifecycle Summary" in text
        assert "Properties with alerts: 2" in text
        assert "Read-only audit" in text


# ---------------------------------------------------------------------------
# Test: No mutation behavior
# ---------------------------------------------------------------------------


class TestNoMutation:
    def test_summary_does_not_mutate(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_all_properties,
        )
        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="open")

        summarize_alert_lifecycle_for_all_properties(
            database_path=temp_db,
        )

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,), temp_db,
        )
        assert rows[0]["alert_status"] == "open"

    def test_export_does_not_mutate(self, temp_db, temp_exports_dir):
        from marketsentry.cross_site_alert_lifecycle import (
            export_cross_site_alert_lifecycle_report,
        )
        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(temp_db, pid, alert_status="open")

        export_cross_site_alert_lifecycle_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
        )

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,), temp_db,
        )
        assert rows[0]["alert_status"] == "open"

    def test_gaps_do_not_mutate(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            detect_alert_lifecycle_gaps,
        )
        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=10)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="open", created_at=old,
        )

        detect_alert_lifecycle_gaps(database_path=temp_db)

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,), temp_db,
        )
        assert rows[0]["alert_status"] == "open"

    def test_watchlist_unchanged(self, temp_db):
        from marketsentry.cross_site_alert_lifecycle import (
            summarize_alert_lifecycle_for_all_properties,
        )
        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        before = execute_query(
            "SELECT active_watch_status FROM watched_properties "
            "WHERE property_id = ?",
            (pid,), temp_db,
        )

        summarize_alert_lifecycle_for_all_properties(
            database_path=temp_db,
        )

        after = execute_query(
            "SELECT active_watch_status FROM watched_properties "
            "WHERE property_id = ?",
            (pid,), temp_db,
        )
        assert before[0]["active_watch_status"] == (
            after[0]["active_watch_status"]
        )


# ---------------------------------------------------------------------------
# Test: No Redfin overwrite
# ---------------------------------------------------------------------------


class TestNoRedfin:
    def test_no_redfin_overwrite(self, temp_db):
        import inspect
        from marketsentry import cross_site_alert_lifecycle as mod
        source = inspect.getsource(mod)
        assert "redfin" not in source.lower() or (
            "redfin" in source.lower()
            and "overwrite" not in source.lower()
        )


# ---------------------------------------------------------------------------
# Test: Quiet gatekeeper unchanged
# ---------------------------------------------------------------------------


class TestQuietGatekeeperUnchanged:
    def test_no_quiet_modification(self):
        import inspect
        from marketsentry import cross_site_alert_lifecycle as mod
        source = inspect.getsource(mod)
        assert "quiet_score" not in source.lower()
        assert "vibrancy_score" not in source.lower()


# ---------------------------------------------------------------------------
# Test: No walkability fields
# ---------------------------------------------------------------------------


class TestNoWalkabilityFields:
    def test_no_walkability(self):
        import inspect
        from marketsentry import cross_site_alert_lifecycle as mod
        source = inspect.getsource(mod)
        assert "walkability" not in source.lower()
        assert "walk_score" not in source.lower()


# ---------------------------------------------------------------------------
# Test: No network calls
# ---------------------------------------------------------------------------


class TestNoNetworkCalls:
    def test_no_requests_import(self):
        import inspect
        from marketsentry import cross_site_alert_lifecycle as mod
        source = inspect.getsource(mod)
        assert "import requests" not in source
        assert "urllib.request" not in source

    def test_no_network_calls(self):
        import inspect
        from marketsentry import cross_site_alert_lifecycle as mod
        source = inspect.getsource(mod)
        assert "requests.get" not in source
        assert "requests.post" not in source
        assert "urlopen" not in source


# ---------------------------------------------------------------------------
# Test: Model fields
# ---------------------------------------------------------------------------


class TestModelFields:
    def test_lifecycle_event_fields(self):
        ev = CrossSiteAlertLifecycleEvent()
        assert hasattr(ev, "event_id")
        assert hasattr(ev, "alert_id")
        assert hasattr(ev, "property_id")
        assert hasattr(ev, "candidate_id")
        assert hasattr(ev, "event_type")
        assert hasattr(ev, "previous_status")
        assert hasattr(ev, "new_status")
        assert hasattr(ev, "action")
        assert hasattr(ev, "source_workflow")
        assert hasattr(ev, "event_notes")
        assert hasattr(ev, "event_at")
        assert hasattr(ev, "source_table")
        assert hasattr(ev, "source_reference")

    def test_property_summary_fields(self):
        ps = CrossSiteAlertLifecyclePropertySummary()
        assert hasattr(ps, "total_alerts")
        assert hasattr(ps, "open_alerts")
        assert hasattr(ps, "lifecycle_gap_count")
        assert hasattr(ps, "lifecycle_summary_label")
        assert hasattr(ps, "oldest_open_alert_age_days")
        assert hasattr(ps, "unresolved_high_or_critical_count")

    def test_report_row_fields(self):
        rr = CrossSiteAlertLifecycleReportRow()
        assert hasattr(rr, "property_id")
        assert hasattr(rr, "alert_id")
        assert hasattr(rr, "gap_categories")
        assert hasattr(rr, "recommended_review_action")

    def test_run_result_fields(self):
        rr = CrossSiteAlertLifecycleRunResult()
        assert hasattr(rr, "summary")
        assert hasattr(rr, "report_rows")
        assert hasattr(rr, "events")
        assert hasattr(rr, "gaps")
        assert hasattr(rr, "export_path")

    def test_summary_fields(self):
        s = CrossSiteAlertLifecycleSummary()
        assert hasattr(s, "total_properties_with_alerts")
        assert hasattr(s, "total_gaps")
        assert hasattr(s, "recommended_actions")


# ---------------------------------------------------------------------------
# Test: Source workflow detection
# ---------------------------------------------------------------------------


class TestSourceWorkflowDetection:
    def test_triage_prefix(self):
        from marketsentry.cross_site_alert_lifecycle import (
            _detect_source_workflow,
        )
        assert _detect_source_workflow("triage_abc") == "triage"

    def test_archive_prefix(self):
        from marketsentry.cross_site_alert_lifecycle import (
            _detect_source_workflow,
        )
        assert _detect_source_workflow("archive_xyz") == "archive_policy"

    def test_expiration_prefix(self):
        from marketsentry.cross_site_alert_lifecycle import (
            _detect_source_workflow,
        )
        assert (
            _detect_source_workflow("expiration_123")
            == "expiration_policy"
        )

    def test_unknown_prefix(self):
        from marketsentry.cross_site_alert_lifecycle import (
            _detect_source_workflow,
        )
        assert _detect_source_workflow("other_foo") == "unknown"

    def test_empty(self):
        from marketsentry.cross_site_alert_lifecycle import (
            _detect_source_workflow,
        )
        assert _detect_source_workflow("") == "unknown"
