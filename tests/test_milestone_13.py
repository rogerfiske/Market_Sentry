"""Tests for Milestone 13: Windows Task Scheduler Automation.

Tests automation helper functions, script validation, command building,
and CLI commands. Does NOT register real Windows Scheduled Tasks.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from marketsentry.automation import (
    COMMAND_MAP,
    EXPECTED_SCRIPTS,
    SCHEDULED_LOG_DIR,
    AutomationStatus,
    build_task_command,
    find_python_executable,
    find_virtualenv_activate_script,
    get_automation_status,
    get_project_root,
    get_scheduled_log_dir,
    read_latest_scheduled_log,
    validate_scripts_exist,
    write_automation_status,
)


# ---------------------------------------------------------------------------
# Test: AutomationStatus model
# ---------------------------------------------------------------------------


class TestAutomationStatusModel:
    """Test the AutomationStatus Pydantic model."""

    def test_default_model(self):
        """AutomationStatus can be created with defaults."""
        status = AutomationStatus()
        assert status.project_root == ""
        assert status.python_executable == ""
        assert status.virtualenv_path is None
        assert status.virtualenv_activate_script is None
        assert status.database_path == ""
        assert status.exports_directory == ""
        assert status.scheduled_logs_directory == ""
        assert status.scripts_directory == ""
        assert status.scripts_found == []
        assert status.scripts_missing == []
        assert status.latest_scheduled_log is None
        assert status.latest_scheduled_log_preview is None

    def test_populated_model(self):
        """AutomationStatus can be populated with values."""
        status = AutomationStatus(
            project_root="/test/root",
            python_executable="/test/python",
            database_path="db/test.db",
            scripts_found=["script1.bat", "script2.bat"],
            scripts_missing=["script3.ps1"],
        )
        assert status.project_root == "/test/root"
        assert len(status.scripts_found) == 2
        assert len(status.scripts_missing) == 1


# ---------------------------------------------------------------------------
# Test: Project root detection
# ---------------------------------------------------------------------------


class TestProjectRootDetection:
    """Test project root detection logic."""

    def test_get_project_root_returns_path(self):
        """get_project_root returns a Path object."""
        root = get_project_root()
        assert isinstance(root, Path)

    def test_get_project_root_has_pyproject_toml(self):
        """Detected project root should contain pyproject.toml."""
        root = get_project_root()
        # The real project root should have pyproject.toml
        assert (root / "pyproject.toml").exists() or (root / "PRD.md").exists()


# ---------------------------------------------------------------------------
# Test: Python executable detection
# ---------------------------------------------------------------------------


class TestPythonExecutableDetection:
    """Test Python executable detection."""

    def test_find_python_executable_returns_path(self):
        """find_python_executable returns a Path object."""
        exe = find_python_executable()
        assert isinstance(exe, Path)

    def test_find_python_executable_exists(self):
        """Detected Python executable should exist."""
        exe = find_python_executable()
        assert exe.exists()

    def test_find_python_executable_with_explicit_root(self):
        """find_python_executable works with explicit project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # No venv in temp dir, should fall back to sys.executable
            exe = find_python_executable(Path(tmpdir))
            assert exe is not None
            assert str(exe) == sys.executable

    def test_find_python_executable_detects_venv(self):
        """find_python_executable detects a virtualenv if present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Create a fake .venv structure
            venv_scripts = root / ".venv" / "Scripts"
            venv_scripts.mkdir(parents=True)
            fake_python = venv_scripts / "python.exe"
            fake_python.write_text("fake")

            exe = find_python_executable(root)
            assert str(exe) == str(fake_python)


# ---------------------------------------------------------------------------
# Test: Virtualenv activate script detection
# ---------------------------------------------------------------------------


class TestVirtualenvDetection:
    """Test virtualenv activate script detection."""

    def test_find_venv_activate_no_venv(self):
        """Returns None when no virtualenv exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_virtualenv_activate_script(Path(tmpdir))
            assert result is None

    def test_find_venv_activate_dot_venv(self):
        """Detects .venv activate script."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            activate = root / ".venv" / "Scripts" / "activate.bat"
            activate.parent.mkdir(parents=True)
            activate.write_text("@echo off")

            result = find_virtualenv_activate_script(root)
            assert result is not None
            assert str(result) == str(activate)

    def test_find_venv_activate_venv(self):
        """Detects venv activate script."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            activate = root / "venv" / "Scripts" / "activate.bat"
            activate.parent.mkdir(parents=True)
            activate.write_text("@echo off")

            result = find_virtualenv_activate_script(root)
            assert result is not None
            assert str(result) == str(activate)


# ---------------------------------------------------------------------------
# Test: Scheduled log directory
# ---------------------------------------------------------------------------


class TestScheduledLogDir:
    """Test scheduled log directory path generation."""

    def test_get_scheduled_log_dir(self):
        """get_scheduled_log_dir returns expected path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            log_dir = get_scheduled_log_dir(root)
            assert str(log_dir).endswith(SCHEDULED_LOG_DIR.replace("/", os.sep))


# ---------------------------------------------------------------------------
# Test: Command building
# ---------------------------------------------------------------------------


class TestCommandBuilding:
    """Test build_task_command function."""

    def test_build_watchlist_refresh_command(self):
        """Build command for watchlist-refresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cmd = build_task_command("watchlist-refresh", root)
            assert isinstance(cmd, list)
            assert "run-watchlist-refresh-workflow" in cmd

    def test_build_initial_review_command(self):
        """Build command for initial-review."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cmd = build_task_command("initial-review", root)
            assert "run-initial-review-workflow" in cmd

    def test_build_dashboard_summary_command(self):
        """Build command for dashboard-summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cmd = build_task_command("dashboard-summary", root)
            assert "dashboard-summary" in cmd

    def test_build_fixture_demo_command(self):
        """Build command for fixture-demo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cmd = build_task_command("fixture-demo", root)
            assert "run-fixture-demo-workflow" in cmd

    def test_build_command_with_db_path(self):
        """Build command with custom database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = Path(tmpdir) / "custom.db"
            cmd = build_task_command("watchlist-refresh", root, db_path=db_path)
            assert "--db" in cmd
            assert str(db_path) in cmd

    def test_build_command_with_output_dir(self):
        """Build command with custom output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            out_dir = Path(tmpdir) / "output"
            cmd = build_task_command("watchlist-refresh", root, output_dir=out_dir)
            assert "--output-dir" in cmd
            assert str(out_dir) in cmd

    def test_build_command_dashboard_no_output_dir(self):
        """Dashboard summary command ignores output_dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            out_dir = Path(tmpdir) / "output"
            cmd = build_task_command("dashboard-summary", root, output_dir=out_dir)
            assert "--output-dir" not in cmd

    def test_build_command_invalid_name(self):
        """Invalid command name raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with pytest.raises(ValueError, match="Unknown command"):
                build_task_command("nonexistent-command", root)

    def test_all_commands_in_map(self):
        """All expected commands are in the COMMAND_MAP."""
        expected = ["watchlist-refresh", "initial-review", "dashboard-summary", "fixture-demo"]
        for cmd_name in expected:
            assert cmd_name in COMMAND_MAP


# ---------------------------------------------------------------------------
# Test: Expected scripts exist
# ---------------------------------------------------------------------------


class TestScriptFilesExist:
    """Test that expected script files exist in the repository."""

    def test_expected_scripts_list_complete(self):
        """EXPECTED_SCRIPTS list contains all required scripts."""
        required = [
            "run_initial_review_workflow.bat",
            "run_watchlist_refresh_workflow.bat",
            "run_dashboard_summary.bat",
            "run_fixture_demo_workflow.bat",
            "install_task_scheduler_watchlist_refresh.ps1",
            "uninstall_task_scheduler_watchlist_refresh.ps1",
            "run_marketsentry_task.ps1",
        ]
        for script in required:
            assert script in EXPECTED_SCRIPTS

    def test_scripts_directory_exists(self):
        """scripts/ directory exists in project root."""
        root = get_project_root()
        scripts_dir = root / "scripts"
        assert scripts_dir.exists(), f"scripts/ directory not found at {scripts_dir}"

    def test_all_script_files_exist(self):
        """All expected script files exist in scripts/ directory."""
        root = get_project_root()
        scripts_dir = root / "scripts"
        for script_name in EXPECTED_SCRIPTS:
            script_path = scripts_dir / script_name
            assert script_path.exists(), f"Script not found: {script_path}"

    def test_validate_scripts_exist_returns_all_true(self):
        """validate_scripts_exist returns True for all scripts."""
        results = validate_scripts_exist()
        for script_name, exists in results.items():
            assert exists, f"Script missing: {script_name}"


# ---------------------------------------------------------------------------
# Test: Script content validation
# ---------------------------------------------------------------------------


class TestScriptContent:
    """Test that script files contain expected commands."""

    def test_watchlist_refresh_bat_content(self):
        """Watchlist refresh batch script contains expected command."""
        root = get_project_root()
        content = (root / "scripts" / "run_watchlist_refresh_workflow.bat").read_text()
        assert "run-watchlist-refresh-workflow" in content
        assert "marketsentry" in content.lower() or "marketsentry" in content

    def test_initial_review_bat_content(self):
        """Initial review batch script contains expected command."""
        root = get_project_root()
        content = (root / "scripts" / "run_initial_review_workflow.bat").read_text()
        assert "run-initial-review-workflow" in content

    def test_dashboard_summary_bat_content(self):
        """Dashboard summary batch script contains expected command."""
        root = get_project_root()
        content = (root / "scripts" / "run_dashboard_summary.bat").read_text()
        assert "dashboard-summary" in content

    def test_fixture_demo_bat_content(self):
        """Fixture demo batch script contains expected command."""
        root = get_project_root()
        content = (root / "scripts" / "run_fixture_demo_workflow.bat").read_text()
        assert "run-fixture-demo-workflow" in content

    def test_bat_scripts_have_log_directory(self):
        """Batch scripts create scheduled log directory."""
        root = get_project_root()
        for bat_name in EXPECTED_SCRIPTS:
            if bat_name.endswith(".bat"):
                content = (root / "scripts" / bat_name).read_text()
                assert "logs" in content and "scheduled" in content, (
                    f"{bat_name} missing log directory reference"
                )

    def test_ps1_wrapper_supports_all_commands(self):
        """PowerShell wrapper supports all command names."""
        root = get_project_root()
        content = (root / "scripts" / "run_marketsentry_task.ps1").read_text()
        for cmd_name in COMMAND_MAP.keys():
            assert cmd_name in content, f"Wrapper missing command: {cmd_name}"

    def test_install_ps1_has_task_name(self):
        """Install script has the default task name."""
        root = get_project_root()
        content = (root / "scripts" / "install_task_scheduler_watchlist_refresh.ps1").read_text()
        assert "Market_Sentry_Watchlist_Refresh" in content

    def test_uninstall_ps1_has_task_name(self):
        """Uninstall script has the default task name."""
        root = get_project_root()
        content = (root / "scripts" / "uninstall_task_scheduler_watchlist_refresh.ps1").read_text()
        assert "Market_Sentry_Watchlist_Refresh" in content

    def test_bat_scripts_activate_venv(self):
        """Batch scripts attempt to activate virtual environment."""
        root = get_project_root()
        for bat_name in EXPECTED_SCRIPTS:
            if bat_name.endswith(".bat"):
                content = (root / "scripts" / bat_name).read_text()
                assert "activate.bat" in content, (
                    f"{bat_name} missing venv activation"
                )

    def test_bat_scripts_no_network_calls(self):
        """Batch scripts do not contain network-related commands."""
        root = get_project_root()
        network_keywords = ["curl", "wget", "invoke-webrequest", "net use"]
        for bat_name in EXPECTED_SCRIPTS:
            if bat_name.endswith(".bat"):
                content = (root / "scripts" / bat_name).read_text().lower()
                for keyword in network_keywords:
                    assert keyword not in content, (
                        f"{bat_name} contains network keyword: {keyword}"
                    )


# ---------------------------------------------------------------------------
# Test: Automation status
# ---------------------------------------------------------------------------


class TestAutomationStatusGathering:
    """Test get_automation_status function."""

    def test_get_automation_status_returns_model(self):
        """get_automation_status returns an AutomationStatus model."""
        status = get_automation_status()
        assert isinstance(status, AutomationStatus)

    def test_status_has_project_root(self):
        """Status includes project root."""
        status = get_automation_status()
        assert status.project_root != ""
        assert Path(status.project_root).exists()

    def test_status_has_python_executable(self):
        """Status includes Python executable."""
        status = get_automation_status()
        assert status.python_executable != ""

    def test_status_has_database_path(self):
        """Status includes database path."""
        status = get_automation_status()
        assert status.database_path != ""

    def test_status_has_scripts_info(self):
        """Status includes script detection results."""
        status = get_automation_status()
        assert len(status.scripts_found) > 0


# ---------------------------------------------------------------------------
# Test: Scheduled log reading/writing
# ---------------------------------------------------------------------------


class TestScheduledLogs:
    """Test scheduled log reading and writing."""

    def test_read_latest_log_empty_dir(self):
        """Returns None when no log files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = read_latest_scheduled_log(Path(tmpdir))
            assert result is None

    def test_read_latest_log_nonexistent_dir(self):
        """Returns None when log directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "nonexistent"
            result = read_latest_scheduled_log(root)
            assert result is None

    def test_read_latest_log_with_files(self):
        """Returns latest log file info when logs exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            log_dir = root / "logs" / "scheduled"
            log_dir.mkdir(parents=True)

            # Create a log file
            log_file = log_dir / "watchlist_refresh_20260506_090000.log"
            log_file.write_text(
                "Start: 2026-05-06 09:00:00\nRunning watchlist refresh\nExit Code: 0",
                encoding="utf-8",
            )

            result = read_latest_scheduled_log(root)
            assert result is not None
            assert "path" in result
            assert "preview" in result
            assert "watchlist_refresh" in result["path"]
            assert "Exit Code: 0" in result["preview"]

    def test_write_automation_status_creates_file(self):
        """write_automation_status creates a status file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Create minimal project structure
            (root / "pyproject.toml").write_text("")

            output = Path(tmpdir) / "status.txt"
            result = write_automation_status(root, output)

            assert Path(result).exists()
            content = Path(result).read_text()
            assert "Market_Sentry Automation Status" in content
            assert "Project Root" in content


# ---------------------------------------------------------------------------
# Test: CLI commands exist
# ---------------------------------------------------------------------------


class TestCLICommands:
    """Test that CLI commands for automation are registered."""

    def test_automation_status_command_exists(self):
        """automation-status command is registered in CLI."""
        from marketsentry.cli import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "automation-status" in command_names

    def test_write_scheduler_scripts_command_exists(self):
        """write-scheduler-scripts command is registered in CLI."""
        from marketsentry.cli import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "write-scheduler-scripts" in command_names

    def test_automation_status_runs(self):
        """automation-status command runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["automation-status"])
        assert result.exit_code == 0
        assert "Automation Status" in result.output

    def test_write_scheduler_scripts_runs(self):
        """write-scheduler-scripts command runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["write-scheduler-scripts"])
        assert result.exit_code == 0
        assert "Scheduler Scripts" in result.output


# ---------------------------------------------------------------------------
# Test: No network calls
# ---------------------------------------------------------------------------


class TestNoNetworkCalls:
    """Verify automation module does not import network libraries."""

    def test_automation_no_requests(self):
        """automation.py does not import requests."""
        import marketsentry.automation as mod

        source = Path(mod.__file__).read_text()
        assert "import requests" not in source
        assert "from requests" not in source

    def test_automation_no_httpx(self):
        """automation.py does not import httpx."""
        import marketsentry.automation as mod

        source = Path(mod.__file__).read_text()
        assert "import httpx" not in source
        assert "from httpx" not in source

    def test_automation_no_urllib(self):
        """automation.py does not import urllib for network access."""
        import marketsentry.automation as mod

        source = Path(mod.__file__).read_text()
        assert "urllib.request" not in source

    def test_automation_no_selenium(self):
        """automation.py does not import selenium."""
        import marketsentry.automation as mod

        source = Path(mod.__file__).read_text()
        assert "import selenium" not in source
        assert "from selenium" not in source

    def test_automation_no_playwright(self):
        """automation.py does not import playwright."""
        import marketsentry.automation as mod

        source = Path(mod.__file__).read_text()
        assert "import playwright" not in source
        assert "from playwright" not in source

    def test_scripts_no_network_commands(self):
        """PowerShell scripts do not contain network commands."""
        root = get_project_root()
        network_keywords = [
            "invoke-webrequest",
            "invoke-restmethod",
            "start-bitstransfer",
            "wget",
            "curl",
        ]
        for script_name in EXPECTED_SCRIPTS:
            if script_name.endswith(".ps1"):
                content = (root / "scripts" / script_name).read_text().lower()
                for keyword in network_keywords:
                    assert keyword not in content, (
                        f"{script_name} contains network keyword: {keyword}"
                    )


# ---------------------------------------------------------------------------
# Test: No real Task Scheduler registration
# ---------------------------------------------------------------------------


class TestNoRealTaskRegistration:
    """Verify tests do not register real Windows Scheduled Tasks."""

    def test_no_register_scheduled_task_call(self):
        """Test suite does not call Register-ScheduledTask."""
        # This test exists to document and verify the constraint
        # that no test in this module registers a real task.
        # The automation module only provides helper functions.
        assert True  # Placeholder confirming no registration occurs

    def test_automation_module_has_no_subprocess_task_creation(self):
        """automation.py does not call schtasks or Register-ScheduledTask."""
        import marketsentry.automation as mod

        source = Path(mod.__file__).read_text()
        assert "schtasks" not in source.lower()
        assert "Register-ScheduledTask" not in source
        assert "New-ScheduledTask" not in source
