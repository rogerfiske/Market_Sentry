"""Cross-site alert triage workflow.

Provides CSV-based export/import triage workflow for managing
accumulated cross-site trend alerts. Operators export filtered
alerts, edit triage decisions offline, and import decisions to
batch-acknowledge, resolve, or archive alerts.

Triage actions change alert status only. They do not modify
watchlist state, Redfin source-of-truth fields, user decisions,
or Quiet Score gatekeeper results.

These are neutral operational review aids, not purchase
recommendations. They do not infer seller intent.
"""

import csv
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from marketsentry.database import execute_query, get_connection, table_exists
from marketsentry.logging_config import logger
from marketsentry.models import (
    CrossSiteAlertTriageDecision,
    CrossSiteAlertTriageExportResult,
    CrossSiteAlertTriageImportResult,
    CrossSiteAlertTriageRow,
    CrossSiteAlertTriageSummary,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_TRIAGE_DECISIONS = frozenset({
    "keep_open",
    "acknowledge",
    "resolve",
    "archive",
    "needs_reparse",
    "needs_manual_review",
})

# Decisions that change alert_status
_STATUS_CHANGING_DECISIONS = {
    "acknowledge": "acknowledged",
    "resolve": "resolved",
    "archive": "archived",
}

TRIAGE_CSV_FIELDNAMES = [
    "triage_export_id",
    "alert_id",
    "property_id",
    "candidate_id",
    "address",
    "city",
    "zip",
    "alert_type",
    "severity",
    "current_status",
    "trend_direction",
    "message",
    "recommended_action",
    "source_context",
    "created_at",
    "alert_age_days",
    "alert_burden_label",
    "repeated_patterns",
    "triage_decision",
    "triage_notes",
]


# ---------------------------------------------------------------------------
# Filter alerts for triage
# ---------------------------------------------------------------------------


def filter_alerts_for_triage(
    database_path: Optional[str] = None,
    status_filter: Optional[str] = "open",
    severity_filter: Optional[str] = None,
    property_id: Optional[int] = None,
    include_acknowledged: bool = False,
) -> List[Dict]:
    """Filter alerts for triage export.

    Args:
        database_path: Optional database path.
        status_filter: Alert status filter (default: open).
        severity_filter: Optional severity filter.
        property_id: Optional property ID filter.
        include_acknowledged: Include acknowledged alerts.

    Returns:
        List of alert row dicts with address context.
    """
    if not table_exists("cross_site_trend_alerts", database_path):
        return []

    conditions = []
    params: list = []

    if status_filter and not include_acknowledged:
        conditions.append("a.alert_status = ?")
        params.append(status_filter)
    elif status_filter and include_acknowledged:
        conditions.append("a.alert_status IN (?, 'acknowledged')")
        params.append(status_filter)
    elif include_acknowledged:
        conditions.append("a.alert_status IN ('open', 'acknowledged')")

    if severity_filter:
        conditions.append("a.severity = ?")
        params.append(severity_filter)

    if property_id is not None:
        conditions.append("a.property_id = ?")
        params.append(property_id)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    query = f"""
    SELECT a.alert_id, a.property_id, a.candidate_id,
           wp.address, wp.city, wp.zip,
           a.alert_type, a.severity, a.alert_status,
           a.trend_direction, a.message, a.recommended_action,
           a.source_context, a.created_at, a.notes
    FROM cross_site_trend_alerts a
    LEFT JOIN watched_properties wp ON a.property_id = wp.property_id
    {where}
    ORDER BY a.created_at ASC
    """

    try:
        results = execute_query(query, tuple(params), database_path=database_path)
        return [dict(r) for r in results]
    except Exception as e:
        logger.error(f"Error filtering alerts for triage: {e}")
        return []


# ---------------------------------------------------------------------------
# Export triage CSV
# ---------------------------------------------------------------------------


def export_cross_site_alert_triage_csv(
    database_path: Optional[str] = None,
    output_path: Optional[str] = None,
    status_filter: Optional[str] = "open",
    severity_filter: Optional[str] = None,
    property_id: Optional[int] = None,
    include_acknowledged: bool = False,
) -> CrossSiteAlertTriageExportResult:
    """Export filtered alerts to a triage CSV.

    Args:
        database_path: Optional database path.
        output_path: Optional output file path.
        status_filter: Alert status filter (default: open).
        severity_filter: Optional severity filter.
        property_id: Optional property ID filter.
        include_acknowledged: Include acknowledged alerts.

    Returns:
        CrossSiteAlertTriageExportResult with export details.
    """
    triage_export_id = f"triage_{uuid.uuid4().hex[:12]}"

    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/exports")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"cross_site_alert_triage_{ts}.csv")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Exporting triage CSV: {output_path}")

    alerts = filter_alerts_for_triage(
        database_path, status_filter, severity_filter, property_id,
        include_acknowledged,
    )

    # Enrich with burden and pattern info
    burden_map = _get_burden_map(database_path)
    pattern_map = _get_pattern_map(database_path)

    rows = []
    for a in alerts:
        pid = a["property_id"]
        age = _calculate_age_days(a.get("created_at"))
        burden_label = burden_map.get(pid, "none")
        patterns = pattern_map.get(pid, "")

        rows.append({
            "triage_export_id": triage_export_id,
            "alert_id": a["alert_id"],
            "property_id": pid,
            "candidate_id": a.get("candidate_id") or "",
            "address": a.get("address") or "",
            "city": a.get("city") or "",
            "zip": a.get("zip") or "",
            "alert_type": a.get("alert_type") or "",
            "severity": a.get("severity") or "",
            "current_status": a.get("alert_status") or "",
            "trend_direction": a.get("trend_direction") or "",
            "message": a.get("message") or "",
            "recommended_action": a.get("recommended_action") or "",
            "source_context": a.get("source_context") or "",
            "created_at": a.get("created_at") or "",
            "alert_age_days": age if age is not None else "",
            "alert_burden_label": burden_label,
            "repeated_patterns": patterns,
            "triage_decision": "keep_open",
            "triage_notes": "",
        })

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRIAGE_CSV_FIELDNAMES)
        writer.writeheader()
        if rows:
            writer.writerows(rows)

    logger.info(f"Exported {len(rows)} alerts to triage CSV")

    return CrossSiteAlertTriageExportResult(
        triage_export_id=triage_export_id,
        output_path=str(output_file),
        row_count=len(rows),
        status_filter=status_filter,
        severity_filter=severity_filter,
        property_id_filter=property_id,
    )


# ---------------------------------------------------------------------------
# Load triage CSV
# ---------------------------------------------------------------------------


def load_cross_site_alert_triage_csv(
    file_path: str,
) -> List[Dict]:
    """Load a triage CSV file and return rows as dicts.

    Args:
        file_path: Path to the triage CSV file.

    Returns:
        List of row dicts.
    """
    rows = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
    except Exception as e:
        logger.error(f"Error loading triage CSV {file_path}: {e}")

    return rows


# ---------------------------------------------------------------------------
# Validate triage decisions
# ---------------------------------------------------------------------------


def validate_cross_site_alert_triage_decisions(
    rows: List[Dict],
    database_path: Optional[str] = None,
    force_status_mismatch: bool = False,
) -> List[CrossSiteAlertTriageDecision]:
    """Validate triage decisions from CSV rows.

    Args:
        rows: List of row dicts from triage CSV.
        database_path: Optional database path.
        force_status_mismatch: Allow status mismatches.

    Returns:
        List of valid CrossSiteAlertTriageDecision objects.
    """
    valid: List[CrossSiteAlertTriageDecision] = []

    if not table_exists("cross_site_trend_alerts", database_path):
        return valid

    # Build map of current alert statuses
    alert_status_map = _get_alert_status_map(database_path)

    for row in rows:
        alert_id_str = row.get("alert_id", "")
        triage_decision = row.get("triage_decision", "").strip()
        triage_export_id = row.get("triage_export_id", "").strip()
        expected_status = row.get("current_status", "").strip()
        triage_notes = row.get("triage_notes", "").strip() or None

        # Validate alert_id is numeric
        try:
            alert_id = int(alert_id_str)
        except (ValueError, TypeError):
            continue

        # Validate alert exists
        if alert_id not in alert_status_map:
            continue

        # Validate triage_decision is allowed
        if triage_decision not in ALLOWED_TRIAGE_DECISIONS:
            continue

        # Validate current_status matches unless force
        actual_status = alert_status_map[alert_id]
        if expected_status and expected_status != actual_status:
            if not force_status_mismatch:
                continue

        valid.append(CrossSiteAlertTriageDecision(
            alert_id=alert_id,
            triage_export_id=triage_export_id,
            expected_status=expected_status,
            triage_decision=triage_decision,
            triage_notes=triage_notes,
        ))

    return valid


# ---------------------------------------------------------------------------
# Apply triage decisions
# ---------------------------------------------------------------------------


def apply_cross_site_alert_triage_decisions(
    file_path: str,
    database_path: Optional[str] = None,
    force_status_mismatch: bool = False,
) -> CrossSiteAlertTriageImportResult:
    """Import triage CSV and apply valid decisions.

    Args:
        file_path: Path to the triage CSV file.
        database_path: Optional database path.
        force_status_mismatch: Allow status mismatches.

    Returns:
        CrossSiteAlertTriageImportResult with counts.
    """
    result = CrossSiteAlertTriageImportResult()

    rows = load_cross_site_alert_triage_csv(file_path)
    result.rows_read = len(rows)

    if not rows:
        return result

    # Get current alert statuses for mismatch detection
    alert_status_map = _get_alert_status_map(database_path)

    # Process each row
    for row in rows:
        alert_id_str = row.get("alert_id", "")
        triage_decision = row.get("triage_decision", "").strip()
        triage_export_id = row.get("triage_export_id", "").strip()
        expected_status = row.get("current_status", "").strip()
        triage_notes = row.get("triage_notes", "").strip() or None

        # Validate alert_id
        try:
            alert_id = int(alert_id_str)
        except (ValueError, TypeError):
            result.invalid_rows += 1
            result.errors.append(f"Invalid alert_id: {alert_id_str}")
            continue

        # Validate alert exists
        if alert_id not in alert_status_map:
            result.invalid_rows += 1
            result.errors.append(f"Alert {alert_id} not found")
            continue

        # Validate triage_decision
        if triage_decision not in ALLOWED_TRIAGE_DECISIONS:
            result.invalid_rows += 1
            result.errors.append(
                f"Invalid decision '{triage_decision}' for alert {alert_id}"
            )
            continue

        # Check status mismatch
        actual_status = alert_status_map[alert_id]
        if expected_status and expected_status != actual_status:
            if not force_status_mismatch:
                result.skipped_status_mismatch += 1
                continue

        result.valid_decisions += 1

        # Apply the decision
        if triage_decision in _STATUS_CHANGING_DECISIONS:
            new_status = _STATUS_CHANGING_DECISIONS[triage_decision]
            _apply_status_change(
                alert_id, actual_status, new_status,
                triage_notes, triage_export_id, database_path,
            )
            if triage_decision == "acknowledge":
                result.acknowledged += 1
            elif triage_decision == "resolve":
                result.resolved += 1
            elif triage_decision == "archive":
                result.archived += 1
        elif triage_decision == "keep_open":
            # No status change, but record notes if present
            if triage_notes:
                _append_notes(alert_id, triage_notes, database_path)
            _record_triage_action(
                triage_export_id, alert_id, actual_status,
                "keep_open", actual_status, triage_notes, database_path,
            )
            result.kept_open += 1
        elif triage_decision == "needs_reparse":
            note = f"[triage:needs_reparse] {triage_notes or ''}".strip()
            _append_notes(alert_id, note, database_path)
            _record_triage_action(
                triage_export_id, alert_id, actual_status,
                "needs_reparse", actual_status, triage_notes, database_path,
            )
            result.needs_reparse += 1
        elif triage_decision == "needs_manual_review":
            note = f"[triage:needs_manual_review] {triage_notes or ''}".strip()
            _append_notes(alert_id, note, database_path)
            _record_triage_action(
                triage_export_id, alert_id, actual_status,
                "needs_manual_review", actual_status, triage_notes, database_path,
            )
            result.needs_manual_review += 1

    return result


# ---------------------------------------------------------------------------
# Triage summary
# ---------------------------------------------------------------------------


def summarize_cross_site_alert_triage(
    database_path: Optional[str] = None,
    exports_dir: Optional[str] = None,
) -> CrossSiteAlertTriageSummary:
    """Summarize current triage state.

    Args:
        database_path: Optional database path.
        exports_dir: Optional exports directory.

    Returns:
        CrossSiteAlertTriageSummary.
    """
    summary = CrossSiteAlertTriageSummary()

    if not table_exists("cross_site_trend_alerts", database_path):
        return summary

    try:
        # Count alerts by status
        status_counts = execute_query(
            """
            SELECT alert_status, COUNT(*) as cnt
            FROM cross_site_trend_alerts
            GROUP BY alert_status
            """,
            database_path=database_path,
        )
        for row in status_counts:
            status = row["alert_status"]
            count = row["cnt"]
            summary.total_alerts += count
            if status == "open":
                summary.open_alerts = count
            elif status == "acknowledged":
                summary.acknowledged_alerts = count
            elif status == "resolved":
                summary.resolved_alerts = count
            elif status == "archived":
                summary.archived_alerts = count

        # Count needs_reparse from notes
        reparse_rows = execute_query(
            """
            SELECT COUNT(*) as cnt FROM cross_site_trend_alerts
            WHERE notes LIKE '%[triage:needs_reparse]%'
            """,
            database_path=database_path,
        )
        if reparse_rows:
            summary.needs_reparse_count = reparse_rows[0]["cnt"]

        # Count needs_manual_review from notes
        review_rows = execute_query(
            """
            SELECT COUNT(*) as cnt FROM cross_site_trend_alerts
            WHERE notes LIKE '%[triage:needs_manual_review]%'
            """,
            database_path=database_path,
        )
        if review_rows:
            summary.needs_manual_review_count = review_rows[0]["cnt"]

        # Count recent triage actions
        if table_exists("cross_site_alert_triage_actions", database_path):
            action_rows = execute_query(
                """
                SELECT COUNT(*) as cnt FROM cross_site_alert_triage_actions
                """,
                database_path=database_path,
            )
            if action_rows:
                summary.recent_triage_actions = action_rows[0]["cnt"]

        # Find latest triage export
        if exports_dir:
            from marketsentry.dashboard import find_latest_report
            report = find_latest_report("cross_site_alert_triage", exports_dir)
            if report:
                summary.latest_triage_export_path = str(report)

    except Exception as e:
        logger.error(f"Error summarizing triage: {e}")

    return summary


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_alert_status_map(
    database_path: Optional[str] = None,
) -> Dict[int, str]:
    """Get map of alert_id -> current alert_status."""
    status_map: Dict[int, str] = {}
    try:
        results = execute_query(
            "SELECT alert_id, alert_status FROM cross_site_trend_alerts",
            database_path=database_path,
        )
        for row in results:
            status_map[row["alert_id"]] = row["alert_status"]
    except Exception as e:
        logger.error(f"Error getting alert status map: {e}")
    return status_map


def _apply_status_change(
    alert_id: int,
    previous_status: str,
    new_status: str,
    triage_notes: Optional[str],
    triage_export_id: str,
    database_path: Optional[str] = None,
) -> None:
    """Apply an alert status change and record triage history."""
    conn = get_connection(database_path)
    cursor = conn.cursor()
    try:
        # Update alert status and append notes
        note_text = triage_notes or ""
        if note_text:
            cursor.execute(
                """
                UPDATE cross_site_trend_alerts
                SET alert_status = ?,
                    notes = CASE
                        WHEN notes IS NULL OR notes = '' THEN ?
                        ELSE notes || '; ' || ?
                    END
                WHERE alert_id = ?
                """,
                (new_status, note_text, note_text, alert_id),
            )
        else:
            cursor.execute(
                """
                UPDATE cross_site_trend_alerts
                SET alert_status = ?
                WHERE alert_id = ?
                """,
                (new_status, alert_id),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error applying status change for alert {alert_id}: {e}")
    finally:
        conn.close()

    # Record triage action
    _record_triage_action(
        triage_export_id, alert_id, previous_status,
        new_status, new_status, triage_notes, database_path,
    )


def _record_triage_action(
    triage_export_id: str,
    alert_id: int,
    previous_status: str,
    action: str,
    new_status: str,
    triage_notes: Optional[str],
    database_path: Optional[str] = None,
) -> None:
    """Record a triage action in the history table."""
    if not table_exists("cross_site_alert_triage_actions", database_path):
        return

    # Get property_id for this alert
    property_id = None
    try:
        rows = execute_query(
            "SELECT property_id FROM cross_site_trend_alerts WHERE alert_id = ?",
            (alert_id,),
            database_path=database_path,
        )
        if rows:
            property_id = rows[0]["property_id"]
    except Exception:
        pass

    conn = get_connection(database_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO cross_site_alert_triage_actions
            (triage_export_id, alert_id, property_id, action,
             previous_status, new_status, triage_notes, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                triage_export_id, alert_id, property_id, action,
                previous_status, new_status, triage_notes or "",
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error recording triage action: {e}")
    finally:
        conn.close()


def _append_notes(
    alert_id: int,
    note_text: str,
    database_path: Optional[str] = None,
) -> None:
    """Append text to an alert's notes field."""
    conn = get_connection(database_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE cross_site_trend_alerts
            SET notes = CASE
                WHEN notes IS NULL OR notes = '' THEN ?
                ELSE notes || '; ' || ?
            END
            WHERE alert_id = ?
            """,
            (note_text, note_text, alert_id),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error appending notes for alert {alert_id}: {e}")
    finally:
        conn.close()


def _calculate_age_days(created_at_str: Optional[str]) -> Optional[int]:
    """Calculate alert age in days."""
    if not created_at_str:
        return None
    try:
        created = datetime.fromisoformat(str(created_at_str))
        delta = datetime.now() - created
        return max(0, delta.days)
    except (ValueError, TypeError):
        return None


def _get_burden_map(
    database_path: Optional[str] = None,
) -> Dict[int, str]:
    """Get map of property_id -> alert_burden_label."""
    burden_map: Dict[int, str] = {}
    try:
        from marketsentry.cross_site_alert_analytics import (
            calculate_alert_burden_for_property,
        )

        if not table_exists("cross_site_trend_alerts", database_path):
            return burden_map

        props = execute_query(
            "SELECT DISTINCT property_id FROM cross_site_trend_alerts",
            database_path=database_path,
        )
        for row in props:
            pid = row["property_id"]
            burden = calculate_alert_burden_for_property(pid, database_path)
            burden_map[pid] = burden.alert_burden_label
    except Exception as e:
        logger.error(f"Error getting burden map: {e}")

    return burden_map


def _get_pattern_map(
    database_path: Optional[str] = None,
) -> Dict[int, str]:
    """Get map of property_id -> repeated patterns string."""
    pattern_map: Dict[int, str] = {}
    try:
        from marketsentry.cross_site_alert_analytics import (
            identify_repeated_alert_patterns,
        )

        if not table_exists("cross_site_trend_alerts", database_path):
            return pattern_map

        props = execute_query(
            "SELECT DISTINCT property_id FROM cross_site_trend_alerts",
            database_path=database_path,
        )
        for row in props:
            pid = row["property_id"]
            patterns = identify_repeated_alert_patterns(pid, database_path)
            if patterns:
                pattern_map[pid] = "; ".join(p.pattern_type for p in patterns)
    except Exception as e:
        logger.error(f"Error getting pattern map: {e}")

    return pattern_map
