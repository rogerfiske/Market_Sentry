"""Tests for Milestone 31: Configurable Alert Expiration Rules and Operator Approval Gates.

Tests cover:
- Default profiles exist
- Conservative profile thresholds
- Standard profile thresholds
- Aggressive_review_only profile thresholds
- Preview resolved alert archive candidate
- Preview acknowledged stale review candidate
- Preview open warning review candidate
- High/critical open alert review-only behavior
- No_archive alert excluded from archive mutation
- Export approval CSV
- Default approval_decision is keep_current
- Import validates expiration_export_id
- Import validates profile_name
- Import validates alert_id exists
- Import validates current_status mismatch
- Force status mismatch allows apply
- Approve_action applies proposed archive
- Approve_action for review appends notes only
- Mark_no_archive appends marker
- Reopen sets status open
- Acknowledge sets status acknowledged
- Resolve sets status resolved
- Archive sets status archived
- Action history recorded
- CLI list profiles
- CLI preview policy
- CLI export approval
- CLI import approval
- CLI summary
- Dashboard expiration policy table loads
- Hygiene recommendation mentions expiration approval workflow
- No auto-apply behavior
- No Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- No walkability fields added
- No real network calls
- Existing MVP 1-30 tests still pass (run with full suite)
"""

import csv
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from marketsentry.database import (
    execute_query,
    get_connection,
    init_db,
    table_exists,
)
from marketsentry.models import (
    CrossSiteAlertExpirationApplyResult,
    CrossSiteAlertExpirationApprovalRow,
    CrossSiteAlertExpirationCandidate,
    CrossSiteAlertExpirationPreviewResult,
    CrossSiteAlertExpirationProfile,
    CrossSiteAlertExpirationRule,
    CrossSiteAlertExpirationSummary,
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


def _create_approval_csv(
    temp_exports_dir: str,
    rows: list,
    expiration_export_id: str = "expiration_test123",
    profile_name: str = "standard",
) -> str:
    """Create an expiration approval CSV for import testing."""
    from marketsentry.cross_site_alert_expiration_policy import (
        EXPIRATION_CSV_FIELDNAMES,
    )

    path = str(Path(temp_exports_dir) / "test_expiration.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPIRATION_CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            full_row = {k: "" for k in EXPIRATION_CSV_FIELDNAMES}
            full_row["expiration_export_id"] = expiration_export_id
            full_row["profile_name"] = profile_name
            full_row.update(row)
            writer.writerow(full_row)
    return path


# ---------------------------------------------------------------------------
# Test: Default profiles exist
# ---------------------------------------------------------------------------


class TestDefaultProfiles:
    """Test that default expiration profiles are properly defined."""

    def test_profiles_exist(self):
        """All 3 default profiles should exist."""
        from marketsentry.cross_site_alert_expiration_policy import (
            get_default_expiration_profiles,
        )

        profiles = get_default_expiration_profiles()
        assert len(profiles) == 3
        names = {p.profile_name for p in profiles}
        assert names == {"conservative", "standard", "aggressive_review_only"}

    def test_conservative_thresholds(self):
        """Conservative profile uses long thresholds."""
        from marketsentry.cross_site_alert_expiration_policy import (
            load_expiration_profile,
        )

        profile = load_expiration_profile("conservative")
        assert profile is not None
        rules = {r.rule_name: r for r in profile.rules}

        # Resolved -> archive after 90 days
        assert rules["resolved_archive_90d"].age_threshold_days == 90
        assert rules["resolved_archive_90d"].proposed_action == "archive"

        # Acknowledged -> review after 45 days
        assert rules["acknowledged_review_45d"].age_threshold_days == 45
        assert rules["acknowledged_review_45d"].proposed_action == "review"

        # Open info/warning -> review after 30 days
        assert rules["open_info_warning_review_30d"].age_threshold_days == 30

    def test_standard_thresholds(self):
        """Standard profile uses balanced thresholds."""
        from marketsentry.cross_site_alert_expiration_policy import (
            load_expiration_profile,
        )

        profile = load_expiration_profile("standard")
        assert profile is not None
        rules = {r.rule_name: r for r in profile.rules}

        assert rules["resolved_archive_60d"].age_threshold_days == 60
        assert rules["acknowledged_review_30d"].age_threshold_days == 30
        assert rules["open_info_warning_review_21d"].age_threshold_days == 21

    def test_aggressive_thresholds(self):
        """Aggressive profile uses short thresholds."""
        from marketsentry.cross_site_alert_expiration_policy import (
            load_expiration_profile,
        )

        profile = load_expiration_profile("aggressive_review_only")
        assert profile is not None
        rules = {r.rule_name: r for r in profile.rules}

        assert rules["resolved_archive_30d"].age_threshold_days == 30
        assert rules["acknowledged_review_14d"].age_threshold_days == 14
        assert rules["open_info_warning_review_14d"].age_threshold_days == 14

    def test_all_profiles_have_high_critical_review_only(self):
        """All profiles have high/critical open alerts as review-only."""
        from marketsentry.cross_site_alert_expiration_policy import (
            get_default_expiration_profiles,
        )

        for profile in get_default_expiration_profiles():
            high_crit = [
                r for r in profile.rules
                if r.rule_name == "open_high_critical_review_only"
            ]
            assert len(high_crit) == 1
            assert high_crit[0].proposed_action == "review"


# ---------------------------------------------------------------------------
# Test: Preview policy
# ---------------------------------------------------------------------------


class TestPreviewPolicy:
    """Test preview_alert_expiration_policy."""

    def test_preview_resolved_archive_candidate(self, temp_db):
        """Resolved alerts older than threshold appear as archive candidate."""
        from marketsentry.cross_site_alert_expiration_policy import (
            preview_alert_expiration_policy,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=65)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old,
        )

        result = preview_alert_expiration_policy(
            database_path=temp_db, profile_name="standard",
        )

        assert result.total_candidates >= 1
        archive_cands = [
            c for c in result.candidates if c.proposed_action == "archive"
        ]
        assert len(archive_cands) >= 1

    def test_preview_acknowledged_review_candidate(self, temp_db):
        """Acknowledged alerts older than threshold appear as review."""
        from marketsentry.cross_site_alert_expiration_policy import (
            preview_alert_expiration_policy,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=35)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="acknowledged",
            severity="warning", created_at=old,
        )

        result = preview_alert_expiration_policy(
            database_path=temp_db, profile_name="standard",
        )

        review_cands = [
            c for c in result.candidates if c.proposed_action == "review"
        ]
        assert len(review_cands) >= 1

    def test_preview_open_warning_review_candidate(self, temp_db):
        """Open warning alerts older than threshold appear as review."""
        from marketsentry.cross_site_alert_expiration_policy import (
            preview_alert_expiration_policy,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=25)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="open",
            severity="warning", created_at=old,
        )

        result = preview_alert_expiration_policy(
            database_path=temp_db, profile_name="standard",
        )

        assert result.total_candidates >= 1
        assert result.proposed_review >= 1

    def test_high_critical_open_review_only(self, temp_db):
        """High/critical open alerts -> review only, never archive."""
        from marketsentry.cross_site_alert_expiration_policy import (
            preview_alert_expiration_policy,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=100)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="open",
            severity="high", created_at=old,
        )
        _insert_alert(
            temp_db, pid, alert_status="open",
            severity="critical", created_at=old,
        )

        result = preview_alert_expiration_policy(
            database_path=temp_db, profile_name="standard",
        )

        archive_cands = [
            c for c in result.candidates if c.proposed_action == "archive"
        ]
        assert len(archive_cands) == 0

        review_cands = [
            c for c in result.candidates if c.proposed_action == "review"
        ]
        assert len(review_cands) >= 2

    def test_no_archive_excluded_from_archive(self, temp_db):
        """Alerts with [no_archive] never get archive proposal."""
        from marketsentry.cross_site_alert_expiration_policy import (
            preview_alert_expiration_policy,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=100)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old,
            notes="[no_archive] Keep this",
        )

        result = preview_alert_expiration_policy(
            database_path=temp_db, profile_name="standard",
        )

        archive_cands = [
            c for c in result.candidates if c.proposed_action == "archive"
        ]
        assert len(archive_cands) == 0

    def test_archived_alerts_excluded(self, temp_db):
        """Already archived alerts are not included in preview."""
        from marketsentry.cross_site_alert_expiration_policy import (
            preview_alert_expiration_policy,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=100)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="archived", created_at=old,
        )

        result = preview_alert_expiration_policy(
            database_path=temp_db, profile_name="standard",
        )

        assert result.total_candidates == 0


# ---------------------------------------------------------------------------
# Test: Export approval CSV
# ---------------------------------------------------------------------------


class TestExportApproval:
    """Test export_alert_expiration_approval_csv."""

    def test_export_creates_csv(self, temp_db, temp_exports_dir):
        """Export creates a CSV file."""
        from marketsentry.cross_site_alert_expiration_policy import (
            export_alert_expiration_approval_csv,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=65)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old,
        )

        result = export_alert_expiration_approval_csv(
            database_path=temp_db,
            profile_name="standard",
            exports_dir=temp_exports_dir,
        )

        assert result["row_count"] >= 1
        assert Path(result["output_path"]).exists()
        assert result["expiration_export_id"].startswith("expiration_")

    def test_default_approval_decision_is_keep_current(
        self, temp_db, temp_exports_dir,
    ):
        """Default approval_decision in CSV is keep_current."""
        from marketsentry.cross_site_alert_expiration_policy import (
            export_alert_expiration_approval_csv,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=65)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old,
        )

        result = export_alert_expiration_approval_csv(
            database_path=temp_db,
            profile_name="standard",
            exports_dir=temp_exports_dir,
        )

        with open(result["output_path"], "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                assert row["approval_decision"] == "keep_current"

    def test_csv_has_required_columns(self, temp_db, temp_exports_dir):
        """CSV has all required columns."""
        from marketsentry.cross_site_alert_expiration_policy import (
            EXPIRATION_CSV_FIELDNAMES,
            export_alert_expiration_approval_csv,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=65)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old,
        )

        result = export_alert_expiration_approval_csv(
            database_path=temp_db,
            profile_name="standard",
            exports_dir=temp_exports_dir,
        )

        with open(result["output_path"], "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            for col in EXPIRATION_CSV_FIELDNAMES:
                assert col in headers


# ---------------------------------------------------------------------------
# Test: Import validation
# ---------------------------------------------------------------------------


class TestImportValidation:
    """Test validation during import."""

    def test_validates_expiration_export_id(self, temp_db, temp_exports_dir):
        """Import skips rows with missing expiration_export_id."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved",
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "approval_decision": "archive",
            "expiration_export_id": "",
            "profile_name": "standard",
        }], expiration_export_id="")

        result = apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        assert result.rows_read == 1
        assert result.invalid_rows == 1
        assert result.archived == 0

    def test_validates_profile_name(self, temp_db, temp_exports_dir):
        """Import skips rows with missing profile_name."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved",
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "approval_decision": "archive",
            "profile_name": "",
        }], profile_name="")

        result = apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        assert result.rows_read == 1
        assert result.invalid_rows == 1

    def test_validates_alert_id_exists(self, temp_db, temp_exports_dir):
        """Import skips rows where alert_id does not exist."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": "99999",
            "current_status": "resolved",
            "approval_decision": "archive",
        }])

        result = apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        assert result.invalid_rows >= 1

    def test_validates_current_status_mismatch(
        self, temp_db, temp_exports_dir,
    ):
        """Import skips rows if current_status does not match."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(
            temp_db, pid, alert_status="open",
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "approval_decision": "archive",
        }])

        result = apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        assert result.skipped_status_mismatch >= 1
        assert result.archived == 0

    def test_force_status_mismatch(self, temp_db, temp_exports_dir):
        """Force flag allows apply even on mismatch."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(
            temp_db, pid, alert_status="open",
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "approval_decision": "archive",
        }])

        result = apply_alert_expiration_approvals(
            file_path=path,
            database_path=temp_db,
            force_status_mismatch=True,
        )

        assert result.skipped_status_mismatch == 0
        assert result.archived >= 1


# ---------------------------------------------------------------------------
# Test: Decision behavior
# ---------------------------------------------------------------------------


class TestDecisionBehavior:
    """Test each approval decision type."""

    def test_approve_action_archive(self, temp_db, temp_exports_dir):
        """approve_action with proposed archive sets status archived."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=65)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old,
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "approval_decision": "approve_action",
            "proposed_action": "archive",
        }])

        result = apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        assert result.archived == 1
        assert result.approved_actions >= 1

        # Verify DB status
        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "archived"

    def test_approve_action_review_notes_only(
        self, temp_db, temp_exports_dir,
    ):
        """approve_action for review appends notes but no status change."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=35)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="acknowledged", created_at=old,
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "acknowledged",
            "approval_decision": "approve_action",
            "proposed_action": "review",
            "approval_notes": "Reviewed and ok",
        }])

        result = apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        assert result.kept_current >= 1

        rows = execute_query(
            "SELECT alert_status, notes FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "acknowledged"
        assert "Reviewed and ok" in (rows[0]["notes"] or "")

    def test_mark_no_archive(self, temp_db, temp_exports_dir):
        """mark_no_archive appends [no_archive] marker."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved",
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "approval_decision": "mark_no_archive",
            "approval_notes": "Permanent keep",
        }])

        result = apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        assert result.marked_no_archive == 1

        rows = execute_query(
            "SELECT notes FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert "[no_archive]" in (rows[0]["notes"] or "")

    def test_reopen_sets_status_open(self, temp_db, temp_exports_dir):
        """reopen decision sets status to open."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved",
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "approval_decision": "reopen",
        }])

        result = apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        assert result.reopened == 1

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "open"

    def test_acknowledge_sets_status(self, temp_db, temp_exports_dir):
        """acknowledge decision sets status to acknowledged."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(
            temp_db, pid, alert_status="open",
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "open",
            "approval_decision": "acknowledge",
        }])

        result = apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        assert result.acknowledged == 1

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "acknowledged"

    def test_resolve_sets_status(self, temp_db, temp_exports_dir):
        """resolve decision sets status to resolved."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(
            temp_db, pid, alert_status="open",
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "open",
            "approval_decision": "resolve",
        }])

        result = apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        assert result.resolved == 1

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "resolved"

    def test_archive_sets_status(self, temp_db, temp_exports_dir):
        """archive decision sets status to archived."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved",
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "approval_decision": "archive",
        }])

        result = apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        assert result.archived == 1

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "archived"

    def test_keep_current_no_change(self, temp_db, temp_exports_dir):
        """keep_current does not change status."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved",
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "approval_decision": "keep_current",
        }])

        result = apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        assert result.kept_current >= 1

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "resolved"


# ---------------------------------------------------------------------------
# Test: Action history
# ---------------------------------------------------------------------------


class TestActionHistory:
    """Test action recording in triage_actions table."""

    def test_action_recorded_on_archive(self, temp_db, temp_exports_dir):
        """Archive action is recorded in triage_actions table."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved",
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "approval_decision": "archive",
        }])

        apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        actions = execute_query(
            "SELECT * FROM cross_site_alert_triage_actions "
            "WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert len(actions) >= 1
        assert actions[0]["triage_export_id"].startswith("expiration_")

    def test_action_recorded_on_approve(self, temp_db, temp_exports_dir):
        """Approve action is also recorded."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=65)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old,
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "approval_decision": "approve_action",
            "proposed_action": "archive",
        }])

        apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        actions = execute_query(
            "SELECT * FROM cross_site_alert_triage_actions "
            "WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert len(actions) >= 1


# ---------------------------------------------------------------------------
# Test: CLI commands
# ---------------------------------------------------------------------------


class TestCLIListProfiles:
    """Test list-cross-site-alert-expiration-profiles CLI."""

    def test_list_profiles(self):
        """CLI list profiles runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["list-cross-site-alert-expiration-profiles"])
        assert result.exit_code == 0
        assert "conservative" in result.output
        assert "standard" in result.output
        assert "aggressive_review_only" in result.output


class TestCLIPreviewPolicy:
    """Test preview-cross-site-alert-expiration-policy CLI."""

    def test_preview_runs(self, temp_db):
        """CLI preview runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "preview-cross-site-alert-expiration-policy",
            "--db", temp_db,
        ])
        assert result.exit_code == 0
        assert "Total candidates" in result.output


class TestCLIExportApproval:
    """Test export-cross-site-alert-expiration-approval CLI."""

    def test_export_runs(self, temp_db, temp_exports_dir):
        """CLI export runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "export-cross-site-alert-expiration-approval",
            "--db", temp_db,
            "--output-dir", temp_exports_dir,
        ])
        assert result.exit_code == 0
        assert "Approval CSV exported" in result.output


class TestCLIImportApproval:
    """Test import-cross-site-alert-expiration-approval CLI."""

    def test_import_runs(self, temp_db, temp_exports_dir):
        """CLI import runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved",
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "approval_decision": "keep_current",
        }])

        runner = CliRunner()
        result = runner.invoke(app, [
            "import-cross-site-alert-expiration-approval",
            "--file", path,
            "--db", temp_db,
        ])
        assert result.exit_code == 0
        assert "Approval import complete" in result.output


class TestCLISummary:
    """Test cross-site-alert-expiration-summary CLI."""

    def test_summary_runs(self, temp_db):
        """CLI summary runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "cross-site-alert-expiration-summary",
            "--db", temp_db,
        ])
        assert result.exit_code == 0
        assert "Total candidates" in result.output


# ---------------------------------------------------------------------------
# Test: Dashboard
# ---------------------------------------------------------------------------


class TestDashboard:
    """Test dashboard integration."""

    def test_expiration_policy_table_loads_empty(self, temp_exports_dir):
        """Table loader returns empty DataFrame when no CSV exists."""
        from marketsentry.dashboard import (
            build_cross_site_alert_expiration_policy_table,
        )

        df = build_cross_site_alert_expiration_policy_table(temp_exports_dir)
        assert df.empty

    def test_expiration_policy_table_loads_csv(
        self, temp_db, temp_exports_dir,
    ):
        """Table loader returns data when CSV exists."""
        from marketsentry.cross_site_alert_expiration_policy import (
            export_alert_expiration_approval_csv,
        )
        from marketsentry.dashboard import (
            build_cross_site_alert_expiration_policy_table,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=65)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old,
        )

        export_alert_expiration_approval_csv(
            database_path=temp_db,
            profile_name="standard",
            exports_dir=temp_exports_dir,
        )

        df = build_cross_site_alert_expiration_policy_table(temp_exports_dir)
        assert not df.empty
        assert "proposed_action" in df.columns


# ---------------------------------------------------------------------------
# Test: Hygiene integration
# ---------------------------------------------------------------------------


class TestHygieneIntegration:
    """Test that hygiene recommendations mention expiration workflow."""

    def test_hygiene_mentions_expiration(self, temp_db):
        """Hygiene next actions mention expiration approval."""
        from marketsentry.cross_site_alert_hygiene import (
            generate_alert_hygiene_next_actions,
        )
        from marketsentry.models import CrossSiteAlertHygieneSummary

        summary = CrossSiteAlertHygieneSummary(
            resolved_archive_candidates=5,
        )
        actions = generate_alert_hygiene_next_actions(summary)
        combined = " ".join(actions)
        assert "export-cross-site-alert-expiration-approval" in combined

    def test_hygiene_still_mentions_archive(self, temp_db):
        """Hygiene next actions still mention archive candidates."""
        from marketsentry.cross_site_alert_hygiene import (
            generate_alert_hygiene_next_actions,
        )
        from marketsentry.models import CrossSiteAlertHygieneSummary

        summary = CrossSiteAlertHygieneSummary(
            resolved_archive_candidates=3,
        )
        actions = generate_alert_hygiene_next_actions(summary)
        combined = " ".join(actions)
        assert "export-cross-site-alert-archive-candidates" in combined


# ---------------------------------------------------------------------------
# Test: No auto-apply
# ---------------------------------------------------------------------------


class TestNoAutoApply:
    """Test that no automatic actions are applied."""

    def test_preview_does_not_mutate(self, temp_db):
        """Preview does not change any alert status."""
        from marketsentry.cross_site_alert_expiration_policy import (
            preview_alert_expiration_policy,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=100)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old,
        )

        preview_alert_expiration_policy(
            database_path=temp_db, profile_name="standard",
        )

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "resolved"

    def test_export_does_not_mutate(self, temp_db, temp_exports_dir):
        """Export does not change any alert status."""
        from marketsentry.cross_site_alert_expiration_policy import (
            export_alert_expiration_approval_csv,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=100)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old,
        )

        export_alert_expiration_approval_csv(
            database_path=temp_db,
            profile_name="standard",
            exports_dir=temp_exports_dir,
        )

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "resolved"

    def test_summary_does_not_mutate(self, temp_db):
        """Summary does not change any alert status."""
        from marketsentry.cross_site_alert_expiration_policy import (
            summarize_alert_expiration_policy,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=100)).isoformat()
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old,
        )

        summarize_alert_expiration_policy(
            database_path=temp_db, profile_name="standard",
        )

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,), database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "resolved"


# ---------------------------------------------------------------------------
# Test: No Redfin overwrite
# ---------------------------------------------------------------------------


class TestNoRedfnOverwrite:
    """Test that expiration policy does not overwrite Redfin data."""

    def test_watched_property_unchanged(self, temp_db, temp_exports_dir):
        """Watched property fields are not modified by archive action."""
        from marketsentry.cross_site_alert_expiration_policy import (
            apply_alert_expiration_approvals,
        )

        pid = _insert_watched_property(temp_db)
        aid = _insert_alert(
            temp_db, pid, alert_status="resolved",
        )

        before = execute_query(
            "SELECT * FROM watched_properties WHERE property_id = ?",
            (pid,), database_path=temp_db,
        )

        path = _create_approval_csv(temp_exports_dir, [{
            "alert_id": str(aid),
            "current_status": "resolved",
            "approval_decision": "archive",
        }])

        apply_alert_expiration_approvals(
            file_path=path, database_path=temp_db,
        )

        after = execute_query(
            "SELECT * FROM watched_properties WHERE property_id = ?",
            (pid,), database_path=temp_db,
        )
        assert before[0]["current_price"] == after[0]["current_price"]
        assert before[0]["displayed_dom"] == after[0]["displayed_dom"]
        assert (
            before[0]["active_watch_status"] == after[0]["active_watch_status"]
        )


# ---------------------------------------------------------------------------
# Test: Quiet gatekeeper unchanged
# ---------------------------------------------------------------------------


class TestQuietGatekeeper:
    """Test that Quiet Score gatekeeper remains unchanged."""

    def test_quiet_score_not_modified(self):
        """Expiration module does not import or modify Quiet Score."""
        import marketsentry.cross_site_alert_expiration_policy as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "quiet_score" not in source.lower()
        assert "quiet_gatekeeper" not in source.lower()


# ---------------------------------------------------------------------------
# Test: No walkability fields
# ---------------------------------------------------------------------------


class TestNoWalkability:
    """Test that no walkability fields are added."""

    def test_no_walkability_in_module(self):
        """Expiration module does not reference walkability."""
        import marketsentry.cross_site_alert_expiration_policy as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "walkability" not in source.lower()
        assert "walk_score" not in source.lower()

    def test_no_walkability_in_models(self):
        """New models do not have walkability fields."""
        m = CrossSiteAlertExpirationCandidate()
        fields = m.model_fields
        for field_name in fields:
            assert "walk" not in field_name.lower()


# ---------------------------------------------------------------------------
# Test: No network calls
# ---------------------------------------------------------------------------


class TestNoNetworkCalls:
    """Test that no real network calls are performed."""

    def test_no_requests_import_in_module(self):
        """Expiration module does not import requests or urllib."""
        import marketsentry.cross_site_alert_expiration_policy as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "import requests" not in source
        assert "import urllib" not in source
        assert "import httpx" not in source

    def test_no_network_in_test(self):
        """This test file does not perform network calls."""
        import marketsentry.cross_site_alert_expiration_policy as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        # Verify module does not use network libraries
        assert "requests.get(" not in source
        assert "urllib.request.urlopen" not in source


# ---------------------------------------------------------------------------
# Test: Scheduled scripts safe
# ---------------------------------------------------------------------------


class TestScheduledScriptsSafe:
    """Test that scheduled scripts do not invoke mutations."""

    def test_hygiene_script_no_import_command(self):
        """Hygiene batch script does not invoke import or mutation."""
        script_path = Path("scripts/run_alert_hygiene_report.bat")
        if script_path.exists():
            content = script_path.read_text(encoding="utf-8")
            assert "import-cross-site-alert-expiration-approval" not in content
            assert "--force-live" not in content

    def test_no_auto_archive_in_scheduled(self):
        """No scheduled script auto-archives alerts."""
        scripts_dir = Path("scripts")
        if scripts_dir.exists():
            for script in scripts_dir.glob("*.bat"):
                content = script.read_text(encoding="utf-8")
                assert (
                    "import-cross-site-alert-expiration-approval"
                    not in content
                )


# ---------------------------------------------------------------------------
# Test: Models
# ---------------------------------------------------------------------------


class TestExpirationModels:
    """Test expiration policy models."""

    def test_rule_model(self):
        """ExpirationRule model has required fields."""
        rule = CrossSiteAlertExpirationRule(
            rule_name="test",
            target_status="resolved",
            age_threshold_days=60,
            proposed_action="archive",
        )
        assert rule.rule_name == "test"
        assert rule.age_threshold_days == 60

    def test_profile_model(self):
        """ExpirationProfile model contains rules."""
        profile = CrossSiteAlertExpirationProfile(
            profile_name="test",
            rules=[
                CrossSiteAlertExpirationRule(
                    rule_name="r1",
                    target_status="resolved",
                    proposed_action="archive",
                ),
            ],
        )
        assert len(profile.rules) == 1

    def test_candidate_model_defaults(self):
        """Candidate model defaults to keep_current."""
        c = CrossSiteAlertExpirationCandidate()
        assert c.approval_decision == "keep_current"

    def test_apply_result_model(self):
        """ApplyResult model has all required counters."""
        r = CrossSiteAlertExpirationApplyResult()
        assert r.rows_read == 0
        assert r.archived == 0
        assert r.reopened == 0
        assert r.acknowledged == 0
        assert r.resolved == 0
        assert r.kept_current == 0
        assert r.marked_no_archive == 0

    def test_summary_model(self):
        """Summary model has required fields."""
        s = CrossSiteAlertExpirationSummary(profile_name="standard")
        assert s.profile_name == "standard"
        assert s.total_candidates == 0


# ---------------------------------------------------------------------------
# Test: Expiration summary
# ---------------------------------------------------------------------------


class TestExpirationSummary:
    """Test summarize_alert_expiration_policy."""

    def test_summary_with_candidates(self, temp_db):
        """Summary shows candidates from preview."""
        from marketsentry.cross_site_alert_expiration_policy import (
            summarize_alert_expiration_policy,
        )

        pid = _insert_watched_property(temp_db)
        old = (datetime.now() - timedelta(days=65)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="resolved", created_at=old,
        )

        summary = summarize_alert_expiration_policy(
            database_path=temp_db, profile_name="standard",
        )

        assert summary.total_candidates >= 1
        assert summary.proposed_archive >= 1
        assert len(summary.next_actions) >= 1

    def test_summary_empty_db(self, temp_db):
        """Summary works on empty database."""
        from marketsentry.cross_site_alert_expiration_policy import (
            summarize_alert_expiration_policy,
        )

        summary = summarize_alert_expiration_policy(
            database_path=temp_db, profile_name="standard",
        )

        assert summary.total_candidates == 0
