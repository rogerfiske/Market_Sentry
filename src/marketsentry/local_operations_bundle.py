"""Local operations bundle for release-candidate hardening.

Generates command inventory, report inventory, scheduled script
inventory, configuration inventory, local safety audit, report
freshness audit, database schema inventory, and a smoke test
workflow. All output is local file export only.

This module does NOT perform live retrieval, send outbound
notifications, mutate candidate/watchlist/alert state, store
credentials, or modify the Quiet Score gatekeeper.
"""

import csv
import io
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# -------------------------------------------------------------------
# Models
# -------------------------------------------------------------------


class LocalOperationsCommandInventoryItem(BaseModel):
    """A single CLI command in the inventory."""

    command_name: str = ""
    category: str = ""
    purpose: str = ""
    mutates_db: bool = False
    live_retrieval_related: bool = False
    safe_for_scheduler_default: bool = False
    notes: str = ""


class LocalOperationsReportInventoryItem(BaseModel):
    """A single report group in the inventory."""

    report_type: str = ""
    latest_file_path: str = ""
    latest_modified: str = ""
    file_count: int = 0
    row_count: int = -1
    freshness: str = "unknown"
    notes: str = ""


class LocalOperationsScriptInventoryItem(BaseModel):
    """A single scheduled script in the inventory."""

    script_path: str = ""
    script_type: str = ""
    exists: bool = False
    contains_live_retrieval_command: bool = False
    contains_force_live: bool = False
    contains_mutation_command: bool = False
    contains_outbound_notification_command: bool = False
    safe_status: str = "unknown"
    notes: str = ""


class LocalOperationsConfigInventoryItem(BaseModel):
    """A single config file in the inventory."""

    config_path: str = ""
    exists: bool = False
    is_template: bool = False
    validation_status: str = "unknown"
    notes: str = ""


class LocalOperationsSafetyCheck(BaseModel):
    """A single safety audit check result."""

    check_name: str = ""
    status: str = "pass"
    detail: str = ""
    file_path: str = ""
    recommended_local_action: str = ""


class LocalOperationsBundleSummary(BaseModel):
    """Aggregate summary of the local operations bundle."""

    command_count: int = 0
    report_group_count: int = 0
    safety_audit_pass: int = 0
    safety_audit_warn: int = 0
    safety_audit_fail: int = 0
    script_safe_count: int = 0
    script_review_count: int = 0
    script_unsafe_count: int = 0
    config_valid_count: int = 0
    config_missing_count: int = 0
    config_unknown_count: int = 0
    table_count: int = 0
    smoke_test_pass: int = 0
    smoke_test_warn: int = 0
    smoke_test_fail: int = 0
    generated_at: str = ""


class LocalOperationsBundleRunResult(BaseModel):
    """Full result of a local operations bundle build."""

    summary: LocalOperationsBundleSummary = Field(
        default_factory=LocalOperationsBundleSummary
    )
    commands: List[LocalOperationsCommandInventoryItem] = Field(
        default_factory=list
    )
    reports: List[LocalOperationsReportInventoryItem] = Field(
        default_factory=list
    )
    scripts: List[LocalOperationsScriptInventoryItem] = Field(
        default_factory=list
    )
    configs: List[LocalOperationsConfigInventoryItem] = Field(
        default_factory=list
    )
    safety_checks: List[LocalOperationsSafetyCheck] = Field(
        default_factory=list
    )
    schema_tables: List[str] = Field(default_factory=list)
    schema_info: Dict[str, Any] = Field(default_factory=dict)
    smoke_tests: List[LocalOperationsSafetyCheck] = Field(
        default_factory=list
    )
    output_paths: List[str] = Field(default_factory=list)


# -------------------------------------------------------------------
# Known command definitions
# -------------------------------------------------------------------

_KNOWN_COMMANDS: List[Dict[str, Any]] = [
    # database/init/status
    {
        "command_name": "init-db",
        "category": "database",
        "purpose": "Initialize the SQLite database",
        "mutates_db": True,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Creates tables if they do not exist",
    },
    {
        "command_name": "db-status",
        "category": "database",
        "purpose": "Show database status and table counts",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only",
    },
    # candidate review
    {
        "command_name": "review-candidates",
        "category": "candidate review",
        "purpose": "Review candidates in terminal",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only review",
    },
    {
        "command_name": "export-candidates",
        "category": "candidate review",
        "purpose": "Export candidate review CSV",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    {
        "command_name": "import-review-decisions",
        "category": "candidate review",
        "purpose": "Import review decisions from CSV",
        "mutates_db": True,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": False,
        "notes": "Mutates candidate state",
    },
    # Redfin fixture processing
    {
        "command_name": "process-redfin-fixtures",
        "category": "redfin fixture",
        "purpose": "Process saved Redfin HTML fixture files",
        "mutates_db": True,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Reads local HTML fixtures only",
    },
    # cross-site fixture processing
    {
        "command_name": "process-cross-site-fixtures",
        "category": "cross-site fixture",
        "purpose": "Process cross-site HTML fixture files",
        "mutates_db": True,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Reads local HTML fixtures only",
    },
    {
        "command_name": "import-cross-site-urls",
        "category": "cross-site fixture",
        "purpose": "Import cross-site URLs from CSV",
        "mutates_db": True,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": False,
        "notes": "Mutates URL registry",
    },
    {
        "command_name": "cross-site-comparison",
        "category": "cross-site analytics",
        "purpose": "Run cross-site comparison report",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only report",
    },
    {
        "command_name": "export-cross-site-comparison",
        "category": "cross-site analytics",
        "purpose": "Export cross-site comparison CSV/MD",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    # county verification
    {
        "command_name": "county-verification",
        "category": "county verification",
        "purpose": "Run county verification report",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only report from local data",
    },
    # Effective DOM v2
    {
        "command_name": "effective-dom-v2",
        "category": "effective dom",
        "purpose": "Calculate Effective DOM v2 with county resets",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only calculation",
    },
    # monitoring snapshots
    {
        "command_name": "monitoring-snapshot",
        "category": "monitoring",
        "purpose": "Generate monitoring snapshot",
        "mutates_db": True,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Appends snapshot row",
    },
    # retrieval compliance/health
    {
        "command_name": "retrieval-health",
        "category": "retrieval compliance",
        "purpose": "Show retrieval health status",
        "mutates_db": False,
        "live_retrieval_related": True,
        "safe_for_scheduler_default": True,
        "notes": "Read-only status check",
    },
    # dashboard
    {
        "command_name": "dashboard",
        "category": "dashboard",
        "purpose": "Launch Streamlit dashboard",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": False,
        "notes": "Interactive; not suitable for scheduler",
    },
    {
        "command_name": "dashboard-summary",
        "category": "dashboard",
        "purpose": "Print dashboard summary to terminal",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only",
    },
    # alert lifecycle
    {
        "command_name": "alert-lifecycle",
        "category": "alert lifecycle",
        "purpose": "Show alert lifecycle status",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only",
    },
    {
        "command_name": "export-alert-lifecycle",
        "category": "alert lifecycle",
        "purpose": "Export alert lifecycle report",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    # alert hygiene/triage/archive/expiration
    {
        "command_name": "alert-hygiene",
        "category": "alert hygiene",
        "purpose": "Show alert hygiene report",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only",
    },
    {
        "command_name": "export-alert-hygiene",
        "category": "alert hygiene",
        "purpose": "Export alert hygiene report CSV/MD",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    {
        "command_name": "apply-alert-triage",
        "category": "alert hygiene",
        "purpose": "Apply triage decisions to alerts",
        "mutates_db": True,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": False,
        "notes": "Mutates alert state",
    },
    {
        "command_name": "apply-alert-archive",
        "category": "alert hygiene",
        "purpose": "Archive resolved alerts",
        "mutates_db": True,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": False,
        "notes": "Mutates alert state",
    },
    {
        "command_name": "apply-alert-expiration",
        "category": "alert hygiene",
        "purpose": "Expire stale alerts per profile",
        "mutates_db": True,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": False,
        "notes": "Mutates alert state",
    },
    # portfolio review pack
    {
        "command_name": "export-portfolio-review-pack",
        "category": "portfolio review",
        "purpose": "Export portfolio review pack CSV/MD",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    {
        "command_name": "export-portfolio-review-comparison",
        "category": "portfolio review",
        "purpose": "Export portfolio comparison CSV/MD",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    {
        "command_name": "export-portfolio-review-trends",
        "category": "portfolio review",
        "purpose": "Export portfolio trends CSV/MD",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    # portfolio trend alerts
    {
        "command_name": "portfolio-trend-alerts",
        "category": "portfolio alerts",
        "purpose": "Evaluate portfolio trend alerts",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only evaluation",
    },
    {
        "command_name": "export-portfolio-trend-alert-digest",
        "category": "portfolio alerts",
        "purpose": "Export trend alert digest CSV/MD",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    {
        "command_name": "persist-portfolio-trend-alerts",
        "category": "portfolio alerts",
        "purpose": "Persist trend alert evaluation to history",
        "mutates_db": True,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Append-only history write",
    },
    {
        "command_name": "export-portfolio-trend-alert-run-comparison",
        "category": "portfolio alerts",
        "purpose": "Export alert run comparison CSV/MD",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    # alert focus
    {
        "command_name": "portfolio-alert-focus",
        "category": "alert focus",
        "purpose": "Preview focused alert items",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only display",
    },
    {
        "command_name": "export-portfolio-alert-focus-digest",
        "category": "alert focus",
        "purpose": "Export focus digest CSV/MD",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    {
        "command_name": "write-portfolio-alert-focus-template",
        "category": "alert focus",
        "purpose": "Generate focus preference config template",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": False,
        "notes": "Writes config file",
    },
    {
        "command_name": "validate-portfolio-alert-focus-config",
        "category": "alert focus",
        "purpose": "Validate focus preference config",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only validation",
    },
    # email digest draft
    {
        "command_name": "portfolio-alert-email-digest",
        "category": "email digest",
        "purpose": "Preview local email digest draft",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only, no email sent",
    },
    {
        "command_name": "export-portfolio-alert-email-digest",
        "category": "email digest",
        "purpose": "Export local email digest draft files",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export, no email sent",
    },
    # operations digest/history
    {
        "command_name": "snapshot-operations-digest",
        "category": "operations digest",
        "purpose": "Create operations digest snapshot",
        "mutates_db": True,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Append-only snapshot",
    },
    {
        "command_name": "export-operations-digest",
        "category": "operations digest",
        "purpose": "Export operations digest CSV/MD",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    {
        "command_name": "export-operations-digest-history",
        "category": "operations digest",
        "purpose": "Export operations digest history CSV/MD",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    {
        "command_name": "export-operations-digest-comparison",
        "category": "operations digest",
        "purpose": "Export operations digest comparison CSV/MD",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    # lifecycle health
    {
        "command_name": "lifecycle-health",
        "category": "lifecycle health",
        "purpose": "Show lifecycle health scores",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only",
    },
    {
        "command_name": "export-lifecycle-health",
        "category": "lifecycle health",
        "purpose": "Export lifecycle health report CSV/MD",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    {
        "command_name": "snapshot-lifecycle-health",
        "category": "lifecycle health",
        "purpose": "Create lifecycle health snapshot",
        "mutates_db": True,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Append-only snapshot",
    },
    # config templates
    {
        "command_name": "write-alert-expiration-profile-template",
        "category": "configuration",
        "purpose": "Generate alert expiration config template",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": False,
        "notes": "Writes config file",
    },
    {
        "command_name": "write-portfolio-trend-alert-rule-template",
        "category": "configuration",
        "purpose": "Generate trend alert rule config template",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": False,
        "notes": "Writes config file",
    },
    # local operations bundle (M48)
    {
        "command_name": "local-operations-bundle",
        "category": "operations bundle",
        "purpose": "Show local operations bundle summary",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only summary",
    },
    {
        "command_name": "export-local-operations-bundle",
        "category": "operations bundle",
        "purpose": "Export local operations bundle CSV/MD",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Local file export",
    },
    {
        "command_name": "local-operations-smoke-test",
        "category": "operations bundle",
        "purpose": "Run local read-only smoke test",
        "mutates_db": False,
        "live_retrieval_related": False,
        "safe_for_scheduler_default": True,
        "notes": "Read-only; does not invoke live retrieval",
    },
]


# -------------------------------------------------------------------
# Known report patterns for inventory
# -------------------------------------------------------------------

_REPORT_PATTERNS: List[Dict[str, str]] = [
    {
        "report_type": "candidate review",
        "glob": "candidate_review_*.csv",
    },
    {
        "report_type": "candidate analysis",
        "glob": "candidate_analysis_*.csv",
    },
    {
        "report_type": "watchlist monitoring",
        "glob": "watchlist_monitoring_*.csv",
    },
    {
        "report_type": "effective dom v2",
        "glob": "effective_dom_v2_*.csv",
    },
    {
        "report_type": "county verification",
        "glob": "county_verification_*.csv",
    },
    {
        "report_type": "cross-site comparison",
        "glob": "cross_site_comparison_*.csv",
    },
    {
        "report_type": "cross-site analytics",
        "glob": "cross_site_analytics_*.csv",
    },
    {
        "report_type": "cross-site trends",
        "glob": "cross_site_trend*.*",
    },
    {
        "report_type": "cross-site alerts",
        "glob": "cross_site_alert_*.csv",
    },
    {
        "report_type": "alert hygiene",
        "glob": "alert_hygiene_*.csv",
    },
    {
        "report_type": "alert lifecycle",
        "glob": "alert_lifecycle_*.csv",
    },
    {
        "report_type": "lifecycle health",
        "glob": "lifecycle_health_*.csv",
    },
    {
        "report_type": "operations digest",
        "glob": "operations_digest_*.*",
    },
    {
        "report_type": "portfolio review pack",
        "glob": "portfolio_review_pack_*.*",
    },
    {
        "report_type": "portfolio comparison",
        "glob": "portfolio_review_comparison_*.*",
    },
    {
        "report_type": "portfolio trends",
        "glob": "portfolio_review_trend*.*",
    },
    {
        "report_type": "portfolio trend alerts",
        "glob": "portfolio_trend_alert_digest_*.*",
    },
    {
        "report_type": "alert focus digest",
        "glob": "portfolio_alert_focus_digest_*.*",
    },
    {
        "report_type": "local email digest draft",
        "glob": "portfolio_alert_email_digest_*.*",
    },
    {
        "report_type": "local operations bundle",
        "glob": "local_operations_bundle_*.*",
    },
]


# -------------------------------------------------------------------
# Known config templates
# -------------------------------------------------------------------

_KNOWN_CONFIGS: List[Dict[str, Any]] = [
    {
        "config_path": ".env.example",
        "is_template": True,
        "notes": "Environment variable template",
    },
    {
        "config_path": "config/alert_expiration_profiles.example.json",
        "is_template": True,
        "notes": "Alert expiration profile template",
    },
    {
        "config_path": "config/portfolio_trend_alert_rules.example.json",
        "is_template": True,
        "notes": "Trend alert rule template",
    },
    {
        "config_path": (
            "config/portfolio_alert_highlight_preferences"
            ".example.json"
        ),
        "is_template": True,
        "notes": "Alert focus highlight preference template",
    },
    {
        "config_path": ".env",
        "is_template": False,
        "notes": "Local environment config (do not print contents)",
    },
    {
        "config_path": "config/alert_expiration_profiles.json",
        "is_template": False,
        "notes": "Local alert expiration profiles",
    },
    {
        "config_path": "config/portfolio_trend_alert_rules.json",
        "is_template": False,
        "notes": "Local trend alert rules",
    },
    {
        "config_path": (
            "config/portfolio_alert_highlight_preferences.json"
        ),
        "is_template": False,
        "notes": "Local alert highlight preferences",
    },
]


# -------------------------------------------------------------------
# Mutation / unsafe patterns for script scanning
# -------------------------------------------------------------------

_MUTATION_PATTERNS = [
    "import-",
    "retrieve-",
    "acknowledge-",
    "resolve-",
    "apply-alert-archive",
    "apply-alert-triage",
    "apply-alert-expiration",
    "delete",
    "update-",
]

_LIVE_RETRIEVAL_PATTERNS = [
    "--force-live",
    "retrieve-",
    "live-retrieve",
    "redfin-live",
]

_OUTBOUND_NOTIFICATION_PATTERNS = [
    "smtp",
    "send-email",
    "send-sms",
    "webhook",
    "send-notification",
]


# -------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------


def build_command_inventory() -> List[
    LocalOperationsCommandInventoryItem
]:
    """Build an inventory of known CLI commands.

    Returns a list of command inventory items with category,
    purpose, safety flags, and notes.
    """
    return [
        LocalOperationsCommandInventoryItem(**cmd)
        for cmd in _KNOWN_COMMANDS
    ]


def build_report_inventory(
    exports_dir: Optional[str] = None,
) -> List[LocalOperationsReportInventoryItem]:
    """Scan exports directory for known report file patterns.

    Args:
        exports_dir: Path to exports directory.
            Defaults to data/exports.

    Returns:
        List of report inventory items with freshness labels.
    """
    if exports_dir is None:
        exports_dir = "data/exports"

    exports_path = Path(exports_dir)
    items: List[LocalOperationsReportInventoryItem] = []
    now = datetime.now()
    stale_threshold = timedelta(days=7)

    for pattern_info in _REPORT_PATTERNS:
        report_type = pattern_info["report_type"]
        glob_pattern = pattern_info["glob"]

        if not exports_path.exists():
            items.append(
                LocalOperationsReportInventoryItem(
                    report_type=report_type,
                    freshness="missing",
                    notes="Exports directory does not exist",
                )
            )
            continue

        matches = sorted(
            exports_path.glob(glob_pattern),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )

        if not matches:
            items.append(
                LocalOperationsReportInventoryItem(
                    report_type=report_type,
                    freshness="missing",
                    notes="No files found",
                )
            )
            continue

        latest = matches[0]
        mtime = datetime.fromtimestamp(latest.stat().st_mtime)
        age = now - mtime
        freshness = "fresh" if age < stale_threshold else "stale"

        row_count = -1
        if latest.suffix == ".csv":
            try:
                text = latest.read_text(encoding="utf-8")
                row_count = max(
                    len(text.strip().splitlines()) - 1, 0
                )
            except Exception:
                row_count = -1

        items.append(
            LocalOperationsReportInventoryItem(
                report_type=report_type,
                latest_file_path=str(latest),
                latest_modified=mtime.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                file_count=len(matches),
                row_count=row_count,
                freshness=freshness,
                notes="",
            )
        )

    return items


def build_scheduler_script_inventory(
    scripts_dir: Optional[str] = None,
) -> List[LocalOperationsScriptInventoryItem]:
    """Scan scripts directory for scheduled script files.

    Args:
        scripts_dir: Path to scripts directory.
            Defaults to scripts/.

    Returns:
        List of script inventory items with safety flags.
    """
    if scripts_dir is None:
        scripts_dir = "scripts"

    scripts_path = Path(scripts_dir)
    items: List[LocalOperationsScriptInventoryItem] = []

    if not scripts_path.exists():
        return items

    for ext in ("*.bat", "*.ps1"):
        for script_file in sorted(scripts_path.glob(ext)):
            item = _analyze_script(script_file)
            items.append(item)

    return items


def _analyze_script(
    script_path: Path,
) -> LocalOperationsScriptInventoryItem:
    """Analyze a single script file for safety flags.

    Args:
        script_path: Path to the script file.

    Returns:
        Script inventory item with safety analysis.
    """
    item = LocalOperationsScriptInventoryItem(
        script_path=str(script_path),
        script_type=script_path.suffix.lstrip("."),
        exists=script_path.exists(),
    )

    if not script_path.exists():
        item.safe_status = "unknown"
        item.notes = "File does not exist"
        return item

    try:
        content = script_path.read_text(encoding="utf-8")
    except Exception:
        item.safe_status = "review"
        item.notes = "Could not read file"
        return item

    lines = [
        line
        for line in content.splitlines()
        if not line.strip().startswith("REM")
        and not line.strip().startswith("#")
        and not line.strip().startswith("::")
    ]
    text_lower = "\n".join(lines).lower()

    for pat in _LIVE_RETRIEVAL_PATTERNS:
        if pat in text_lower:
            item.contains_live_retrieval_command = True
            break

    if "--force-live" in text_lower:
        item.contains_force_live = True

    for pat in _MUTATION_PATTERNS:
        if pat in text_lower:
            # Exclude safe export-only commands that happen to
            # contain 'import-' pattern
            if pat == "import-" and "import-review" in text_lower:
                item.contains_mutation_command = True
            elif pat == "import-":
                # import- in export commands is safe
                pass
            else:
                item.contains_mutation_command = True
                break

    for pat in _OUTBOUND_NOTIFICATION_PATTERNS:
        if pat in text_lower:
            item.contains_outbound_notification_command = True
            break

    if (
        item.contains_live_retrieval_command
        or item.contains_force_live
        or item.contains_outbound_notification_command
    ):
        item.safe_status = "unsafe"
    elif item.contains_mutation_command:
        item.safe_status = "review"
    else:
        item.safe_status = "safe"

    return item


def build_config_inventory(
    project_root: Optional[str] = None,
) -> List[LocalOperationsConfigInventoryItem]:
    """Inspect known config templates and local config files.

    Args:
        project_root: Project root directory.
            Defaults to current directory.

    Returns:
        List of config inventory items.
    """
    if project_root is None:
        project_root = "."

    root = Path(project_root)
    items: List[LocalOperationsConfigInventoryItem] = []

    for cfg in _KNOWN_CONFIGS:
        cfg_path = root / cfg["config_path"]
        exists = cfg_path.exists()

        validation_status = "unknown"
        if exists and cfg["is_template"]:
            validation_status = "template_present"
        elif exists and not cfg["is_template"]:
            validation_status = "config_present"
        elif not exists and cfg["is_template"]:
            validation_status = "template_missing"
        elif not exists and not cfg["is_template"]:
            validation_status = "not_configured"

        items.append(
            LocalOperationsConfigInventoryItem(
                config_path=cfg["config_path"],
                exists=exists,
                is_template=cfg["is_template"],
                validation_status=validation_status,
                notes=cfg.get("notes", ""),
            )
        )

    return items


def run_local_safety_audit(
    project_root: Optional[str] = None,
    scripts_dir: Optional[str] = None,
) -> List[LocalOperationsSafetyCheck]:
    """Run local static safety checks on the project.

    Checks for browser automation references, outbound notification
    references, live retrieval scheduled by default, unsafe
    scheduler commands, walkability fields, Redfin source-of-truth
    overwrite patterns, Quiet Score gatekeeper modifications, and
    network imports in report-only modules.

    Args:
        project_root: Project root directory.
        scripts_dir: Scripts directory.

    Returns:
        List of safety check results.
    """
    if project_root is None:
        project_root = "."
    if scripts_dir is None:
        scripts_dir = "scripts"

    checks: List[LocalOperationsSafetyCheck] = []

    # Check 1: browser automation in source modules
    # Exclude local_operations_bundle.py because it contains
    # these patterns as audit search strings, not imports.
    checks.append(
        _check_source_for_patterns(
            project_root,
            "browser_automation",
            [
                "from playwright",
                "import playwright",
                "from selenium",
                "import selenium",
            ],
            "Browser automation import detected",
            "Remove browser automation imports",
            exclude_files=["local_operations_bundle.py"],
        )
    )

    # Check 2: outbound notification in source modules
    # Exclude local_operations_bundle.py because it contains
    # these patterns as audit search strings, not imports.
    checks.append(
        _check_source_for_patterns(
            project_root,
            "outbound_notification_imports",
            [
                "import smtplib",
                "from smtplib",
                "import twilio",
                "from twilio",
            ],
            "Outbound notification import detected",
            "Remove outbound notification imports",
            exclude_files=["local_operations_bundle.py"],
        )
    )

    # Check 3: walkability fields in source modules
    # Exclude modules that contain walkability strings as
    # validation guard patterns (forbidden config keys).
    checks.append(
        _check_source_for_patterns(
            project_root,
            "walkability_fields",
            [
                "walkability_score",
                "walk_score",
                "walkability_rating",
            ],
            "Walkability field detected in source",
            "Remove walkability fields",
            exclude_files=[
                "local_operations_bundle.py",
                "portfolio_alert_focus.py",
                "portfolio_trend_alerts.py",
            ],
        )
    )

    # Check 4: scheduled scripts safety
    scripts_path = Path(scripts_dir)
    script_safe = True
    script_detail = "All scheduled scripts are safe"
    if scripts_path.exists():
        for ext in ("*.bat", "*.ps1"):
            for sf in scripts_path.glob(ext):
                analysis = _analyze_script(sf)
                if analysis.safe_status == "unsafe":
                    script_safe = False
                    script_detail = (
                        f"Unsafe script: {sf.name}"
                    )
                    break

    checks.append(
        LocalOperationsSafetyCheck(
            check_name="scheduled_script_safety",
            status="pass" if script_safe else "warning",
            detail=script_detail,
            recommended_local_action=(
                ""
                if script_safe
                else "Review flagged scripts"
            ),
        )
    )

    # Check 5: Quiet Score gatekeeper
    checks.append(
        _check_source_for_patterns(
            project_root,
            "quiet_gatekeeper_modification",
            [
                "QUIET_THRESHOLD = ",
                "quiet_threshold =",
            ],
            "Quiet Score threshold modification detected",
            "Verify gatekeeper threshold remains at 70.0",
            exclude_files=[
                "config.py",
                "scoring.py",
                "quiet_vibrancy.py",
                "local_operations_bundle.py",
            ],
        )
    )

    # Check 6: Redfin source-of-truth overwrite
    checks.append(
        _check_source_for_patterns(
            project_root,
            "redfin_sot_overwrite",
            [
                "redfin_source_of_truth = ",
                "overwrite_redfin_sot",
            ],
            "Redfin source-of-truth overwrite pattern detected",
            "Verify Redfin SOT fields are not overwritten",
            exclude_files=["local_operations_bundle.py"],
        )
    )

    # Check 7: network imports in report modules
    # Exclude local_operations_bundle.py because it contains
    # network import strings as audit search patterns.
    report_modules = [
        "portfolio_alert_email_digest.py",
        "portfolio_alert_focus.py",
        "portfolio_trend_alert_history.py",
    ]
    net_safe = True
    net_detail = "No network imports in report modules"
    src_dir = Path(project_root) / "src" / "marketsentry"
    for mod_name in report_modules:
        mod_path = src_dir / mod_name
        if mod_path.exists():
            try:
                source = mod_path.read_text(encoding="utf-8")
                for pat in [
                    "import requests",
                    "from requests",
                    "import httpx",
                    "from httpx",
                    "import urllib.request",
                    "from urllib.request",
                ]:
                    if pat in source:
                        net_safe = False
                        net_detail = (
                            f"Network import in {mod_name}"
                        )
                        break
            except Exception:
                pass
        if not net_safe:
            break

    checks.append(
        LocalOperationsSafetyCheck(
            check_name="report_module_network_imports",
            status="pass" if net_safe else "fail",
            detail=net_detail,
            recommended_local_action=(
                ""
                if net_safe
                else "Remove network imports from report modules"
            ),
        )
    )

    return checks


def _check_source_for_patterns(
    project_root: str,
    check_name: str,
    patterns: List[str],
    fail_detail: str,
    action: str,
    exclude_files: Optional[List[str]] = None,
) -> LocalOperationsSafetyCheck:
    """Check source files for specific patterns.

    Args:
        project_root: Project root directory.
        check_name: Name of the safety check.
        patterns: List of string patterns to search for.
        fail_detail: Detail message if pattern found.
        action: Recommended action if pattern found.
        exclude_files: Files to exclude from checking.

    Returns:
        Safety check result.
    """
    src_dir = Path(project_root) / "src" / "marketsentry"
    if exclude_files is None:
        exclude_files = []

    if not src_dir.exists():
        return LocalOperationsSafetyCheck(
            check_name=check_name,
            status="pass",
            detail="Source directory not found (clean)",
        )

    for py_file in src_dir.glob("*.py"):
        if py_file.name in exclude_files:
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            for pat in patterns:
                if pat in source:
                    return LocalOperationsSafetyCheck(
                        check_name=check_name,
                        status="fail",
                        detail=f"{fail_detail}: {py_file.name}",
                        file_path=str(py_file),
                        recommended_local_action=action,
                    )
        except Exception:
            continue

    return LocalOperationsSafetyCheck(
        check_name=check_name,
        status="pass",
        detail=f"No {check_name} patterns found",
    )


def run_report_freshness_audit(
    exports_dir: Optional[str] = None,
) -> List[LocalOperationsReportInventoryItem]:
    """Run a freshness audit on exported reports.

    Delegates to build_report_inventory for consistency.

    Args:
        exports_dir: Path to exports directory.

    Returns:
        List of report inventory items with freshness labels.
    """
    return build_report_inventory(exports_dir)


def build_database_schema_inventory(
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Inspect SQLite database schema.

    Args:
        db_path: Path to the SQLite database file.
            Defaults to data/market_sentry.db.

    Returns:
        Dictionary with table_count, table_names,
        column_counts, index_counts, and notes.
    """
    if db_path is None:
        db_path = "data/market_sentry.db"

    result: Dict[str, Any] = {
        "db_path": db_path,
        "exists": False,
        "table_count": 0,
        "table_names": [],
        "column_counts": {},
        "index_counts": {},
        "notes": "",
    }

    db_file = Path(db_path)
    if not db_file.exists():
        result["notes"] = "Database file does not exist"
        return result

    result["exists"] = True

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        result["table_count"] = len(tables)
        result["table_names"] = tables

        for table in tables:
            cursor.execute(
                f"PRAGMA table_info('{table}')"  # noqa: S608
            )
            cols = cursor.fetchall()
            result["column_counts"][table] = len(cols)

        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        )
        all_indexes = cursor.fetchall()
        result["index_counts"]["total"] = len(all_indexes)

        conn.close()
    except Exception as e:
        result["notes"] = f"Error reading database: {e}"

    return result


def run_local_smoke_test(
    db_path: Optional[str] = None,
    use_temp_db: bool = True,
) -> List[LocalOperationsSafetyCheck]:
    """Run lightweight local smoke tests.

    Verifies package imports, config loads, database init,
    dashboard import, key module imports, and export directory
    existence. Does not run full pytest or invoke live retrieval.

    Args:
        db_path: Path to database. Ignored if use_temp_db is True.
        use_temp_db: If True, uses a temporary database path.

    Returns:
        List of smoke test check results.
    """
    checks: List[LocalOperationsSafetyCheck] = []

    # Check 1: package imports
    try:
        import marketsentry  # noqa: F401

        checks.append(
            LocalOperationsSafetyCheck(
                check_name="package_import",
                status="pass",
                detail="marketsentry package imports cleanly",
            )
        )
    except Exception as e:
        checks.append(
            LocalOperationsSafetyCheck(
                check_name="package_import",
                status="fail",
                detail=f"Import failed: {e}",
                recommended_local_action=(
                    "Fix package import errors"
                ),
            )
        )

    # Check 2: config loads
    try:
        from marketsentry.config import config as _cfg  # noqa: F401

        checks.append(
            LocalOperationsSafetyCheck(
                check_name="config_load",
                status="pass",
                detail="Config module loads cleanly",
            )
        )
    except Exception as e:
        checks.append(
            LocalOperationsSafetyCheck(
                check_name="config_load",
                status="fail",
                detail=f"Config load failed: {e}",
                recommended_local_action=(
                    "Fix config module errors"
                ),
            )
        )

    # Check 3: database init
    try:
        import tempfile

        from marketsentry.database import init_db as _init

        if use_temp_db:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".db", delete=False
            )
            test_db = tmp.name
            tmp.close()
        else:
            test_db = db_path or "data/market_sentry.db"

        _init(test_db)

        if use_temp_db:
            Path(test_db).unlink(missing_ok=True)

        checks.append(
            LocalOperationsSafetyCheck(
                check_name="database_init",
                status="pass",
                detail="Database init succeeds",
            )
        )
    except Exception as e:
        checks.append(
            LocalOperationsSafetyCheck(
                check_name="database_init",
                status="fail",
                detail=f"Database init failed: {e}",
                recommended_local_action=(
                    "Fix database initialization"
                ),
            )
        )

    # Check 4: dashboard summary import
    try:
        from marketsentry.dashboard_app import (  # noqa: F401
            build_dashboard_summary as _ds,
        )

        checks.append(
            LocalOperationsSafetyCheck(
                check_name="dashboard_import",
                status="pass",
                detail="Dashboard summary module imports",
            )
        )
    except Exception:
        checks.append(
            LocalOperationsSafetyCheck(
                check_name="dashboard_import",
                status="warning",
                detail="Dashboard import unavailable",
                recommended_local_action=(
                    "Install streamlit for dashboard"
                ),
            )
        )

    # Check 5: key report modules import
    key_modules = [
        "marketsentry.portfolio_alert_email_digest",
        "marketsentry.portfolio_alert_focus",
        "marketsentry.portfolio_trend_alert_history",
    ]
    all_ok = True
    failed_mod = ""
    for mod_name in key_modules:
        try:
            __import__(mod_name)
        except Exception:
            all_ok = False
            failed_mod = mod_name
            break

    if all_ok:
        checks.append(
            LocalOperationsSafetyCheck(
                check_name="report_modules_import",
                status="pass",
                detail="Key report modules import cleanly",
            )
        )
    else:
        checks.append(
            LocalOperationsSafetyCheck(
                check_name="report_modules_import",
                status="fail",
                detail=f"Module import failed: {failed_mod}",
                recommended_local_action=(
                    "Fix module import errors"
                ),
            )
        )

    # Check 6: export directory
    exports_path = Path("data/exports")
    if exports_path.exists():
        checks.append(
            LocalOperationsSafetyCheck(
                check_name="export_directory",
                status="pass",
                detail="data/exports directory exists",
            )
        )
    else:
        try:
            exports_path.mkdir(parents=True, exist_ok=True)
            checks.append(
                LocalOperationsSafetyCheck(
                    check_name="export_directory",
                    status="pass",
                    detail=(
                        "data/exports directory created"
                    ),
                )
            )
        except Exception as e:
            checks.append(
                LocalOperationsSafetyCheck(
                    check_name="export_directory",
                    status="fail",
                    detail=f"Cannot create exports dir: {e}",
                    recommended_local_action=(
                        "Create data/exports directory"
                    ),
                )
            )

    return checks


def build_local_operations_bundle(
    db_path: Optional[str] = None,
    exports_dir: Optional[str] = None,
    project_root: Optional[str] = None,
    scripts_dir: Optional[str] = None,
) -> LocalOperationsBundleRunResult:
    """Build the complete local operations bundle.

    Aggregates command inventory, report inventory, script
    inventory, config inventory, safety audit, schema inventory,
    and smoke test results.

    Args:
        db_path: Path to SQLite database.
        exports_dir: Path to exports directory.
        project_root: Project root directory.
        scripts_dir: Scripts directory.

    Returns:
        Complete bundle run result.
    """
    commands = build_command_inventory()
    reports = build_report_inventory(exports_dir)
    scripts = build_scheduler_script_inventory(scripts_dir)
    configs = build_config_inventory(project_root)
    safety = run_local_safety_audit(project_root, scripts_dir)
    schema = build_database_schema_inventory(db_path)
    smoke = run_local_smoke_test(db_path, use_temp_db=True)

    s_pass = sum(1 for c in safety if c.status == "pass")
    s_warn = sum(1 for c in safety if c.status == "warning")
    s_fail = sum(1 for c in safety if c.status == "fail")

    sc_safe = sum(
        1 for s in scripts if s.safe_status == "safe"
    )
    sc_review = sum(
        1 for s in scripts if s.safe_status == "review"
    )
    sc_unsafe = sum(
        1 for s in scripts if s.safe_status == "unsafe"
    )

    c_valid = sum(
        1
        for c in configs
        if c.validation_status
        in ("template_present", "config_present")
    )
    c_missing = sum(
        1
        for c in configs
        if c.validation_status
        in ("template_missing", "not_configured")
    )
    c_unknown = sum(
        1 for c in configs if c.validation_status == "unknown"
    )

    sm_pass = sum(1 for t in smoke if t.status == "pass")
    sm_warn = sum(1 for t in smoke if t.status == "warning")
    sm_fail = sum(1 for t in smoke if t.status == "fail")

    report_groups = len(
        {r.report_type for r in reports if r.freshness != "missing"}
    )

    summary = LocalOperationsBundleSummary(
        command_count=len(commands),
        report_group_count=report_groups,
        safety_audit_pass=s_pass,
        safety_audit_warn=s_warn,
        safety_audit_fail=s_fail,
        script_safe_count=sc_safe,
        script_review_count=sc_review,
        script_unsafe_count=sc_unsafe,
        config_valid_count=c_valid,
        config_missing_count=c_missing,
        config_unknown_count=c_unknown,
        table_count=schema.get("table_count", 0),
        smoke_test_pass=sm_pass,
        smoke_test_warn=sm_warn,
        smoke_test_fail=sm_fail,
        generated_at=datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )

    return LocalOperationsBundleRunResult(
        summary=summary,
        commands=commands,
        reports=reports,
        scripts=scripts,
        configs=configs,
        safety_checks=safety,
        schema_tables=schema.get("table_names", []),
        schema_info=schema,
        smoke_tests=smoke,
    )


def export_local_operations_bundle(
    bundle: LocalOperationsBundleRunResult,
    output_dir: Optional[str] = None,
    fmt: str = "both",
) -> LocalOperationsBundleRunResult:
    """Export the local operations bundle to Markdown and/or CSV.

    Args:
        bundle: The bundle run result to export.
        output_dir: Output directory for exports.
            Defaults to data/exports.
        fmt: Export format - csv, md, or both.

    Returns:
        Updated bundle with output_paths populated.
    """
    if output_dir is None:
        output_dir = "data/exports"

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"local_operations_bundle_{ts}"

    paths: List[str] = []

    if fmt in ("md", "both"):
        md_path = out_path / f"{base}.md"
        md_content = _build_markdown(bundle)
        md_path.write_text(md_content, encoding="utf-8")
        paths.append(str(md_path))

    if fmt in ("csv", "both"):
        csv_path = out_path / f"{base}.csv"
        csv_content = _build_csv(bundle)
        csv_path.write_text(csv_content, encoding="utf-8")
        paths.append(str(csv_path))

    bundle.output_paths = paths
    return bundle


# -------------------------------------------------------------------
# Internal formatting helpers
# -------------------------------------------------------------------


def _build_markdown(
    bundle: LocalOperationsBundleRunResult,
) -> str:
    """Build Markdown content for the operations bundle.

    Args:
        bundle: The bundle run result.

    Returns:
        Markdown string.
    """
    s = bundle.summary
    lines = [
        "# Local Operations Bundle - Release Candidate Summary",
        "",
        f"Generated: {s.generated_at}",
        "",
        "## Summary",
        "",
        f"- Commands: {s.command_count}",
        f"- Report groups with files: {s.report_group_count}",
        f"- Safety audit: {s.safety_audit_pass} pass, "
        f"{s.safety_audit_warn} warn, "
        f"{s.safety_audit_fail} fail",
        f"- Scripts: {s.script_safe_count} safe, "
        f"{s.script_review_count} review, "
        f"{s.script_unsafe_count} unsafe",
        f"- Configs: {s.config_valid_count} present, "
        f"{s.config_missing_count} missing, "
        f"{s.config_unknown_count} unknown",
        f"- Database tables: {s.table_count}",
        f"- Smoke tests: {s.smoke_test_pass} pass, "
        f"{s.smoke_test_warn} warn, "
        f"{s.smoke_test_fail} fail",
        "",
    ]

    # Command inventory
    lines.append("## Command Inventory")
    lines.append("")
    lines.append(
        "| Command | Category | Purpose | "
        "Mutates DB | Live Retrieval | Scheduler Safe |"
    )
    lines.append(
        "|---------|----------|---------|"
        "-----------|----------------|----------------|"
    )
    for cmd in bundle.commands:
        lines.append(
            f"| {cmd.command_name} | {cmd.category} | "
            f"{cmd.purpose} | "
            f"{'Yes' if cmd.mutates_db else 'No'} | "
            f"{'Yes' if cmd.live_retrieval_related else 'No'} | "
            f"{'Yes' if cmd.safe_for_scheduler_default else 'No'}"
            f" |"
        )
    lines.append("")

    # Report inventory
    lines.append("## Report Inventory / Freshness")
    lines.append("")
    lines.append(
        "| Report Type | Freshness | Files | "
        "Rows | Latest Modified | Latest File |"
    )
    lines.append(
        "|-------------|-----------|-------|"
        "-----|-----------------|-------------|"
    )
    for rpt in bundle.reports:
        row_str = (
            str(rpt.row_count) if rpt.row_count >= 0 else "-"
        )
        lines.append(
            f"| {rpt.report_type} | {rpt.freshness} | "
            f"{rpt.file_count} | {row_str} | "
            f"{rpt.latest_modified or '-'} | "
            f"{rpt.latest_file_path or '-'} |"
        )
    lines.append("")

    # Script safety inventory
    lines.append("## Scheduled Script Safety")
    lines.append("")
    lines.append(
        "| Script | Type | Safe Status | "
        "Live Retrieval | Force Live | "
        "Mutation | Notification |"
    )
    lines.append(
        "|--------|------|-------------|"
        "----------------|------------|"
        "----------|--------------|"
    )
    for scr in bundle.scripts:
        lines.append(
            f"| {scr.script_path} | {scr.script_type} | "
            f"{scr.safe_status} | "
            f"{'Yes' if scr.contains_live_retrieval_command else 'No'} | "
            f"{'Yes' if scr.contains_force_live else 'No'} | "
            f"{'Yes' if scr.contains_mutation_command else 'No'} | "
            f"{'Yes' if scr.contains_outbound_notification_command else 'No'}"
            f" |"
        )
    lines.append("")

    # Config inventory
    lines.append("## Configuration Inventory")
    lines.append("")
    lines.append(
        "| Config Path | Exists | Template | "
        "Validation | Notes |"
    )
    lines.append(
        "|-------------|--------|----------|"
        "------------|-------|"
    )
    for cfg in bundle.configs:
        lines.append(
            f"| {cfg.config_path} | "
            f"{'Yes' if cfg.exists else 'No'} | "
            f"{'Yes' if cfg.is_template else 'No'} | "
            f"{cfg.validation_status} | {cfg.notes} |"
        )
    lines.append("")

    # Safety audit
    lines.append("## Safety Audit")
    lines.append("")
    lines.append(
        "| Check | Status | Detail | "
        "Recommended Action |"
    )
    lines.append(
        "|-------|--------|--------|"
        "--------------------|"
    )
    for chk in bundle.safety_checks:
        lines.append(
            f"| {chk.check_name} | {chk.status} | "
            f"{chk.detail} | "
            f"{chk.recommended_local_action or '-'} |"
        )
    lines.append("")

    # Schema inventory
    lines.append("## Database Schema Inventory")
    lines.append("")
    si = bundle.schema_info
    lines.append(
        f"- Database path: {si.get('db_path', 'unknown')}"
    )
    lines.append(
        f"- Exists: {'Yes' if si.get('exists') else 'No'}"
    )
    lines.append(f"- Table count: {si.get('table_count', 0)}")
    if bundle.schema_tables:
        lines.append(f"- Tables: {', '.join(bundle.schema_tables)}")
    if si.get("notes"):
        lines.append(f"- Notes: {si['notes']}")
    lines.append("")

    # Smoke test summary
    lines.append("## Smoke Test Summary")
    lines.append("")
    lines.append("| Check | Status | Detail |")
    lines.append("|-------|--------|--------|")
    for st in bundle.smoke_tests:
        lines.append(
            f"| {st.check_name} | {st.status} | "
            f"{st.detail} |"
        )
    lines.append("")

    # Recommended next actions
    lines.append("## Recommended Local Next Actions")
    lines.append("")
    actions_added = False
    for chk in bundle.safety_checks + bundle.smoke_tests:
        if chk.recommended_local_action:
            lines.append(
                f"- [{chk.check_name}] "
                f"{chk.recommended_local_action}"
            )
            actions_added = True
    if not actions_added:
        lines.append("- No recommended actions. All checks pass.")
    lines.append("")

    return "\n".join(lines)


def _build_csv(
    bundle: LocalOperationsBundleRunResult,
) -> str:
    """Build CSV content for the operations bundle.

    Args:
        bundle: The bundle run result.

    Returns:
        CSV string.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "section",
            "item_name",
            "status",
            "category",
            "detail",
            "file_path",
            "recommended_local_action",
        ]
    )

    for cmd in bundle.commands:
        safe_label = (
            "scheduler_safe"
            if cmd.safe_for_scheduler_default
            else "not_scheduler_safe"
        )
        writer.writerow(
            [
                "command_inventory",
                cmd.command_name,
                safe_label,
                cmd.category,
                cmd.purpose,
                "",
                cmd.notes,
            ]
        )

    for rpt in bundle.reports:
        writer.writerow(
            [
                "report_inventory",
                rpt.report_type,
                rpt.freshness,
                "",
                f"files={rpt.file_count} rows={rpt.row_count}",
                rpt.latest_file_path,
                rpt.notes,
            ]
        )

    for scr in bundle.scripts:
        writer.writerow(
            [
                "script_inventory",
                scr.script_path,
                scr.safe_status,
                scr.script_type,
                "",
                scr.script_path,
                scr.notes,
            ]
        )

    for cfg in bundle.configs:
        writer.writerow(
            [
                "config_inventory",
                cfg.config_path,
                cfg.validation_status,
                "template" if cfg.is_template else "config",
                cfg.notes,
                cfg.config_path,
                "",
            ]
        )

    for chk in bundle.safety_checks:
        writer.writerow(
            [
                "safety_audit",
                chk.check_name,
                chk.status,
                "",
                chk.detail,
                chk.file_path,
                chk.recommended_local_action,
            ]
        )

    si = bundle.schema_info
    writer.writerow(
        [
            "schema_inventory",
            si.get("db_path", ""),
            "exists" if si.get("exists") else "missing",
            "",
            f"tables={si.get('table_count', 0)}",
            si.get("db_path", ""),
            si.get("notes", ""),
        ]
    )

    for st_item in bundle.smoke_tests:
        writer.writerow(
            [
                "smoke_test",
                st_item.check_name,
                st_item.status,
                "",
                st_item.detail,
                st_item.file_path,
                st_item.recommended_local_action,
            ]
        )

    return output.getvalue()
