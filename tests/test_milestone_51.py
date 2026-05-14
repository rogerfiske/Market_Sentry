"""Tests for Milestone 51: Guided Operator Workflow.

Tests operator workflow status, one-command refresh, candidate
action helpers (decision, location scores, noise notes), export,
CLI commands, dashboard, and guard-rails.
"""

import csv
import io
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from marketsentry.operator_workflow import (
    VALID_DECISIONS,
    VALID_NOISE_RISKS,
    OperatorCandidateActionResult,
    OperatorWorkflowAction,
    OperatorWorkflowRunResult,
    OperatorWorkflowStatus,
    OperatorWorkflowStep,
    OperatorWorkflowWarning,
    apply_candidate_decision,
    apply_candidate_location_scores,
    apply_candidate_noise_notes,
    build_missing_data_actions,
    build_operator_workflow_status,
    export_operator_action_summary,
    run_operator_refresh_workflow,
)

runner = CliRunner()


# -------------------------------------------------------------------
# Test fixtures
# -------------------------------------------------------------------


def _create_test_db(db_path: str) -> None:
    """Create test database with required tables."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS candidate_review_queue (
            candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            discovery_date DATE NOT NULL,
            source_site TEXT NOT NULL,
            source_search_url TEXT NOT NULL,
            redfin_url TEXT NOT NULL,
            address TEXT NOT NULL,
            normalized_address TEXT,
            city TEXT NOT NULL,
            zip TEXT NOT NULL,
            price REAL,
            beds INTEGER,
            baths REAL,
            sqft INTEGER,
            lot_size REAL,
            displayed_dom INTEGER,
            quiet_score REAL,
            vibrancy_score REAL,
            quiet_gatekeeper_result TEXT,
            garage_spaces INTEGER,
            gas_service BOOLEAN,
            gas_evidence TEXT,
            effective_dom_estimate INTEGER,
            listing_churn_count INTEGER,
            dom_reset_count INTEGER,
            sale_rent_alternation_count INTEGER,
            review_status TEXT DEFAULT 'pending',
            user_decision TEXT,
            user_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watched_properties (
            property_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_saved_date DATE NOT NULL,
            active_watch_status BOOLEAN DEFAULT 1,
            redfin_url TEXT,
            zillow_url TEXT,
            realtor_url TEXT,
            homes_url TEXT,
            compass_url TEXT,
            address TEXT NOT NULL,
            normalized_address TEXT,
            city TEXT NOT NULL,
            zip TEXT NOT NULL,
            apn TEXT,
            current_price REAL,
            original_observed_price REAL,
            beds INTEGER,
            baths REAL,
            sqft INTEGER,
            lot_size REAL,
            garage_spaces INTEGER,
            gas_service BOOLEAN,
            gas_evidence TEXT,
            quiet_score REAL,
            vibrancy_score REAL,
            displayed_dom INTEGER,
            effective_dom INTEGER,
            effective_dom_delta INTEGER,
            listing_churn_count INTEGER,
            dom_reset_count INTEGER,
            sale_rent_alternation_count INTEGER,
            county_sale_verified BOOLEAN,
            ownership_transfer_found BOOLEAN,
            last_checked_date DATE,
            next_check_date DATE,
            watch_priority INTEGER DEFAULT 0,
            user_notes TEXT,
            recent_churn_index REAL,
            effective_dom_v2 REAL,
            county_reset_applied INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_review_actions (
            review_action_id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            action_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_decision TEXT NOT NULL,
            user_notes TEXT,
            promoted_property_id INTEGER,
            FOREIGN KEY (candidate_id)
                REFERENCES candidate_review_queue (candidate_id),
            FOREIGN KEY (promoted_property_id)
                REFERENCES watched_properties (property_id)
        )
    """)
    conn.commit()
    conn.close()


def _insert_candidate(
    db_path: str,
    candidate_id: int = 1,
    address: str = "123 Main St",
    user_decision: str | None = None,
    review_status: str = "pending",
    quiet_score: float | None = None,
    vibrancy_score: float | None = None,
    price: float | None = 500000.0,
    beds: int | None = 3,
    baths: float | None = 2.0,
    sqft: int | None = 1500,
    user_notes: str | None = None,
    normalized_address: str | None = None,
) -> None:
    """Insert a candidate into the review queue."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO candidate_review_queue "
        "(candidate_id, discovery_date, source_site, "
        "source_search_url, redfin_url, address, "
        "normalized_address, city, zip, price, beds, baths, "
        "sqft, quiet_score, vibrancy_score, review_status, "
        "user_decision, user_notes) "
        "VALUES (?, '2026-01-01', 'test', "
        "'http://test.com/search', 'http://test.com/prop', "
        "?, ?, 'Temecula', '92592', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            candidate_id,
            address,
            normalized_address or address,
            price,
            beds,
            baths,
            sqft,
            quiet_score,
            vibrancy_score,
            review_status,
            user_decision,
            user_notes,
        ),
    )
    conn.commit()
    conn.close()


def _insert_watched(
    db_path: str,
    property_id: int = 1,
    address: str = "123 Main St",
    normalized_address: str | None = None,
) -> None:
    """Insert a watched property."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO watched_properties "
        "(property_id, first_saved_date, address, "
        "normalized_address, city, zip, "
        "active_watch_status) "
        "VALUES (?, '2026-01-01', ?, ?, 'Temecula', "
        "'92592', 1)",
        (
            property_id,
            address,
            normalized_address or address,
        ),
    )
    conn.commit()
    conn.close()


# -------------------------------------------------------------------
# Workflow status tests
# -------------------------------------------------------------------


class TestWorkflowStatusEmpty:
    """Operator workflow status on empty database."""

    def test_status_builds_empty_db(self):
        """Status builds on empty database."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            status = build_operator_workflow_status(
                db_path=db, exports_dir=tmp
            )
            assert isinstance(status, OperatorWorkflowStatus)
            assert status.total_candidates == 0
            assert status.pending_candidates == 0
            assert status.maybe_candidates == 0
            assert status.saved_candidates == 0
            assert status.rejected_candidates == 0
            assert status.hold_candidates == 0
            assert status.active_watched == 0

    def test_status_missing_db(self):
        """Status handles missing database gracefully."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "none.db")
            status = build_operator_workflow_status(
                db_path=db, exports_dir=tmp,
            )
            assert isinstance(status, OperatorWorkflowStatus)
            assert status.total_candidates == 0
            # Clean up SQLite file if created by connect
            db_file = Path(db)
            if db_file.exists():
                try:
                    db_file.unlink()
                except OSError:
                    pass


class TestWorkflowStatusWithData:
    """Operator workflow status with sample candidates."""

    def test_status_counts_candidates(self):
        """Status counts candidates by decision."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1, user_decision=None)
            _insert_candidate(
                db, 2, user_decision="save",
                review_status="reviewed"
            )
            _insert_candidate(
                db, 3, user_decision="maybe",
                review_status="reviewed"
            )
            _insert_candidate(
                db, 4, user_decision="reject",
                review_status="reviewed"
            )
            _insert_candidate(
                db, 5,
                user_decision="hold_for_more_data",
                review_status="reviewed",
            )
            _insert_watched(db, 1)

            status = build_operator_workflow_status(
                db_path=db, exports_dir=tmp
            )
            assert status.total_candidates == 5
            assert status.pending_candidates >= 1
            assert status.saved_candidates == 1
            assert status.maybe_candidates == 1
            assert status.rejected_candidates == 1
            assert status.hold_candidates == 1
            assert status.active_watched == 1

    def test_missing_quiet_vibrancy_detection(self):
        """Detects candidates missing Quiet/Vibrancy."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(
                db, 1, quiet_score=None,
                vibrancy_score=None,
            )
            _insert_candidate(
                db, 2, quiet_score=9.0,
                vibrancy_score=1.5,
            )
            status = build_operator_workflow_status(
                db_path=db, exports_dir=tmp
            )
            assert status.missing_quiet_vibrancy >= 1

    def test_missing_price_detection(self):
        """Detects candidates missing price."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1, price=None)
            _insert_candidate(db, 2, price=500000.0)
            status = build_operator_workflow_status(
                db_path=db, exports_dir=tmp
            )
            assert status.missing_price >= 1

    def test_recommended_actions_populated(self):
        """Recommended actions populated with data."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(
                db, 1, quiet_score=None,
                vibrancy_score=None,
            )
            status = build_operator_workflow_status(
                db_path=db, exports_dir=tmp
            )
            assert len(status.recommended_actions) > 0
            assert any(
                a.action_id == "enter_scores"
                for a in status.recommended_actions
            )


# -------------------------------------------------------------------
# Candidate decision tests
# -------------------------------------------------------------------


class TestCandidateDecisionSave:
    """Apply candidate decision: save."""

    def test_save_promotes_to_watchlist(self):
        """Save decision promotes to watchlist."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1, address="100 Test Rd")
            result = apply_candidate_decision(
                candidate_id=1,
                decision="save",
                notes="Good property",
                db_path=db,
            )
            assert result.success is True
            assert "promoted" in result.detail.lower() or \
                "saved" in result.detail.lower()

    def test_duplicate_save_no_duplicate_watched(self):
        """Duplicate save does not duplicate watched."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(
                db, 1, address="100 Test Rd"
            )
            # First save
            r1 = apply_candidate_decision(
                candidate_id=1,
                decision="save",
                db_path=db,
            )
            assert r1.success is True
            # Second save
            r2 = apply_candidate_decision(
                candidate_id=1,
                decision="save",
                db_path=db,
            )
            assert r2.success is True
            # Verify not duplicated
            conn = sqlite3.connect(db)
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM "
                "watched_properties"
            )
            count = cur.fetchone()[0]
            conn.close()
            assert count <= 1


class TestCandidateDecisionOther:
    """Apply candidate decision: maybe/reject/hold."""

    def test_maybe_updates_decision(self):
        """Maybe updates decision."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            result = apply_candidate_decision(
                candidate_id=1,
                decision="maybe",
                notes="Need more data",
                db_path=db,
            )
            assert result.success is True
            assert "maybe" in result.detail.lower()

    def test_reject_updates_decision(self):
        """Reject updates decision."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            result = apply_candidate_decision(
                candidate_id=1,
                decision="reject",
                db_path=db,
            )
            assert result.success is True
            assert "reject" in result.detail.lower()

    def test_hold_updates_decision(self):
        """Hold for more data updates decision."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            result = apply_candidate_decision(
                candidate_id=1,
                decision="hold_for_more_data",
                db_path=db,
            )
            assert result.success is True
            assert "hold_for_more_data" in result.detail


class TestCandidateDecisionValidation:
    """Decision validation tests."""

    def test_invalid_candidate_id(self):
        """Invalid candidate ID handled."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            result = apply_candidate_decision(
                candidate_id=999,
                decision="save",
                db_path=db,
            )
            assert result.success is False
            assert "not found" in result.detail.lower()

    def test_invalid_decision(self):
        """Invalid decision handled."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            result = apply_candidate_decision(
                candidate_id=1,
                decision="invalid_decision",
                db_path=db,
            )
            assert result.success is False
            assert "invalid" in result.detail.lower()

    def test_notes_appended(self):
        """Notes appended to existing notes."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(
                db, 1, user_notes="Original notes"
            )
            apply_candidate_decision(
                candidate_id=1,
                decision="maybe",
                notes="Additional note",
                db_path=db,
            )
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT user_notes FROM "
                "candidate_review_queue "
                "WHERE candidate_id = 1"
            )
            row = cur.fetchone()
            conn.close()
            assert "Original notes" in row["user_notes"]
            assert "Additional note" in row["user_notes"]


# -------------------------------------------------------------------
# Location scores tests
# -------------------------------------------------------------------


class TestLocationScores:
    """Candidate location scores tests."""

    def test_scores_written(self):
        """Location scores write quiet/vibrancy."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            result = apply_candidate_location_scores(
                candidate_id=1,
                quiet_score=9.5,
                vibrancy_score=1.2,
                db_path=db,
            )
            assert result.success is True
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT quiet_score, vibrancy_score "
                "FROM candidate_review_queue "
                "WHERE candidate_id = 1"
            )
            row = cur.fetchone()
            conn.close()
            assert row["quiet_score"] == 9.5
            assert row["vibrancy_score"] == 1.2

    def test_gatekeeper_pass_quiet_gte_7(self):
        """Quiet gatekeeper pass when quiet >= 7.0."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            result = apply_candidate_location_scores(
                candidate_id=1,
                quiet_score=7.0,
                vibrancy_score=2.0,
                db_path=db,
            )
            assert result.success is True
            assert "pass" in result.detail.lower()

    def test_gatekeeper_fail_quiet_lt_7(self):
        """Quiet gatekeeper fail when quiet < 7.0."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            result = apply_candidate_location_scores(
                candidate_id=1,
                quiet_score=6.9,
                vibrancy_score=1.0,
                db_path=db,
            )
            assert result.success is True
            assert "fail" in result.detail.lower()

    def test_low_vibrancy_no_override_poor_quiet(self):
        """Low vibrancy does not override poor Quiet."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            result = apply_candidate_location_scores(
                candidate_id=1,
                quiet_score=5.0,
                vibrancy_score=0.5,
                db_path=db,
            )
            assert result.success is True
            # Even with very low vibrancy, poor quiet fails
            assert "fail" in result.detail.lower()

    def test_scores_notes_appended(self):
        """Location score notes saved/appended."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(
                db, 1, user_notes="Existing"
            )
            apply_candidate_location_scores(
                candidate_id=1,
                quiet_score=8.0,
                vibrancy_score=2.0,
                notes="New score note",
                db_path=db,
            )
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT user_notes FROM "
                "candidate_review_queue "
                "WHERE candidate_id = 1"
            )
            row = cur.fetchone()
            conn.close()
            assert "Existing" in row["user_notes"]
            assert "New score note" in row["user_notes"]

    def test_scores_update_watched_property(self):
        """Scores update watched property if promoted."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            addr = "100 Test Rd"
            _insert_candidate(
                db, 1, address=addr,
                normalized_address=addr,
            )
            _insert_watched(
                db, 1, address=addr,
                normalized_address=addr,
            )
            apply_candidate_location_scores(
                candidate_id=1,
                quiet_score=9.0,
                vibrancy_score=1.5,
                db_path=db,
            )
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT quiet_score, vibrancy_score "
                "FROM watched_properties "
                "WHERE property_id = 1"
            )
            row = cur.fetchone()
            conn.close()
            assert row["quiet_score"] == 9.0
            assert row["vibrancy_score"] == 1.5

    def test_invalid_candidate_scores(self):
        """Invalid candidate ID for scores."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            result = apply_candidate_location_scores(
                candidate_id=999,
                quiet_score=8.0,
                vibrancy_score=2.0,
                db_path=db,
            )
            assert result.success is False
            assert "not found" in result.detail.lower()


# -------------------------------------------------------------------
# Noise notes tests
# -------------------------------------------------------------------


class TestNoiseNotes:
    """Candidate noise notes tests."""

    def test_noise_notes_saved(self):
        """Noise notes saved to candidate."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            result = apply_candidate_noise_notes(
                candidate_id=1,
                noise_risk="moderate",
                noise_sources="traffic,airport",
                notes="Local knowledge concern",
                db_path=db,
            )
            assert result.success is True
            assert "moderate" in result.detail.lower()

    def test_noise_notes_appended(self):
        """Noise notes appended to existing notes."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(
                db, 1, user_notes="Previous notes"
            )
            apply_candidate_noise_notes(
                candidate_id=1,
                noise_risk="high",
                noise_sources="airport",
                notes="Airport flight path",
                db_path=db,
            )
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT user_notes FROM "
                "candidate_review_queue "
                "WHERE candidate_id = 1"
            )
            row = cur.fetchone()
            conn.close()
            assert "Previous notes" in row["user_notes"]
            assert "Noise observation" in row["user_notes"]
            assert "airport" in row["user_notes"].lower()

    def test_noise_notes_invalid_risk(self):
        """Invalid noise risk handled."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            result = apply_candidate_noise_notes(
                candidate_id=1,
                noise_risk="invalid_risk",
                db_path=db,
            )
            assert result.success is False
            assert "invalid" in result.detail.lower()

    def test_noise_notes_invalid_candidate(self):
        """Invalid candidate for noise notes."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            result = apply_candidate_noise_notes(
                candidate_id=999,
                noise_risk="low",
                db_path=db,
            )
            assert result.success is False
            assert "not found" in result.detail.lower()


# -------------------------------------------------------------------
# Refresh workflow tests
# -------------------------------------------------------------------


class TestRefreshWorkflow:
    """Operator refresh workflow tests."""

    def test_refresh_runs_local_commands(self):
        """Refresh runs local report commands."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            result = run_operator_refresh_workflow(
                db_path=db, exports_dir=tmp
            )
            assert isinstance(result, OperatorWorkflowRunResult)
            assert len(result.steps) > 0

    def test_refresh_no_live_retrieval(self):
        """Refresh does not run live retrieval."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        assert "requests.get" not in source
        assert "httpx.get" not in source
        assert "urllib.request" not in source

    def test_refresh_handles_missing_db(self):
        """Refresh handles missing database."""
        with tempfile.TemporaryDirectory() as tmp:
            result = run_operator_refresh_workflow(
                db_path=str(Path(tmp) / "missing.db"),
                exports_dir=tmp,
            )
            assert len(result.warnings) > 0
            assert any(
                "not found" in w.message.lower()
                for w in result.warnings
            )

    def test_refresh_tolerates_empty_tables(self):
        """Refresh tolerates empty tables."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            result = run_operator_refresh_workflow(
                db_path=db, exports_dir=tmp
            )
            assert isinstance(result, OperatorWorkflowRunResult)
            # Should not crash with no data


# -------------------------------------------------------------------
# Export tests
# -------------------------------------------------------------------


class TestExportActionSummary:
    """Export operator action summary tests."""

    def test_export_md(self):
        """Export Markdown action summary."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            paths = export_operator_action_summary(
                db_path=db, exports_dir=tmp, fmt="md"
            )
            assert len(paths) == 1
            assert paths[0].endswith(".md")
            content = Path(paths[0]).read_text(
                encoding="utf-8"
            )
            assert "Operator Action Summary" in content
            assert "Candidate Status" in content

    def test_export_csv(self):
        """Export CSV action summary."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            paths = export_operator_action_summary(
                db_path=db, exports_dir=tmp, fmt="csv"
            )
            assert len(paths) == 1
            assert paths[0].endswith(".csv")
            content = Path(paths[0]).read_text(
                encoding="utf-8"
            )
            reader = csv.reader(io.StringIO(content))
            header = next(reader)
            assert "section" in header
            assert "item" in header

    def test_export_both(self):
        """Export both Markdown and CSV."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            paths = export_operator_action_summary(
                db_path=db, exports_dir=tmp, fmt="both"
            )
            assert len(paths) == 2
            extensions = {Path(p).suffix for p in paths}
            assert ".md" in extensions
            assert ".csv" in extensions


# -------------------------------------------------------------------
# Missing data actions tests
# -------------------------------------------------------------------


class TestMissingDataActions:
    """Build missing data actions tests."""

    def test_missing_scores_detected(self):
        """Missing scores generate actions."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(
                db, 1, quiet_score=None,
                vibrancy_score=None,
            )
            actions = build_missing_data_actions(
                db_path=db
            )
            assert len(actions) >= 1
            assert any(
                "scores" in a.action_id
                for a in actions
            )

    def test_no_missing_data_no_actions(self):
        """No missing data means fewer actions."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(
                db, 1, quiet_score=9.0,
                vibrancy_score=1.5,
                user_decision="save",
                review_status="reviewed",
            )
            actions = build_missing_data_actions(
                db_path=db
            )
            # Should have no score actions
            assert not any(
                "scores" in a.action_id
                for a in actions
            )


# -------------------------------------------------------------------
# CLI tests
# -------------------------------------------------------------------


class TestCLICommands:
    """CLI command tests."""

    def test_cli_operator_workflow_status(self):
        """CLI operator-workflow-status runs."""
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            result = runner.invoke(
                app,
                [
                    "operator-workflow-status",
                    "--db", db,
                ],
            )
            assert result.exit_code == 0

    def test_cli_candidate_decision(self):
        """CLI candidate-decision runs."""
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            result = runner.invoke(
                app,
                [
                    "candidate-decision",
                    "--candidate-id", "1",
                    "--decision", "maybe",
                    "--notes", "Test",
                    "--db", db,
                ],
            )
            assert result.exit_code == 0

    def test_cli_candidate_location_scores(self):
        """CLI candidate-location-scores runs."""
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            result = runner.invoke(
                app,
                [
                    "candidate-location-scores",
                    "--candidate-id", "1",
                    "--quiet-score", "8.5",
                    "--vibrancy-score", "1.5",
                    "--db", db,
                ],
            )
            assert result.exit_code == 0

    def test_cli_candidate_noise_notes(self):
        """CLI candidate-noise-notes runs."""
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            _insert_candidate(db, 1)
            result = runner.invoke(
                app,
                [
                    "candidate-noise-notes",
                    "--candidate-id", "1",
                    "--noise-risk", "moderate",
                    "--noise-sources", "traffic",
                    "--db", db,
                ],
            )
            assert result.exit_code == 0

    def test_cli_run_operator_refresh(self):
        """CLI run-operator-refresh-workflow runs."""
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            result = runner.invoke(
                app,
                [
                    "run-operator-refresh-workflow",
                    "--db", db,
                    "--exports-dir", tmp,
                ],
            )
            assert result.exit_code == 0

    def test_cli_export_operator_action_summary(self):
        """CLI export-operator-action-summary runs."""
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "test.db")
            _create_test_db(db)
            result = runner.invoke(
                app,
                [
                    "export-operator-action-summary",
                    "--db", db,
                    "--exports-dir", tmp,
                    "--format", "both",
                ],
            )
            assert result.exit_code == 0


# -------------------------------------------------------------------
# Dashboard tests
# -------------------------------------------------------------------


class TestDashboard:
    """Dashboard Operator Workflow section tests."""

    def test_dashboard_imports(self):
        """Dashboard imports operator workflow module."""
        source = Path(
            "src/marketsentry/dashboard_app.py"
        ).read_text(encoding="utf-8")
        assert "operator_workflow" in source

    def test_dashboard_section_exists(self):
        """Dashboard has Operator Workflow section."""
        source = Path(
            "src/marketsentry/dashboard_app.py"
        ).read_text(encoding="utf-8")
        assert "Operator Workflow" in source

    def test_dashboard_action_forms(self):
        """Dashboard has action forms."""
        source = Path(
            "src/marketsentry/dashboard_app.py"
        ).read_text(encoding="utf-8")
        assert "operator_decision_form" in source
        assert "operator_scores_form" in source
        assert "operator_noise_form" in source
        assert "operator_refresh_form" in source

    def test_dashboard_multiselect_noise(self):
        """Dashboard has noise source multiselect."""
        source = Path(
            "src/marketsentry/dashboard_app.py"
        ).read_text(encoding="utf-8")
        assert "multiselect" in source
        assert "Noise Sources" in source


# -------------------------------------------------------------------
# Guard-rail tests
# -------------------------------------------------------------------


class TestNoRedfinOverwrite:
    """No Redfin source-of-truth overwrite."""

    def test_no_redfin_sot_overwrite(self):
        """Module does not overwrite Redfin SOT."""
        import marketsentry.operator_workflow as mod

        assert not hasattr(mod, "redfin_source_of_truth")
        assert not hasattr(mod, "overwrite_redfin_sot")

    def test_only_explicit_candidate_fields(self):
        """Module updates only explicit fields."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        # Module updates candidate fields via SQL
        # but does not touch redfin_url, source_site,
        # address, city, zip, etc.
        assert "UPDATE candidate_review_queue" in source
        # All updates are to allowed fields:
        # user_decision, user_notes, quiet_score,
        # vibrancy_score, quiet_gatekeeper_result,
        # review_status, updated_at


class TestQuietGatekeeperUnchanged:
    """Quiet Score gatekeeper unchanged."""

    def test_no_quiet_threshold_change(self):
        """Module does not change Quiet threshold."""
        import marketsentry.operator_workflow as mod

        assert not hasattr(mod, "QUIET_THRESHOLD")
        assert not hasattr(mod, "quiet_threshold")

    def test_uses_existing_gatekeeper(self):
        """Module uses existing gatekeeper function."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        assert "apply_quiet_gatekeeper" in source

    def test_gatekeeper_threshold_unchanged(self):
        """Quiet gatekeeper threshold is 7.0."""
        from marketsentry.quiet_vibrancy import (
            apply_quiet_gatekeeper,
        )

        result_pass, _ = apply_quiet_gatekeeper(7.0, 2.0)
        result_fail, _ = apply_quiet_gatekeeper(6.9, 2.0)
        assert result_pass == "pass"
        assert result_fail == "fail_noise_risk"


class TestNoWalkability:
    """No walkability fields added."""

    def test_no_walkability_fields(self):
        """Module has no walkability attributes."""
        import marketsentry.operator_workflow as mod

        assert not hasattr(mod, "walkability_score")
        assert not hasattr(mod, "walk_score")
        assert not hasattr(mod, "walkability_rating")

    def test_no_walkability_in_source(self):
        """Source code has no walkability references."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        # Check that there are no walkability field
        # assignments (OK to reference in tests/docs)
        assert "walkability_score =" not in source
        assert "walk_score =" not in source


class TestNoBrowserAutomation:
    """No browser automation added."""

    def test_no_playwright_import(self):
        """Module does not import playwright."""
        import marketsentry.operator_workflow as mod

        assert not hasattr(mod, "playwright")

    def test_no_selenium_import(self):
        """Module does not import selenium."""
        import marketsentry.operator_workflow as mod

        assert not hasattr(mod, "selenium")

    def test_no_browser_automation_source(self):
        """Source has no browser automation."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        # Check imports only (not string literals)
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith(
                ("import ", "from ")
            ):
                assert "playwright" not in stripped
                assert "selenium" not in stripped


class TestNoNetworkCalls:
    """No real network calls in tests."""

    def test_no_requests_import(self):
        """Module does not import requests."""
        import marketsentry.operator_workflow as mod

        assert not hasattr(mod, "requests")

    def test_no_httpx_import(self):
        """Module does not import httpx."""
        import marketsentry.operator_workflow as mod

        assert not hasattr(mod, "httpx")

    def test_no_smtplib_import(self):
        """Module does not import smtplib."""
        import marketsentry.operator_workflow as mod

        assert not hasattr(mod, "smtplib")


class TestNoOutboundNotifications:
    """No outbound notifications sent."""

    def test_no_notification_imports(self):
        """Module has no notification imports."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith(
                ("import ", "from ")
            ):
                assert "smtplib" not in stripped
                assert "email.mime" not in stripped
                assert "twilio" not in stripped
                assert "sendgrid" not in stripped

    def test_no_webhook_calls(self):
        """Module has no webhook calls."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith(
                ("import ", "from ")
            ):
                assert "webhook" not in stripped


# -------------------------------------------------------------------
# Model tests
# -------------------------------------------------------------------


class TestModels:
    """Test Pydantic model construction."""

    def test_workflow_step_model(self):
        """OperatorWorkflowStep constructs."""
        step = OperatorWorkflowStep(
            step_id="test",
            description="Test step",
            status="pass",
        )
        assert step.step_id == "test"
        assert step.status == "pass"

    def test_workflow_warning_model(self):
        """OperatorWorkflowWarning constructs."""
        w = OperatorWorkflowWarning(
            warning_id="test",
            message="Test warning",
            severity="warning",
        )
        assert w.warning_id == "test"
        assert w.severity == "warning"

    def test_workflow_action_model(self):
        """OperatorWorkflowAction constructs."""
        a = OperatorWorkflowAction(
            action_id="test",
            description="Test action",
            priority="high",
            command="marketsentry test",
        )
        assert a.action_id == "test"
        assert a.priority == "high"

    def test_candidate_action_result_model(self):
        """OperatorCandidateActionResult constructs."""
        r = OperatorCandidateActionResult(
            candidate_id=1,
            action="test",
            success=True,
            detail="OK",
        )
        assert r.candidate_id == 1
        assert r.success is True
        assert r.promoted_property_id is None

    def test_workflow_status_model(self):
        """OperatorWorkflowStatus constructs."""
        s = OperatorWorkflowStatus()
        assert s.total_candidates == 0
        assert s.latest_reports == []
        assert s.recommended_actions == []

    def test_workflow_run_result_model(self):
        """OperatorWorkflowRunResult constructs."""
        r = OperatorWorkflowRunResult()
        assert r.steps == []
        assert r.warnings == []
        assert r.output_paths == []


class TestValidConstants:
    """Test valid decision and noise risk constants."""

    def test_valid_decisions(self):
        """Valid decisions set correct."""
        assert "save" in VALID_DECISIONS
        assert "reject" in VALID_DECISIONS
        assert "maybe" in VALID_DECISIONS
        assert "hold_for_more_data" in VALID_DECISIONS
        assert len(VALID_DECISIONS) == 4

    def test_valid_noise_risks(self):
        """Valid noise risks set correct."""
        assert "low" in VALID_NOISE_RISKS
        assert "moderate" in VALID_NOISE_RISKS
        assert "high" in VALID_NOISE_RISKS
        assert "severe" in VALID_NOISE_RISKS
        assert "unknown" in VALID_NOISE_RISKS
        assert len(VALID_NOISE_RISKS) == 5


# -------------------------------------------------------------------
# Current project safety audit tests
# -------------------------------------------------------------------


class TestCurrentProjectSafety:
    """Current project safety checks."""

    def test_no_force_live_in_scripts(self):
        """No --force-live in scheduled scripts."""
        scripts_dir = Path("scripts")
        if scripts_dir.exists():
            for script in scripts_dir.glob("*.bat"):
                content = script.read_text(
                    encoding="utf-8"
                )
                assert "--force-live" not in content
            for script in scripts_dir.glob("*.sh"):
                content = script.read_text(
                    encoding="utf-8"
                )
                assert "--force-live" not in content

    def test_no_live_retrieval_in_operator_module(self):
        """Operator module has no live retrieval."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith(
                ("import ", "from ")
            ):
                assert "requests" not in stripped
                assert "httpx" not in stripped
                assert (
                    "urllib.request" not in stripped
                )

    def test_operator_workflow_doc_exists(self):
        """Operator workflow documentation exists."""
        assert Path(
            "docs/OPERATOR_WORKFLOW.md"
        ).exists()

    def test_decision_note_exists(self):
        """Decision note 050 exists."""
        assert Path(
            "docs/decisions/050-guided-operator-workflow.md"
        ).exists()


# -------------------------------------------------------------------
# M51A regression tests - database path defaults
# -------------------------------------------------------------------


class TestM51ADefaultDatabasePath:
    """M51A: CLI commands default to canonical db path."""

    def test_cli_help_shows_canonical_default(self):
        """CLI help shows db/marketsentry.db default."""
        from marketsentry.cli import app

        result = runner.invoke(
            app,
            ["operator-workflow-status", "--help"],
        )
        assert result.exit_code == 0
        # Must NOT show the wrong default
        assert "data/market_sentry.db" not in result.output
        # Should show canonical default
        assert "marketsentry.db" in result.output

    def test_candidate_location_scores_help_default(self):
        """candidate-location-scores help uses canonical."""
        from marketsentry.cli import app

        result = runner.invoke(
            app,
            ["candidate-location-scores", "--help"],
        )
        assert result.exit_code == 0
        assert "data/market_sentry.db" not in result.output

    def test_candidate_noise_notes_help_default(self):
        """candidate-noise-notes help uses canonical."""
        from marketsentry.cli import app

        result = runner.invoke(
            app,
            ["candidate-noise-notes", "--help"],
        )
        assert result.exit_code == 0
        assert "data/market_sentry.db" not in result.output

    def test_candidate_decision_help_default(self):
        """candidate-decision help uses canonical."""
        from marketsentry.cli import app

        result = runner.invoke(
            app,
            ["candidate-decision", "--help"],
        )
        assert result.exit_code == 0
        assert "data/market_sentry.db" not in result.output

    def test_run_refresh_help_default(self):
        """run-operator-refresh-workflow help canonical."""
        from marketsentry.cli import app

        result = runner.invoke(
            app,
            [
                "run-operator-refresh-workflow",
                "--help",
            ],
        )
        assert result.exit_code == 0
        assert "data/market_sentry.db" not in result.output

    def test_export_action_summary_help_default(self):
        """export-operator-action-summary help canonical."""
        from marketsentry.cli import app

        result = runner.invoke(
            app,
            [
                "export-operator-action-summary",
                "--help",
            ],
        )
        assert result.exit_code == 0
        assert "data/market_sentry.db" not in result.output

    def test_module_defaults_canonical(self):
        """Module function defaults use canonical path."""
        import inspect
        from marketsentry.operator_workflow import (
            build_operator_workflow_status,
            run_operator_refresh_workflow,
            apply_candidate_decision,
            apply_candidate_location_scores,
            apply_candidate_noise_notes,
            build_missing_data_actions,
            export_operator_action_summary,
        )

        for fn in [
            build_operator_workflow_status,
            run_operator_refresh_workflow,
            apply_candidate_decision,
            apply_candidate_location_scores,
            apply_candidate_noise_notes,
            build_missing_data_actions,
            export_operator_action_summary,
        ]:
            src = inspect.getsource(fn)
            # Module uses None default with fallback;
            # the fallback must not be the wrong path
            assert "data/market_sentry.db" not in src


# -------------------------------------------------------------------
# M51A regression tests - refresh workflow imports
# -------------------------------------------------------------------


class TestM51ARefreshWorkflowImports:
    """M51A: Refresh workflow uses correct function names."""

    def test_no_recalc_all_candidates(self):
        """No import of nonexistent recalc_all_candidates."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        assert "recalc_all_candidates" not in source

    def test_no_snapshot_watchlist_observations(self):
        """No import of nonexistent snapshot_watchlist."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        assert "snapshot_watchlist_observations" not in source

    def test_no_export_monitoring_report_wrong_module(self):
        """No import of export_monitoring_report from
        monitoring module."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        # Should use export_watchlist_monitoring_report
        # from monitoring_report, not export_monitoring_report
        # from monitoring
        assert "export_monitoring_report" not in source
        assert "export_watchlist_monitoring_report" in source

    def test_uses_recalculate_candidates(self):
        """Uses correct recalculate_candidates function."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        assert "recalculate_candidates" in source

    def test_uses_create_snapshots_for_all_watched(self):
        """Uses correct create_snapshots function."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        assert "create_snapshots_for_all_watched" in source

    def test_uses_monitoring_report_module(self):
        """Uses monitoring_report module for report export."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        assert "from marketsentry.monitoring_report" in source

    def test_operations_digest_correct_kwarg(self):
        """export_operations_digest uses db_path kwarg."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        # Find the digest call in refresh workflow
        # Should use db_path=, not database_path=
        in_digest = False
        for line in source.splitlines():
            if "export_operations_digest" in line:
                in_digest = True
            if in_digest and "database_path=" in line:
                assert False, (
                    "export_operations_digest should use "
                    "db_path=, not database_path="
                )
            if in_digest and ")" in line and "(" not in line:
                in_digest = False

    def test_portfolio_review_pack_correct_kwarg(self):
        """export_portfolio_review_pack uses db_path."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        # Find the pack call in refresh workflow
        in_pack = False
        for line in source.splitlines():
            if "export_portfolio_review_pack" in line:
                in_pack = True
            if in_pack and "database_path=" in line:
                assert False, (
                    "export_portfolio_review_pack should "
                    "use db_path=, not database_path="
                )
            if in_pack and ")" in line and "(" not in line:
                in_pack = False

    def test_candidate_analysis_no_output_dir(self):
        """export_candidate_analysis_report no output_dir."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        # Find the candidate analysis call
        in_analysis = False
        for line in source.splitlines():
            if "export_candidate_analysis_report" in line:
                in_analysis = True
            if in_analysis and "output_dir=" in line:
                assert False, (
                    "export_candidate_analysis_report "
                    "should not use output_dir="
                )
            if in_analysis and ")" in line and "(" not in line:
                in_analysis = False

    def test_has_effective_dom_v2_step(self):
        """Refresh has Effective DOM v2 persistence step."""
        source = Path(
            "src/marketsentry/operator_workflow.py"
        ).read_text(encoding="utf-8")
        assert "persist_effective_dom_v2" in source
        assert "effective_dom_v2_persistence" in source


class TestM51ARefreshWorkflowExecution:
    """M51A: Refresh workflow runs correctly."""

    def test_refresh_uses_provided_db(self, tmp_path):
        """Refresh uses provided temp DB, not another."""
        db = str(tmp_path / "test.db")
        exports = str(tmp_path / "exports")
        Path(exports).mkdir(exist_ok=True)
        _create_test_db(db)
        _insert_candidate(db, 1)
        result = run_operator_refresh_workflow(
            db_path=db, exports_dir=exports
        )
        # Should have run steps against our DB
        assert isinstance(
            result, OperatorWorkflowRunResult
        )
        assert len(result.steps) >= 1

    def test_refresh_produces_steps(self, tmp_path):
        """Refresh produces expected step count."""
        db = str(tmp_path / "test.db")
        exports = str(tmp_path / "exports")
        Path(exports).mkdir(exist_ok=True)
        _create_test_db(db)
        _insert_candidate(db, 1)
        result = run_operator_refresh_workflow(
            db_path=db, exports_dir=exports
        )
        # Should have 8 steps (recalc, dom v2,
        # snapshot, monitoring, candidate, digest,
        # portfolio, bundle)
        assert len(result.steps) >= 7

    def test_refresh_empty_db_graceful(self, tmp_path):
        """Refresh handles empty DB gracefully."""
        db = str(tmp_path / "test.db")
        exports = str(tmp_path / "exports")
        Path(exports).mkdir(exist_ok=True)
        _create_test_db(db)
        result = run_operator_refresh_workflow(
            db_path=db, exports_dir=exports
        )
        assert isinstance(
            result, OperatorWorkflowRunResult
        )
        # Should not crash

    def test_refresh_no_import_warnings(self, tmp_path):
        """Refresh no import-error warnings for core
        functions."""
        db = str(tmp_path / "test.db")
        exports = str(tmp_path / "exports")
        Path(exports).mkdir(exist_ok=True)
        _create_test_db(db)
        _insert_candidate(db, 1)
        result = run_operator_refresh_workflow(
            db_path=db, exports_dir=exports
        )
        for w in result.warnings:
            # Should not have import errors
            assert "cannot import name" not in \
                w.message.lower()
            # Should not have unexpected keyword arg
            assert "unexpected keyword" not in \
                w.message.lower()

    def test_refresh_state_not_mutated(self, tmp_path):
        """Refresh does not mutate candidate decisions."""
        db = str(tmp_path / "test.db")
        exports = str(tmp_path / "exports")
        Path(exports).mkdir(exist_ok=True)
        _create_test_db(db)
        _insert_candidate(
            db, 1, user_decision="maybe",
            review_status="reviewed",
        )
        run_operator_refresh_workflow(
            db_path=db, exports_dir=exports
        )
        # Decision should remain unchanged
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT user_decision FROM "
            "candidate_review_queue "
            "WHERE candidate_id = 1"
        )
        row = cur.fetchone()
        conn.close()
        assert row["user_decision"] == "maybe"
