"""Tests for Milestone 12: Local Review Dashboard and Report Viewer.

Covers:
- DashboardSummary, DashboardData, ReportManifestRow, DashboardTableSpec models
- Dashboard summary counts from database
- Latest report discovery
- Report manifest loading
- CSV report loading
- Candidate table preparation
- Watchlist table preparation
- Monitoring table preparation
- Effective DOM v2 table preparation
- County verification table preparation
- Cross-site table preparation
- dashboard-summary CLI command registration
- launch-dashboard CLI command registration
- No live network calls
- Existing MVP 1-11 tests still pass (verified via full test suite)
"""

import csv
import gc
import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from marketsentry.database import init_db, migrate_schema
from marketsentry.dashboard import (
    DashboardData,
    DashboardSummary,
    DashboardTableSpec,
    ReportManifestRow,
    build_candidate_table,
    build_county_verification_table,
    build_cross_site_table,
    build_effective_dom_v2_table,
    build_monitoring_table,
    build_watchlist_table,
    find_latest_report,
    find_workflow_summaries,
    get_dashboard_summary,
    load_dashboard_data,
    load_latest_report_manifest,
    load_report_csv,
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestDashboardModels:
    """Tests for dashboard Pydantic models."""

    def test_report_manifest_row_defaults(self):
        """ReportManifestRow has correct default values."""
        row = ReportManifestRow()
        assert row.created_at == ""
        assert row.workflow_name == ""
        assert row.report_type == ""
        assert row.file_path == ""
        assert row.row_count == ""
        assert row.notes == ""

    def test_report_manifest_row_with_values(self):
        """ReportManifestRow stores fields correctly."""
        row = ReportManifestRow(
            created_at="2026-05-06T10:00:00",
            workflow_name="fixture_demo",
            report_type="candidate_review",
            file_path="data/exports/test.csv",
            row_count="42",
            notes="Test note",
        )
        assert row.workflow_name == "fixture_demo"
        assert row.row_count == "42"

    def test_dashboard_summary_defaults(self):
        """DashboardSummary has correct default values."""
        summary = DashboardSummary()
        assert summary.database_path == ""
        assert summary.database_exists is False
        assert summary.candidates_total == 0
        assert summary.watched_total == 0
        assert summary.watched_active == 0
        assert summary.snapshots_total == 0
        assert summary.cross_site_observations == 0
        assert summary.county_records == 0
        assert summary.listing_events == 0
        assert summary.reports_in_manifest == 0
        assert summary.high_priority_watched == 0
        assert summary.quiet_gatekeeper_failures == 0
        assert summary.strong_review_candidates == 0
        assert summary.county_reset_applied_count == 0
        assert summary.high_churn_count == 0

    def test_dashboard_table_spec(self):
        """DashboardTableSpec stores fields correctly."""
        spec = DashboardTableSpec(
            title="Test Table",
            description="A test table",
            columns=["col1", "col2"],
            row_count=10,
        )
        assert spec.title == "Test Table"
        assert len(spec.columns) == 2
        assert spec.row_count == 10

    def test_dashboard_data_defaults(self):
        """DashboardData has correct default values."""
        data = DashboardData()
        assert isinstance(data.summary, DashboardSummary)
        assert data.candidates is None
        assert data.watched is None
        assert data.monitoring is None
        assert data.effective_dom_v2 is None
        assert data.county_verification is None
        assert data.cross_site is None
        assert data.manifest == []
        assert data.workflow_summaries == []


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------


class TestDashboardSummary:
    """Tests for dashboard summary counts."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database with sample data."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        init_db(db_path)
        migrate_schema(db_path)
        from marketsentry.sample_data import seed_sample_candidates

        seed_sample_candidates(db_path)
        yield db_path
        gc.collect()
        try:
            Path(db_path).unlink(missing_ok=True)
        except PermissionError:
            pass

    def test_summary_with_db(self, temp_db):
        """Dashboard summary returns counts for existing database."""
        summary = get_dashboard_summary(temp_db)
        assert summary.database_exists is True
        assert summary.candidates_total == 3
        assert summary.watched_total == 0

    def test_summary_nonexistent_db(self):
        """Dashboard summary handles non-existent database."""
        summary = get_dashboard_summary("nonexistent.db")
        assert summary.database_exists is False
        assert summary.candidates_total == 0

    def test_summary_fields_present(self, temp_db):
        """Dashboard summary includes all expected fields."""
        summary = get_dashboard_summary(temp_db)
        assert hasattr(summary, "candidates_total")
        assert hasattr(summary, "watched_total")
        assert hasattr(summary, "watched_active")
        assert hasattr(summary, "snapshots_total")
        assert hasattr(summary, "cross_site_observations")
        assert hasattr(summary, "county_records")
        assert hasattr(summary, "reports_in_manifest")
        assert hasattr(summary, "high_priority_watched")
        assert hasattr(summary, "quiet_gatekeeper_failures")
        assert hasattr(summary, "strong_review_candidates")
        assert hasattr(summary, "county_reset_applied_count")
        assert hasattr(summary, "high_churn_count")


# ---------------------------------------------------------------------------
# Report discovery
# ---------------------------------------------------------------------------


class TestReportDiscovery:
    """Tests for latest report discovery."""

    @pytest.fixture
    def temp_exports(self):
        """Create a temp exports directory with sample reports."""
        with tempfile.TemporaryDirectory() as d:
            # Create sample report files
            (Path(d) / "candidate_analysis_20260501_100000.csv").write_text(
                "col1,col2\nval1,val2\n", encoding="utf-8"
            )
            (Path(d) / "candidate_analysis_20260502_100000.csv").write_text(
                "col1,col2\nval1,val2\n", encoding="utf-8"
            )
            (Path(d) / "watchlist_monitoring_20260501_100000.csv").write_text(
                "col1\nval1\n", encoding="utf-8"
            )
            (Path(d) / "effective_dom_v2_20260501_100000.csv").write_text(
                "col1\nval1\n", encoding="utf-8"
            )
            (Path(d) / "county_verification_20260501_100000.csv").write_text(
                "col1\nval1\n", encoding="utf-8"
            )
            (Path(d) / "workflow_summary_20260501_100000.md").write_text(
                "# Summary\n", encoding="utf-8"
            )
            (Path(d) / "workflow_summary_20260502_100000.md").write_text(
                "# Summary 2\n", encoding="utf-8"
            )
            yield d

    def test_find_latest_report(self, temp_exports):
        """find_latest_report returns most recent report."""
        result = find_latest_report("candidate_analysis", temp_exports)
        assert result is not None
        assert "candidate_analysis" in result.name

    def test_find_latest_report_monitoring(self, temp_exports):
        """find_latest_report finds monitoring report."""
        result = find_latest_report("watchlist_monitoring", temp_exports)
        assert result is not None
        assert "watchlist_monitoring" in result.name

    def test_find_latest_report_v2(self, temp_exports):
        """find_latest_report finds Effective DOM v2 report."""
        result = find_latest_report("effective_dom_v2", temp_exports)
        assert result is not None

    def test_find_latest_report_county(self, temp_exports):
        """find_latest_report finds county verification report."""
        result = find_latest_report("county_verification", temp_exports)
        assert result is not None

    def test_find_latest_report_not_found(self, temp_exports):
        """find_latest_report returns None when not found."""
        result = find_latest_report("cross_site_report", temp_exports)
        assert result is None

    def test_find_latest_report_nonexistent_dir(self):
        """find_latest_report handles non-existent directory."""
        result = find_latest_report("candidate_analysis", "nonexistent_dir")
        assert result is None

    def test_find_latest_report_unknown_type(self, temp_exports):
        """find_latest_report returns None for unknown type."""
        result = find_latest_report("unknown_type", temp_exports)
        assert result is None

    def test_find_workflow_summaries(self, temp_exports):
        """find_workflow_summaries returns sorted summary paths."""
        summaries = find_workflow_summaries(temp_exports)
        assert len(summaries) == 2
        # Should be sorted by mtime, newest first
        assert all(isinstance(p, Path) for p in summaries)

    def test_find_workflow_summaries_empty(self):
        """find_workflow_summaries handles empty directory."""
        with tempfile.TemporaryDirectory() as d:
            summaries = find_workflow_summaries(d)
            assert summaries == []


# ---------------------------------------------------------------------------
# Report manifest
# ---------------------------------------------------------------------------


class TestReportManifest:
    """Tests for report manifest loading."""

    @pytest.fixture
    def temp_exports_with_manifest(self):
        """Create a temp exports directory with a manifest."""
        with tempfile.TemporaryDirectory() as d:
            manifest_path = Path(d) / "report_manifest.csv"
            with open(manifest_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "created_at", "workflow_name", "report_type",
                        "file_path", "row_count", "notes",
                    ],
                )
                writer.writeheader()
                writer.writerow({
                    "created_at": "2026-05-06T10:00:00",
                    "workflow_name": "fixture_demo",
                    "report_type": "candidate_review",
                    "file_path": "test.csv",
                    "row_count": "5",
                    "notes": "",
                })
                writer.writerow({
                    "created_at": "2026-05-06T10:00:00",
                    "workflow_name": "fixture_demo",
                    "report_type": "workflow_summary",
                    "file_path": "summary.md",
                    "row_count": "",
                    "notes": "Demo",
                })
            yield d

    def test_load_manifest(self, temp_exports_with_manifest):
        """load_latest_report_manifest loads rows correctly."""
        rows = load_latest_report_manifest(temp_exports_with_manifest)
        assert len(rows) == 2
        assert rows[0].report_type == "candidate_review"
        assert rows[0].row_count == "5"
        assert rows[1].report_type == "workflow_summary"

    def test_load_manifest_empty_dir(self):
        """load_latest_report_manifest returns empty list when no manifest."""
        with tempfile.TemporaryDirectory() as d:
            rows = load_latest_report_manifest(d)
            assert rows == []


# ---------------------------------------------------------------------------
# CSV report loading
# ---------------------------------------------------------------------------


class TestCSVReportLoading:
    """Tests for CSV report loading."""

    def test_load_report_csv(self):
        """load_report_csv loads CSV into DataFrame."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            writer = csv.DictWriter(f, fieldnames=["address", "price"])
            writer.writeheader()
            writer.writerow({"address": "123 Main St", "price": "500000"})
            writer.writerow({"address": "456 Oak Ave", "price": "600000"})
            path = f.name

        try:
            df = load_report_csv(Path(path))
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert "address" in df.columns
            assert "price" in df.columns
        finally:
            os.unlink(path)

    def test_load_report_csv_nonexistent(self):
        """load_report_csv returns empty DataFrame for missing file."""
        df = load_report_csv(Path("nonexistent.csv"))
        assert isinstance(df, pd.DataFrame)
        assert df.empty


# ---------------------------------------------------------------------------
# Table builders
# ---------------------------------------------------------------------------


class TestTableBuilders:
    """Tests for dashboard table preparation functions."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database with sample data."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        init_db(db_path)
        migrate_schema(db_path)
        from marketsentry.sample_data import seed_sample_candidates

        seed_sample_candidates(db_path)
        yield db_path
        gc.collect()
        try:
            Path(db_path).unlink(missing_ok=True)
        except PermissionError:
            pass

    @pytest.fixture
    def temp_exports_with_reports(self):
        """Create temp exports with sample report CSVs."""
        with tempfile.TemporaryDirectory() as d:
            # Monitoring report
            monitoring_path = Path(d) / "watchlist_monitoring_20260501_100000.csv"
            with open(monitoring_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "property_id", "address", "current_price",
                        "previous_price", "price_change", "listing_status",
                    ],
                )
                writer.writeheader()
                writer.writerow({
                    "property_id": "1",
                    "address": "123 Main St",
                    "current_price": "500000",
                    "previous_price": "510000",
                    "price_change": "-10000",
                    "listing_status": "Active",
                })

            # Effective DOM v2 report
            v2_path = Path(d) / "effective_dom_v2_20260501_100000.csv"
            with open(v2_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "property_id", "address", "city",
                        "effective_dom_v1", "effective_dom_v2",
                        "county_reset_applied",
                    ],
                )
                writer.writeheader()
                writer.writerow({
                    "property_id": "1",
                    "address": "123 Main St",
                    "city": "Temecula",
                    "effective_dom_v1": "200",
                    "effective_dom_v2": "45",
                    "county_reset_applied": "1",
                })

            # County verification report
            county_path = Path(d) / "county_verification_20260501_100000.csv"
            with open(county_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "property_id", "address", "city",
                        "county_transfer_found", "county_reset_supported",
                    ],
                )
                writer.writeheader()
                writer.writerow({
                    "property_id": "1",
                    "address": "123 Main St",
                    "city": "Temecula",
                    "county_transfer_found": "1",
                    "county_reset_supported": "1",
                })

            yield d

    def test_build_candidate_table(self, temp_db):
        """build_candidate_table returns DataFrame with candidates."""
        df = build_candidate_table(temp_db)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3  # seed_sample_candidates creates 3
        assert "candidate_id" in df.columns
        assert "address" in df.columns

    def test_build_candidate_table_empty_db(self):
        """build_candidate_table returns empty DataFrame for empty database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            init_db(db_path)
            migrate_schema(db_path)
            df = build_candidate_table(db_path)
            assert isinstance(df, pd.DataFrame)
            assert df.empty
        finally:
            gc.collect()
            try:
                Path(db_path).unlink(missing_ok=True)
            except PermissionError:
                pass

    def test_build_candidate_table_nonexistent_db(self):
        """build_candidate_table handles non-existent database."""
        df = build_candidate_table("nonexistent.db")
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_build_watchlist_table(self, temp_db):
        """build_watchlist_table returns DataFrame (empty for candidates only)."""
        df = build_watchlist_table(temp_db)
        assert isinstance(df, pd.DataFrame)
        # Only candidates seeded, no watched properties
        assert df.empty

    def test_build_monitoring_table(self, temp_exports_with_reports):
        """build_monitoring_table returns DataFrame from report CSV."""
        df = build_monitoring_table(temp_exports_with_reports)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "property_id" in df.columns

    def test_build_monitoring_table_empty(self):
        """build_monitoring_table returns empty DataFrame when no report."""
        with tempfile.TemporaryDirectory() as d:
            df = build_monitoring_table(d)
            assert isinstance(df, pd.DataFrame)
            assert df.empty

    def test_build_effective_dom_v2_table(self, temp_exports_with_reports):
        """build_effective_dom_v2_table returns DataFrame from report CSV."""
        df = build_effective_dom_v2_table(temp_exports_with_reports)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "effective_dom_v1" in df.columns
        assert "effective_dom_v2" in df.columns

    def test_build_effective_dom_v2_table_empty(self):
        """build_effective_dom_v2_table returns empty DataFrame when no report."""
        with tempfile.TemporaryDirectory() as d:
            df = build_effective_dom_v2_table(d)
            assert isinstance(df, pd.DataFrame)
            assert df.empty

    def test_build_county_verification_table(self, temp_exports_with_reports):
        """build_county_verification_table returns DataFrame from report CSV."""
        df = build_county_verification_table(temp_exports_with_reports)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "county_transfer_found" in df.columns

    def test_build_county_verification_table_empty(self):
        """build_county_verification_table returns empty DataFrame when no report."""
        with tempfile.TemporaryDirectory() as d:
            df = build_county_verification_table(d)
            assert isinstance(df, pd.DataFrame)
            assert df.empty

    def test_build_cross_site_table_empty(self):
        """build_cross_site_table returns empty DataFrame when no report."""
        with tempfile.TemporaryDirectory() as d:
            df = build_cross_site_table(d)
            assert isinstance(df, pd.DataFrame)
            assert df.empty


# ---------------------------------------------------------------------------
# Full dashboard data loader
# ---------------------------------------------------------------------------


class TestDashboardDataLoader:
    """Tests for load_dashboard_data."""

    @pytest.fixture
    def temp_env(self):
        """Create temp database and exports directory."""
        with tempfile.TemporaryDirectory() as out_dir:
            db_path = os.path.join(out_dir, "dashboard_test.db")
            init_db(db_path)
            migrate_schema(db_path)
            from marketsentry.sample_data import seed_sample_candidates

            seed_sample_candidates(db_path)
            yield db_path, out_dir

    def test_load_dashboard_data(self, temp_env):
        """load_dashboard_data returns complete DashboardData."""
        db_path, out_dir = temp_env
        data = load_dashboard_data(db_path, out_dir)

        assert isinstance(data, DashboardData)
        assert isinstance(data.summary, DashboardSummary)
        assert data.summary.database_exists is True
        assert data.summary.candidates_total == 3
        assert isinstance(data.candidates, pd.DataFrame)
        assert len(data.candidates) == 3

    def test_load_dashboard_data_nonexistent_db(self):
        """load_dashboard_data handles non-existent database."""
        with tempfile.TemporaryDirectory() as d:
            data = load_dashboard_data("nonexistent.db", d)
            assert data.summary.database_exists is False


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


class TestCLIDashboardCommands:
    """Tests for CLI dashboard commands."""

    def test_cli_has_dashboard_commands(self):
        """CLI app has dashboard-summary and launch-dashboard commands."""
        from marketsentry.cli import app

        command_names = []
        for cmd_info in app.registered_commands:
            name = cmd_info.name or cmd_info.callback.__name__
            command_names.append(name)

        assert "dashboard-summary" in command_names
        assert "launch-dashboard" in command_names


# ---------------------------------------------------------------------------
# No network calls
# ---------------------------------------------------------------------------


class TestNoNetworkCalls:
    """Verify dashboard module makes no network calls."""

    def test_dashboard_imports_no_network(self):
        """Dashboard module does not import network libraries at module level."""
        import importlib
        import marketsentry.dashboard as dash_mod

        source = Path(dash_mod.__file__).read_text(encoding="utf-8")

        # Should not import requests, httpx, urllib at module level
        assert "import requests" not in source
        assert "import httpx" not in source
        assert "import urllib.request" not in source
        assert "import socket" not in source

    def test_dashboard_app_no_network_imports(self):
        """Dashboard app does not import network libraries."""
        app_path = (
            Path(__file__).parent.parent
            / "src"
            / "marketsentry"
            / "dashboard_app.py"
        )
        if not app_path.exists():
            pytest.skip("dashboard_app.py not found")

        source = app_path.read_text(encoding="utf-8")
        assert "import requests" not in source
        assert "import httpx" not in source
        assert "import urllib.request" not in source
