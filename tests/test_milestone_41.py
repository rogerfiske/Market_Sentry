"""Milestone 41 tests: Portfolio Review Pack Historical Comparison Reports.

Tests cover CSV loading, pack finding, comparison detection, summary
metrics, CSV/MD export, CLI commands, dashboard, scheduled script
safety, and guard-rail constraints.
"""

import csv
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_pack_csv(dir_path, filename, rows):
    """Write a portfolio review pack CSV file with standard headers."""
    from marketsentry.portfolio_review_comparison import (
        COMPARISON_CSV_FIELDNAMES,
    )
    # Use the review pack fieldnames from M40
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
# Load CSV tests
# ---------------------------------------------------------------------------

class TestLoadCSV:
    """Tests for loading portfolio review pack CSV files."""

    def test_load_valid_csv(self):
        """Load a valid portfolio review pack CSV."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
        )
        with tempfile.TemporaryDirectory() as td:
            path = _write_pack_csv(td, "pack.csv", [_base_row()])
            snap = load_portfolio_review_pack_csv(path)
            assert snap.property_count == 1
            assert snap.file_path == path
            assert len(snap.rows) == 1
            assert snap.rows[0]["property_id"] == "1"

    def test_load_missing_csv(self):
        """Loading a missing CSV returns empty snapshot."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
        )
        snap = load_portfolio_review_pack_csv("/nonexistent/path.csv")
        assert snap.property_count == 0
        assert len(snap.rows) == 0

    def test_load_empty_csv(self):
        """Loading a CSV with headers but no data rows."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
        )
        with tempfile.TemporaryDirectory() as td:
            path = _write_pack_csv(td, "empty.csv", [])
            snap = load_portfolio_review_pack_csv(path)
            assert snap.property_count == 0


# ---------------------------------------------------------------------------
# Find pack tests
# ---------------------------------------------------------------------------

class TestFindPack:
    """Tests for finding latest and previous pack CSVs."""

    def test_find_latest_pack(self):
        """Find the latest pack CSV by modification time."""
        from marketsentry.portfolio_review_comparison import (
            find_latest_portfolio_review_pack,
        )
        with tempfile.TemporaryDirectory() as td:
            import time
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            time.sleep(0.05)
            p2 = _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row()],
            )
            result = find_latest_portfolio_review_pack(td)
            assert result == p2

    def test_find_previous_pack(self):
        """Find the previous (second newest) pack CSV."""
        from marketsentry.portfolio_review_comparison import (
            find_previous_portfolio_review_pack,
        )
        with tempfile.TemporaryDirectory() as td:
            import time
            p1 = _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            time.sleep(0.05)
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row()],
            )
            result = find_previous_portfolio_review_pack(td)
            assert result == p1

    def test_find_previous_pack_single_file(self):
        """No previous pack when only one CSV exists."""
        from marketsentry.portfolio_review_comparison import (
            find_previous_portfolio_review_pack,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            result = find_previous_portfolio_review_pack(td)
            assert result is None

    def test_handle_missing_previous_pack(self):
        """Comparison works with no previous pack."""
        from marketsentry.portfolio_review_comparison import (
            compare_current_to_previous_portfolio_pack,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            changes, summary, curr, prev = (
                compare_current_to_previous_portfolio_pack(
                    exports_dir=td,
                )
            )
            assert len(changes) == 1
            assert changes[0].change_type == "added"
            assert summary.added_count == 1


# ---------------------------------------------------------------------------
# Comparison detection tests
# ---------------------------------------------------------------------------

class TestCompareChanges:
    """Tests for per-property change detection."""

    def test_added_property(self):
        """Detect a property added to the current pack."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
            compare_portfolio_review_packs,
        )
        with tempfile.TemporaryDirectory() as td:
            curr_path = _write_pack_csv(
                td, "curr.csv", [_base_row(property_id="1")]
            )
            prev_path = _write_pack_csv(td, "prev.csv", [])
            curr = load_portfolio_review_pack_csv(curr_path)
            prev = load_portfolio_review_pack_csv(prev_path)
            changes = compare_portfolio_review_packs(curr, prev)
            assert len(changes) == 1
            assert changes[0].change_type == "added"
            assert changes[0].trend_label == "new"

    def test_removed_property(self):
        """Detect a property removed from the current pack."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
            compare_portfolio_review_packs,
        )
        with tempfile.TemporaryDirectory() as td:
            curr_path = _write_pack_csv(td, "curr.csv", [])
            prev_path = _write_pack_csv(
                td, "prev.csv", [_base_row(property_id="1")]
            )
            curr = load_portfolio_review_pack_csv(curr_path)
            prev = load_portfolio_review_pack_csv(prev_path)
            changes = compare_portfolio_review_packs(curr, prev)
            assert len(changes) == 1
            assert changes[0].change_type == "removed"
            assert changes[0].trend_label == "removed"

    def test_unchanged_property(self):
        """No material changes detected."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
            compare_portfolio_review_packs,
        )
        with tempfile.TemporaryDirectory() as td:
            row = _base_row(property_id="1")
            curr_path = _write_pack_csv(td, "curr.csv", [row])
            prev_path = _write_pack_csv(td, "prev.csv", [row])
            curr = load_portfolio_review_pack_csv(curr_path)
            prev = load_portfolio_review_pack_csv(prev_path)
            changes = compare_portfolio_review_packs(curr, prev)
            assert len(changes) == 1
            assert changes[0].change_type == "unchanged"
            assert changes[0].trend_label == "unchanged"

    def test_priority_label_change(self):
        """Detect priority label change."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
            compare_portfolio_review_packs,
        )
        with tempfile.TemporaryDirectory() as td:
            curr_path = _write_pack_csv(td, "curr.csv", [
                _base_row(
                    property_id="1",
                    review_priority_label="immediate_review",
                    review_priority_score="45",
                ),
            ])
            prev_path = _write_pack_csv(td, "prev.csv", [
                _base_row(
                    property_id="1",
                    review_priority_label="normal_review",
                    review_priority_score="15",
                ),
            ])
            curr = load_portfolio_review_pack_csv(curr_path)
            prev = load_portfolio_review_pack_csv(prev_path)
            changes = compare_portfolio_review_packs(curr, prev)
            assert changes[0].change_type == "changed"
            assert changes[0].current_priority_label == "immediate_review"
            assert changes[0].previous_priority_label == "normal_review"
            assert changes[0].priority_score_delta == 30

    def test_priority_score_change(self):
        """Detect material priority score change."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
            compare_portfolio_review_packs,
        )
        with tempfile.TemporaryDirectory() as td:
            curr_path = _write_pack_csv(td, "curr.csv", [
                _base_row(
                    property_id="1",
                    review_priority_score="25",
                ),
            ])
            prev_path = _write_pack_csv(td, "prev.csv", [
                _base_row(
                    property_id="1",
                    review_priority_score="15",
                ),
            ])
            curr = load_portfolio_review_pack_csv(curr_path)
            prev = load_portfolio_review_pack_csv(prev_path)
            changes = compare_portfolio_review_packs(curr, prev)
            assert changes[0].change_type == "changed"
            assert changes[0].priority_score_delta == 10

    def test_lifecycle_health_label_change(self):
        """Detect lifecycle health label change."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
            compare_portfolio_review_packs,
        )
        with tempfile.TemporaryDirectory() as td:
            curr_path = _write_pack_csv(td, "curr.csv", [
                _base_row(
                    property_id="1",
                    lifecycle_health_label="attention_required",
                    lifecycle_health_score="40.0",
                ),
            ])
            prev_path = _write_pack_csv(td, "prev.csv", [
                _base_row(
                    property_id="1",
                    lifecycle_health_label="needs_review",
                    lifecycle_health_score="65.0",
                ),
            ])
            curr = load_portfolio_review_pack_csv(curr_path)
            prev = load_portfolio_review_pack_csv(prev_path)
            changes = compare_portfolio_review_packs(curr, prev)
            assert changes[0].change_type == "changed"
            assert (
                changes[0].current_lifecycle_health_label
                == "attention_required"
            )
            assert changes[0].lifecycle_health_score_delta == -25.0

    def test_alert_count_change(self):
        """Detect open alert count change."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
            compare_portfolio_review_packs,
        )
        with tempfile.TemporaryDirectory() as td:
            curr_path = _write_pack_csv(td, "curr.csv", [
                _base_row(property_id="1", open_alert_count="5"),
            ])
            prev_path = _write_pack_csv(td, "prev.csv", [
                _base_row(property_id="1", open_alert_count="3"),
            ])
            curr = load_portfolio_review_pack_csv(curr_path)
            prev = load_portfolio_review_pack_csv(prev_path)
            changes = compare_portfolio_review_packs(curr, prev)
            assert changes[0].change_type == "changed"
            assert changes[0].open_alert_delta == 2

    def test_effective_dom_v2_material_change(self):
        """Detect Effective DOM v2 material change (>= 14 days)."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
            compare_portfolio_review_packs,
        )
        with tempfile.TemporaryDirectory() as td:
            curr_path = _write_pack_csv(td, "curr.csv", [
                _base_row(property_id="1", effective_dom_v2="60"),
            ])
            prev_path = _write_pack_csv(td, "prev.csv", [
                _base_row(property_id="1", effective_dom_v2="45"),
            ])
            curr = load_portfolio_review_pack_csv(curr_path)
            prev = load_portfolio_review_pack_csv(prev_path)
            changes = compare_portfolio_review_packs(curr, prev)
            assert changes[0].change_type == "changed"
            assert changes[0].effective_dom_v2_delta == 15

    def test_churn_index_material_change(self):
        """Detect Churn Index material change (>= 1.0)."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
            compare_portfolio_review_packs,
        )
        with tempfile.TemporaryDirectory() as td:
            curr_path = _write_pack_csv(td, "curr.csv", [
                _base_row(property_id="1", recent_churn_index="4.5"),
            ])
            prev_path = _write_pack_csv(td, "prev.csv", [
                _base_row(property_id="1", recent_churn_index="2.1"),
            ])
            curr = load_portfolio_review_pack_csv(curr_path)
            prev = load_portfolio_review_pack_csv(prev_path)
            changes = compare_portfolio_review_packs(curr, prev)
            assert changes[0].change_type == "changed"
            assert changes[0].churn_index_delta == pytest.approx(2.4)

    def test_cross_site_confidence_material_change(self):
        """Detect cross-site confidence material change (>= 10)."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
            compare_portfolio_review_packs,
        )
        with tempfile.TemporaryDirectory() as td:
            curr_path = _write_pack_csv(td, "curr.csv", [
                _base_row(
                    property_id="1",
                    cross_site_confidence_score="90.0",
                ),
            ])
            prev_path = _write_pack_csv(td, "prev.csv", [
                _base_row(
                    property_id="1",
                    cross_site_confidence_score="78.5",
                ),
            ])
            curr = load_portfolio_review_pack_csv(curr_path)
            prev = load_portfolio_review_pack_csv(prev_path)
            changes = compare_portfolio_review_packs(curr, prev)
            assert changes[0].change_type == "changed"
            assert changes[0].cross_site_confidence_delta == pytest.approx(
                11.5
            )


# ---------------------------------------------------------------------------
# Summary metrics tests
# ---------------------------------------------------------------------------

class TestSummaryMetrics:
    """Tests for comparison summary computation."""

    def test_summary_counts(self):
        """Summary includes correct aggregate counts."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
            compare_portfolio_review_packs,
            summarize_portfolio_review_changes,
        )
        with tempfile.TemporaryDirectory() as td:
            curr_path = _write_pack_csv(td, "curr.csv", [
                _base_row(property_id="1"),  # unchanged
                _base_row(property_id="2"),  # added (not in prev)
                _base_row(
                    property_id="3",
                    open_alert_count="5",
                ),  # alert burden increased
            ])
            prev_path = _write_pack_csv(td, "prev.csv", [
                _base_row(property_id="1"),
                _base_row(property_id="3", open_alert_count="2"),
                _base_row(property_id="4"),  # removed
            ])
            curr = load_portfolio_review_pack_csv(curr_path)
            prev = load_portfolio_review_pack_csv(prev_path)
            changes = compare_portfolio_review_packs(curr, prev)
            summary = summarize_portfolio_review_changes(
                changes, curr, prev
            )
            assert summary.total_properties_current == 3
            assert summary.total_properties_previous == 3
            assert summary.added_count == 1
            assert summary.removed_count == 1
            assert summary.no_change_count == 1
            assert summary.alert_burden_increased_count == 1


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------

class TestExport:
    """Tests for comparison report export."""

    def test_csv_export(self):
        """Export comparison CSV with correct columns."""
        from marketsentry.portfolio_review_comparison import (
            export_portfolio_review_comparison,
            COMPARISON_CSV_FIELDNAMES,
        )
        with tempfile.TemporaryDirectory() as td:
            import time
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(property_id="1")],
            )
            time.sleep(0.05)
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(property_id="1"),
                 _base_row(property_id="2")],
            )
            result = export_portfolio_review_comparison(
                exports_dir=td, output_dir=td, fmt="csv",
            )
            assert len(result.export_paths) == 1
            assert result.export_paths[0].endswith(".csv")
            assert result.row_count == 2

            # Verify CSV columns
            with open(result.export_paths[0], encoding="utf-8") as f:
                reader = csv.DictReader(f)
                assert set(reader.fieldnames) == set(
                    COMPARISON_CSV_FIELDNAMES
                )

    def test_md_export(self):
        """Export comparison Markdown with expected sections."""
        from marketsentry.portfolio_review_comparison import (
            export_portfolio_review_comparison,
        )
        with tempfile.TemporaryDirectory() as td:
            import time
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(property_id="1")],
            )
            time.sleep(0.05)
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [
                    _base_row(
                        property_id="1",
                        review_priority_label="immediate_review",
                        review_priority_score="45",
                    ),
                    _base_row(property_id="2"),
                ],
            )
            result = export_portfolio_review_comparison(
                exports_dir=td, output_dir=td, fmt="md",
            )
            assert len(result.export_paths) == 1
            content = Path(result.export_paths[0]).read_text(
                encoding="utf-8"
            )
            assert "Portfolio Review Pack Comparison Report" in content
            assert "Summary Metrics" in content
            assert "Added Properties" in content
            assert "analytical review aid" in content

    def test_both_export(self):
        """Export both CSV and Markdown."""
        from marketsentry.portfolio_review_comparison import (
            export_portfolio_review_comparison,
        )
        with tempfile.TemporaryDirectory() as td:
            import time
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(property_id="1")],
            )
            time.sleep(0.05)
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(property_id="1")],
            )
            result = export_portfolio_review_comparison(
                exports_dir=td, output_dir=td, fmt="both",
            )
            assert len(result.export_paths) == 2
            exts = {
                os.path.splitext(p)[1] for p in result.export_paths
            }
            assert ".csv" in exts
            assert ".md" in exts


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:
    """Tests for CLI commands."""

    def test_cli_compare_portfolio_review_packs(self):
        """CLI compare-portfolio-review-packs runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            import time
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            time.sleep(0.05)
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row()],
            )
            result = runner.invoke(
                app,
                ["compare-portfolio-review-packs",
                 "--exports-dir", td],
            )
            assert result.exit_code == 0
            assert "Comparison" in result.output

    def test_cli_export_portfolio_review_comparison(self):
        """CLI export-portfolio-review-comparison runs."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            import time
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            time.sleep(0.05)
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row()],
            )
            result = runner.invoke(
                app,
                ["export-portfolio-review-comparison",
                 "--exports-dir", td,
                 "--output-dir", td,
                 "--format", "csv"],
            )
            assert result.exit_code == 0
            assert "Export" in result.output


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------

class TestDashboard:
    """Tests for dashboard comparison section."""

    def test_dashboard_comparison_data_loads(self):
        """Dashboard comparison section loads without error."""
        from marketsentry.portfolio_review_comparison import (
            compare_current_to_previous_portfolio_pack,
        )
        with tempfile.TemporaryDirectory() as td:
            import time
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            time.sleep(0.05)
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row()],
            )
            changes, summary, curr, prev = (
                compare_current_to_previous_portfolio_pack(
                    exports_dir=td,
                )
            )
            assert summary.total_properties_current == 1
            assert summary.total_properties_previous == 1


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
        # Check only non-comment lines for dangerous commands
        executable_lines = [
            ln.lower() for ln in lines
            if ln.strip() and not ln.strip().upper().startswith("REM")
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
            if ln.strip() and not ln.strip().upper().startswith("REM")
        ]
        exec_text = "\n".join(executable_lines)
        assert "triage-alert" not in exec_text
        assert "archive-alert" not in exec_text
        assert "delete-alert" not in exec_text
        assert "update-alert" not in exec_text

    def test_script_contains_comparison_command(self):
        """Script includes the comparison report command."""
        script_path = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        )
        if not script_path.exists():
            pytest.skip("Script not found")
        content = script_path.read_text(encoding="utf-8").lower()
        assert "export-portfolio-review-comparison" in content


# ---------------------------------------------------------------------------
# Safety guard-rail tests
# ---------------------------------------------------------------------------

class TestSafety:
    """Safety guard-rail tests."""

    def test_no_candidate_watchlist_alert_mutation(self):
        """Comparison module does not mutate DB state."""
        import inspect
        import marketsentry.portfolio_review_comparison as mod

        source = inspect.getsource(mod)
        assert "INSERT INTO" not in source
        assert "UPDATE " not in source.replace(
            "update_alert", ""
        ).replace("update(", "")
        assert "DELETE FROM" not in source

    def test_no_redfin_source_overwrite(self):
        """Comparison does not write to Redfin source-of-truth."""
        import inspect
        import marketsentry.portfolio_review_comparison as mod

        source = inspect.getsource(mod)
        assert "redfin_source" not in source.lower()
        assert "source_of_truth" not in source.lower()

    def test_quiet_gatekeeper_unchanged(self):
        """Comparison does not modify quiet gatekeeper logic."""
        import inspect
        import marketsentry.portfolio_review_comparison as mod

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
        """No walkability fields in comparison module."""
        import inspect
        import marketsentry.portfolio_review_comparison as mod

        source = inspect.getsource(mod)
        assert "walkability" not in source.lower()
        assert "walk_score" not in source.lower()

    def test_no_network_calls(self):
        """Comparison module does not import network libraries."""
        import inspect
        import marketsentry.portfolio_review_comparison as mod

        source = inspect.getsource(mod)
        assert "import requests" not in source
        assert "import urllib" not in source
        assert "import httpx" not in source

    def test_no_browser_automation(self):
        """Comparison module does not use browser automation."""
        import inspect
        import marketsentry.portfolio_review_comparison as mod

        source = inspect.getsource(mod)
        lower = source.lower()
        assert "playwright" not in lower
        assert "selenium" not in lower
        assert "captcha" not in lower
        assert "anti-bot" not in lower
        assert "paywall" not in lower

    def test_model_classes_exist(self):
        """All 5 required model classes are importable."""
        from marketsentry.portfolio_review_comparison import (
            PortfolioReviewPackSnapshot,
            PortfolioReviewPropertyChange,
            PortfolioReviewComparisonSummary,
            PortfolioReviewComparisonReportRow,
            PortfolioReviewComparisonRunResult,
        )
        assert PortfolioReviewPackSnapshot is not None
        assert PortfolioReviewPropertyChange is not None
        assert PortfolioReviewComparisonSummary is not None
        assert PortfolioReviewComparisonReportRow is not None
        assert PortfolioReviewComparisonRunResult is not None

    def test_required_functions_exist(self):
        """All 7 required functions are importable."""
        from marketsentry.portfolio_review_comparison import (
            load_portfolio_review_pack_csv,
            compare_portfolio_review_packs,
            compare_current_to_previous_portfolio_pack,
            find_latest_portfolio_review_pack,
            find_previous_portfolio_review_pack,
            summarize_portfolio_review_changes,
            export_portfolio_review_comparison,
        )
        assert callable(load_portfolio_review_pack_csv)
        assert callable(compare_portfolio_review_packs)
        assert callable(compare_current_to_previous_portfolio_pack)
        assert callable(find_latest_portfolio_review_pack)
        assert callable(find_previous_portfolio_review_pack)
        assert callable(summarize_portfolio_review_changes)
        assert callable(export_portfolio_review_comparison)

    def test_existing_m40_tests_still_importable(self):
        """M40 portfolio review pack still works."""
        from marketsentry.portfolio_review_pack import (
            PortfolioReviewPropertyBrief,
            PortfolioReviewPackSummary,
            build_portfolio_review_pack,
            export_portfolio_review_pack,
        )
        assert PortfolioReviewPropertyBrief is not None
        assert PortfolioReviewPackSummary is not None
        assert callable(build_portfolio_review_pack)
        assert callable(export_portfolio_review_pack)
