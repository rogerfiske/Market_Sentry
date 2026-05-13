"""Milestone 42 tests: Portfolio Review Pack Trend Visualization and Scoring.

Tests cover pack export discovery, timestamp parsing, series loading,
portfolio trend series, property trend series, aggregate burden scoring,
trend direction detection, CSV/MD export, CLI commands, dashboard,
scheduled script safety, and guard-rail constraints.
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
# Discovery tests
# ---------------------------------------------------------------------------

class TestDiscovery:
    """Tests for discovering portfolio review pack exports."""

    def test_discover_exports_empty_dir(self):
        """Empty directory returns empty list."""
        from marketsentry.portfolio_review_trends import (
            discover_portfolio_review_pack_exports,
        )
        with tempfile.TemporaryDirectory() as td:
            result = discover_portfolio_review_pack_exports(td)
            assert result == []

    def test_discover_exports_finds_packs(self):
        """Discover pack CSV files in directory."""
        from marketsentry.portfolio_review_trends import (
            discover_portfolio_review_pack_exports,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row()],
            )
            result = discover_portfolio_review_pack_exports(td)
            assert len(result) == 2

    def test_discover_exports_sorted_chronologically(self):
        """Discovered packs are sorted by timestamp."""
        from marketsentry.portfolio_review_trends import (
            discover_portfolio_review_pack_exports,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row()],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            result = discover_portfolio_review_pack_exports(td)
            assert len(result) == 2
            # First should be the earlier date
            assert "20260501" in result[0][0]
            assert "20260502" in result[1][0]


# ---------------------------------------------------------------------------
# Timestamp parsing tests
# ---------------------------------------------------------------------------

class TestTimestampParsing:
    """Tests for parsing timestamps from filenames."""

    def test_parse_timestamp_valid(self):
        """Parse timestamp from valid filename."""
        from marketsentry.portfolio_review_trends import (
            _parse_timestamp_from_filename,
        )
        result = _parse_timestamp_from_filename(
            "portfolio_review_pack_20260513_143000.csv"
        )
        assert result == "2026-05-13 14:30:00"

    def test_parse_timestamp_invalid(self):
        """Invalid filename returns None."""
        from marketsentry.portfolio_review_trends import (
            _parse_timestamp_from_filename,
        )
        result = _parse_timestamp_from_filename("random_file.csv")
        assert result is None

    def test_fallback_to_modified_time(self):
        """Fall back to file modification time when no timestamp."""
        from marketsentry.portfolio_review_trends import (
            discover_portfolio_review_pack_exports,
        )
        with tempfile.TemporaryDirectory() as td:
            # Write file with non-standard name that still matches glob
            _write_pack_csv(
                td, "portfolio_review_pack_custom.csv",
                [_base_row()],
            )
            result = discover_portfolio_review_pack_exports(td)
            assert len(result) == 1
            # Should have a timestamp from mtime
            assert result[0][1] != ""


# ---------------------------------------------------------------------------
# Load series tests
# ---------------------------------------------------------------------------

class TestLoadSeries:
    """Tests for loading pack series."""

    def test_load_pack_series(self):
        """Load multiple pack CSVs as a time series."""
        from marketsentry.portfolio_review_trends import (
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(property_id="1")],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(property_id="1"),
                 _base_row(property_id="2")],
            )
            series = load_portfolio_review_pack_series(td)
            assert len(series) == 2
            # First pack has 1 row, second has 2
            assert len(series[0][2]) == 1
            assert len(series[1][2]) == 2

    def test_handle_missing_columns_gracefully(self):
        """Handle CSV with missing columns without crashing."""
        from marketsentry.portfolio_review_trends import (
            load_portfolio_review_pack_series,
            build_portfolio_trend_series,
        )
        with tempfile.TemporaryDirectory() as td:
            # Write a CSV with minimal columns
            path = os.path.join(
                td, "portfolio_review_pack_20260501_100000.csv"
            )
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["property_id", "address"]
                )
                writer.writeheader()
                writer.writerow({
                    "property_id": "1",
                    "address": "123 Main St",
                })
            series = load_portfolio_review_pack_series(td)
            assert len(series) == 1
            # Should not crash when building trends
            points = build_portfolio_trend_series(series)
            assert len(points) == 1
            assert points[0].property_count == 1


# ---------------------------------------------------------------------------
# Portfolio trend series tests
# ---------------------------------------------------------------------------

class TestPortfolioTrendSeries:
    """Tests for building portfolio-level trend series."""

    def test_build_portfolio_trend_series(self):
        """Build portfolio trend series from two packs."""
        from marketsentry.portfolio_review_trends import (
            build_portfolio_trend_series,
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [
                    _base_row(property_id="1"),
                    _base_row(
                        property_id="2",
                        review_priority_label="immediate_review",
                    ),
                ],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [
                    _base_row(property_id="1"),
                    _base_row(property_id="2"),
                    _base_row(property_id="3"),
                ],
            )
            series = load_portfolio_review_pack_series(td)
            points = build_portfolio_trend_series(series)
            assert len(points) == 2
            assert points[0].property_count == 2
            assert points[1].property_count == 3
            assert points[0].immediate_review_count == 1
            assert points[1].normal_review_count == 3

    def test_aggregate_review_burden_score_low(self):
        """Low-burden portfolio gets low score."""
        from marketsentry.portfolio_review_trends import (
            build_portfolio_trend_series,
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [
                    _base_row(
                        property_id="1",
                        review_priority_label="low_current_activity",
                        lifecycle_health_label="healthy",
                        open_alert_count="0",
                        high_critical_alert_count="0",
                        quiet_gatekeeper_result="pass",
                        recent_churn_index="0.5",
                        effective_dom_delta="10",
                    ),
                ],
            )
            series = load_portfolio_review_pack_series(td)
            points = build_portfolio_trend_series(series)
            assert len(points) == 1
            assert points[0].aggregate_review_burden_score < 20
            assert points[0].aggregate_review_status_label == "low_burden"

    def test_aggregate_review_burden_score_high(self):
        """High-burden portfolio gets high score."""
        from marketsentry.portfolio_review_trends import (
            build_portfolio_trend_series,
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            rows = []
            for i in range(1, 6):
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
                td, "portfolio_review_pack_20260501_100000.csv",
                rows,
            )
            series = load_portfolio_review_pack_series(td)
            points = build_portfolio_trend_series(series)
            assert len(points) == 1
            assert points[0].aggregate_review_burden_score >= 70
            assert points[0].aggregate_review_status_label == "high_burden"

    def test_burden_score_capped_at_100(self):
        """Burden score does not exceed 100."""
        from marketsentry.portfolio_review_trends import (
            calculate_portfolio_trend_score,
            PortfolioReviewTrendPoint,
        )
        point = PortfolioReviewTrendPoint(
            property_count=10,
            immediate_review_count=20,
            high_review_count=20,
            lifecycle_attention_required_count=20,
            high_critical_alert_total=50,
            quiet_fail_count=20,
            high_churn_count=20,
            high_effective_dom_delta_count=20,
        )
        score = calculate_portfolio_trend_score(point)
        assert score == 100


# ---------------------------------------------------------------------------
# Property trend series tests
# ---------------------------------------------------------------------------

class TestPropertyTrendSeries:
    """Tests for building per-property trend series."""

    def test_property_trend_one_pack(self):
        """Property seen in one pack is 'new'."""
        from marketsentry.portfolio_review_trends import (
            build_property_trend_series,
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(property_id="1")],
            )
            series = load_portfolio_review_pack_series(td)
            props = build_property_trend_series(series)
            assert len(props) == 1
            assert props[0].times_seen == 1
            assert props[0].trend_direction == "new"

    def test_property_trend_multiple_packs(self):
        """Property across multiple packs computes deltas."""
        from marketsentry.portfolio_review_trends import (
            build_property_trend_series,
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="65.0",
                    open_alert_count="3",
                )],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="65.0",
                    open_alert_count="3",
                )],
            )
            series = load_portfolio_review_pack_series(td)
            props = build_property_trend_series(series)
            assert len(props) == 1
            assert props[0].times_seen == 2
            assert props[0].trend_direction != "new"

    def test_priority_label_change_count(self):
        """Count priority label changes across packs."""
        from marketsentry.portfolio_review_trends import (
            build_property_trend_series,
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(
                    property_id="1",
                    review_priority_label="normal_review",
                )],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(
                    property_id="1",
                    review_priority_label="high_review",
                )],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260503_100000.csv",
                [_base_row(
                    property_id="1",
                    review_priority_label="immediate_review",
                )],
            )
            series = load_portfolio_review_pack_series(td)
            props = build_property_trend_series(series)
            assert props[0].priority_label_changes == 2

    def test_lifecycle_health_label_change_count(self):
        """Count lifecycle health label changes across packs."""
        from marketsentry.portfolio_review_trends import (
            build_property_trend_series,
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_label="healthy",
                )],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_label="needs_review",
                )],
            )
            series = load_portfolio_review_pack_series(td)
            props = build_property_trend_series(series)
            assert props[0].lifecycle_health_label_changes == 1

    def test_open_alert_delta(self):
        """Compute open alert delta from first to latest."""
        from marketsentry.portfolio_review_trends import (
            build_property_trend_series,
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(property_id="1", open_alert_count="2")],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(property_id="1", open_alert_count="5")],
            )
            series = load_portfolio_review_pack_series(td)
            props = build_property_trend_series(series)
            assert props[0].open_alert_delta_first_to_latest == 3

    def test_effective_dom_v2_delta(self):
        """Compute Effective DOM v2 delta from first to latest."""
        from marketsentry.portfolio_review_trends import (
            build_property_trend_series,
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(property_id="1", effective_dom_v2="30")],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(property_id="1", effective_dom_v2="60")],
            )
            series = load_portfolio_review_pack_series(td)
            props = build_property_trend_series(series)
            assert props[0].effective_dom_v2_delta_first_to_latest == 30

    def test_churn_index_delta(self):
        """Compute Churn Index delta from first to latest."""
        from marketsentry.portfolio_review_trends import (
            build_property_trend_series,
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(
                    property_id="1", recent_churn_index="1.0",
                )],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(
                    property_id="1", recent_churn_index="3.5",
                )],
            )
            series = load_portfolio_review_pack_series(td)
            props = build_property_trend_series(series)
            assert props[0].churn_index_delta_first_to_latest == pytest.approx(
                2.5
            )

    def test_cross_site_confidence_delta(self):
        """Compute cross-site confidence delta from first to latest."""
        from marketsentry.portfolio_review_trends import (
            build_property_trend_series,
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(
                    property_id="1",
                    cross_site_confidence_score="60.0",
                )],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(
                    property_id="1",
                    cross_site_confidence_score="85.0",
                )],
            )
            series = load_portfolio_review_pack_series(td)
            props = build_property_trend_series(series)
            assert (
                props[0].cross_site_confidence_delta_first_to_latest
                == pytest.approx(25.0)
            )


# ---------------------------------------------------------------------------
# Trend direction tests
# ---------------------------------------------------------------------------

class TestTrendDirection:
    """Tests for trend direction classification."""

    def test_property_trend_direction_improved(self):
        """Property with improved metrics gets 'improved' direction."""
        from marketsentry.portfolio_review_trends import (
            build_property_trend_series,
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="50.0",
                    open_alert_count="5",
                    cross_site_confidence_score="60.0",
                    recent_churn_index="4.0",
                )],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="80.0",
                    open_alert_count="1",
                    cross_site_confidence_score="90.0",
                    recent_churn_index="1.5",
                )],
            )
            series = load_portfolio_review_pack_series(td)
            props = build_property_trend_series(series)
            assert props[0].trend_direction == "improved"

    def test_property_trend_direction_degraded(self):
        """Property with degraded metrics gets 'degraded' direction."""
        from marketsentry.portfolio_review_trends import (
            build_property_trend_series,
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="80.0",
                    open_alert_count="1",
                    cross_site_confidence_score="90.0",
                    recent_churn_index="1.0",
                )],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="50.0",
                    open_alert_count="5",
                    cross_site_confidence_score="60.0",
                    recent_churn_index="4.5",
                )],
            )
            series = load_portfolio_review_pack_series(td)
            props = build_property_trend_series(series)
            assert props[0].trend_direction == "degraded"

    def test_property_trend_direction_stable(self):
        """Property with minimal changes gets 'stable' direction."""
        from marketsentry.portfolio_review_trends import (
            build_property_trend_series,
            load_portfolio_review_pack_series,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="65.0",
                    open_alert_count="3",
                    cross_site_confidence_score="78.5",
                    recent_churn_index="2.1",
                )],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="66.0",
                    open_alert_count="3",
                    cross_site_confidence_score="79.0",
                    recent_churn_index="2.0",
                )],
            )
            series = load_portfolio_review_pack_series(td)
            props = build_property_trend_series(series)
            assert props[0].trend_direction == "stable"


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------

class TestExport:
    """Tests for trend report export."""

    def test_trend_csv_export(self):
        """Export trend CSV with correct columns."""
        from marketsentry.portfolio_review_trends import (
            export_portfolio_review_trend_report,
            TREND_CSV_FIELDNAMES,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(property_id="1")],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(property_id="1"),
                 _base_row(property_id="2")],
            )
            result = export_portfolio_review_trend_report(
                exports_dir=td, output_dir=td, fmt="csv",
            )
            assert len(result.export_paths) == 1
            assert result.export_paths[0].endswith(".csv")
            assert result.source_file_count == 2
            assert result.portfolio_trend_points == 2
            assert result.property_trend_rows == 2

            # Verify CSV columns
            with open(
                result.export_paths[0], encoding="utf-8"
            ) as f:
                reader = csv.DictReader(f)
                assert set(reader.fieldnames) == set(
                    TREND_CSV_FIELDNAMES
                )
                rows = list(reader)
                # 2 portfolio_summary rows + 2 property_trend rows
                assert len(rows) == 4
                row_types = [r["row_type"] for r in rows]
                assert "portfolio_summary" in row_types
                assert "property_trend" in row_types

    def test_trend_md_export(self):
        """Export trend Markdown with expected sections."""
        from marketsentry.portfolio_review_trends import (
            export_portfolio_review_trend_report,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(property_id="1")],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row(
                    property_id="1",
                    lifecycle_health_score="80.0",
                    open_alert_count="0",
                )],
            )
            result = export_portfolio_review_trend_report(
                exports_dir=td, output_dir=td, fmt="md",
            )
            assert len(result.export_paths) == 1
            content = Path(result.export_paths[0]).read_text(
                encoding="utf-8"
            )
            assert "Portfolio Review Pack Trend Report" in content
            assert "Source Files Analyzed" in content
            assert "Portfolio Trend Summary" in content
            assert "Aggregate Burden Over Time" in content
            assert "Priority Count Trend" in content
            assert "Lifecycle Health Trend" in content
            assert "Alert Burden Trend" in content
            assert "analytical review aid" in content

    def test_trend_both_export(self):
        """Export both CSV and Markdown."""
        from marketsentry.portfolio_review_trends import (
            export_portfolio_review_trend_report,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(property_id="1")],
            )
            result = export_portfolio_review_trend_report(
                exports_dir=td, output_dir=td, fmt="both",
            )
            assert len(result.export_paths) == 2
            exts = {
                os.path.splitext(p)[1] for p in result.export_paths
            }
            assert ".csv" in exts
            assert ".md" in exts

    def test_trend_export_no_packs(self):
        """Export with no packs returns warnings."""
        from marketsentry.portfolio_review_trends import (
            export_portfolio_review_trend_report,
        )
        with tempfile.TemporaryDirectory() as td:
            result = export_portfolio_review_trend_report(
                exports_dir=td, output_dir=td, fmt="both",
            )
            assert len(result.export_paths) == 0
            assert len(result.warnings) > 0


# ---------------------------------------------------------------------------
# Summarize tests
# ---------------------------------------------------------------------------

class TestSummarize:
    """Tests for portfolio review trend summarization."""

    def test_summarize_trends(self):
        """Summarize produces correct aggregate counts."""
        from marketsentry.portfolio_review_trends import (
            build_portfolio_trend_series,
            build_property_trend_series,
            load_portfolio_review_pack_series,
            summarize_portfolio_review_trends,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [
                    _base_row(property_id="1"),
                    _base_row(property_id="2"),
                ],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [
                    _base_row(property_id="1"),
                    _base_row(property_id="2"),
                    _base_row(property_id="3"),
                ],
            )
            series = load_portfolio_review_pack_series(td)
            portfolio_points = build_portfolio_trend_series(series)
            property_points = build_property_trend_series(series)
            summary = summarize_portfolio_review_trends(
                portfolio_points, property_points
            )
            assert summary.pack_count == 2
            assert summary.total_properties_tracked == 3
            assert summary.first_pack_date != ""
            assert summary.latest_pack_date != ""
            # Property 3 is new (only in second pack)
            assert summary.new_count >= 1

    def test_burden_trend_direction(self):
        """Burden trend direction reflects score change."""
        from marketsentry.portfolio_review_trends import (
            build_portfolio_trend_series,
            build_property_trend_series,
            load_portfolio_review_pack_series,
            summarize_portfolio_review_trends,
        )
        with tempfile.TemporaryDirectory() as td:
            # First pack: low burden
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row(
                    property_id="1",
                    review_priority_label="low_current_activity",
                    lifecycle_health_label="healthy",
                    open_alert_count="0",
                    high_critical_alert_count="0",
                    quiet_gatekeeper_result="pass",
                    recent_churn_index="0.5",
                    effective_dom_delta="10",
                )],
            )
            # Second pack: higher burden
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [
                    _base_row(
                        property_id="1",
                        review_priority_label="immediate_review",
                        lifecycle_health_label="attention_required",
                        open_alert_count="5",
                        high_critical_alert_count="3",
                        quiet_gatekeeper_result="fail",
                        recent_churn_index="5.0",
                        effective_dom_delta="100",
                    ),
                    _base_row(
                        property_id="2",
                        review_priority_label="immediate_review",
                        lifecycle_health_label="attention_required",
                        open_alert_count="4",
                        high_critical_alert_count="2",
                        quiet_gatekeeper_result="fail",
                        recent_churn_index="4.5",
                        effective_dom_delta="80",
                    ),
                ],
            )
            series = load_portfolio_review_pack_series(td)
            portfolio_points = build_portfolio_trend_series(series)
            property_points = build_property_trend_series(series)
            summary = summarize_portfolio_review_trends(
                portfolio_points, property_points
            )
            assert summary.burden_trend_direction == "degraded"


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:
    """Tests for CLI commands."""

    def test_cli_portfolio_review_trends(self):
        """CLI portfolio-review-trends runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row()],
            )
            result = runner.invoke(
                app,
                ["portfolio-review-trends",
                 "--exports-dir", td],
            )
            assert result.exit_code == 0
            assert "Portfolio Review Trends" in result.output
            assert "No mutations" in result.output

    def test_cli_portfolio_review_trends_empty(self):
        """CLI portfolio-review-trends with no packs exits cleanly."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            result = runner.invoke(
                app,
                ["portfolio-review-trends",
                 "--exports-dir", td],
            )
            assert result.exit_code == 0
            assert "No portfolio review pack CSV files found" in result.output

    def test_cli_export_portfolio_review_trends(self):
        """CLI export-portfolio-review-trends runs and creates files."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row()],
            )
            result = runner.invoke(
                app,
                ["export-portfolio-review-trends",
                 "--exports-dir", td,
                 "--output-dir", td,
                 "--format", "both"],
            )
            assert result.exit_code == 0
            assert "Portfolio Review Trend Report" in result.output
            assert "No mutations" in result.output


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------

class TestDashboard:
    """Tests for dashboard trend section."""

    def test_dashboard_trend_data_loads(self):
        """Dashboard trend data loads without error."""
        from marketsentry.portfolio_review_trends import (
            build_portfolio_trend_series,
            build_property_trend_series,
            load_portfolio_review_pack_series,
            summarize_portfolio_review_trends,
        )
        with tempfile.TemporaryDirectory() as td:
            _write_pack_csv(
                td, "portfolio_review_pack_20260501_100000.csv",
                [_base_row()],
            )
            _write_pack_csv(
                td, "portfolio_review_pack_20260502_100000.csv",
                [_base_row()],
            )
            series = load_portfolio_review_pack_series(td)
            portfolio_points = build_portfolio_trend_series(series)
            property_points = build_property_trend_series(series)
            summary = summarize_portfolio_review_trends(
                portfolio_points, property_points
            )
            assert summary.pack_count == 2
            assert summary.total_properties_tracked == 1
            assert summary.latest_burden_score >= 0
            assert summary.latest_burden_label in (
                "low_burden", "moderate_burden",
                "elevated_burden", "high_burden",
            )


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

    def test_script_contains_trends_command(self):
        """Script includes the trends report command."""
        script_path = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        )
        if not script_path.exists():
            pytest.skip("Script not found")
        content = script_path.read_text(encoding="utf-8").lower()
        assert "export-portfolio-review-trends" in content

    def test_script_contains_all_three_commands(self):
        """Script runs pack, comparison, and trends commands."""
        script_path = Path(
            "scripts/run_portfolio_review_pack_report.bat"
        )
        if not script_path.exists():
            pytest.skip("Script not found")
        content = script_path.read_text(encoding="utf-8").lower()
        assert "export-portfolio-review-pack" in content
        assert "export-portfolio-review-comparison" in content
        assert "export-portfolio-review-trends" in content


# ---------------------------------------------------------------------------
# Safety guard-rail tests
# ---------------------------------------------------------------------------

class TestSafety:
    """Safety guard-rail tests."""

    def test_no_candidate_watchlist_alert_mutation(self):
        """Trends module does not mutate DB state."""
        import inspect
        import marketsentry.portfolio_review_trends as mod

        source = inspect.getsource(mod)
        assert "INSERT INTO" not in source
        assert "UPDATE " not in source.replace(
            "update_alert", ""
        ).replace("update(", "")
        assert "DELETE FROM" not in source

    def test_no_redfin_source_overwrite(self):
        """Trends module does not write to Redfin source-of-truth."""
        import inspect
        import marketsentry.portfolio_review_trends as mod

        source = inspect.getsource(mod)
        assert "redfin_source" not in source.lower()
        assert "source_of_truth" not in source.lower()

    def test_quiet_gatekeeper_unchanged(self):
        """Trends does not modify quiet gatekeeper logic."""
        import inspect
        import marketsentry.portfolio_review_trends as mod

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
        """No walkability fields in trends module."""
        import inspect
        import marketsentry.portfolio_review_trends as mod

        source = inspect.getsource(mod)
        assert "walkability" not in source.lower()
        assert "walk_score" not in source.lower()

    def test_no_network_calls(self):
        """Trends module does not import network libraries."""
        import inspect
        import marketsentry.portfolio_review_trends as mod

        source = inspect.getsource(mod)
        assert "import requests" not in source
        assert "import urllib" not in source
        assert "import httpx" not in source

    def test_no_browser_automation(self):
        """Trends module does not use browser automation."""
        import inspect
        import marketsentry.portfolio_review_trends as mod

        source = inspect.getsource(mod)
        lower = source.lower()
        assert "playwright" not in lower
        assert "selenium" not in lower
        assert "captcha" not in lower
        assert "anti-bot" not in lower
        assert "paywall" not in lower

    def test_model_classes_exist(self):
        """All 5 required model classes are importable."""
        from marketsentry.portfolio_review_trends import (
            PortfolioReviewTrendPoint,
            PortfolioReviewPropertyTrendPoint,
            PortfolioReviewTrendSummary,
            PortfolioReviewTrendReportRow,
            PortfolioReviewTrendRunResult,
        )
        assert PortfolioReviewTrendPoint is not None
        assert PortfolioReviewPropertyTrendPoint is not None
        assert PortfolioReviewTrendSummary is not None
        assert PortfolioReviewTrendReportRow is not None
        assert PortfolioReviewTrendRunResult is not None

    def test_required_functions_exist(self):
        """All 7 required functions are importable."""
        from marketsentry.portfolio_review_trends import (
            discover_portfolio_review_pack_exports,
            load_portfolio_review_pack_series,
            build_portfolio_trend_series,
            build_property_trend_series,
            calculate_portfolio_trend_score,
            summarize_portfolio_review_trends,
            export_portfolio_review_trend_report,
        )
        assert callable(discover_portfolio_review_pack_exports)
        assert callable(load_portfolio_review_pack_series)
        assert callable(build_portfolio_trend_series)
        assert callable(build_property_trend_series)
        assert callable(calculate_portfolio_trend_score)
        assert callable(summarize_portfolio_review_trends)
        assert callable(export_portfolio_review_trend_report)

    def test_existing_m40_m41_still_importable(self):
        """M40 and M41 modules still import cleanly."""
        from marketsentry.portfolio_review_pack import (
            build_portfolio_review_pack,
            export_portfolio_review_pack,
        )
        from marketsentry.portfolio_review_comparison import (
            compare_portfolio_review_packs,
            export_portfolio_review_comparison,
        )
        assert callable(build_portfolio_review_pack)
        assert callable(export_portfolio_review_pack)
        assert callable(compare_portfolio_review_packs)
        assert callable(export_portfolio_review_comparison)

    def test_trend_csv_fieldnames(self):
        """Trend CSV fieldnames match specification."""
        from marketsentry.portfolio_review_trends import (
            TREND_CSV_FIELDNAMES,
        )
        required = [
            "row_type", "captured_at", "pack_file",
            "property_id", "candidate_id", "address",
            "metric_name", "metric_value", "trend_direction",
            "trend_summary", "recommended_review_action",
        ]
        assert TREND_CSV_FIELDNAMES == required
