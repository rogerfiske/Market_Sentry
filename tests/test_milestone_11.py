"""Tests for Milestone 11: End-to-End Operating Workflow and Runbook.

Covers:
- WorkflowStepResult and WorkflowRunResult models
- Workflow summary file generation
- Report manifest append/update
- workflow-status count collection
- run_initial_review_workflow with sample/local fixtures
- run_watchlist_refresh_workflow with sample/local fixtures
- run_full_fixture_demo_workflow deterministic behavior
- CLI workflow commands where practical
- No live network call behavior
- Existing MVP 1-10 tests still pass (verified via full test suite)
"""

import csv
import gc
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from marketsentry.database import (
    get_table_count,
    init_db,
    migrate_schema,
    table_exists,
)
from marketsentry.models import (
    WorkflowError,
    WorkflowOutputFile,
    WorkflowRunResult,
    WorkflowStepResult,
    WorkflowWarning,
)


class TestWorkflowModels:
    """Tests for workflow result Pydantic models."""

    def test_workflow_step_result_defaults(self):
        """WorkflowStepResult has correct default values."""
        step = WorkflowStepResult(step_name="test_step")
        assert step.step_name == "test_step"
        assert step.status == "pending"
        assert step.started_at is None
        assert step.completed_at is None
        assert step.duration_seconds is None
        assert step.records_processed == 0
        assert step.records_created == 0
        assert step.records_updated == 0
        assert step.records_skipped == 0
        assert step.warnings == []
        assert step.errors == []
        assert step.output_files == []
        assert step.notes == ""

    def test_workflow_step_result_with_values(self):
        """WorkflowStepResult stores all fields correctly."""
        now = datetime.now()
        step = WorkflowStepResult(
            step_name="import_data",
            status="completed",
            started_at=now,
            completed_at=now,
            duration_seconds=1.5,
            records_processed=10,
            records_created=5,
            records_updated=3,
            records_skipped=2,
            warnings=["Warning 1"],
            errors=[],
            output_files=[WorkflowOutputFile(file_path="test.csv", report_type="test")],
            notes="Test note",
        )
        assert step.records_processed == 10
        assert step.records_created == 5
        assert len(step.output_files) == 1
        assert step.output_files[0].file_path == "test.csv"

    def test_workflow_run_result_defaults(self):
        """WorkflowRunResult has correct default values."""
        result = WorkflowRunResult(workflow_name="test_workflow")
        assert result.workflow_name == "test_workflow"
        assert result.database_path == ""
        assert result.started_at is None
        assert result.steps == []
        assert result.output_files == []
        assert result.warnings == []
        assert result.errors == []
        assert result.summary_file is None
        assert result.next_recommended_action == ""

    def test_workflow_run_result_with_steps(self):
        """WorkflowRunResult stores steps correctly."""
        result = WorkflowRunResult(
            workflow_name="initial_review",
            database_path="test.db",
            started_at=datetime.now(),
        )
        step1 = WorkflowStepResult(step_name="step1", status="completed")
        step2 = WorkflowStepResult(step_name="step2", status="skipped")
        result.steps.append(step1)
        result.steps.append(step2)
        assert len(result.steps) == 2
        assert result.steps[0].step_name == "step1"
        assert result.steps[1].status == "skipped"

    def test_workflow_output_file(self):
        """WorkflowOutputFile stores all fields correctly."""
        out = WorkflowOutputFile(
            file_path="data/exports/test.csv",
            report_type="candidate_review",
            row_count=42,
            notes="Test output",
        )
        assert out.file_path == "data/exports/test.csv"
        assert out.report_type == "candidate_review"
        assert out.row_count == 42

    def test_workflow_warning(self):
        """WorkflowWarning stores fields correctly."""
        w = WorkflowWarning(step_name="import", message="No data found")
        assert w.step_name == "import"
        assert w.message == "No data found"

    def test_workflow_error(self):
        """WorkflowError stores fields correctly."""
        e = WorkflowError(step_name="parse", message="File not found")
        assert e.step_name == "parse"
        assert e.message == "File not found"


class TestWorkflowSummary:
    """Tests for workflow summary file generation."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for output."""
        with tempfile.TemporaryDirectory() as d:
            yield d

    def test_generate_workflow_summary_creates_file(self, temp_dir):
        """generate_workflow_summary creates a markdown file."""
        from marketsentry.workflow import generate_workflow_summary

        result = WorkflowRunResult(
            workflow_name="test_workflow",
            database_path="test.db",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration_seconds=1.0,
        )
        step = WorkflowStepResult(
            step_name="test_step",
            status="completed",
            records_processed=5,
        )
        result.steps.append(step)
        result.next_recommended_action = "Review the output."

        summary_path = generate_workflow_summary(result, temp_dir)

        assert Path(summary_path).exists()
        assert summary_path.endswith(".md")

        content = Path(summary_path).read_text(encoding="utf-8")
        assert "test_workflow" in content
        assert "test_step" in content
        assert "completed" in content
        assert "Review the output" in content
        assert "not a purchase recommendation" in content.lower()

    def test_generate_workflow_summary_includes_errors(self, temp_dir):
        """Workflow summary includes error details."""
        from marketsentry.workflow import generate_workflow_summary

        result = WorkflowRunResult(
            workflow_name="error_workflow",
            database_path="test.db",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration_seconds=0.5,
        )
        result.errors.append(WorkflowError(step_name="step1", message="Something broke"))

        summary_path = generate_workflow_summary(result, temp_dir)
        content = Path(summary_path).read_text(encoding="utf-8")
        assert "Something broke" in content

    def test_generate_workflow_summary_includes_output_files(self, temp_dir):
        """Workflow summary includes output file listing."""
        from marketsentry.workflow import generate_workflow_summary

        result = WorkflowRunResult(
            workflow_name="report_workflow",
            database_path="test.db",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration_seconds=0.5,
        )
        result.output_files.append(WorkflowOutputFile(
            file_path="test_report.csv",
            report_type="candidate_review",
            row_count=10,
        ))

        summary_path = generate_workflow_summary(result, temp_dir)
        content = Path(summary_path).read_text(encoding="utf-8")
        assert "test_report.csv" in content
        assert "candidate_review" in content


class TestReportManifest:
    """Tests for report manifest append/update."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for output."""
        with tempfile.TemporaryDirectory() as d:
            yield d

    def test_append_report_manifest_creates_file(self, temp_dir):
        """append_report_manifest creates manifest CSV if it does not exist."""
        from marketsentry.workflow import append_report_manifest

        result = WorkflowRunResult(
            workflow_name="test_workflow",
            database_path="test.db",
        )
        result.output_files.append(WorkflowOutputFile(
            file_path="report.csv",
            report_type="candidate_review",
            row_count=5,
        ))
        result.summary_file = "summary.md"

        manifest_path = append_report_manifest(result, temp_dir)
        assert Path(manifest_path).exists()

        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should have 2 rows: output file + summary
        assert len(rows) == 2
        assert rows[0]["report_type"] == "candidate_review"
        assert rows[0]["file_path"] == "report.csv"
        assert rows[0]["row_count"] == "5"
        assert rows[1]["report_type"] == "workflow_summary"

    def test_append_report_manifest_appends_to_existing(self, temp_dir):
        """append_report_manifest appends to existing manifest."""
        from marketsentry.workflow import append_report_manifest

        # First append
        result1 = WorkflowRunResult(workflow_name="workflow1", database_path="test.db")
        result1.output_files.append(WorkflowOutputFile(
            file_path="report1.csv", report_type="candidate_review", row_count=3
        ))
        append_report_manifest(result1, temp_dir)

        # Second append
        result2 = WorkflowRunResult(workflow_name="workflow2", database_path="test.db")
        result2.output_files.append(WorkflowOutputFile(
            file_path="report2.csv", report_type="watchlist_monitoring", row_count=7
        ))
        manifest_path = append_report_manifest(result2, temp_dir)

        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should have rows from both appends
        assert len(rows) >= 2
        workflow_names = {row["workflow_name"] for row in rows}
        assert "workflow1" in workflow_names
        assert "workflow2" in workflow_names

    def test_manifest_has_correct_columns(self, temp_dir):
        """Report manifest CSV has all required columns."""
        from marketsentry.workflow import append_report_manifest

        result = WorkflowRunResult(workflow_name="test", database_path="test.db")
        result.output_files.append(WorkflowOutputFile(
            file_path="r.csv", report_type="test_type", row_count=1
        ))
        manifest_path = append_report_manifest(result, temp_dir)

        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

        expected = ["created_at", "workflow_name", "report_type", "file_path", "row_count", "notes"]
        for col in expected:
            assert col in fieldnames


class TestWorkflowStatus:
    """Tests for workflow status count collection."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        init_db(db_path)
        migrate_schema(db_path)
        yield db_path
        gc.collect()
        try:
            Path(db_path).unlink(missing_ok=True)
        except PermissionError:
            pass

    def test_get_workflow_status_with_db(self, temp_db):
        """get_workflow_status returns table counts for existing database."""
        from marketsentry.workflow import get_workflow_status

        status = get_workflow_status(temp_db)

        assert status["database_exists"] is True
        assert "tables" in status
        assert "candidate_review_queue" in status["tables"]
        assert "watched_properties" in status["tables"]
        assert "listing_events" in status["tables"]
        assert "property_observation_snapshots" in status["tables"]

    def test_get_workflow_status_nonexistent_db(self):
        """get_workflow_status handles non-existent database."""
        from marketsentry.workflow import get_workflow_status

        status = get_workflow_status("nonexistent_db_path.db")
        assert status["database_exists"] is False

    def test_get_workflow_status_returns_zero_counts_for_empty_db(self, temp_db):
        """Workflow status returns 0 counts for empty tables."""
        from marketsentry.workflow import get_workflow_status

        status = get_workflow_status(temp_db)
        for table_name, count in status["tables"].items():
            assert count == 0


class TestInitialReviewWorkflow:
    """Tests for run_initial_review_workflow."""

    @pytest.fixture
    def temp_env(self):
        """Create temp database and output directory."""
        with tempfile.TemporaryDirectory() as out_dir:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
                db_path = f.name
            yield db_path, out_dir
            gc.collect()
            try:
                Path(db_path).unlink(missing_ok=True)
            except PermissionError:
                pass

    def test_initial_review_workflow_runs_with_no_inputs(self, temp_env):
        """Initial review workflow runs with no optional inputs (all steps skip)."""
        from marketsentry.workflow import run_initial_review_workflow

        db_path, out_dir = temp_env
        result = run_initial_review_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        assert result.workflow_name == "initial_review"
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration_seconds is not None
        assert len(result.steps) == 8
        assert result.next_recommended_action != ""
        assert result.summary_file is not None
        assert Path(result.summary_file).exists()

    def test_initial_review_workflow_db_initialized(self, temp_env):
        """Initial review workflow initializes the database."""
        from marketsentry.workflow import run_initial_review_workflow

        db_path, out_dir = temp_env
        result = run_initial_review_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        db_step = result.steps[0]
        assert db_step.step_name == "initialize_database"
        assert db_step.status == "completed"

        # Verify DB actually initialized
        assert Path(db_path).exists()
        assert table_exists("candidate_review_queue", db_path)

    def test_initial_review_skips_missing_inputs(self, temp_env):
        """Initial review workflow skips steps when input files/dirs are missing."""
        from marketsentry.workflow import run_initial_review_workflow

        db_path, out_dir = temp_env
        result = run_initial_review_workflow(
            database_path=db_path,
            redfin_urls_file="nonexistent.csv",
            redfin_search_dir="nonexistent_dir",
            redfin_details_dir="nonexistent_dir",
            output_dir=out_dir,
        )

        # URL import should be skipped
        url_step = [s for s in result.steps if s.step_name == "import_redfin_urls"][0]
        assert url_step.status == "skipped"

        # Search fixture parsing should be skipped
        search_step = [s for s in result.steps if s.step_name == "parse_redfin_search_fixtures"][0]
        assert search_step.status == "skipped"

    def test_initial_review_generates_reports(self, temp_env):
        """Initial review workflow generates review CSV and analysis report."""
        from marketsentry.workflow import run_initial_review_workflow
        from marketsentry.sample_data import seed_sample_candidates

        db_path, out_dir = temp_env
        init_db(db_path)
        migrate_schema(db_path)
        seed_sample_candidates(db_path)

        result = run_initial_review_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        # Should have output files
        assert len(result.output_files) >= 2
        report_types = [f.report_type for f in result.output_files]
        assert "candidate_review" in report_types
        assert "candidate_analysis" in report_types


class TestWatchlistRefreshWorkflow:
    """Tests for run_watchlist_refresh_workflow."""

    @pytest.fixture
    def temp_env(self):
        """Create temp database and output directory."""
        with tempfile.TemporaryDirectory() as out_dir:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
                db_path = f.name
            yield db_path, out_dir
            gc.collect()
            try:
                Path(db_path).unlink(missing_ok=True)
            except PermissionError:
                pass

    def test_watchlist_refresh_runs_with_no_inputs(self, temp_env):
        """Watchlist refresh workflow runs with no optional inputs."""
        from marketsentry.workflow import run_watchlist_refresh_workflow

        db_path, out_dir = temp_env
        result = run_watchlist_refresh_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        assert result.workflow_name == "watchlist_refresh"
        assert result.started_at is not None
        assert result.completed_at is not None
        assert len(result.steps) == 9
        assert result.summary_file is not None
        assert Path(result.summary_file).exists()

    def test_watchlist_refresh_skips_missing_inputs(self, temp_env):
        """Watchlist refresh skips steps when optional inputs are missing."""
        from marketsentry.workflow import run_watchlist_refresh_workflow

        db_path, out_dir = temp_env
        result = run_watchlist_refresh_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        # Cross-site step should be skipped
        cs_step = [s for s in result.steps if s.step_name == "parse_cross_site_fixtures"][0]
        assert cs_step.status == "skipped"

        # County step should be skipped
        county_step = [s for s in result.steps if s.step_name == "import_county_records"][0]
        assert county_step.status == "skipped"

    def test_watchlist_refresh_db_initialized(self, temp_env):
        """Watchlist refresh initializes the database as first step."""
        from marketsentry.workflow import run_watchlist_refresh_workflow

        db_path, out_dir = temp_env
        result = run_watchlist_refresh_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        db_step = result.steps[0]
        assert db_step.step_name == "initialize_database"
        assert db_step.status == "completed"


class TestFixtureDemoWorkflow:
    """Tests for run_full_fixture_demo_workflow."""

    @pytest.fixture
    def temp_env(self):
        """Create temp output directory and demo database path."""
        with tempfile.TemporaryDirectory() as out_dir:
            db_path = os.path.join(out_dir, "demo_test.db")
            yield db_path, out_dir

    def test_fixture_demo_runs_end_to_end(self, temp_env):
        """Fixture demo workflow runs all steps end-to-end."""
        from marketsentry.workflow import run_full_fixture_demo_workflow

        db_path, out_dir = temp_env
        result = run_full_fixture_demo_workflow(
            database_path=db_path,
            output_dir=out_dir,
            reset_demo_db=True,
        )

        assert result.workflow_name == "fixture_demo"
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration_seconds is not None
        assert len(result.steps) >= 10

        # Database should exist
        assert Path(db_path).exists()

    def test_fixture_demo_seeds_candidates(self, temp_env):
        """Fixture demo seeds sample candidates."""
        from marketsentry.workflow import run_full_fixture_demo_workflow

        db_path, out_dir = temp_env
        result = run_full_fixture_demo_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        seed_step = [s for s in result.steps if s.step_name == "seed_sample_candidates"][0]
        assert seed_step.status == "completed"
        assert seed_step.records_created > 0

    def test_fixture_demo_simulates_review(self, temp_env):
        """Fixture demo simulates review decisions."""
        from marketsentry.workflow import run_full_fixture_demo_workflow

        db_path, out_dir = temp_env
        result = run_full_fixture_demo_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        review_step = [s for s in result.steps if s.step_name == "simulate_review_decisions"][0]
        assert review_step.status == "completed"
        assert "save" in review_step.notes.lower() or "saved" in review_step.notes.lower()

    def test_fixture_demo_imports_decisions(self, temp_env):
        """Fixture demo imports review decisions and promotes candidates."""
        from marketsentry.workflow import run_full_fixture_demo_workflow

        db_path, out_dir = temp_env
        result = run_full_fixture_demo_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        import_step = [s for s in result.steps if s.step_name == "import_review_decisions"][0]
        assert import_step.status == "completed"
        assert "promoted" in import_step.notes.lower() or "save" in import_step.notes.lower()

    def test_fixture_demo_generates_reports(self, temp_env):
        """Fixture demo generates output reports."""
        from marketsentry.workflow import run_full_fixture_demo_workflow

        db_path, out_dir = temp_env
        result = run_full_fixture_demo_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        assert len(result.output_files) >= 1
        report_types = [f.report_type for f in result.output_files]
        assert "candidate_review" in report_types

    def test_fixture_demo_generates_summary(self, temp_env):
        """Fixture demo generates workflow summary file."""
        from marketsentry.workflow import run_full_fixture_demo_workflow

        db_path, out_dir = temp_env
        result = run_full_fixture_demo_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        assert result.summary_file is not None
        assert Path(result.summary_file).exists()
        content = Path(result.summary_file).read_text(encoding="utf-8")
        assert "fixture_demo" in content

    def test_fixture_demo_reset_db(self, temp_env):
        """Fixture demo with reset_demo_db deletes and recreates database."""
        from marketsentry.workflow import run_full_fixture_demo_workflow

        db_path, out_dir = temp_env

        # Run once to create database
        run_full_fixture_demo_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )
        assert Path(db_path).exists()

        # Run again with reset
        result = run_full_fixture_demo_workflow(
            database_path=db_path,
            output_dir=out_dir,
            reset_demo_db=True,
        )

        assert result.workflow_name == "fixture_demo"
        # Should have a warning about deleting old database
        warning_msgs = [w.message for w in result.warnings]
        assert any("delete" in m.lower() or "deleted" in m.lower() for m in warning_msgs)

    def test_fixture_demo_deterministic(self, temp_env):
        """Fixture demo produces deterministic results."""
        from marketsentry.workflow import run_full_fixture_demo_workflow

        db_path, out_dir = temp_env
        result = run_full_fixture_demo_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        # Should always seed the same number of candidates
        seed_step = [s for s in result.steps if s.step_name == "seed_sample_candidates"][0]
        assert seed_step.records_created == 3  # sample_data seeds 3 candidates

    def test_fixture_demo_no_network_calls(self, temp_env):
        """Fixture demo makes no network calls (implicit: no exceptions from missing network)."""
        from marketsentry.workflow import run_full_fixture_demo_workflow

        db_path, out_dir = temp_env

        # If network calls were made, this would raise exceptions in CI/offline envs
        result = run_full_fixture_demo_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        # All steps should be completed or skipped (no network-related failures)
        for step in result.steps:
            assert step.status in ("completed", "skipped"), (
                f"Step {step.step_name} has unexpected status: {step.status}"
            )

    def test_fixture_demo_next_action(self, temp_env):
        """Fixture demo provides a next recommended action."""
        from marketsentry.workflow import run_full_fixture_demo_workflow

        db_path, out_dir = temp_env
        result = run_full_fixture_demo_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        assert result.next_recommended_action != ""
        assert len(result.next_recommended_action) > 10


class TestReportManifestIntegration:
    """Integration tests for report manifest with workflows."""

    @pytest.fixture
    def temp_env(self):
        """Create temp output directory and demo database path."""
        with tempfile.TemporaryDirectory() as out_dir:
            db_path = os.path.join(out_dir, "manifest_test.db")
            yield db_path, out_dir

    def test_fixture_demo_creates_manifest(self, temp_env):
        """Fixture demo creates report manifest file."""
        from marketsentry.workflow import run_full_fixture_demo_workflow

        db_path, out_dir = temp_env
        result = run_full_fixture_demo_workflow(
            database_path=db_path,
            output_dir=out_dir,
        )

        manifest_path = Path(out_dir) / "report_manifest.csv"
        assert manifest_path.exists()

        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should have at least one entry (plus summary)
        assert len(rows) >= 1
        # All entries should be from fixture_demo workflow
        for row in rows:
            assert row["workflow_name"] == "fixture_demo"


class TestCLIWorkflowCommands:
    """Tests for CLI workflow commands (basic smoke tests)."""

    def test_cli_app_has_workflow_commands(self):
        """CLI app has all required workflow commands."""
        from marketsentry.cli import app

        # Get registered command names
        command_names = []
        for cmd_info in app.registered_commands:
            name = cmd_info.name or cmd_info.callback.__name__
            command_names.append(name)

        # Also check registered groups
        for group_info in app.registered_groups:
            if hasattr(group_info, 'name'):
                command_names.append(group_info.name)

        # Check that workflow commands exist
        assert "run-initial-review-workflow" in command_names
        assert "run-watchlist-refresh-workflow" in command_names
        assert "run-fixture-demo-workflow" in command_names
        assert "workflow-status" in command_names


class TestWorkflowHelpers:
    """Tests for workflow internal helper functions."""

    def test_run_step_creates_step(self):
        """_run_step creates a step with running status."""
        from marketsentry.workflow import _run_step

        step = _run_step("test_step")
        assert step.step_name == "test_step"
        assert step.status == "running"
        assert step.started_at is not None

    def test_complete_step(self):
        """_complete_step marks step as completed."""
        from marketsentry.workflow import _complete_step, _run_step

        step = _run_step("test")
        _complete_step(step)
        assert step.status == "completed"
        assert step.completed_at is not None
        assert step.duration_seconds is not None

    def test_skip_step(self):
        """_skip_step marks step as skipped with reason."""
        from marketsentry.workflow import _run_step, _skip_step

        step = _run_step("test")
        _skip_step(step, "No input file")
        assert step.status == "skipped"
        assert "No input file" in step.notes

    def test_fail_step(self):
        """_fail_step marks step as failed with error."""
        from marketsentry.workflow import _fail_step, _run_step

        step = _run_step("test")
        _fail_step(step, "Something broke")
        assert step.status == "failed"
        assert "Something broke" in step.errors

    def test_count_csv_rows(self):
        """_count_csv_rows counts data rows correctly."""
        from marketsentry.workflow import _count_csv_rows

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            writer = csv.DictWriter(f, fieldnames=["a", "b"])
            writer.writeheader()
            writer.writerow({"a": "1", "b": "2"})
            writer.writerow({"a": "3", "b": "4"})
            f.flush()
            path = f.name

        try:
            assert _count_csv_rows(path) == 2
        finally:
            os.unlink(path)

    def test_count_csv_rows_empty_file(self):
        """_count_csv_rows returns 0 for nonexistent file."""
        from marketsentry.workflow import _count_csv_rows

        assert _count_csv_rows("nonexistent_file.csv") == 0

    def test_simulate_review_decisions(self):
        """_simulate_review_decisions marks first 2 as save, rest as reject."""
        from marketsentry.workflow import _simulate_review_decisions

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a review CSV
            review_path = os.path.join(temp_dir, "review.csv")
            with open(review_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["address", "user_decision", "user_notes"]
                )
                writer.writeheader()
                for i in range(5):
                    writer.writerow({
                        "address": f"Address {i}",
                        "user_decision": "",
                        "user_notes": "",
                    })

            reviewed_path = _simulate_review_decisions(review_path, temp_dir)
            assert Path(reviewed_path).exists()

            with open(reviewed_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 5
            assert rows[0]["user_decision"] == "save"
            assert rows[1]["user_decision"] == "save"
            assert rows[2]["user_decision"] == "reject"
            assert rows[3]["user_decision"] == "reject"
            assert rows[4]["user_decision"] == "reject"
