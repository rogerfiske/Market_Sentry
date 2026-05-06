"""Dry-run approval and history gate for Market_Sentry.

Records dry-run approvals so that future live retrieval can verify
that a matching dry-run was performed. Extends the audit log with
structured approval records.

No network calls are performed by this module.
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from marketsentry.logging_config import logger
from marketsentry.source_adapters.policy import (
    DryRunApprovalRecord,
    RetrievalPolicyDecision,
    RetrievalPolicyReason,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_APPROVAL_DIR = "logs/retrieval_audit"

APPROVAL_FIELDNAMES = [
    "timestamp",
    "source_site",
    "url",
    "normalized_url",
    "request_type",
    "compliance_status",
    "allowed",
    "blocked",
    "reasons",
    "network_call_performed",
]


# ---------------------------------------------------------------------------
# URL normalization
# ---------------------------------------------------------------------------


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication and matching.

    Strips trailing slashes, lowercases the domain, removes fragments.

    Args:
        url: URL to normalize.

    Returns:
        Normalized URL string.
    """
    from urllib.parse import urlparse, urlunparse

    try:
        parsed = urlparse(url.strip())
        # Lowercase scheme and host
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        # Strip trailing slashes from path
        path = parsed.path.rstrip("/")
        if not path:
            path = "/"
        # Remove fragment
        return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))
    except Exception:
        return url.strip().rstrip("/")


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


def record_dry_run_approval(
    source_site: str,
    url: str,
    request_type: str,
    compliance_status: str,
    allowed: bool,
    blocked: bool,
    reasons: Optional[List[str]] = None,
    approval_dir: Optional[str] = None,
) -> str:
    """Record a dry-run approval for future reference.

    Args:
        source_site: Source adapter name.
        url: URL that was dry-run previewed.
        request_type: Type of request.
        compliance_status: Summary of compliance check result.
        allowed: Whether the dry-run was allowed.
        blocked: Whether it would be blocked in live mode.
        reasons: List of reasons for the decision.
        approval_dir: Directory for approval logs.

    Returns:
        Path to the approval log file.
    """
    dir_path = Path(approval_dir or DEFAULT_APPROVAL_DIR)
    dir_path.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    log_file = dir_path / f"dry_run_approvals_{date_str}.csv"

    file_exists = log_file.exists()

    normalized = normalize_url(url)

    record = {
        "timestamp": datetime.now().isoformat(),
        "source_site": source_site,
        "url": url,
        "normalized_url": normalized,
        "request_type": request_type,
        "compliance_status": compliance_status,
        "allowed": str(allowed),
        "blocked": str(blocked),
        "reasons": "; ".join(reasons) if reasons else "",
        "network_call_performed": "False",
    }

    with open(log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=APPROVAL_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)

    logger.debug(f"Dry-run approval recorded: {source_site} {url}")
    return str(log_file)


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def has_recent_dry_run_approval(
    source_site: str,
    url: str,
    max_age_hours: int = 24,
    approval_dir: Optional[str] = None,
) -> bool:
    """Check if a recent dry-run approval exists for a URL.

    Searches approval logs for a matching dry-run record within
    the specified time window.

    Args:
        source_site: Source adapter name.
        url: URL to check.
        max_age_hours: Maximum age in hours for a valid approval.
        approval_dir: Directory containing approval logs.

    Returns:
        True if a recent dry-run approval exists.
    """
    dir_path = Path(approval_dir or DEFAULT_APPROVAL_DIR)
    if not dir_path.exists():
        return False

    normalized = normalize_url(url)
    cutoff = datetime.now() - timedelta(hours=max_age_hours)

    # Check approval files from recent dates
    for log_file in sorted(dir_path.glob("dry_run_approvals_*.csv"), reverse=True):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Match source and normalized URL
                    if (
                        row.get("source_site") == source_site
                        and row.get("normalized_url") == normalized
                    ):
                        # Check timestamp
                        try:
                            ts = datetime.fromisoformat(row["timestamp"])
                            if ts >= cutoff:
                                return True
                        except (ValueError, KeyError):
                            continue
        except (OSError, csv.Error):
            continue

    return False


def get_dry_run_approvals(
    source_site: Optional[str] = None,
    max_age_hours: int = 24,
    approval_dir: Optional[str] = None,
) -> List[DryRunApprovalRecord]:
    """Get recent dry-run approval records.

    Args:
        source_site: Filter by source site. None for all.
        max_age_hours: Maximum age in hours.
        approval_dir: Directory containing approval logs.

    Returns:
        List of DryRunApprovalRecord objects.
    """
    dir_path = Path(approval_dir or DEFAULT_APPROVAL_DIR)
    if not dir_path.exists():
        return []

    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    records: List[DryRunApprovalRecord] = []

    for log_file in sorted(dir_path.glob("dry_run_approvals_*.csv"), reverse=True):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Filter by source
                    if source_site and row.get("source_site") != source_site:
                        continue

                    # Check timestamp
                    try:
                        ts = datetime.fromisoformat(row.get("timestamp", ""))
                        if ts < cutoff:
                            continue
                    except (ValueError, TypeError):
                        continue

                    record = DryRunApprovalRecord(
                        source_site=row.get("source_site", ""),
                        url=row.get("url", ""),
                        normalized_url=row.get("normalized_url", ""),
                        request_type=row.get("request_type", ""),
                        dry_run_timestamp=row.get("timestamp", ""),
                        compliance_status=row.get("compliance_status", ""),
                        allowed=row.get("allowed", "").lower() == "true",
                        blocked=row.get("blocked", "").lower() == "true",
                        reasons=row.get("reasons", "").split("; ") if row.get("reasons") else [],
                        network_call_performed=False,
                    )
                    records.append(record)
        except (OSError, csv.Error):
            continue

    return records


def require_recent_dry_run_before_live(
    source_site: str,
    url: str,
    max_age_hours: int = 24,
    approval_dir: Optional[str] = None,
) -> tuple:
    """Check if a recent dry-run exists and return a policy-compatible result.

    Args:
        source_site: Source adapter name.
        url: URL to check.
        max_age_hours: Maximum age in hours.
        approval_dir: Directory containing approval logs.

    Returns:
        Tuple of (has_approval: bool, reason: RetrievalPolicyReason or None).
    """
    has_approval = has_recent_dry_run_approval(
        source_site=source_site,
        url=url,
        max_age_hours=max_age_hours,
        approval_dir=approval_dir,
    )

    if has_approval:
        return True, None

    reason = RetrievalPolicyReason(
        code="dry_run_required",
        message=(
            f"No recent dry-run approval found for {source_site} URL within "
            f"{max_age_hours} hours. Run a dry-run first."
        ),
        severity="error",
    )
    return False, reason
