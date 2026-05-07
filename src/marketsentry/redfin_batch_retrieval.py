"""Redfin pending capture batch retrieval orchestrator.

Processes pending fixture capture queue items for Redfin one at a time,
applying the full Milestone 14-16 compliance, policy, dry-run, robots,
and rate-limit guardrails for each request.

Supports three modes:
  - dry_run_only: evaluate pending requests, write audit, no retrieval.
  - retrieve_only: retrieve and save fixtures, no processing.
  - retrieve_and_process: retrieve, save, process, export, mark captured.

Default mode is dry_run_only unless explicitly overridden.
Live retrieval requires --force-live and full environment configuration.

No browser automation, Playwright, Selenium, CAPTCHA bypass, login
bypass, paywall bypass, anti-bot bypass, or technical access-control
bypass.
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
from marketsentry.source_adapters.base import RetrievalResult
from marketsentry.source_adapters.http_client import HttpClient
from marketsentry.source_adapters.redfin_adapter import RedfinAdapter


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class BatchRetrievalConfig(BaseModel):
    """Configuration for a batch retrieval run."""

    mode: str = "dry_run_only"  # dry_run_only | retrieve_only | retrieve_and_process
    max_items: int = 0  # 0 means no limit
    request_type_filter: Optional[str] = None  # search | property_detail | None
    force_live: bool = False
    database_path: Optional[str] = None
    output_dir: Optional[str] = None


class BatchRetrievalItemResult(BaseModel):
    """Result for a single batch retrieval item."""

    capture_request_id: int = 0
    source_url: str = ""
    request_type: str = ""
    decision: str = ""  # allowed | blocked | error | dry_run
    network_call_performed: bool = False
    fixture_path: str = ""
    status: str = ""  # retrieved | blocked | failed | dry_run | skipped
    reason: str = ""
    error: str = ""
    marked_captured: bool = False


class BatchRetrievalRunResult(BaseModel):
    """Aggregate result for a batch retrieval run."""

    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    started_at: str = ""
    completed_at: str = ""
    mode: str = "dry_run_only"
    max_items: int = 0
    request_type_filter: Optional[str] = None
    pending_scanned: int = 0
    dry_run_only_count: int = 0
    attempted_live: int = 0
    retrieved: int = 0
    blocked: int = 0
    failed: int = 0
    fixtures_saved: int = 0
    processed_after_retrieval: bool = False
    queue_items_marked_captured: int = 0
    reports_exported: List[str] = Field(default_factory=list)
    audit_log_path: str = ""
    items: List[BatchRetrievalItemResult] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# Manifest columns
# ---------------------------------------------------------------------------

BATCH_MANIFEST_COLUMNS = [
    "run_id",
    "started_at",
    "completed_at",
    "mode",
    "max_items",
    "request_type_filter",
    "pending_scanned",
    "attempted_live",
    "retrieved",
    "blocked",
    "failed",
    "fixtures_saved",
    "processed_after_retrieval",
    "queue_items_marked_captured",
    "audit_log_path",
    "notes",
]

ITEM_MANIFEST_COLUMNS = [
    "run_id",
    "capture_request_id",
    "source_url",
    "request_type",
    "decision",
    "network_call_performed",
    "fixture_path",
    "status",
    "reason",
    "error",
]


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------


def _ensure_manifest_dir(manifest_path: str) -> None:
    """Ensure the manifest file's parent directory exists."""
    Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)


def _append_batch_manifest(
    manifest_path: str,
    result: "BatchRetrievalRunResult",
) -> None:
    """Append a batch run row to the batch manifest CSV.

    Args:
        manifest_path: Path to the batch manifest CSV.
        result: Completed batch run result.
    """
    _ensure_manifest_dir(manifest_path)
    file_exists = Path(manifest_path).exists()

    with open(manifest_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=BATCH_MANIFEST_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "run_id": result.run_id,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "mode": result.mode,
            "max_items": result.max_items,
            "request_type_filter": result.request_type_filter or "",
            "pending_scanned": result.pending_scanned,
            "attempted_live": result.attempted_live,
            "retrieved": result.retrieved,
            "blocked": result.blocked,
            "failed": result.failed,
            "fixtures_saved": result.fixtures_saved,
            "processed_after_retrieval": result.processed_after_retrieval,
            "queue_items_marked_captured": result.queue_items_marked_captured,
            "audit_log_path": result.audit_log_path,
            "notes": result.notes,
        })


def _append_item_manifest(
    manifest_path: str,
    run_id: str,
    item: "BatchRetrievalItemResult",
) -> None:
    """Append an item row to the per-item manifest CSV.

    Args:
        manifest_path: Path to the per-item manifest CSV.
        run_id: Batch run ID.
        item: Item result to record.
    """
    _ensure_manifest_dir(manifest_path)
    file_exists = Path(manifest_path).exists()

    with open(manifest_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ITEM_MANIFEST_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "run_id": run_id,
            "capture_request_id": item.capture_request_id,
            "source_url": item.source_url,
            "request_type": item.request_type,
            "decision": item.decision,
            "network_call_performed": item.network_call_performed,
            "fixture_path": item.fixture_path,
            "status": item.status,
            "reason": item.reason,
            "error": item.error,
        })


# ---------------------------------------------------------------------------
# Pending request filtering
# ---------------------------------------------------------------------------


def get_pending_redfin_capture_requests(
    request_type: Optional[str] = None,
    max_items: int = 0,
    database_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get pending Redfin fixture capture requests from the queue.

    Args:
        request_type: Filter by request type (search, property_detail). None for all.
        max_items: Maximum number of items to return. 0 for no limit.
        database_path: Path to database file.

    Returns:
        List of pending capture request dicts filtered to Redfin only.
    """
    pending = list_pending_capture_requests(
        source_site="redfin",
        database_path=database_path,
    )

    if request_type:
        # Normalize property/property_detail
        type_filter = request_type.lower().strip()
        pending = [
            r for r in pending
            if _normalize_request_type(r.get("request_type", "")) == type_filter
        ]

    if max_items > 0:
        pending = pending[:max_items]

    return pending


def _normalize_request_type(request_type: str) -> str:
    """Normalize request type labels.

    Args:
        request_type: Raw request type string.

    Returns:
        Normalized type: 'search' or 'property_detail'.
    """
    rt = request_type.lower().strip()
    if rt in ("property", "property_detail", "detail"):
        return "property_detail"
    if rt in ("search",):
        return "search"
    return rt


# ---------------------------------------------------------------------------
# Single-item retrieval
# ---------------------------------------------------------------------------


def retrieve_pending_redfin_capture_request(
    capture_request: Dict[str, Any],
    adapter: Optional[RedfinAdapter] = None,
    http_client: Optional[HttpClient] = None,
    force_live: bool = False,
    dry_run_only: bool = False,
    database_path: Optional[str] = None,
) -> BatchRetrievalItemResult:
    """Process a single pending capture request.

    Applies full policy checks via the Redfin adapter. If dry_run_only,
    performs only a dry-run preview. If force_live and all checks pass,
    retrieves and saves the fixture.

    Args:
        capture_request: Dict from fixture_capture_queue table row.
        adapter: Optional RedfinAdapter instance (created if None).
        http_client: Optional HTTP client (inject FakeHttpClient for tests).
        force_live: Whether to attempt live retrieval.
        dry_run_only: If True, only perform dry-run evaluation.
        database_path: Path to database file.

    Returns:
        BatchRetrievalItemResult with retrieval outcome.
    """
    if adapter is None:
        adapter = RedfinAdapter()

    url = capture_request.get("source_url", "")
    request_type = _normalize_request_type(
        capture_request.get("request_type", "")
    )
    capture_id = capture_request.get("capture_request_id", 0)

    item_result = BatchRetrievalItemResult(
        capture_request_id=capture_id,
        source_url=url,
        request_type=request_type,
    )

    try:
        if dry_run_only:
            # Dry-run only: evaluate policy, no network call
            retrieval_result = _do_dry_run(adapter, url, request_type)
            item_result.decision = "dry_run"
            item_result.status = "dry_run"
            item_result.network_call_performed = False
            if retrieval_result.blocked:
                item_result.reason = retrieval_result.block_reason
            else:
                item_result.reason = retrieval_result.dry_run_preview or "Dry-run OK"
            return item_result

        if not force_live:
            # No force-live: block without attempting
            item_result.decision = "blocked"
            item_result.status = "blocked"
            item_result.reason = (
                "Live retrieval requires --force-live flag. "
                "Use dry-run to preview first."
            )
            return item_result

        # Attempt live retrieval with full policy checks
        retrieval_result = _do_live_retrieval(
            adapter, url, request_type, http_client
        )

        item_result.network_call_performed = retrieval_result.network_call_performed

        if retrieval_result.blocked:
            item_result.decision = "blocked"
            item_result.status = "blocked"
            item_result.reason = retrieval_result.block_reason
        elif retrieval_result.success:
            item_result.decision = "allowed"
            item_result.status = "retrieved"
            item_result.fixture_path = retrieval_result.fixture_path
        else:
            item_result.decision = "blocked"
            item_result.status = "failed"
            item_result.reason = retrieval_result.error_message or "Unknown error"

    except Exception as e:
        item_result.decision = "error"
        item_result.status = "failed"
        item_result.error = f"{type(e).__name__}: {e}"

    return item_result


def _do_dry_run(
    adapter: RedfinAdapter,
    url: str,
    request_type: str,
) -> RetrievalResult:
    """Perform a dry-run preview for a URL.

    Args:
        adapter: Redfin adapter instance.
        url: URL to preview.
        request_type: 'search' or 'property_detail'.

    Returns:
        RetrievalResult from the adapter dry-run method.
    """
    if request_type == "search":
        return adapter.dry_run_search(url)
    else:
        return adapter.dry_run_property_detail(url)


def _do_live_retrieval(
    adapter: RedfinAdapter,
    url: str,
    request_type: str,
    http_client: Optional[HttpClient] = None,
) -> RetrievalResult:
    """Perform live retrieval for a URL.

    Args:
        adapter: Redfin adapter instance.
        url: URL to retrieve.
        request_type: 'search' or 'property_detail'.
        http_client: Optional HTTP client.

    Returns:
        RetrievalResult from the adapter retrieve method.
    """
    if request_type == "search":
        return adapter.retrieve_search(url, http_client=http_client)
    else:
        return adapter.retrieve_property_detail(url, http_client=http_client)


# ---------------------------------------------------------------------------
# Batch retrieval
# ---------------------------------------------------------------------------


def retrieve_pending_redfin_capture_batch(
    config: Optional[BatchRetrievalConfig] = None,
    adapter: Optional[RedfinAdapter] = None,
    http_client: Optional[HttpClient] = None,
    batch_manifest_path: Optional[str] = None,
    item_manifest_path: Optional[str] = None,
) -> BatchRetrievalRunResult:
    """Process pending Redfin fixture capture requests as a batch.

    Reads pending capture queue items, applies policy checks, and
    optionally retrieves fixtures and processes them.

    Args:
        config: Batch retrieval configuration.
        adapter: Optional RedfinAdapter instance.
        http_client: Optional HTTP client (inject FakeHttpClient for tests).
        batch_manifest_path: Path to batch manifest CSV.
        item_manifest_path: Path to per-item manifest CSV.

    Returns:
        BatchRetrievalRunResult with aggregate statistics.
    """
    if config is None:
        config = BatchRetrievalConfig()

    if adapter is None:
        adapter = RedfinAdapter()

    if batch_manifest_path is None:
        batch_manifest_path = "data/processed/redfin_batch_retrieval_manifest.csv"
    if item_manifest_path is None:
        item_manifest_path = "data/processed/redfin_batch_retrieval_items.csv"

    result = BatchRetrievalRunResult(
        started_at=datetime.now().isoformat(),
        mode=config.mode,
        max_items=config.max_items,
        request_type_filter=config.request_type_filter,
    )

    # Determine mode flags
    dry_run_only = config.mode == "dry_run_only"
    force_live = config.force_live and config.mode != "dry_run_only"
    process_after = config.mode == "retrieve_and_process"

    # Get pending requests
    pending = get_pending_redfin_capture_requests(
        request_type=config.request_type_filter,
        max_items=config.max_items,
        database_path=config.database_path,
    )

    result.pending_scanned = len(pending)

    if not pending:
        result.notes = "No pending Redfin capture requests found."
        result.completed_at = datetime.now().isoformat()
        _append_batch_manifest(batch_manifest_path, result)
        return result

    # Process each item
    for capture_request in pending:
        item_result = retrieve_pending_redfin_capture_request(
            capture_request=capture_request,
            adapter=adapter,
            http_client=http_client,
            force_live=force_live,
            dry_run_only=dry_run_only,
            database_path=config.database_path,
        )

        # Update counters
        if item_result.status == "dry_run":
            result.dry_run_only_count += 1
        elif item_result.status == "retrieved":
            result.attempted_live += 1
            result.retrieved += 1
            result.fixtures_saved += 1
        elif item_result.status == "blocked":
            if force_live:
                result.attempted_live += 1
            result.blocked += 1
        elif item_result.status == "failed":
            result.attempted_live += 1
            result.failed += 1

        # Record per-item manifest
        _append_item_manifest(item_manifest_path, result.run_id, item_result)

        result.items.append(item_result)

    # Post-retrieval processing if configured
    if process_after and result.retrieved > 0:
        try:
            from marketsentry.retrieved_fixture_processor import (
                process_redfin_retrieved_fixtures,
            )

            proc_result = process_redfin_retrieved_fixtures(
                database_path=config.database_path,
                output_dir=config.output_dir,
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
                            database_path=config.database_path,
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
    elif config.mode == "retrieve_only" and result.retrieved > 0:
        # retrieve_only: mark captured without processing
        for item in result.items:
            if item.status == "retrieved" and item.fixture_path:
                try:
                    marked = mark_fixture_captured(
                        capture_request_id=item.capture_request_id,
                        fixture_path=item.fixture_path,
                        database_path=config.database_path,
                    )
                    if marked:
                        item.marked_captured = True
                        result.queue_items_marked_captured += 1
                except Exception as e:
                    result.warnings.append(
                        f"Failed to mark captured (ID {item.capture_request_id}): {e}"
                    )

    # Set audit log path
    audit_dir = Path("logs/retrieval_audit")
    today = datetime.now().strftime("%Y%m%d")
    result.audit_log_path = str(audit_dir / f"retrieval_audit_{today}.csv")

    result.completed_at = datetime.now().isoformat()

    # Write batch manifest
    _append_batch_manifest(batch_manifest_path, result)

    return result


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def summarize_batch_retrieval_run(result: BatchRetrievalRunResult) -> str:
    """Generate an ASCII-safe summary of a batch retrieval run.

    Args:
        result: Completed batch run result.

    Returns:
        Multi-line string summary.
    """
    lines = [
        "=== Redfin Pending Capture Batch Retrieval ===",
        f"Run ID: {result.run_id}",
        f"Mode: {result.mode}",
        f"Started: {result.started_at}",
        f"Completed: {result.completed_at}",
        "",
        f"Pending scanned: {result.pending_scanned}",
        f"Dry-run only: {result.dry_run_only_count}",
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
        for rpt in result.reports_exported:
            lines.append(f"  - {rpt}")

    if result.audit_log_path:
        lines.append(f"Audit log: {result.audit_log_path}")

    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in result.warnings:
            lines.append(f"  - {w}")

    if result.errors:
        lines.append("")
        lines.append("Errors:")
        for e in result.errors:
            lines.append(f"  - {e}")

    if result.notes:
        lines.append("")
        lines.append(f"Notes: {result.notes}")

    # Per-item details
    if result.items:
        lines.append("")
        lines.append("--- Per-Item Results ---")
        for item in result.items:
            lines.append(
                f"  [{item.status.upper()}] ID={item.capture_request_id} "
                f"type={item.request_type} url={item.source_url}"
            )
            if item.reason:
                lines.append(f"    Reason: {item.reason}")
            if item.fixture_path:
                lines.append(f"    Fixture: {item.fixture_path}")
            if item.error:
                lines.append(f"    Error: {item.error}")
            if item.marked_captured:
                lines.append("    Marked captured: yes")

    return "\n".join(lines)
