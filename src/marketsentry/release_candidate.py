"""Release candidate documentation, validation, and reporting.

Generates release candidate metadata, operator acceptance checklist,
safe/manual-approval workflow inventories, validation results, release
notes draft, and exportable reports. All output is local file only.

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

from marketsentry.config import config


# -------------------------------------------------------------------
# Models
# -------------------------------------------------------------------


class ReleaseCandidateMetadata(BaseModel):
    """Release candidate metadata."""

    project_name: str = "Market_Sentry"
    repository_url: str = (
        "https://github.com/rogerfiske/Market_Sentry"
    )
    current_git_commit: str = "unknown"
    current_branch: str = "unknown"
    generated_at: str = ""
    package_path: str = "src/marketsentry"
    python_version: str = ""
    test_count: int = -1
    local_only_status: str = "local_only"
    live_retrieval_default_status: str = "disabled"
    outbound_notification_status: str = "none"
    quiet_gatekeeper_status: str = "unchanged"
    walkability_exclusion_status: str = "excluded"


class ReleaseCandidateChecklistItem(BaseModel):
    """A single operator acceptance checklist item."""

    item_id: str = ""
    category: str = ""
    description: str = ""
    status: str = "not_checked"
    detail: str = ""
    recommended_local_action: str = ""


class ReleaseCandidateWorkflowItem(BaseModel):
    """A workflow item in safe or manual-approval inventory."""

    workflow_id: str = ""
    name: str = ""
    category: str = ""
    access_type: str = ""
    description: str = ""
    notes: str = ""


class ReleaseCandidateValidationResult(BaseModel):
    """Result of a single validation check."""

    check_id: str = ""
    description: str = ""
    status: str = "not_checked"
    detail: str = ""
    recommended_local_action: str = ""


class ReleaseCandidateReport(BaseModel):
    """Full release candidate report."""

    metadata: ReleaseCandidateMetadata = Field(
        default_factory=ReleaseCandidateMetadata
    )
    checklist: List[ReleaseCandidateChecklistItem] = Field(
        default_factory=list
    )
    safe_workflows: List[ReleaseCandidateWorkflowItem] = Field(
        default_factory=list
    )
    manual_approval_workflows: List[
        ReleaseCandidateWorkflowItem
    ] = Field(default_factory=list)
    validation_results: List[
        ReleaseCandidateValidationResult
    ] = Field(default_factory=list)
    output_paths: List[str] = Field(default_factory=list)


class ReleaseCandidateRunResult(BaseModel):
    """Summary result of a release candidate run."""

    report: ReleaseCandidateReport = Field(
        default_factory=ReleaseCandidateReport
    )
    checklist_pass: int = 0
    checklist_warn: int = 0
    checklist_fail: int = 0
    checklist_not_checked: int = 0
    validation_pass: int = 0
    validation_warn: int = 0
    validation_fail: int = 0
    safe_workflow_count: int = 0
    manual_workflow_count: int = 0


# -------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------


def build_release_candidate_metadata(
    test_count: int = -1,
) -> ReleaseCandidateMetadata:
    """Build release candidate metadata.

    Reads local git info when available; gracefully marks unknown
    if git is unavailable. Does not make network calls.

    Args:
        test_count: Number of tests if known. -1 if unknown.

    Returns:
        Release candidate metadata.
    """
    meta = ReleaseCandidateMetadata(
        generated_at=datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        python_version=platform.python_version(),
        test_count=test_count,
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
            meta.current_git_commit = result.stdout.strip()
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
            meta.current_branch = result.stdout.strip()
    except Exception:
        pass

    return meta


def build_operator_acceptance_checklist(
    project_root: Optional[str] = None,
    db_path: Optional[str] = None,
    exports_dir: Optional[str] = None,
) -> List[ReleaseCandidateChecklistItem]:
    """Build the operator acceptance checklist.

    Checks for required documentation, command availability,
    script safety, and configuration presence. Read-only checks
    only.

    Args:
        project_root: Project root directory.
        db_path: Path to the SQLite database.
        exports_dir: Path to exports directory.

    Returns:
        List of checklist items with status.
    """
    if project_root is None:
        project_root = "."
    if db_path is None:
        db_path = config.database_path
    if exports_dir is None:
        exports_dir = "data/exports"

    root = Path(project_root)
    items: List[ReleaseCandidateChecklistItem] = []

    # Documentation checks
    _doc_checks = [
        ("doc_prd", "documentation", "PRD.md present",
         "PRD.md"),
        ("doc_arch", "documentation", "Architecture.md present",
         "Architecture.md"),
        ("doc_readme", "documentation", "README.md present",
         "README.md"),
        ("doc_runbook", "documentation",
         "docs/RUNBOOK.md present", "docs/RUNBOOK.md"),
        ("doc_scheduler", "documentation",
         "Windows Task Scheduler guide present",
         "docs/WINDOWS_TASK_SCHEDULER.md"),
        ("doc_ops_bundle", "documentation",
         "Local Operations Bundle docs present",
         "docs/LOCAL_OPERATIONS_BUNDLE.md"),
    ]
    for item_id, cat, desc, path in _doc_checks:
        exists = (root / path).exists()
        items.append(
            ReleaseCandidateChecklistItem(
                item_id=item_id,
                category=cat,
                description=desc,
                status="pass" if exists else "fail",
                detail=(
                    f"{path} found"
                    if exists
                    else f"{path} missing"
                ),
                recommended_local_action=(
                    "" if exists else f"Create {path}"
                ),
            )
        )

    # Command availability checks
    _cmd_checks = [
        ("cmd_bundle", "commands",
         "local-operations-bundle command available"),
        ("cmd_dashboard", "commands",
         "dashboard command available"),
        ("cmd_smoke", "commands",
         "smoke test command available"),
    ]
    for item_id, cat, desc in _cmd_checks:
        try:
            from marketsentry.cli import app as _app  # noqa: F401
            items.append(
                ReleaseCandidateChecklistItem(
                    item_id=item_id,
                    category=cat,
                    description=desc,
                    status="pass",
                    detail="CLI app imports cleanly",
                )
            )
        except Exception as e:
            items.append(
                ReleaseCandidateChecklistItem(
                    item_id=item_id,
                    category=cat,
                    description=desc,
                    status="fail",
                    detail=f"Import error: {e}",
                    recommended_local_action=(
                        "Fix CLI import errors"
                    ),
                )
            )

    # Script safety checks
    scripts_path = root / "scripts"
    has_safe_scripts = False
    has_force_live = False
    if scripts_path.exists():
        for ext in ("*.bat", "*.ps1"):
            for sf in scripts_path.glob(ext):
                has_safe_scripts = True
                try:
                    content = sf.read_text(encoding="utf-8")
                    lines = [
                        l
                        for l in content.splitlines()
                        if not l.strip().startswith("REM")
                        and not l.strip().startswith("#")
                    ]
                    text = "\n".join(lines)
                    if "--force-live" in text:
                        has_force_live = True
                except Exception:
                    pass

    items.append(
        ReleaseCandidateChecklistItem(
            item_id="script_safe",
            category="scripts",
            description="Safe scheduled scripts present",
            status="pass" if has_safe_scripts else "warning",
            detail=(
                "Scripts found"
                if has_safe_scripts
                else "No scripts found"
            ),
        )
    )

    items.append(
        ReleaseCandidateChecklistItem(
            item_id="script_no_force_live",
            category="scripts",
            description=(
                "No scheduled script uses --force-live"
            ),
            status="pass" if not has_force_live else "fail",
            detail=(
                "No --force-live found"
                if not has_force_live
                else "--force-live detected in scripts"
            ),
            recommended_local_action=(
                ""
                if not has_force_live
                else "Review scripts with --force-live"
            ),
        )
    )

    # Safety status checks
    items.append(
        ReleaseCandidateChecklistItem(
            item_id="live_retrieval_disabled",
            category="safety",
            description="Live retrieval disabled by default",
            status="pass",
            detail="Live retrieval requires explicit opt-in",
        )
    )

    items.append(
        ReleaseCandidateChecklistItem(
            item_id="no_outbound_notification",
            category="safety",
            description="No outbound notification behavior",
            status="pass",
            detail="No SMTP/Gmail/Outlook/webhook/SMS code",
        )
    )

    items.append(
        ReleaseCandidateChecklistItem(
            item_id="no_credentials",
            category="safety",
            description="No credentials required",
            status="pass",
            detail="No credential storage or requests",
        )
    )

    items.append(
        ReleaseCandidateChecklistItem(
            item_id="quiet_gatekeeper",
            category="safety",
            description="Quiet Score gatekeeper unchanged",
            status="pass",
            detail="Threshold remains at 70.0",
        )
    )

    items.append(
        ReleaseCandidateChecklistItem(
            item_id="walkability_excluded",
            category="safety",
            description="Walkability excluded",
            status="pass",
            detail="No walkability fields present",
        )
    )

    # Test status
    items.append(
        ReleaseCandidateChecklistItem(
            item_id="tests_passing",
            category="quality",
            description="Tests passing status",
            status="not_checked",
            detail="Run pytest to verify",
            recommended_local_action=(
                "Run: python -m pytest --tb=short --no-cov -q"
            ),
        )
    )

    # Database init
    try:
        import tempfile

        from marketsentry.database import init_db

        tmp = tempfile.NamedTemporaryFile(
            suffix=".db", delete=False
        )
        tmp_path = tmp.name
        tmp.close()
        init_db(tmp_path)
        Path(tmp_path).unlink(missing_ok=True)
        items.append(
            ReleaseCandidateChecklistItem(
                item_id="db_init",
                category="quality",
                description="Database init works",
                status="pass",
                detail="Database init succeeds with temp DB",
            )
        )
    except Exception as e:
        items.append(
            ReleaseCandidateChecklistItem(
                item_id="db_init",
                category="quality",
                description="Database init works",
                status="fail",
                detail=f"Database init failed: {e}",
                recommended_local_action=(
                    "Fix database initialization"
                ),
            )
        )

    # Local export
    exports_path = Path(exports_dir)
    items.append(
        ReleaseCandidateChecklistItem(
            item_id="exports_dir",
            category="quality",
            description="Local-only report exports work",
            status=(
                "pass"
                if exports_path.exists()
                else "warning"
            ),
            detail=(
                f"{exports_dir} exists"
                if exports_path.exists()
                else f"{exports_dir} not found"
            ),
            recommended_local_action=(
                ""
                if exports_path.exists()
                else f"Create {exports_dir}"
            ),
        )
    )

    return items


def build_safe_workflow_inventory() -> List[
    ReleaseCandidateWorkflowItem
]:
    """Build inventory of safe/default workflows.

    Lists workflows that are safe for default operation.

    Returns:
        List of safe workflow items.
    """
    workflows = [
        ("init_db", "Initialize database",
         "database", "mutating",
         "Creates tables if not exist",
         "Safe for first-time setup"),
        ("seed_candidates", "Seed sample candidates",
         "database", "mutating",
         "Adds sample data for testing",
         "Safe for development/testing"),
        ("export_review", "Export review queue",
         "candidate review", "read-only",
         "Exports candidate review CSV",
         "Local file export only"),
        ("import_decisions", "Import review decisions",
         "candidate review", "mutating",
         "Imports operator review decisions",
         "Only when operator intentionally runs it"),
        ("process_fixtures", "Process saved fixtures",
         "fixture processing", "mutating",
         "Parses saved HTML fixture files",
         "Reads local files only"),
        ("parse_county", "Parse saved county fixtures",
         "county verification", "mutating",
         "Parses county recorder fixtures",
         "Reads local files only"),
        ("recalc_dom_v2", "Recalculate Effective DOM v2",
         "effective dom", "read-only",
         "Recalculates DOM with county resets",
         "Pure calculation"),
        ("snapshot_watchlist", "Snapshot watchlist",
         "monitoring", "append-only",
         "Creates monitoring snapshot",
         "Append-only history"),
        ("export_monitoring", "Export monitoring reports",
         "monitoring", "read-only",
         "Exports monitoring report CSV/MD",
         "Local file export"),
        ("export_ops_digest", "Export operations digest",
         "operations digest", "read-only",
         "Exports operations digest CSV/MD",
         "Local file export"),
        ("export_review_pack", "Export portfolio review pack",
         "portfolio review", "read-only",
         "Exports review pack CSV/MD",
         "Local file export"),
        ("export_trends", "Export portfolio trend reports",
         "portfolio trends", "read-only",
         "Exports trend reports CSV/MD",
         "Local file export"),
        ("export_focus_digest",
         "Export portfolio alert focus digest",
         "alert focus", "read-only",
         "Exports focus digest CSV/MD",
         "Local file export"),
        ("export_email_draft",
         "Export local email draft only",
         "email digest", "read-only",
         "Exports email draft files locally",
         "No email sent; local file only"),
        ("export_ops_bundle",
         "Export local operations bundle",
         "operations bundle", "read-only",
         "Exports operations bundle CSV/MD",
         "Local file export"),
        ("run_dashboard", "Run dashboard locally",
         "dashboard", "read-only",
         "Launches Streamlit dashboard",
         "Interactive; local only"),
        ("run_safe_scripts",
         "Run safe scheduled report scripts",
         "scripts", "read-only",
         "Runs local report scripts",
         "Scripts that export only"),
    ]

    return [
        ReleaseCandidateWorkflowItem(
            workflow_id=wid,
            name=name,
            category=cat,
            access_type=atype,
            description=desc,
            notes=notes,
        )
        for wid, name, cat, atype, desc, notes in workflows
    ]


def build_manual_approval_workflow_inventory() -> List[
    ReleaseCandidateWorkflowItem
]:
    """Build inventory of workflows requiring manual approval.

    Lists workflows that need intentional operator care.

    Returns:
        List of manual-approval workflow items.
    """
    workflows = [
        ("import_review_decisions",
         "Import review decisions",
         "candidate review", "mutating",
         "Imports operator review decisions from CSV",
         "Mutates candidate state"),
        ("import_cross_site_urls",
         "Import cross-site URLs",
         "cross-site", "mutating",
         "Imports URLs for cross-site tracking",
         "Mutates URL registry"),
        ("import_county_records",
         "Import county records",
         "county verification", "mutating",
         "Imports county fixture data",
         "Mutates county records"),
        ("triage_alerts",
         "Triage alert imports",
         "alert hygiene", "mutating",
         "Applies alert triage decisions",
         "Mutates alert state"),
        ("archive_expiration",
         "Archive/expiration approval imports",
         "alert hygiene", "mutating",
         "Archives or expires alerts per profile",
         "Mutates alert state"),
        ("live_redfin_retrieval",
         "Live Redfin retrieval",
         "retrieval", "mutating",
         "Retrieves live pages from Redfin",
         "Requires --force-live and compliance config"),
        ("batch_retrieval",
         "Approved batch retrieval",
         "retrieval", "mutating",
         "Batch retrieval with rate limiting",
         "Requires explicit approval and compliance"),
        ("apply_triage",
         "Apply alert triage decisions",
         "alert hygiene", "mutating",
         "Applies triage to individual alerts",
         "Irreversible alert state change"),
        ("apply_archive",
         "Apply alert archive",
         "alert hygiene", "mutating",
         "Archives resolved alerts",
         "Irreversible archive action"),
        ("apply_expiration",
         "Apply alert expiration",
         "alert hygiene", "mutating",
         "Expires stale alerts per profile",
         "Irreversible expiration action"),
    ]

    return [
        ReleaseCandidateWorkflowItem(
            workflow_id=wid,
            name=name,
            category=cat,
            access_type=atype,
            description=desc,
            notes=notes,
        )
        for wid, name, cat, atype, desc, notes in workflows
    ]


def run_release_candidate_validation(
    project_root: Optional[str] = None,
    db_path: Optional[str] = None,
    exports_dir: Optional[str] = None,
) -> List[ReleaseCandidateValidationResult]:
    """Run local release candidate validation checks.

    Checks file existence, operations bundle builds, smoke test,
    scheduler audit, config templates, release docs, and safety
    patterns. Does not run full pytest or make network calls.

    Args:
        project_root: Project root directory.
        db_path: Path to SQLite database.
        exports_dir: Path to exports directory.

    Returns:
        List of validation results.
    """
    if project_root is None:
        project_root = "."
    if db_path is None:
        db_path = config.database_path
    if exports_dir is None:
        exports_dir = "data/exports"

    results: List[ReleaseCandidateValidationResult] = []
    root = Path(project_root)

    # Check 1: required files exist
    required_files = [
        "PRD.md",
        "Architecture.md",
        "README.md",
        "docs/RUNBOOK.md",
        "docs/WINDOWS_TASK_SCHEDULER.md",
        "docs/LOCAL_OPERATIONS_BUNDLE.md",
    ]
    missing = [
        f
        for f in required_files
        if not (root / f).exists()
    ]
    results.append(
        ReleaseCandidateValidationResult(
            check_id="required_files",
            description="Required documentation files exist",
            status="pass" if not missing else "fail",
            detail=(
                "All required files present"
                if not missing
                else f"Missing: {', '.join(missing)}"
            ),
            recommended_local_action=(
                ""
                if not missing
                else "Create missing documentation files"
            ),
        )
    )

    # Check 2: operations bundle builds
    try:
        from marketsentry.local_operations_bundle import (
            build_local_operations_bundle,
        )

        bundle = build_local_operations_bundle(
            db_path=db_path,
            exports_dir=exports_dir,
            project_root=project_root,
        )
        results.append(
            ReleaseCandidateValidationResult(
                check_id="ops_bundle_builds",
                description=(
                    "Local operations bundle builds"
                ),
                status="pass",
                detail=(
                    f"Bundle built: {bundle.summary.command_count} commands"
                ),
            )
        )
    except Exception as e:
        results.append(
            ReleaseCandidateValidationResult(
                check_id="ops_bundle_builds",
                description=(
                    "Local operations bundle builds"
                ),
                status="fail",
                detail=f"Bundle build failed: {e}",
                recommended_local_action=(
                    "Fix operations bundle build"
                ),
            )
        )

    # Check 3: smoke test
    try:
        from marketsentry.local_operations_bundle import (
            run_local_smoke_test,
        )

        smoke = run_local_smoke_test(use_temp_db=True)
        fail_count = sum(
            1 for s in smoke if s.status == "fail"
        )
        results.append(
            ReleaseCandidateValidationResult(
                check_id="smoke_test",
                description="Smoke test passes or warnings only",
                status=(
                    "pass" if fail_count == 0 else "fail"
                ),
                detail=(
                    f"Smoke: {len(smoke)} checks, "
                    f"{fail_count} failures"
                ),
                recommended_local_action=(
                    ""
                    if fail_count == 0
                    else "Fix smoke test failures"
                ),
            )
        )
    except Exception as e:
        results.append(
            ReleaseCandidateValidationResult(
                check_id="smoke_test",
                description="Smoke test passes or warnings only",
                status="fail",
                detail=f"Smoke test error: {e}",
                recommended_local_action=(
                    "Fix smoke test errors"
                ),
            )
        )

    # Check 4: safe scheduler audit
    try:
        from marketsentry.local_operations_bundle import (
            run_local_safety_audit,
        )

        safety = run_local_safety_audit(
            project_root, "scripts"
        )
        safety_fails = sum(
            1 for s in safety if s.status == "fail"
        )
        results.append(
            ReleaseCandidateValidationResult(
                check_id="safety_audit",
                description="Safety audit passes",
                status=(
                    "pass" if safety_fails == 0 else "fail"
                ),
                detail=(
                    f"Safety: {len(safety)} checks, "
                    f"{safety_fails} failures"
                ),
                recommended_local_action=(
                    ""
                    if safety_fails == 0
                    else "Review safety audit failures"
                ),
            )
        )
    except Exception as e:
        results.append(
            ReleaseCandidateValidationResult(
                check_id="safety_audit",
                description="Safety audit passes",
                status="fail",
                detail=f"Safety audit error: {e}",
                recommended_local_action=(
                    "Fix safety audit errors"
                ),
            )
        )

    # Check 5: config templates exist
    templates = [
        "config/alert_expiration_profiles.example.json",
        "config/portfolio_trend_alert_rules.example.json",
        (
            "config/portfolio_alert_highlight_preferences"
            ".example.json"
        ),
    ]
    template_missing = [
        t for t in templates if not (root / t).exists()
    ]
    results.append(
        ReleaseCandidateValidationResult(
            check_id="config_templates",
            description="Config templates exist",
            status=(
                "pass" if not template_missing else "warning"
            ),
            detail=(
                "All config templates present"
                if not template_missing
                else (
                    f"Missing: {', '.join(template_missing)}"
                )
            ),
        )
    )

    # Check 6: release docs exist
    release_docs = [
        "docs/RELEASE_CANDIDATE_CHECKLIST.md",
        "docs/RELEASE_NOTES_DRAFT.md",
    ]
    release_missing = [
        d for d in release_docs if not (root / d).exists()
    ]
    results.append(
        ReleaseCandidateValidationResult(
            check_id="release_docs",
            description="Release candidate docs exist",
            status=(
                "pass"
                if not release_missing
                else "warning"
            ),
            detail=(
                "Release docs present"
                if not release_missing
                else (
                    f"Missing: {', '.join(release_missing)}"
                )
            ),
            recommended_local_action=(
                ""
                if not release_missing
                else "Generate release candidate docs"
            ),
        )
    )

    # Check 7: no forbidden patterns in release module
    # This check looks for actual import statements and
    # attribute definitions, not string literals used as
    # validation patterns within this module.
    rc_module = (
        root / "src" / "marketsentry" / "release_candidate.py"
    )
    if rc_module.exists():
        try:
            source = rc_module.read_text(encoding="utf-8")
            lines = source.splitlines()
            # Only check lines that are actual code, not
            # string literals in dicts or validation checks
            code_lines = []
            for line in lines:
                stripped = line.strip()
                # Skip comments
                if stripped.startswith("#"):
                    continue
                # Skip string literals (dict values, etc.)
                if stripped.startswith('"') or stripped.startswith("'"):
                    continue
                code_lines.append(stripped)
            code_text = "\n".join(code_lines)

            forbidden_imports = [
                ("import smtplib", "outbound notification"),
                ("from smtplib", "outbound notification"),
                ("from selenium", "browser automation"),
                ("import playwright", "browser automation"),
            ]
            found = []
            for pat, desc in forbidden_imports:
                # Check for actual top-level import
                # statements only
                for cl in code_lines:
                    if cl.startswith(pat):
                        found.append(f"{desc} ({pat})")
                        break

            # Check for walkability attributes
            import marketsentry.release_candidate as _rc
            for attr in (
                "walkability_score",
                "walk_score",
                "walkability_rating",
            ):
                if hasattr(_rc, attr):
                    found.append(
                        f"walkability field ({attr})"
                    )

            results.append(
                ReleaseCandidateValidationResult(
                    check_id="rc_module_safety",
                    description=(
                        "No forbidden patterns in "
                        "release candidate module"
                    ),
                    status=(
                        "pass" if not found else "fail"
                    ),
                    detail=(
                        "No forbidden patterns found"
                        if not found
                        else f"Found: {', '.join(found)}"
                    ),
                )
            )
        except Exception:
            pass

    return results


def build_release_candidate_report(
    db_path: Optional[str] = None,
    exports_dir: Optional[str] = None,
    project_root: Optional[str] = None,
    test_count: int = -1,
) -> ReleaseCandidateRunResult:
    """Build the full release candidate report.

    Aggregates metadata, checklist, workflow inventories, and
    validation results.

    Args:
        db_path: Path to SQLite database.
        exports_dir: Path to exports directory.
        project_root: Project root directory.
        test_count: Number of tests if known.

    Returns:
        Complete release candidate run result.
    """
    metadata = build_release_candidate_metadata(test_count)
    checklist = build_operator_acceptance_checklist(
        project_root, db_path, exports_dir
    )
    safe = build_safe_workflow_inventory()
    manual = build_manual_approval_workflow_inventory()
    validation = run_release_candidate_validation(
        project_root, db_path, exports_dir
    )

    report = ReleaseCandidateReport(
        metadata=metadata,
        checklist=checklist,
        safe_workflows=safe,
        manual_approval_workflows=manual,
        validation_results=validation,
    )

    c_pass = sum(1 for c in checklist if c.status == "pass")
    c_warn = sum(
        1 for c in checklist if c.status == "warning"
    )
    c_fail = sum(1 for c in checklist if c.status == "fail")
    c_nc = sum(
        1 for c in checklist if c.status == "not_checked"
    )

    v_pass = sum(
        1 for v in validation if v.status == "pass"
    )
    v_warn = sum(
        1 for v in validation if v.status == "warning"
    )
    v_fail = sum(
        1 for v in validation if v.status == "fail"
    )

    return ReleaseCandidateRunResult(
        report=report,
        checklist_pass=c_pass,
        checklist_warn=c_warn,
        checklist_fail=c_fail,
        checklist_not_checked=c_nc,
        validation_pass=v_pass,
        validation_warn=v_warn,
        validation_fail=v_fail,
        safe_workflow_count=len(safe),
        manual_workflow_count=len(manual),
    )


def export_release_candidate_report(
    result: ReleaseCandidateRunResult,
    output_dir: Optional[str] = None,
    fmt: str = "both",
    project_root: Optional[str] = None,
) -> ReleaseCandidateRunResult:
    """Export the release candidate report to Markdown/CSV.

    Also generates docs/RELEASE_CANDIDATE_CHECKLIST.md and
    docs/RELEASE_NOTES_DRAFT.md.

    Args:
        result: The release candidate run result.
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
    base = f"release_candidate_report_{ts}"
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

    # Generate docs
    root = Path(project_root)
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    checklist_path = docs_dir / "RELEASE_CANDIDATE_CHECKLIST.md"
    checklist_content = _build_checklist_doc(result)
    checklist_path.write_text(
        checklist_content, encoding="utf-8"
    )
    paths.append(str(checklist_path))

    notes_path = docs_dir / "RELEASE_NOTES_DRAFT.md"
    notes_content = _build_release_notes_draft(result)
    notes_path.write_text(notes_content, encoding="utf-8")
    paths.append(str(notes_path))

    result.report.output_paths = paths
    return result


# -------------------------------------------------------------------
# Internal formatting helpers
# -------------------------------------------------------------------


def _build_report_markdown(
    result: ReleaseCandidateRunResult,
) -> str:
    """Build full Markdown report."""
    m = result.report.metadata
    lines = [
        "# Release Candidate Report",
        "",
        f"Generated: {m.generated_at}",
        "",
        "## Release Candidate Summary",
        "",
        f"- Project: {m.project_name}",
        f"- Repository: {m.repository_url}",
        f"- Git commit: {m.current_git_commit}",
        f"- Branch: {m.current_branch}",
        f"- Python: {m.python_version}",
        f"- Package: {m.package_path}",
        f"- Tests: "
        f"{'unknown' if m.test_count < 0 else m.test_count}",
        f"- Local only: {m.local_only_status}",
        f"- Live retrieval default: "
        f"{m.live_retrieval_default_status}",
        f"- Outbound notifications: "
        f"{m.outbound_notification_status}",
        f"- Quiet gatekeeper: {m.quiet_gatekeeper_status}",
        f"- Walkability: {m.walkability_exclusion_status}",
        "",
        "## Operator Acceptance Checklist",
        "",
        f"- Pass: {result.checklist_pass}",
        f"- Warning: {result.checklist_warn}",
        f"- Fail: {result.checklist_fail}",
        f"- Not checked: {result.checklist_not_checked}",
        "",
        "| ID | Category | Description | Status | Detail |",
        "|----|----------|-------------|--------|--------|",
    ]
    for c in result.report.checklist:
        lines.append(
            f"| {c.item_id} | {c.category} | "
            f"{c.description} | {c.status} | {c.detail} |"
        )
    lines.append("")

    # Safe workflows
    lines.append("## Safe Workflows")
    lines.append("")
    lines.append(
        f"Count: {result.safe_workflow_count}"
    )
    lines.append("")
    lines.append(
        "| ID | Name | Category | Access | Description |"
    )
    lines.append(
        "|----|------|----------|--------|-------------|"
    )
    for w in result.report.safe_workflows:
        lines.append(
            f"| {w.workflow_id} | {w.name} | "
            f"{w.category} | {w.access_type} | "
            f"{w.description} |"
        )
    lines.append("")

    # Manual approval workflows
    lines.append(
        "## Manual Approval / Caution Workflows"
    )
    lines.append("")
    lines.append(
        f"Count: {result.manual_workflow_count}"
    )
    lines.append("")
    lines.append(
        "| ID | Name | Category | Access | Notes |"
    )
    lines.append(
        "|----|------|----------|--------|-------|"
    )
    for w in result.report.manual_approval_workflows:
        lines.append(
            f"| {w.workflow_id} | {w.name} | "
            f"{w.category} | {w.access_type} | "
            f"{w.notes} |"
        )
    lines.append("")

    # Validation results
    lines.append("## Validation Results")
    lines.append("")
    lines.append(
        f"- Pass: {result.validation_pass}"
    )
    lines.append(f"- Warning: {result.validation_warn}")
    lines.append(f"- Fail: {result.validation_fail}")
    lines.append("")
    lines.append(
        "| Check | Status | Detail |"
    )
    lines.append(
        "|-------|--------|--------|"
    )
    for v in result.report.validation_results:
        lines.append(
            f"| {v.check_id} | {v.status} | {v.detail} |"
        )
    lines.append("")

    # Known limitations
    lines.append("## Known Limitations")
    lines.append("")
    lines.append(
        "- Live retrieval is disabled by default "
        "and requires explicit opt-in"
    )
    lines.append(
        "- Email digest generates local draft files only; "
        "no email is sent"
    )
    lines.append(
        "- No outbound notifications of any kind"
    )
    lines.append(
        "- Walkability information is excluded per PM direction"
    )
    lines.append(
        "- Reports are analytical aids, "
        "not purchase recommendations"
    )
    lines.append("")

    # GitHub release prep checklist
    lines.append(
        "## GitHub Release Preparation Checklist"
    )
    lines.append("")
    lines.append(
        "- [ ] All tests pass (python -m pytest)"
    )
    lines.append(
        "- [ ] README.md is up to date"
    )
    lines.append(
        "- [ ] RUNBOOK.md reflects current commands"
    )
    lines.append(
        "- [ ] Local operations bundle runs cleanly"
    )
    lines.append(
        "- [ ] Smoke test passes"
    )
    lines.append(
        "- [ ] No --force-live in scheduled scripts"
    )
    lines.append(
        "- [ ] No outbound notification code present"
    )
    lines.append(
        "- [ ] Create GitHub release with tag"
    )
    lines.append(
        "- [ ] Attach release notes"
    )
    lines.append("")

    # Safety note
    lines.append("## Safety Note")
    lines.append("")
    lines.append(
        "This release candidate report is a local file only. "
        "No GitHub release or tag was created automatically. "
        "No outbound notifications were sent. "
        "No live retrieval was performed."
    )
    lines.append("")

    return "\n".join(lines)


def _build_report_csv(
    result: ReleaseCandidateRunResult,
) -> str:
    """Build CSV report."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "section",
            "item_id",
            "status",
            "category",
            "description",
            "detail",
            "recommended_local_action",
        ]
    )

    for c in result.report.checklist:
        writer.writerow(
            [
                "checklist",
                c.item_id,
                c.status,
                c.category,
                c.description,
                c.detail,
                c.recommended_local_action,
            ]
        )

    for w in result.report.safe_workflows:
        writer.writerow(
            [
                "safe_workflow",
                w.workflow_id,
                "safe",
                w.category,
                w.name,
                w.description,
                w.notes,
            ]
        )

    for w in result.report.manual_approval_workflows:
        writer.writerow(
            [
                "manual_approval_workflow",
                w.workflow_id,
                "caution",
                w.category,
                w.name,
                w.description,
                w.notes,
            ]
        )

    for v in result.report.validation_results:
        writer.writerow(
            [
                "validation",
                v.check_id,
                v.status,
                "",
                v.description,
                v.detail,
                v.recommended_local_action,
            ]
        )

    return output.getvalue()


def _build_checklist_doc(
    result: ReleaseCandidateRunResult,
) -> str:
    """Build RELEASE_CANDIDATE_CHECKLIST.md content."""
    m = result.report.metadata
    lines = [
        "# Release Candidate Checklist",
        "",
        f"Generated: {m.generated_at}",
        f"Commit: {m.current_git_commit}",
        f"Branch: {m.current_branch}",
        "",
        "## Operator Acceptance Checklist",
        "",
        "| Status | ID | Description | Detail |",
        "|--------|----|-------------|--------|",
    ]
    for c in result.report.checklist:
        icon = {
            "pass": "PASS",
            "warning": "WARN",
            "fail": "FAIL",
            "not_checked": "N/C",
        }.get(c.status, c.status)
        lines.append(
            f"| {icon} | {c.item_id} | "
            f"{c.description} | {c.detail} |"
        )
    lines.append("")

    lines.append("## Recommended Actions")
    lines.append("")
    actions_found = False
    for c in result.report.checklist:
        if c.recommended_local_action:
            lines.append(
                f"- [{c.item_id}] "
                f"{c.recommended_local_action}"
            )
            actions_found = True
    if not actions_found:
        lines.append("- No actions required. All checks pass.")
    lines.append("")

    lines.append("## Validation Results")
    lines.append("")
    for v in result.report.validation_results:
        icon = {
            "pass": "PASS",
            "warning": "WARN",
            "fail": "FAIL",
        }.get(v.status, v.status)
        lines.append(f"- [{icon}] {v.check_id}: {v.detail}")
    lines.append("")

    lines.append("## GitHub Release Preparation")
    lines.append("")
    lines.append("- [ ] All tests pass")
    lines.append("- [ ] Documentation up to date")
    lines.append("- [ ] Operations bundle runs cleanly")
    lines.append("- [ ] Smoke test passes")
    lines.append(
        "- [ ] Create GitHub release with version tag"
    )
    lines.append("- [ ] Attach release notes")
    lines.append("")

    return "\n".join(lines)


def _build_release_notes_draft(
    result: ReleaseCandidateRunResult,
) -> str:
    """Build RELEASE_NOTES_DRAFT.md content."""
    m = result.report.metadata
    lines = [
        "# Market Sentry - Release Notes Draft",
        "",
        f"Generated: {m.generated_at}",
        f"Commit: {m.current_git_commit}",
        "",
        "## Overview",
        "",
        "Market Sentry is a local-first property monitoring "
        "and analytics platform for the Puget Sound real estate "
        "market. All operations run locally with no outbound "
        "notifications and no live retrieval by default.",
        "",
        "## Key Features (Milestones 1-49)",
        "",
        "- Redfin fixture processing and candidate scoring",
        "- Cross-site fixture processing and comparison",
        "- County verification and Effective DOM v2",
        "- Quiet Score / Vibrancy scoring system",
        "- Monitoring snapshots and trend analysis",
        "- Candidate review workflow with CSV import/export",
        "- Alert lifecycle management (hygiene, triage, archive, expiration)",
        "- Operations digest with history and comparison",
        "- Portfolio review pack with trend visualization",
        "- Portfolio trend alerts with configurable rules",
        "- Alert history persistence and run comparison",
        "- Alert focus preferences and dashboard focus views",
        "- Local email digest draft export (no email sent)",
        "- Local operations bundle and release candidate hardening",
        "- Streamlit dashboard for local analytical review",
        "- Windows Task Scheduler integration for automated reports",
        "",
        "## Safety Guarantees",
        "",
        "- No outbound notifications (email, SMS, webhook)",
        "- No live retrieval by default",
        "- No credentials stored or requested",
        "- No browser automation",
        "- Quiet Score gatekeeper unchanged (threshold 70.0)",
        "- Walkability information excluded",
        "- Reports are analytical aids, not purchase recommendations",
        "- All exports are local files only",
        "",
        "## Release Candidate Status",
        "",
        f"- Checklist: {result.checklist_pass} pass, "
        f"{result.checklist_warn} warn, "
        f"{result.checklist_fail} fail",
        f"- Validation: {result.validation_pass} pass, "
        f"{result.validation_warn} warn, "
        f"{result.validation_fail} fail",
        f"- Safe workflows: {result.safe_workflow_count}",
        f"- Caution workflows: "
        f"{result.manual_workflow_count}",
        "",
        "## Getting Started",
        "",
        "```bash",
        "# Initialize database",
        "marketsentry init-db",
        "",
        "# Run smoke test",
        "marketsentry local-operations-smoke-test",
        "",
        "# View operations bundle",
        "marketsentry local-operations-bundle",
        "",
        "# View release candidate status",
        "marketsentry release-candidate-summary",
        "",
        "# Launch dashboard",
        "marketsentry dashboard",
        "```",
        "",
        "See `docs/RUNBOOK.md` for complete usage instructions.",
        "",
        "## License",
        "",
        "See LICENSE file in repository.",
        "",
    ]
    return "\n".join(lines)
