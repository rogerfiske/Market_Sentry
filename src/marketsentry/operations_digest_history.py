"""Operations Digest Historical Snapshots and Comparison Reports (Milestone 39).

This module tracks high-level operations changes over time by persisting
append-only digest snapshots and generating snapshot-over-snapshot comparison
reports.  It is read-only except for writing snapshot rows and export files.
It does not mutate candidate, watchlist, alert, or property state.
"""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from marketsentry.database import execute_query, get_connection, table_exists
from marketsentry.models import (
    OperationsDigestComparisonReportRow,
    OperationsDigestHistorySummary,
    OperationsDigestSnapshot,
    OperationsDigestSnapshotRunResult,
    OperationsDigestTrendChange,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert *val* to int."""
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _row_to_dict(row: Any) -> Dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return {}
    return dict(row)


# ---------------------------------------------------------------------------
# Digest score and status label
# ---------------------------------------------------------------------------

DIGEST_STATUS_THRESHOLDS = [
    (90, "clear"),
    (75, "light_review"),
    (60, "active_review"),
    (40, "heavy_review"),
    (0, "backlog_attention"),
]


def _calculate_digest_score(metrics: Dict[str, int]) -> int:
    """Calculate operational digest score 0-100.

    Higher score means fewer local review backlogs.  This is an
    operational-health metric only and is not purchase advice.

    Args:
        metrics: Dictionary of metric counts from
                 calculate_operations_digest_snapshot_metrics.

    Returns:
        Integer score 0-100.
    """
    score = 100

    # Pending candidate decisions: -2 each, max -20
    score -= min(metrics.get("pending_user_decision_count", 0) * 2, 20)
    # Reject location noise: -1 each, max -5
    score -= min(metrics.get("reject_location_noise_count", 0) * 1, 5)
    # High churn: -2 each, max -10
    score -= min(metrics.get("high_churn_count", 0) * 2, 10)
    # High effective DOM delta: -1 each, max -5
    score -= min(metrics.get("high_effective_dom_delta_count", 0) * 1, 5)
    # Low cross-site confidence: -2 each, max -10
    score -= min(metrics.get("low_cross_site_confidence_count", 0) * 2, 10)
    # High discrepancy severity: -2 each, max -10
    score -= min(metrics.get("high_discrepancy_severity_count", 0) * 2, 10)
    # High/critical open alerts: -3 each, max -15
    score -= min(
        metrics.get("high_or_critical_open_alert_count", 0) * 3, 15
    )
    # Stale open alerts: -2 each, max -10
    score -= min(metrics.get("stale_open_alert_count", 0) * 2, 10)
    # Needs reparse: -1 each, max -5
    score -= min(metrics.get("needs_reparse_count", 0) * 1, 5)
    # Needs manual review: -2 each, max -10
    score -= min(metrics.get("needs_manual_review_count", 0) * 2, 10)
    # Lifecycle attention required: -3 each, max -10
    score -= min(
        metrics.get("lifecycle_attention_required_count", 0) * 3, 10
    )
    # Lifecycle needs review: -2 each, max -10
    score -= min(metrics.get("lifecycle_needs_review_count", 0) * 2, 10)
    # Lifecycle gaps: -2 each, max -10
    score -= min(metrics.get("lifecycle_gap_count", 0) * 2, 10)
    # Retrieval health issues: -2 each, max -10
    score -= min(metrics.get("retrieval_health_issue_count", 0) * 2, 10)
    # Retrieval pending capture: -1 each, max -5
    score -= min(
        metrics.get("retrieval_pending_capture_count", 0) * 1, 5
    )

    return max(0, score)


def _digest_status_label(score: int) -> str:
    """Return the status label for a given digest score.

    Args:
        score: Digest score 0-100.

    Returns:
        One of: clear, light_review, active_review, heavy_review,
        backlog_attention.
    """
    for threshold, label in DIGEST_STATUS_THRESHOLDS:
        if score >= threshold:
            return label
    return "backlog_attention"


# ---------------------------------------------------------------------------
# Metric calculation
# ---------------------------------------------------------------------------

def calculate_operations_digest_snapshot_metrics(
    db_path: Optional[str] = None,
) -> Dict[str, int]:
    """Query the database and compute all digest snapshot metrics.

    This is a read-only operation.  It queries existing tables but does
    not mutate any state.

    Args:
        db_path: Database path.

    Returns:
        Dictionary mapping metric names to integer counts.
    """
    metrics: Dict[str, int] = {}

    # --- Candidate counts ---
    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM candidate_review_queue",
            database_path=db_path,
        )
        metrics["candidate_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["candidate_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM candidate_review_queue "
            "WHERE review_status = 'pending_user_decision'",
            database_path=db_path,
        )
        metrics["pending_user_decision_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["pending_user_decision_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM candidate_review_queue "
            "WHERE review_status = 'strong_review'",
            database_path=db_path,
        )
        metrics["strong_review_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["strong_review_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM candidate_review_queue "
            "WHERE review_status = 'reject_location_noise'",
            database_path=db_path,
        )
        metrics["reject_location_noise_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["reject_location_noise_count"] = 0

    # --- Watched property counts ---
    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM watched_properties",
            database_path=db_path,
        )
        metrics["watched_property_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["watched_property_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM watched_properties "
            "WHERE active_watch_status = 1",
            database_path=db_path,
        )
        metrics["active_watched_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["active_watched_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM watched_properties "
            "WHERE watch_priority = 1",
            database_path=db_path,
        )
        metrics["high_priority_watched_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["high_priority_watched_count"] = 0

    # --- Gas / Garage evidence ---
    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM watched_properties "
            "WHERE gas_service = 1 OR "
            "(gas_evidence IS NOT NULL AND gas_evidence != '')",
            database_path=db_path,
        )
        metrics["gas_evidence_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["gas_evidence_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM watched_properties "
            "WHERE garage_spaces IS NOT NULL AND garage_spaces > 0",
            database_path=db_path,
        )
        metrics["garage_evidence_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["garage_evidence_count"] = 0

    # --- County reset / churn / DOM ---
    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM watched_properties "
            "WHERE county_reset_applied = 1",
            database_path=db_path,
        )
        metrics["county_reset_applied_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["county_reset_applied_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM watched_properties "
            "WHERE recent_churn_index > 3",
            database_path=db_path,
        )
        metrics["high_churn_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["high_churn_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM watched_properties "
            "WHERE effective_dom_v2 IS NOT NULL AND "
            "effective_dom_v1 IS NOT NULL AND "
            "ABS(effective_dom_v2 - effective_dom_v1) > 30",
            database_path=db_path,
        )
        metrics["high_effective_dom_delta_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["high_effective_dom_delta_count"] = 0

    # --- Cross-site ---
    try:
        rows = execute_query(
            "SELECT COUNT(DISTINCT property_id) AS cnt "
            "FROM cross_site_observations",
            database_path=db_path,
        )
        metrics["cross_site_observed_property_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["cross_site_observed_property_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM cross_site_analytics_snapshots "
            "WHERE overall_cross_site_confidence_score < 50",
            database_path=db_path,
        )
        metrics["low_cross_site_confidence_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["low_cross_site_confidence_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM cross_site_analytics_snapshots "
            "WHERE discrepancy_severity_label IN "
            "('high', 'critical')",
            database_path=db_path,
        )
        metrics["high_discrepancy_severity_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["high_discrepancy_severity_count"] = 0

    # --- Alerts ---
    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM cross_site_trend_alerts "
            "WHERE alert_status = 'open'",
            database_path=db_path,
        )
        metrics["open_alert_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["open_alert_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM cross_site_trend_alerts "
            "WHERE alert_status = 'open' "
            "AND severity IN ('high', 'critical')",
            database_path=db_path,
        )
        metrics["high_or_critical_open_alert_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["high_or_critical_open_alert_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM cross_site_trend_alerts "
            "WHERE alert_status = 'open' "
            "AND julianday('now') - julianday(created_at) > 14",
            database_path=db_path,
        )
        metrics["stale_open_alert_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["stale_open_alert_count"] = 0

    # --- Lifecycle health ---
    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM cross_site_trend_alerts "
            "WHERE alert_type = 'needs_reparse'",
            database_path=db_path,
        )
        metrics["needs_reparse_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["needs_reparse_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM cross_site_trend_alerts "
            "WHERE alert_type = 'needs_manual_review'",
            database_path=db_path,
        )
        metrics["needs_manual_review_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["needs_manual_review_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM candidate_review_queue "
            "WHERE review_status = 'archive_candidate'",
            database_path=db_path,
        )
        metrics["archive_candidate_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["archive_candidate_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt "
            "FROM cross_site_lifecycle_health_snapshots "
            "WHERE lifecycle_health_label = 'attention_required'",
            database_path=db_path,
        )
        metrics["lifecycle_attention_required_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["lifecycle_attention_required_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt "
            "FROM cross_site_lifecycle_health_snapshots "
            "WHERE lifecycle_health_label = 'needs_review'",
            database_path=db_path,
        )
        metrics["lifecycle_needs_review_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["lifecycle_needs_review_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt "
            "FROM cross_site_lifecycle_health_snapshots "
            "WHERE lifecycle_health_label = 'degraded'",
            database_path=db_path,
        )
        metrics["lifecycle_degraded_trend_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["lifecycle_degraded_trend_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt "
            "FROM cross_site_lifecycle_health_snapshots "
            "WHERE lifecycle_gap_count > 0",
            database_path=db_path,
        )
        metrics["lifecycle_gap_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["lifecycle_gap_count"] = 0

    # --- Retrieval ---
    try:
        if table_exists("fixture_capture_queue", database_path=db_path):
            rows = execute_query(
                "SELECT COUNT(*) AS cnt FROM fixture_capture_queue "
                "WHERE status = 'pending'",
                database_path=db_path,
            )
            metrics["retrieval_pending_capture_count"] = _safe_int(
                dict(rows[0]).get("cnt") if rows else 0
            )
        else:
            metrics["retrieval_pending_capture_count"] = 0
    except Exception:
        metrics["retrieval_pending_capture_count"] = 0

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt "
            "FROM cross_site_lifecycle_health_snapshots "
            "WHERE recommended_review_action IS NOT NULL "
            "AND recommended_review_action != ''",
            database_path=db_path,
        )
        metrics["retrieval_health_issue_count"] = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        metrics["retrieval_health_issue_count"] = 0

    # --- Review priorities ---
    try:
        from marketsentry.operations_digest import (
            rank_operations_review_priorities,
        )

        priorities = rank_operations_review_priorities(db_path)
        metrics["top_priority_count"] = len(priorities)
        metrics["immediate_review_count"] = sum(
            1 for p in priorities if p.priority_label == "immediate_review"
        )
        metrics["high_review_count"] = sum(
            1 for p in priorities if p.priority_label == "high_review"
        )
    except Exception:
        metrics["top_priority_count"] = 0
        metrics["immediate_review_count"] = 0
        metrics["high_review_count"] = 0

    # --- Next actions ---
    try:
        from marketsentry.operations_digest import (
            build_operations_digest,
        )

        digest = build_operations_digest(db_path)
        metrics["next_action_count"] = len(digest.next_actions)
    except Exception:
        metrics["next_action_count"] = 0

    return metrics


# ---------------------------------------------------------------------------
# Snapshot CRUD
# ---------------------------------------------------------------------------

_SNAPSHOT_COLUMNS = [
    "digest_snapshot_id",
    "captured_at",
    "candidate_count",
    "pending_user_decision_count",
    "strong_review_count",
    "reject_location_noise_count",
    "watched_property_count",
    "active_watched_count",
    "high_priority_watched_count",
    "gas_evidence_count",
    "garage_evidence_count",
    "county_reset_applied_count",
    "high_churn_count",
    "high_effective_dom_delta_count",
    "cross_site_observed_property_count",
    "low_cross_site_confidence_count",
    "high_discrepancy_severity_count",
    "open_alert_count",
    "high_or_critical_open_alert_count",
    "stale_open_alert_count",
    "needs_reparse_count",
    "needs_manual_review_count",
    "archive_candidate_count",
    "lifecycle_attention_required_count",
    "lifecycle_needs_review_count",
    "lifecycle_degraded_trend_count",
    "lifecycle_gap_count",
    "retrieval_pending_capture_count",
    "retrieval_health_issue_count",
    "top_priority_count",
    "immediate_review_count",
    "high_review_count",
    "next_action_count",
    "digest_score",
    "digest_status_label",
    "notes",
    "created_at",
]


def _row_to_snapshot(row: Any) -> OperationsDigestSnapshot:
    """Convert a database row to an OperationsDigestSnapshot."""
    d = _row_to_dict(row)
    if not d:
        return OperationsDigestSnapshot()
    return OperationsDigestSnapshot(
        digest_snapshot_id=_safe_int(d.get("digest_snapshot_id")),
        captured_at=str(d.get("captured_at", "")),
        candidate_count=_safe_int(d.get("candidate_count")),
        pending_user_decision_count=_safe_int(
            d.get("pending_user_decision_count")
        ),
        strong_review_count=_safe_int(d.get("strong_review_count")),
        reject_location_noise_count=_safe_int(
            d.get("reject_location_noise_count")
        ),
        watched_property_count=_safe_int(d.get("watched_property_count")),
        active_watched_count=_safe_int(d.get("active_watched_count")),
        high_priority_watched_count=_safe_int(
            d.get("high_priority_watched_count")
        ),
        gas_evidence_count=_safe_int(d.get("gas_evidence_count")),
        garage_evidence_count=_safe_int(d.get("garage_evidence_count")),
        county_reset_applied_count=_safe_int(
            d.get("county_reset_applied_count")
        ),
        high_churn_count=_safe_int(d.get("high_churn_count")),
        high_effective_dom_delta_count=_safe_int(
            d.get("high_effective_dom_delta_count")
        ),
        cross_site_observed_property_count=_safe_int(
            d.get("cross_site_observed_property_count")
        ),
        low_cross_site_confidence_count=_safe_int(
            d.get("low_cross_site_confidence_count")
        ),
        high_discrepancy_severity_count=_safe_int(
            d.get("high_discrepancy_severity_count")
        ),
        open_alert_count=_safe_int(d.get("open_alert_count")),
        high_or_critical_open_alert_count=_safe_int(
            d.get("high_or_critical_open_alert_count")
        ),
        stale_open_alert_count=_safe_int(d.get("stale_open_alert_count")),
        needs_reparse_count=_safe_int(d.get("needs_reparse_count")),
        needs_manual_review_count=_safe_int(
            d.get("needs_manual_review_count")
        ),
        archive_candidate_count=_safe_int(d.get("archive_candidate_count")),
        lifecycle_attention_required_count=_safe_int(
            d.get("lifecycle_attention_required_count")
        ),
        lifecycle_needs_review_count=_safe_int(
            d.get("lifecycle_needs_review_count")
        ),
        lifecycle_degraded_trend_count=_safe_int(
            d.get("lifecycle_degraded_trend_count")
        ),
        lifecycle_gap_count=_safe_int(d.get("lifecycle_gap_count")),
        retrieval_pending_capture_count=_safe_int(
            d.get("retrieval_pending_capture_count")
        ),
        retrieval_health_issue_count=_safe_int(
            d.get("retrieval_health_issue_count")
        ),
        top_priority_count=_safe_int(d.get("top_priority_count")),
        immediate_review_count=_safe_int(d.get("immediate_review_count")),
        high_review_count=_safe_int(d.get("high_review_count")),
        next_action_count=_safe_int(d.get("next_action_count")),
        digest_score=_safe_int(d.get("digest_score", 100)),
        digest_status_label=str(d.get("digest_status_label", "clear")),
        notes=str(d.get("notes") or ""),
        created_at=str(d.get("created_at", "")),
    )


def get_latest_operations_digest_snapshot(
    db_path: Optional[str] = None,
) -> Optional[OperationsDigestSnapshot]:
    """Retrieve the most recent digest snapshot.

    Args:
        db_path: Database path.

    Returns:
        OperationsDigestSnapshot or None if no snapshots exist.
    """
    try:
        rows = execute_query(
            "SELECT * FROM operations_digest_snapshots "
            "ORDER BY captured_at DESC LIMIT 1",
            database_path=db_path,
        )
        if rows:
            return _row_to_snapshot(rows[0])
    except Exception:
        pass
    return None


def get_previous_operations_digest_snapshot(
    db_path: Optional[str] = None,
) -> Optional[OperationsDigestSnapshot]:
    """Retrieve the second-most-recent digest snapshot.

    Args:
        db_path: Database path.

    Returns:
        OperationsDigestSnapshot or None if fewer than 2 snapshots exist.
    """
    try:
        rows = execute_query(
            "SELECT * FROM operations_digest_snapshots "
            "ORDER BY captured_at DESC LIMIT 1 OFFSET 1",
            database_path=db_path,
        )
        if rows:
            return _row_to_snapshot(rows[0])
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Material change detection
# ---------------------------------------------------------------------------

_MATERIAL_CHANGE_FIELDS = [
    ("candidate_count", "candidate backlog changed"),
    ("active_watched_count", "active watched count changed"),
    ("high_or_critical_open_alert_count", "high/critical alerts changed"),
    (
        "lifecycle_attention_required_count",
        "lifecycle attention_required changed",
    ),
    ("lifecycle_needs_review_count", "lifecycle needs_review changed"),
    ("retrieval_health_issue_count", "retrieval health issue count changed"),
    ("top_priority_count", "top_priority_count changed"),
]


def _detect_material_changes(
    current: Dict[str, int],
    previous: Optional[OperationsDigestSnapshot],
    current_score: int,
    current_label: str,
) -> List[str]:
    """Detect material changes between current metrics and previous snapshot.

    Args:
        current: Current metrics dictionary.
        previous: Previous snapshot (may be None).
        current_score: Current digest score.
        current_label: Current digest status label.

    Returns:
        List of change descriptions.  Empty if no material changes.
    """
    if previous is None:
        return ["first snapshot"]

    changes: List[str] = []

    for field, desc in _MATERIAL_CHANGE_FIELDS:
        prev_val = getattr(previous, field, 0)
        curr_val = current.get(field, 0)
        if curr_val != prev_val:
            changes.append(desc)

    if abs(current_score - previous.digest_score) >= 5:
        changes.append(
            f"digest_score changed by "
            f"{current_score - previous.digest_score}"
        )

    if current_label != previous.digest_status_label:
        changes.append(
            f"digest_status_label changed from "
            f"{previous.digest_status_label} to {current_label}"
        )

    return changes


# ---------------------------------------------------------------------------
# Snapshot creation
# ---------------------------------------------------------------------------

def create_operations_digest_snapshot(
    db_path: Optional[str] = None,
    force: bool = False,
) -> OperationsDigestSnapshotRunResult:
    """Create a new digest snapshot if material changes are detected.

    Args:
        db_path: Database path.
        force: Create snapshot even without material changes.

    Returns:
        OperationsDigestSnapshotRunResult with creation status.
    """
    result = OperationsDigestSnapshotRunResult()

    # Calculate current metrics
    metrics = calculate_operations_digest_snapshot_metrics(db_path)
    score = _calculate_digest_score(metrics)
    label = _digest_status_label(score)

    result.digest_score = score
    result.digest_status_label = label
    result.key_counts = dict(metrics)

    # Get previous snapshot for comparison
    previous = get_latest_operations_digest_snapshot(db_path)

    # Check for same-day snapshot
    if previous and not force:
        prev_date = previous.captured_at[:10] if previous.captured_at else ""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if prev_date == today:
            # Same day - check for material changes
            changes = _detect_material_changes(
                metrics, previous, score, label
            )
            if not changes:
                result.snapshot_skipped = True
                result.skip_reason = (
                    "Same-day snapshot with no material changes detected"
                )
                return result

    # Detect material changes for reporting
    changes = _detect_material_changes(metrics, previous, score, label)
    if not changes and not force:
        result.snapshot_skipped = True
        result.skip_reason = "No material changes detected"
        return result

    result.material_changes = changes if changes else ["forced snapshot"]

    # Insert snapshot
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    insert_cols = [
        "captured_at",
        "candidate_count",
        "pending_user_decision_count",
        "strong_review_count",
        "reject_location_noise_count",
        "watched_property_count",
        "active_watched_count",
        "high_priority_watched_count",
        "gas_evidence_count",
        "garage_evidence_count",
        "county_reset_applied_count",
        "high_churn_count",
        "high_effective_dom_delta_count",
        "cross_site_observed_property_count",
        "low_cross_site_confidence_count",
        "high_discrepancy_severity_count",
        "open_alert_count",
        "high_or_critical_open_alert_count",
        "stale_open_alert_count",
        "needs_reparse_count",
        "needs_manual_review_count",
        "archive_candidate_count",
        "lifecycle_attention_required_count",
        "lifecycle_needs_review_count",
        "lifecycle_degraded_trend_count",
        "lifecycle_gap_count",
        "retrieval_pending_capture_count",
        "retrieval_health_issue_count",
        "top_priority_count",
        "immediate_review_count",
        "high_review_count",
        "next_action_count",
        "digest_score",
        "digest_status_label",
        "notes",
    ]
    placeholders = ", ".join(["?"] * len(insert_cols))
    col_names = ", ".join(insert_cols)

    notes_text = "; ".join(result.material_changes)
    values = [
        now,
        metrics.get("candidate_count", 0),
        metrics.get("pending_user_decision_count", 0),
        metrics.get("strong_review_count", 0),
        metrics.get("reject_location_noise_count", 0),
        metrics.get("watched_property_count", 0),
        metrics.get("active_watched_count", 0),
        metrics.get("high_priority_watched_count", 0),
        metrics.get("gas_evidence_count", 0),
        metrics.get("garage_evidence_count", 0),
        metrics.get("county_reset_applied_count", 0),
        metrics.get("high_churn_count", 0),
        metrics.get("high_effective_dom_delta_count", 0),
        metrics.get("cross_site_observed_property_count", 0),
        metrics.get("low_cross_site_confidence_count", 0),
        metrics.get("high_discrepancy_severity_count", 0),
        metrics.get("open_alert_count", 0),
        metrics.get("high_or_critical_open_alert_count", 0),
        metrics.get("stale_open_alert_count", 0),
        metrics.get("needs_reparse_count", 0),
        metrics.get("needs_manual_review_count", 0),
        metrics.get("archive_candidate_count", 0),
        metrics.get("lifecycle_attention_required_count", 0),
        metrics.get("lifecycle_needs_review_count", 0),
        metrics.get("lifecycle_degraded_trend_count", 0),
        metrics.get("lifecycle_gap_count", 0),
        metrics.get("retrieval_pending_capture_count", 0),
        metrics.get("retrieval_health_issue_count", 0),
        metrics.get("top_priority_count", 0),
        metrics.get("immediate_review_count", 0),
        metrics.get("high_review_count", 0),
        metrics.get("next_action_count", 0),
        score,
        label,
        notes_text,
    ]

    conn = get_connection(database_path=db_path)
    try:
        cursor = conn.execute(
            f"INSERT INTO operations_digest_snapshots "
            f"({col_names}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
        result.digest_snapshot_id = cursor.lastrowid or 0
        result.snapshot_created = True
    except Exception as exc:
        conn.rollback()
        result.warnings.append(f"Snapshot insert failed: {exc}")
        logger.error("Snapshot insert failed: %s", exc)
    finally:
        conn.close()

    return result


# ---------------------------------------------------------------------------
# Trend calculation
# ---------------------------------------------------------------------------

_TREND_METRICS = [
    "candidate_count",
    "pending_user_decision_count",
    "active_watched_count",
    "high_or_critical_open_alert_count",
    "stale_open_alert_count",
    "lifecycle_attention_required_count",
    "lifecycle_needs_review_count",
    "lifecycle_gap_count",
    "retrieval_health_issue_count",
    "top_priority_count",
    "digest_score",
]


def calculate_operations_digest_trend_change(
    current: OperationsDigestSnapshot,
    previous: OperationsDigestSnapshot,
) -> List[OperationsDigestTrendChange]:
    """Calculate trend changes between two snapshots.

    Args:
        current: The more recent snapshot.
        previous: The older snapshot.

    Returns:
        List of OperationsDigestTrendChange for each tracked metric.
    """
    changes: List[OperationsDigestTrendChange] = []

    for metric in _TREND_METRICS:
        curr_val = getattr(current, metric, 0)
        prev_val = getattr(previous, metric, 0)
        delta = curr_val - prev_val

        # For digest_score, higher is better (improved)
        # For all other metrics, lower is better (improved)
        if metric == "digest_score":
            if delta > 0:
                direction = "improved"
            elif delta < 0:
                direction = "degraded"
            else:
                direction = "stable"
        else:
            if delta < 0:
                direction = "improved"
            elif delta > 0:
                direction = "degraded"
            else:
                direction = "stable"

        changes.append(
            OperationsDigestTrendChange(
                metric_name=metric,
                current_value=curr_val,
                previous_value=prev_val,
                delta=delta,
                trend_direction=direction,
            )
        )

    return changes


def _overall_trend_direction(
    changes: List[OperationsDigestTrendChange],
) -> str:
    """Determine overall trend direction from individual changes.

    Args:
        changes: List of trend changes.

    Returns:
        One of: improved, degraded, stable, new.
    """
    if not changes:
        return "new"
    improved = sum(1 for c in changes if c.trend_direction == "improved")
    degraded = sum(1 for c in changes if c.trend_direction == "degraded")
    if improved > degraded:
        return "improved"
    elif degraded > improved:
        return "degraded"
    return "stable"


# ---------------------------------------------------------------------------
# History summary
# ---------------------------------------------------------------------------

def summarize_operations_digest_history(
    db_path: Optional[str] = None,
) -> OperationsDigestHistorySummary:
    """Build a summary of digest snapshot history.

    Args:
        db_path: Database path.

    Returns:
        OperationsDigestHistorySummary with snapshot counts, latest/previous
        scores, trend direction, and recommended next actions.
    """
    summary = OperationsDigestHistorySummary()

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM operations_digest_snapshots",
            database_path=db_path,
        )
        summary.snapshot_count = _safe_int(
            dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        summary.snapshot_count = 0

    latest = get_latest_operations_digest_snapshot(db_path)
    if latest and latest.digest_snapshot_id:
        summary.latest_digest_score = latest.digest_score
        summary.latest_digest_status = latest.digest_status_label
    else:
        summary.trend_direction = "new"
        return summary

    previous = get_previous_operations_digest_snapshot(db_path)
    if previous and previous.digest_snapshot_id:
        summary.previous_digest_score = previous.digest_score
        summary.previous_digest_status = previous.digest_status_label

        changes = calculate_operations_digest_trend_change(latest, previous)
        summary.trend_changes = changes
        summary.trend_direction = _overall_trend_direction(changes)
    else:
        summary.trend_direction = "new"

    # Generate recommended next actions
    actions: List[str] = []
    if latest.pending_user_decision_count > 0:
        actions.append(
            "Review pending candidate decisions with "
            "marketsentry candidates-pending"
        )
    if latest.high_or_critical_open_alert_count > 0:
        actions.append(
            "Triage high/critical alerts with "
            "marketsentry export-cross-site-alert-triage"
        )
    if latest.stale_open_alert_count > 0:
        actions.append(
            "Review stale alerts with "
            "marketsentry export-cross-site-alert-lifecycle-report"
        )
    if latest.lifecycle_attention_required_count > 0:
        actions.append(
            "Address lifecycle attention-required items with "
            "marketsentry export-lifecycle-health-report"
        )
    if latest.retrieval_health_issue_count > 0:
        actions.append(
            "Investigate retrieval health issues with "
            "marketsentry export-operations-digest"
        )
    if not actions:
        actions.append("No immediate actions required. Operations are clear.")

    summary.recommended_next_actions = actions

    return summary


# ---------------------------------------------------------------------------
# Comparison report export
# ---------------------------------------------------------------------------

COMPARISON_CSV_FIELDNAMES = [
    "current_snapshot_id",
    "current_captured_at",
    "previous_snapshot_id",
    "previous_captured_at",
    "digest_score_current",
    "digest_score_previous",
    "digest_score_delta",
    "digest_status_current",
    "digest_status_previous",
    "digest_status_changed",
    "candidate_count_current",
    "candidate_count_previous",
    "candidate_count_delta",
    "pending_user_decision_current",
    "pending_user_decision_previous",
    "pending_user_decision_delta",
    "active_watched_current",
    "active_watched_previous",
    "active_watched_delta",
    "high_or_critical_open_alerts_current",
    "high_or_critical_open_alerts_previous",
    "high_or_critical_open_alerts_delta",
    "lifecycle_attention_required_current",
    "lifecycle_attention_required_previous",
    "lifecycle_attention_required_delta",
    "lifecycle_needs_review_current",
    "lifecycle_needs_review_previous",
    "lifecycle_needs_review_delta",
    "retrieval_health_issues_current",
    "retrieval_health_issues_previous",
    "retrieval_health_issues_delta",
    "top_priority_count_current",
    "top_priority_count_previous",
    "top_priority_count_delta",
    "trend_direction",
    "trend_summary",
    "recommended_review_action",
]


def _build_comparison_row(
    current: OperationsDigestSnapshot,
    previous: Optional[OperationsDigestSnapshot],
    trend_dir: str,
) -> OperationsDigestComparisonReportRow:
    """Build a single comparison report row.

    Args:
        current: Current snapshot.
        previous: Previous snapshot (may be None).
        trend_dir: Overall trend direction.

    Returns:
        OperationsDigestComparisonReportRow.
    """
    prev = previous or OperationsDigestSnapshot()
    has_prev = previous is not None and previous.digest_snapshot_id > 0

    # Build trend summary
    summary_parts: List[str] = []
    if current.digest_score != prev.digest_score and has_prev:
        delta = current.digest_score - prev.digest_score
        direction_word = "up" if delta > 0 else "down"
        summary_parts.append(
            f"Digest score {direction_word} {abs(delta)} points"
        )
    if current.pending_user_decision_count != (
        prev.pending_user_decision_count
    ) and has_prev:
        d = (
            current.pending_user_decision_count
            - prev.pending_user_decision_count
        )
        summary_parts.append(f"Pending decisions delta: {d:+d}")
    if not summary_parts:
        summary_parts.append("No significant changes")

    # Recommended review action
    if trend_dir == "degraded":
        action = "Review backlog increases and address open items"
    elif trend_dir == "improved":
        action = "Continue current review cadence"
    elif trend_dir == "new":
        action = "Establish baseline review cadence"
    else:
        action = "Maintain current operations"

    return OperationsDigestComparisonReportRow(
        current_snapshot_id=current.digest_snapshot_id,
        current_captured_at=current.captured_at,
        previous_snapshot_id=prev.digest_snapshot_id if has_prev else 0,
        previous_captured_at=prev.captured_at if has_prev else "",
        digest_score_current=current.digest_score,
        digest_score_previous=prev.digest_score if has_prev else 0,
        digest_score_delta=(
            current.digest_score - prev.digest_score if has_prev else 0
        ),
        digest_status_current=current.digest_status_label,
        digest_status_previous=(
            prev.digest_status_label if has_prev else ""
        ),
        digest_status_changed=(
            current.digest_status_label != prev.digest_status_label
            if has_prev
            else False
        ),
        candidate_count_current=current.candidate_count,
        candidate_count_previous=(
            prev.candidate_count if has_prev else 0
        ),
        candidate_count_delta=(
            current.candidate_count - prev.candidate_count
            if has_prev
            else 0
        ),
        pending_user_decision_current=(
            current.pending_user_decision_count
        ),
        pending_user_decision_previous=(
            prev.pending_user_decision_count if has_prev else 0
        ),
        pending_user_decision_delta=(
            current.pending_user_decision_count
            - prev.pending_user_decision_count
            if has_prev
            else 0
        ),
        active_watched_current=current.active_watched_count,
        active_watched_previous=(
            prev.active_watched_count if has_prev else 0
        ),
        active_watched_delta=(
            current.active_watched_count - prev.active_watched_count
            if has_prev
            else 0
        ),
        high_or_critical_open_alerts_current=(
            current.high_or_critical_open_alert_count
        ),
        high_or_critical_open_alerts_previous=(
            prev.high_or_critical_open_alert_count if has_prev else 0
        ),
        high_or_critical_open_alerts_delta=(
            current.high_or_critical_open_alert_count
            - prev.high_or_critical_open_alert_count
            if has_prev
            else 0
        ),
        lifecycle_attention_required_current=(
            current.lifecycle_attention_required_count
        ),
        lifecycle_attention_required_previous=(
            prev.lifecycle_attention_required_count if has_prev else 0
        ),
        lifecycle_attention_required_delta=(
            current.lifecycle_attention_required_count
            - prev.lifecycle_attention_required_count
            if has_prev
            else 0
        ),
        lifecycle_needs_review_current=(
            current.lifecycle_needs_review_count
        ),
        lifecycle_needs_review_previous=(
            prev.lifecycle_needs_review_count if has_prev else 0
        ),
        lifecycle_needs_review_delta=(
            current.lifecycle_needs_review_count
            - prev.lifecycle_needs_review_count
            if has_prev
            else 0
        ),
        retrieval_health_issues_current=(
            current.retrieval_health_issue_count
        ),
        retrieval_health_issues_previous=(
            prev.retrieval_health_issue_count if has_prev else 0
        ),
        retrieval_health_issues_delta=(
            current.retrieval_health_issue_count
            - prev.retrieval_health_issue_count
            if has_prev
            else 0
        ),
        top_priority_count_current=current.top_priority_count,
        top_priority_count_previous=(
            prev.top_priority_count if has_prev else 0
        ),
        top_priority_count_delta=(
            current.top_priority_count - prev.top_priority_count
            if has_prev
            else 0
        ),
        trend_direction=trend_dir,
        trend_summary="; ".join(summary_parts),
        recommended_review_action=action,
    )


def export_operations_digest_comparison_report(
    db_path: Optional[str] = None,
    output_dir: str = "data/exports",
    fmt: str = "csv",
) -> List[str]:
    """Export a snapshot-over-snapshot comparison report.

    Args:
        db_path: Database path.
        output_dir: Directory to write export files.
        fmt: Export format - 'csv', 'md', or 'both'.

    Returns:
        List of export file paths.
    """
    current = get_latest_operations_digest_snapshot(db_path)
    previous = get_previous_operations_digest_snapshot(db_path)

    if not current or not current.digest_snapshot_id:
        logger.warning("No digest snapshots found for comparison report")
        return []

    # Calculate trend
    if previous and previous.digest_snapshot_id:
        changes = calculate_operations_digest_trend_change(
            current, previous
        )
        trend_dir = _overall_trend_direction(changes)
    else:
        trend_dir = "new"

    row = _build_comparison_row(current, previous, trend_dir)
    row_dict = row.model_dump()

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: List[str] = []

    if fmt in ("csv", "both"):
        csv_path = os.path.join(
            output_dir,
            f"operations_digest_comparison_{ts}.csv",
        )
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COMPARISON_CSV_FIELDNAMES)
            writer.writeheader()
            writer.writerow(row_dict)
        paths.append(csv_path)

    if fmt in ("md", "both"):
        md_path = os.path.join(
            output_dir,
            f"operations_digest_comparison_{ts}.md",
        )
        lines = [
            "# Operations Digest Comparison Report",
            "",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "",
            "## Snapshot Comparison",
            "",
            f"| Metric | Current | Previous | Delta |",
            f"| ------- | ------- | ------- | ------- |",
            f"| Digest Score | {row.digest_score_current} | "
            f"{row.digest_score_previous} | {row.digest_score_delta:+d} |",
            f"| Digest Status | {row.digest_status_current} | "
            f"{row.digest_status_previous} | "
            f"{'changed' if row.digest_status_changed else 'unchanged'} |",
            f"| Candidate Count | {row.candidate_count_current} | "
            f"{row.candidate_count_previous} | "
            f"{row.candidate_count_delta:+d} |",
            f"| Pending Decisions | "
            f"{row.pending_user_decision_current} | "
            f"{row.pending_user_decision_previous} | "
            f"{row.pending_user_decision_delta:+d} |",
            f"| Active Watched | {row.active_watched_current} | "
            f"{row.active_watched_previous} | "
            f"{row.active_watched_delta:+d} |",
            f"| High/Critical Alerts | "
            f"{row.high_or_critical_open_alerts_current} | "
            f"{row.high_or_critical_open_alerts_previous} | "
            f"{row.high_or_critical_open_alerts_delta:+d} |",
            f"| Lifecycle Attention Required | "
            f"{row.lifecycle_attention_required_current} | "
            f"{row.lifecycle_attention_required_previous} | "
            f"{row.lifecycle_attention_required_delta:+d} |",
            f"| Lifecycle Needs Review | "
            f"{row.lifecycle_needs_review_current} | "
            f"{row.lifecycle_needs_review_previous} | "
            f"{row.lifecycle_needs_review_delta:+d} |",
            f"| Retrieval Health Issues | "
            f"{row.retrieval_health_issues_current} | "
            f"{row.retrieval_health_issues_previous} | "
            f"{row.retrieval_health_issues_delta:+d} |",
            f"| Top Priority Count | "
            f"{row.top_priority_count_current} | "
            f"{row.top_priority_count_previous} | "
            f"{row.top_priority_count_delta:+d} |",
            "",
            "## Trend",
            "",
            f"- Direction: {row.trend_direction}",
            f"- Summary: {row.trend_summary}",
            f"- Recommended: {row.recommended_review_action}",
            "",
            "---",
            "",
            "Read-only comparison report. No mutations performed.",
        ]
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        paths.append(md_path)

    return paths
