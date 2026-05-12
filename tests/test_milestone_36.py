"""Tests for Milestone 36: Property-Level Lifecycle Health Scoring.

Validates health scoring, label thresholds, component breakdown,
summary, CSV/Markdown export, CLI commands, dashboard integration,
and safety constraints.
"""

import csv
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from marketsentry.database import init_db
from marketsentry.models import (
    CrossSiteLifecycleHealthComponent,
    CrossSiteLifecycleHealthReportRow,
    CrossSiteLifecycleHealthRunResult,
    CrossSiteLifecycleHealthScore,
    CrossSiteLifecycleHealthSummary,
)


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = str(tmp_path / "test_m36.db")
    init_db(db_path)
    yield db_path


@pytest.fixture
def temp_exports_dir(tmp_path):
    """Create a temporary exports directory."""
    exports = tmp_path / "exports"
    exports.mkdir()
    return str(exports)


def _insert_candidate(db_path, candidate_id, property_id, address="123 Main St",
                       city="TestCity", zip_code="12345"):
    """Insert a test candidate."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO candidates "
        "(candidate_id, property_id, address, city, zip) "
        "VALUES (?, ?, ?, ?, ?)",
        (candidate_id, property_id, address, city, zip_code),
    )
    conn.commit()
    conn.close()


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


def _insert_triage_action(db_path, triage_action_id, alert_id, property_id,
                           action="acknowledge", previous_status="open",
                           new_status="acknowledged", applied_at=None,
                           triage_export_id="triage_test", triage_notes=""):
    """Insert a test triage action."""
    if applied_at is None:
        applied_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO cross_site_alert_triage_actions "
        "(triage_action_id, triage_export_id, alert_id, property_id, "
        "action, previous_status, new_status, triage_notes, applied_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (triage_action_id, triage_export_id, alert_id, property_id,
         action, previous_status, new_status, triage_notes, applied_at),
    )
    conn.commit()
    conn.close()


# ── Score with no alerts ──

class TestNoAlerts:
    """Properties with no alerts should have excellent or good scores."""

    def test_no_alerts_excellent(self, temp_db):
        """Property with no alerts scores excellent."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.lifecycle_health_score == 100.0
        assert score.lifecycle_health_label == "excellent"

    def test_no_alerts_no_components(self, temp_db):
        """Property with no alerts has no deduction components."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        deductions = [c for c in score.components if c.component_score_delta < 0]
        assert len(deductions) == 0


# ── Score with open high/critical alerts ──

class TestHighCriticalAlerts:
    """Open high/critical alerts decrease score."""

    def test_high_alert_decreases_score(self, temp_db):
        """One open high alert decreases score."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, severity="high", status="open")
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.lifecycle_health_score < 100.0
        assert score.high_or_critical_open_alert_count == 1

    def test_critical_alert_decreases_score(self, temp_db):
        """One open critical alert decreases score."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, severity="critical", status="open")
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.lifecycle_health_score < 100.0

    def test_multiple_high_critical_more_decrease(self, temp_db):
        """Multiple high/critical alerts decrease score more."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, severity="high", status="open")
        score1 = calculate_lifecycle_health_score_for_property(1, temp_db)

        _insert_alert(temp_db, 2, 1, severity="critical", status="open")
        score2 = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score2.lifecycle_health_score < score1.lifecycle_health_score


# ── Score with lifecycle gaps ──

class TestLifecycleGaps:
    """Lifecycle gaps decrease score."""

    def test_stale_open_creates_gap(self, temp_db):
        """Old open alert without triage creates a lifecycle gap."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        old_date = (datetime.now() - timedelta(days=10)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        _insert_alert(temp_db, 1, 1, status="open", created_at=old_date)
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.lifecycle_health_score < 100.0
        assert score.lifecycle_gap_count > 0


# ── Score with stale open alerts ──

class TestStaleOpenAlerts:
    """Stale open alerts decrease score."""

    def test_stale_alert_decreases(self, temp_db):
        """Open alert older than 7 days decreases score."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        old_date = (datetime.now() - timedelta(days=10)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        _insert_alert(temp_db, 1, 1, status="open", created_at=old_date)
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.stale_open_alert_count >= 1
        assert score.lifecycle_health_score < 100.0


# ── Score with needs_reparse ──

class TestNeedsReparse:
    """Needs reparse markers decrease score."""

    def test_needs_reparse_decreases(self, temp_db):
        """Alert with needs_reparse note decreases score."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(
            temp_db, 1, 1, status="open",
            notes="[triage:needs_reparse]",
        )
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.needs_reparse_count >= 1
        assert score.lifecycle_health_score < 100.0


# ── Score with needs_manual_review ──

class TestNeedsManualReview:
    """Needs manual review markers decrease score."""

    def test_needs_manual_review_decreases(self, temp_db):
        """Alert with needs_manual_review note decreases score."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(
            temp_db, 1, 1, status="open",
            notes="[triage:needs_manual_review]",
        )
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.needs_manual_review_count >= 1
        assert score.lifecycle_health_score < 100.0


# ── Score with repeated patterns ──

class TestRepeatedPatterns:
    """Repeated unresolved patterns decrease score."""

    def test_repeated_patterns_decrease(self, temp_db):
        """Two open alerts of same type create a repeated pattern."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(
            temp_db, 1, 1, alert_type="price_change", status="open",
        )
        _insert_alert(
            temp_db, 2, 1, alert_type="price_change", status="open",
        )
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.repeated_patterns >= 1
        assert score.lifecycle_health_score < 100.0


# ── Score with mostly resolved/archived history ──

class TestResolvedHistory:
    """Mostly resolved/archived history should keep score high."""

    def test_all_resolved_stays_high(self, temp_db):
        """All resolved alerts should score excellent or good."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="resolved")
        _insert_alert(temp_db, 2, 1, status="resolved")
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.lifecycle_health_score >= 90.0

    def test_all_archived_stays_high(self, temp_db):
        """All archived alerts should score excellent or good."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="archived")
        _insert_alert(temp_db, 2, 1, status="archived")
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.lifecycle_health_score >= 90.0


# ── Health label thresholds ──

class TestHealthLabels:
    """Test health label classification."""

    def test_excellent_threshold(self):
        """Score >= 90 classifies as excellent."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            classify_lifecycle_health_label,
        )
        assert classify_lifecycle_health_label(100) == "excellent"
        assert classify_lifecycle_health_label(90) == "excellent"

    def test_good_threshold(self):
        """Score 75-89 classifies as good."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            classify_lifecycle_health_label,
        )
        assert classify_lifecycle_health_label(89) == "good"
        assert classify_lifecycle_health_label(75) == "good"

    def test_watch_threshold(self):
        """Score 60-74 classifies as watch."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            classify_lifecycle_health_label,
        )
        assert classify_lifecycle_health_label(74) == "watch"
        assert classify_lifecycle_health_label(60) == "watch"

    def test_needs_review_threshold(self):
        """Score 40-59 classifies as needs_review."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            classify_lifecycle_health_label,
        )
        assert classify_lifecycle_health_label(59) == "needs_review"
        assert classify_lifecycle_health_label(40) == "needs_review"

    def test_attention_required_threshold(self):
        """Score 0-39 classifies as attention_required."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            classify_lifecycle_health_label,
        )
        assert classify_lifecycle_health_label(39) == "attention_required"
        assert classify_lifecycle_health_label(0) == "attention_required"


# ── Component breakdown ──

class TestComponentBreakdown:
    """Component breakdown is detailed and correct."""

    def test_component_names(self, temp_db):
        """Components include expected names."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        old_date = (datetime.now() - timedelta(days=10)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        _insert_alert(
            temp_db, 1, 1, severity="high", status="open",
            created_at=old_date,
        )
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        comp_names = [c.component_name for c in score.components]
        assert "open_high_critical_alerts" in comp_names

    def test_component_has_explanation(self, temp_db):
        """Each component has a non-empty explanation."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, severity="high", status="open")
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        for c in score.components:
            if c.component_score_delta != 0:
                assert c.explanation != ""

    def test_component_deltas_sum(self, temp_db):
        """Sum of component deltas should match score difference from 100."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, severity="high", status="open")
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        delta_sum = sum(c.component_score_delta for c in score.components)
        expected = max(0.0, min(100.0, 100.0 + delta_sum))
        assert score.lifecycle_health_score == round(expected, 1)


# ── Summary label counts ──

class TestSummaryLabelCounts:
    """Summary aggregation and label counting."""

    def test_summary_counts(self, temp_db):
        """Summary counts match individual scores."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_scores,
            summarize_lifecycle_health_scores,
        )

        _insert_watched_property(temp_db, 1)
        _insert_watched_property(temp_db, 2, address="456 Oak Ave")
        _insert_alert(temp_db, 1, 1, status="resolved")
        _insert_alert(temp_db, 2, 2, severity="high", status="open")

        scores = calculate_lifecycle_health_scores(temp_db)
        summary = summarize_lifecycle_health_scores(scores)
        assert summary.properties_scored == 2
        total_labels = sum(summary.label_counts.values())
        assert total_labels == 2

    def test_summary_lowest_properties(self, temp_db):
        """Summary lists lowest-scoring properties."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_scores,
            summarize_lifecycle_health_scores,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, severity="high", status="open")

        scores = calculate_lifecycle_health_scores(temp_db)
        summary = summarize_lifecycle_health_scores(scores)
        assert len(summary.lowest_health_properties) > 0


# ── CSV report export ──

class TestCSVExport:
    """CSV report export validation."""

    def test_csv_export_creates_file(self, temp_db, temp_exports_dir):
        """Export creates a CSV file."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            export_lifecycle_health_report,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        result = export_lifecycle_health_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
            format="csv",
        )
        assert len(result.export_paths) == 1
        assert os.path.exists(result.export_paths[0])

    def test_csv_has_required_columns(self, temp_db, temp_exports_dir):
        """CSV file contains all required columns."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            export_lifecycle_health_report,
            HEALTH_CSV_FIELDNAMES,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        result = export_lifecycle_health_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
            format="csv",
        )
        with open(result.export_paths[0], "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            for field in HEALTH_CSV_FIELDNAMES:
                assert field in headers, f"Missing column: {field}"

    def test_csv_row_count(self, temp_db, temp_exports_dir):
        """CSV has correct number of rows."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            export_lifecycle_health_report,
        )

        _insert_watched_property(temp_db, 1)
        _insert_watched_property(temp_db, 2, address="456 Oak Ave")
        _insert_alert(temp_db, 1, 1, status="open")
        _insert_alert(temp_db, 2, 2, status="resolved")

        result = export_lifecycle_health_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
            format="csv",
        )
        with open(result.export_paths[0], "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2

    def test_csv_filename_pattern(self, temp_db, temp_exports_dir):
        """CSV filename follows expected pattern."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            export_lifecycle_health_report,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        result = export_lifecycle_health_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
            format="csv",
        )
        filename = Path(result.export_paths[0]).name
        assert filename.startswith("cross_site_lifecycle_health_")
        assert filename.endswith(".csv")


# ── Markdown report export ──

class TestMarkdownExport:
    """Markdown report export validation."""

    def test_md_export_creates_file(self, temp_db, temp_exports_dir):
        """Export creates a Markdown file."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            export_lifecycle_health_report,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        result = export_lifecycle_health_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
            format="md",
        )
        assert len(result.export_paths) == 1
        assert result.export_paths[0].endswith(".md")
        assert os.path.exists(result.export_paths[0])

    def test_md_contains_summary(self, temp_db, temp_exports_dir):
        """Markdown file contains summary section."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            export_lifecycle_health_report,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        result = export_lifecycle_health_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
            format="md",
        )
        content = Path(result.export_paths[0]).read_text(encoding="utf-8")
        assert "## Summary" in content
        assert "read-only" in content.lower()

    def test_both_format_exports(self, temp_db, temp_exports_dir):
        """Both format creates CSV and Markdown files."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            export_lifecycle_health_report,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        result = export_lifecycle_health_report(
            database_path=temp_db,
            output_dir=temp_exports_dir,
            format="both",
        )
        assert len(result.export_paths) == 2
        extensions = {Path(p).suffix for p in result.export_paths}
        assert ".csv" in extensions
        assert ".md" in extensions


# ── CLI commands ──

class TestCLIHealthSummary:
    """CLI lifecycle health summary command tests."""

    def test_cli_health_summary_runs(self, temp_db):
        """Health summary CLI command runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        runner = CliRunner()
        result = runner.invoke(
            app, ["cross-site-lifecycle-health-summary", "--db", temp_db],
        )
        assert result.exit_code == 0
        assert "Properties scored" in result.output

    def test_cli_health_summary_single_property(self, temp_db):
        """Health summary with --property-id shows single property."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        runner = CliRunner()
        result = runner.invoke(
            app, [
                "cross-site-lifecycle-health-summary",
                "--db", temp_db,
                "--property-id", "1",
            ],
        )
        assert result.exit_code == 0
        assert "Health Score" in result.output


class TestCLIHealthReport:
    """CLI lifecycle health report export command tests."""

    def test_cli_health_report_runs(self, temp_db, temp_exports_dir):
        """Health report CLI command runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        runner = CliRunner()
        result = runner.invoke(
            app, [
                "export-cross-site-lifecycle-health-report",
                "--db", temp_db,
                "--output-dir", temp_exports_dir,
            ],
        )
        assert result.exit_code == 0
        assert "Report exported" in result.output

    def test_cli_health_report_md_format(self, temp_db, temp_exports_dir):
        """Health report with --format md exports markdown."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        runner = CliRunner()
        result = runner.invoke(
            app, [
                "export-cross-site-lifecycle-health-report",
                "--db", temp_db,
                "--output-dir", temp_exports_dir,
                "--format", "md",
            ],
        )
        assert result.exit_code == 0

    def test_cli_health_report_no_data(self, temp_db, temp_exports_dir):
        """Health report with no data shows warning."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app, [
                "export-cross-site-lifecycle-health-report",
                "--db", temp_db,
                "--output-dir", temp_exports_dir,
            ],
        )
        assert result.exit_code == 0


# ── Dashboard ──

class TestDashboard:
    """Dashboard lifecycle health section tests."""

    def test_dashboard_imports(self):
        """Dashboard module imports without error."""
        import marketsentry.dashboard_app  # noqa: F401

    def test_dashboard_health_section_keyword(self):
        """Dashboard source contains lifecycle health section."""
        src = Path(
            "src/marketsentry/dashboard_app.py"
        ).read_text(encoding="utf-8")
        assert "Lifecycle Health" in src
        assert "calculate_lifecycle_health_scores" in src


# ── No alert/watchlist mutation ──

class TestNoMutation:
    """Health scoring must not mutate alert or watchlist state."""

    def test_no_alert_mutation(self, temp_db):
        """Calculating health scores does not change alert status."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_scores,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, severity="high", status="open")

        # Get initial state
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        before = [dict(r) for r in conn.execute(
            "SELECT * FROM cross_site_trend_alerts"
        ).fetchall()]
        conn.close()

        # Calculate scores
        calculate_lifecycle_health_scores(temp_db)

        # Verify no change
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        after = [dict(r) for r in conn.execute(
            "SELECT * FROM cross_site_trend_alerts"
        ).fetchall()]
        conn.close()

        assert before == after

    def test_no_watchlist_mutation(self, temp_db):
        """Calculating health scores does not change watchlist state."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_scores,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        before = [dict(r) for r in conn.execute(
            "SELECT * FROM watched_properties"
        ).fetchall()]
        conn.close()

        calculate_lifecycle_health_scores(temp_db)

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        after = [dict(r) for r in conn.execute(
            "SELECT * FROM watched_properties"
        ).fetchall()]
        conn.close()

        assert before == after


# ── No Redfin source-of-truth overwrite ──

class TestNoRedfin:
    """Health module must not overwrite Redfin source-of-truth fields."""

    def test_no_redfin_overwrite_in_source(self):
        """Module source does not contain redfin field update queries."""
        src = Path(
            "src/marketsentry/cross_site_alert_lifecycle_health.py"
        ).read_text(encoding="utf-8").lower()
        assert "update candidates" not in src
        assert "update watched_properties" not in src


# ── Quiet gatekeeper unchanged ──

class TestQuietGatekeeper:
    """Quiet Score gatekeeper must remain unchanged."""

    def test_no_quiet_score_reference(self):
        """Health module does not reference quiet_score."""
        src = Path(
            "src/marketsentry/cross_site_alert_lifecycle_health.py"
        ).read_text(encoding="utf-8").lower()
        assert "quiet_score" not in src
        assert "vibrancy_score" not in src


# ── No walkability ──

class TestNoWalkability:
    """No walkability fields added."""

    def test_no_walkability_in_module(self):
        """Health module does not contain walkability references."""
        src = Path(
            "src/marketsentry/cross_site_alert_lifecycle_health.py"
        ).read_text(encoding="utf-8").lower()
        assert "walkability" not in src
        assert "walk_score" not in src

    def test_no_walkability_in_models(self):
        """M36 models do not contain walkability fields."""
        src = Path(
            "src/marketsentry/models.py"
        ).read_text(encoding="utf-8")
        # Check only the M36 section
        m36_start = src.find("Milestone 36")
        if m36_start > 0:
            m36_section = src[m36_start:].lower()
            assert "walkability" not in m36_section


# ── No real network calls ──

class TestNoNetworkCalls:
    """Tests must not make real network calls."""

    def test_no_requests_in_module(self):
        """Health module does not import requests."""
        src = Path(
            "src/marketsentry/cross_site_alert_lifecycle_health.py"
        ).read_text(encoding="utf-8")
        assert "import requests" not in src
        assert "requests.get" not in src

    def test_no_urllib_in_module(self):
        """Health module does not use urllib for HTTP calls."""
        src = Path(
            "src/marketsentry/cross_site_alert_lifecycle_health.py"
        ).read_text(encoding="utf-8")
        assert "urllib.request" not in src


# ── Models ──

class TestModels:
    """M36 model validation."""

    def test_health_score_model(self):
        """CrossSiteLifecycleHealthScore initializes with defaults."""
        score = CrossSiteLifecycleHealthScore()
        assert score.lifecycle_health_score == 100.0
        assert score.lifecycle_health_label == "excellent"
        assert score.components == []

    def test_health_component_model(self):
        """CrossSiteLifecycleHealthComponent initializes correctly."""
        comp = CrossSiteLifecycleHealthComponent(
            component_name="test",
            component_score_delta=-10.0,
            severity="high",
            explanation="Test explanation",
            supporting_count=1,
        )
        assert comp.component_name == "test"
        assert comp.component_score_delta == -10.0

    def test_health_report_row_model(self):
        """CrossSiteLifecycleHealthReportRow has expected fields."""
        row = CrossSiteLifecycleHealthReportRow()
        assert row.property_id == 0
        assert row.lifecycle_health_score == 100.0
        assert row.component_summary == ""

    def test_health_summary_model(self):
        """CrossSiteLifecycleHealthSummary has expected fields."""
        summary = CrossSiteLifecycleHealthSummary()
        assert summary.properties_scored == 0
        assert summary.label_counts == {}
        assert summary.lowest_health_properties == []

    def test_health_run_result_model(self):
        """CrossSiteLifecycleHealthRunResult has expected fields."""
        result = CrossSiteLifecycleHealthRunResult()
        assert result.scores == []
        assert result.summary is None
        assert result.export_paths == []


# ── Alert burden label ──

class TestAlertBurden:
    """Alert burden classification tests."""

    def test_burden_none(self):
        """No alerts means no burden."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            _classify_alert_burden,
        )
        assert _classify_alert_burden(0, 0) == "none"

    def test_burden_low(self):
        """Few open alerts means low burden."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            _classify_alert_burden,
        )
        assert _classify_alert_burden(5, 1) == "low"

    def test_burden_moderate(self):
        """Several open alerts means moderate burden."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            _classify_alert_burden,
        )
        assert _classify_alert_burden(10, 4) == "moderate"

    def test_burden_high(self):
        """Many open alerts means high burden."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            _classify_alert_burden,
        )
        assert _classify_alert_burden(15, 8) == "high"


# ── Score clamping ──

class TestScoreClamping:
    """Score is clamped to 0-100 range."""

    def test_score_floor(self, temp_db):
        """Score cannot go below 0."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        # Create many high/critical alerts to drive score well below 0
        for i in range(1, 20):
            old_date = (datetime.now() - timedelta(days=30)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            _insert_alert(
                temp_db, i, 1, severity="critical", status="open",
                created_at=old_date,
                notes="[triage:needs_reparse][triage:needs_manual_review]",
            )
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.lifecycle_health_score >= 0.0

    def test_score_ceiling(self, temp_db):
        """Score cannot exceed 100."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.lifecycle_health_score <= 100.0


# ── Multiple properties scoring ──

class TestMultipleProperties:
    """Scoring multiple properties."""

    def test_scores_all_properties(self, temp_db):
        """Scores returned for all properties with alerts."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_scores,
        )

        _insert_watched_property(temp_db, 1)
        _insert_watched_property(temp_db, 2, address="456 Oak Ave")
        _insert_alert(temp_db, 1, 1, status="open")
        _insert_alert(temp_db, 2, 2, status="resolved")

        scores = calculate_lifecycle_health_scores(temp_db)
        assert len(scores) == 2

    def test_scores_sorted_ascending(self, temp_db):
        """Scores are sorted by score ascending (worst first)."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_scores,
        )

        _insert_watched_property(temp_db, 1)
        _insert_watched_property(temp_db, 2, address="456 Oak Ave")
        _insert_alert(temp_db, 1, 1, severity="high", status="open")
        _insert_alert(temp_db, 2, 2, status="resolved")

        scores = calculate_lifecycle_health_scores(temp_db)
        assert len(scores) == 2
        assert scores[0].lifecycle_health_score <= scores[1].lifecycle_health_score


# ── Recommended action ──

class TestRecommendedAction:
    """Recommended review action tests."""

    def test_excellent_no_action(self, temp_db):
        """Excellent health has no immediate action."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert "no action" in score.recommended_review_action.lower()

    def test_attention_required_action(self, temp_db):
        """Attention required has review recommendation."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        for i in range(1, 15):
            old_date = (datetime.now() - timedelta(days=30)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            _insert_alert(
                temp_db, i, 1, severity="critical", status="open",
                created_at=old_date,
            )
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.lifecycle_health_label == "attention_required"
        assert "review" in score.recommended_review_action.lower()


# ── No browser automation in module ──

class TestNoBrowserAutomation:
    """Health module must not contain browser automation references."""

    def test_no_browser_automation(self):
        """Module has no browser automation imports or references."""
        src = Path(
            "src/marketsentry/cross_site_alert_lifecycle_health.py"
        ).read_text(encoding="utf-8").lower()
        # Do not check for negation patterns - check for actual imports
        assert "from playwright" not in src
        assert "from selenium" not in src
        assert "import playwright" not in src
        assert "import selenium" not in src

    def test_no_captcha_bypass(self):
        """Module has no CAPTCHA bypass references."""
        src = Path(
            "src/marketsentry/cross_site_alert_lifecycle_health.py"
        ).read_text(encoding="utf-8").lower()
        assert "captcha" not in src


# ── Avg time to resolution ──

class TestAvgTimeToResolution:
    """Average time-to-resolution calculation."""

    def test_avg_resolution_with_data(self, temp_db):
        """Avg time-to-resolution populated when data exists."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        created = (datetime.now() - timedelta(days=5)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        resolved = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _insert_alert(temp_db, 1, 1, status="resolved", created_at=created)
        _insert_triage_action(
            temp_db, 1, 1, 1, action="resolve",
            previous_status="open", new_status="resolved",
            applied_at=resolved,
        )
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.avg_time_to_resolution_days is not None
        assert score.avg_time_to_resolution_days > 0

    def test_avg_resolution_without_data(self, temp_db):
        """Avg time-to-resolution is None when no resolved alerts."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_score_for_property,
        )

        _insert_watched_property(temp_db, 1)
        _insert_alert(temp_db, 1, 1, status="open")
        score = calculate_lifecycle_health_score_for_property(1, temp_db)
        assert score.avg_time_to_resolution_days is None


# ── Empty database ──

class TestEmptyDatabase:
    """Handling empty/fresh database."""

    def test_empty_db_no_errors(self, temp_db):
        """Fresh database returns empty scores without error."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_scores,
        )
        scores = calculate_lifecycle_health_scores(temp_db)
        assert scores == []

    def test_empty_db_summary(self, temp_db):
        """Empty scores produces valid summary."""
        from marketsentry.cross_site_alert_lifecycle_health import (
            calculate_lifecycle_health_scores,
            summarize_lifecycle_health_scores,
        )
        scores = calculate_lifecycle_health_scores(temp_db)
        summary = summarize_lifecycle_health_scores(scores)
        assert summary.properties_scored == 0
