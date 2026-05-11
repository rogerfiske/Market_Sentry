"""Tests for Milestone 30: Opt-In Resolved Alert Archive Policy Workflow.

Tests cover:
- Identify archive candidates by age
- Exclude open alerts
- Exclude acknowledged alerts
- Exclude already archived alerts
- Exclude no_archive marked alerts
- Export archive candidate CSV
- Default archive_decision is keep_resolved
- Import validates archive_export_id
- Import validates alert_id exists
- Import validates current_status mismatch
- Force status mismatch allows apply
- Archive decision sets status archived
- Reopen decision sets status open
- Keep_resolved does not change status
- No_archive adds marker and does not change status
- Archive notes appended
- Action history recorded
- CLI export-cross-site-alert-archive-candidates
- CLI import-cross-site-alert-archive-decisions
- CLI cross-site-alert-archive-summary
- Dashboard archive policy table loads
- Hygiene recommendation references archive workflow
- No auto-archive behavior
- No Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- No walkability fields added
- No real network calls
- Existing MVP 1-29 tests still pass (run with full suite)
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
    CrossSiteAlertArchiveCandidate,
    CrossSiteAlertArchiveDecision,
    CrossSiteAlertArchiveExportResult,
    CrossSiteAlertArchiveImportResult,
    CrossSiteAlertArchiveSummary,
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
    notes: str = "",
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
            snapshot_id, created_at, message, recommended_action, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            property_id, alert_type, severity, alert_status,
            snapshot_id, created_at,
            f"Test {alert_type} alert",
            "Review cross-site data",
            notes,
        ),
    )
    aid = cursor.lastrowid
    conn.commit()
    conn.close()
    return aid


def _create_archive_csv(
    temp_exports_dir: str,
    rows: list,
    archive_export_id: str = "archive_test123",
) -> str:
    """Create an archive candidate CSV for import testing."""
    from marketsentry.cross_site_alert_archive_policy import ARCHIVE_CSV_FIELDNAMES

    path = str(Path(temp_exports_dir) / "test_archive.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ARCHIVE_CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            full_row = {k: "" for k in ARCHIVE_CSV_FIELDNAMES}
            full_row["archive_export_id"] = archive_export_id
            full_row.update(row)
            writer.writerow(full_row)
    return path


# ---------------------------------------------------------------------------
# Test: Identify archive candidates by age
# ---------------------------------------------------------------------------


class TestIdentifyArchiveCandidates:
    """Test archive candidate identification."""

    def test_identifies_old_resolved_alert(self, temp_db):
        """Resolved alert older than threshold should be a candidate."""
        from marketsentry.cross_site_alert_archive_policy import (
            identify_resolved_alert_archive_candidates,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        candidates = identify_resolved_alert_archive_candidates(
            temp_db, resolved_age_days=30,
        )
        assert len(candidates) >= 1
        assert candidates[0].current_status == "resolved"
        assert candidates[0].alert_age_days >= 40

    def test_does_not_flag_recent_resolved(self, temp_db):
        """Resolved alert newer than threshold should not be a candidate."""
        from marketsentry.cross_site_alert_archive_policy import (
            identify_resolved_alert_archive_candidates,
        )

        pid = _insert_watched_property(temp_db)
        recent = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=recent,
        )

        candidates = identify_resolved_alert_archive_candidates(
            temp_db, resolved_age_days=30,
        )
        assert len(candidates) == 0

    def test_excludes_open_alerts(self, temp_db):
        """Open alerts should never be archive candidates."""
        from marketsentry.cross_site_alert_archive_policy import (
            identify_resolved_alert_archive_candidates,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="open", created_at=old_date,
        )

        candidates = identify_resolved_alert_archive_candidates(
            temp_db, resolved_age_days=30,
        )
        assert len(candidates) == 0

    def test_excludes_acknowledged_alerts(self, temp_db):
        """Acknowledged alerts should never be archive candidates."""
        from marketsentry.cross_site_alert_archive_policy import (
            identify_resolved_alert_archive_candidates,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="acknowledged", created_at=old_date,
        )

        candidates = identify_resolved_alert_archive_candidates(
            temp_db, resolved_age_days=30,
        )
        assert len(candidates) == 0

    def test_excludes_already_archived_alerts(self, temp_db):
        """Already archived alerts should not be candidates."""
        from marketsentry.cross_site_alert_archive_policy import (
            identify_resolved_alert_archive_candidates,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="archived", created_at=old_date,
        )

        candidates = identify_resolved_alert_archive_candidates(
            temp_db, resolved_age_days=30,
        )
        assert len(candidates) == 0

    def test_excludes_no_archive_marked_alerts(self, temp_db):
        """Alerts with [no_archive] in notes should be excluded."""
        from marketsentry.cross_site_alert_archive_policy import (
            identify_resolved_alert_archive_candidates,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
            notes="[no_archive] Keep for reference",
        )

        candidates = identify_resolved_alert_archive_candidates(
            temp_db, resolved_age_days=30,
        )
        assert len(candidates) == 0

    def test_property_id_filter(self, temp_db):
        """Should filter by property_id when specified."""
        from marketsentry.cross_site_alert_archive_policy import (
            identify_resolved_alert_archive_candidates,
        )

        pid1 = _insert_watched_property(temp_db, "100 First St")
        pid2 = _insert_watched_property(temp_db, "200 Second St")
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(temp_db, pid1, alert_status="resolved", created_at=old_date)
        _insert_alert(temp_db, pid2, alert_status="resolved", created_at=old_date)

        candidates = identify_resolved_alert_archive_candidates(
            temp_db, resolved_age_days=30, property_id=pid1,
        )
        assert len(candidates) == 1
        assert candidates[0].property_id == pid1

    def test_returns_empty_when_table_missing(self):
        """Should return empty list if alerts table does not exist."""
        from marketsentry.cross_site_alert_archive_policy import (
            identify_resolved_alert_archive_candidates,
        )

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            empty_db = f.name
        try:
            candidates = identify_resolved_alert_archive_candidates(
                empty_db, resolved_age_days=30,
            )
            assert candidates == []
        finally:
            os.unlink(empty_db)


# ---------------------------------------------------------------------------
# Test: Export archive candidate CSV
# ---------------------------------------------------------------------------


class TestExportArchiveCandidates:
    """Test archive candidate CSV export."""

    def test_export_creates_csv(self, temp_db, temp_exports_dir):
        """Export should create a CSV file."""
        from marketsentry.cross_site_alert_archive_policy import (
            export_cross_site_alert_archive_candidates,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(temp_db, pid, alert_status="resolved", created_at=old_date)

        result = export_cross_site_alert_archive_candidates(
            database_path=temp_db, exports_dir=temp_exports_dir,
        )

        assert Path(result.output_path).exists()
        assert result.row_count >= 1
        assert result.archive_export_id.startswith("archive_")

    def test_default_decision_is_keep_resolved(self, temp_db, temp_exports_dir):
        """Default archive_decision should be keep_resolved."""
        from marketsentry.cross_site_alert_archive_policy import (
            export_cross_site_alert_archive_candidates,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(temp_db, pid, alert_status="resolved", created_at=old_date)

        result = export_cross_site_alert_archive_candidates(
            database_path=temp_db, exports_dir=temp_exports_dir,
        )

        with open(result.output_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                assert row["archive_decision"] == "keep_resolved"

    def test_csv_has_required_columns(self, temp_db, temp_exports_dir):
        """CSV should contain all required columns."""
        from marketsentry.cross_site_alert_archive_policy import (
            ARCHIVE_CSV_FIELDNAMES,
            export_cross_site_alert_archive_candidates,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(temp_db, pid, alert_status="resolved", created_at=old_date)

        result = export_cross_site_alert_archive_candidates(
            database_path=temp_db, exports_dir=temp_exports_dir,
        )

        with open(result.output_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert set(ARCHIVE_CSV_FIELDNAMES).issubset(set(reader.fieldnames))


# ---------------------------------------------------------------------------
# Test: Import validation
# ---------------------------------------------------------------------------


class TestImportValidation:
    """Test archive decision import validation."""

    def test_validates_archive_export_id(self, temp_db, temp_exports_dir):
        """Import should accept rows with valid archive_export_id."""
        from marketsentry.cross_site_alert_archive_policy import (
            validate_cross_site_alert_archive_decisions,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        rows = [{
            "alert_id": str(aid),
            "archive_export_id": "archive_abc123",
            "current_status": "resolved",
            "archive_decision": "archive",
        }]

        valid = validate_cross_site_alert_archive_decisions(
            rows, database_path=temp_db,
        )
        assert len(valid) == 1

    def test_validates_alert_id_exists(self, temp_db, temp_exports_dir):
        """Import should reject rows with nonexistent alert_id."""
        from marketsentry.cross_site_alert_archive_policy import (
            validate_cross_site_alert_archive_decisions,
        )

        rows = [{
            "alert_id": "99999",
            "archive_export_id": "archive_abc123",
            "current_status": "resolved",
            "archive_decision": "archive",
        }]

        valid = validate_cross_site_alert_archive_decisions(
            rows, database_path=temp_db,
        )
        assert len(valid) == 0

    def test_validates_status_mismatch(self, temp_db, temp_exports_dir):
        """Import should skip rows with status mismatch by default."""
        from marketsentry.cross_site_alert_archive_policy import (
            apply_cross_site_alert_archive_decisions,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="open", created_at=old_date,
        )

        path = _create_archive_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "archive_decision": "archive",
        }])

        result = apply_cross_site_alert_archive_decisions(
            file_path=path, database_path=temp_db,
        )
        assert result.skipped_status_mismatch >= 1

    def test_force_status_mismatch_allows_apply(self, temp_db, temp_exports_dir):
        """Force flag should allow apply even with status mismatch."""
        from marketsentry.cross_site_alert_archive_policy import (
            apply_cross_site_alert_archive_decisions,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        # CSV says "open" but alert is actually "resolved"
        path = _create_archive_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "open",
            "archive_decision": "archive",
        }])

        result = apply_cross_site_alert_archive_decisions(
            file_path=path, database_path=temp_db,
            force_status_mismatch=True,
        )
        assert result.archived >= 1

    def test_invalid_decision_rejected(self, temp_db, temp_exports_dir):
        """Invalid archive_decision should be rejected."""
        from marketsentry.cross_site_alert_archive_policy import (
            apply_cross_site_alert_archive_decisions,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        path = _create_archive_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "archive_decision": "invalid_decision",
        }])

        result = apply_cross_site_alert_archive_decisions(
            file_path=path, database_path=temp_db,
        )
        assert result.invalid_rows >= 1


# ---------------------------------------------------------------------------
# Test: Decision behavior
# ---------------------------------------------------------------------------


class TestDecisionBehavior:
    """Test archive decision application behavior."""

    def test_archive_sets_status_archived(self, temp_db, temp_exports_dir):
        """Archive decision should set alert_status to archived."""
        from marketsentry.cross_site_alert_archive_policy import (
            apply_cross_site_alert_archive_decisions,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        path = _create_archive_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "archive_decision": "archive",
        }])

        apply_cross_site_alert_archive_decisions(
            file_path=path, database_path=temp_db,
        )

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "archived"

    def test_reopen_sets_status_open(self, temp_db, temp_exports_dir):
        """Reopen decision should set alert_status to open."""
        from marketsentry.cross_site_alert_archive_policy import (
            apply_cross_site_alert_archive_decisions,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        path = _create_archive_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "archive_decision": "reopen",
        }])

        apply_cross_site_alert_archive_decisions(
            file_path=path, database_path=temp_db,
        )

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "open"

    def test_keep_resolved_does_not_change_status(self, temp_db, temp_exports_dir):
        """Keep_resolved should not change status."""
        from marketsentry.cross_site_alert_archive_policy import (
            apply_cross_site_alert_archive_decisions,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        path = _create_archive_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "archive_decision": "keep_resolved",
        }])

        result = apply_cross_site_alert_archive_decisions(
            file_path=path, database_path=temp_db,
        )

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "resolved"
        assert result.kept_resolved >= 1

    def test_no_archive_adds_marker(self, temp_db, temp_exports_dir):
        """No_archive should add [no_archive] marker to notes."""
        from marketsentry.cross_site_alert_archive_policy import (
            apply_cross_site_alert_archive_decisions,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        path = _create_archive_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "archive_decision": "no_archive",
            "archive_notes": "Keep for reference",
        }])

        result = apply_cross_site_alert_archive_decisions(
            file_path=path, database_path=temp_db,
        )

        rows = execute_query(
            "SELECT alert_status, notes FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "resolved"
        assert "[no_archive]" in rows[0]["notes"]
        assert result.no_archive >= 1

    def test_no_archive_excludes_from_future_candidates(self, temp_db, temp_exports_dir):
        """Alert with [no_archive] should be excluded from future candidates."""
        from marketsentry.cross_site_alert_archive_policy import (
            apply_cross_site_alert_archive_decisions,
            identify_resolved_alert_archive_candidates,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        # First verify it's a candidate
        before = identify_resolved_alert_archive_candidates(
            temp_db, resolved_age_days=30,
        )
        assert len(before) >= 1

        # Mark as no_archive
        path = _create_archive_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "archive_decision": "no_archive",
        }])
        apply_cross_site_alert_archive_decisions(
            file_path=path, database_path=temp_db,
        )

        # Verify it's no longer a candidate
        after = identify_resolved_alert_archive_candidates(
            temp_db, resolved_age_days=30,
        )
        assert len(after) == 0


# ---------------------------------------------------------------------------
# Test: Notes appended
# ---------------------------------------------------------------------------


class TestNotesAppended:
    """Test archive notes are appended."""

    def test_archive_notes_appended(self, temp_db, temp_exports_dir):
        """Archive notes should be appended to alert notes."""
        from marketsentry.cross_site_alert_archive_policy import (
            apply_cross_site_alert_archive_decisions,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
            notes="existing note",
        )

        path = _create_archive_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "archive_decision": "keep_resolved",
            "archive_notes": "reviewed 2026-05",
        }])

        apply_cross_site_alert_archive_decisions(
            file_path=path, database_path=temp_db,
        )

        rows = execute_query(
            "SELECT notes FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert "existing note" in rows[0]["notes"]
        assert "reviewed 2026-05" in rows[0]["notes"]


# ---------------------------------------------------------------------------
# Test: Action history recorded
# ---------------------------------------------------------------------------


class TestActionHistory:
    """Test archive action history recording."""

    def test_archive_action_recorded(self, temp_db, temp_exports_dir):
        """Archive action should be recorded in triage_actions table."""
        from marketsentry.cross_site_alert_archive_policy import (
            apply_cross_site_alert_archive_decisions,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        path = _create_archive_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "archive_decision": "archive",
            "archive_notes": "old resolved",
        }])

        apply_cross_site_alert_archive_decisions(
            file_path=path, database_path=temp_db,
        )

        actions = execute_query(
            """SELECT * FROM cross_site_alert_triage_actions
               WHERE alert_id = ? AND triage_export_id LIKE 'archive_%'""",
            (aid,), database_path=temp_db,
        )
        assert len(actions) >= 1
        assert actions[0]["action"] == "archive"
        assert actions[0]["new_status"] == "archived"

    def test_no_archive_action_recorded(self, temp_db, temp_exports_dir):
        """No_archive action should be recorded in triage_actions table."""
        from marketsentry.cross_site_alert_archive_policy import (
            apply_cross_site_alert_archive_decisions,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        path = _create_archive_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "archive_decision": "no_archive",
        }])

        apply_cross_site_alert_archive_decisions(
            file_path=path, database_path=temp_db,
        )

        actions = execute_query(
            """SELECT * FROM cross_site_alert_triage_actions
               WHERE alert_id = ? AND action = 'no_archive'""",
            (aid,), database_path=temp_db,
        )
        assert len(actions) >= 1


# ---------------------------------------------------------------------------
# Test: CLI commands
# ---------------------------------------------------------------------------


class TestCLIExportArchive:
    """Test CLI export-cross-site-alert-archive-candidates."""

    def test_cli_export_runs(self, temp_db, temp_exports_dir):
        """CLI export command should run without errors."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "export-cross-site-alert-archive-candidates",
                "--db", temp_db,
                "--output-dir", temp_exports_dir,
            ],
        )

        assert result.exit_code == 0
        assert "SUCCESS" in result.output

    def test_cli_export_shows_counts(self, temp_db, temp_exports_dir):
        """CLI export should show candidate count."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(temp_db, pid, alert_status="resolved", created_at=old_date)

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "export-cross-site-alert-archive-candidates",
                "--db", temp_db,
                "--output-dir", temp_exports_dir,
            ],
        )

        assert result.exit_code == 0
        assert "Candidate rows" in result.output


class TestCLIImportArchive:
    """Test CLI import-cross-site-alert-archive-decisions."""

    def test_cli_import_runs(self, temp_db, temp_exports_dir):
        """CLI import command should run without errors."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        path = _create_archive_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "archive_decision": "keep_resolved",
        }])

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "import-cross-site-alert-archive-decisions",
                "--file", path,
                "--db", temp_db,
            ],
        )

        assert result.exit_code == 0
        assert "SUCCESS" in result.output


class TestCLIArchiveSummary:
    """Test CLI cross-site-alert-archive-summary."""

    def test_cli_summary_runs(self, temp_db):
        """CLI summary command should run without errors."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "cross-site-alert-archive-summary",
                "--db", temp_db,
            ],
        )

        assert result.exit_code == 0
        assert "Eligible archive candidates" in result.output

    def test_cli_summary_shows_counts(self, temp_db):
        """CLI summary should show relevant counts."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(temp_db, pid, alert_status="resolved", created_at=old_date)

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["cross-site-alert-archive-summary", "--db", temp_db],
        )

        assert result.exit_code == 0
        assert "Already archived" in result.output


# ---------------------------------------------------------------------------
# Test: Dashboard integration
# ---------------------------------------------------------------------------


class TestDashboardArchivePolicy:
    """Test dashboard archive policy integration."""

    def test_build_archive_table_with_csv(self, temp_db, temp_exports_dir):
        """Dashboard should load archive data from CSV."""
        from marketsentry.cross_site_alert_archive_policy import (
            export_cross_site_alert_archive_candidates,
        )
        from marketsentry.dashboard import build_cross_site_alert_archive_policy_table

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(temp_db, pid, alert_status="resolved", created_at=old_date)

        export_cross_site_alert_archive_candidates(
            database_path=temp_db, exports_dir=temp_exports_dir,
        )

        df = build_cross_site_alert_archive_policy_table(temp_exports_dir)
        assert not df.empty
        assert "alert_id" in df.columns
        assert "archive_decision" in df.columns

    def test_build_archive_table_empty_when_no_report(self, temp_exports_dir):
        """Dashboard should return empty DataFrame when no report."""
        from marketsentry.dashboard import build_cross_site_alert_archive_policy_table

        df = build_cross_site_alert_archive_policy_table(temp_exports_dir)
        assert df.empty

    def test_archive_table_imported_in_dashboard_app(self):
        """Dashboard app should import the archive table builder."""
        from marketsentry.dashboard_app import (
            build_cross_site_alert_archive_policy_table,
        )

        assert callable(build_cross_site_alert_archive_policy_table)


# ---------------------------------------------------------------------------
# Test: Hygiene recommendation references archive workflow
# ---------------------------------------------------------------------------


class TestHygieneIntegration:
    """Test hygiene recommendation update."""

    def test_hygiene_next_actions_reference_archive_workflow(self):
        """Hygiene next actions should reference archive candidates command."""
        from marketsentry.cross_site_alert_hygiene import (
            generate_alert_hygiene_next_actions,
        )
        from marketsentry.models import CrossSiteAlertHygieneSummary

        summary = CrossSiteAlertHygieneSummary(resolved_archive_candidates=5)
        actions = generate_alert_hygiene_next_actions(summary)

        # Should reference the archive candidates command, not the triage command
        archive_actions = [
            a for a in actions
            if "export-cross-site-alert-archive-candidates" in a
        ]
        assert len(archive_actions) >= 1

    def test_hygiene_resolved_candidate_recommended_action(self, temp_db):
        """Resolved archive candidate should reference archive workflow."""
        from marketsentry.cross_site_alert_hygiene import (
            identify_old_resolved_alerts,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(temp_db, pid, alert_status="resolved", created_at=old_date)

        issues = identify_old_resolved_alerts(temp_db, archive_days=30)
        assert len(issues) >= 1
        assert "archive" in issues[0].recommended_action.lower()
        assert "archive_decision" in issues[0].recommended_action


# ---------------------------------------------------------------------------
# Test: No auto-archive behavior
# ---------------------------------------------------------------------------


class TestNoAutoArchive:
    """Test that no automatic archiving occurs."""

    def test_identify_does_not_change_status(self, temp_db):
        """Identifying candidates should not change any alert status."""
        from marketsentry.cross_site_alert_archive_policy import (
            identify_resolved_alert_archive_candidates,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        identify_resolved_alert_archive_candidates(temp_db, resolved_age_days=30)

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "resolved"

    def test_export_does_not_change_status(self, temp_db, temp_exports_dir):
        """Exporting candidates should not change any alert status."""
        from marketsentry.cross_site_alert_archive_policy import (
            export_cross_site_alert_archive_candidates,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        export_cross_site_alert_archive_candidates(
            database_path=temp_db, exports_dir=temp_exports_dir,
        )

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "resolved"

    def test_summary_does_not_change_status(self, temp_db):
        """Summarizing should not change any alert status."""
        from marketsentry.cross_site_alert_archive_policy import (
            summarize_cross_site_alert_archive_policy,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        summarize_cross_site_alert_archive_policy(database_path=temp_db)

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "resolved"


# ---------------------------------------------------------------------------
# Test: No Redfin source-of-truth overwrite
# ---------------------------------------------------------------------------


class TestNoRedfnOverwrite:
    """Test archive policy does not overwrite Redfin data."""

    def test_archive_does_not_modify_watched_properties(self, temp_db, temp_exports_dir):
        """Archive should not modify watched_properties table."""
        from marketsentry.cross_site_alert_archive_policy import (
            apply_cross_site_alert_archive_decisions,
        )

        pid = _insert_watched_property(temp_db, "99 Source St")
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old_date,
        )

        before = execute_query(
            "SELECT * FROM watched_properties WHERE property_id = ?",
            (pid,), database_path=temp_db,
        )

        path = _create_archive_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "archive_decision": "archive",
        }])
        apply_cross_site_alert_archive_decisions(
            file_path=path, database_path=temp_db,
        )

        after = execute_query(
            "SELECT * FROM watched_properties WHERE property_id = ?",
            (pid,), database_path=temp_db,
        )

        assert dict(before[0]) == dict(after[0])


# ---------------------------------------------------------------------------
# Test: Quiet gatekeeper unchanged
# ---------------------------------------------------------------------------


class TestQuietGatekeeperUnchanged:
    """Test Quiet Score gatekeeper is not modified."""

    def test_archive_module_does_not_import_quiet_score(self):
        """Archive module should not import quiet score."""
        import inspect
        import marketsentry.cross_site_alert_archive_policy as mod

        source = inspect.getsource(mod)
        assert "quiet_score" not in source.lower()
        assert "vibrancy" not in source.lower()


# ---------------------------------------------------------------------------
# Test: No walkability fields
# ---------------------------------------------------------------------------


class TestNoWalkabilityFields:
    """Test no walkability fields were added."""

    def test_archive_module_no_walkability(self):
        """Archive module should not reference walkability."""
        import inspect
        import marketsentry.cross_site_alert_archive_policy as mod

        source = inspect.getsource(mod)
        assert "walkability" not in source.lower()
        assert "walk_score" not in source.lower()

    def test_archive_models_no_walkability(self):
        """Archive models should not contain walkability fields."""
        candidate = CrossSiteAlertArchiveCandidate()
        export_result = CrossSiteAlertArchiveExportResult()
        import_result = CrossSiteAlertArchiveImportResult()
        decision = CrossSiteAlertArchiveDecision()
        summary = CrossSiteAlertArchiveSummary()

        for obj in [candidate, export_result, import_result, decision, summary]:
            for field in obj.model_fields:
                assert "walk" not in field.lower()


# ---------------------------------------------------------------------------
# Test: No network calls
# ---------------------------------------------------------------------------


class TestNoNetworkCalls:
    """Test no network calls are performed."""

    def test_archive_module_no_network_imports(self):
        """Archive module should not import network libraries."""
        import inspect
        import marketsentry.cross_site_alert_archive_policy as mod

        source = inspect.getsource(mod)
        assert "import requests" not in source
        assert "import httpx" not in source
        assert "import urllib" not in source
        assert "import aiohttp" not in source
        assert "playwright" not in source.lower()
        assert "selenium" not in source.lower()

    def test_archive_check_no_socket_calls(self, temp_db):
        """Running archive identification should not open network connections."""
        from marketsentry.cross_site_alert_archive_policy import (
            identify_resolved_alert_archive_candidates,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(temp_db, pid, alert_status="resolved", created_at=old_date)

        with patch("socket.socket") as mock_socket:
            identify_resolved_alert_archive_candidates(temp_db, resolved_age_days=30)
            mock_socket.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Scheduled scripts do not invoke archive mutation
# ---------------------------------------------------------------------------


class TestScheduledScriptsSafe:
    """Test scheduled scripts do not invoke archive mutations."""

    def test_hygiene_script_does_not_import_archive(self):
        """Hygiene batch script should not invoke archive import."""
        script = Path("scripts/run_alert_hygiene_report.bat")
        if script.exists():
            content = script.read_text(encoding="utf-8")
            assert "import-cross-site-alert-archive" not in content
            assert "--force-live" not in content

    def test_watchlist_script_does_not_import_archive(self):
        """Watchlist batch script should not invoke archive import."""
        script = Path("scripts/run_watchlist_refresh_workflow.bat")
        if script.exists():
            content = script.read_text(encoding="utf-8")
            assert "import-cross-site-alert-archive" not in content


# ---------------------------------------------------------------------------
# Test: Models
# ---------------------------------------------------------------------------


class TestArchiveModels:
    """Test archive policy models."""

    def test_candidate_default_decision(self):
        """Default archive_decision should be keep_resolved."""
        c = CrossSiteAlertArchiveCandidate()
        assert c.archive_decision == "keep_resolved"

    def test_export_result_defaults(self):
        """Export result should have expected defaults."""
        r = CrossSiteAlertArchiveExportResult()
        assert r.row_count == 0
        assert r.resolved_age_days == 30

    def test_import_result_defaults(self):
        """Import result should have expected defaults."""
        r = CrossSiteAlertArchiveImportResult()
        assert r.rows_read == 0
        assert r.archived == 0
        assert r.reopened == 0
        assert r.kept_resolved == 0
        assert r.no_archive == 0
        assert r.errors == []

    def test_summary_defaults(self):
        """Summary should have expected defaults."""
        s = CrossSiteAlertArchiveSummary()
        assert s.eligible_candidates == 0
        assert s.already_archived == 0
        assert s.no_archive_marked == 0
        assert s.next_actions == []

    def test_allowed_decisions_constant(self):
        """ALLOWED_ARCHIVE_DECISIONS should have the 4 expected values."""
        from marketsentry.cross_site_alert_archive_policy import (
            ALLOWED_ARCHIVE_DECISIONS,
        )

        assert "keep_resolved" in ALLOWED_ARCHIVE_DECISIONS
        assert "archive" in ALLOWED_ARCHIVE_DECISIONS
        assert "reopen" in ALLOWED_ARCHIVE_DECISIONS
        assert "no_archive" in ALLOWED_ARCHIVE_DECISIONS
        assert len(ALLOWED_ARCHIVE_DECISIONS) == 4


# ---------------------------------------------------------------------------
# Test: Summary
# ---------------------------------------------------------------------------


class TestArchiveSummary:
    """Test archive policy summary."""

    def test_summary_counts(self, temp_db):
        """Summary should have correct counts."""
        from marketsentry.cross_site_alert_archive_policy import (
            summarize_cross_site_alert_archive_policy,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()

        _insert_alert(temp_db, pid, alert_status="resolved", created_at=old_date)
        _insert_alert(temp_db, pid, alert_status="open")
        _insert_alert(temp_db, pid, alert_status="archived", created_at=old_date)

        summary = summarize_cross_site_alert_archive_policy(
            database_path=temp_db,
        )

        assert summary.eligible_candidates >= 1
        assert summary.total_resolved >= 1
        assert summary.total_open >= 1
        assert summary.already_archived >= 1

    def test_summary_next_actions(self, temp_db):
        """Summary should generate next actions."""
        from marketsentry.cross_site_alert_archive_policy import (
            summarize_cross_site_alert_archive_policy,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(temp_db, pid, alert_status="resolved", created_at=old_date)

        summary = summarize_cross_site_alert_archive_policy(
            database_path=temp_db,
        )

        assert len(summary.next_actions) >= 1
        assert any(
            "export" in a.lower()
            for a in summary.next_actions
        )
