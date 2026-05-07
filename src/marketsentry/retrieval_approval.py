"""Redfin batch retrieval approval workflow.

Provides a two-step approval workflow for batch live retrieval:

1. Prepare: Dry-run pending Redfin capture requests and write a
   user-editable approval CSV with approved_for_live=false.
2. Retrieve: Load the user-edited CSV and retrieve only rows where
   the user set approved_for_live=true, requiring --force-live and
   re-checking all policy gates.

No browser automation, no bypass mechanisms. Live retrieval is disabled
by default. Scheduled tasks must not invoke approved retrieval.
"""

import csv
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from marketsentry.fixture_capture_queue import (
    list_pending_capture_requests,
    mark_fixture_captured,
)
from marketsentry.logging_config import logger
from marketsentry.redfin_batch_retrieval import (
    BatchRetrievalItemResult,
    _normalize_request_type,
    retrieve_pending_redfin_capture_request,
)
from marketsentry.source_adapters.base import RetrievalResult
from marketsentry.source_adapters.dry_run_approval import normalize_url
from marketsentry.source_adapters.http_client import HttpClient
from marketsentry.source_adapters.redfin_adapter import RedfinAdapter


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RetrievalApprovalRow(BaseModel):
    """A single row in the approval CSV."""

    approval_run_id: str = ""
    capture_request_id: int = 0
    source_site: str = "redfin"
    source_url: str = ""
    normalized_url: str = ""
    request_type: str = ""
    suggested_fixture_path: str = ""
    policy_decision: str = ""
    policy_reasons: str = ""
    compliance_passed: bool = False
    robots_passed: bool = False
    rate_limit_passed: bool = False
    dry_run_approved: bool = False
    network_call_performed: bool = False
    approved_for_live: bool = False
    user_notes: str = ""


class RetrievalApprovalPackage(BaseModel):
    """Result from preparing an approval package."""

    approval_run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = ""
    pending_scanned: int = 0
    approval_rows_written: int = 0
    approval_csv_path: str = ""
    approval_summary_path: str = ""
    rows: List[RetrievalApprovalRow] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class RetrievalApprovalImportResult(BaseModel):
    """Result from loading and validating an approval CSV."""

    approval_run_id: str = ""
    rows_loaded: int = 0
    approved_count: int = 0
    skipped_count: int = 0
    validation_errors: List[str] = Field(default_factory=list)
    valid_rows: List[RetrievalApprovalRow] = Field(default_factory=list)
    approved_rows: List[RetrievalApprovalRow] = Field(default_factory=list)


class ApprovedRetrievalRunResult(BaseModel):
    """Result from retrieving approved items."""

    approval_run_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    rows_loaded: int = 0
    approved_count: int = 0
    attempted_live: int = 0
    retrieved: int = 0
    blocked: int = 0
    failed: int = 0
    fixtures_saved: int = 0
    processed_after_retrieval: bool = False
    queue_items_marked_captured: int = 0
    reports_exported: List[str] = Field(default_factory=list)
    items: List[BatchRetrievalItemResult] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Approval CSV columns
# ---------------------------------------------------------------------------

APPROVAL_CSV_COLUMNS = [
    "approval_run_id",
    "capture_request_id",
    "source_site",
    "source_url",
    "normalized_url",
    "request_type",
    "suggested_fixture_path",
    "policy_decision",
    "policy_reasons",
    "compliance_passed",
    "robots_passed",
    "rate_limit_passed",
    "dry_run_approved",
    "network_call_performed",
    "approved_for_live",
    "user_notes",
]

# Approval manifest columns
APPROVAL_MANIFEST_COLUMNS = [
    "approval_run_id",
    "created_at",
    "pending_scanned",
    "approval_rows_written",
    "approval_csv_path",
    "approval_summary_path",
    "approved_count_when_imported",
    "retrieved_count",
    "blocked_count",
    "failed_count",
    "notes",
]


# ---------------------------------------------------------------------------
# Prepare approval package
# ---------------------------------------------------------------------------


def prepare_redfin_batch_approval_package(
    max_items: int = 0,
    request_type: Optional[str] = None,
    database_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> RetrievalApprovalPackage:
    """Prepare a batch approval package for pending Redfin capture requests.

    Dry-runs each pending item and writes an approval CSV with
    approved_for_live=false for user review.

    Args:
        max_items: Maximum number of items. 0 for no limit.
        request_type: Filter by request type. None for all.
        database_path: Path to database file.
        output_dir: Output directory for approval files.

    Returns:
        RetrievalApprovalPackage with file paths and statistics.
    """
    package = RetrievalApprovalPackage(
        created_at=datetime.now().isoformat(),
    )

    # Get pending requests
    pending = list_pending_capture_requests(
        source_site="redfin",
        database_path=database_path,
    )

    # Filter by request type
    if request_type:
        type_filter = _normalize_request_type(request_type)
        pending = [
            r for r in pending
            if _normalize_request_type(r.get("request_type", "")) == type_filter
        ]

    # Apply max_items
    if max_items > 0:
        pending = pending[:max_items]

    package.pending_scanned = len(pending)

    if not pending:
        package.warnings.append("No pending Redfin capture requests found.")
        return package

    # Dry-run each item
    adapter = RedfinAdapter()

    for capture_req in pending:
        url = capture_req.get("source_url", "")
        req_type = _normalize_request_type(capture_req.get("request_type", ""))
        cap_id = capture_req.get("capture_request_id", 0)

        # Perform dry-run via batch retrieval helper
        item_result = retrieve_pending_redfin_capture_request(
            capture_request=capture_req,
            adapter=adapter,
            dry_run_only=True,
            database_path=database_path,
        )

        # Determine policy status from dry-run result
        row = RetrievalApprovalRow(
            approval_run_id=package.approval_run_id,
            capture_request_id=cap_id,
            source_site="redfin",
            source_url=url,
            normalized_url=normalize_url(url),
            request_type=req_type,
            suggested_fixture_path=capture_req.get("suggested_fixture_path", ""),
            policy_decision=item_result.decision,
            policy_reasons=item_result.reason,
            compliance_passed="blocked" not in item_result.reason.lower()
            if item_result.reason else True,
            robots_passed="robots" not in item_result.reason.lower()
            if item_result.reason else True,
            rate_limit_passed="rate" not in item_result.reason.lower()
            if item_result.reason else True,
            dry_run_approved=item_result.status == "dry_run",
            network_call_performed=False,
            approved_for_live=False,  # Always default false
            user_notes="",
        )

        package.rows.append(row)

    # Write approval CSV
    export_dir = Path(output_dir or "data/exports/retrieval_approvals")
    export_dir.mkdir(parents=True, exist_ok=True)

    csv_filename = f"redfin_batch_approval_{package.approval_run_id}.csv"
    csv_path = export_dir / csv_filename
    _write_approval_csv(str(csv_path), package.rows)
    package.approval_csv_path = str(csv_path)
    package.approval_rows_written = len(package.rows)

    # Write Markdown summary
    md_filename = f"redfin_batch_approval_{package.approval_run_id}.md"
    md_path = export_dir / md_filename
    _write_approval_summary(str(md_path), package)
    package.approval_summary_path = str(md_path)

    # Write to approval manifest
    _append_approval_manifest(
        manifest_path="data/processed/redfin_retrieval_approval_manifest.csv",
        package=package,
    )

    return package


def _write_approval_csv(path: str, rows: List[RetrievalApprovalRow]) -> None:
    """Write approval rows to a CSV file.

    Args:
        path: Output CSV path.
        rows: Approval rows to write.
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=APPROVAL_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "approval_run_id": row.approval_run_id,
                "capture_request_id": row.capture_request_id,
                "source_site": row.source_site,
                "source_url": row.source_url,
                "normalized_url": row.normalized_url,
                "request_type": row.request_type,
                "suggested_fixture_path": row.suggested_fixture_path,
                "policy_decision": row.policy_decision,
                "policy_reasons": row.policy_reasons,
                "compliance_passed": str(row.compliance_passed),
                "robots_passed": str(row.robots_passed),
                "rate_limit_passed": str(row.rate_limit_passed),
                "dry_run_approved": str(row.dry_run_approved),
                "network_call_performed": str(row.network_call_performed),
                "approved_for_live": str(row.approved_for_live).lower(),
                "user_notes": row.user_notes,
            })


def _write_approval_summary(path: str, package: RetrievalApprovalPackage) -> None:
    """Write a Markdown summary of the approval package.

    Args:
        path: Output Markdown path.
        package: Approval package to summarize.
    """
    lines = [
        "# Redfin Batch Retrieval Approval Package",
        "",
        f"**Run ID:** {package.approval_run_id}",
        f"**Created:** {package.created_at}",
        f"**Pending scanned:** {package.pending_scanned}",
        f"**Rows written:** {package.approval_rows_written}",
        "",
        "## Instructions",
        "",
        "1. Open the companion CSV file in a spreadsheet editor.",
        "2. Review each row's policy_decision and policy_reasons.",
        "3. For items you want to retrieve, change `approved_for_live` from `false` to `true`.",
        "4. Save the CSV file.",
        "5. Run: `marketsentry retrieve-approved-redfin-batch --approval-file <csv_path> --force-live`",
        "",
        "## Safety Reminders",
        "",
        "- Only items with `approved_for_live=true` will be retrieved.",
        "- `--force-live` is required for any network calls.",
        "- All policy checks are re-evaluated at retrieval time.",
        "- If a policy check fails at retrieval time, the item is blocked even if approved.",
        "- Rate limits are enforced per item.",
        "",
        "## Items",
        "",
        "| # | ID | Type | URL | Decision |",
        "|---|---|---|---|---|",
    ]

    for i, row in enumerate(package.rows, 1):
        url_short = row.source_url[:60] + "..." if len(row.source_url) > 60 else row.source_url
        lines.append(
            f"| {i} | {row.capture_request_id} | {row.request_type} | {url_short} | {row.policy_decision} |"
        )

    if package.warnings:
        lines.extend(["", "## Warnings", ""])
        for w in package.warnings:
            lines.append(f"- {w}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Approval manifest
# ---------------------------------------------------------------------------


def _append_approval_manifest(
    manifest_path: str,
    package: RetrievalApprovalPackage,
    approved_count: int = 0,
    retrieved_count: int = 0,
    blocked_count: int = 0,
    failed_count: int = 0,
    notes: str = "",
) -> None:
    """Append a row to the approval manifest CSV.

    Args:
        manifest_path: Path to manifest CSV.
        package: Approval package.
        approved_count: Number of items approved by user.
        retrieved_count: Number successfully retrieved.
        blocked_count: Number blocked at retrieval.
        failed_count: Number that failed.
        notes: Additional notes.
    """
    Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
    file_exists = Path(manifest_path).exists()

    with open(manifest_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=APPROVAL_MANIFEST_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "approval_run_id": package.approval_run_id,
            "created_at": package.created_at,
            "pending_scanned": package.pending_scanned,
            "approval_rows_written": package.approval_rows_written,
            "approval_csv_path": package.approval_csv_path,
            "approval_summary_path": package.approval_summary_path,
            "approved_count_when_imported": approved_count,
            "retrieved_count": retrieved_count,
            "blocked_count": blocked_count,
            "failed_count": failed_count,
            "notes": notes,
        })


# ---------------------------------------------------------------------------
# Load and validate approval CSV
# ---------------------------------------------------------------------------


def load_retrieval_approval_csv(
    csv_path: str,
) -> RetrievalApprovalImportResult:
    """Load an approval CSV file and parse its rows.

    Args:
        csv_path: Path to the approval CSV file.

    Returns:
        RetrievalApprovalImportResult with parsed rows.
    """
    result = RetrievalApprovalImportResult()

    if not Path(csv_path).exists():
        result.validation_errors.append(f"Approval CSV not found: {csv_path}")
        return result

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_dict in reader:
            result.rows_loaded += 1
            row = RetrievalApprovalRow(
                approval_run_id=row_dict.get("approval_run_id", ""),
                capture_request_id=int(row_dict.get("capture_request_id", 0)),
                source_site=row_dict.get("source_site", "redfin"),
                source_url=row_dict.get("source_url", ""),
                normalized_url=row_dict.get("normalized_url", ""),
                request_type=row_dict.get("request_type", ""),
                suggested_fixture_path=row_dict.get("suggested_fixture_path", ""),
                policy_decision=row_dict.get("policy_decision", ""),
                policy_reasons=row_dict.get("policy_reasons", ""),
                compliance_passed=_parse_bool(row_dict.get("compliance_passed", "false")),
                robots_passed=_parse_bool(row_dict.get("robots_passed", "false")),
                rate_limit_passed=_parse_bool(row_dict.get("rate_limit_passed", "false")),
                dry_run_approved=_parse_bool(row_dict.get("dry_run_approved", "false")),
                network_call_performed=_parse_bool(row_dict.get("network_call_performed", "false")),
                approved_for_live=_parse_bool(row_dict.get("approved_for_live", "false")),
                user_notes=row_dict.get("user_notes", ""),
            )

            # Track approval_run_id
            if not result.approval_run_id:
                result.approval_run_id = row.approval_run_id
            elif result.approval_run_id != row.approval_run_id:
                result.validation_errors.append(
                    f"Mixed approval_run_id: expected {result.approval_run_id}, "
                    f"got {row.approval_run_id} for capture_request_id={row.capture_request_id}"
                )

            result.valid_rows.append(row)

            if row.approved_for_live:
                result.approved_count += 1
                result.approved_rows.append(row)
            else:
                result.skipped_count += 1

    return result


def _parse_bool(value: str) -> bool:
    """Parse a boolean string value.

    Args:
        value: String representation of boolean.

    Returns:
        Boolean value.
    """
    return value.strip().lower() in ("true", "1", "yes")


def validate_retrieval_approval_csv(
    import_result: RetrievalApprovalImportResult,
    database_path: Optional[str] = None,
) -> RetrievalApprovalImportResult:
    """Validate approval rows against current queue state.

    Checks that capture_request_id still exists, is pending, and URL
    still matches.

    Args:
        import_result: Loaded approval data.
        database_path: Path to database file.

    Returns:
        Updated RetrievalApprovalImportResult with validation errors.
    """
    if import_result.validation_errors:
        return import_result

    # Get current pending requests
    pending = list_pending_capture_requests(
        source_site="redfin",
        database_path=database_path,
    )

    pending_by_id = {r["capture_request_id"]: r for r in pending}

    validated_approved = []

    for row in import_result.approved_rows:
        cap_id = row.capture_request_id

        # Validate capture_request_id exists and is pending
        if cap_id not in pending_by_id:
            import_result.validation_errors.append(
                f"Capture request {cap_id} not found or no longer pending."
            )
            continue

        queue_item = pending_by_id[cap_id]

        # Validate URL still matches
        queue_url = normalize_url(queue_item.get("source_url", ""))
        approval_url = normalize_url(row.source_url)
        if queue_url != approval_url:
            import_result.validation_errors.append(
                f"URL mismatch for capture request {cap_id}: "
                f"queue={queue_item.get('source_url', '')}, "
                f"approval={row.source_url}"
            )
            continue

        validated_approved.append(row)

    import_result.approved_rows = validated_approved
    import_result.approved_count = len(validated_approved)

    return import_result


# ---------------------------------------------------------------------------
# Retrieve approved batch
# ---------------------------------------------------------------------------


def retrieve_approved_redfin_batch(
    approval_csv_path: str,
    force_live: bool = False,
    dry_run_only: bool = False,
    process_after_retrieval: bool = False,
    database_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    adapter: Optional[RedfinAdapter] = None,
    http_client: Optional[HttpClient] = None,
    manifest_path: Optional[str] = None,
) -> ApprovedRetrievalRunResult:
    """Retrieve only approved items from an approval CSV.

    Loads the user-edited approval CSV, validates rows, and retrieves
    only items with approved_for_live=true. Requires --force-live.
    All policy checks are re-evaluated per item at retrieval time.

    Args:
        approval_csv_path: Path to the user-edited approval CSV.
        force_live: Whether to attempt live retrieval.
        dry_run_only: If True, validate and preview only.
        process_after_retrieval: Process fixtures after retrieval.
        database_path: Path to database file.
        output_dir: Output directory for reports.
        adapter: Optional RedfinAdapter (created if None).
        http_client: Optional HTTP client (inject FakeHttpClient for tests).
        manifest_path: Path to approval manifest CSV.

    Returns:
        ApprovedRetrievalRunResult with retrieval statistics.
    """
    if adapter is None:
        adapter = RedfinAdapter()

    if manifest_path is None:
        manifest_path = "data/processed/redfin_retrieval_approval_manifest.csv"

    result = ApprovedRetrievalRunResult(
        started_at=datetime.now().isoformat(),
    )

    # Load and validate CSV
    import_result = load_retrieval_approval_csv(approval_csv_path)
    result.approval_run_id = import_result.approval_run_id
    result.rows_loaded = import_result.rows_loaded
    result.approved_count = import_result.approved_count

    if import_result.validation_errors:
        result.errors.extend(import_result.validation_errors)

    # Validate against current queue state
    import_result = validate_retrieval_approval_csv(
        import_result, database_path=database_path
    )

    if import_result.validation_errors:
        result.errors.extend(import_result.validation_errors)

    result.approved_count = import_result.approved_count

    if not import_result.approved_rows:
        result.warnings.append("No approved rows to retrieve.")
        result.completed_at = datetime.now().isoformat()
        # Update manifest
        _update_approval_manifest_retrieval(
            manifest_path, result, import_result.approval_run_id
        )
        return result

    if dry_run_only:
        result.warnings.append("Dry-run only mode. No retrieval performed.")
        result.completed_at = datetime.now().isoformat()
        _update_approval_manifest_retrieval(
            manifest_path, result, import_result.approval_run_id
        )
        return result

    if not force_live:
        result.warnings.append(
            "Live retrieval requires --force-live. No retrieval performed."
        )
        result.completed_at = datetime.now().isoformat()
        _update_approval_manifest_retrieval(
            manifest_path, result, import_result.approval_run_id
        )
        return result

    # Retrieve each approved item
    for row in import_result.approved_rows:
        capture_request = {
            "capture_request_id": row.capture_request_id,
            "source_url": row.source_url,
            "request_type": row.request_type,
        }

        item_result = retrieve_pending_redfin_capture_request(
            capture_request=capture_request,
            adapter=adapter,
            http_client=http_client,
            force_live=True,
            dry_run_only=False,
            database_path=database_path,
        )

        result.attempted_live += 1

        if item_result.status == "retrieved":
            result.retrieved += 1
            result.fixtures_saved += 1
        elif item_result.status == "blocked":
            result.blocked += 1
        else:
            result.failed += 1

        result.items.append(item_result)

    # Post-retrieval processing
    if process_after_retrieval and result.retrieved > 0:
        try:
            from marketsentry.retrieved_fixture_processor import (
                process_redfin_retrieved_fixtures,
            )

            proc_result = process_redfin_retrieved_fixtures(
                database_path=database_path,
                output_dir=output_dir,
            )
            result.processed_after_retrieval = True
            result.reports_exported = proc_result.reports_exported

            # Mark captured only after successful processing
            for item in result.items:
                if item.status == "retrieved" and item.fixture_path:
                    try:
                        marked = mark_fixture_captured(
                            capture_request_id=item.capture_request_id,
                            fixture_path=item.fixture_path,
                            database_path=database_path,
                        )
                        if marked:
                            item.marked_captured = True
                            result.queue_items_marked_captured += 1
                    except Exception as e:
                        result.warnings.append(
                            f"Failed to mark captured (ID {item.capture_request_id}): {e}"
                        )
        except Exception as e:
            result.errors.append(f"Post-retrieval processing error: {e}")
    elif result.retrieved > 0 and not process_after_retrieval:
        # Mark captured without processing
        for item in result.items:
            if item.status == "retrieved" and item.fixture_path:
                try:
                    marked = mark_fixture_captured(
                        capture_request_id=item.capture_request_id,
                        fixture_path=item.fixture_path,
                        database_path=database_path,
                    )
                    if marked:
                        item.marked_captured = True
                        result.queue_items_marked_captured += 1
                except Exception as e:
                    result.warnings.append(
                        f"Failed to mark captured (ID {item.capture_request_id}): {e}"
                    )

    result.completed_at = datetime.now().isoformat()

    # Update manifest
    _update_approval_manifest_retrieval(
        manifest_path, result, import_result.approval_run_id
    )

    return result


def _update_approval_manifest_retrieval(
    manifest_path: str,
    result: ApprovedRetrievalRunResult,
    approval_run_id: str,
) -> None:
    """Append retrieval results to the approval manifest.

    Args:
        manifest_path: Path to manifest CSV.
        result: Retrieval run result.
        approval_run_id: Approval run ID.
    """
    # Create a minimal package for the manifest append
    package = RetrievalApprovalPackage(
        approval_run_id=approval_run_id,
        created_at=result.started_at,
        pending_scanned=result.rows_loaded,
        approval_rows_written=0,
        approval_csv_path="",
        approval_summary_path="",
    )

    notes_parts = []
    if result.warnings:
        notes_parts.append("; ".join(result.warnings))
    if result.errors:
        notes_parts.append("Errors: " + "; ".join(result.errors))

    _append_approval_manifest(
        manifest_path=manifest_path,
        package=package,
        approved_count=result.approved_count,
        retrieved_count=result.retrieved,
        blocked_count=result.blocked,
        failed_count=result.failed,
        notes="; ".join(notes_parts) if notes_parts else "retrieval_run",
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def summarize_approval_package(package: RetrievalApprovalPackage) -> str:
    """Generate an ASCII-safe summary of an approval package.

    Args:
        package: Approval package to summarize.

    Returns:
        Multi-line string summary.
    """
    lines = [
        "=== Redfin Batch Retrieval Approval Package ===",
        f"Run ID: {package.approval_run_id}",
        f"Created: {package.created_at}",
        f"Pending scanned: {package.pending_scanned}",
        f"Rows written: {package.approval_rows_written}",
        f"Approval CSV: {package.approval_csv_path}",
        f"Summary: {package.approval_summary_path}",
        "",
        "Next steps:",
        "  1. Open the approval CSV in a spreadsheet editor.",
        "  2. Set approved_for_live=true for items you want to retrieve.",
        "  3. Save the CSV.",
        "  4. Run: marketsentry retrieve-approved-redfin-batch \\",
        f"       --approval-file \"{package.approval_csv_path}\" --force-live",
    ]

    if package.warnings:
        lines.extend(["", "Warnings:"])
        for w in package.warnings:
            lines.append(f"  - {w}")

    if package.errors:
        lines.extend(["", "Errors:"])
        for e in package.errors:
            lines.append(f"  - {e}")

    return "\n".join(lines)


def summarize_approved_retrieval_run(result: ApprovedRetrievalRunResult) -> str:
    """Generate an ASCII-safe summary of an approved retrieval run.

    Args:
        result: Approved retrieval run result.

    Returns:
        Multi-line string summary.
    """
    lines = [
        "=== Redfin Approved Batch Retrieval ===",
        f"Approval Run ID: {result.approval_run_id}",
        f"Started: {result.started_at}",
        f"Completed: {result.completed_at}",
        "",
        f"Rows loaded: {result.rows_loaded}",
        f"Approved: {result.approved_count}",
        f"Attempted live: {result.attempted_live}",
        f"Retrieved: {result.retrieved}",
        f"Blocked: {result.blocked}",
        f"Failed: {result.failed}",
        f"Fixtures saved: {result.fixtures_saved}",
        f"Processed after retrieval: {result.processed_after_retrieval}",
        f"Queue items marked captured: {result.queue_items_marked_captured}",
    ]

    if result.reports_exported:
        lines.append(f"Reports exported: {len(result.reports_exported)}")

    if result.warnings:
        lines.extend(["", "Warnings:"])
        for w in result.warnings:
            lines.append(f"  - {w}")

    if result.errors:
        lines.extend(["", "Errors:"])
        for e in result.errors:
            lines.append(f"  - {e}")

    if result.items:
        lines.extend(["", "--- Per-Item Results ---"])
        for item in result.items:
            lines.append(
                f"  [{item.status.upper()}] ID={item.capture_request_id} "
                f"url={item.source_url}"
            )
            if item.reason:
                lines.append(f"    Reason: {item.reason}")
            if item.fixture_path:
                lines.append(f"    Fixture: {item.fixture_path}")

    return "\n".join(lines)
