"""Windows Task Scheduler automation helpers for Market_Sentry.

Provides utility functions for detecting project paths, virtual environments,
building CLI commands, and managing scheduled task logs. These helpers support
Windows Task Scheduler integration without performing any live network calls.

All scheduled workflows operate on local data only: SQLite database, CSV imports,
saved HTML fixtures, and generated reports.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field

from marketsentry.config import config
from marketsentry.logging_config import logger


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class AutomationStatus(BaseModel):
    """Status information for automation environment."""

    project_root: str = ""
    python_executable: str = ""
    virtualenv_path: Optional[str] = None
    virtualenv_activate_script: Optional[str] = None
    database_path: str = ""
    exports_directory: str = ""
    scheduled_logs_directory: str = ""
    scripts_directory: str = ""
    scripts_found: List[str] = Field(default_factory=list)
    scripts_missing: List[str] = Field(default_factory=list)
    latest_scheduled_log: Optional[str] = None
    latest_scheduled_log_preview: Optional[str] = None


# ---------------------------------------------------------------------------
# Expected script files
# ---------------------------------------------------------------------------

EXPECTED_SCRIPTS = [
    "run_initial_review_workflow.bat",
    "run_watchlist_refresh_workflow.bat",
    "run_dashboard_summary.bat",
    "run_fixture_demo_workflow.bat",
    "run_alert_hygiene_report.bat",
    "install_task_scheduler_watchlist_refresh.ps1",
    "uninstall_task_scheduler_watchlist_refresh.ps1",
    "run_marketsentry_task.ps1",
]

# Mapping from command names to CLI commands
COMMAND_MAP: Dict[str, str] = {
    "watchlist-refresh": "run-watchlist-refresh-workflow",
    "initial-review": "run-initial-review-workflow",
    "dashboard-summary": "dashboard-summary",
    "fixture-demo": "run-fixture-demo-workflow",
}

SCHEDULED_LOG_DIR = "logs/scheduled"


# ---------------------------------------------------------------------------
# Path detection helpers
# ---------------------------------------------------------------------------


def get_project_root() -> Path:
    """Detect the project root directory.

    Walks up from the current file's location looking for pyproject.toml
    or PRD.md as project root markers.

    Returns:
        Path to the project root directory.
    """
    # Start from the marketsentry package directory
    current = Path(__file__).resolve().parent

    # Walk up looking for project markers
    for _ in range(10):
        if (current / "pyproject.toml").exists() or (current / "PRD.md").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    # Fall back to current working directory
    return Path.cwd()


def find_python_executable(project_root: Optional[Path] = None) -> Optional[Path]:
    """Find the Python executable, preferring virtualenv if available.

    Args:
        project_root: Project root directory. Detected automatically if None.

    Returns:
        Path to Python executable, or None if not found.
    """
    root = project_root or get_project_root()

    # Check for virtualenv Python first
    venv_candidates = [
        root / ".venv" / "Scripts" / "python.exe",
        root / "venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
        root / "venv" / "bin" / "python",
    ]

    for candidate in venv_candidates:
        if candidate.exists():
            return candidate

    # Fall back to current Python
    return Path(sys.executable)


def find_virtualenv_activate_script(
    project_root: Optional[Path] = None,
) -> Optional[Path]:
    """Find the virtualenv activate script.

    Args:
        project_root: Project root directory. Detected automatically if None.

    Returns:
        Path to activate script, or None if no virtualenv found.
    """
    root = project_root or get_project_root()

    # Check common virtualenv locations (Windows batch activate)
    candidates = [
        root / ".venv" / "Scripts" / "activate.bat",
        root / "venv" / "Scripts" / "activate.bat",
        root / ".venv" / "bin" / "activate",
        root / "venv" / "bin" / "activate",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def get_scheduled_log_dir(project_root: Optional[Path] = None) -> Path:
    """Get the scheduled log directory path.

    Args:
        project_root: Project root directory. Detected automatically if None.

    Returns:
        Path to the scheduled log directory.
    """
    root = project_root or get_project_root()
    return root / SCHEDULED_LOG_DIR


# ---------------------------------------------------------------------------
# Command building
# ---------------------------------------------------------------------------


def build_task_command(
    command_name: str,
    project_root: Path,
    db_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> List[str]:
    """Build a CLI command list for a scheduled task.

    Args:
        command_name: One of: watchlist-refresh, initial-review,
            dashboard-summary, fixture-demo.
        project_root: Project root directory.
        db_path: Optional database path override.
        output_dir: Optional output directory override.

    Returns:
        List of command arguments suitable for subprocess.

    Raises:
        ValueError: If command_name is not recognized.
    """
    if command_name not in COMMAND_MAP:
        raise ValueError(
            f"Unknown command: {command_name}. "
            f"Valid commands: {', '.join(COMMAND_MAP.keys())}"
        )

    cli_command = COMMAND_MAP[command_name]

    # Find Python executable
    python_exe = find_python_executable(project_root)
    python_path = str(python_exe) if python_exe else sys.executable

    # Build base command using the CLI module
    cmd = [python_path, "-c", "from marketsentry.cli import app; app()", cli_command]

    # Add optional arguments
    if db_path:
        cmd.extend(["--db", str(db_path)])
    if output_dir and command_name != "dashboard-summary":
        cmd.extend(["--output-dir", str(output_dir)])

    return cmd


# ---------------------------------------------------------------------------
# Automation status
# ---------------------------------------------------------------------------


def get_automation_status(
    project_root: Optional[Path] = None,
) -> AutomationStatus:
    """Gather automation environment status.

    Args:
        project_root: Project root directory. Detected automatically if None.

    Returns:
        AutomationStatus with detected environment information.
    """
    root = project_root or get_project_root()
    scripts_dir = root / "scripts"
    log_dir = get_scheduled_log_dir(root)

    status = AutomationStatus(
        project_root=str(root),
        python_executable=str(find_python_executable(root) or sys.executable),
        database_path=config.database_path,
        exports_directory=config.data_exports_dir,
        scheduled_logs_directory=str(log_dir),
        scripts_directory=str(scripts_dir),
    )

    # Virtualenv detection
    venv_activate = find_virtualenv_activate_script(root)
    if venv_activate:
        status.virtualenv_activate_script = str(venv_activate)
        status.virtualenv_path = str(venv_activate.parent.parent)

    # Script file detection
    for script_name in EXPECTED_SCRIPTS:
        script_path = scripts_dir / script_name
        if script_path.exists():
            status.scripts_found.append(script_name)
        else:
            status.scripts_missing.append(script_name)

    # Latest scheduled log
    latest_log = read_latest_scheduled_log(root)
    if latest_log:
        status.latest_scheduled_log = latest_log["path"]
        status.latest_scheduled_log_preview = latest_log["preview"]

    return status


# ---------------------------------------------------------------------------
# Scheduled log helpers
# ---------------------------------------------------------------------------


def write_automation_status(
    project_root: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> str:
    """Write automation status to a text file.

    Args:
        project_root: Project root directory. Detected automatically if None.
        output_path: Optional output file path. Defaults to logs/scheduled/automation_status.txt.

    Returns:
        Path to the written status file.
    """
    root = project_root or get_project_root()
    status = get_automation_status(root)

    if output_path is None:
        log_dir = get_scheduled_log_dir(root)
        log_dir.mkdir(parents=True, exist_ok=True)
        output_path = log_dir / "automation_status.txt"

    lines = [
        "Market_Sentry Automation Status",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"Project Root: {status.project_root}",
        f"Python Executable: {status.python_executable}",
        f"Virtualenv: {status.virtualenv_path or 'Not detected'}",
        f"Database Path: {status.database_path}",
        f"Exports Directory: {status.exports_directory}",
        f"Scheduled Logs: {status.scheduled_logs_directory}",
        "",
        f"Scripts Found: {len(status.scripts_found)}",
    ]

    for script in status.scripts_found:
        lines.append(f"  - {script}")

    if status.scripts_missing:
        lines.append(f"Scripts Missing: {len(status.scripts_missing)}")
        for script in status.scripts_missing:
            lines.append(f"  - {script}")

    if status.latest_scheduled_log:
        lines.append(f"\nLatest Scheduled Log: {status.latest_scheduled_log}")

    lines.append("")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Automation status written to {output_path}")

    return str(output_path)


def read_latest_scheduled_log(
    project_root: Optional[Path] = None,
    max_preview_lines: int = 20,
) -> Optional[Dict[str, str]]:
    """Read the latest scheduled log file.

    Args:
        project_root: Project root directory. Detected automatically if None.
        max_preview_lines: Maximum lines to include in preview.

    Returns:
        Dict with 'path' and 'preview' keys, or None if no logs found.
    """
    root = project_root or get_project_root()
    log_dir = get_scheduled_log_dir(root)

    if not log_dir.exists():
        return None

    log_files = sorted(log_dir.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)

    if not log_files:
        return None

    latest = log_files[0]

    try:
        content = latest.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        preview = "\n".join(lines[:max_preview_lines])
        if len(lines) > max_preview_lines:
            preview += f"\n... ({len(lines) - max_preview_lines} more lines)"
    except Exception:
        preview = "(unable to read log file)"

    return {
        "path": str(latest),
        "preview": preview,
    }


def validate_scripts_exist(
    project_root: Optional[Path] = None,
) -> Dict[str, bool]:
    """Validate that expected script files exist.

    Args:
        project_root: Project root directory. Detected automatically if None.

    Returns:
        Dict mapping script names to existence booleans.
    """
    root = project_root or get_project_root()
    scripts_dir = root / "scripts"

    results = {}
    for script_name in EXPECTED_SCRIPTS:
        results[script_name] = (scripts_dir / script_name).exists()

    return results
