"""Alert Lifecycle Audit Trail and Operations Summary.

Consolidates alert lifecycle activity from triage, archive, and expiration
workflows into a unified read-only audit trail. Does not mutate alert state,
watchlist status, or Redfin source-of-truth fields.

Milestone 34.
"""

import csv
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from marketsentry.models import (
    CrossSiteAlertLifecycleEvent,
    CrossSiteAlertLifecyclePropertySummary,
    CrossSiteAlertLifecycleReportRow,
    CrossSiteAlertLifecycleRunResult,
    CrossSiteAlertLifecycleSummary,
)

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row or dict to a plain dict."""
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except (TypeError, ValueError):
        return {}

# Default gap thresholds (days)
DEFAULT_OPEN_STALE_DAYS = 7
DEFAULT_ACK_STALE_DAYS = 14
DEFAULT_RESOLVED_ARCHIVE_DAYS = 30
DEFAULT_REOPENED_STALE_DAYS = 7

LIFECYCLE_CSV_FIELDNAMES = [
    "property_id",
    "candidate_id",
    "address",
    "city",
    "zip",
    "alert_id",
    "alert_type",
    "severity",
    "current_status",
    "event_count",
    "first_event_at",
    "latest_event_at",
    "latest_event_type",
    "lifecycle_summary_label",
    "lifecycle_gap_count",
    "gap_categories",
    "needs_reparse_count",
    "needs_manual_review_count",
    "no_archive_count",
    "recommended_review_action",
]

# Lifecycle summary labels
_LABEL_NO_ALERTS = "no_alerts"
_LABEL_ACTIVE = "active_alerts"
_LABEL_UNDER_REVIEW = "under_review"
_LABEL_MOSTLY_RESOLVED = "mostly_resolved"
_LABEL_ARCHIVED_HISTORY = "archived_history"
_LABEL_NEEDS_ATTENTION = "needs_attention"


def _generate_event_id(
    alert_id: int,
    event_type: str,
    event_at: str,
    source_ref: str,
) -> str:
    """Generate a deterministic event ID from key fields."""
    raw = f"{alert_id}:{event_type}:{event_at}:{source_ref}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _detect_source_workflow(triage_export_id: str) -> str:
    """Determine the source workflow from the triage_export_id prefix."""
    if not triage_export_id:
        return "unknown"
    if triage_export_id.startswith("triage_"):
        return "triage"
    if triage_export_id.startswith("archive_"):
        return "archive_policy"
    if triage_export_id.startswith("expiration_"):
        return "expiration_policy"
    return "unknown"


def _parse_notes_markers(notes: Optional[str]) -> Dict[str, int]:
    """Count note markers in alert notes text."""
    counts: Dict[str, int] = {
        "no_archive": 0,
        "needs_reparse": 0,
        "needs_manual_review": 0,
    }
    if not notes:
        return counts
    lower = notes.lower()
    counts["no_archive"] = lower.count("[no_archive]")
    counts["needs_reparse"] = lower.count("[triage:needs_reparse]")
    counts["needs_manual_review"] = lower.count(
        "[triage:needs_manual_review]"
    )
    return counts


def load_alert_lifecycle_events(
    database_path: Optional[str] = None,
    alert_id: Optional[int] = None,
    property_id: Optional[int] = None,
) -> List[CrossSiteAlertLifecycleEvent]:
    """Load and normalize lifecycle events from database tables.

    Combines alert creation events from cross_site_trend_alerts and
    action events from cross_site_alert_triage_actions into a unified
    chronological event stream.

    Args:
        database_path: Path to the SQLite database.
        alert_id: Optional filter for a specific alert.
        property_id: Optional filter for a specific property.

    Returns:
        List of normalized lifecycle events sorted by event_at.
    """
    from marketsentry.database import execute_query, table_exists

    events: List[CrossSiteAlertLifecycleEvent] = []

    # Load alert creation events
    if table_exists("cross_site_trend_alerts", database_path):
        query = (
            "SELECT alert_id, property_id, candidate_id, "
            "alert_type, severity, alert_status, created_at, notes "
            "FROM cross_site_trend_alerts"
        )
        params: list = []
        conditions: list = []
        if alert_id is not None:
            conditions.append("alert_id = ?")
            params.append(alert_id)
        if property_id is not None:
            conditions.append("property_id = ?")
            params.append(property_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        try:
            rows = execute_query(query, tuple(params), database_path)
            for raw in rows:
                row = _row_to_dict(raw)
                ts = row.get("created_at", "") or ""
                eid = _generate_event_id(
                    row["alert_id"], "alert_created", ts, "trend_alerts",
                )
                events.append(
                    CrossSiteAlertLifecycleEvent(
                        event_id=eid,
                        alert_id=row["alert_id"],
                        property_id=row.get("property_id", 0),
                        candidate_id=row.get("candidate_id"),
                        event_type="alert_created",
                        previous_status=None,
                        new_status=row.get("alert_status", "open"),
                        action="create",
                        source_workflow="alert_generation",
                        event_notes=row.get("notes"),
                        event_at=ts,
                        source_table="cross_site_trend_alerts",
                        source_reference=str(row["alert_id"]),
                    )
                )
        except Exception as e:
            logger.warning(f"Error loading alert creation events: {e}")

    # Load triage/archive/expiration action events
    if table_exists("cross_site_alert_triage_actions", database_path):
        query = (
            "SELECT triage_action_id, triage_export_id, alert_id, "
            "property_id, action, previous_status, new_status, "
            "triage_notes, applied_at "
            "FROM cross_site_alert_triage_actions"
        )
        params = []
        conditions = []
        if alert_id is not None:
            conditions.append("alert_id = ?")
            params.append(alert_id)
        if property_id is not None:
            conditions.append("property_id = ?")
            params.append(property_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        try:
            rows = execute_query(query, tuple(params), database_path)
            for raw in rows:
                row = _row_to_dict(raw)
                ts = row.get("applied_at", "") or ""
                export_id = row.get("triage_export_id", "") or ""
                source_wf = _detect_source_workflow(export_id)
                action_str = row.get("action", "") or ""
                event_type = _map_action_to_event_type(
                    action_str, source_wf,
                )
                eid = _generate_event_id(
                    row["alert_id"],
                    event_type,
                    ts,
                    str(row.get("triage_action_id", "")),
                )
                events.append(
                    CrossSiteAlertLifecycleEvent(
                        event_id=eid,
                        alert_id=row["alert_id"],
                        property_id=row.get("property_id", 0) or 0,
                        candidate_id=None,
                        event_type=event_type,
                        previous_status=row.get("previous_status"),
                        new_status=row.get("new_status"),
                        action=action_str,
                        source_workflow=source_wf,
                        event_notes=row.get("triage_notes"),
                        event_at=ts,
                        source_table="cross_site_alert_triage_actions",
                        source_reference=export_id,
                    )
                )
        except Exception as e:
            logger.warning(f"Error loading triage action events: {e}")

    # Sort chronologically
    events.sort(key=lambda e: e.event_at or "")
    return events


def _map_action_to_event_type(action: str, source_workflow: str) -> str:
    """Map a raw action string to a normalized event type."""
    action_lower = (action or "").lower().strip()
    mapping = {
        "acknowledge": "acknowledged",
        "resolve": "resolved",
        "archive": "archived",
        "reopen": "reopened",
        "no_archive": "no_archive_marked",
        "mark_no_archive": "no_archive_marked",
        "needs_reparse": "needs_reparse_marked",
        "needs_manual_review": "needs_manual_review_marked",
        "keep_open": "triage_applied",
        "keep_current": "triage_applied",
        "keep_resolved": "triage_applied",
        "approve_action": "expiration_approved",
    }
    mapped = mapping.get(action_lower)
    if mapped:
        return mapped

    # Prefix-based fallback
    if source_workflow == "archive_policy":
        return "archive_decision_applied"
    if source_workflow == "expiration_policy":
        return "expiration_approved"
    return "triage_applied"


def build_alert_lifecycle_for_alert(
    alert_id: int,
    database_path: Optional[str] = None,
) -> List[CrossSiteAlertLifecycleEvent]:
    """Build the complete lifecycle event stream for a single alert.

    Args:
        alert_id: The alert ID to retrieve events for.
        database_path: Path to the SQLite database.

    Returns:
        Chronologically ordered list of lifecycle events for the alert.
    """
    return load_alert_lifecycle_events(
        database_path=database_path,
        alert_id=alert_id,
    )


def summarize_alert_lifecycle_for_property(
    property_id: int,
    database_path: Optional[str] = None,
    open_stale_days: int = DEFAULT_OPEN_STALE_DAYS,
    ack_stale_days: int = DEFAULT_ACK_STALE_DAYS,
    resolved_archive_days: int = DEFAULT_RESOLVED_ARCHIVE_DAYS,
    reopened_stale_days: int = DEFAULT_REOPENED_STALE_DAYS,
) -> CrossSiteAlertLifecyclePropertySummary:
    """Build a lifecycle summary for a single property.

    Args:
        property_id: The property ID to summarize.
        database_path: Path to the SQLite database.
        open_stale_days: Days before an open alert is considered stale.
        ack_stale_days: Days before an acknowledged alert is stale.
        resolved_archive_days: Days before resolved alert is archive candidate.
        reopened_stale_days: Days before a reopened alert is stale.

    Returns:
        Property-level lifecycle summary with metrics and label.
    """
    from marketsentry.database import execute_query, table_exists

    summary = CrossSiteAlertLifecyclePropertySummary(
        property_id=property_id,
    )

    # Get property address info from watched_properties first, fallback to candidates
    try:
        rows = execute_query(
            "SELECT address, city, zip FROM watched_properties "
            "WHERE property_id = ? LIMIT 1",
            (property_id,),
            database_path,
        )
        if rows:
            r = _row_to_dict(rows[0])
            summary.address = r.get("address", "") or ""
            summary.city = r.get("city", "") or ""
            summary.zip_code = r.get("zip", "") or ""
        else:
            rows = execute_query(
                "SELECT address, city, zip FROM candidates "
                "WHERE property_id = ? LIMIT 1",
                (property_id,),
                database_path,
            )
            if rows:
                r = _row_to_dict(rows[0])
                summary.address = r.get("address", "") or ""
                summary.city = r.get("city", "") or ""
                summary.zip_code = r.get("zip", "") or ""
    except Exception:
        pass

    if not table_exists("cross_site_trend_alerts", database_path):
        return summary

    # Get alert counts by status
    try:
        raw_alerts = execute_query(
            "SELECT alert_id, alert_status, severity, created_at, notes "
            "FROM cross_site_trend_alerts WHERE property_id = ?",
            (property_id,),
            database_path,
        )
    except Exception:
        return summary

    if not raw_alerts:
        return summary

    alerts = [_row_to_dict(r) for r in raw_alerts]
    summary.total_alerts = len(alerts)
    now = datetime.now()

    for alert in alerts:
        status = (alert.get("alert_status") or "").lower()
        severity = (alert.get("severity") or "").lower()
        notes = alert.get("notes") or ""

        if status == "open":
            summary.open_alerts += 1
            if severity in ("high", "critical"):
                summary.unresolved_high_or_critical_count += 1
            # Track oldest open alert age
            created = alert.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created)
                    age = (now - dt).days
                    if (
                        summary.oldest_open_alert_age_days is None
                        or age > summary.oldest_open_alert_age_days
                    ):
                        summary.oldest_open_alert_age_days = age
                except (ValueError, TypeError):
                    pass
        elif status == "acknowledged":
            summary.acknowledged_alerts += 1
            if severity in ("high", "critical"):
                summary.unresolved_high_or_critical_count += 1
        elif status == "resolved":
            summary.resolved_alerts += 1
        elif status == "archived":
            summary.archived_alerts += 1

        # Parse note markers
        markers = _parse_notes_markers(notes)
        summary.no_archive_count += markers["no_archive"]
        summary.needs_reparse_count += markers["needs_reparse"]
        summary.needs_manual_review_count += markers["needs_manual_review"]

    # Load events for this property
    events = load_alert_lifecycle_events(
        database_path=database_path,
        property_id=property_id,
    )
    summary.total_lifecycle_events = len(events)

    # Count reopened events
    for ev in events:
        if ev.event_type == "reopened":
            summary.reopened_count += 1

    # Latest event timestamp
    if events:
        summary.latest_event_at = events[-1].event_at

    # Detect gaps
    gaps = detect_alert_lifecycle_gaps(
        database_path=database_path,
        property_id=property_id,
        open_stale_days=open_stale_days,
        ack_stale_days=ack_stale_days,
        resolved_archive_days=resolved_archive_days,
        reopened_stale_days=reopened_stale_days,
    )
    summary.lifecycle_gap_count = len(gaps)

    # Determine lifecycle label
    summary.lifecycle_summary_label = _compute_lifecycle_label(summary, gaps)

    return summary


def _compute_lifecycle_label(
    summary: CrossSiteAlertLifecyclePropertySummary,
    gaps: List[dict],
) -> str:
    """Compute a lifecycle summary label for a property."""
    if summary.total_alerts == 0:
        return _LABEL_NO_ALERTS

    if len(gaps) > 0 or summary.unresolved_high_or_critical_count > 0:
        return _LABEL_NEEDS_ATTENTION

    if summary.open_alerts > 0:
        return _LABEL_ACTIVE

    if summary.acknowledged_alerts > 0:
        return _LABEL_UNDER_REVIEW

    if summary.resolved_alerts > 0 and summary.archived_alerts == 0:
        return _LABEL_MOSTLY_RESOLVED

    if (
        summary.archived_alerts > 0
        and summary.open_alerts == 0
        and summary.acknowledged_alerts == 0
    ):
        return _LABEL_ARCHIVED_HISTORY

    return _LABEL_MOSTLY_RESOLVED


def summarize_alert_lifecycle_for_all_properties(
    database_path: Optional[str] = None,
    open_stale_days: int = DEFAULT_OPEN_STALE_DAYS,
    ack_stale_days: int = DEFAULT_ACK_STALE_DAYS,
    resolved_archive_days: int = DEFAULT_RESOLVED_ARCHIVE_DAYS,
    reopened_stale_days: int = DEFAULT_REOPENED_STALE_DAYS,
) -> CrossSiteAlertLifecycleSummary:
    """Build an aggregate lifecycle summary across all properties.

    Args:
        database_path: Path to the SQLite database.
        open_stale_days: Days before an open alert is considered stale.
        ack_stale_days: Days before an acknowledged alert is stale.
        resolved_archive_days: Days before resolved alert is archive candidate.
        reopened_stale_days: Days before a reopened alert is stale.

    Returns:
        Aggregate summary with per-property breakdowns.
    """
    from marketsentry.database import execute_query, table_exists

    result = CrossSiteAlertLifecycleSummary()

    if not table_exists("cross_site_trend_alerts", database_path):
        result.warnings.append(
            "cross_site_trend_alerts table does not exist."
        )
        return result

    # Get distinct property IDs with alerts
    try:
        raw_rows = execute_query(
            "SELECT DISTINCT property_id FROM cross_site_trend_alerts",
            database_path=database_path,
        )
    except Exception as e:
        result.warnings.append(f"Error loading property IDs: {e}")
        return result

    rows = [_row_to_dict(r) for r in raw_rows]
    property_ids = [r["property_id"] for r in rows if r.get("property_id")]

    for pid in property_ids:
        psummary = summarize_alert_lifecycle_for_property(
            property_id=pid,
            database_path=database_path,
            open_stale_days=open_stale_days,
            ack_stale_days=ack_stale_days,
            resolved_archive_days=resolved_archive_days,
            reopened_stale_days=reopened_stale_days,
        )
        if psummary.total_alerts > 0:
            result.property_summaries.append(psummary)
            result.total_alerts += psummary.total_alerts
            result.total_lifecycle_events += psummary.total_lifecycle_events
            result.open_alerts += psummary.open_alerts
            result.acknowledged_alerts += psummary.acknowledged_alerts
            result.resolved_alerts += psummary.resolved_alerts
            result.archived_alerts += psummary.archived_alerts
            result.total_gaps += psummary.lifecycle_gap_count
            result.needs_reparse_count += psummary.needs_reparse_count
            result.needs_manual_review_count += (
                psummary.needs_manual_review_count
            )

    result.total_properties_with_alerts = len(result.property_summaries)

    # Build recommended actions
    if result.open_alerts > 0:
        result.recommended_actions.append(
            f"Review {result.open_alerts} open alert(s) via triage workflow."
        )
    if result.total_gaps > 0:
        result.recommended_actions.append(
            f"Investigate {result.total_gaps} lifecycle gap(s) "
            f"across properties."
        )
    if result.needs_reparse_count > 0:
        result.recommended_actions.append(
            f"Re-parse fixtures for {result.needs_reparse_count} "
            f"needs_reparse marker(s)."
        )
    if result.needs_manual_review_count > 0:
        result.recommended_actions.append(
            f"Manual review needed for "
            f"{result.needs_manual_review_count} marker(s)."
        )

    return result


def detect_alert_lifecycle_gaps(
    database_path: Optional[str] = None,
    alert_id: Optional[int] = None,
    property_id: Optional[int] = None,
    open_stale_days: int = DEFAULT_OPEN_STALE_DAYS,
    ack_stale_days: int = DEFAULT_ACK_STALE_DAYS,
    resolved_archive_days: int = DEFAULT_RESOLVED_ARCHIVE_DAYS,
    reopened_stale_days: int = DEFAULT_REOPENED_STALE_DAYS,
) -> List[dict]:
    """Detect potential workflow gaps in alert lifecycles.

    Identifies alerts where expected follow-up actions have not occurred
    within configured thresholds. These are review aids only; the module
    does not auto-fix gaps.

    Args:
        database_path: Path to the SQLite database.
        alert_id: Optional filter for a specific alert.
        property_id: Optional filter for a specific property.
        open_stale_days: Days before an open alert without triage is flagged.
        ack_stale_days: Days before an acknowledged alert without resolution.
        resolved_archive_days: Days before resolved alert is archive candidate.
        reopened_stale_days: Days before a reopened alert is flagged.

    Returns:
        List of gap dicts with alert_id, gap_category, description, age_days.
    """
    from marketsentry.database import execute_query, table_exists

    gaps: List[dict] = []

    if not table_exists("cross_site_trend_alerts", database_path):
        return gaps

    # Build query
    query = (
        "SELECT alert_id, property_id, alert_status, severity, "
        "created_at, notes "
        "FROM cross_site_trend_alerts"
    )
    params: list = []
    conditions: list = []
    if alert_id is not None:
        conditions.append("alert_id = ?")
        params.append(alert_id)
    if property_id is not None:
        conditions.append("property_id = ?")
        params.append(property_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    try:
        raw_alerts = execute_query(query, tuple(params), database_path)
    except Exception:
        return gaps

    alerts = [_row_to_dict(r) for r in raw_alerts]
    now = datetime.now()

    # Load all triage actions for lookup
    triage_actions: Dict[int, List[dict]] = {}
    if table_exists("cross_site_alert_triage_actions", database_path):
        try:
            ta_query = (
                "SELECT alert_id, action, new_status, applied_at "
                "FROM cross_site_alert_triage_actions"
            )
            ta_params: list = []
            ta_conditions: list = []
            if alert_id is not None:
                ta_conditions.append("alert_id = ?")
                ta_params.append(alert_id)
            if property_id is not None:
                ta_conditions.append("property_id = ?")
                ta_params.append(property_id)
            if ta_conditions:
                ta_query += " WHERE " + " AND ".join(ta_conditions)
            ta_rows = execute_query(
                ta_query, tuple(ta_params), database_path,
            )
            for raw in ta_rows:
                row = _row_to_dict(raw)
                aid = row["alert_id"]
                if aid not in triage_actions:
                    triage_actions[aid] = []
                triage_actions[aid].append(row)
        except Exception:
            pass

    for alert in alerts:
        aid = alert["alert_id"]
        status = (alert.get("alert_status") or "").lower()
        created_at = alert.get("created_at", "")
        notes = alert.get("notes") or ""
        actions = triage_actions.get(aid, [])

        try:
            created_dt = datetime.fromisoformat(created_at) if created_at else None
        except (ValueError, TypeError):
            created_dt = None

        age_days = (now - created_dt).days if created_dt else None

        # Gap 1: Open alert older than threshold with no triage action
        if status == "open" and age_days is not None:
            if age_days >= open_stale_days and not actions:
                gaps.append({
                    "alert_id": aid,
                    "property_id": alert.get("property_id"),
                    "gap_category": "open_no_triage",
                    "description": (
                        f"Open alert aged {age_days}d with no triage action."
                    ),
                    "age_days": age_days,
                })

        # Gap 2: needs_reparse marker with no later resolved/archive
        if "[triage:needs_reparse]" in notes.lower():
            has_resolution = any(
                (a.get("new_status") or "").lower()
                in ("resolved", "archived")
                for a in actions
            )
            if not has_resolution:
                gaps.append({
                    "alert_id": aid,
                    "property_id": alert.get("property_id"),
                    "gap_category": "needs_reparse_unresolved",
                    "description": (
                        "Alert has needs_reparse marker "
                        "with no later resolution."
                    ),
                    "age_days": age_days,
                })

        # Gap 3: needs_manual_review with no later ack/resolved/archive
        if "[triage:needs_manual_review]" in notes.lower():
            has_followup = any(
                (a.get("new_status") or "").lower()
                in ("acknowledged", "resolved", "archived")
                for a in actions
            )
            if not has_followup:
                gaps.append({
                    "alert_id": aid,
                    "property_id": alert.get("property_id"),
                    "gap_category": "needs_manual_review_unresolved",
                    "description": (
                        "Alert has needs_manual_review marker "
                        "with no later follow-up."
                    ),
                    "age_days": age_days,
                })

        # Gap 4: Acknowledged older than threshold with no resolution
        if status == "acknowledged" and age_days is not None:
            if age_days >= ack_stale_days:
                has_resolution = any(
                    (a.get("new_status") or "").lower()
                    in ("resolved", "archived")
                    for a in actions
                )
                if not has_resolution:
                    gaps.append({
                        "alert_id": aid,
                        "property_id": alert.get("property_id"),
                        "gap_category": "acknowledged_stale",
                        "description": (
                            f"Acknowledged alert aged {age_days}d "
                            f"with no resolution."
                        ),
                        "age_days": age_days,
                    })

        # Gap 5: Resolved older than archive threshold, not archived
        if status == "resolved" and age_days is not None:
            if age_days >= resolved_archive_days:
                is_no_archive = "[no_archive]" in notes.lower()
                if not is_no_archive:
                    gaps.append({
                        "alert_id": aid,
                        "property_id": alert.get("property_id"),
                        "gap_category": "resolved_archive_candidate",
                        "description": (
                            f"Resolved alert aged {age_days}d, "
                            f"not archived or no_archive marked."
                        ),
                        "age_days": age_days,
                    })

        # Gap 6: Reopened alert still open beyond threshold
        if status == "open":
            was_reopened = any(
                (a.get("action") or "").lower() == "reopen"
                for a in actions
            )
            if was_reopened and age_days is not None:
                if age_days >= reopened_stale_days:
                    gaps.append({
                        "alert_id": aid,
                        "property_id": alert.get("property_id"),
                        "gap_category": "reopened_stale",
                        "description": (
                            f"Reopened alert still open after {age_days}d."
                        ),
                        "age_days": age_days,
                    })

    return gaps


def export_cross_site_alert_lifecycle_report(
    database_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    format: str = "csv",
    open_stale_days: int = DEFAULT_OPEN_STALE_DAYS,
    ack_stale_days: int = DEFAULT_ACK_STALE_DAYS,
    resolved_archive_days: int = DEFAULT_RESOLVED_ARCHIVE_DAYS,
    reopened_stale_days: int = DEFAULT_REOPENED_STALE_DAYS,
) -> CrossSiteAlertLifecycleRunResult:
    """Export a unified lifecycle audit report.

    Generates a CSV and/or Markdown report showing per-alert lifecycle
    metrics, gap counts, and recommended actions.

    Args:
        database_path: Path to the SQLite database.
        output_dir: Directory for output files.
        format: Report format - 'csv', 'md', or 'both'.
        open_stale_days: Days before open alert is stale.
        ack_stale_days: Days before acknowledged alert is stale.
        resolved_archive_days: Days before resolved is archive candidate.
        reopened_stale_days: Days before reopened alert is stale.

    Returns:
        RunResult with report rows, events, gaps, and export path.
    """
    from marketsentry.database import execute_query, table_exists

    result = CrossSiteAlertLifecycleRunResult()
    out_dir = Path(output_dir) if output_dir else Path("data/exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Build the summary
    summary = summarize_alert_lifecycle_for_all_properties(
        database_path=database_path,
        open_stale_days=open_stale_days,
        ack_stale_days=ack_stale_days,
        resolved_archive_days=resolved_archive_days,
        reopened_stale_days=reopened_stale_days,
    )
    result.summary = summary
    result.warnings = list(summary.warnings)

    if not table_exists("cross_site_trend_alerts", database_path):
        result.warnings.append(
            "cross_site_trend_alerts table not found."
        )
        return result

    # Build per-alert report rows
    try:
        raw_alerts = execute_query(
            "SELECT alert_id, property_id, candidate_id, alert_type, "
            "severity, alert_status, created_at, notes "
            "FROM cross_site_trend_alerts",
            database_path=database_path,
        )
        alerts = [_row_to_dict(r) for r in raw_alerts]
    except Exception as e:
        result.warnings.append(f"Error loading alerts: {e}")
        return result

    # Load all events
    all_events = load_alert_lifecycle_events(
        database_path=database_path,
    )
    result.events = all_events

    # Build events-by-alert lookup
    events_by_alert: Dict[int, List[CrossSiteAlertLifecycleEvent]] = {}
    for ev in all_events:
        if ev.alert_id not in events_by_alert:
            events_by_alert[ev.alert_id] = []
        events_by_alert[ev.alert_id].append(ev)

    # Detect all gaps
    all_gaps = detect_alert_lifecycle_gaps(
        database_path=database_path,
        open_stale_days=open_stale_days,
        ack_stale_days=ack_stale_days,
        resolved_archive_days=resolved_archive_days,
        reopened_stale_days=reopened_stale_days,
    )
    result.gaps = all_gaps

    # Build gaps-by-alert lookup
    gaps_by_alert: Dict[int, List[dict]] = {}
    for gap in all_gaps:
        aid = gap["alert_id"]
        if aid not in gaps_by_alert:
            gaps_by_alert[aid] = []
        gaps_by_alert[aid].append(gap)

    # Property summary lookup
    prop_summaries: Dict[int, CrossSiteAlertLifecyclePropertySummary] = {}
    for ps in summary.property_summaries:
        prop_summaries[ps.property_id] = ps

    for alert in alerts:
        aid = alert["alert_id"]
        pid = alert.get("property_id", 0)
        alert_events = events_by_alert.get(aid, [])
        alert_gaps = gaps_by_alert.get(aid, [])
        notes = alert.get("notes") or ""
        markers = _parse_notes_markers(notes)

        # Get property info
        ps = prop_summaries.get(pid)
        address = ps.address if ps else ""
        city = ps.city if ps else ""
        zip_code = ps.zip_code if ps else ""

        # Compute per-alert lifecycle label
        status = (alert.get("alert_status") or "").lower()
        label = _compute_alert_lifecycle_label(status, alert_gaps)

        # Determine recommended action
        rec_action = _compute_recommended_action(
            status, alert_gaps, markers,
        )

        gap_cats = ",".join(
            sorted(set(g["gap_category"] for g in alert_gaps))
        )

        first_at = alert_events[0].event_at if alert_events else None
        latest_at = alert_events[-1].event_at if alert_events else None
        latest_type = (
            alert_events[-1].event_type if alert_events else ""
        )

        row = CrossSiteAlertLifecycleReportRow(
            property_id=pid,
            candidate_id=alert.get("candidate_id"),
            address=address,
            city=city,
            zip_code=zip_code,
            alert_id=aid,
            alert_type=alert.get("alert_type", ""),
            severity=alert.get("severity", ""),
            current_status=alert.get("alert_status", ""),
            event_count=len(alert_events),
            first_event_at=first_at,
            latest_event_at=latest_at,
            latest_event_type=latest_type,
            lifecycle_summary_label=label,
            lifecycle_gap_count=len(alert_gaps),
            gap_categories=gap_cats,
            needs_reparse_count=markers["needs_reparse"],
            needs_manual_review_count=markers["needs_manual_review"],
            no_archive_count=markers["no_archive"],
            recommended_review_action=rec_action,
        )
        result.report_rows.append(row)

    # Write CSV
    if format in ("csv", "both"):
        csv_path = out_dir / f"cross_site_alert_lifecycle_{ts}.csv"
        _write_lifecycle_csv(csv_path, result.report_rows)
        result.export_path = str(csv_path)

    # Write Markdown
    if format in ("md", "both"):
        md_path = out_dir / f"cross_site_alert_lifecycle_{ts}.md"
        _write_lifecycle_md(md_path, result)
        if not result.export_path:
            result.export_path = str(md_path)

    return result


def _compute_alert_lifecycle_label(
    status: str, gaps: List[dict],
) -> str:
    """Compute a lifecycle label for a single alert."""
    if gaps:
        return _LABEL_NEEDS_ATTENTION
    if status == "open":
        return _LABEL_ACTIVE
    if status == "acknowledged":
        return _LABEL_UNDER_REVIEW
    if status == "resolved":
        return _LABEL_MOSTLY_RESOLVED
    if status == "archived":
        return _LABEL_ARCHIVED_HISTORY
    return _LABEL_ACTIVE


def _compute_recommended_action(
    status: str,
    gaps: List[dict],
    markers: Dict[str, int],
) -> str:
    """Compute a recommended review action for an alert."""
    gap_cats = {g["gap_category"] for g in gaps}

    if "needs_reparse_unresolved" in gap_cats:
        return "Re-parse fixture and review alert."
    if "needs_manual_review_unresolved" in gap_cats:
        return "Manual review needed."
    if "open_no_triage" in gap_cats:
        return "Export triage CSV and review."
    if "acknowledged_stale" in gap_cats:
        return "Resolve or archive via triage."
    if "resolved_archive_candidate" in gap_cats:
        return "Consider archiving or mark no_archive."
    if "reopened_stale" in gap_cats:
        return "Review reopened alert and resolve."

    if status == "open":
        return "Monitor or triage."
    if status == "acknowledged":
        return "Resolve when ready."
    if status == "resolved":
        return "No action needed."
    if status == "archived":
        return "No action needed."

    return "No action needed."


def _write_lifecycle_csv(
    path: Path,
    rows: List[CrossSiteAlertLifecycleReportRow],
) -> None:
    """Write lifecycle report rows to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LIFECYCLE_CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "property_id": row.property_id,
                "candidate_id": row.candidate_id or "",
                "address": row.address,
                "city": row.city,
                "zip": row.zip_code,
                "alert_id": row.alert_id,
                "alert_type": row.alert_type,
                "severity": row.severity,
                "current_status": row.current_status,
                "event_count": row.event_count,
                "first_event_at": row.first_event_at or "",
                "latest_event_at": row.latest_event_at or "",
                "latest_event_type": row.latest_event_type,
                "lifecycle_summary_label": row.lifecycle_summary_label,
                "lifecycle_gap_count": row.lifecycle_gap_count,
                "gap_categories": row.gap_categories,
                "needs_reparse_count": row.needs_reparse_count,
                "needs_manual_review_count": row.needs_manual_review_count,
                "no_archive_count": row.no_archive_count,
                "recommended_review_action": (
                    row.recommended_review_action
                ),
            })


def _write_lifecycle_md(
    path: Path,
    result: CrossSiteAlertLifecycleRunResult,
) -> None:
    """Write lifecycle report as Markdown."""
    lines = [
        "# Cross-Site Alert Lifecycle Audit Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- Properties with alerts: "
        f"{result.summary.total_properties_with_alerts}",
        f"- Total alerts: {result.summary.total_alerts}",
        f"- Total lifecycle events: "
        f"{result.summary.total_lifecycle_events}",
        f"- Open: {result.summary.open_alerts}",
        f"- Acknowledged: {result.summary.acknowledged_alerts}",
        f"- Resolved: {result.summary.resolved_alerts}",
        f"- Archived: {result.summary.archived_alerts}",
        f"- Lifecycle gaps: {result.summary.total_gaps}",
        f"- Needs reparse: {result.summary.needs_reparse_count}",
        f"- Needs manual review: "
        f"{result.summary.needs_manual_review_count}",
        "",
    ]

    if result.summary.recommended_actions:
        lines.append("## Recommended Actions")
        lines.append("")
        for action in result.summary.recommended_actions:
            lines.append(f"- {action}")
        lines.append("")

    if result.gaps:
        lines.append("## Lifecycle Gaps")
        lines.append("")
        lines.append(
            "| Alert ID | Category | Description | Age (days) |"
        )
        lines.append("|----------|----------|-------------|------------|")
        for gap in result.gaps:
            lines.append(
                f"| {gap['alert_id']} "
                f"| {gap['gap_category']} "
                f"| {gap['description']} "
                f"| {gap.get('age_days', '')} |"
            )
        lines.append("")

    lines.append("## Per-Alert Details")
    lines.append("")
    lines.append(
        "| Alert ID | Type | Severity | Status | Events "
        "| Label | Gaps | Action |"
    )
    lines.append(
        "|----------|------|----------|--------|--------"
        "|-------|------|--------|"
    )
    for row in result.report_rows:
        lines.append(
            f"| {row.alert_id} "
            f"| {row.alert_type} "
            f"| {row.severity} "
            f"| {row.current_status} "
            f"| {row.event_count} "
            f"| {row.lifecycle_summary_label} "
            f"| {row.lifecycle_gap_count} "
            f"| {row.recommended_review_action} |"
        )
    lines.append("")
    lines.append(
        "*This report is read-only. "
        "It does not mutate alert or watchlist state.*"
    )

    path.write_text("\n".join(lines), encoding="utf-8")


def format_alert_lifecycle_summary(
    summary: CrossSiteAlertLifecycleSummary,
) -> str:
    """Format a lifecycle summary as human-readable text.

    Args:
        summary: The lifecycle summary to format.

    Returns:
        Multi-line string suitable for CLI output.
    """
    lines = [
        "Cross-Site Alert Lifecycle Summary",
        "=" * 40,
        f"Properties with alerts: "
        f"{summary.total_properties_with_alerts}",
        f"Total alerts: {summary.total_alerts}",
        f"Total lifecycle events: {summary.total_lifecycle_events}",
        "",
        "Alert Status Breakdown:",
        f"  Open: {summary.open_alerts}",
        f"  Acknowledged: {summary.acknowledged_alerts}",
        f"  Resolved: {summary.resolved_alerts}",
        f"  Archived: {summary.archived_alerts}",
        "",
        f"Lifecycle gaps: {summary.total_gaps}",
        f"Needs reparse: {summary.needs_reparse_count}",
        f"Needs manual review: {summary.needs_manual_review_count}",
    ]

    if summary.recommended_actions:
        lines.append("")
        lines.append("Recommended Actions:")
        for action in summary.recommended_actions:
            lines.append(f"  - {action}")

    lines.append("")
    lines.append(
        "Read-only audit. No mutations performed."
    )
    return "\n".join(lines)
