"""Retrieval operations dashboard data loading and reporting.

Provides typed models and read-only data-loading helpers for the
retrieval operations dashboard. All functions operate on local files
(CSV manifests, audit logs, SQLite database, fixture directories).
No network calls are performed.

Testable without launching Streamlit.
"""

import csv
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from marketsentry.logging_config import logger


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RetrievalOperationsSummary(BaseModel):
    """Overview summary of the retrieval ecosystem."""

    pending_capture_requests: int = 0
    captured_capture_requests: int = 0
    skipped_capture_requests: int = 0
    invalid_capture_requests: int = 0
    archived_capture_requests: int = 0
    total_capture_requests: int = 0

    approval_packages_created: int = 0
    approved_rows_pending_retrieval: int = 0

    batch_retrieval_runs: int = 0
    retrieved_fixture_count: int = 0
    blocked_retrieval_decisions: int = 0

    audit_records_network_true: int = 0
    audit_records_network_false: int = 0
    audit_total_decisions: int = 0
    audit_allowed: int = 0
    audit_blocked: int = 0
    audit_dry_runs: int = 0

    latest_audit_file: str = ""
    latest_approval_package: str = ""
    latest_batch_manifest: str = ""

    live_retrieval_enabled: bool = False
    allowed_sources: str = ""
    user_agent_configured: bool = False
    contact_email_configured: bool = False
    dry_run_required: bool = True
    max_requests_per_minute: int = 6


class FixtureCaptureQueueTable(BaseModel):
    """Table data for the fixture capture queue."""

    rows: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=lambda: [
        "capture_request_id", "created_at", "source_site", "request_type",
        "source_url", "suggested_fixture_path", "status", "priority",
        "reason", "notes",
    ])


class RetrievalApprovalPackageTable(BaseModel):
    """Table data for retrieval approval packages."""

    rows: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=lambda: [
        "approval_run_id", "created_at", "pending_scanned",
        "approval_rows_written", "approval_csv_path",
        "approval_summary_path", "approved_count_when_imported",
        "retrieved_count", "blocked_count", "failed_count", "notes",
    ])
    latest_csv_files: List[str] = Field(default_factory=list)


class BatchRetrievalManifestTable(BaseModel):
    """Table data for batch retrieval manifest."""

    rows: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=lambda: [
        "run_id", "started_at", "completed_at", "mode",
        "pending_scanned", "attempted_live", "retrieved", "blocked",
        "failed", "fixtures_saved", "processed_after_retrieval",
        "queue_items_marked_captured",
    ])


class BatchRetrievalItemTable(BaseModel):
    """Table data for per-item batch retrieval results."""

    rows: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=lambda: [
        "run_id", "capture_request_id", "source_url", "request_type",
        "decision", "network_call_performed", "fixture_path",
        "status", "reason", "error",
    ])


class RetrievalAuditSummaryTable(BaseModel):
    """Summary data from retrieval audit logs."""

    total_records: int = 0
    allowed: int = 0
    blocked: int = 0
    dry_runs: int = 0
    live_attempts: int = 0
    network_call_true: int = 0
    network_call_false: int = 0
    blocked_reasons: Dict[str, int] = Field(default_factory=dict)
    latest_audit_file: str = ""
    files_scanned: int = 0


class DryRunApprovalSummaryTable(BaseModel):
    """Summary data from dry-run approval logs."""

    total_records: int = 0
    allowed: int = 0
    blocked: int = 0
    latest_file: str = ""
    files_scanned: int = 0
    rows: List[Dict[str, Any]] = Field(default_factory=list)


class RetrievedFixtureInventoryTable(BaseModel):
    """Inventory of retrieved fixture files."""

    rows: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=lambda: [
        "fixture_path", "fixture_type", "metadata_path",
        "source_url", "retrieved_at", "content_length",
        "content_hash", "processed",
    ])
    total_search_fixtures: int = 0
    total_detail_fixtures: int = 0


class RetrievalOperationsTables(BaseModel):
    """All dashboard tables for retrieval operations."""

    summary: RetrievalOperationsSummary = Field(
        default_factory=RetrievalOperationsSummary
    )
    capture_queue: FixtureCaptureQueueTable = Field(
        default_factory=FixtureCaptureQueueTable
    )
    approval_packages: RetrievalApprovalPackageTable = Field(
        default_factory=RetrievalApprovalPackageTable
    )
    batch_manifest: BatchRetrievalManifestTable = Field(
        default_factory=BatchRetrievalManifestTable
    )
    batch_items: BatchRetrievalItemTable = Field(
        default_factory=BatchRetrievalItemTable
    )
    audit_summary: RetrievalAuditSummaryTable = Field(
        default_factory=RetrievalAuditSummaryTable
    )
    dry_run_summary: DryRunApprovalSummaryTable = Field(
        default_factory=DryRunApprovalSummaryTable
    )
    fixture_inventory: RetrievedFixtureInventoryTable = Field(
        default_factory=RetrievedFixtureInventoryTable
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def get_retrieval_operations_summary(
    database_path: Optional[str] = None,
    audit_dir: Optional[str] = None,
    processed_dir: Optional[str] = None,
    approvals_dir: Optional[str] = None,
) -> RetrievalOperationsSummary:
    """Build a high-level summary of retrieval operations.

    Args:
        database_path: Path to database file.
        audit_dir: Path to audit log directory.
        processed_dir: Path to processed data directory.
        approvals_dir: Path to approval exports directory.

    Returns:
        RetrievalOperationsSummary with all counts.
    """
    summary = RetrievalOperationsSummary()

    # Capture queue counts
    queue = load_fixture_capture_queue_table(database_path=database_path)
    for row in queue.rows:
        status = row.get("status", "")
        if status == "pending":
            summary.pending_capture_requests += 1
        elif status == "captured":
            summary.captured_capture_requests += 1
        elif status == "skipped":
            summary.skipped_capture_requests += 1
        elif status == "invalid":
            summary.invalid_capture_requests += 1
        elif status == "archived":
            summary.archived_capture_requests += 1
    summary.total_capture_requests = len(queue.rows)

    # Approval manifest
    approval_manifest = load_retrieval_approval_manifest(
        processed_dir=processed_dir
    )
    summary.approval_packages_created = len(approval_manifest.rows)

    # Count approved rows pending retrieval
    total_approved = 0
    total_retrieved = 0
    for row in approval_manifest.rows:
        try:
            total_approved += int(row.get("approved_count_when_imported", 0))
            total_retrieved += int(row.get("retrieved_count", 0))
        except (ValueError, TypeError):
            pass
    summary.approved_rows_pending_retrieval = max(
        0, total_approved - total_retrieved
    )

    # Latest approval package
    if approval_manifest.latest_csv_files:
        summary.latest_approval_package = approval_manifest.latest_csv_files[0]

    # Batch retrieval manifest
    batch_manifest = load_batch_retrieval_manifest(processed_dir=processed_dir)
    summary.batch_retrieval_runs = len(batch_manifest.rows)
    for row in batch_manifest.rows:
        try:
            summary.retrieved_fixture_count += int(row.get("retrieved", 0))
            summary.blocked_retrieval_decisions += int(row.get("blocked", 0))
        except (ValueError, TypeError):
            pass

    if batch_manifest.rows:
        summary.latest_batch_manifest = str(
            Path(processed_dir or "data/processed")
            / "redfin_batch_retrieval_manifest.csv"
        )

    # Audit summary
    audit = load_retrieval_audit_summary(audit_dir=audit_dir)
    summary.audit_total_decisions = audit.total_records
    summary.audit_allowed = audit.allowed
    summary.audit_blocked = audit.blocked
    summary.audit_dry_runs = audit.dry_runs
    summary.audit_records_network_true = audit.network_call_true
    summary.audit_records_network_false = audit.network_call_false
    summary.latest_audit_file = audit.latest_audit_file

    # Safety indicators from environment
    from marketsentry.source_adapters.compliance import (
        RetrievalComplianceConfig,
    )

    cc = RetrievalComplianceConfig.from_env()
    summary.live_retrieval_enabled = cc.live_retrieval_enabled
    summary.allowed_sources = ", ".join(cc.allowed_live_sources) or "(none)"
    summary.user_agent_configured = bool(cc.live_user_agent)
    summary.contact_email_configured = bool(cc.live_contact_email)
    summary.dry_run_required = cc.require_dry_run_before_live
    summary.max_requests_per_minute = cc.max_requests_per_minute

    return summary


def load_fixture_capture_queue_table(
    database_path: Optional[str] = None,
) -> FixtureCaptureQueueTable:
    """Load the fixture capture queue from the database.

    Args:
        database_path: Path to database file.

    Returns:
        FixtureCaptureQueueTable with all rows.
    """
    table = FixtureCaptureQueueTable()
    try:
        from marketsentry.fixture_capture_queue import (
            list_all_capture_requests,
        )

        rows = list_all_capture_requests(database_path=database_path)
        table.rows = rows
    except Exception as e:
        logger.debug(f"Could not load capture queue: {e}")

    return table


def load_retrieval_approval_manifest(
    processed_dir: Optional[str] = None,
    approvals_dir: Optional[str] = None,
) -> RetrievalApprovalPackageTable:
    """Load the retrieval approval manifest CSV.

    Args:
        processed_dir: Path to processed data directory.
        approvals_dir: Path to approval exports directory.

    Returns:
        RetrievalApprovalPackageTable with manifest rows and CSV file list.
    """
    table = RetrievalApprovalPackageTable()

    manifest_path = Path(
        processed_dir or "data/processed"
    ) / "redfin_retrieval_approval_manifest.csv"

    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                table.rows = list(reader)
        except Exception as e:
            logger.debug(f"Could not load approval manifest: {e}")

    # List latest CSV files from approvals directory
    approvals_path = Path(approvals_dir or "data/exports/retrieval_approvals")
    if approvals_path.exists():
        csv_files = sorted(
            approvals_path.glob("redfin_batch_approval_*.csv"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        table.latest_csv_files = [str(f) for f in csv_files[:10]]

    return table


def load_latest_retrieval_approval_packages(
    approvals_dir: Optional[str] = None,
    max_packages: int = 10,
) -> List[Dict[str, Any]]:
    """Load the latest approval package CSV files.

    Args:
        approvals_dir: Path to approval exports directory.
        max_packages: Maximum number of packages to return.

    Returns:
        List of dicts with package info (path, row count, run_id).
    """
    packages: List[Dict[str, Any]] = []
    approvals_path = Path(approvals_dir or "data/exports/retrieval_approvals")
    if not approvals_path.exists():
        return packages

    csv_files = sorted(
        approvals_path.glob("redfin_batch_approval_*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for csv_file in csv_files[:max_packages]:
        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                run_id = rows[0].get("approval_run_id", "") if rows else ""
                packages.append({
                    "path": str(csv_file),
                    "row_count": len(rows),
                    "approval_run_id": run_id,
                    "modified": datetime.fromtimestamp(
                        csv_file.stat().st_mtime
                    ).isoformat(),
                })
        except Exception:
            packages.append({
                "path": str(csv_file),
                "row_count": 0,
                "approval_run_id": "",
                "modified": "",
            })

    return packages


def load_batch_retrieval_manifest(
    processed_dir: Optional[str] = None,
) -> BatchRetrievalManifestTable:
    """Load the batch retrieval manifest CSV.

    Args:
        processed_dir: Path to processed data directory.

    Returns:
        BatchRetrievalManifestTable with manifest rows.
    """
    table = BatchRetrievalManifestTable()

    manifest_path = Path(
        processed_dir or "data/processed"
    ) / "redfin_batch_retrieval_manifest.csv"

    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                table.rows = list(reader)
        except Exception as e:
            logger.debug(f"Could not load batch manifest: {e}")

    return table


def load_batch_retrieval_items(
    processed_dir: Optional[str] = None,
) -> BatchRetrievalItemTable:
    """Load the per-item batch retrieval manifest CSV.

    Args:
        processed_dir: Path to processed data directory.

    Returns:
        BatchRetrievalItemTable with item rows.
    """
    table = BatchRetrievalItemTable()

    items_path = Path(
        processed_dir or "data/processed"
    ) / "redfin_batch_retrieval_items.csv"

    if items_path.exists():
        try:
            with open(items_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                table.rows = list(reader)
        except Exception as e:
            logger.debug(f"Could not load batch items: {e}")

    return table


def load_retrieval_audit_summary(
    audit_dir: Optional[str] = None,
) -> RetrievalAuditSummaryTable:
    """Summarize retrieval audit logs.

    Args:
        audit_dir: Path to audit log directory.

    Returns:
        RetrievalAuditSummaryTable with summary counts.
    """
    summary = RetrievalAuditSummaryTable()

    log_dir = Path(audit_dir or "logs/retrieval_audit")
    if not log_dir.exists():
        return summary

    audit_files = sorted(
        log_dir.glob("retrieval_audit_*.csv"),
        key=lambda p: p.name,
    )

    summary.files_scanned = len(audit_files)
    if audit_files:
        summary.latest_audit_file = str(audit_files[-1])

    for audit_file in audit_files:
        try:
            with open(audit_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    summary.total_records += 1

                    allowed = row.get("allowed", "").lower() == "true"
                    blocked = row.get("blocked", "").lower() == "true"
                    dry_run = row.get("dry_run", "").lower() == "true"
                    net_call = row.get(
                        "network_call_performed", ""
                    ).lower() == "true"

                    if allowed and not blocked:
                        summary.allowed += 1
                    if blocked:
                        summary.blocked += 1
                        reason = row.get("reason", "")
                        if reason:
                            # Truncate long reasons for grouping
                            key = reason[:80]
                            summary.blocked_reasons[key] = (
                                summary.blocked_reasons.get(key, 0) + 1
                            )

                    if dry_run:
                        summary.dry_runs += 1
                    else:
                        summary.live_attempts += 1

                    if net_call:
                        summary.network_call_true += 1
                    else:
                        summary.network_call_false += 1
        except Exception as e:
            logger.debug(f"Could not parse audit file {audit_file}: {e}")

    return summary


def load_dry_run_approval_summary(
    audit_dir: Optional[str] = None,
) -> DryRunApprovalSummaryTable:
    """Summarize dry-run approval logs.

    Args:
        audit_dir: Path to audit log directory.

    Returns:
        DryRunApprovalSummaryTable with summary counts and recent rows.
    """
    summary = DryRunApprovalSummaryTable()

    log_dir = Path(audit_dir or "logs/retrieval_audit")
    if not log_dir.exists():
        return summary

    approval_files = sorted(
        log_dir.glob("dry_run_approvals_*.csv"),
        key=lambda p: p.name,
    )

    summary.files_scanned = len(approval_files)
    if approval_files:
        summary.latest_file = str(approval_files[-1])

    for approval_file in approval_files:
        try:
            with open(approval_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    summary.total_records += 1
                    allowed = row.get("allowed", "").lower() == "true"
                    blocked = row.get("blocked", "").lower() == "true"

                    if allowed and not blocked:
                        summary.allowed += 1
                    if blocked:
                        summary.blocked += 1

                    summary.rows.append(dict(row))
        except Exception as e:
            logger.debug(f"Could not parse approval file {approval_file}: {e}")

    # Keep only recent rows (last 50)
    if len(summary.rows) > 50:
        summary.rows = summary.rows[-50:]

    return summary


def load_retrieved_fixture_inventory(
    raw_dir: Optional[str] = None,
    processed_dir: Optional[str] = None,
) -> RetrievedFixtureInventoryTable:
    """Inventory retrieved fixture files with metadata.

    Args:
        raw_dir: Path to raw data directory (parent of redfin/).
        processed_dir: Path to processed data directory.

    Returns:
        RetrievedFixtureInventoryTable with fixture rows.
    """
    inventory = RetrievedFixtureInventoryTable()

    raw_base = Path(raw_dir or "data/raw")

    # Load processing manifest for processed status
    processed_hashes: set = set()
    processing_manifest_path = Path(
        processed_dir or "data/processed"
    ) / "redfin_fixture_processing_manifest.csv"

    if processing_manifest_path.exists():
        try:
            with open(processing_manifest_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    h = row.get("content_hash", "")
                    if h:
                        processed_hashes.add(h)
        except Exception:
            pass

    # Scan search fixtures
    search_dir = raw_base / "redfin" / "search"
    if search_dir.exists():
        for html_file in sorted(search_dir.glob("*.html")):
            entry = _build_fixture_entry(
                html_file, "search", processed_hashes
            )
            inventory.rows.append(entry)
            inventory.total_search_fixtures += 1

    # Scan detail fixtures
    details_dir = raw_base / "redfin" / "details"
    if details_dir.exists():
        for html_file in sorted(details_dir.glob("*.html")):
            entry = _build_fixture_entry(
                html_file, "property_detail", processed_hashes
            )
            inventory.rows.append(entry)
            inventory.total_detail_fixtures += 1

    return inventory


def _build_fixture_entry(
    html_path: Path,
    fixture_type: str,
    processed_hashes: set,
) -> Dict[str, Any]:
    """Build a fixture inventory entry.

    Args:
        html_path: Path to the HTML fixture file.
        fixture_type: Type of fixture (search, property_detail).
        processed_hashes: Set of already-processed content hashes.

    Returns:
        Dict with fixture inventory fields.
    """
    entry: Dict[str, Any] = {
        "fixture_path": str(html_path),
        "fixture_type": fixture_type,
        "metadata_path": "",
        "source_url": "",
        "retrieved_at": "",
        "content_length": 0,
        "content_hash": "",
        "processed": False,
    }

    # Try loading sidecar metadata JSON
    json_path = html_path.with_suffix(".json")
    if json_path.exists():
        entry["metadata_path"] = str(json_path)
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                entry["source_url"] = meta.get("source_url", "")
                entry["retrieved_at"] = meta.get("retrieved_at", "")
                entry["content_length"] = meta.get("content_length", 0)
        except Exception:
            pass

    # Compute content hash
    try:
        content = html_path.read_bytes()
        entry["content_length"] = entry["content_length"] or len(content)
        content_hash = hashlib.sha256(content).hexdigest()[:16]
        entry["content_hash"] = content_hash
        entry["processed"] = content_hash in processed_hashes
    except Exception:
        pass

    return entry


def build_retrieval_operations_tables(
    database_path: Optional[str] = None,
    audit_dir: Optional[str] = None,
    processed_dir: Optional[str] = None,
    raw_dir: Optional[str] = None,
    approvals_dir: Optional[str] = None,
) -> RetrievalOperationsTables:
    """Build all retrieval operations tables for the dashboard.

    Args:
        database_path: Path to database file.
        audit_dir: Path to audit log directory.
        processed_dir: Path to processed data directory.
        raw_dir: Path to raw data directory.
        approvals_dir: Path to approval exports directory.

    Returns:
        RetrievalOperationsTables with all data.
    """
    tables = RetrievalOperationsTables()

    tables.summary = get_retrieval_operations_summary(
        database_path=database_path,
        audit_dir=audit_dir,
        processed_dir=processed_dir,
        approvals_dir=approvals_dir,
    )

    tables.capture_queue = load_fixture_capture_queue_table(
        database_path=database_path
    )

    tables.approval_packages = load_retrieval_approval_manifest(
        processed_dir=processed_dir,
        approvals_dir=approvals_dir,
    )

    tables.batch_manifest = load_batch_retrieval_manifest(
        processed_dir=processed_dir
    )

    tables.batch_items = load_batch_retrieval_items(
        processed_dir=processed_dir
    )

    tables.audit_summary = load_retrieval_audit_summary(
        audit_dir=audit_dir
    )

    tables.dry_run_summary = load_dry_run_approval_summary(
        audit_dir=audit_dir
    )

    tables.fixture_inventory = load_retrieved_fixture_inventory(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
    )

    return tables


# ---------------------------------------------------------------------------
# CLI summary output
# ---------------------------------------------------------------------------


def format_retrieval_operations_summary(
    summary: RetrievalOperationsSummary,
) -> str:
    """Format a retrieval operations summary as ASCII-safe text.

    Args:
        summary: Retrieval operations summary.

    Returns:
        Multi-line string summary.
    """
    lines = [
        "=== Retrieval Operations Summary ===",
        "",
        "--- Fixture Capture Queue ---",
        f"  Pending:   {summary.pending_capture_requests}",
        f"  Captured:  {summary.captured_capture_requests}",
        f"  Skipped:   {summary.skipped_capture_requests}",
        f"  Invalid:   {summary.invalid_capture_requests}",
        f"  Archived:  {summary.archived_capture_requests}",
        f"  Total:     {summary.total_capture_requests}",
        "",
        "--- Approval Packages ---",
        f"  Packages created:              {summary.approval_packages_created}",
        f"  Approved rows pending retrieval: {summary.approved_rows_pending_retrieval}",
        "",
        "--- Batch Retrieval ---",
        f"  Batch runs:           {summary.batch_retrieval_runs}",
        f"  Retrieved fixtures:   {summary.retrieved_fixture_count}",
        f"  Blocked decisions:    {summary.blocked_retrieval_decisions}",
        "",
        "--- Retrieval Audit ---",
        f"  Total decisions:        {summary.audit_total_decisions}",
        f"  Allowed:                {summary.audit_allowed}",
        f"  Blocked:                {summary.audit_blocked}",
        f"  Dry runs:               {summary.audit_dry_runs}",
        f"  Network calls (true):   {summary.audit_records_network_true}",
        f"  Network calls (false):  {summary.audit_records_network_false}",
        "",
        "--- Latest Files ---",
        f"  Audit file:       {summary.latest_audit_file or '(none)'}",
        f"  Approval package: {summary.latest_approval_package or '(none)'}",
        f"  Batch manifest:   {summary.latest_batch_manifest or '(none)'}",
        "",
        "--- Safety Configuration ---",
        f"  Live retrieval enabled:    {summary.live_retrieval_enabled}",
        f"  Allowed sources:           {summary.allowed_sources}",
        f"  User-Agent configured:     {summary.user_agent_configured}",
        f"  Contact email configured:  {summary.contact_email_configured}",
        f"  Dry-run required:          {summary.dry_run_required}",
        f"  Max requests/minute:       {summary.max_requests_per_minute}",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Export report
# ---------------------------------------------------------------------------


def export_retrieval_operations_report(
    database_path: Optional[str] = None,
    audit_dir: Optional[str] = None,
    processed_dir: Optional[str] = None,
    raw_dir: Optional[str] = None,
    approvals_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    report_format: str = "md",
) -> str:
    """Export a retrieval operations report to a file.

    Args:
        database_path: Path to database file.
        audit_dir: Path to audit log directory.
        processed_dir: Path to processed data directory.
        raw_dir: Path to raw data directory.
        approvals_dir: Path to approval exports directory.
        output_dir: Output directory for the report.
        report_format: "md" for Markdown, "csv" for CSV.

    Returns:
        Path to the exported report file.
    """
    tables = build_retrieval_operations_tables(
        database_path=database_path,
        audit_dir=audit_dir,
        processed_dir=processed_dir,
        raw_dir=raw_dir,
        approvals_dir=approvals_dir,
    )

    export_dir = Path(output_dir or "data/exports")
    export_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if report_format == "csv":
        return _export_csv_report(tables, export_dir, timestamp)
    else:
        return _export_md_report(tables, export_dir, timestamp)


def _export_md_report(
    tables: RetrievalOperationsTables,
    export_dir: Path,
    timestamp: str,
) -> str:
    """Export a Markdown retrieval operations report.

    Args:
        tables: All retrieval operations tables.
        export_dir: Output directory.
        timestamp: Timestamp string for filename.

    Returns:
        Path to the exported file.
    """
    report_path = export_dir / f"retrieval_operations_{timestamp}.md"
    s = tables.summary

    lines = [
        "# Retrieval Operations Report",
        f"",
        f"**Generated:** {datetime.now().isoformat()}",
        "",
        "## Fixture Capture Queue",
        "",
        f"| Status | Count |",
        f"|--------|-------|",
        f"| Pending | {s.pending_capture_requests} |",
        f"| Captured | {s.captured_capture_requests} |",
        f"| Skipped | {s.skipped_capture_requests} |",
        f"| Invalid | {s.invalid_capture_requests} |",
        f"| Archived | {s.archived_capture_requests} |",
        f"| **Total** | **{s.total_capture_requests}** |",
        "",
        "## Approval Packages",
        "",
        f"- Packages created: {s.approval_packages_created}",
        f"- Approved rows pending retrieval: {s.approved_rows_pending_retrieval}",
        "",
        "## Batch Retrieval",
        "",
        f"- Batch runs: {s.batch_retrieval_runs}",
        f"- Retrieved fixtures: {s.retrieved_fixture_count}",
        f"- Blocked decisions: {s.blocked_retrieval_decisions}",
        "",
        "## Retrieval Audit",
        "",
        f"- Total decisions: {s.audit_total_decisions}",
        f"- Allowed: {s.audit_allowed}",
        f"- Blocked: {s.audit_blocked}",
        f"- Dry runs: {s.audit_dry_runs}",
        f"- Network calls (true): {s.audit_records_network_true}",
        f"- Network calls (false): {s.audit_records_network_false}",
        "",
        "## Safety Configuration",
        "",
        f"- Live retrieval enabled: {s.live_retrieval_enabled}",
        f"- Allowed sources: {s.allowed_sources}",
        f"- User-Agent configured: {s.user_agent_configured}",
        f"- Contact email configured: {s.contact_email_configured}",
        f"- Dry-run required: {s.dry_run_required}",
        f"- Max requests/minute: {s.max_requests_per_minute}",
    ]

    # Batch retrieval runs table
    if tables.batch_manifest.rows:
        lines.extend(["", "## Batch Retrieval Runs", ""])
        cols = ["run_id", "mode", "retrieved", "blocked", "failed"]
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "|".join(["---"] * len(cols)) + "|")
        for row in tables.batch_manifest.rows:
            vals = [str(row.get(c, "")) for c in cols]
            lines.append("| " + " | ".join(vals) + " |")

    # Fixture inventory summary
    inv = tables.fixture_inventory
    if inv.rows:
        lines.extend([
            "",
            "## Retrieved Fixture Inventory",
            "",
            f"- Search fixtures: {inv.total_search_fixtures}",
            f"- Detail fixtures: {inv.total_detail_fixtures}",
            f"- Total fixtures: {len(inv.rows)}",
        ])

    # Blocked reasons
    if tables.audit_summary.blocked_reasons:
        lines.extend(["", "## Blocked Reasons", ""])
        for reason, count in sorted(
            tables.audit_summary.blocked_reasons.items(),
            key=lambda x: -x[1],
        ):
            lines.append(f"- ({count}) {reason}")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return str(report_path)


def _export_csv_report(
    tables: RetrievalOperationsTables,
    export_dir: Path,
    timestamp: str,
) -> str:
    """Export a CSV retrieval operations report.

    Args:
        tables: All retrieval operations tables.
        export_dir: Output directory.
        timestamp: Timestamp string for filename.

    Returns:
        Path to the exported file.
    """
    report_path = export_dir / f"retrieval_operations_{timestamp}.csv"
    s = tables.summary

    rows = [
        {"category": "capture_queue", "metric": "pending", "value": str(s.pending_capture_requests)},
        {"category": "capture_queue", "metric": "captured", "value": str(s.captured_capture_requests)},
        {"category": "capture_queue", "metric": "skipped", "value": str(s.skipped_capture_requests)},
        {"category": "capture_queue", "metric": "invalid", "value": str(s.invalid_capture_requests)},
        {"category": "capture_queue", "metric": "archived", "value": str(s.archived_capture_requests)},
        {"category": "capture_queue", "metric": "total", "value": str(s.total_capture_requests)},
        {"category": "approvals", "metric": "packages_created", "value": str(s.approval_packages_created)},
        {"category": "approvals", "metric": "approved_pending", "value": str(s.approved_rows_pending_retrieval)},
        {"category": "batch_retrieval", "metric": "runs", "value": str(s.batch_retrieval_runs)},
        {"category": "batch_retrieval", "metric": "retrieved", "value": str(s.retrieved_fixture_count)},
        {"category": "batch_retrieval", "metric": "blocked", "value": str(s.blocked_retrieval_decisions)},
        {"category": "audit", "metric": "total_decisions", "value": str(s.audit_total_decisions)},
        {"category": "audit", "metric": "allowed", "value": str(s.audit_allowed)},
        {"category": "audit", "metric": "blocked", "value": str(s.audit_blocked)},
        {"category": "audit", "metric": "dry_runs", "value": str(s.audit_dry_runs)},
        {"category": "audit", "metric": "network_true", "value": str(s.audit_records_network_true)},
        {"category": "audit", "metric": "network_false", "value": str(s.audit_records_network_false)},
        {"category": "safety", "metric": "live_enabled", "value": str(s.live_retrieval_enabled)},
        {"category": "safety", "metric": "allowed_sources", "value": s.allowed_sources},
        {"category": "safety", "metric": "user_agent", "value": str(s.user_agent_configured)},
        {"category": "safety", "metric": "contact_email", "value": str(s.contact_email_configured)},
        {"category": "safety", "metric": "dry_run_required", "value": str(s.dry_run_required)},
        {"category": "safety", "metric": "max_rpm", "value": str(s.max_requests_per_minute)},
    ]

    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["category", "metric", "value"]
        )
        writer.writeheader()
        writer.writerows(rows)

    return str(report_path)
