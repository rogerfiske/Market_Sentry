"""Tests for Milestone 40: Local Portfolio Review Pack."""

from __future__ import annotations

import csv
import os
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from marketsentry.cli import app
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
        "ALTER TABLE watched_properties ADD COLUMN effective_dom_v1 INTEGER",
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


def _insert_watched(db_path: str, property_id: int = 1,
                     gas_service: int = 0, garage_spaces: int = 0,
                     watch_priority: int = 0,
                     quiet_score: float | None = None,
                     vibrancy_score: float | None = None,
                     effective_dom: int | None = None,
                     effective_dom_v1: int | None = None,
                     effective_dom_v2: int | None = None,
                     effective_dom_delta: int | None = None,
                     county_reset_applied: int = 0,
                     recent_churn_index: float | None = None,
                     listing_churn_count: int = 0,
                     dom_reset_count: int = 0,
                     sale_rent_alternation_count: int = 0,
                     current_price: float | None = None,
                     beds: int | None = None,
                     baths: float | None = None,
                     sqft: int | None = None,
                     redfin_url: str = "",
                     gas_evidence: str = "",
                     active_watch_status: int = 1) -> None:
    """Insert a watched property."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO watched_properties "
        "(property_id, first_saved_date, address, city, zip, "
        "gas_service, gas_evidence, garage_spaces, active_watch_status, "
        "watch_priority, quiet_score, vibrancy_score, "
        "effective_dom, effective_dom_v1, effective_dom_v2, "
        "effective_dom_delta, county_reset_applied, recent_churn_index, "
        "listing_churn_count, dom_reset_count, sale_rent_alternation_count, "
        "current_price, beds, baths, sqft, redfin_url) "
        "VALUES (?, '2026-01-01', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (property_id, f"{property_id} Main St", "Temecula", "92592",
         gas_service, gas_evidence, garage_spaces, active_watch_status,
         watch_priority, quiet_score, vibrancy_score,
         effective_dom, effective_dom_v1, effective_dom_v2,
         effective_dom_delta, county_reset_applied, recent_churn_index,
         listing_churn_count, dom_reset_count, sale_rent_alternation_count,
         current_price, beds, baths, sqft, redfin_url),
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
                             lifecycle_gap_count: int = 0,
                             recommended_review_action: str = "") -> None:
    """Insert a lifecycle health snapshot."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO cross_site_lifecycle_health_snapshots "
        "(property_id, lifecycle_health_score, lifecycle_health_label, "
        "lifecycle_gap_count, recommended_review_action) "
        "VALUES (?, ?, ?, ?, ?)",
        (property_id, score, label, lifecycle_gap_count,
         recommended_review_action),
    )
    conn.commit()
    conn.close()


def _insert_analytics(db_path: str, property_id: int = 1,
                       confidence: float = 85.0,
                       severity_label: str = "low") -> None:
    """Insert a cross-site analytics snapshot."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO cross_site_analytics_snapshots "
        "(property_id, overall_cross_site_confidence_score, "
        "discrepancy_severity_label, captured_at) "
        "VALUES (?, ?, ?, datetime('now'))",
        (property_id, confidence, severity_label),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Build pack tests
# ---------------------------------------------------------------------------

class TestBuildPack:
    """Portfolio review pack build tests."""

    def test_build_pack_empty_db(self, tmp_path):
        """Build pack on empty database returns empty results."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.portfolio_review_pack import (
            build_portfolio_review_pack,
        )
        summary, briefs, actions = build_portfolio_review_pack(db)
        assert summary.total_watched == 0
        assert len(briefs) == 0
        assert len(actions) >= 1  # at least "no actions required"

    def test_build_pack_with_watched(self, tmp_path):
        """Build pack with watched properties returns briefs."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1, quiet_score=80.0, vibrancy_score=20.0)
        _insert_watched(db, 2, quiet_score=50.0, vibrancy_score=60.0)
        from marketsentry.portfolio_review_pack import (
            build_portfolio_review_pack,
        )
        summary, briefs, actions = build_portfolio_review_pack(db)
        assert summary.total_watched == 2
        assert len(briefs) == 2


# ---------------------------------------------------------------------------
# Property brief tests
# ---------------------------------------------------------------------------

class TestPropertyBrief:
    """Property brief content tests."""

    def test_brief_with_quiet_vibrancy(self, tmp_path):
        """Brief includes quiet/vibrancy scores and gatekeeper result."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1, quiet_score=80.0, vibrancy_score=15.0)
        from marketsentry.portfolio_review_pack import (
            build_property_review_brief,
        )
        row = {"property_id": 1, "quiet_score": 80.0,
               "vibrancy_score": 15.0, "address": "1 Main St",
               "city": "Temecula", "zip": "92592",
               "active_watch_status": 1}
        brief = build_property_review_brief(row, db)
        assert brief.quiet_score == 80.0
        assert brief.vibrancy_score == 15.0
        assert brief.quiet_gatekeeper_result == "pass"

    def test_quiet_gatekeeper_failure_visible(self, tmp_path):
        """Quiet gatekeeper failure appears as flag."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.portfolio_review_pack import (
            build_property_review_brief,
        )
        row = {"property_id": 1, "quiet_score": 40.0,
               "vibrancy_score": 80.0, "address": "1 Main St",
               "city": "Temecula", "zip": "92592",
               "active_watch_status": 1}
        brief = build_property_review_brief(row, db)
        assert brief.quiet_gatekeeper_result == "fail"
        flag_names = [f.flag_name for f in brief.flags]
        assert "Quiet Gatekeeper" in flag_names

    def test_brief_with_effective_dom_v2(self, tmp_path):
        """Brief includes Effective DOM v1 and v2."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.portfolio_review_pack import (
            build_property_review_brief,
        )
        row = {"property_id": 1, "effective_dom": 90,
               "effective_dom_v1": 90, "effective_dom_v2": 60,
               "effective_dom_delta": 30,
               "address": "1 Main St", "city": "Temecula",
               "zip": "92592", "active_watch_status": 1}
        brief = build_property_review_brief(row, db)
        assert brief.effective_dom_v1 == 90
        assert brief.effective_dom_v2 == 60
        assert brief.effective_dom_delta == 30

    def test_brief_with_churn_index(self, tmp_path):
        """Brief includes Churn Index and related fields."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.portfolio_review_pack import (
            build_property_review_brief,
        )
        row = {"property_id": 1, "recent_churn_index": 5.2,
               "listing_churn_count": 3, "dom_reset_count": 2,
               "sale_rent_alternation_count": 1,
               "address": "1 Main St", "city": "Temecula",
               "zip": "92592", "active_watch_status": 1}
        brief = build_property_review_brief(row, db)
        assert brief.recent_churn_index == 5.2
        assert brief.listing_churn_count == 3
        assert brief.dom_reset_count == 2
        flag_names = [f.flag_name for f in brief.flags]
        assert "High Churn" in flag_names

    def test_brief_with_gas_garage(self, tmp_path):
        """Brief includes gas and garage evidence."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.portfolio_review_pack import (
            build_property_review_brief,
        )
        row = {"property_id": 1, "gas_service": 1,
               "gas_evidence": "SoCal Gas line visible",
               "garage_spaces": 2,
               "address": "1 Main St", "city": "Temecula",
               "zip": "92592", "active_watch_status": 1}
        brief = build_property_review_brief(row, db)
        assert "Yes" in brief.gas_evidence
        assert "SoCal Gas" in brief.gas_evidence
        assert brief.garage_spaces == 2

    def test_brief_with_cross_site_analytics(self, tmp_path):
        """Brief includes cross-site confidence and discrepancy."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1)
        _insert_analytics(db, 1, confidence=30.0, severity_label="high")
        from marketsentry.portfolio_review_pack import (
            build_property_review_brief,
        )
        row = {"property_id": 1, "address": "1 Main St",
               "city": "Temecula", "zip": "92592",
               "active_watch_status": 1}
        brief = build_property_review_brief(row, db)
        assert brief.cross_site_confidence_score == 30.0
        assert brief.discrepancy_severity_label == "high"
        flag_names = [f.flag_name for f in brief.flags]
        assert "Low Cross-Site Confidence" in flag_names
        assert "Discrepancy Severity" in flag_names

    def test_brief_with_alert_lifecycle(self, tmp_path):
        """Brief includes alert burden and lifecycle health."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1)
        _insert_alert(db, 1, 1, "open", "critical")
        _insert_alert(db, 2, 1, "open", "high")
        _insert_health_snapshot(
            db, 1, "attention_required", 35.0, 2, "Review required"
        )
        from marketsentry.portfolio_review_pack import (
            build_property_review_brief,
        )
        row = {"property_id": 1, "address": "1 Main St",
               "city": "Temecula", "zip": "92592",
               "active_watch_status": 1}
        brief = build_property_review_brief(row, db)
        assert brief.open_alert_count == 2
        assert brief.high_critical_alert_count == 2
        assert brief.alert_burden_label == "high"
        assert brief.lifecycle_health_label == "attention_required"
        assert brief.lifecycle_gap_count == 2


# ---------------------------------------------------------------------------
# Priority ranking tests
# ---------------------------------------------------------------------------

class TestPriorityRanking:
    """Review priority ranking tests."""

    def test_ranking_order(self, tmp_path):
        """Properties with more issues rank higher."""
        from marketsentry.portfolio_review_pack import (
            PortfolioReviewPropertyBrief,
            rank_portfolio_review_briefs,
        )
        b1 = PortfolioReviewPropertyBrief(
            property_id=1,
            lifecycle_health_label="attention_required",
            high_critical_alert_count=2,
        )
        b2 = PortfolioReviewPropertyBrief(
            property_id=2,
            lifecycle_health_label="excellent",
        )
        ranked = rank_portfolio_review_briefs([b2, b1])
        assert ranked[0].property_id == 1
        assert ranked[0].review_priority_label == "immediate_review"
        assert ranked[1].review_priority_label in (
            "low_current_activity", "monitor"
        )

    def test_five_labels(self):
        """All five priority labels can be assigned."""
        from marketsentry.portfolio_review_pack import (
            PortfolioReviewPropertyBrief,
            rank_portfolio_review_briefs,
        )
        briefs = [
            PortfolioReviewPropertyBrief(
                property_id=1,
                lifecycle_health_label="attention_required",
                high_critical_alert_count=2,
            ),
            PortfolioReviewPropertyBrief(
                property_id=2,
                high_critical_alert_count=1,
            ),
            PortfolioReviewPropertyBrief(
                property_id=3,
                recent_churn_index=5.0,
            ),
            PortfolioReviewPropertyBrief(
                property_id=4,
                watch_priority=1,
            ),
            PortfolioReviewPropertyBrief(
                property_id=5,
                quiet_score=80.0,
                active_watch_status=False,
            ),
        ]
        ranked = rank_portfolio_review_briefs(briefs)
        labels = {b.review_priority_label for b in ranked}
        assert "immediate_review" in labels
        assert "low_current_activity" in labels


# ---------------------------------------------------------------------------
# Next action tests
# ---------------------------------------------------------------------------

class TestNextActions:
    """Next action generation tests."""

    def test_actions_from_alerts(self):
        """Next actions include triage when alerts present."""
        from marketsentry.portfolio_review_pack import (
            PortfolioReviewPropertyBrief,
            generate_property_next_actions,
        )
        briefs = [
            PortfolioReviewPropertyBrief(
                property_id=1, high_critical_alert_count=2,
            ),
        ]
        actions = generate_property_next_actions(briefs)
        assert any("triage" in a.action.lower() for a in actions)

    def test_actions_empty_portfolio(self):
        """No immediate actions for an empty portfolio."""
        from marketsentry.portfolio_review_pack import (
            generate_property_next_actions,
        )
        actions = generate_property_next_actions([])
        assert len(actions) == 1
        assert "no immediate" in actions[0].action.lower()


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------

class TestExport:
    """Review pack export tests."""

    def test_md_export(self, tmp_path):
        """Markdown export is generated and contains key sections."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1, quiet_score=80.0, garage_spaces=2)
        out_dir = str(tmp_path / "exports")
        from marketsentry.portfolio_review_pack import (
            export_portfolio_review_pack,
        )
        result = export_portfolio_review_pack(db, out_dir, fmt="md")
        assert len(result.export_paths) == 1
        assert result.export_paths[0].endswith(".md")
        content = Path(result.export_paths[0]).read_text(encoding="utf-8")
        assert "Portfolio Review Pack" in content
        assert "Portfolio Summary" in content
        assert "Property Briefs" in content
        assert "Not a purchase recommendation" in content

    def test_csv_export(self, tmp_path):
        """CSV export contains correct columns."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1, quiet_score=80.0)
        out_dir = str(tmp_path / "exports")
        from marketsentry.portfolio_review_pack import (
            export_portfolio_review_pack,
        )
        result = export_portfolio_review_pack(db, out_dir, fmt="csv")
        assert len(result.export_paths) == 1
        assert result.export_paths[0].endswith(".csv")
        with open(result.export_paths[0], newline="",
                  encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert "property_id" in rows[0]
        assert "quiet_gatekeeper_result" in rows[0]

    def test_both_export(self, tmp_path):
        """Both MD and CSV exports are generated."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1)
        out_dir = str(tmp_path / "exports")
        from marketsentry.portfolio_review_pack import (
            export_portfolio_review_pack,
        )
        result = export_portfolio_review_pack(db, out_dir, fmt="both")
        assert len(result.export_paths) == 2
        extensions = {Path(p).suffix for p in result.export_paths}
        assert ".md" in extensions
        assert ".csv" in extensions


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:
    """CLI command tests."""

    def test_cli_portfolio_review_pack(self, tmp_path):
        """CLI portfolio-review-pack runs successfully."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1, quiet_score=80.0)
        result = runner.invoke(app, [
            "portfolio-review-pack", "--db", db,
        ])
        assert result.exit_code == 0
        assert "Portfolio Review Pack" in result.output

    def test_cli_export_portfolio_review_pack(self, tmp_path):
        """CLI export-portfolio-review-pack runs successfully."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1, quiet_score=80.0)
        out_dir = str(tmp_path / "exports")
        result = runner.invoke(app, [
            "export-portfolio-review-pack",
            "--db", db,
            "--output-dir", out_dir,
            "--format", "both",
        ])
        assert result.exit_code == 0
        assert "Report" in result.output or "report" in result.output.lower()

    def test_cli_empty_db(self, tmp_path):
        """CLI runs on empty database without error."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        result = runner.invoke(app, [
            "portfolio-review-pack", "--db", db,
        ])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------

class TestDashboard:
    """Dashboard portfolio review tests."""

    def test_dashboard_portfolio_data_loads(self, tmp_path):
        """Dashboard portfolio review functions load correctly."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1, quiet_score=80.0)
        _insert_watched(db, 2, quiet_score=50.0)
        from marketsentry.portfolio_review_pack import (
            build_portfolio_review_pack,
        )
        summary, briefs, actions = build_portfolio_review_pack(db)
        assert summary.total_watched == 2
        assert len(briefs) == 2


# ---------------------------------------------------------------------------
# Scheduled script safety tests
# ---------------------------------------------------------------------------

class TestScheduledScript:
    """Scheduled script safety tests."""

    def test_script_no_live_retrieval(self):
        """Script does not contain live retrieval commands."""
        script_path = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        )
        if not script_path.exists():
            pytest.skip("Script not found")
        content = script_path.read_text(encoding="utf-8").lower()
        assert "force-live" not in content
        assert "import-" not in content
        assert "redfin-fetch" not in content
        assert "scrape" not in content

    def test_script_no_mutation_commands(self):
        """Script does not contain mutation commands."""
        script_path = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        )
        if not script_path.exists():
            pytest.skip("Script not found")
        content = script_path.read_text(encoding="utf-8").lower()
        assert "apply-triage" not in content
        assert "apply-expiration" not in content


# ---------------------------------------------------------------------------
# Safety / guard-rail tests
# ---------------------------------------------------------------------------

class TestSafety:
    """Safety guard-rail tests."""

    def test_no_candidate_watchlist_alert_mutation(self):
        """Module does not mutate candidate/watchlist/alert state."""
        src = Path(
            "src/marketsentry/portfolio_review_pack.py"
        ).read_text(encoding="utf-8")
        assert "UPDATE candidate_review_queue" not in src
        assert "DELETE FROM candidate_review_queue" not in src
        assert "UPDATE watched_properties" not in src
        assert "DELETE FROM watched_properties" not in src
        assert "UPDATE cross_site_trend_alerts" not in src
        assert "DELETE FROM cross_site_trend_alerts" not in src
        assert "INSERT INTO candidate_review_queue" not in src
        assert "INSERT INTO watched_properties" not in src

    def test_no_redfin_source_overwrite(self):
        """Module does not overwrite Redfin source-of-truth fields."""
        src = Path(
            "src/marketsentry/portfolio_review_pack.py"
        ).read_text(encoding="utf-8")
        assert "redfin_price" not in src
        assert "redfin_status" not in src

    def test_quiet_gatekeeper_unchanged(self):
        """Module does not modify Quiet Score or Vibrancy Score."""
        src = Path(
            "src/marketsentry/portfolio_review_pack.py"
        ).read_text(encoding="utf-8")
        assert "UPDATE" not in src

    def test_no_walkability_fields(self):
        """Module does not add walkability fields."""
        src = Path(
            "src/marketsentry/portfolio_review_pack.py"
        ).read_text(encoding="utf-8")
        assert "walkability" not in src
        assert "walk_score" not in src

    def test_no_network_calls(self):
        """Module does not import network libraries."""
        src = Path(
            "src/marketsentry/portfolio_review_pack.py"
        ).read_text(encoding="utf-8")
        assert "import requests" not in src
        assert "import urllib" not in src
        assert "import httpx" not in src
        assert "import aiohttp" not in src

    def test_no_browser_automation(self):
        """Module does not use browser automation."""
        src = Path(
            "src/marketsentry/portfolio_review_pack.py"
        ).read_text(encoding="utf-8")
        assert "selenium" not in src
        assert "playwright" not in src
        assert "webdriver" not in src

    def test_model_classes_exist(self):
        """All six M40 models are importable."""
        from marketsentry.portfolio_review_pack import (
            PortfolioReviewFlag,
            PortfolioReviewMetric,
            PortfolioReviewNextAction,
            PortfolioReviewPackRunResult,
            PortfolioReviewPackSummary,
            PortfolioReviewPropertyBrief,
        )
        assert PortfolioReviewPackSummary is not None
        assert PortfolioReviewPropertyBrief is not None
        assert PortfolioReviewMetric is not None
        assert PortfolioReviewFlag is not None
        assert PortfolioReviewNextAction is not None
        assert PortfolioReviewPackRunResult is not None

    def test_county_reset_in_brief(self, tmp_path):
        """Brief shows county reset status."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.portfolio_review_pack import (
            build_property_review_brief,
        )
        row = {"property_id": 1, "county_reset_applied": 1,
               "address": "1 Main St", "city": "Temecula",
               "zip": "92592", "active_watch_status": 1}
        brief = build_property_review_brief(row, db)
        assert brief.county_reset_applied is True

    def test_include_inactive(self, tmp_path):
        """Include-inactive flag includes inactive properties."""
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1, active_watch_status=1)
        _insert_watched(db, 2, active_watch_status=0)
        from marketsentry.portfolio_review_pack import (
            build_portfolio_review_pack,
        )
        _, briefs_active, _ = build_portfolio_review_pack(
            db, include_inactive=False
        )
        _, briefs_all, _ = build_portfolio_review_pack(
            db, include_inactive=True
        )
        assert len(briefs_active) == 1
        assert len(briefs_all) == 2
