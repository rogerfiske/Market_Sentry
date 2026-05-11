"""Tests for Milestone 29: Scheduled Triage Reminder and Alert Hygiene Reports.

Tests cover:
- Stale open alert detection
- Old acknowledged alert detection
- Old resolved alert archive candidate detection
- Needs_reparse pending detection
- Needs_manual_review pending detection
- High burden property detection
- Repeated unresolved pattern detection
- Hygiene summary counts
- Next actions generated
- CSV report export
- Markdown report export
- cross-site-alert-hygiene-check CLI
- export-cross-site-alert-hygiene-report CLI
- Scheduled hygiene batch script exists
- Scheduled hygiene script does not include live retrieval or --force-live
- Dashboard hygiene data loads
- No Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- No walkability fields added
- No real network calls
- Existing MVP 1-28 tests still pass (run with full suite)
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
    CrossSiteAlertHygieneConfig,
    CrossSiteAlertHygieneIssue,
    CrossSiteAlertHygieneReportRow,
    CrossSiteAlertHygieneRunResult,
    CrossSiteAlertHygieneSummary,
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


# ---------------------------------------------------------------------------
# Test: Stale open alert detection
# ---------------------------------------------------------------------------


class TestStaleOpenAlerts:
    """Test stale open alert identification."""

    def test_detects_stale_open_alert(self, temp_db):
        """Open alert older than stale_days should be flagged."""
        from marketsentry.cross_site_alert_hygiene import identify_stale_open_alerts

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        issues = identify_stale_open_alerts(temp_db, stale_days=7)
        assert len(issues) >= 1
        assert issues[0].category == "stale_open_alert"
        assert issues[0].alert_age_days >= 10

    def test_does_not_flag_recent_open_alert(self, temp_db):
        """Open alert newer than stale_days should not be flagged."""
        from marketsentry.cross_site_alert_hygiene import identify_stale_open_alerts

        pid = _insert_watched_property(temp_db)
        recent = (datetime.now() - timedelta(days=2)).isoformat()
        _insert_alert(temp_db, pid, created_at=recent)

        issues = identify_stale_open_alerts(temp_db, stale_days=7)
        assert len(issues) == 0

    def test_stale_open_severity_warning_under_14_days(self, temp_db):
        """Open alert 7-13 days old should have warning severity."""
        from marketsentry.cross_site_alert_hygiene import identify_stale_open_alerts

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        issues = identify_stale_open_alerts(temp_db, stale_days=7)
        assert issues[0].severity == "warning"

    def test_stale_open_severity_high_over_14_days(self, temp_db):
        """Open alert 14+ days old should have high severity."""
        from marketsentry.cross_site_alert_hygiene import identify_stale_open_alerts

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=20)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        issues = identify_stale_open_alerts(temp_db, stale_days=7)
        assert issues[0].severity == "high"

    def test_returns_empty_when_table_missing(self, temp_db):
        """Should return empty list if alerts table does not exist."""
        from marketsentry.cross_site_alert_hygiene import identify_stale_open_alerts

        # Use a fresh DB without alerts table
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            empty_db = f.name
        try:
            issues = identify_stale_open_alerts(empty_db, stale_days=7)
            assert issues == []
        finally:
            os.unlink(empty_db)


# ---------------------------------------------------------------------------
# Test: Old acknowledged alert detection
# ---------------------------------------------------------------------------


class TestOldAcknowledgedAlerts:
    """Test old acknowledged alert identification."""

    def test_detects_old_acknowledged_alert(self, temp_db):
        """Acknowledged alert older than stale_days should be flagged."""
        from marketsentry.cross_site_alert_hygiene import identify_old_acknowledged_alerts

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=20)).isoformat()
        _insert_alert(temp_db, pid, alert_status="acknowledged", created_at=old_date)

        issues = identify_old_acknowledged_alerts(temp_db, stale_days=14)
        assert len(issues) >= 1
        assert issues[0].category == "stale_acknowledged_alert"

    def test_does_not_flag_recent_acknowledged(self, temp_db):
        """Acknowledged alert newer than stale_days should not be flagged."""
        from marketsentry.cross_site_alert_hygiene import identify_old_acknowledged_alerts

        pid = _insert_watched_property(temp_db)
        recent = (datetime.now() - timedelta(days=5)).isoformat()
        _insert_alert(temp_db, pid, alert_status="acknowledged", created_at=recent)

        issues = identify_old_acknowledged_alerts(temp_db, stale_days=14)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Test: Old resolved alert archive candidate detection
# ---------------------------------------------------------------------------


class TestOldResolvedAlerts:
    """Test old resolved alert archive candidate identification."""

    def test_detects_resolved_archive_candidate(self, temp_db):
        """Resolved alert older than archive_days should be flagged."""
        from marketsentry.cross_site_alert_hygiene import identify_old_resolved_alerts

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=40)).isoformat()
        _insert_alert(temp_db, pid, alert_status="resolved", created_at=old_date)

        issues = identify_old_resolved_alerts(temp_db, archive_days=30)
        assert len(issues) >= 1
        assert issues[0].category == "resolved_archive_candidate"

    def test_does_not_flag_recent_resolved(self, temp_db):
        """Resolved alert newer than archive_days should not be flagged."""
        from marketsentry.cross_site_alert_hygiene import identify_old_resolved_alerts

        pid = _insert_watched_property(temp_db)
        recent = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, alert_status="resolved", created_at=recent)

        issues = identify_old_resolved_alerts(temp_db, archive_days=30)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Test: Needs_reparse pending detection
# ---------------------------------------------------------------------------


class TestNeedsReparseAlerts:
    """Test needs_reparse pending alert identification."""

    def test_detects_needs_reparse_pending(self, temp_db):
        """Alert with needs_reparse note and open status should be flagged."""
        from marketsentry.cross_site_alert_hygiene import identify_needs_reparse_alerts

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="open",
            created_at=old_date,
            notes="[triage:needs_reparse] fixture update needed",
        )

        issues = identify_needs_reparse_alerts(temp_db, stale_days=7)
        assert len(issues) >= 1
        assert issues[0].category == "needs_reparse_pending"

    def test_ignores_resolved_needs_reparse(self, temp_db):
        """Resolved alert with needs_reparse note should not be flagged."""
        from marketsentry.cross_site_alert_hygiene import identify_needs_reparse_alerts

        pid = _insert_watched_property(temp_db)
        _insert_alert(
            temp_db, pid, alert_status="resolved",
            notes="[triage:needs_reparse] done",
        )

        issues = identify_needs_reparse_alerts(temp_db)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Test: Needs_manual_review pending detection
# ---------------------------------------------------------------------------


class TestNeedsManualReviewAlerts:
    """Test needs_manual_review pending alert identification."""

    def test_detects_needs_manual_review_pending(self, temp_db):
        """Alert with needs_manual_review note and open status should be flagged."""
        from marketsentry.cross_site_alert_hygiene import (
            identify_needs_manual_review_alerts,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(
            temp_db, pid, alert_status="acknowledged",
            created_at=old_date,
            notes="[triage:needs_manual_review] check data",
        )

        issues = identify_needs_manual_review_alerts(temp_db, stale_days=7)
        assert len(issues) >= 1
        assert issues[0].category == "needs_manual_review_pending"

    def test_ignores_archived_needs_manual_review(self, temp_db):
        """Archived alert with needs_manual_review note should not be flagged."""
        from marketsentry.cross_site_alert_hygiene import (
            identify_needs_manual_review_alerts,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(
            temp_db, pid, alert_status="archived",
            notes="[triage:needs_manual_review]",
        )

        issues = identify_needs_manual_review_alerts(temp_db)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Test: High burden property detection
# ---------------------------------------------------------------------------


class TestHighBurdenProperties:
    """Test high burden property identification."""

    def test_detects_high_burden_property(self, temp_db):
        """Property with many open alerts should be flagged as high burden."""
        from marketsentry.cross_site_alert_hygiene import (
            identify_high_burden_properties,
        )

        pid = _insert_watched_property(temp_db)
        # Insert multiple open alerts to trigger high burden
        for i in range(5):
            _insert_alert(
                temp_db, pid,
                alert_type=f"type_{i}",
                severity="high" if i < 2 else "warning",
            )

        issues = identify_high_burden_properties(temp_db)
        # Should detect high burden due to multiple alerts
        assert len(issues) >= 1
        assert issues[0].category == "high_alert_burden_property"

    def test_no_issues_for_low_burden_property(self, temp_db):
        """Property with one low-severity open alert should not be flagged."""
        from marketsentry.cross_site_alert_hygiene import (
            identify_high_burden_properties,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, severity="info")

        issues = identify_high_burden_properties(temp_db)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Test: Repeated unresolved pattern detection
# ---------------------------------------------------------------------------


class TestRepeatedUnresolvedPatterns:
    """Test repeated unresolved pattern identification."""

    def test_detects_repeated_unresolved_pattern(self, temp_db):
        """Multiple open alerts of same type should flag repeated pattern."""
        from marketsentry.cross_site_alert_hygiene import (
            identify_repeated_unresolved_patterns,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_type="confidence_drop")
        _insert_alert(temp_db, pid, alert_type="confidence_drop")

        issues = identify_repeated_unresolved_patterns(temp_db, threshold=2)
        assert len(issues) >= 1
        assert issues[0].category == "repeated_unresolved_pattern"
        assert issues[0].repeated_pattern == "confidence_drop"

    def test_does_not_flag_unique_types(self, temp_db):
        """Single alert per type should not flag repeated pattern."""
        from marketsentry.cross_site_alert_hygiene import (
            identify_repeated_unresolved_patterns,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid, alert_type="confidence_drop")
        _insert_alert(temp_db, pid, alert_type="price_mismatch")

        issues = identify_repeated_unresolved_patterns(temp_db, threshold=2)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Test: Hygiene summary counts
# ---------------------------------------------------------------------------


class TestHygieneSummary:
    """Test hygiene check summary counts."""

    def test_summary_counts_correct(self, temp_db):
        """Run result should have correct summary counts."""
        from marketsentry.cross_site_alert_hygiene import (
            run_cross_site_alert_hygiene_check,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()

        # Stale open alert
        _insert_alert(temp_db, pid, alert_status="open", created_at=old_date)

        # Old acknowledged alert
        ack_date = (datetime.now() - timedelta(days=20)).isoformat()
        _insert_alert(temp_db, pid, alert_status="acknowledged", created_at=ack_date)

        # Old resolved alert
        resolved_date = (datetime.now() - timedelta(days=35)).isoformat()
        _insert_alert(temp_db, pid, alert_status="resolved", created_at=resolved_date)

        result = run_cross_site_alert_hygiene_check(database_path=temp_db)

        assert result.summary.stale_open_alerts >= 1
        assert result.summary.stale_acknowledged_alerts >= 1
        assert result.summary.resolved_archive_candidates >= 1
        assert result.summary.total_issues >= 3

    def test_summary_with_no_alerts(self, temp_db):
        """Summary should be zero when no alerts exist."""
        from marketsentry.cross_site_alert_hygiene import (
            run_cross_site_alert_hygiene_check,
        )

        result = run_cross_site_alert_hygiene_check(database_path=temp_db)
        assert result.summary.total_issues == 0

    def test_issues_have_sequential_ids(self, temp_db):
        """Issues should have sequential IDs starting at 1."""
        from marketsentry.cross_site_alert_hygiene import (
            run_cross_site_alert_hygiene_check,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)
        _insert_alert(temp_db, pid, created_at=old_date)

        result = run_cross_site_alert_hygiene_check(database_path=temp_db)
        if result.issues:
            ids = [i.issue_id for i in result.issues]
            assert ids[0] == 1
            for i in range(1, len(ids)):
                assert ids[i] == ids[i - 1] + 1


# ---------------------------------------------------------------------------
# Test: Next actions generated
# ---------------------------------------------------------------------------


class TestNextActions:
    """Test next action generation."""

    def test_next_actions_for_stale_open(self, temp_db):
        """Should generate next action for stale open alerts."""
        from marketsentry.cross_site_alert_hygiene import (
            generate_alert_hygiene_next_actions,
        )

        summary = CrossSiteAlertHygieneSummary(stale_open_alerts=3)
        actions = generate_alert_hygiene_next_actions(summary)
        assert any("stale open" in a.lower() for a in actions)

    def test_next_actions_healthy(self):
        """Should report healthy when no issues."""
        from marketsentry.cross_site_alert_hygiene import (
            generate_alert_hygiene_next_actions,
        )

        summary = CrossSiteAlertHygieneSummary()
        actions = generate_alert_hygiene_next_actions(summary)
        assert any("healthy" in a.lower() or "no hygiene" in a.lower() for a in actions)

    def test_next_actions_for_all_categories(self):
        """Should generate actions for all non-zero categories."""
        from marketsentry.cross_site_alert_hygiene import (
            generate_alert_hygiene_next_actions,
        )

        summary = CrossSiteAlertHygieneSummary(
            stale_open_alerts=1,
            stale_acknowledged_alerts=1,
            resolved_archive_candidates=1,
            needs_reparse_pending=1,
            needs_manual_review_pending=1,
            high_burden_properties=1,
            repeated_unresolved_patterns=1,
        )
        actions = generate_alert_hygiene_next_actions(summary)
        assert len(actions) >= 7


# ---------------------------------------------------------------------------
# Test: CSV report export
# ---------------------------------------------------------------------------


class TestCSVReportExport:
    """Test CSV report export."""

    def test_csv_report_created(self, temp_db, temp_exports_dir):
        """CSV export should create a file."""
        from marketsentry.cross_site_alert_hygiene import (
            export_cross_site_alert_hygiene_report,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        result = export_cross_site_alert_hygiene_report(
            database_path=temp_db,
            exports_dir=temp_exports_dir,
            report_format="csv",
        )

        assert result.csv_path is not None
        assert Path(result.csv_path).exists()

    def test_csv_report_has_required_columns(self, temp_db, temp_exports_dir):
        """CSV should contain all required columns."""
        from marketsentry.cross_site_alert_hygiene import (
            HYGIENE_CSV_FIELDNAMES,
            export_cross_site_alert_hygiene_report,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        result = export_cross_site_alert_hygiene_report(
            database_path=temp_db,
            exports_dir=temp_exports_dir,
            report_format="csv",
        )

        with open(result.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert set(HYGIENE_CSV_FIELDNAMES).issubset(set(reader.fieldnames))

    def test_csv_report_row_count(self, temp_db, temp_exports_dir):
        """CSV should have correct number of data rows."""
        from marketsentry.cross_site_alert_hygiene import (
            export_cross_site_alert_hygiene_report,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        result = export_cross_site_alert_hygiene_report(
            database_path=temp_db,
            exports_dir=temp_exports_dir,
            report_format="csv",
        )

        with open(result.csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # Header + data rows
        assert len(rows) >= 2

    def test_empty_report_when_no_issues(self, temp_db, temp_exports_dir):
        """CSV should be created even when no issues found."""
        from marketsentry.cross_site_alert_hygiene import (
            export_cross_site_alert_hygiene_report,
        )

        result = export_cross_site_alert_hygiene_report(
            database_path=temp_db,
            exports_dir=temp_exports_dir,
            report_format="csv",
        )

        assert result.csv_path is not None
        assert Path(result.csv_path).exists()
        assert result.summary.total_issues == 0


# ---------------------------------------------------------------------------
# Test: Markdown report export
# ---------------------------------------------------------------------------


class TestMarkdownReportExport:
    """Test Markdown report export."""

    def test_markdown_report_created(self, temp_db, temp_exports_dir):
        """Markdown export should create a file."""
        from marketsentry.cross_site_alert_hygiene import (
            export_cross_site_alert_hygiene_report,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        result = export_cross_site_alert_hygiene_report(
            database_path=temp_db,
            exports_dir=temp_exports_dir,
            report_format="md",
        )

        assert result.md_path is not None
        assert Path(result.md_path).exists()

    def test_markdown_report_contains_sections(self, temp_db, temp_exports_dir):
        """Markdown report should include summary and next actions."""
        from marketsentry.cross_site_alert_hygiene import (
            export_cross_site_alert_hygiene_report,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        result = export_cross_site_alert_hygiene_report(
            database_path=temp_db,
            exports_dir=temp_exports_dir,
            report_format="md",
        )

        content = Path(result.md_path).read_text(encoding="utf-8")
        assert "## Summary" in content
        assert "## Recommended Next Actions" in content

    def test_both_format_creates_csv_and_md(self, temp_db, temp_exports_dir):
        """Format 'both' should create CSV and Markdown files."""
        from marketsentry.cross_site_alert_hygiene import (
            export_cross_site_alert_hygiene_report,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        result = export_cross_site_alert_hygiene_report(
            database_path=temp_db,
            exports_dir=temp_exports_dir,
            report_format="both",
        )

        assert result.csv_path is not None
        assert result.md_path is not None
        assert Path(result.csv_path).exists()
        assert Path(result.md_path).exists()


# ---------------------------------------------------------------------------
# Test: Configurable thresholds
# ---------------------------------------------------------------------------


class TestConfigurableThresholds:
    """Test configurable hygiene thresholds."""

    def test_custom_open_stale_days(self, temp_db):
        """Custom open_stale_days should change detection threshold."""
        from marketsentry.cross_site_alert_hygiene import (
            run_cross_site_alert_hygiene_check,
        )

        pid = _insert_watched_property(temp_db)
        # 5 days old
        old_date = (datetime.now() - timedelta(days=5)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        # Default 7 days: should not flag
        result_default = run_cross_site_alert_hygiene_check(database_path=temp_db)
        stale_default = result_default.summary.stale_open_alerts

        # Custom 3 days: should flag
        cfg = CrossSiteAlertHygieneConfig(open_stale_days=3)
        result_custom = run_cross_site_alert_hygiene_check(
            database_path=temp_db, config=cfg,
        )
        stale_custom = result_custom.summary.stale_open_alerts

        assert stale_custom > stale_default

    def test_default_config_values(self):
        """Default config should have expected threshold values."""
        cfg = CrossSiteAlertHygieneConfig()
        assert cfg.open_stale_days == 7
        assert cfg.acknowledged_stale_days == 14
        assert cfg.resolved_archive_days == 30
        assert cfg.needs_reparse_stale_days == 7
        assert cfg.needs_manual_review_stale_days == 7
        assert "high" in cfg.high_burden_labels
        assert "elevated_review" in cfg.high_burden_labels
        assert cfg.repeated_unresolved_threshold == 2


# ---------------------------------------------------------------------------
# Test: CLI cross-site-alert-hygiene-check
# ---------------------------------------------------------------------------


class TestCLIHygieneCheck:
    """Test cross-site-alert-hygiene-check CLI command."""

    def test_cli_hygiene_check_runs(self, temp_db, temp_exports_dir):
        """CLI command should run without errors."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "cross-site-alert-hygiene-check",
                "--db", temp_db,
                "--format", "both",
            ],
        )

        assert result.exit_code == 0
        assert "SUCCESS" in result.output

    def test_cli_hygiene_check_shows_counts(self, temp_db):
        """CLI command should show issue counts."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["cross-site-alert-hygiene-check", "--db", temp_db],
        )

        assert result.exit_code == 0
        assert "Stale open alerts" in result.output


# ---------------------------------------------------------------------------
# Test: CLI export-cross-site-alert-hygiene-report
# ---------------------------------------------------------------------------


class TestCLIExportHygieneReport:
    """Test export-cross-site-alert-hygiene-report CLI command."""

    def test_cli_export_runs(self, temp_db, temp_exports_dir):
        """CLI export command should run without errors."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "export-cross-site-alert-hygiene-report",
                "--db", temp_db,
                "--format", "csv",
            ],
        )

        assert result.exit_code == 0
        assert "SUCCESS" in result.output

    def test_cli_export_shows_issue_count(self, temp_db):
        """CLI export should show issue count."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "export-cross-site-alert-hygiene-report",
                "--db", temp_db,
            ],
        )

        assert result.exit_code == 0
        assert "Issues found" in result.output


# ---------------------------------------------------------------------------
# Test: Scheduled hygiene batch script exists
# ---------------------------------------------------------------------------


class TestScheduledScript:
    """Test scheduled alert hygiene batch script."""

    def test_batch_script_exists(self):
        """run_alert_hygiene_report.bat should exist in scripts/."""
        script = Path("scripts/run_alert_hygiene_report.bat")
        assert script.exists(), f"Expected batch script at {script}"

    def test_batch_script_does_not_include_live_retrieval(self):
        """Batch script must not contain live retrieval commands."""
        script = Path("scripts/run_alert_hygiene_report.bat")
        content = script.read_text(encoding="utf-8")

        assert "--force-live" not in content
        assert "run-approved-retrieval" not in content.lower()
        assert "run-live-retrieval" not in content.lower()
        assert "force-live" not in content
        assert "playwright" not in content.lower()
        assert "selenium" not in content.lower()

    def test_batch_script_runs_hygiene_command(self):
        """Batch script should invoke the hygiene check command."""
        script = Path("scripts/run_alert_hygiene_report.bat")
        content = script.read_text(encoding="utf-8")

        assert "cross-site-alert-hygiene-check" in content

    def test_batch_script_logs_to_scheduled(self):
        """Batch script should log to logs/scheduled/."""
        script = Path("scripts/run_alert_hygiene_report.bat")
        content = script.read_text(encoding="utf-8")

        assert "logs\\scheduled" in content or "logs/scheduled" in content

    def test_expected_scripts_includes_hygiene(self):
        """EXPECTED_SCRIPTS should include the hygiene batch script."""
        from marketsentry.automation import EXPECTED_SCRIPTS

        assert "run_alert_hygiene_report.bat" in EXPECTED_SCRIPTS


# ---------------------------------------------------------------------------
# Test: Dashboard hygiene data loads
# ---------------------------------------------------------------------------


class TestDashboardHygiene:
    """Test dashboard alert hygiene integration."""

    def test_build_hygiene_table_with_csv(self, temp_db, temp_exports_dir):
        """Dashboard should load hygiene data from CSV."""
        from marketsentry.cross_site_alert_hygiene import (
            export_cross_site_alert_hygiene_report,
        )
        from marketsentry.dashboard import build_cross_site_alert_hygiene_table

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        export_cross_site_alert_hygiene_report(
            database_path=temp_db,
            exports_dir=temp_exports_dir,
            report_format="csv",
        )

        df = build_cross_site_alert_hygiene_table(temp_exports_dir)
        assert not df.empty
        assert "category" in df.columns
        assert "severity" in df.columns

    def test_build_hygiene_table_empty_when_no_report(self, temp_exports_dir):
        """Dashboard should return empty DataFrame when no report exists."""
        from marketsentry.dashboard import build_cross_site_alert_hygiene_table

        df = build_cross_site_alert_hygiene_table(temp_exports_dir)
        assert df.empty

    def test_hygiene_table_imported_in_dashboard_app(self):
        """Dashboard app should import the hygiene table builder."""
        from marketsentry.dashboard_app import build_cross_site_alert_hygiene_table

        assert callable(build_cross_site_alert_hygiene_table)


# ---------------------------------------------------------------------------
# Test: No Redfin source-of-truth overwrite
# ---------------------------------------------------------------------------


class TestNoRedfnOverwrite:
    """Test hygiene does not overwrite Redfin source-of-truth."""

    def test_hygiene_does_not_modify_watched_properties(self, temp_db):
        """Hygiene check should not modify watched_properties table."""
        from marketsentry.cross_site_alert_hygiene import (
            run_cross_site_alert_hygiene_check,
        )

        pid = _insert_watched_property(temp_db, address="99 Source St")
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        # Record state before
        before = execute_query(
            "SELECT * FROM watched_properties WHERE property_id = ?",
            (pid,),
            database_path=temp_db,
        )

        run_cross_site_alert_hygiene_check(database_path=temp_db)

        # State after should be identical
        after = execute_query(
            "SELECT * FROM watched_properties WHERE property_id = ?",
            (pid,),
            database_path=temp_db,
        )

        assert dict(before[0]) == dict(after[0])

    def test_hygiene_does_not_modify_alert_status(self, temp_db):
        """Hygiene check should not change alert statuses."""
        from marketsentry.cross_site_alert_hygiene import (
            run_cross_site_alert_hygiene_check,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        aid = _insert_alert(temp_db, pid, created_at=old_date)

        run_cross_site_alert_hygiene_check(database_path=temp_db)

        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts WHERE alert_id = ?",
            (aid,),
            database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "open"


# ---------------------------------------------------------------------------
# Test: Quiet gatekeeper remains unchanged
# ---------------------------------------------------------------------------


class TestQuietGatekeeperUnchanged:
    """Test that Quiet Score gatekeeper is not modified."""

    def test_hygiene_module_does_not_import_quiet_score(self):
        """Hygiene module should not import quiet score functions."""
        import inspect
        import marketsentry.cross_site_alert_hygiene as mod

        source = inspect.getsource(mod)
        assert "quiet_score" not in source.lower()
        assert "vibrancy" not in source.lower()

    def test_hygiene_check_does_not_change_quiet_score(self, temp_db):
        """Running hygiene check should not change any quiet score data."""
        from marketsentry.cross_site_alert_hygiene import (
            run_cross_site_alert_hygiene_check,
        )

        pid = _insert_watched_property(temp_db)
        _insert_alert(temp_db, pid)

        # Get quiet gatekeeper state if table exists
        before_gk = None
        if table_exists("quiet_gatekeeper_results", temp_db):
            before_gk = execute_query(
                "SELECT * FROM quiet_gatekeeper_results",
                database_path=temp_db,
            )

        run_cross_site_alert_hygiene_check(database_path=temp_db)

        if table_exists("quiet_gatekeeper_results", temp_db):
            after_gk = execute_query(
                "SELECT * FROM quiet_gatekeeper_results",
                database_path=temp_db,
            )
            assert before_gk == after_gk


# ---------------------------------------------------------------------------
# Test: No walkability fields added
# ---------------------------------------------------------------------------


class TestNoWalkabilityFields:
    """Test that no walkability fields were added."""

    def test_hygiene_module_no_walkability(self):
        """Hygiene module should not reference walkability."""
        import inspect
        import marketsentry.cross_site_alert_hygiene as mod

        source = inspect.getsource(mod)
        assert "walkability" not in source.lower()
        assert "walk_score" not in source.lower()

    def test_hygiene_models_no_walkability(self):
        """Hygiene models should not contain walkability fields."""
        issue = CrossSiteAlertHygieneIssue()
        summary = CrossSiteAlertHygieneSummary()
        config = CrossSiteAlertHygieneConfig()
        row = CrossSiteAlertHygieneReportRow()
        result = CrossSiteAlertHygieneRunResult()

        for obj in [issue, summary, config, row, result]:
            fields = obj.model_fields.keys()
            for field in fields:
                assert "walk" not in field.lower()


# ---------------------------------------------------------------------------
# Test: No real network calls
# ---------------------------------------------------------------------------


class TestNoNetworkCalls:
    """Test that no network calls are performed."""

    def test_hygiene_module_no_network_imports(self):
        """Hygiene module should not import network libraries."""
        import inspect
        import marketsentry.cross_site_alert_hygiene as mod

        source = inspect.getsource(mod)
        assert "import requests" not in source
        assert "import httpx" not in source
        assert "import urllib" not in source
        assert "import aiohttp" not in source
        assert "playwright" not in source.lower()
        assert "selenium" not in source.lower()

    def test_hygiene_check_no_socket_calls(self, temp_db):
        """Running hygiene check should not open network connections."""
        from marketsentry.cross_site_alert_hygiene import (
            run_cross_site_alert_hygiene_check,
        )

        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _insert_alert(temp_db, pid, created_at=old_date)

        with patch("socket.socket") as mock_socket:
            run_cross_site_alert_hygiene_check(database_path=temp_db)
            mock_socket.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Models
# ---------------------------------------------------------------------------


class TestModels:
    """Test hygiene models."""

    def test_hygiene_issue_default_values(self):
        """HygieneIssue should have expected default values."""
        issue = CrossSiteAlertHygieneIssue()
        assert issue.issue_id == 0
        assert issue.category == ""
        assert issue.severity == "info"

    def test_hygiene_summary_default_values(self):
        """HygieneSummary should have expected default values."""
        summary = CrossSiteAlertHygieneSummary()
        assert summary.total_issues == 0
        assert summary.stale_open_alerts == 0
        assert summary.issues_by_severity == {}

    def test_hygiene_run_result_default_values(self):
        """HygieneRunResult should have expected default values."""
        result = CrossSiteAlertHygieneRunResult()
        assert result.issues == []
        assert result.csv_path is None
        assert result.md_path is None
        assert result.warnings == []
        assert result.errors == []

    def test_hygiene_report_row_fields(self):
        """HygieneReportRow should have 15 expected fields."""
        row = CrossSiteAlertHygieneReportRow()
        assert len(row.model_fields) == 15

    def test_hygiene_config_override(self):
        """Config should accept custom values."""
        cfg = CrossSiteAlertHygieneConfig(
            open_stale_days=3,
            acknowledged_stale_days=7,
            resolved_archive_days=14,
        )
        assert cfg.open_stale_days == 3
        assert cfg.acknowledged_stale_days == 7
        assert cfg.resolved_archive_days == 14


# ---------------------------------------------------------------------------
# Test: Constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Test module constants."""

    def test_csv_fieldnames_count(self):
        """HYGIENE_CSV_FIELDNAMES should have 15 columns."""
        from marketsentry.cross_site_alert_hygiene import HYGIENE_CSV_FIELDNAMES

        assert len(HYGIENE_CSV_FIELDNAMES) == 15

    def test_csv_fieldnames_match_report_row(self):
        """HYGIENE_CSV_FIELDNAMES should match CrossSiteAlertHygieneReportRow fields."""
        from marketsentry.cross_site_alert_hygiene import HYGIENE_CSV_FIELDNAMES

        row = CrossSiteAlertHygieneReportRow()
        model_fields = set(row.model_fields.keys())
        csv_fields = set(HYGIENE_CSV_FIELDNAMES)
        assert csv_fields == model_fields
