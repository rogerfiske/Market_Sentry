"""Tests for Prompt 011A: Export Path Configuration Stabilization.

Verifies that:
- Config has canonical data_exports_dir attribute.
- Config.export_path property alias returns data_exports_dir.
- No module references a missing Config attribute.
- Report modules work with default paths (no explicit output_path).
- Report modules work with explicit output paths.
- Workflow modules still use explicit paths successfully.
"""

import ast
import gc
import os
import tempfile
from pathlib import Path

import pytest

from marketsentry.config import Config, config
from marketsentry.database import init_db, migrate_schema


class TestConfigExportPath:
    """Tests for export path configuration consistency."""

    def test_config_has_data_exports_dir(self):
        """Config has canonical data_exports_dir attribute."""
        assert hasattr(config, "data_exports_dir")
        assert isinstance(config.data_exports_dir, str)
        assert config.data_exports_dir == "data/exports"

    def test_config_export_path_alias(self):
        """Config.export_path property returns data_exports_dir."""
        assert hasattr(config, "export_path")
        assert config.export_path == config.data_exports_dir

    def test_config_export_path_is_property(self):
        """Config.export_path is a property, not a stored field."""
        assert isinstance(Config.__dict__["export_path"], property)

    def test_config_from_env_has_export_path(self):
        """Config created from env has working export_path alias."""
        cfg = Config.from_env()
        assert cfg.export_path == cfg.data_exports_dir

    def test_config_custom_exports_dir(self):
        """Custom data_exports_dir is reflected in export_path alias."""
        cfg = Config(data_exports_dir="custom/exports")
        assert cfg.export_path == "custom/exports"
        assert cfg.data_exports_dir == "custom/exports"


class TestNoMissingConfigAttributes:
    """Verify no source module references undefined Config attributes."""

    def test_no_config_export_path_references_in_source(self):
        """No source file references config.export_path (all replaced with data_exports_dir)."""
        src_dir = Path(__file__).parent.parent / "src" / "marketsentry"
        violations = []

        for py_file in src_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            # Check for config.export_path but allow the property definition in config.py
            if py_file.name == "config.py":
                continue
            if "config.export_path" in content:
                violations.append(str(py_file.name))

        assert violations == [], (
            f"Files still referencing config.export_path: {violations}"
        )

    def test_config_module_defines_export_path_property(self):
        """config.py defines export_path as a property."""
        src_dir = Path(__file__).parent.parent / "src" / "marketsentry"
        config_py = src_dir / "config.py"
        content = config_py.read_text(encoding="utf-8")
        assert "def export_path" in content
        assert "@property" in content


class TestReportDefaultPaths:
    """Tests that report modules work with default paths (no explicit output_path)."""

    @pytest.fixture
    def temp_db_with_data(self):
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

    def test_monitoring_report_default_path(self, temp_db_with_data):
        """Watchlist monitoring report works with default path."""
        from marketsentry.monitoring_report import export_watchlist_monitoring_report

        # Should not raise AttributeError for config.export_path
        row_count = export_watchlist_monitoring_report(
            database_path=temp_db_with_data
        )
        assert isinstance(row_count, int)

    def test_county_verification_report_default_path(self, temp_db_with_data):
        """County verification report works with default path."""
        from marketsentry.county_verification_report import (
            export_county_verification_report,
        )

        row_count = export_county_verification_report(
            database_path=temp_db_with_data
        )
        assert isinstance(row_count, int)

    def test_effective_dom_v2_report_default_path(self, temp_db_with_data):
        """Effective DOM v2 report works with default path."""
        from marketsentry.effective_dom_v2_report import export_effective_dom_v2_report

        row_count = export_effective_dom_v2_report(
            database_path=temp_db_with_data
        )
        assert isinstance(row_count, int)

    def test_candidate_analysis_report_default_path(self, temp_db_with_data):
        """Candidate analysis report works with default path."""
        from marketsentry.candidate_report import export_candidate_analysis_report

        output_path = export_candidate_analysis_report(
            database_path=temp_db_with_data
        )
        assert isinstance(output_path, str)
        assert Path(output_path).exists()


class TestReportExplicitPaths:
    """Tests that report modules work with explicit output paths."""

    @pytest.fixture
    def temp_db_with_data(self):
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
    def temp_dir(self):
        """Create a temporary directory for output."""
        with tempfile.TemporaryDirectory() as d:
            yield d

    def test_monitoring_report_explicit_path(self, temp_db_with_data, temp_dir):
        """Watchlist monitoring report runs without AttributeError on explicit path."""
        from marketsentry.monitoring_report import export_watchlist_monitoring_report

        output_path = os.path.join(temp_dir, "test_monitoring.csv")
        # No watched properties exist, so returns 0 and does not write file.
        # The key verification is no AttributeError on config.export_path.
        row_count = export_watchlist_monitoring_report(
            output_path, temp_db_with_data
        )
        assert isinstance(row_count, int)
        assert row_count == 0

    def test_county_verification_report_explicit_path(
        self, temp_db_with_data, temp_dir
    ):
        """County verification report runs without AttributeError on explicit path."""
        from marketsentry.county_verification_report import (
            export_county_verification_report,
        )

        output_path = os.path.join(temp_dir, "test_county.csv")
        row_count = export_county_verification_report(
            output_path, temp_db_with_data
        )
        assert isinstance(row_count, int)
        assert row_count == 0

    def test_effective_dom_v2_report_explicit_path(
        self, temp_db_with_data, temp_dir
    ):
        """Effective DOM v2 report runs without AttributeError on explicit path."""
        from marketsentry.effective_dom_v2_report import export_effective_dom_v2_report

        output_path = os.path.join(temp_dir, "test_v2.csv")
        row_count = export_effective_dom_v2_report(
            output_path, temp_db_with_data
        )
        assert isinstance(row_count, int)
        assert row_count == 0

    def test_candidate_analysis_report_explicit_path(
        self, temp_db_with_data, temp_dir
    ):
        """Candidate analysis report works with explicit path."""
        from marketsentry.candidate_report import export_candidate_analysis_report

        output_path = os.path.join(temp_dir, "test_analysis.csv")
        result_path = export_candidate_analysis_report(
            temp_db_with_data, output_path
        )
        assert isinstance(result_path, str)
        assert Path(result_path).exists()


class TestWorkflowExplicitPaths:
    """Tests that workflow modules still use explicit paths successfully."""

    @pytest.fixture
    def temp_env(self):
        """Create temp output directory and demo database path."""
        with tempfile.TemporaryDirectory() as out_dir:
            db_path = os.path.join(out_dir, "export_path_test.db")
            yield db_path, out_dir

    def test_fixture_demo_workflow_uses_explicit_paths(self, temp_env):
        """Fixture demo workflow generates reports with explicit output_dir."""
        from marketsentry.workflow import run_full_fixture_demo_workflow

        db_path, out_dir = temp_env
        result = run_full_fixture_demo_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        # All output files should exist in the explicit output directory
        for out_file in result.output_files:
            assert Path(out_file.file_path).exists(), (
                f"Output file not found: {out_file.file_path}"
            )

        # Summary should exist
        assert result.summary_file is not None
        assert Path(result.summary_file).exists()
