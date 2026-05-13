"""Milestone 43 tests: Portfolio Trend Threshold Alerts and Notification Digest.

Tests cover default rules, aggregate burden alerts, property degradation
alerts, alert summary, CSV/MD digest export, CLI commands, dashboard,
scheduled script safety, no outbound notifications, and guard-rail
constraints.
"""

import csv
import os
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_pack_csv(dir_path, filename, rows):
    """Write a portfolio review pack CSV file with standard headers."""
    from marketsentry.portfolio_review_pack import REVIEW_CSV_FIELDNAMES

    path = os.path.join(dir_path, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            full_row = {fn: "" for fn in REVIEW_CSV_FIELDNAMES}
            full_row.update(row)
            writer.writerow(full_row)
    return path


def _base_row(**overrides):
    """Create a base row dict with sensible defaults."""
    row = {
        "property_id": "1",
        "address": "123 Main St",
        "city": "Temecula",
        "zip": "92592",
        "current_price": "625000",
        "beds": "4",
        "baths": "2.5",
        "sqft": "2100",
        "watch_priority_label": "normal",
        "active_watch_status": "True",
        "quiet_score": "82.5",
        "quiet_gatekeeper_result": "pass",
        "vibrancy_score": "15.0",
        "gas_evidence": "",
        "garage_spaces": "2",
        "effective_dom_v1": "180",
        "effective_dom_v2": "45",
        "effective_dom_delta": "135",
        "county_reset_applied": "True",
        "recent_churn_index": "2.1",
        "listing_churn_count": "3",
        "dom_reset_count": "2",
        "sale_rent_alternation_count": "0",
        "cross_site_confidence_score": "78.5",
        "discrepancy_severity_label": "moderate",
        "open_alert_count": "3",
        "high_critical_alert_count": "1",
        "alert_burden_label": "moderate",
        "lifecycle_health_score": "65.0",
        "lifecycle_health_label": "needs_review",
        "lifecycle_gap_count": "2",
        "review_priority_label": "normal_review",
        "review_priority_score": "15",
        "recommended_review_action": "Review alerts",
        "redfin_url": "https://www.redfin.com/CA/Temecula/123-Main-St",
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# Default rules tests
# ---------------------------------------------------------------------------

class TestDefaultRules:
    """Tests for default alert rules."""

    def test_default_rules_load(self):
        """Default alert rules load successfully."""
        from marketsentry.portfolio_trend_alerts import (
            get_default_portfolio_trend_alert_rules,
        )
        rules = get_default_portfolio_trend_alert_rules()
        assert len(rules) > 0
        # All rules should have rule_id
        for r in rules:
            assert r.rule_id
            assert r.alert_scope in ("portfolio", "property")
            assert r.severity in ("info", "warning", "high")

    def test_rules_cover_portfolio_and_property(self):
        """Rules include both portfolio and property scopes."""
        from marketsentry.portfolio_trend_alerts import (
            get_default_portfolio_trend_alert_rules,
        )
        rules = get_default_portfolio_trend_alert_rules()
        scopes = {r.alert_scope for r in rules}
        assert "portfolio" in scopes
        assert "property" in scopes


# ---------------------------------------------------------------------------
# No data test
# ---------------------------------------------------------------------------

class TestNoData:
    """Tests for no pack data scenario."""

    def test_no_pack_data_produces_info_alert(self):
        """Missing pack data triggers an info alert."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_portfolio_trend_alerts,
        )
        with tempfile.TemporaryDirectory() as td:
            digest = evaluate_portfolio_trend_alerts(td)
            assert len(digest.alerts) == 1
            assert digest.alerts[0].severity == "info"
            assert digest.alerts[0].alert_type == "no_data"


# ---------------------------------------------------------------------------
# Aggregate burden alert tests
# ---------------------------------------------------------------------------

class TestAggregateBurdenAlerts:
    """Tests for aggregate burden threshold alerts."""

    def test_aggregate_burden_high_threshold(self):
        """Burden score >= 80 triggers high alert."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_portfolio_trend_alerts,
        )
        with tempfile.TemporaryDirectory() as td:
            # Create pack with many high-burden properties
            rows = []
            for i in range(1, 8):
                rows.append(_base_row(
                    property_id=str(i),
                    review_priority_label="immediate_review",
                    lifecycle_health_label="attention_required",
                    open_alert_count="5",
                    high_critical_alert_count="3",
                    quiet_gatekeeper_result="fail",
                    recent_churn_index="5.0",
                    effective_dom_delta="100",
                ))
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260501_100000.csv",
                rows,
            )
            digest = evaluate_portfolio_trend_alerts(td)
            high_alerts = [
                a for a in digest.alerts
                if a.alert_type == "aggregate_burden_high"
            ]
            assert len(high_alerts) == 1
            assert high_alerts[0].severity == "high"

    def test_aggregate_burden_warning_threshold(self):
        """Burden score >= 60 but < 80 triggers warning alert."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_aggregate_burden_alerts,
        )
        from marketsentry.portfolio_review_trends import (
            PortfolioReviewTrendPoint,
        )
        point = PortfolioReviewTrendPoint(
            aggregate_review_burden_score=65,
            pack_file="test.csv",
        )
        alerts = evaluate_aggregate_burden_alerts(
            [point], "2026-05-13 10:00:00"
        )
        burden_alerts = [
            a for a in alerts
            if a.alert_type == "aggregate_burden_warning"
        ]
        assert len(burden_alerts) == 1
        assert burden_alerts[0].severity == "warning"

    def test_aggregate_burden_increase_alert(self):
        """Burden increase >= 15 triggers warning alert."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_aggregate_burden_alerts,
        )
        from marketsentry.portfolio_review_trends import (
            PortfolioReviewTrendPoint,
        )
        prev = PortfolioReviewTrendPoint(
            aggregate_review_burden_score=30,
            pack_file="prev.csv",
        )
        curr = PortfolioReviewTrendPoint(
            aggregate_review_burden_score=50,
            pack_file="curr.csv",
        )
        alerts = evaluate_aggregate_burden_alerts(
            [prev, curr], "2026-05-13 10:00:00"
        )
        increase_alerts = [
            a for a in alerts
            if a.alert_type == "aggregate_burden_increase"
        ]
        assert len(increase_alerts) == 1
        assert increase_alerts[0].severity == "warning"
        assert "20" in increase_alerts[0].delta_value

    def test_burden_label_worsening_alert(self):
        """Burden label change to elevated/high triggers alert."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_aggregate_burden_alerts,
        )
        from marketsentry.portfolio_review_trends import (
            PortfolioReviewTrendPoint,
        )
        prev = PortfolioReviewTrendPoint(
            aggregate_review_burden_score=40,
            aggregate_review_status_label="moderate_burden",
            pack_file="prev.csv",
        )
        curr = PortfolioReviewTrendPoint(
            aggregate_review_burden_score=50,
            aggregate_review_status_label="elevated_burden",
            pack_file="curr.csv",
        )
        alerts = evaluate_aggregate_burden_alerts(
            [prev, curr], "2026-05-13 10:00:00"
        )
        label_alerts = [
            a for a in alerts
            if a.alert_type == "burden_label_worsening"
        ]
        assert len(label_alerts) == 1

    def test_immediate_review_increase_alert(self):
        """Rising immediate review count triggers warning."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_aggregate_burden_alerts,
        )
        from marketsentry.portfolio_review_trends import (
            PortfolioReviewTrendPoint,
        )
        prev = PortfolioReviewTrendPoint(
            immediate_review_count=1,
            pack_file="prev.csv",
        )
        curr = PortfolioReviewTrendPoint(
            immediate_review_count=3,
            pack_file="curr.csv",
        )
        alerts = evaluate_aggregate_burden_alerts(
            [prev, curr], "2026-05-13 10:00:00"
        )
        backlog_alerts = [
            a for a in alerts
            if a.alert_type == "backlog_immediate_increase"
        ]
        assert len(backlog_alerts) == 1
        assert backlog_alerts[0].severity == "warning"

    def test_high_critical_alert_increase(self):
        """Rising high/critical alert total triggers high alert."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_aggregate_burden_alerts,
        )
        from marketsentry.portfolio_review_trends import (
            PortfolioReviewTrendPoint,
        )
        prev = PortfolioReviewTrendPoint(
            high_critical_alert_total=2,
            pack_file="prev.csv",
        )
        curr = PortfolioReviewTrendPoint(
            high_critical_alert_total=4,
            pack_file="curr.csv",
        )
        alerts = evaluate_aggregate_burden_alerts(
            [prev, curr], "2026-05-13 10:00:00"
        )
        hca_alerts = [
            a for a in alerts
            if a.alert_type == "high_critical_alert_increase"
        ]
        assert len(hca_alerts) == 1
        assert hca_alerts[0].severity == "high"


# ---------------------------------------------------------------------------
# Property trend alert tests
# ---------------------------------------------------------------------------

class TestPropertyAlerts:
    """Tests for property-level trend alerts."""

    def test_degraded_property_trend_alert(self):
        """Degraded property trend triggers warning."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_property_trend_alerts,
        )
        from marketsentry.portfolio_review_trends import (
            PortfolioReviewPropertyTrendPoint,
        )
        pt = PortfolioReviewPropertyTrendPoint(
            property_id=1,
            address="123 Main St",
            trend_direction="degraded",
            trend_summary="Health dropped",
        )
        alerts = evaluate_property_trend_alerts(
            [pt], "2026-05-13 10:00:00"
        )
        degraded = [
            a for a in alerts
            if a.alert_type == "property_trend_degraded"
        ]
        assert len(degraded) == 1
        assert degraded[0].severity == "warning"

    def test_lifecycle_health_score_drop_alert(self):
        """Health score drop >= 15 triggers warning."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_property_trend_alerts,
        )
        from marketsentry.portfolio_review_trends import (
            PortfolioReviewPropertyTrendPoint,
        )
        pt = PortfolioReviewPropertyTrendPoint(
            property_id=1,
            address="456 Oak Ave",
            lifecycle_health_score_delta_first_to_latest=-20.0,
            latest_lifecycle_health_score=45.0,
        )
        alerts = evaluate_property_trend_alerts(
            [pt], "2026-05-13 10:00:00"
        )
        health_drop = [
            a for a in alerts
            if a.alert_type == "lifecycle_health_drop"
        ]
        assert len(health_drop) == 1
        assert health_drop[0].severity == "warning"

    def test_lifecycle_label_attention_required_alert(self):
        """Label changing to attention_required triggers high."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_property_trend_alerts,
        )
        from marketsentry.portfolio_review_trends import (
            PortfolioReviewPropertyTrendPoint,
        )
        pt = PortfolioReviewPropertyTrendPoint(
            property_id=1,
            address="789 Pine Ln",
            latest_lifecycle_health_label="attention_required",
            lifecycle_health_label_changes=1,
        )
        alerts = evaluate_property_trend_alerts(
            [pt], "2026-05-13 10:00:00"
        )
        label_alerts = [
            a for a in alerts
            if a.alert_type == "lifecycle_label_worsening"
        ]
        assert len(label_alerts) == 1
        assert label_alerts[0].severity == "high"

    def test_open_alert_count_increase_alert(self):
        """Open alert count increase >= 2 triggers warning."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_property_trend_alerts,
        )
        from marketsentry.portfolio_review_trends import (
            PortfolioReviewPropertyTrendPoint,
        )
        pt = PortfolioReviewPropertyTrendPoint(
            property_id=1,
            address="101 Elm Ct",
            open_alert_delta_first_to_latest=3,
            latest_open_alert_count=6,
        )
        alerts = evaluate_property_trend_alerts(
            [pt], "2026-05-13 10:00:00"
        )
        alert_inc = [
            a for a in alerts
            if a.alert_type == "open_alert_increase"
        ]
        assert len(alert_inc) == 1
        assert alert_inc[0].severity == "warning"

    def test_cross_site_confidence_drop_alert(self):
        """Cross-site confidence drop >= 15 triggers warning."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_property_trend_alerts,
        )
        from marketsentry.portfolio_review_trends import (
            PortfolioReviewPropertyTrendPoint,
        )
        pt = PortfolioReviewPropertyTrendPoint(
            property_id=1,
            address="202 Cedar Dr",
            cross_site_confidence_delta_first_to_latest=-20.0,
            latest_cross_site_confidence=55.0,
        )
        alerts = evaluate_property_trend_alerts(
            [pt], "2026-05-13 10:00:00"
        )
        conf_drop = [
            a for a in alerts
            if a.alert_type == "cross_site_confidence_drop"
        ]
        assert len(conf_drop) == 1
        assert conf_drop[0].severity == "warning"

    def test_churn_increase_alert(self):
        """Churn Index increase >= 1.5 triggers warning."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_property_trend_alerts,
        )
        from marketsentry.portfolio_review_trends import (
            PortfolioReviewPropertyTrendPoint,
        )
        pt = PortfolioReviewPropertyTrendPoint(
            property_id=1,
            address="303 Birch Way",
            churn_index_delta_first_to_latest=2.0,
            latest_recent_churn_index=4.5,
        )
        alerts = evaluate_property_trend_alerts(
            [pt], "2026-05-13 10:00:00"
        )
        churn_alerts = [
            a for a in alerts
            if a.alert_type == "churn_index_increase"
        ]
        assert len(churn_alerts) == 1
        assert churn_alerts[0].severity == "warning"

    def test_effective_dom_v2_increase_alert(self):
        """Effective DOM v2 increase >= 30 triggers info."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_property_trend_alerts,
        )
        from marketsentry.portfolio_review_trends import (
            PortfolioReviewPropertyTrendPoint,
        )
        pt = PortfolioReviewPropertyTrendPoint(
            property_id=1,
            address="404 Maple St",
            effective_dom_v2_delta_first_to_latest=35,
            latest_effective_dom_v2=80,
        )
        alerts = evaluate_property_trend_alerts(
            [pt], "2026-05-13 10:00:00"
        )
        dom_alerts = [
            a for a in alerts
            if a.alert_type == "effective_dom_v2_increase"
        ]
        assert len(dom_alerts) == 1
        assert dom_alerts[0].severity == "info"


# ---------------------------------------------------------------------------
# Summary tests
# ---------------------------------------------------------------------------

class TestSummary:
    """Tests for alert summary."""

    def test_summarize_alerts_by_severity(self):
        """Summary counts alerts by severity."""
        from marketsentry.portfolio_trend_alerts import (
            summarize_portfolio_trend_alerts,
            PortfolioTrendAlert,
        )
        alerts = [
            PortfolioTrendAlert(severity="high"),
            PortfolioTrendAlert(severity="high"),
            PortfolioTrendAlert(severity="warning"),
            PortfolioTrendAlert(severity="warning"),
            PortfolioTrendAlert(severity="warning"),
            PortfolioTrendAlert(severity="info"),
        ]
        summary = summarize_portfolio_trend_alerts(alerts)
        assert summary.total_alerts == 6
        assert summary.high_count == 2
        assert summary.warning_count == 3
        assert summary.info_count == 1


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------

class TestExport:
    """Tests for digest export."""

    def test_md_digest_export(self):
        """Export Markdown digest with expected sections."""
        from marketsentry.portfolio_trend_alerts import (
            export_portfolio_trend_alert_digest,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260501_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="80.0",
                    open_alert_count="1",
                )],
            )
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260502_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="50.0",
                    open_alert_count="5",
                    review_priority_label="immediate_review",
                )],
            )
            result = export_portfolio_trend_alert_digest(
                exports_dir=td, output_dir=td, fmt="md",
            )
            assert len(result.export_paths) == 1
            content = Path(result.export_paths[0]).read_text(
                encoding="utf-8"
            )
            assert "Portfolio Trend Alert Digest" in content
            assert "Alert Summary" in content
            assert "analytical review aid" in content
            assert "No outbound notifications" in content

    def test_csv_digest_export(self):
        """Export CSV digest with correct columns."""
        from marketsentry.portfolio_trend_alerts import (
            export_portfolio_trend_alert_digest,
            ALERT_DIGEST_CSV_FIELDNAMES,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260501_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="80.0",
                )],
            )
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260502_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="50.0",
                )],
            )
            result = export_portfolio_trend_alert_digest(
                exports_dir=td, output_dir=td, fmt="csv",
            )
            assert len(result.export_paths) == 1
            assert result.export_paths[0].endswith(".csv")
            with open(
                result.export_paths[0], encoding="utf-8"
            ) as f:
                reader = csv.DictReader(f)
                assert set(reader.fieldnames) == set(
                    ALERT_DIGEST_CSV_FIELDNAMES
                )
                rows = list(reader)
                assert len(rows) > 0

    def test_both_digest_export(self):
        """Export both CSV and Markdown."""
        from marketsentry.portfolio_trend_alerts import (
            export_portfolio_trend_alert_digest,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260501_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="80.0",
                    open_alert_count="1",
                )],
            )
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260502_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="50.0",
                    open_alert_count="5",
                )],
            )
            result = export_portfolio_trend_alert_digest(
                exports_dir=td, output_dir=td, fmt="both",
            )
            assert len(result.export_paths) == 2
            exts = {
                os.path.splitext(p)[1]
                for p in result.export_paths
            }
            assert ".csv" in exts
            assert ".md" in exts

    def test_no_alerts_export(self):
        """Export with no packs returns warnings."""
        from marketsentry.portfolio_trend_alerts import (
            export_portfolio_trend_alert_digest,
        )
        with tempfile.TemporaryDirectory() as td:
            result = export_portfolio_trend_alert_digest(
                exports_dir=td, output_dir=td, fmt="both",
            )
            # Should still produce alerts (info: no data)
            assert result.alert_count >= 1


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:
    """Tests for CLI commands."""

    def test_cli_portfolio_trend_alerts(self):
        """CLI portfolio-trend-alerts runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260502_100000.csv",
                [_base_row()],
            )
            result = runner.invoke(
                app,
                ["portfolio-trend-alerts",
                 "--exports-dir", td],
            )
            assert result.exit_code == 0
            assert "Portfolio Trend Alerts" in result.output
            assert "No mutations" in result.output
            assert "No outbound" in result.output

    def test_cli_export_portfolio_trend_alert_digest(self):
        """CLI export-portfolio-trend-alert-digest runs."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260502_100000.csv",
                [_base_row()],
            )
            result = runner.invoke(
                app,
                ["export-portfolio-trend-alert-digest",
                 "--exports-dir", td,
                 "--output-dir", td,
                 "--format", "both"],
            )
            assert result.exit_code == 0
            assert "Portfolio Trend Alert Digest" in result.output
            assert "No outbound" in result.output


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------

class TestDashboard:
    """Tests for dashboard alert section."""

    def test_dashboard_alert_data_loads(self):
        """Dashboard alert data loads without error."""
        from marketsentry.portfolio_trend_alerts import (
            evaluate_portfolio_trend_alerts,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            _write_pack_csv(
                td,
                "portfolio_review_pack_20260502_100000.csv",
                [_base_row()],
            )
            digest = evaluate_portfolio_trend_alerts(td)
            assert digest.summary.total_alerts >= 0
            assert digest.summary.high_count >= 0
            assert digest.summary.warning_count >= 0
            assert digest.summary.info_count >= 0


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
        content = script_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        executable_lines = [
            ln.lower() for ln in lines
            if ln.strip()
            and not ln.strip().upper().startswith("REM")
        ]
        exec_text = "\n".join(executable_lines)
        assert "force-live" not in exec_text
        assert "import-" not in exec_text
        assert "redfin-fetch" not in exec_text
        assert "scrape" not in exec_text

    def test_script_no_mutation_commands(self):
        """Script does not contain mutation commands."""
        script_path = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        )
        if not script_path.exists():
            pytest.skip("Script not found")
        content = script_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        executable_lines = [
            ln.lower() for ln in lines
            if ln.strip()
            and not ln.strip().upper().startswith("REM")
        ]
        exec_text = "\n".join(executable_lines)
        assert "triage-alert" not in exec_text
        assert "archive-alert" not in exec_text
        assert "delete-alert" not in exec_text
        assert "update-alert" not in exec_text

    def test_script_no_outbound_notifications(self):
        """Script does not contain outbound notification commands."""
        script_path = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        )
        if not script_path.exists():
            pytest.skip("Script not found")
        content = script_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        executable_lines = [
            ln.lower() for ln in lines
            if ln.strip()
            and not ln.strip().upper().startswith("REM")
        ]
        exec_text = "\n".join(executable_lines)
        assert "send-email" not in exec_text
        assert "send-sms" not in exec_text
        assert "webhook" not in exec_text
        assert "notify" not in exec_text

    def test_script_contains_alert_digest_command(self):
        """Script includes the alert digest command."""
        script_path = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        )
        if not script_path.exists():
            pytest.skip("Script not found")
        content = script_path.read_text(encoding="utf-8").lower()
        assert "export-portfolio-trend-alert-digest" in content

    def test_script_contains_all_four_commands(self):
        """Script runs pack, comparison, trends, and alert digest."""
        script_path = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        )
        if not script_path.exists():
            pytest.skip("Script not found")
        content = script_path.read_text(encoding="utf-8").lower()
        assert "export-portfolio-review-pack" in content
        assert "export-portfolio-review-comparison" in content
        assert "export-portfolio-review-trends" in content
        assert "export-portfolio-trend-alert-digest" in content


# ---------------------------------------------------------------------------
# Safety guard-rail tests
# ---------------------------------------------------------------------------

class TestSafety:
    """Safety guard-rail tests."""

    def test_no_outbound_notification_behavior(self):
        """Alert module does not send outbound notifications."""
        import inspect
        import marketsentry.portfolio_trend_alerts as mod

        source = inspect.getsource(mod)
        lower = source.lower()
        assert "send_email" not in lower
        assert "send_sms" not in lower
        assert "smtp" not in lower
        assert "webhook" not in lower
        assert "import smtplib" not in lower

    def test_no_candidate_watchlist_alert_mutation(self):
        """Alert module does not mutate DB state."""
        import inspect
        import marketsentry.portfolio_trend_alerts as mod

        source = inspect.getsource(mod)
        assert "INSERT INTO" not in source
        assert "UPDATE " not in source.replace(
            "update_alert", ""
        ).replace("update(", "")
        assert "DELETE FROM" not in source

    def test_no_redfin_source_overwrite(self):
        """Alert module does not write to Redfin source-of-truth."""
        import inspect
        import marketsentry.portfolio_trend_alerts as mod

        source = inspect.getsource(mod)
        assert "redfin_source" not in source.lower()
        assert "source_of_truth" not in source.lower()

    def test_quiet_gatekeeper_unchanged(self):
        """Alert module does not modify quiet gatekeeper logic."""
        import inspect
        import marketsentry.portfolio_trend_alerts as mod

        source = inspect.getsource(mod)
        assert "quiet_threshold" not in source.lower()
        assert "gatekeeper_threshold" not in source.lower()
        assert "def quiet_gatekeeper" not in source
        # Quiet gatekeeper thresholds still at 70.0
        from marketsentry.portfolio_review_pack import (
            _quiet_gatekeeper_result,
        )
        src2 = inspect.getsource(_quiet_gatekeeper_result)
        assert "70.0" in src2

    def test_no_walkability_fields(self):
        """No walkability fields in alert module."""
        import inspect
        import marketsentry.portfolio_trend_alerts as mod

        source = inspect.getsource(mod)
        assert "walkability" not in source.lower()
        assert "walk_score" not in source.lower()

    def test_no_network_calls(self):
        """Alert module does not import network libraries."""
        import inspect
        import marketsentry.portfolio_trend_alerts as mod

        source = inspect.getsource(mod)
        assert "import requests" not in source
        assert "import urllib" not in source
        assert "import httpx" not in source

    def test_no_browser_automation(self):
        """Alert module does not use browser automation."""
        import inspect
        import marketsentry.portfolio_trend_alerts as mod

        source = inspect.getsource(mod)
        lower = source.lower()
        assert "playwright" not in lower
        assert "selenium" not in lower
        assert "captcha" not in lower
        assert "anti-bot" not in lower
        assert "paywall" not in lower

    def test_model_classes_exist(self):
        """All 5 required model classes are importable."""
        from marketsentry.portfolio_trend_alerts import (
            PortfolioTrendAlert,
            PortfolioTrendAlertRule,
            PortfolioTrendAlertSummary,
            PortfolioTrendAlertDigest,
            PortfolioTrendAlertRunResult,
        )
        assert PortfolioTrendAlert is not None
        assert PortfolioTrendAlertRule is not None
        assert PortfolioTrendAlertSummary is not None
        assert PortfolioTrendAlertDigest is not None
        assert PortfolioTrendAlertRunResult is not None

    def test_required_functions_exist(self):
        """All 6 required functions are importable."""
        from marketsentry.portfolio_trend_alerts import (
            get_default_portfolio_trend_alert_rules,
            evaluate_portfolio_trend_alerts,
            evaluate_aggregate_burden_alerts,
            evaluate_property_trend_alerts,
            summarize_portfolio_trend_alerts,
            export_portfolio_trend_alert_digest,
        )
        assert callable(get_default_portfolio_trend_alert_rules)
        assert callable(evaluate_portfolio_trend_alerts)
        assert callable(evaluate_aggregate_burden_alerts)
        assert callable(evaluate_property_trend_alerts)
        assert callable(summarize_portfolio_trend_alerts)
        assert callable(export_portfolio_trend_alert_digest)

    def test_existing_m40_m41_m42_still_importable(self):
        """M40, M41, and M42 modules still import cleanly."""
        from marketsentry.portfolio_review_pack import (
            build_portfolio_review_pack,
            export_portfolio_review_pack,
        )
        from marketsentry.portfolio_review_comparison import (
            compare_portfolio_review_packs,
            export_portfolio_review_comparison,
        )
        from marketsentry.portfolio_review_trends import (
            build_portfolio_trend_series,
            export_portfolio_review_trend_report,
        )
        assert callable(build_portfolio_review_pack)
        assert callable(export_portfolio_review_pack)
        assert callable(compare_portfolio_review_packs)
        assert callable(export_portfolio_review_comparison)
        assert callable(build_portfolio_trend_series)
        assert callable(export_portfolio_review_trend_report)

    def test_alert_csv_fieldnames(self):
        """Alert CSV fieldnames match specification."""
        from marketsentry.portfolio_trend_alerts import (
            ALERT_DIGEST_CSV_FIELDNAMES,
        )
        required = [
            "alert_id", "alert_scope", "property_id",
            "candidate_id", "address", "severity",
            "alert_type", "message", "metric_name",
            "previous_value", "current_value", "delta_value",
            "recommended_local_action", "source_pack_file",
            "generated_at",
        ]
        assert ALERT_DIGEST_CSV_FIELDNAMES == required
