"""Retrieval operations aging, alerts, and health checks.

Provides health check functions that inspect local data (SQLite database,
CSV manifests, audit logs, policy files, fixture directories) to surface
stale items, missing config, audit anomalies, and next recommended actions.

All functions are read-only and perform no network calls.
"""

import csv
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from marketsentry.logging_config import logger


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RetrievalHealthIssue(BaseModel):
    """A single health check issue found during inspection."""

    category: str = ""
    severity: str = "info"  # info, warning, error, critical
    message: str = ""
    detail: str = ""
    source: str = ""
    item_id: str = ""
    age_days: float = 0.0


class RetrievalAgingBucket(BaseModel):
    """Counts of items by age bracket."""

    bucket_label: str = ""
    count: int = 0
    threshold_days: float = 0.0


class RetrievalNextAction(BaseModel):
    """A recommended next action for the operator."""

    priority: int = 0
    action: str = ""
    reason: str = ""
    command: str = ""


class RetrievalHealthCheckConfig(BaseModel):
    """Configurable thresholds for health checks."""

    pending_capture_stale_days: float = 7.0
    approval_package_stale_hours: float = 24.0
    dry_run_approval_stale_hours: float = 24.0
    retrieved_fixture_unprocessed_hours: float = 24.0
    repeated_blocked_threshold: int = 3
    policies_dir: str = "data/policies/robots"


class RetrievalHealthSummary(BaseModel):
    """Aggregate result of all health checks."""

    checked_at: str = ""
    total_issues: int = 0
    info_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    critical_count: int = 0
    issues: List[RetrievalHealthIssue] = Field(default_factory=list)
    aging_buckets: List[RetrievalAgingBucket] = Field(default_factory=list)
    next_actions: List[RetrievalNextAction] = Field(default_factory=list)
    stale_capture_request_count: int = 0
    stale_approval_package_count: int = 0
    unprocessed_fixture_count: int = 0
    audit_anomaly_count: int = 0
    missing_policy_count: int = 0
    repeated_block_count: int = 0
    unprocessed_cross_site_fixture_count: int = 0
    stale_cross_site_capture_request_count: int = 0
    missing_parser_count: int = 0


# ---------------------------------------------------------------------------
# Top-level runner
# ---------------------------------------------------------------------------


def run_retrieval_health_checks(
    database_path: Optional[str] = None,
    audit_dir: Optional[str] = None,
    processed_dir: Optional[str] = None,
    raw_dir: Optional[str] = None,
    config: Optional[RetrievalHealthCheckConfig] = None,
    now: Optional[datetime] = None,
) -> RetrievalHealthSummary:
    """Run all retrieval health checks and return a summary.

    Args:
        database_path: Path to the SQLite database.
        audit_dir: Path to audit log directory.
        processed_dir: Path to processed data directory.
        raw_dir: Path to raw data directory.
        config: Optional health check configuration overrides.
        now: Optional current time for testing.

    Returns:
        RetrievalHealthSummary with all issues found.
    """
    if config is None:
        config = RetrievalHealthCheckConfig()
    if now is None:
        now = datetime.now()

    summary = RetrievalHealthSummary(checked_at=now.isoformat())

    # Run each category of checks
    summary.issues.extend(
        check_fixture_capture_queue_aging(
            database_path=database_path, config=config, now=now,
        )
    )
    summary.issues.extend(
        check_approval_package_aging(
            processed_dir=processed_dir, config=config, now=now,
        )
    )
    summary.issues.extend(
        check_batch_retrieval_failures(
            processed_dir=processed_dir, config=config,
        )
    )
    summary.issues.extend(
        check_retrieval_audit_anomalies(
            audit_dir=audit_dir,
        )
    )
    summary.issues.extend(
        check_retrieved_fixture_processing_gaps(
            processed_dir=processed_dir, raw_dir=raw_dir,
            config=config, now=now,
        )
    )
    summary.issues.extend(
        check_local_policy_files(
            database_path=database_path, config=config,
        )
    )
    summary.issues.extend(
        check_cross_site_fixture_processing_gaps(
            processed_dir=processed_dir, raw_dir=raw_dir,
            config=config, now=now,
        )
    )
    summary.issues.extend(
        check_cross_site_parser_availability(
            database_path=database_path,
        )
    )

    # Count by severity
    for issue in summary.issues:
        if issue.severity == "info":
            summary.info_count += 1
        elif issue.severity == "warning":
            summary.warning_count += 1
        elif issue.severity == "error":
            summary.error_count += 1
        elif issue.severity == "critical":
            summary.critical_count += 1
    summary.total_issues = len(summary.issues)

    # Count specific categories
    summary.stale_capture_request_count = sum(
        1 for i in summary.issues if i.category == "stale_capture_request"
    )
    summary.stale_approval_package_count = sum(
        1 for i in summary.issues if i.category == "stale_approval_package"
    )
    summary.unprocessed_fixture_count = sum(
        1 for i in summary.issues if i.category == "unprocessed_fixture"
    )
    summary.audit_anomaly_count = sum(
        1 for i in summary.issues if i.category == "audit_anomaly"
    )
    summary.missing_policy_count = sum(
        1 for i in summary.issues if i.category == "missing_policy"
    )
    summary.repeated_block_count = sum(
        1 for i in summary.issues if i.category == "repeated_block"
    )
    summary.unprocessed_cross_site_fixture_count = sum(
        1 for i in summary.issues
        if i.category == "unprocessed_cross_site_fixture"
    )
    summary.stale_cross_site_capture_request_count = sum(
        1 for i in summary.issues
        if i.category == "stale_capture_request"
        and i.source in ("zillow", "realtor", "homes", "compass")
    )
    summary.missing_parser_count = sum(
        1 for i in summary.issues if i.category == "missing_parser"
    )

    # Build aging buckets for capture queue
    _build_aging_buckets(summary)

    # Generate next actions
    summary.next_actions = generate_retrieval_next_actions(summary)

    return summary


# ---------------------------------------------------------------------------
# Individual health checks
# ---------------------------------------------------------------------------


def check_fixture_capture_queue_aging(
    database_path: Optional[str] = None,
    config: Optional[RetrievalHealthCheckConfig] = None,
    now: Optional[datetime] = None,
) -> List[RetrievalHealthIssue]:
    """Check for stale pending fixture capture requests.

    Args:
        database_path: Path to the SQLite database.
        config: Health check configuration.
        now: Current time for age calculation.

    Returns:
        List of health issues for stale pending capture requests.
    """
    if config is None:
        config = RetrievalHealthCheckConfig()
    if now is None:
        now = datetime.now()

    issues: List[RetrievalHealthIssue] = []

    try:
        from marketsentry.fixture_capture_queue import list_all_capture_requests

        rows = list_all_capture_requests(database_path=database_path)
    except Exception as e:
        logger.debug(f"Could not load capture queue for health check: {e}")
        return issues

    threshold = timedelta(days=config.pending_capture_stale_days)

    for row in rows:
        if row.get("status") != "pending":
            continue

        created_at_str = row.get("created_at", "")
        if not created_at_str:
            continue

        try:
            created_at = datetime.fromisoformat(created_at_str)
        except (ValueError, TypeError):
            continue

        age = now - created_at
        if age > threshold:
            age_days = age.total_seconds() / 86400.0
            issues.append(RetrievalHealthIssue(
                category="stale_capture_request",
                severity="warning",
                message=f"Pending capture request is {age_days:.1f} days old",
                detail=(
                    f"URL: {row.get('source_url', '')}, "
                    f"Type: {row.get('request_type', '')}, "
                    f"Source: {row.get('source_site', '')}"
                ),
                source=row.get("source_site", ""),
                item_id=str(row.get("capture_request_id", "")),
                age_days=age_days,
            ))

    return issues


def check_approval_package_aging(
    processed_dir: Optional[str] = None,
    config: Optional[RetrievalHealthCheckConfig] = None,
    now: Optional[datetime] = None,
) -> List[RetrievalHealthIssue]:
    """Check for stale approval packages that were never retrieved.

    Args:
        processed_dir: Path to processed data directory.
        config: Health check configuration.
        now: Current time for age calculation.

    Returns:
        List of health issues for stale approval packages.
    """
    if config is None:
        config = RetrievalHealthCheckConfig()
    if now is None:
        now = datetime.now()

    issues: List[RetrievalHealthIssue] = []

    manifest_path = Path(
        processed_dir or "data/processed"
    ) / "redfin_retrieval_approval_manifest.csv"

    if not manifest_path.exists():
        return issues

    threshold = timedelta(hours=config.approval_package_stale_hours)

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                created_at_str = row.get("created_at", "")
                if not created_at_str:
                    continue

                try:
                    created_at = datetime.fromisoformat(created_at_str)
                except (ValueError, TypeError):
                    continue

                age = now - created_at
                if age <= threshold:
                    continue

                # Check if any approved rows were never retrieved
                try:
                    approved = int(row.get("approved_count_when_imported", 0))
                    retrieved = int(row.get("retrieved_count", 0))
                except (ValueError, TypeError):
                    approved = 0
                    retrieved = 0

                run_id = row.get("approval_run_id", "")

                if approved > retrieved:
                    age_hours = age.total_seconds() / 3600.0
                    issues.append(RetrievalHealthIssue(
                        category="stale_approval_package",
                        severity="warning",
                        message=(
                            f"Approval package {run_id} is {age_hours:.1f}h old "
                            f"with {approved - retrieved} unretrieved approved rows"
                        ),
                        detail=(
                            f"Approved: {approved}, Retrieved: {retrieved}, "
                            f"Created: {created_at_str}"
                        ),
                        source="redfin",
                        item_id=run_id,
                        age_days=age.total_seconds() / 86400.0,
                    ))
    except Exception as e:
        logger.debug(f"Could not check approval manifest: {e}")

    return issues


def check_batch_retrieval_failures(
    processed_dir: Optional[str] = None,
    config: Optional[RetrievalHealthCheckConfig] = None,
) -> List[RetrievalHealthIssue]:
    """Check for repeatedly blocked retrieval attempts.

    Args:
        processed_dir: Path to processed data directory.
        config: Health check configuration.

    Returns:
        List of health issues for repeated retrieval blocks.
    """
    if config is None:
        config = RetrievalHealthCheckConfig()

    issues: List[RetrievalHealthIssue] = []

    items_path = Path(
        processed_dir or "data/processed"
    ) / "redfin_batch_retrieval_items.csv"

    if not items_path.exists():
        return issues

    # Count blocks per URL
    block_counts: Dict[str, int] = {}
    block_reasons: Dict[str, str] = {}

    try:
        with open(items_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                decision = row.get("decision", "").upper()
                if decision == "BLOCKED" or row.get("status", "").lower() == "blocked":
                    url = row.get("source_url", "")
                    if url:
                        block_counts[url] = block_counts.get(url, 0) + 1
                        reason = row.get("reason", "")
                        if reason:
                            block_reasons[url] = reason
    except Exception as e:
        logger.debug(f"Could not check batch items: {e}")
        return issues

    threshold = config.repeated_blocked_threshold
    for url, count in block_counts.items():
        if count >= threshold:
            issues.append(RetrievalHealthIssue(
                category="repeated_block",
                severity="warning",
                message=f"URL blocked {count} times (threshold: {threshold})",
                detail=(
                    f"URL: {url}, "
                    f"Last reason: {block_reasons.get(url, 'unknown')}"
                ),
                source="redfin",
                item_id=url,
                age_days=0.0,
            ))

    return issues


def check_retrieval_audit_anomalies(
    audit_dir: Optional[str] = None,
) -> List[RetrievalHealthIssue]:
    """Check for unexpected network_call_performed=true in audit logs.

    Any record with network_call_performed=true is flagged as a critical
    anomaly, since network calls should only happen during explicit live
    retrieval commands.

    Args:
        audit_dir: Path to audit log directory.

    Returns:
        List of health issues for audit anomalies.
    """
    issues: List[RetrievalHealthIssue] = []

    log_dir = Path(audit_dir or "logs/retrieval_audit")
    if not log_dir.exists():
        return issues

    audit_files = sorted(log_dir.glob("retrieval_audit_*.csv"))

    for audit_file in audit_files:
        try:
            with open(audit_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    net_call = row.get(
                        "network_call_performed", ""
                    ).lower() == "true"
                    if net_call:
                        issues.append(RetrievalHealthIssue(
                            category="audit_anomaly",
                            severity="critical",
                            message=(
                                "Unexpected network_call_performed=true "
                                "in audit log"
                            ),
                            detail=(
                                f"File: {audit_file.name}, "
                                f"URL: {row.get('url', '')}, "
                                f"Source: {row.get('source_site', '')}, "
                                f"Mode: {row.get('retrieval_mode', '')}, "
                                f"Time: {row.get('timestamp', '')}"
                            ),
                            source=row.get("source_site", ""),
                            item_id=row.get("url", ""),
                        ))
        except Exception as e:
            logger.debug(f"Could not parse audit file {audit_file}: {e}")

    return issues


def check_retrieved_fixture_processing_gaps(
    processed_dir: Optional[str] = None,
    raw_dir: Optional[str] = None,
    config: Optional[RetrievalHealthCheckConfig] = None,
    now: Optional[datetime] = None,
) -> List[RetrievalHealthIssue]:
    """Check for retrieved fixtures that have not been processed.

    Compares fixtures found in data/raw/redfin/ against the processing
    manifest to find unprocessed files.

    Args:
        processed_dir: Path to processed data directory.
        raw_dir: Path to raw data directory.
        config: Health check configuration.
        now: Current time for age calculation.

    Returns:
        List of health issues for unprocessed fixtures.
    """
    if config is None:
        config = RetrievalHealthCheckConfig()
    if now is None:
        now = datetime.now()

    issues: List[RetrievalHealthIssue] = []

    # Load processed fixture paths from manifest
    manifest_path = Path(
        processed_dir or "data/processed"
    ) / "redfin_fixture_processing_manifest.csv"

    processed_paths: set = set()
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    status = row.get("status", "")
                    if status == "processed":
                        fp = row.get("fixture_path", "")
                        if fp:
                            processed_paths.add(Path(fp).name)
        except Exception as e:
            logger.debug(f"Could not load processing manifest: {e}")

    # Scan raw fixture directories for HTML files
    raw_path = Path(raw_dir or "data/raw")
    redfin_dirs = [
        raw_path / "redfin" / "search",
        raw_path / "redfin" / "details",
    ]

    threshold = timedelta(hours=config.retrieved_fixture_unprocessed_hours)

    for fixture_dir in redfin_dirs:
        if not fixture_dir.exists():
            continue
        for html_file in fixture_dir.glob("*.html"):
            if html_file.name in processed_paths:
                continue

            # Check age
            try:
                mtime = datetime.fromtimestamp(html_file.stat().st_mtime)
                age = now - mtime
                if age > threshold:
                    age_hours = age.total_seconds() / 3600.0
                    issues.append(RetrievalHealthIssue(
                        category="unprocessed_fixture",
                        severity="warning",
                        message=(
                            f"Retrieved fixture unprocessed for "
                            f"{age_hours:.1f} hours"
                        ),
                        detail=f"Path: {html_file}",
                        source="redfin",
                        item_id=str(html_file),
                        age_days=age.total_seconds() / 86400.0,
                    ))
            except Exception as e:
                logger.debug(f"Could not stat fixture {html_file}: {e}")

    return issues


def check_local_policy_files(
    database_path: Optional[str] = None,
    config: Optional[RetrievalHealthCheckConfig] = None,
) -> List[RetrievalHealthIssue]:
    """Check for missing local robots policy files and config values.

    Flags missing robots policy when live retrieval is configured or the
    capture queue is non-empty. Also checks for missing User-Agent and
    contact email when live retrieval is enabled.

    Args:
        database_path: Path to the SQLite database.
        config: Health check configuration.

    Returns:
        List of health issues for missing policy files and config.
    """
    if config is None:
        config = RetrievalHealthCheckConfig()

    issues: List[RetrievalHealthIssue] = []

    # Load compliance config
    from marketsentry.source_adapters.compliance import RetrievalComplianceConfig

    cc = RetrievalComplianceConfig.from_env()

    # Check if capture queue has pending items
    has_pending = False
    try:
        from marketsentry.fixture_capture_queue import list_all_capture_requests

        rows = list_all_capture_requests(database_path=database_path)
        has_pending = any(r.get("status") == "pending" for r in rows)
    except Exception:
        pass

    needs_policy = cc.live_retrieval_enabled or has_pending

    if needs_policy:
        # Check for Redfin robots policy file
        policies_dir = Path(config.policies_dir)
        redfin_robots = policies_dir / "redfin_robots.txt"
        if not redfin_robots.exists():
            severity = "error" if cc.live_retrieval_enabled else "warning"
            issues.append(RetrievalHealthIssue(
                category="missing_policy",
                severity=severity,
                message="Missing local robots policy file for Redfin",
                detail=(
                    f"Expected: {redfin_robots}. "
                    "Save Redfin's robots.txt locally before live retrieval."
                ),
                source="redfin",
            ))

    # Check config when live retrieval is enabled
    if cc.live_retrieval_enabled:
        if not cc.live_user_agent:
            issues.append(RetrievalHealthIssue(
                category="missing_policy",
                severity="error",
                message="Live retrieval enabled but User-Agent not configured",
                detail=(
                    "Set MARKETSENTRY_LIVE_USER_AGENT environment variable "
                    "to identify your client."
                ),
                source="config",
            ))

        if not cc.live_contact_email:
            issues.append(RetrievalHealthIssue(
                category="missing_policy",
                severity="error",
                message="Live retrieval enabled but contact email not configured",
                detail=(
                    "Set MARKETSENTRY_LIVE_CONTACT_EMAIL environment variable "
                    "to provide operator contact information."
                ),
                source="config",
            ))

    return issues


def check_cross_site_fixture_processing_gaps(
    processed_dir: Optional[str] = None,
    raw_dir: Optional[str] = None,
    config: Optional[RetrievalHealthCheckConfig] = None,
    now: Optional[datetime] = None,
) -> List[RetrievalHealthIssue]:
    """Check for unprocessed cross-site fixtures.

    Compares HTML fixtures in cross-site source directories against the
    cross-site processing manifest to find unprocessed files.

    Args:
        processed_dir: Path to processed data directory.
        raw_dir: Path to raw data directory.
        config: Health check configuration.
        now: Current time for age calculation.

    Returns:
        List of health issues for unprocessed cross-site fixtures.
    """
    if config is None:
        config = RetrievalHealthCheckConfig()
    if now is None:
        now = datetime.now()

    issues: List[RetrievalHealthIssue] = []

    cross_site_sources = ["zillow", "realtor", "homes", "compass"]

    # Load processed fixture hashes from cross-site manifest
    manifest_path = Path(
        processed_dir or "data/processed"
    ) / "cross_site_fixture_processing_manifest.csv"

    processed_hashes: set = set()
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    h = row.get("content_hash", "")
                    status = row.get("status", "")
                    if h and status == "processed":
                        processed_hashes.add(h)
        except Exception as e:
            logger.debug(f"Could not load cross-site manifest: {e}")

    # Scan cross-site directories for HTML files
    raw_path = Path(raw_dir or "data/raw")

    threshold = timedelta(hours=config.retrieved_fixture_unprocessed_hours)

    for source in cross_site_sources:
        source_dirs = [
            raw_path / source / "details",
            Path(f"data/raw/cross_site/{source}"),
        ]
        for fixture_dir in source_dirs:
            if not fixture_dir.exists():
                continue
            for html_file in fixture_dir.glob("*.html"):
                # Compute content hash
                try:
                    import hashlib

                    content = html_file.read_text(
                        encoding="utf-8", errors="replace",
                    )
                    content_hash = hashlib.sha256(
                        content.encode("utf-8")
                    ).hexdigest()
                except Exception:
                    continue

                if content_hash in processed_hashes:
                    continue

                # Check age
                try:
                    mtime = datetime.fromtimestamp(html_file.stat().st_mtime)
                    age = now - mtime
                    if age > threshold:
                        age_hours = age.total_seconds() / 3600.0
                        issues.append(RetrievalHealthIssue(
                            category="unprocessed_cross_site_fixture",
                            severity="warning",
                            message=(
                                f"Cross-site {source} fixture unprocessed "
                                f"for {age_hours:.1f} hours"
                            ),
                            detail=f"Path: {html_file}",
                            source=source,
                            item_id=str(html_file),
                            age_days=age.total_seconds() / 86400.0,
                        ))
                except Exception as e:
                    logger.debug(
                        f"Could not stat cross-site fixture {html_file}: {e}"
                    )

    return issues


def check_cross_site_parser_availability(
    database_path: Optional[str] = None,
) -> List[RetrievalHealthIssue]:
    """Check that parsers are available for cross-site sources with pending requests.

    Only flags a missing parser warning when there are pending capture
    requests for a source that lacks a parser.

    Args:
        database_path: Path to the SQLite database.

    Returns:
        List of health issues for missing parsers.
    """
    issues: List[RetrievalHealthIssue] = []

    cross_site_sources = ["zillow", "realtor", "homes", "compass"]

    # Check which sources have pending capture requests
    sources_with_pending: set = set()
    try:
        from marketsentry.fixture_capture_queue import list_all_capture_requests

        rows = list_all_capture_requests(database_path=database_path)
        for row in rows:
            if row.get("status") == "pending":
                src = row.get("source_site", "")
                if src in cross_site_sources:
                    sources_with_pending.add(src)
    except Exception:
        pass

    if not sources_with_pending:
        return issues

    # Check parser availability
    from marketsentry.cross_site_fixture_processor import _get_parser

    for source in sources_with_pending:
        parser = _get_parser(source)
        if parser is None:
            issues.append(RetrievalHealthIssue(
                category="missing_parser",
                severity="warning",
                message=f"No parser available for {source}",
                detail=(
                    f"Source {source} has pending capture requests "
                    f"but no parser is available to process fixtures."
                ),
                source=source,
            ))

    return issues


# ---------------------------------------------------------------------------
# Next actions
# ---------------------------------------------------------------------------


def generate_retrieval_next_actions(
    summary: RetrievalHealthSummary,
) -> List[RetrievalNextAction]:
    """Generate recommended next actions based on health check results.

    Args:
        summary: The health check summary with all issues.

    Returns:
        Prioritized list of next actions.
    """
    actions: List[RetrievalNextAction] = []
    priority = 1

    # Critical issues first
    if summary.critical_count > 0:
        actions.append(RetrievalNextAction(
            priority=priority,
            action="Investigate critical audit anomalies",
            reason=(
                f"{summary.critical_count} critical issue(s) found "
                "(unexpected network calls in audit logs)"
            ),
            command="marketsentry retrieval-health-check",
        ))
        priority += 1

    # Missing policy files
    if summary.missing_policy_count > 0:
        actions.append(RetrievalNextAction(
            priority=priority,
            action="Resolve missing policy files or configuration",
            reason=f"{summary.missing_policy_count} missing policy/config issue(s)",
            command=(
                "Save robots.txt to data/policies/robots/redfin_robots.txt "
                "and configure MARKETSENTRY_LIVE_* env vars"
            ),
        ))
        priority += 1

    # Stale capture requests
    if summary.stale_capture_request_count > 0:
        actions.append(RetrievalNextAction(
            priority=priority,
            action="Process or skip stale pending capture requests",
            reason=(
                f"{summary.stale_capture_request_count} pending capture "
                "request(s) older than threshold"
            ),
            command="marketsentry list-fixture-capture-queue",
        ))
        priority += 1

    # Unprocessed fixtures
    if summary.unprocessed_fixture_count > 0:
        actions.append(RetrievalNextAction(
            priority=priority,
            action="Process retrieved but unprocessed fixtures",
            reason=(
                f"{summary.unprocessed_fixture_count} fixture(s) "
                "awaiting processing"
            ),
            command="marketsentry process-redfin-retrieved-fixtures",
        ))
        priority += 1

    # Stale approval packages
    if summary.stale_approval_package_count > 0:
        actions.append(RetrievalNextAction(
            priority=priority,
            action="Review or discard stale approval packages",
            reason=(
                f"{summary.stale_approval_package_count} approval package(s) "
                "with unretrieved approved rows"
            ),
            command="marketsentry retrieval-operations-summary",
        ))
        priority += 1

    # Repeated blocks
    if summary.repeated_block_count > 0:
        actions.append(RetrievalNextAction(
            priority=priority,
            action="Investigate repeatedly blocked URLs",
            reason=(
                f"{summary.repeated_block_count} URL(s) blocked "
                "multiple times"
            ),
            command="marketsentry retrieval-operations-summary",
        ))
        priority += 1

    # Unprocessed cross-site fixtures
    if summary.unprocessed_cross_site_fixture_count > 0:
        actions.append(RetrievalNextAction(
            priority=priority,
            action="Process unprocessed cross-site fixtures",
            reason=(
                f"{summary.unprocessed_cross_site_fixture_count} "
                "cross-site fixture(s) awaiting processing"
            ),
            command="marketsentry process-cross-site-fixtures",
        ))
        priority += 1

    # Stale cross-site capture requests
    if summary.stale_cross_site_capture_request_count > 0:
        actions.append(RetrievalNextAction(
            priority=priority,
            action="Save cross-site manual fixtures for stale capture requests",
            reason=(
                f"{summary.stale_cross_site_capture_request_count} "
                "cross-site capture request(s) older than threshold"
            ),
            command="marketsentry list-fixture-capture-queue",
        ))
        priority += 1

    # Missing parsers
    if summary.missing_parser_count > 0:
        actions.append(RetrievalNextAction(
            priority=priority,
            action="Investigate missing cross-site parsers",
            reason=(
                f"{summary.missing_parser_count} source(s) with pending "
                "requests lack a parser"
            ),
            command="marketsentry retrieval-health-check",
        ))
        priority += 1

    # If no issues, recommend routine check
    if not actions:
        actions.append(RetrievalNextAction(
            priority=1,
            action="No action required",
            reason="All retrieval health checks passed",
            command="",
        ))

    return actions


# ---------------------------------------------------------------------------
# Formatting and export
# ---------------------------------------------------------------------------


def format_retrieval_health_summary(
    summary: RetrievalHealthSummary,
) -> str:
    """Format the health summary as a human-readable string.

    Args:
        summary: The health check summary.

    Returns:
        ASCII-safe formatted string.
    """
    lines: List[str] = []
    lines.append("=== Retrieval Health Check ===")
    lines.append("")
    lines.append(f"Checked at: {summary.checked_at}")
    lines.append(f"Total issues: {summary.total_issues}")
    lines.append(f"  Info:     {summary.info_count}")
    lines.append(f"  Warning:  {summary.warning_count}")
    lines.append(f"  Error:    {summary.error_count}")
    lines.append(f"  Critical: {summary.critical_count}")
    lines.append("")

    lines.append("Category Counts:")
    lines.append(
        f"  Stale capture requests:     {summary.stale_capture_request_count}"
    )
    lines.append(
        f"  Stale approval packages:    {summary.stale_approval_package_count}"
    )
    lines.append(
        f"  Unprocessed fixtures:       {summary.unprocessed_fixture_count}"
    )
    lines.append(
        f"  Audit anomalies:            {summary.audit_anomaly_count}"
    )
    lines.append(
        f"  Missing policies/config:    {summary.missing_policy_count}"
    )
    lines.append(
        f"  Repeated blocks:            {summary.repeated_block_count}"
    )
    lines.append(
        f"  Unprocessed cross-site:     "
        f"{summary.unprocessed_cross_site_fixture_count}"
    )
    lines.append(
        f"  Stale cross-site captures:  "
        f"{summary.stale_cross_site_capture_request_count}"
    )
    lines.append(
        f"  Missing parsers:            {summary.missing_parser_count}"
    )
    lines.append("")

    if summary.issues:
        lines.append("Issues:")
        for issue in summary.issues:
            lines.append(
                f"  [{issue.severity.upper()}] {issue.category}: "
                f"{issue.message}"
            )
            if issue.detail:
                lines.append(f"    {issue.detail}")
        lines.append("")

    if summary.next_actions:
        lines.append("Next Actions:")
        for action in summary.next_actions:
            lines.append(f"  {action.priority}. {action.action}")
            lines.append(f"     Reason: {action.reason}")
            if action.command:
                lines.append(f"     Command: {action.command}")
        lines.append("")

    return "\n".join(lines)


def export_retrieval_health_report(
    database_path: Optional[str] = None,
    audit_dir: Optional[str] = None,
    processed_dir: Optional[str] = None,
    raw_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    report_format: str = "md",
    config: Optional[RetrievalHealthCheckConfig] = None,
) -> str:
    """Run health checks and export a report.

    Args:
        database_path: Path to the SQLite database.
        audit_dir: Path to audit log directory.
        processed_dir: Path to processed data directory.
        raw_dir: Path to raw data directory.
        output_dir: Directory for the report file.
        report_format: 'md' or 'csv'.
        config: Optional health check configuration.

    Returns:
        Path to the exported report file.
    """
    summary = run_retrieval_health_checks(
        database_path=database_path,
        audit_dir=audit_dir,
        processed_dir=processed_dir,
        raw_dir=raw_dir,
        config=config,
    )

    out_dir = Path(output_dir or "data/exports")
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if report_format == "csv":
        return _export_csv_report(summary, out_dir, timestamp)
    return _export_md_report(summary, out_dir, timestamp)


def _export_md_report(
    summary: RetrievalHealthSummary,
    out_dir: Path,
    timestamp: str,
) -> str:
    """Export health report as Markdown.

    Args:
        summary: Health check summary.
        out_dir: Output directory.
        timestamp: Filename timestamp.

    Returns:
        Path to the exported file.
    """
    report_path = out_dir / f"retrieval_health_{timestamp}.md"

    lines: List[str] = []
    lines.append("# Retrieval Health Check Report")
    lines.append("")
    lines.append(f"Generated: {summary.checked_at}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total issues: {summary.total_issues}")
    lines.append(f"- Info: {summary.info_count}")
    lines.append(f"- Warning: {summary.warning_count}")
    lines.append(f"- Error: {summary.error_count}")
    lines.append(f"- Critical: {summary.critical_count}")
    lines.append("")
    lines.append("## Category Counts")
    lines.append("")
    lines.append(
        f"- Stale capture requests: {summary.stale_capture_request_count}"
    )
    lines.append(
        f"- Stale approval packages: {summary.stale_approval_package_count}"
    )
    lines.append(
        f"- Unprocessed fixtures: {summary.unprocessed_fixture_count}"
    )
    lines.append(f"- Audit anomalies: {summary.audit_anomaly_count}")
    lines.append(
        f"- Missing policies/config: {summary.missing_policy_count}"
    )
    lines.append(f"- Repeated blocks: {summary.repeated_block_count}")
    lines.append(
        f"- Unprocessed cross-site fixtures: "
        f"{summary.unprocessed_cross_site_fixture_count}"
    )
    lines.append(
        f"- Stale cross-site capture requests: "
        f"{summary.stale_cross_site_capture_request_count}"
    )
    lines.append(f"- Missing parsers: {summary.missing_parser_count}")
    lines.append("")

    if summary.issues:
        lines.append("## Issues")
        lines.append("")
        lines.append(
            "| Severity | Category | Message | Detail |"
        )
        lines.append("| --- | --- | --- | --- |")
        for issue in summary.issues:
            lines.append(
                f"| {issue.severity} | {issue.category} | "
                f"{issue.message} | {issue.detail} |"
            )
        lines.append("")

    if summary.next_actions:
        lines.append("## Next Actions")
        lines.append("")
        for action in summary.next_actions:
            lines.append(f"{action.priority}. **{action.action}**")
            lines.append(f"   - Reason: {action.reason}")
            if action.command:
                lines.append(f"   - Command: `{action.command}`")
            lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return str(report_path)


def _export_csv_report(
    summary: RetrievalHealthSummary,
    out_dir: Path,
    timestamp: str,
) -> str:
    """Export health report as CSV.

    Args:
        summary: Health check summary.
        out_dir: Output directory.
        timestamp: Filename timestamp.

    Returns:
        Path to the exported file.
    """
    report_path = out_dir / f"retrieval_health_{timestamp}.csv"

    fieldnames = [
        "severity", "category", "message", "detail",
        "source", "item_id", "age_days",
    ]

    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for issue in summary.issues:
            writer.writerow({
                "severity": issue.severity,
                "category": issue.category,
                "message": issue.message,
                "detail": issue.detail,
                "source": issue.source,
                "item_id": issue.item_id,
                "age_days": f"{issue.age_days:.1f}",
            })

    return str(report_path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_aging_buckets(summary: RetrievalHealthSummary) -> None:
    """Build aging distribution buckets from stale capture request issues.

    Args:
        summary: Health summary to update in place.
    """
    buckets = {
        "7-14 days": (7.0, 14.0, 0),
        "14-30 days": (14.0, 30.0, 0),
        "30+ days": (30.0, float("inf"), 0),
    }

    for issue in summary.issues:
        if issue.category != "stale_capture_request":
            continue
        for label, (lo, hi, _) in list(buckets.items()):
            if lo <= issue.age_days < hi:
                buckets[label] = (lo, hi, buckets[label][2] + 1)

    for label, (lo, _, count) in buckets.items():
        if count > 0:
            summary.aging_buckets.append(RetrievalAgingBucket(
                bucket_label=label,
                count=count,
                threshold_days=lo,
            ))
