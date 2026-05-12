"""Tests for Milestone 38: Watchlist Operations Digest."""

from __future__ import annotations

import csv
import os
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from marketsentry.cli import app
from marketsentry.models import (
    OperationsDigestMetric,
    OperationsDigestNextAction,
    OperationsDigestPropertyPriority,
    OperationsDigestReportRow,
    OperationsDigestRunResult,
    OperationsDigestSection,
    OperationsDigestSummary,
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
            pass  # column already exists
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
                       user_decision: str | None = None) -> None:
    """Insert a candidate into the review queue."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO candidate_review_queue "
        "(candidate_id, discovery_date, source_site, source_search_url, "
        "redfin_url, address, city, zip, user_decision) "
        "VALUES (?, '2026-01-01', 'test', 'http://example.com/search', "
        "'http://example.com/prop', ?, ?, ?, ?)",
        (candidate_id, f"{candidate_id} Main St", "Temecula", "92592",
         user_decision),
    )
    conn.commit()
    conn.close()


def _insert_watched(db_path: str, property_id: int = 1,
                     gas_service: int = 0, garage_spaces: int = 0,
                     watch_priority: int = 0,
                     recent_churn_index: float | None = None,
                     effective_dom_delta: float | None = None,
                     effective_dom: float | None = None,
                     effective_dom_v2: float | None = None,
                     county_reset_applied: int = 0) -> None:
    """Insert a watched property."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO watched_properties "
        "(property_id, first_saved_date, address, city, zip, gas_service, "
        "garage_spaces, active_watch_status, watch_priority, "
        "recent_churn_index, effective_dom_delta, effective_dom, "
        "effective_dom_v2, county_reset_applied) "
        "VALUES (?, '2026-01-01', ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)",
        (property_id, f"{property_id} Main St", "Temecula", "92592",
         gas_service, garage_spaces, watch_priority,
         recent_churn_index, effective_dom_delta, effective_dom,
         effective_dom_v2, county_reset_applied),
    )
    conn.commit()
    conn.close()


def _insert_alert(db_path: str, alert_id: int = 1, property_id: int = 1,
                   alert_status: str = "open",
                   alert_severity: str = "warning",
                   created_at: str = "2026-05-01 00:00:00") -> None:
    """Insert a cross-site trend alert."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO cross_site_trend_alerts "
        "(alert_id, property_id, alert_status, severity, "
        "alert_type, message, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (alert_id, property_id, alert_status, alert_severity,
         "confidence_drop", "Test alert", created_at),
    )
    conn.commit()
    conn.close()


def _insert_health_snapshot(db_path: str, property_id: int = 1,
                             label: str = "excellent",
                             score: float = 95.0) -> None:
    """Insert a lifecycle health snapshot."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO cross_site_lifecycle_health_snapshots "
        "(property_id, lifecycle_health_score, lifecycle_health_label) "
        "VALUES (?, ?, ?)",
        (property_id, score, label),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Tests: Empty database
# ---------------------------------------------------------------------------


class TestEmptyDatabase:
    """Digest should build cleanly on an empty database."""

    def test_build_empty(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest import build_operations_digest
        digest = build_operations_digest(db, str(tmp_path))
        assert len(digest.sections) == 7
        assert digest.generated_at != ""

    def test_export_empty(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest import export_operations_digest
        result = export_operations_digest(db, str(tmp_path), str(tmp_path))
        assert result.sections_built == 7
        assert len(result.export_paths) == 2  # md + csv


# ---------------------------------------------------------------------------
# Tests: Candidate data
# ---------------------------------------------------------------------------


class TestCandidateDigest:
    """Tests for candidate review digest section."""

    def test_candidate_counts(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_candidate(db, 1, "strong_review")
        _insert_candidate(db, 2, "review")
        _insert_candidate(db, 3, None)  # pending
        from marketsentry.operations_digest import build_candidate_review_digest
        sec = build_candidate_review_digest(db, str(tmp_path))
        assert sec.section_name == "Candidate Review"
        vals = {m.metric_name: m.metric_value for m in sec.metrics}
        assert vals["candidate_count"] == "3"
        assert vals["strong_review_count"] == "1"
        assert vals["pending_user_decision_count"] == "1"

    def test_pending_severity(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_candidate(db, 1, None)
        from marketsentry.operations_digest import build_candidate_review_digest
        sec = build_candidate_review_digest(db, str(tmp_path))
        pending = [m for m in sec.metrics
                   if m.metric_name == "pending_user_decision_count"][0]
        assert pending.severity == "warning"


# ---------------------------------------------------------------------------
# Tests: Watchlist data
# ---------------------------------------------------------------------------


class TestWatchlistDigest:
    """Tests for watchlist digest section."""

    def test_watchlist_counts(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1, gas_service=1, garage_spaces=2,
                         watch_priority=1)
        _insert_watched(db, 2, gas_service=0, garage_spaces=0)
        from marketsentry.operations_digest import build_watchlist_digest
        sec = build_watchlist_digest(db, str(tmp_path))
        vals = {m.metric_name: m.metric_value for m in sec.metrics}
        assert vals["watched_property_count"] == "2"
        assert vals["active_watched_count"] == "2"
        assert vals["high_priority_count"] == "1"
        assert vals["gas_evidence_count"] == "1"
        assert vals["garage_evidence_count"] == "1"


# ---------------------------------------------------------------------------
# Tests: Effective DOM digest
# ---------------------------------------------------------------------------


class TestEffectiveDomDigest:
    """Tests for Effective DOM / Churn section."""

    def test_dom_metrics(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1, county_reset_applied=1,
                         recent_churn_index=8.0,
                         effective_dom=200, effective_dom_v2=100,
                         effective_dom_delta=80)
        _insert_watched(db, 2)
        from marketsentry.operations_digest import build_effective_dom_digest
        sec = build_effective_dom_digest(db, str(tmp_path))
        vals = {m.metric_name: m.metric_value for m in sec.metrics}
        assert vals["county_reset_applied_count"] == "1"
        assert vals["high_recent_churn_count"] == "1"
        assert vals["v2_materially_below_v1_count"] == "1"
        assert vals["high_effective_dom_delta_count"] == "1"


# ---------------------------------------------------------------------------
# Tests: Cross-site digest
# ---------------------------------------------------------------------------


class TestCrossSiteDigest:
    """Tests for cross-site section."""

    def test_no_observations(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest import build_cross_site_digest
        sec = build_cross_site_digest(db, str(tmp_path))
        assert sec.section_name == "Cross-Site Validation"


# ---------------------------------------------------------------------------
# Tests: Alert digest
# ---------------------------------------------------------------------------


class TestAlertDigest:
    """Tests for alerts and hygiene section."""

    def test_alert_counts(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1)
        _insert_alert(db, 1, 1, "open", "high", "2026-01-01 00:00:00")
        _insert_alert(db, 2, 1, "open", "warning")
        _insert_alert(db, 3, 1, "resolved", "info", "2025-01-01 00:00:00")
        from marketsentry.operations_digest import build_alert_digest
        sec = build_alert_digest(db, str(tmp_path))
        vals = {m.metric_name: m.metric_value for m in sec.metrics}
        assert vals["open_alert_count"] == "2"
        assert vals["high_critical_open_alert_count"] == "1"
        assert int(vals["stale_open_alert_count"]) >= 1

    def test_archive_candidates(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1)
        _insert_alert(db, 1, 1, "resolved", "info", "2025-01-01 00:00:00")
        from marketsentry.operations_digest import build_alert_digest
        sec = build_alert_digest(db, str(tmp_path))
        vals = {m.metric_name: m.metric_value for m in sec.metrics}
        assert int(vals["archive_candidates_count"]) >= 1


# ---------------------------------------------------------------------------
# Tests: Lifecycle digest
# ---------------------------------------------------------------------------


class TestLifecycleDigest:
    """Tests for lifecycle health section."""

    def test_health_snapshot_counts(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_health_snapshot(db, 1, "attention_required", 30.0)
        _insert_health_snapshot(db, 2, "needs_review", 50.0)
        from marketsentry.operations_digest import build_lifecycle_digest
        sec = build_lifecycle_digest(db, str(tmp_path))
        vals = {m.metric_name: m.metric_value for m in sec.metrics}
        assert vals["properties_scored"] == "2"
        assert vals["attention_required_count"] == "1"
        assert vals["needs_review_count"] == "1"


# ---------------------------------------------------------------------------
# Tests: Retrieval operations digest
# ---------------------------------------------------------------------------


class TestRetrievalDigest:
    """Tests for retrieval operations section."""

    def test_no_network_note(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest import build_retrieval_operations_digest
        sec = build_retrieval_operations_digest(db, str(tmp_path))
        vals = {m.metric_name: m.metric_value for m in sec.metrics}
        assert vals["digest_network_calls"] == "none"

    def test_pending_capture_count(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO fixture_capture_queue "
            "(source_site, source_url, status) "
            "VALUES ('test', 'http://example.com', 'pending')"
        )
        conn.commit()
        conn.close()
        from marketsentry.operations_digest import build_retrieval_operations_digest
        sec = build_retrieval_operations_digest(db, str(tmp_path))
        vals = {m.metric_name: m.metric_value for m in sec.metrics}
        assert vals["pending_capture_queue_count"] == "1"


# ---------------------------------------------------------------------------
# Tests: Priority ranking
# ---------------------------------------------------------------------------


class TestPriorityRanking:
    """Tests for review priority ranking."""

    def test_attention_required_is_immediate(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1)
        _insert_health_snapshot(db, 1, "attention_required", 20.0)
        from marketsentry.operations_digest import rank_operations_review_priorities
        prios = rank_operations_review_priorities(db)
        assert len(prios) >= 1
        assert prios[0].priority_label == "immediate_review"

    def test_high_critical_alert_is_high_review(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1)
        _insert_alert(db, 1, 1, "open", "critical")
        from marketsentry.operations_digest import rank_operations_review_priorities
        prios = rank_operations_review_priorities(db)
        assert len(prios) >= 1
        assert prios[0].priority_label in ("immediate_review", "high_review")

    def test_empty_db_no_priorities(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest import rank_operations_review_priorities
        prios = rank_operations_review_priorities(db)
        assert prios == []

    def test_priority_sorting(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1)
        _insert_watched(db, 2)
        _insert_health_snapshot(db, 1, "attention_required", 20.0)
        _insert_alert(db, 1, 2, "open", "warning", "2026-01-01 00:00:00")
        from marketsentry.operations_digest import rank_operations_review_priorities
        prios = rank_operations_review_priorities(db)
        assert len(prios) >= 2
        labels = [p.priority_label for p in prios]
        assert labels[0] == "immediate_review"

    def test_high_churn_adds_priority(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1, recent_churn_index=8.0,
                         effective_dom_delta=90)
        from marketsentry.operations_digest import rank_operations_review_priorities
        prios = rank_operations_review_priorities(db)
        assert len(prios) >= 1
        assert any("churn" in r.lower() for r in prios[0].reasons)


# ---------------------------------------------------------------------------
# Tests: Next actions
# ---------------------------------------------------------------------------


class TestNextActions:
    """Tests for next action generation."""

    def test_pending_decisions_trigger_action(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_candidate(db, 1, None)
        from marketsentry.operations_digest import build_operations_digest
        digest = build_operations_digest(db, str(tmp_path))
        cmds = [a.command for a in digest.next_actions]
        assert "marketsentry export-review" in cmds

    def test_always_includes_dashboard(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest import build_operations_digest
        digest = build_operations_digest(db, str(tmp_path))
        cmds = [a.command for a in digest.next_actions]
        assert "marketsentry launch-dashboard" in cmds

    def test_high_critical_alerts_trigger_triage(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1)
        _insert_alert(db, 1, 1, "open", "high")
        from marketsentry.operations_digest import build_operations_digest
        digest = build_operations_digest(db, str(tmp_path))
        cmds = [a.command for a in digest.next_actions]
        assert any("triage" in c for c in cmds)


# ---------------------------------------------------------------------------
# Tests: Markdown export
# ---------------------------------------------------------------------------


class TestMarkdownExport:
    """Tests for Markdown digest export."""

    def test_md_file_created(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest import export_operations_digest
        result = export_operations_digest(db, str(tmp_path), str(tmp_path), "md")
        assert len(result.export_paths) == 1
        assert result.export_paths[0].endswith(".md")
        content = Path(result.export_paths[0]).read_text()
        assert "Watchlist Operations Digest" in content
        assert "No mutations" in content

    def test_md_contains_sections(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_watched(db, 1)
        from marketsentry.operations_digest import export_operations_digest
        result = export_operations_digest(db, str(tmp_path), str(tmp_path), "md")
        content = Path(result.export_paths[0]).read_text()
        assert "## Watchlist" in content
        assert "## Candidate Review" in content


# ---------------------------------------------------------------------------
# Tests: CSV export
# ---------------------------------------------------------------------------


class TestCSVExport:
    """Tests for CSV digest export."""

    def test_csv_file_created(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest import export_operations_digest
        result = export_operations_digest(db, str(tmp_path), str(tmp_path), "csv")
        assert len(result.export_paths) == 1
        assert result.export_paths[0].endswith(".csv")

    def test_csv_has_fieldnames(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_candidate(db, 1, "review")
        from marketsentry.operations_digest import export_operations_digest
        result = export_operations_digest(db, str(tmp_path), str(tmp_path), "csv")
        with open(result.export_paths[0], newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            assert "section" in reader.fieldnames
            assert "metric_name" in reader.fieldnames
            assert "metric_value" in reader.fieldnames
            assert "severity" in reader.fieldnames

    def test_both_format(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        from marketsentry.operations_digest import export_operations_digest
        result = export_operations_digest(db, str(tmp_path), str(tmp_path), "both")
        assert len(result.export_paths) == 2
        exts = {Path(p).suffix for p in result.export_paths}
        assert exts == {".csv", ".md"}


# ---------------------------------------------------------------------------
# Tests: CLI operations-digest
# ---------------------------------------------------------------------------


class TestCLIDigest:
    """Tests for the operations-digest CLI command."""

    def test_cli_runs(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        result = runner.invoke(app, [
            "operations-digest", "--db", db,
            "--exports-dir", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "Watchlist Operations Digest" in result.output
        assert "No mutations performed" in result.output

    def test_cli_with_data(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_candidate(db, 1, None)
        _insert_watched(db, 1)
        result = runner.invoke(app, [
            "operations-digest", "--db", db,
            "--exports-dir", str(tmp_path),
        ])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Tests: CLI export-operations-digest
# ---------------------------------------------------------------------------


class TestCLIExportDigest:
    """Tests for the export-operations-digest CLI command."""

    def test_cli_export_runs(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        result = runner.invoke(app, [
            "export-operations-digest", "--db", db,
            "--output-dir", str(tmp_path),
            "--format", "both",
        ])
        assert result.exit_code == 0
        assert "Operations Digest Export" in result.output
        assert "No mutations performed" in result.output

    def test_cli_export_csv_only(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        result = runner.invoke(app, [
            "export-operations-digest", "--db", db,
            "--output-dir", str(tmp_path),
            "--format", "csv",
        ])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Tests: Dashboard loads
# ---------------------------------------------------------------------------


class TestDashboard:
    """Tests that dashboard digest integration does not break import."""

    def test_dashboard_imports(self) -> None:
        import marketsentry.dashboard_app  # noqa: F401


# ---------------------------------------------------------------------------
# Tests: Scheduled script safety
# ---------------------------------------------------------------------------


class TestScheduledScript:
    """Tests that the scheduled script is safe."""

    def test_script_exists(self) -> None:
        script = Path("scripts/run_operations_digest_report.bat")
        assert script.exists()

    def test_no_force_live(self) -> None:
        content = Path("scripts/run_operations_digest_report.bat").read_text()
        assert "--force-live" not in content

    def test_no_import_commands(self) -> None:
        content = Path("scripts/run_operations_digest_report.bat").read_text().lower()
        assert "import-review" not in content
        assert "import-cross-site" not in content
        assert "import-county" not in content

    def test_no_mutation_commands(self) -> None:
        content = Path("scripts/run_operations_digest_report.bat").read_text().lower()
        assert "acknowledge" not in content
        assert "resolve" not in content


# ---------------------------------------------------------------------------
# Tests: No mutation
# ---------------------------------------------------------------------------


class TestNoMutation:
    """Digest must not mutate candidate/watchlist/alert state."""

    def test_module_has_no_update_or_delete(self) -> None:
        src = Path("src/marketsentry/operations_digest.py").read_text()
        for line in src.split("\n"):
            stripped = line.strip().upper()
            if stripped.startswith('"') or stripped.startswith("'"):
                if "UPDATE " in stripped and "SELECT" not in stripped:
                    pytest.fail(f"Mutation SQL found: {line.strip()}")
                if "DELETE " in stripped:
                    pytest.fail(f"Delete SQL found: {line.strip()}")

    def test_build_digest_does_not_change_db(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_candidate(db, 1, "review")
        _insert_watched(db, 1)
        _insert_alert(db, 1, 1, "open", "high")

        conn = sqlite3.connect(db)
        before_c = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        before_w = conn.execute(
            "SELECT COUNT(*) FROM watched_properties"
        ).fetchone()[0]
        before_a = conn.execute(
            "SELECT COUNT(*) FROM cross_site_trend_alerts"
        ).fetchone()[0]
        conn.close()

        from marketsentry.operations_digest import build_operations_digest
        build_operations_digest(db, str(tmp_path))

        conn = sqlite3.connect(db)
        after_c = conn.execute(
            "SELECT COUNT(*) FROM candidate_review_queue"
        ).fetchone()[0]
        after_w = conn.execute(
            "SELECT COUNT(*) FROM watched_properties"
        ).fetchone()[0]
        after_a = conn.execute(
            "SELECT COUNT(*) FROM cross_site_trend_alerts"
        ).fetchone()[0]
        conn.close()

        assert before_c == after_c
        assert before_w == after_w
        assert before_a == after_a


# ---------------------------------------------------------------------------
# Tests: No Redfin overwrite
# ---------------------------------------------------------------------------


class TestNoRedfin:
    """Digest must not overwrite Redfin source-of-truth fields."""

    def test_no_redfin_field_writes(self) -> None:
        src = Path("src/marketsentry/operations_digest.py").read_text()
        for field in ("current_price", "beds", "baths", "sqft",
                      "listing_status", "displayed_dom"):
            assert f"SET {field}" not in src


# ---------------------------------------------------------------------------
# Tests: Quiet gatekeeper unchanged
# ---------------------------------------------------------------------------


class TestQuietGatekeeper:
    """Digest must not modify Quiet Score gatekeeper."""

    def test_no_quiet_modification(self) -> None:
        src = Path("src/marketsentry/operations_digest.py").read_text()
        assert "SET quiet" not in src.lower()


# ---------------------------------------------------------------------------
# Tests: No walkability
# ---------------------------------------------------------------------------


class TestNoWalkability:
    """No walkability fields added."""

    def test_no_walkability_in_module(self) -> None:
        src = Path("src/marketsentry/operations_digest.py").read_text().lower()
        assert "walkability" not in src
        assert "walk_score" not in src
        assert "walkscore" not in src


# ---------------------------------------------------------------------------
# Tests: No network calls
# ---------------------------------------------------------------------------


class TestNoNetworkCalls:
    """Digest performs no real network calls."""

    def test_no_requests_import(self) -> None:
        src = Path("src/marketsentry/operations_digest.py").read_text()
        assert "import requests" not in src
        assert "import httpx" not in src
        assert "import urllib.request" not in src

    def test_no_socket_import(self) -> None:
        src = Path("src/marketsentry/operations_digest.py").read_text()
        assert "import socket" not in src


# ---------------------------------------------------------------------------
# Tests: No browser automation
# ---------------------------------------------------------------------------


class TestNoBrowserAutomation:
    """No browser automation in digest module."""

    def test_no_playwright_selenium(self) -> None:
        src = Path("src/marketsentry/operations_digest.py").read_text().lower()
        assert "playwright" not in src
        assert "selenium" not in src
        assert "webdriver" not in src


# ---------------------------------------------------------------------------
# Tests: Models
# ---------------------------------------------------------------------------


class TestModels:
    """Test that all M38 models instantiate correctly."""

    def test_operations_digest_metric(self) -> None:
        m = OperationsDigestMetric(metric_name="test", metric_value="42")
        assert m.metric_name == "test"
        assert m.severity == "info"

    def test_operations_digest_section(self) -> None:
        s = OperationsDigestSection(section_name="Test")
        assert s.section_name == "Test"
        assert s.metrics == []

    def test_operations_digest_property_priority(self) -> None:
        p = OperationsDigestPropertyPriority(
            property_id=1, priority_label="high_review"
        )
        assert p.priority_label == "high_review"
        assert p.reasons == []

    def test_operations_digest_next_action(self) -> None:
        a = OperationsDigestNextAction(action="test", command="cmd")
        assert a.priority == "normal"

    def test_operations_digest_summary(self) -> None:
        s = OperationsDigestSummary()
        assert s.sections == []
        assert s.top_priorities == []
        assert s.next_actions == []

    def test_operations_digest_report_row(self) -> None:
        r = OperationsDigestReportRow(section="Test", metric_name="foo")
        assert r.severity == "info"

    def test_operations_digest_run_result(self) -> None:
        r = OperationsDigestRunResult()
        assert r.sections_built == 0
        assert r.export_paths == []


# ---------------------------------------------------------------------------
# Tests: Multiple properties
# ---------------------------------------------------------------------------


class TestMultipleProperties:
    """Test digest with multiple watched properties."""

    def test_multiple_watched(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        for i in range(1, 6):
            _insert_watched(db, i)
        from marketsentry.operations_digest import build_operations_digest
        digest = build_operations_digest(db, str(tmp_path))
        w_sec = [s for s in digest.sections
                 if s.section_name == "Watchlist"][0]
        vals = {m.metric_name: m.metric_value for m in w_sec.metrics}
        assert vals["watched_property_count"] == "5"


# ---------------------------------------------------------------------------
# Tests: Full digest build
# ---------------------------------------------------------------------------


class TestFullDigest:
    """Integration test: build full digest with mixed data."""

    def test_full_build(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_candidate(db, 1, "strong_review")
        _insert_candidate(db, 2, None)
        _insert_watched(db, 1, gas_service=1, garage_spaces=2,
                         watch_priority=1, recent_churn_index=7.0,
                         effective_dom_delta=90)
        _insert_watched(db, 2)
        _insert_alert(db, 1, 1, "open", "high", "2026-01-01 00:00:00")
        _insert_alert(db, 2, 1, "resolved", "info", "2025-01-01 00:00:00")
        _insert_health_snapshot(db, 1, "attention_required", 25.0)
        _insert_health_snapshot(db, 2, "excellent", 95.0)

        from marketsentry.operations_digest import build_operations_digest
        digest = build_operations_digest(db, str(tmp_path))

        assert len(digest.sections) == 7
        assert len(digest.top_priorities) >= 1
        assert digest.top_priorities[0].priority_label == "immediate_review"
        assert len(digest.next_actions) >= 1

    def test_full_export(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        _init_db(db)
        _insert_candidate(db, 1, "review")
        _insert_watched(db, 1)
        from marketsentry.operations_digest import export_operations_digest
        result = export_operations_digest(db, str(tmp_path), str(tmp_path))
        assert result.sections_built == 7
        assert result.metric_count > 0
        assert len(result.export_paths) == 2
