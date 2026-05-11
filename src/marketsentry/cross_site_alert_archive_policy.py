"""Opt-in resolved alert archive policy workflow.

Identifies old resolved cross-site alerts eligible for archive review,
exports them to a user-reviewable CSV, and imports reviewed decisions.
Archive policy is opt-in only: it does not automatically archive alerts,
change watchlist status, overwrite Redfin source-of-truth fields, or
modify Quiet Score gatekeeper results.

Reports are operational review aids, not purchase recommendations.
"""

import csv
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from marketsentry.database import execute_query, get_connection, table_exists
from marketsentry.logging_config import logger
from marketsentry.models import (
    CrossSiteAlertArchiveCandidate,
    CrossSiteAlertArchiveDecision,
    CrossSiteAlertArchiveExportResult,
    CrossSiteAlertArchiveImportResult,
    CrossSiteAlertArchiveSummary,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARCHIVE_CSV_FIELDNAMES = [
    "archive_export_id",
    "alert_id",
    "property_id",
    "candidate_id",
    "address",
    "city",
    "zip",
    "alert_type",
    "severity",
    "current_status",
    "created_at",
    "alert_age_days",
    "message",
    "recommended_action",
    "source_context",
    "existing_notes",
    "archive_decision",
    "archive_notes",
]

ALLOWED_ARCHIVE_DECISIONS = frozenset({
    "keep_resolved",
    "archive",
    "reopen",
    "no_archive",
})

_STATUS_CHANGING_ARCHIVE_DECISIONS = {
    "archive": "archived",
    "reopen": "open",
}


# ---------------------------------------------------------------------------
# Identify archive candidates
# ---------------------------------------------------------------------------


def identify_resolved_alert_archive_candidates(
    database_path: Optional[str] = None,
    resolved_age_days: int = 30,
    property_id: Optional[int] = None,
    severity: Optional[str] = None,
) -> List[CrossSiteAlertArchiveCandidate]:
    """Identify resolved alerts eligible for archive review.

    Criteria:
    - alert_status = 'resolved'
    - age >= resolved_age_days (based on created_at)
    - excludes archived alerts
    - excludes open or acknowledged alerts
    - excludes alerts with [no_archive] in notes

    Args:
        database_path: Optional database path.
        resolved_age_days: Minimum age in days for candidates.
        property_id: Optional filter by property ID.
        severity: Optional filter by severity.

    Returns:
        List of archive candidate objects.
    """
    if not table_exists("cross_site_trend_alerts", database_path):
        return []

    conditions = ["a.alert_status = 'resolved'"]
    params: list = []

    if property_id is not None:
        conditions.append("a.property_id = ?")
        params.append(property_id)

    if severity:
        conditions.append("a.severity = ?")
        params.append(severity)

    where_clause = " AND ".join(conditions)

    query = f"""
    SELECT a.alert_id, a.property_id, a.candidate_id,
           a.alert_type, a.severity, a.alert_status,
           a.created_at, a.message, a.recommended_action,
           a.source_context, a.notes,
           wp.address, wp.city, wp.zip
    FROM cross_site_trend_alerts a
    LEFT JOIN watched_properties wp ON a.property_id = wp.property_id
    WHERE {where_clause}
    ORDER BY a.created_at ASC
    """

    candidates: List[CrossSiteAlertArchiveCandidate] = []
    try:
        rows = execute_query(query, tuple(params), database_path=database_path)
        for row in rows:
            # Exclude alerts with [no_archive] marker
            notes = row["notes"] or ""
            if "[no_archive]" in notes:
                continue

            age = _age_days(row["created_at"])
            if age is None or age < resolved_age_days:
                continue

            candidates.append(CrossSiteAlertArchiveCandidate(
                alert_id=row["alert_id"],
                property_id=row["property_id"],
                candidate_id=row["candidate_id"],
                address=row["address"],
                city=row["city"],
                zip=row["zip"],
                alert_type=row["alert_type"],
                severity=row["severity"],
                current_status=row["alert_status"],
                created_at=row["created_at"],
                alert_age_days=age,
                message=row["message"],
                recommended_action=row["recommended_action"],
                source_context=row["source_context"],
                existing_notes=notes if notes else None,
                archive_decision="keep_resolved",
            ))
    except Exception as e:
        logger.error(f"Error identifying archive candidates: {e}")

    return candidates


# ---------------------------------------------------------------------------
# Export archive candidates
# ---------------------------------------------------------------------------


def export_cross_site_alert_archive_candidates(
    database_path: Optional[str] = None,
    output_path: Optional[str] = None,
    resolved_age_days: int = 30,
    property_id: Optional[int] = None,
    severity: Optional[str] = None,
    exports_dir: Optional[str] = None,
) -> CrossSiteAlertArchiveExportResult:
    """Export archive candidate alerts to a reviewable CSV.

    Args:
        database_path: Optional database path.
        output_path: Optional explicit output file path.
        resolved_age_days: Minimum age in days for candidates.
        property_id: Optional property ID filter.
        severity: Optional severity filter.
        exports_dir: Optional exports directory.

    Returns:
        CrossSiteAlertArchiveExportResult with path and counts.
    """
    archive_export_id = f"archive_{uuid.uuid4().hex[:12]}"

    candidates = identify_resolved_alert_archive_candidates(
        database_path=database_path,
        resolved_age_days=resolved_age_days,
        property_id=property_id,
        severity=severity,
    )

    # Determine output path
    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path(exports_dir) if exports_dir else Path("data/exports")
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(
            out_dir / f"cross_site_alert_archive_candidates_{ts}.csv"
        )

    # Stamp export ID on each candidate
    for c in candidates:
        c.archive_export_id = archive_export_id

    # Write CSV
    _write_archive_csv(candidates, output_path)

    return CrossSiteAlertArchiveExportResult(
        archive_export_id=archive_export_id,
        output_path=output_path,
        row_count=len(candidates),
        resolved_age_days=resolved_age_days,
        property_id_filter=property_id,
        severity_filter=severity,
    )


# ---------------------------------------------------------------------------
# Load archive CSV
# ---------------------------------------------------------------------------


def load_cross_site_alert_archive_csv(file_path: str) -> List[Dict]:
    """Load archive candidate CSV rows.

    Args:
        file_path: Path to the archive CSV.

    Returns:
        List of row dictionaries.
    """
    rows: List[Dict] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
    except Exception as e:
        logger.error(f"Error loading archive CSV {file_path}: {e}")
    return rows


# ---------------------------------------------------------------------------
# Validate archive decisions
# ---------------------------------------------------------------------------


def validate_cross_site_alert_archive_decisions(
    rows: List[Dict],
    database_path: Optional[str] = None,
    force_status_mismatch: bool = False,
) -> List[CrossSiteAlertArchiveDecision]:
    """Validate archive decisions from CSV rows.

    Args:
        rows: List of row dicts from archive CSV.
        database_path: Optional database path.
        force_status_mismatch: Allow apply even if status changed.

    Returns:
        List of validated decisions.
    """
    valid: List[CrossSiteAlertArchiveDecision] = []

    if not table_exists("cross_site_trend_alerts", database_path):
        return valid

    alert_status_map = _get_alert_status_map(database_path)

    for row in rows:
        alert_id_str = row.get("alert_id", "")
        archive_decision = row.get("archive_decision", "").strip()
        archive_export_id = row.get("archive_export_id", "").strip()
        expected_status = row.get("current_status", "").strip()
        archive_notes = row.get("archive_notes", "").strip() or None

        # Validate alert_id is numeric
        try:
            alert_id = int(alert_id_str)
        except (ValueError, TypeError):
            continue

        # Validate alert exists
        if alert_id not in alert_status_map:
            continue

        # Validate archive_decision is allowed
        if archive_decision not in ALLOWED_ARCHIVE_DECISIONS:
            continue

        # Validate current_status matches unless force
        actual_status = alert_status_map[alert_id]
        if expected_status and expected_status != actual_status:
            if not force_status_mismatch:
                continue

        valid.append(CrossSiteAlertArchiveDecision(
            alert_id=alert_id,
            archive_export_id=archive_export_id,
            expected_status=expected_status,
            archive_decision=archive_decision,
            archive_notes=archive_notes,
        ))

    return valid


# ---------------------------------------------------------------------------
# Apply archive decisions
# ---------------------------------------------------------------------------


def apply_cross_site_alert_archive_decisions(
    file_path: str,
    database_path: Optional[str] = None,
    force_status_mismatch: bool = False,
) -> CrossSiteAlertArchiveImportResult:
    """Import archive CSV and apply decisions.

    Args:
        file_path: Path to the archive CSV.
        database_path: Optional database path.
        force_status_mismatch: Allow apply even if status changed.

    Returns:
        CrossSiteAlertArchiveImportResult with counts.
    """
    result = CrossSiteAlertArchiveImportResult()

    rows = load_cross_site_alert_archive_csv(file_path)
    result.rows_read = len(rows)

    if not rows:
        return result

    if not table_exists("cross_site_trend_alerts", database_path):
        result.errors.append("cross_site_trend_alerts table not found")
        return result

    alert_status_map = _get_alert_status_map(database_path)

    for row in rows:
        alert_id_str = row.get("alert_id", "")
        archive_decision = row.get("archive_decision", "").strip()
        archive_export_id = row.get("archive_export_id", "").strip()
        expected_status = row.get("current_status", "").strip()
        archive_notes = row.get("archive_notes", "").strip() or None

        # Validate alert_id
        try:
            alert_id = int(alert_id_str)
        except (ValueError, TypeError):
            result.invalid_rows += 1
            continue

        # Validate alert exists
        if alert_id not in alert_status_map:
            result.invalid_rows += 1
            result.errors.append(f"Alert {alert_id} not found")
            continue

        # Validate decision
        if archive_decision not in ALLOWED_ARCHIVE_DECISIONS:
            result.invalid_rows += 1
            result.errors.append(
                f"Alert {alert_id}: invalid decision '{archive_decision}'"
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
        if archive_decision in _STATUS_CHANGING_ARCHIVE_DECISIONS:
            new_status = _STATUS_CHANGING_ARCHIVE_DECISIONS[archive_decision]
            _apply_status_change(
                alert_id, actual_status, new_status,
                database_path,
            )
            _record_archive_action(
                archive_export_id, alert_id, actual_status,
                archive_decision, new_status, archive_notes,
                database_path,
            )
            if archive_decision == "archive":
                result.archived += 1
            elif archive_decision == "reopen":
                result.reopened += 1
        elif archive_decision == "no_archive":
            # Add [no_archive] marker + notes
            note_text = "[no_archive]"
            if archive_notes:
                note_text = f"[no_archive] {archive_notes}"
            _append_notes(alert_id, note_text, database_path)
            _record_archive_action(
                archive_export_id, alert_id, actual_status,
                "no_archive", actual_status, archive_notes,
                database_path,
            )
            result.no_archive += 1
        elif archive_decision == "keep_resolved":
            # Append notes if any, but no status change
            if archive_notes:
                _append_notes(alert_id, archive_notes, database_path)
            _record_archive_action(
                archive_export_id, alert_id, actual_status,
                "keep_resolved", actual_status, archive_notes,
                database_path,
            )
            result.kept_resolved += 1

    return result


# ---------------------------------------------------------------------------
# Archive policy summary
# ---------------------------------------------------------------------------


def summarize_cross_site_alert_archive_policy(
    database_path: Optional[str] = None,
    resolved_age_days: int = 30,
    exports_dir: Optional[str] = None,
) -> CrossSiteAlertArchiveSummary:
    """Summarize current archive policy state.

    Args:
        database_path: Optional database path.
        resolved_age_days: Minimum age for candidates.
        exports_dir: Optional exports directory.

    Returns:
        CrossSiteAlertArchiveSummary with counts and actions.
    """
    summary = CrossSiteAlertArchiveSummary()

    if not table_exists("cross_site_trend_alerts", database_path):
        return summary

    try:
        # Count alerts by status
        status_rows = execute_query(
            """
            SELECT alert_status, COUNT(*) as cnt
            FROM cross_site_trend_alerts
            GROUP BY alert_status
            """,
            database_path=database_path,
        )
        for r in status_rows:
            status = r["alert_status"]
            cnt = r["cnt"]
            if status == "resolved":
                summary.total_resolved = cnt
            elif status == "open":
                summary.total_open = cnt
            elif status == "acknowledged":
                summary.total_acknowledged = cnt
            elif status == "archived":
                summary.already_archived = cnt

        # Count eligible candidates
        candidates = identify_resolved_alert_archive_candidates(
            database_path=database_path,
            resolved_age_days=resolved_age_days,
        )
        summary.eligible_candidates = len(candidates)

        # Count no_archive marked
        no_archive_rows = execute_query(
            """
            SELECT COUNT(*) as cnt
            FROM cross_site_trend_alerts
            WHERE notes LIKE '%[no_archive]%'
            """,
            database_path=database_path,
        )
        if no_archive_rows:
            summary.no_archive_marked = no_archive_rows[0]["cnt"]

        # Count recent archive actions
        if table_exists("cross_site_alert_triage_actions", database_path):
            action_rows = execute_query(
                """
                SELECT COUNT(*) as cnt
                FROM cross_site_alert_triage_actions
                WHERE action LIKE 'archive_policy_%'
                   OR action IN ('archive', 'reopen', 'no_archive',
                                 'keep_resolved')
                      AND triage_export_id LIKE 'archive_%'
                """,
                database_path=database_path,
            )
            if action_rows:
                summary.recent_archive_actions = action_rows[0]["cnt"]

    except Exception as e:
        logger.error(f"Error summarizing archive policy: {e}")

    # Generate next actions
    summary.next_actions = _generate_archive_next_actions(summary)

    return summary


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _age_days(created_at_str: Optional[str]) -> Optional[int]:
    """Calculate age in days from a timestamp string."""
    if not created_at_str:
        return None
    try:
        created = datetime.fromisoformat(str(created_at_str))
        delta = datetime.now() - created
        return max(0, delta.days)
    except (ValueError, TypeError):
        return None


def _get_alert_status_map(
    database_path: Optional[str] = None,
) -> Dict[int, str]:
    """Build a map of alert_id -> current alert_status."""
    result: Dict[int, str] = {}
    try:
        rows = execute_query(
            "SELECT alert_id, alert_status FROM cross_site_trend_alerts",
            database_path=database_path,
        )
        for row in rows:
            result[row["alert_id"]] = row["alert_status"]
    except Exception:
        pass
    return result


def _apply_status_change(
    alert_id: int,
    previous_status: str,
    new_status: str,
    database_path: Optional[str] = None,
) -> None:
    """Update alert status in the database."""
    conn = get_connection(database_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE cross_site_trend_alerts SET alert_status = ? WHERE alert_id = ?",
            (new_status, alert_id),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error changing alert {alert_id} status: {e}")
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


def _record_archive_action(
    archive_export_id: str,
    alert_id: int,
    previous_status: str,
    action: str,
    new_status: str,
    archive_notes: Optional[str],
    database_path: Optional[str] = None,
) -> None:
    """Record an archive action in the triage_actions table."""
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
                archive_export_id, alert_id, property_id, action,
                previous_status, new_status, archive_notes or "",
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error recording archive action: {e}")
    finally:
        conn.close()


def _write_archive_csv(
    candidates: List[CrossSiteAlertArchiveCandidate],
    path: str,
) -> None:
    """Write archive candidates to CSV."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ARCHIVE_CSV_FIELDNAMES)
        writer.writeheader()
        for c in candidates:
            writer.writerow({
                "archive_export_id": c.archive_export_id,
                "alert_id": c.alert_id,
                "property_id": c.property_id,
                "candidate_id": c.candidate_id or "",
                "address": c.address or "",
                "city": c.city or "",
                "zip": c.zip or "",
                "alert_type": c.alert_type,
                "severity": c.severity,
                "current_status": c.current_status,
                "created_at": c.created_at or "",
                "alert_age_days": c.alert_age_days if c.alert_age_days is not None else "",
                "message": c.message or "",
                "recommended_action": c.recommended_action or "",
                "source_context": c.source_context or "",
                "existing_notes": c.existing_notes or "",
                "archive_decision": c.archive_decision,
                "archive_notes": c.archive_notes or "",
            })


def _generate_archive_next_actions(
    summary: CrossSiteAlertArchiveSummary,
) -> List[str]:
    """Generate recommended next actions from archive summary."""
    actions: List[str] = []

    if summary.eligible_candidates > 0:
        actions.append(
            f"Export {summary.eligible_candidates} archive candidate(s): "
            f"marketsentry export-cross-site-alert-archive-candidates"
        )

    if summary.already_archived > 0:
        actions.append(
            f"{summary.already_archived} alert(s) already archived"
        )

    if summary.no_archive_marked > 0:
        actions.append(
            f"{summary.no_archive_marked} alert(s) marked no_archive "
            f"and exempt from future archive review"
        )

    if not actions:
        actions.append(
            "No resolved alerts eligible for archive at current threshold."
        )

    return actions
