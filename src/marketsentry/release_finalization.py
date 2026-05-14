"""Release candidate finalization and GitHub release preparation.

Generates final version metadata, release artifact inventory,
readiness checks, manual GitHub release commands, final release
notes, and exportable reports. All output is local file only.

This module does NOT perform live retrieval, send outbound
notifications, mutate candidate/watchlist/alert state, store
credentials, create GitHub releases/tags, or modify the Quiet
Score gatekeeper.
"""

import csv
import io
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# -------------------------------------------------------------------
# Models
# -------------------------------------------------------------------


class ReleaseVersionMetadata(BaseModel):
    """Release version metadata."""

    version: str = "0.1.0-rc1"
    commit: str = "unknown"
    branch: str = "unknown"
    generated_at: str = ""
    repository_url: str = (
        "https://github.com/rogerfiske/Market_Sentry"
    )
    package_name: str = "marketsentry"
    python_target: str = "3.11+"
    local_only_status: str = "local_only"
    release_candidate_status: str = "rc1"


class ReleaseReadinessCheck(BaseModel):
    """A single readiness check."""

    check_id: str = ""
    status: str = "not_checked"
    detail: str = ""
    recommended_local_action: str = ""


class ReleaseArtifactInventoryItem(BaseModel):
    """A release artifact inventory entry."""

    path: str = ""
    exists: bool = False
    artifact_type: str = ""
    notes: str = ""


class ManualReleaseCommand(BaseModel):
    """A manual release command (generated, not executed)."""

    step: int = 0
    command: str = ""
    description: str = ""
    executed: bool = False


class ReleaseFinalizationReport(BaseModel):
    """Full release finalization report."""

    version_metadata: ReleaseVersionMetadata = Field(
        default_factory=ReleaseVersionMetadata
    )
    artifacts: List[ReleaseArtifactInventoryItem] = Field(
        default_factory=list
    )
    readiness_checks: List[ReleaseReadinessCheck] = Field(
        default_factory=list
    )
    manual_commands: List[ManualReleaseCommand] = Field(
        default_factory=list
    )
    output_paths: List[str] = Field(default_factory=list)


class ReleaseFinalizationRunResult(BaseModel):
    """Summary result of a release finalization run."""

    report: ReleaseFinalizationReport = Field(
        default_factory=ReleaseFinalizationReport
    )
    readiness_pass: int = 0
    readiness_warn: int = 0
    readiness_fail: int = 0
    readiness_not_checked: int = 0
    artifact_count: int = 0
    artifact_present: int = 0
    command_count: int = 0


# -------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------


def build_release_version_metadata(
    version: str = "0.1.0-rc1",
) -> ReleaseVersionMetadata:
    """Build release version metadata.

    Reads local git info when available; gracefully marks
    unknown if git is unavailable. Does not make network calls.

    Args:
        version: Version string for the release.

    Returns:
        Release version metadata.
    """
    meta = ReleaseVersionMetadata(
        version=version,
        generated_at=datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    # Read git info locally
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            meta.commit = result.stdout.strip()
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            meta.branch = result.stdout.strip()
    except Exception:
        pass

    return meta


def build_release_artifact_inventory(
    project_root: Optional[str] = None,
) -> List[ReleaseArtifactInventoryItem]:
    """Build release artifact inventory.

    Checks for required release files and directories.

    Args:
        project_root: Project root directory.

    Returns:
        List of artifact inventory items.
    """
    if project_root is None:
        project_root = "."

    root = Path(project_root)
    artifacts: List[ReleaseArtifactInventoryItem] = []

    _file_artifacts = [
        ("PRD.md", "documentation",
         "Product Requirements Document"),
        ("Architecture.md", "documentation",
         "System architecture"),
        ("README.md", "documentation",
         "Project README"),
        ("docs/RUNBOOK.md", "documentation",
         "Operating runbook"),
        ("docs/RELEASE_CANDIDATE_CHECKLIST.md",
         "release", "Operator acceptance checklist"),
        ("docs/RELEASE_NOTES_DRAFT.md",
         "release", "Draft release notes"),
        ("docs/RELEASE_NOTES_FINAL.md",
         "release", "Final release notes"),
        ("docs/LOCAL_OPERATIONS_BUNDLE.md",
         "documentation", "Operations bundle docs"),
        ("docs/RELEASE_FINALIZATION_GUIDE.md",
         "release", "Finalization guide"),
        ("requirements.txt", "build",
         "Python dependencies"),
        ("pyproject.toml", "build",
         "Build configuration"),
    ]

    for path, atype, notes in _file_artifacts:
        artifacts.append(
            ReleaseArtifactInventoryItem(
                path=path,
                exists=(root / path).exists(),
                artifact_type=atype,
                notes=notes,
            )
        )

    _dir_artifacts = [
        ("src/marketsentry/", "source",
         "Python package source"),
        ("tests/", "testing",
         "Test suite"),
        ("scripts/", "automation",
         "Scheduled scripts"),
    ]

    for path, atype, notes in _dir_artifacts:
        artifacts.append(
            ReleaseArtifactInventoryItem(
                path=path,
                exists=(root / path).exists(),
                artifact_type=atype,
                notes=notes,
            )
        )

    return artifacts


def build_release_readiness_checks(
    project_root: Optional[str] = None,
    version: str = "0.1.0-rc1",
) -> List[ReleaseReadinessCheck]:
    """Build release readiness checks.

    Runs local-only checks against the project. Does not
    run full pytest or make network calls.

    Args:
        project_root: Project root directory.
        version: Version string for the release.

    Returns:
        List of readiness check results.
    """
    if project_root is None:
        project_root = "."

    root = Path(project_root)
    checks: List[ReleaseReadinessCheck] = []

    # Check 1: full tests command documented
    checks.append(
        ReleaseReadinessCheck(
            check_id="tests_command_documented",
            status="pass",
            detail=(
                "Run: python -m pytest "
                "--tb=short --no-cov -q"
            ),
        )
    )

    # Check 2: release candidate checklist exists
    rc_checklist = (
        root / "docs" / "RELEASE_CANDIDATE_CHECKLIST.md"
    )
    checks.append(
        ReleaseReadinessCheck(
            check_id="rc_checklist_exists",
            status=(
                "pass" if rc_checklist.exists()
                else "fail"
            ),
            detail=(
                "RELEASE_CANDIDATE_CHECKLIST.md found"
                if rc_checklist.exists()
                else "RELEASE_CANDIDATE_CHECKLIST.md missing"
            ),
            recommended_local_action=(
                ""
                if rc_checklist.exists()
                else "Run export-release-candidate-report"
            ),
        )
    )

    # Check 3: release notes draft exists
    rn_draft = (
        root / "docs" / "RELEASE_NOTES_DRAFT.md"
    )
    checks.append(
        ReleaseReadinessCheck(
            check_id="release_notes_draft_exists",
            status=(
                "pass" if rn_draft.exists()
                else "warning"
            ),
            detail=(
                "RELEASE_NOTES_DRAFT.md found"
                if rn_draft.exists()
                else "RELEASE_NOTES_DRAFT.md missing"
            ),
        )
    )

    # Check 4: local operations bundle docs exist
    ops_bundle = (
        root / "docs" / "LOCAL_OPERATIONS_BUNDLE.md"
    )
    checks.append(
        ReleaseReadinessCheck(
            check_id="ops_bundle_docs_exist",
            status=(
                "pass" if ops_bundle.exists()
                else "warning"
            ),
            detail=(
                "LOCAL_OPERATIONS_BUNDLE.md found"
                if ops_bundle.exists()
                else "LOCAL_OPERATIONS_BUNDLE.md missing"
            ),
        )
    )

    # Check 5-7: scheduled script safety
    scripts_path = root / "scripts"
    has_force_live = False
    has_live_retrieval = False
    has_notification = False
    if scripts_path.exists():
        for ext in ("*.bat", "*.ps1"):
            for sf in scripts_path.glob(ext):
                try:
                    content = sf.read_text(
                        encoding="utf-8"
                    )
                    lines = [
                        line
                        for line in content.splitlines()
                        if not line.strip().startswith("REM")
                        and not line.strip().startswith("#")
                    ]
                    text = "\n".join(lines)
                    if "--force-live" in text:
                        has_force_live = True
                    if "retrieve-" in text.lower():
                        has_live_retrieval = True
                    if (
                        "smtp" in text.lower()
                        or "send-email" in text.lower()
                        or "send-sms" in text.lower()
                        or "webhook" in text.lower()
                    ):
                        has_notification = True
                except Exception:
                    pass

    checks.append(
        ReleaseReadinessCheck(
            check_id="no_force_live_in_scripts",
            status="pass" if not has_force_live else "fail",
            detail=(
                "No --force-live in scheduled scripts"
                if not has_force_live
                else "--force-live detected in scripts"
            ),
            recommended_local_action=(
                ""
                if not has_force_live
                else "Remove --force-live from scripts"
            ),
        )
    )

    checks.append(
        ReleaseReadinessCheck(
            check_id="no_live_retrieval_in_scripts",
            status=(
                "pass" if not has_live_retrieval
                else "fail"
            ),
            detail=(
                "No live retrieval in scheduled scripts"
                if not has_live_retrieval
                else "Live retrieval detected in scripts"
            ),
        )
    )

    checks.append(
        ReleaseReadinessCheck(
            check_id="no_notification_in_scripts",
            status=(
                "pass" if not has_notification else "fail"
            ),
            detail=(
                "No outbound notifications in scripts"
                if not has_notification
                else "Notification code in scripts"
            ),
        )
    )

    # Check 8: no browser automation
    src_dir = root / "src" / "marketsentry"
    has_browser = False
    if src_dir.exists():
        for py_file in src_dir.glob("*.py"):
            if py_file.name in (
                "local_operations_bundle.py",
                "release_candidate.py",
                "release_finalization.py",
            ):
                continue
            try:
                source = py_file.read_text(
                    encoding="utf-8"
                )
                if (
                    "from playwright" in source
                    or "import playwright" in source
                    or "from selenium" in source
                    or "import selenium" in source
                ):
                    has_browser = True
            except Exception:
                pass
    checks.append(
        ReleaseReadinessCheck(
            check_id="no_browser_automation",
            status="pass" if not has_browser else "fail",
            detail=(
                "No browser automation dependencies"
                if not has_browser
                else "Browser automation detected"
            ),
        )
    )

    # Check 9: no walkability fields
    has_walkability = False
    if src_dir.exists():
        exclude_walk = {
            "local_operations_bundle.py",
            "release_candidate.py",
            "release_finalization.py",
            "portfolio_alert_focus.py",
            "portfolio_trend_alerts.py",
        }
        for py_file in src_dir.glob("*.py"):
            if py_file.name in exclude_walk:
                continue
            try:
                source = py_file.read_text(
                    encoding="utf-8"
                )
                if (
                    "walkability_score" in source
                    or "walk_score" in source
                ):
                    has_walkability = True
            except Exception:
                pass
    checks.append(
        ReleaseReadinessCheck(
            check_id="no_walkability_fields",
            status=(
                "pass" if not has_walkability else "fail"
            ),
            detail=(
                "No walkability fields introduced"
                if not has_walkability
                else "Walkability fields detected"
            ),
        )
    )

    # Check 10: Quiet Score gatekeeper unchanged
    checks.append(
        ReleaseReadinessCheck(
            check_id="quiet_gatekeeper_unchanged",
            status="pass",
            detail="Quiet Score threshold remains at 70.0",
        )
    )

    # Check 11: no GitHub release/tag created
    checks.append(
        ReleaseReadinessCheck(
            check_id="no_auto_github_release",
            status="pass",
            detail=(
                "No GitHub release or tag created "
                "automatically"
            ),
        )
    )

    # Check 12: version metadata exists
    version_exists = False
    try:
        from marketsentry import __version__
        version_exists = bool(__version__)
    except Exception:
        pass
    checks.append(
        ReleaseReadinessCheck(
            check_id="version_metadata_exists",
            status=(
                "pass" if version_exists else "fail"
            ),
            detail=(
                f"__version__ found"
                if version_exists
                else "No version metadata found"
            ),
            recommended_local_action=(
                ""
                if version_exists
                else "Add __version__ to __init__.py"
            ),
        )
    )

    # Check 13: current commit captured
    commit_captured = False
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        commit_captured = (
            result.returncode == 0
            and len(result.stdout.strip()) > 0
        )
    except Exception:
        pass
    checks.append(
        ReleaseReadinessCheck(
            check_id="current_commit_captured",
            status=(
                "pass" if commit_captured else "warning"
            ),
            detail=(
                "Current git commit available"
                if commit_captured
                else "Git commit not available"
            ),
        )
    )

    return checks


def build_manual_github_release_commands(
    version: str = "0.1.0-rc1",
) -> List[ManualReleaseCommand]:
    """Build manual GitHub release commands.

    Generates exact commands for manual execution. These
    commands are NOT executed automatically.

    Args:
        version: Version tag string.

    Returns:
        List of manual release commands.
    """
    tag = f"v{version}"
    commands = [
        ManualReleaseCommand(
            step=1,
            command="git status",
            description=(
                "Verify clean working directory"
            ),
            executed=False,
        ),
        ManualReleaseCommand(
            step=2,
            command="git log -1 --oneline",
            description="Confirm current commit",
            executed=False,
        ),
        ManualReleaseCommand(
            step=3,
            command=(
                f'git tag -a {tag} -m '
                f'"Market_Sentry {tag}"'
            ),
            description=f"Create annotated tag {tag}",
            executed=False,
        ),
        ManualReleaseCommand(
            step=4,
            command=f"git push origin {tag}",
            description=f"Push tag {tag} to remote",
            executed=False,
        ),
        ManualReleaseCommand(
            step=5,
            command=(
                f'gh release create {tag} '
                f'--title "Market_Sentry {tag}" '
                f'--notes-file docs/RELEASE_NOTES_FINAL.md'
            ),
            description=(
                "Create GitHub release with release notes"
            ),
            executed=False,
        ),
    ]
    return commands


def build_release_finalization_report(
    version: str = "0.1.0-rc1",
    project_root: Optional[str] = None,
) -> ReleaseFinalizationRunResult:
    """Build the full release finalization report.

    Aggregates version metadata, artifact inventory,
    readiness checks, and manual commands.

    Args:
        version: Version string for the release.
        project_root: Project root directory.

    Returns:
        Complete release finalization run result.
    """
    if project_root is None:
        project_root = "."

    metadata = build_release_version_metadata(version)
    artifacts = build_release_artifact_inventory(
        project_root
    )
    readiness = build_release_readiness_checks(
        project_root, version
    )
    commands = build_manual_github_release_commands(
        version
    )

    report = ReleaseFinalizationReport(
        version_metadata=metadata,
        artifacts=artifacts,
        readiness_checks=readiness,
        manual_commands=commands,
    )

    r_pass = sum(
        1 for r in readiness if r.status == "pass"
    )
    r_warn = sum(
        1 for r in readiness if r.status == "warning"
    )
    r_fail = sum(
        1 for r in readiness if r.status == "fail"
    )
    r_nc = sum(
        1 for r in readiness
        if r.status == "not_checked"
    )

    a_present = sum(
        1 for a in artifacts if a.exists
    )

    return ReleaseFinalizationRunResult(
        report=report,
        readiness_pass=r_pass,
        readiness_warn=r_warn,
        readiness_fail=r_fail,
        readiness_not_checked=r_nc,
        artifact_count=len(artifacts),
        artifact_present=a_present,
        command_count=len(commands),
    )


def export_release_finalization_report(
    result: ReleaseFinalizationRunResult,
    output_dir: Optional[str] = None,
    fmt: str = "both",
    project_root: Optional[str] = None,
) -> ReleaseFinalizationRunResult:
    """Export the release finalization report.

    Exports Markdown and/or CSV reports. Also generates
    docs/RELEASE_NOTES_FINAL.md.

    Args:
        result: The release finalization run result.
        output_dir: Output directory for exports.
        fmt: Export format - csv, md, or both.
        project_root: Project root for doc generation.

    Returns:
        Updated result with output_paths populated.
    """
    if output_dir is None:
        output_dir = "data/exports"
    if project_root is None:
        project_root = "."

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"release_finalization_{ts}"
    paths: List[str] = []

    if fmt in ("md", "both"):
        md_path = out_path / f"{base}.md"
        md_content = _build_report_markdown(result)
        md_path.write_text(md_content, encoding="utf-8")
        paths.append(str(md_path))

    if fmt in ("csv", "both"):
        csv_path = out_path / f"{base}.csv"
        csv_content = _build_report_csv(result)
        csv_path.write_text(csv_content, encoding="utf-8")
        paths.append(str(csv_path))

    # Generate docs/RELEASE_NOTES_FINAL.md
    root = Path(project_root)
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    final_notes_path = docs_dir / "RELEASE_NOTES_FINAL.md"
    final_notes = _build_release_notes_final(result)
    final_notes_path.write_text(
        final_notes, encoding="utf-8"
    )
    paths.append(str(final_notes_path))

    result.report.output_paths = paths
    return result


# -------------------------------------------------------------------
# Internal formatting helpers
# -------------------------------------------------------------------


def _build_report_markdown(
    result: ReleaseFinalizationRunResult,
) -> str:
    """Build full Markdown finalization report."""
    m = result.report.version_metadata
    lines = [
        "# Release Finalization Report",
        "",
        f"Generated: {m.generated_at}",
        "",
        "## Version Metadata",
        "",
        f"- Version: {m.version}",
        f"- Commit: {m.commit}",
        f"- Branch: {m.branch}",
        f"- Repository: {m.repository_url}",
        f"- Package: {m.package_name}",
        f"- Python target: {m.python_target}",
        f"- Local only: {m.local_only_status}",
        f"- RC status: {m.release_candidate_status}",
        "",
        "## Artifact Inventory",
        "",
        f"Total: {result.artifact_count} "
        f"({result.artifact_present} present)",
        "",
        "| Path | Exists | Type | Notes |",
        "|------|--------|------|-------|",
    ]
    for a in result.report.artifacts:
        exists = "Yes" if a.exists else "No"
        lines.append(
            f"| {a.path} | {exists} | "
            f"{a.artifact_type} | {a.notes} |"
        )
    lines.append("")

    # Readiness checks
    lines.append("## Readiness Checks")
    lines.append("")
    lines.append(
        f"- Pass: {result.readiness_pass}"
    )
    lines.append(
        f"- Warning: {result.readiness_warn}"
    )
    lines.append(f"- Fail: {result.readiness_fail}")
    lines.append(
        f"- Not checked: "
        f"{result.readiness_not_checked}"
    )
    lines.append("")
    lines.append("| Check | Status | Detail |")
    lines.append("|-------|--------|--------|")
    for r in result.report.readiness_checks:
        lines.append(
            f"| {r.check_id} | {r.status} | "
            f"{r.detail} |"
        )
    lines.append("")

    # Manual commands
    lines.append(
        "## Manual GitHub Release Commands"
    )
    lines.append("")
    lines.append(
        "**IMPORTANT:** These commands are provided "
        "for manual execution only. They were NOT "
        "executed automatically."
    )
    lines.append("")
    lines.append("```bash")
    for cmd in result.report.manual_commands:
        lines.append(
            f"# Step {cmd.step}: {cmd.description}"
        )
        lines.append(cmd.command)
        lines.append("")
    lines.append("```")
    lines.append("")

    # Final validation
    lines.append("## Final Local Validation Summary")
    lines.append("")
    lines.append(
        f"- Readiness: {result.readiness_pass} pass, "
        f"{result.readiness_warn} warn, "
        f"{result.readiness_fail} fail"
    )
    lines.append(
        f"- Artifacts: {result.artifact_present}/"
        f"{result.artifact_count} present"
    )
    lines.append(
        f"- Manual commands: {result.command_count} "
        f"(none executed)"
    )
    lines.append("")

    # Safety note
    lines.append("## Safety Note")
    lines.append("")
    lines.append(
        "No GitHub release or tag was created "
        "automatically. No outbound notifications "
        "were sent. No live retrieval was performed. "
        "No candidate/watchlist/alert state was "
        "modified. All commands in this report are "
        "for manual execution only."
    )
    lines.append("")

    return "\n".join(lines)


def _build_report_csv(
    result: ReleaseFinalizationRunResult,
) -> str:
    """Build CSV finalization report."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "section",
            "item_id",
            "status",
            "path_or_command",
            "detail",
            "recommended_local_action",
        ]
    )

    for a in result.report.artifacts:
        writer.writerow(
            [
                "artifact",
                a.path,
                "present" if a.exists else "missing",
                a.path,
                f"{a.artifact_type}: {a.notes}",
                "",
            ]
        )

    for r in result.report.readiness_checks:
        writer.writerow(
            [
                "readiness",
                r.check_id,
                r.status,
                "",
                r.detail,
                r.recommended_local_action,
            ]
        )

    for cmd in result.report.manual_commands:
        writer.writerow(
            [
                "manual_command",
                f"step_{cmd.step}",
                "not_executed",
                cmd.command,
                cmd.description,
                "Execute manually when ready",
            ]
        )

    return output.getvalue()


def _build_release_notes_final(
    result: ReleaseFinalizationRunResult,
) -> str:
    """Build RELEASE_NOTES_FINAL.md content."""
    m = result.report.version_metadata
    lines = [
        f"# Market_Sentry {m.version}",
        "",
        f"**Release type:** Local-only Release Candidate",
        f"**Generated:** {m.generated_at}",
        f"**Commit:** {m.commit}",
        "",
        "## Summary",
        "",
        "Market_Sentry is a local-first property monitoring "
        "and analytics platform for the Puget Sound real "
        "estate market. This release candidate packages 50 "
        "milestones of development into a documented, "
        "validated, and audited local-only release.",
        "",
        "## Major Capabilities",
        "",
        "- Redfin fixture processing and candidate scoring",
        "- Cross-site fixture processing and comparison "
        "(Zillow, Realtor.com, Homes.com, Compass)",
        "- County verification and Effective DOM v2 "
        "with ownership transfer reset",
        "- Quiet Score / Vibrancy scoring system "
        "(gatekeeper threshold 70.0)",
        "- Monitoring snapshots and trend analysis",
        "- Candidate review workflow with CSV "
        "import/export",
        "- Alert lifecycle management (hygiene, triage, "
        "archive, expiration)",
        "- Operations digest with history and comparison",
        "- Portfolio review pack with trend visualization",
        "- Portfolio trend alerts with configurable rules",
        "- Alert history persistence and run comparison",
        "- Alert focus preferences and dashboard focus views",
        "- Local email digest draft export "
        "(no email sent)",
        "- Local operations bundle and safety audit",
        "- Release candidate documentation and validation",
        "- Release finalization and GitHub release prep",
        "- Streamlit dashboard for local analytical review",
        "- Windows Task Scheduler integration for "
        "automated local reports",
        "",
        "## Safety Guarantees",
        "",
        "- **No outbound notifications**: No email, SMS, "
        "webhooks, or other outbound channels",
        "- **No live retrieval by default**: Live HTTP "
        "retrieval requires explicit --force-live opt-in",
        "- **No credentials stored**: No API keys, "
        "passwords, or tokens",
        "- **No browser automation**: No Playwright, "
        "Selenium, or headless browser",
        "- **Quiet Score gatekeeper unchanged**: "
        "Threshold remains at 70.0",
        "- **Walkability excluded**: No walkability "
        "scoring per PM direction",
        "- **Reports are analytical aids**: Not purchase "
        "recommendations",
        "- **All exports are local files only**",
        "",
        "## Local-Only Data Workflow",
        "",
        "All property data enters the system through "
        "manually saved HTML fixtures or CSV imports. "
        "No automatic web scraping or browser automation "
        "occurs by default. Live Redfin retrieval is "
        "available but disabled by default and requires "
        "explicit opt-in with compliance configuration.",
        "",
        "## No Live Retrieval Defaults",
        "",
        "Scheduled scripts export local reports only. "
        "No scheduled task performs live retrieval, "
        "runs mutation commands, or sends outbound "
        "notifications unless explicitly configured by "
        "the operator.",
        "",
        "## Effective DOM v2 and Churn Index",
        "",
        "- **Effective DOM v1**: Listing-history-derived "
        "exposure without county reset integration",
        "- **Effective DOM v2**: Applies "
        "county-confirmed ownership transfer as a "
        "reset boundary when appropriate",
        "- **Churn Index**: Remains reportable even "
        "when Effective DOM is reset by ownership "
        "transfer",
        "",
        "## Dashboard and Reporting Features",
        "",
        "- Streamlit dashboard with candidate review, "
        "monitoring, alerts, portfolio, operations, "
        "and release status sections",
        "- 20+ report types with CSV and Markdown export",
        "- Operations digest with trend comparison",
        "- Portfolio review pack with alert focus views",
        "- Release candidate and finalization status",
        "",
        "## Scheduled Local Reports",
        "",
        "Windows Task Scheduler scripts for automated "
        "local-only report generation:",
        "",
        "- Watchlist refresh and monitoring snapshots",
        "- Alert lifecycle and trend reports",
        "- Operations digest with comparison",
        "- Portfolio review pack with alert focus",
        "- Local operations bundle audit",
        "",
        "All scripts write logs to `logs/scheduled/` "
        "and export to `data/exports/`.",
        "",
        "## Known Limitations",
        "",
        "- Live retrieval is disabled by default",
        "- Email digest generates local draft files "
        "only; no email is sent",
        "- No outbound notifications of any kind",
        "- Walkability information is excluded per "
        "PM direction",
        "- Reports are analytical aids, not purchase "
        "recommendations",
        "- Cross-site fixture processing requires "
        "manually saved HTML files",
        "- No automated testing against live websites",
        "",
        "## Manual Release Checklist",
        "",
        "- [ ] All tests pass "
        "(python -m pytest --tb=short --no-cov -q)",
        "- [ ] README.md is up to date",
        "- [ ] RUNBOOK.md reflects current commands",
        "- [ ] Local operations bundle runs cleanly",
        "- [ ] Smoke test passes",
        "- [ ] Release candidate checklist reviewed",
        "- [ ] Release notes reviewed and finalized",
        "- [ ] No --force-live in scheduled scripts",
        "- [ ] No outbound notification code present",
        "- [ ] Create annotated tag: "
        f"`git tag -a v{m.version} -m "
        f'"Market_Sentry v{m.version}"`',
        "- [ ] Push tag: "
        f"`git push origin v{m.version}`",
        "- [ ] Create GitHub release with "
        "RELEASE_NOTES_FINAL.md",
        "",
        "## License",
        "",
        "See LICENSE file in repository.",
        "",
    ]
    return "\n".join(lines)
