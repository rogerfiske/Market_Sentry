"""Lifecycle Health Trend Snapshots and Scheduled Health Reports.

Tracks health-score movement over time with append-only per-property
snapshots. Detects improvement, degradation, and label changes.

Read-only except for append-only health snapshot rows. Does not mutate
alert status, watchlist status, or Redfin source-of-truth fields.

Milestone 37.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from marketsentry.database import execute_query, get_connection, table_exists
from marketsentry.models import (
    CrossSiteLifecycleHealthSnapshot,
    CrossSiteLifecycleHealthSnapshotRunResult,
    CrossSiteLifecycleHealthTrendChange,
    CrossSiteLifecycleHealthTrendReportRow,
    CrossSiteLifecycleHealthTrendSummary,
)

logger = logging.getLogger(__name__)

HEALTH_TREND_CSV_FIELDNAMES = [
    "property_id",
    "candidate_id",
    "address",
    "city",
    "zip",
    "current_health_score",
    "previous_health_score",
    "health_score_delta",
    "current_health_label",
    "previous_health_label",
    "health_label_changed",
    "current_open_alert_count",
    "previous_open_alert_count",
    "open_alert_delta",
    "current_high_or_critical_open_alert_count",
    "previous_high_or_critical_open_alert_count",
    "high_or_critical_delta",
    "current_lifecycle_gap_count",
    "previous_lifecycle_gap_count",
    "lifecycle_gap_delta",
    "current_needs_reparse_count",
    "previous_needs_reparse_count",
    "needs_reparse_delta",
    "current_needs_manual_review_count",
    "previous_needs_manual_review_count",
    "needs_manual_review_delta",
    "trend_direction",
    "trend_summary",
    "recommended_review_action",
]


def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row or dict to a plain dict."""
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except (TypeError, ValueError):
        return {}


def _safe_float(val) -> Optional[float]:
    """Safely convert a value to float or return None."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> Optional[int]:
    """Safely convert a value to int or return None."""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _parse_datetime(val: Optional[str]) -> Optional[datetime]:
    """Parse a datetime string in common formats."""
    if not val:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def _is_same_day(dt1_str: Optional[str], dt2_str: Optional[str]) -> bool:
    """Check if two datetime strings represent the same calendar day."""
    if not dt1_str or not dt2_str:
        return False
    d1 = _parse_datetime(dt1_str)
    d2 = _parse_datetime(dt2_str)
    if d1 and d2:
        return d1.date() == d2.date()
    return False


def _snapshot_from_row(d: dict) -> CrossSiteLifecycleHealthSnapshot:
    """Build a health snapshot model from a database row dict."""
    return CrossSiteLifecycleHealthSnapshot(
        health_snapshot_id=d.get("health_snapshot_id", 0),
        property_id=d.get("property_id", 0),
        candidate_id=_safe_int(d.get("candidate_id")),
        captured_at=d.get("captured_at"),
        lifecycle_health_score=_safe_float(
            d.get("lifecycle_health_score"),
        ) or 100.0,
        lifecycle_health_label=d.get("lifecycle_health_label", "excellent"),
        open_alert_count=d.get("open_alert_count", 0),
        high_or_critical_open_alert_count=d.get(
            "high_or_critical_open_alert_count", 0,
        ),
        lifecycle_gap_count=d.get("lifecycle_gap_count", 0),
        stale_open_alert_count=d.get("stale_open_alert_count", 0),
        needs_reparse_count=d.get("needs_reparse_count", 0),
        needs_manual_review_count=d.get("needs_manual_review_count", 0),
        alert_burden_label=d.get("alert_burden_label", "none"),
        repeated_patterns=d.get("repeated_patterns", 0),
        oldest_open_alert_age_days=_safe_int(
            d.get("oldest_open_alert_age_days"),
        ),
        avg_time_to_resolution_days=_safe_float(
            d.get("avg_time_to_resolution_days"),
        ),
        latest_lifecycle_event_at=d.get("latest_lifecycle_event_at"),
        component_summary=d.get("component_summary", ""),
        recommended_review_action=d.get("recommended_review_action", ""),
        notes=d.get("notes"),
        created_at=d.get("created_at"),
    )


def _has_material_change(
    current_score: "CrossSiteLifecycleHealthScore",
    previous_snap: CrossSiteLifecycleHealthSnapshot,
) -> bool:
    """Check if there is a material change between current score and previous snapshot.

    Material changes include: health score changed by >= 5 points,
    label changed, open alert count changed, high/critical count changed,
    lifecycle gap count changed, needs_reparse/manual_review changed,
    or component_summary changed materially.

    Args:
        current_score: The newly computed health score.
        previous_snap: The most recent stored snapshot.

    Returns:
        True if material change detected, False otherwise.
    """
    if abs(
        current_score.lifecycle_health_score
        - previous_snap.lifecycle_health_score
    ) >= 5:
        return True
    if (
        current_score.lifecycle_health_label
        != previous_snap.lifecycle_health_label
    ):
        return True
    if current_score.open_alert_count != previous_snap.open_alert_count:
        return True
    if (
        current_score.high_or_critical_open_alert_count
        != previous_snap.high_or_critical_open_alert_count
    ):
        return True
    if current_score.lifecycle_gap_count != previous_snap.lifecycle_gap_count:
        return True
    if current_score.needs_reparse_count != previous_snap.needs_reparse_count:
        return True
    if (
        current_score.needs_manual_review_count
        != previous_snap.needs_manual_review_count
    ):
        return True
    return False


def _ensure_health_snapshot_table(
    database_path: Optional[str] = None,
) -> None:
    """Ensure the lifecycle health snapshots table exists."""
    if table_exists(
        "cross_site_lifecycle_health_snapshots",
        database_path=database_path,
    ):
        return

    from marketsentry.schema import (
        CREATE_CROSS_SITE_LIFECYCLE_HEALTH_SNAPSHOTS_TABLE,
    )

    conn = get_connection(database_path)
    cursor = conn.cursor()
    try:
        cursor.execute(CREATE_CROSS_SITE_LIFECYCLE_HEALTH_SNAPSHOTS_TABLE)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating health snapshots table: {e}")
        raise
    finally:
        conn.close()


def _insert_health_snapshot(
    score: "CrossSiteLifecycleHealthScore",
    component_summary: str,
    database_path: Optional[str] = None,
) -> int:
    """Insert a health snapshot into the database and return its ID."""
    conn = get_connection(database_path)
    cursor = conn.cursor()
    captured = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute(
            """
            INSERT INTO cross_site_lifecycle_health_snapshots (
                property_id, candidate_id, captured_at,
                lifecycle_health_score, lifecycle_health_label,
                open_alert_count, high_or_critical_open_alert_count,
                lifecycle_gap_count, stale_open_alert_count,
                needs_reparse_count, needs_manual_review_count,
                alert_burden_label, repeated_patterns,
                oldest_open_alert_age_days, avg_time_to_resolution_days,
                latest_lifecycle_event_at, component_summary,
                recommended_review_action, notes
            ) VALUES (
                ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?
            )
            """,
            (
                score.property_id,
                score.candidate_id,
                captured,
                score.lifecycle_health_score,
                score.lifecycle_health_label,
                score.open_alert_count,
                score.high_or_critical_open_alert_count,
                score.lifecycle_gap_count,
                score.stale_open_alert_count,
                score.needs_reparse_count,
                score.needs_manual_review_count,
                score.alert_burden_label,
                score.repeated_patterns,
                score.oldest_open_alert_age_days,
                score.avg_time_to_resolution_days,
                score.latest_lifecycle_event_at,
                component_summary,
                score.recommended_review_action,
                None,
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting health snapshot: {e}")
        raise
    finally:
        conn.close()


def _build_component_summary(
    score: "CrossSiteLifecycleHealthScore",
) -> str:
    """Build a component summary string from a health score."""
    parts = []
    for c in score.components:
        if c.component_score_delta != 0:
            parts.append(
                f"{c.component_name}:{c.component_score_delta:+.0f}"
            )
    return "; ".join(parts) if parts else "no deductions"


# ── Public API ──


def create_lifecycle_health_snapshots(
    database_path: Optional[str] = None,
    force: bool = False,
) -> CrossSiteLifecycleHealthSnapshotRunResult:
    """Create append-only health snapshots for all scored properties.

    Computes current health scores and persists one snapshot per
    property when health data exists. Skips same-day/no-change
    snapshots unless --force is set.

    Args:
        database_path: Path to the SQLite database.
        force: If True, create snapshots even without material change.

    Returns:
        CrossSiteLifecycleHealthSnapshotRunResult with counts.
    """
    from marketsentry.cross_site_alert_lifecycle_health import (
        calculate_lifecycle_health_scores,
    )

    result = CrossSiteLifecycleHealthSnapshotRunResult()

    _ensure_health_snapshot_table(database_path)

    scores = calculate_lifecycle_health_scores(
        database_path=database_path,
    )
    result.properties_scanned = len(scores)

    label_counts: Dict[str, int] = {}

    for score in scores:
        label = score.lifecycle_health_label
        label_counts[label] = label_counts.get(label, 0) + 1

        comp_summary = _build_component_summary(score)

        if not force:
            prev = get_latest_lifecycle_health_snapshot(
                property_id=score.property_id,
                database_path=database_path,
            )
            if prev:
                if _is_same_day(
                    datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    prev.captured_at,
                ):
                    if not _has_material_change(score, prev):
                        result.snapshots_skipped += 1
                        continue

                if _has_material_change(score, prev):
                    result.material_changes_detected += 1

        _insert_health_snapshot(score, comp_summary, database_path)
        result.snapshots_created += 1

    result.label_counts = label_counts
    return result


def get_latest_lifecycle_health_snapshot(
    property_id: int,
    database_path: Optional[str] = None,
) -> Optional[CrossSiteLifecycleHealthSnapshot]:
    """Retrieve the most recent health snapshot for a property.

    Args:
        property_id: The property ID.
        database_path: Path to the SQLite database.

    Returns:
        CrossSiteLifecycleHealthSnapshot or None if no snapshots exist.
    """
    if not table_exists(
        "cross_site_lifecycle_health_snapshots",
        database_path=database_path,
    ):
        return None

    query = """
        SELECT * FROM cross_site_lifecycle_health_snapshots
        WHERE property_id = ?
        ORDER BY captured_at DESC LIMIT 1
    """
    rows = execute_query(query, (property_id,), database_path=database_path)
    if not rows:
        return None

    return _snapshot_from_row(_row_to_dict(rows[0]))


def get_previous_lifecycle_health_snapshot(
    property_id: int,
    database_path: Optional[str] = None,
) -> Optional[CrossSiteLifecycleHealthSnapshot]:
    """Retrieve the second-most-recent health snapshot for a property.

    Args:
        property_id: The property ID.
        database_path: Path to the SQLite database.

    Returns:
        CrossSiteLifecycleHealthSnapshot or None if fewer than two exist.
    """
    if not table_exists(
        "cross_site_lifecycle_health_snapshots",
        database_path=database_path,
    ):
        return None

    query = """
        SELECT * FROM cross_site_lifecycle_health_snapshots
        WHERE property_id = ?
        ORDER BY captured_at DESC LIMIT 1 OFFSET 1
    """
    rows = execute_query(query, (property_id,), database_path=database_path)
    if not rows:
        return None

    return _snapshot_from_row(_row_to_dict(rows[0]))


def calculate_lifecycle_health_trend_change(
    property_id: int,
    database_path: Optional[str] = None,
) -> Optional[CrossSiteLifecycleHealthTrendChange]:
    """Compute health trend change for a single property.

    Compares the latest and previous health snapshots. Returns None
    if fewer than two snapshots exist.

    Args:
        property_id: The property ID.
        database_path: Path to the SQLite database.

    Returns:
        CrossSiteLifecycleHealthTrendChange or None.
    """
    latest = get_latest_lifecycle_health_snapshot(
        property_id=property_id,
        database_path=database_path,
    )
    if not latest:
        return None

    previous = get_previous_lifecycle_health_snapshot(
        property_id=property_id,
        database_path=database_path,
    )

    # Get address info
    address = ""
    city = ""
    zip_code = ""
    try:
        rows = execute_query(
            "SELECT address, city, zip FROM watched_properties "
            "WHERE property_id = ? LIMIT 1",
            (property_id,),
            database_path,
        )
        if rows:
            d = _row_to_dict(rows[0])
            address = d.get("address", "") or ""
            city = d.get("city", "") or ""
            zip_code = d.get("zip", "") or ""
    except Exception:
        pass

    if not previous:
        # New — first snapshot, no comparison
        return CrossSiteLifecycleHealthTrendChange(
            property_id=property_id,
            candidate_id=latest.candidate_id,
            address=address,
            city=city,
            zip_code=zip_code,
            current_health_score=latest.lifecycle_health_score,
            previous_health_score=0.0,
            health_score_delta=0.0,
            current_health_label=latest.lifecycle_health_label,
            previous_health_label="",
            health_label_changed=False,
            current_open_alert_count=latest.open_alert_count,
            current_high_or_critical_open_alert_count=(
                latest.high_or_critical_open_alert_count
            ),
            current_lifecycle_gap_count=latest.lifecycle_gap_count,
            current_needs_reparse_count=latest.needs_reparse_count,
            current_needs_manual_review_count=(
                latest.needs_manual_review_count
            ),
            trend_direction="new",
            trend_summary="First health snapshot. No comparison available.",
            recommended_review_action=(
                "Baseline established. Continue monitoring."
            ),
        )

    # Compute deltas
    score_delta = round(
        latest.lifecycle_health_score
        - previous.lifecycle_health_score,
        1,
    )
    label_changed = (
        latest.lifecycle_health_label != previous.lifecycle_health_label
    )
    open_delta = latest.open_alert_count - previous.open_alert_count
    hc_delta = (
        latest.high_or_critical_open_alert_count
        - previous.high_or_critical_open_alert_count
    )
    gap_delta = latest.lifecycle_gap_count - previous.lifecycle_gap_count
    reparse_delta = (
        latest.needs_reparse_count - previous.needs_reparse_count
    )
    manual_delta = (
        latest.needs_manual_review_count
        - previous.needs_manual_review_count
    )

    # Determine trend direction
    improving = 0
    worsening = 0

    if score_delta > 0:
        improving += 1
    elif score_delta < 0:
        worsening += 1

    if open_delta < 0:
        improving += 1
    elif open_delta > 0:
        worsening += 1

    if gap_delta < 0:
        improving += 1
    elif gap_delta > 0:
        worsening += 1

    if improving > worsening:
        direction = "improved"
    elif worsening > improving:
        direction = "degraded"
    else:
        direction = "stable"

    # Summary
    parts = []
    if score_delta != 0:
        parts.append(
            f"Health score changed by {score_delta:+.1f}"
        )
    if label_changed:
        parts.append(
            f"Label changed from {previous.lifecycle_health_label} "
            f"to {latest.lifecycle_health_label}"
        )
    if open_delta != 0:
        parts.append(f"Open alerts changed by {open_delta:+d}")
    if gap_delta != 0:
        parts.append(f"Lifecycle gaps changed by {gap_delta:+d}")

    summary = "; ".join(parts) if parts else "No material changes"

    # Recommended action
    if direction == "degraded":
        rec = (
            "Review degraded properties. Address open alerts "
            "and lifecycle gaps."
        )
    elif direction == "improved":
        rec = "Trend improving. Continue current workflow."
    else:
        rec = "No action needed. Metrics stable."

    return CrossSiteLifecycleHealthTrendChange(
        property_id=property_id,
        candidate_id=latest.candidate_id,
        address=address,
        city=city,
        zip_code=zip_code,
        current_health_score=latest.lifecycle_health_score,
        previous_health_score=previous.lifecycle_health_score,
        health_score_delta=score_delta,
        current_health_label=latest.lifecycle_health_label,
        previous_health_label=previous.lifecycle_health_label,
        health_label_changed=label_changed,
        current_open_alert_count=latest.open_alert_count,
        previous_open_alert_count=previous.open_alert_count,
        open_alert_delta=open_delta,
        current_high_or_critical_open_alert_count=(
            latest.high_or_critical_open_alert_count
        ),
        previous_high_or_critical_open_alert_count=(
            previous.high_or_critical_open_alert_count
        ),
        high_or_critical_delta=hc_delta,
        current_lifecycle_gap_count=latest.lifecycle_gap_count,
        previous_lifecycle_gap_count=previous.lifecycle_gap_count,
        lifecycle_gap_delta=gap_delta,
        current_needs_reparse_count=latest.needs_reparse_count,
        previous_needs_reparse_count=previous.needs_reparse_count,
        needs_reparse_delta=reparse_delta,
        current_needs_manual_review_count=(
            latest.needs_manual_review_count
        ),
        previous_needs_manual_review_count=(
            previous.needs_manual_review_count
        ),
        needs_manual_review_delta=manual_delta,
        trend_direction=direction,
        trend_summary=summary,
        recommended_review_action=rec,
    )


def summarize_lifecycle_health_trends(
    database_path: Optional[str] = None,
) -> CrossSiteLifecycleHealthTrendSummary:
    """Build an aggregate health trend summary across all properties.

    Counts improved, degraded, stable, and new properties. Identifies
    attention_required and needs_review current counts.

    Args:
        database_path: Path to the SQLite database.

    Returns:
        CrossSiteLifecycleHealthTrendSummary with counts and actions.
    """
    summary = CrossSiteLifecycleHealthTrendSummary()

    if not table_exists(
        "cross_site_lifecycle_health_snapshots",
        database_path=database_path,
    ):
        summary.warnings.append(
            "No health snapshots table found."
        )
        return summary

    # Get distinct property IDs with snapshots
    try:
        raw = execute_query(
            "SELECT DISTINCT property_id "
            "FROM cross_site_lifecycle_health_snapshots",
            database_path=database_path,
        )
    except Exception as e:
        summary.warnings.append(f"Error loading property IDs: {e}")
        return summary

    property_ids = [
        _row_to_dict(r)["property_id"]
        for r in raw
        if _row_to_dict(r).get("property_id")
    ]
    summary.properties_with_snapshots = len(property_ids)

    for pid in property_ids:
        change = calculate_lifecycle_health_trend_change(
            property_id=pid,
            database_path=database_path,
        )
        if not change:
            continue

        if change.trend_direction == "improved":
            summary.improved_count += 1
        elif change.trend_direction == "degraded":
            summary.degraded_count += 1
        elif change.trend_direction == "new":
            summary.new_count += 1
        else:
            summary.stable_count += 1

        if change.current_health_label == "attention_required":
            summary.attention_required_current_count += 1
        if change.current_health_label == "needs_review":
            summary.needs_review_current_count += 1

    # Recommended actions
    if summary.attention_required_current_count > 0:
        summary.recommended_next_actions.append(
            f"Review {summary.attention_required_current_count} "
            f"property(ies) with attention_required status."
        )
    if summary.degraded_count > 0:
        summary.recommended_next_actions.append(
            f"Investigate {summary.degraded_count} "
            f"property(ies) with degraded health trends."
        )
    if not summary.recommended_next_actions:
        summary.recommended_next_actions.append(
            "No immediate actions needed. Continue monitoring."
        )

    return summary


def export_lifecycle_health_trend_report(
    database_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Optional[str]:
    """Export lifecycle health trend comparison to CSV.

    Computes trend changes for all properties with snapshots and
    writes a CSV report.

    Args:
        database_path: Path to the SQLite database.
        output_dir: Directory for export. Defaults to data/exports.

    Returns:
        Path to the exported CSV, or None if no data.
    """
    if not table_exists(
        "cross_site_lifecycle_health_snapshots",
        database_path=database_path,
    ):
        logger.info("No health snapshots table. Cannot export trend report.")
        return None

    # Get distinct property IDs
    try:
        raw = execute_query(
            "SELECT DISTINCT property_id "
            "FROM cross_site_lifecycle_health_snapshots",
            database_path=database_path,
        )
    except Exception:
        return None

    property_ids = [
        _row_to_dict(r)["property_id"]
        for r in raw
        if _row_to_dict(r).get("property_id")
    ]

    if not property_ids:
        return None

    rows: List[CrossSiteLifecycleHealthTrendReportRow] = []
    for pid in property_ids:
        change = calculate_lifecycle_health_trend_change(
            property_id=pid,
            database_path=database_path,
        )
        if not change:
            continue

        row = CrossSiteLifecycleHealthTrendReportRow(
            property_id=change.property_id,
            candidate_id=change.candidate_id,
            address=change.address,
            city=change.city,
            zip_code=change.zip_code,
            current_health_score=change.current_health_score,
            previous_health_score=change.previous_health_score,
            health_score_delta=change.health_score_delta,
            current_health_label=change.current_health_label,
            previous_health_label=change.previous_health_label,
            health_label_changed=change.health_label_changed,
            current_open_alert_count=change.current_open_alert_count,
            previous_open_alert_count=change.previous_open_alert_count,
            open_alert_delta=change.open_alert_delta,
            current_high_or_critical_open_alert_count=(
                change.current_high_or_critical_open_alert_count
            ),
            previous_high_or_critical_open_alert_count=(
                change.previous_high_or_critical_open_alert_count
            ),
            high_or_critical_delta=change.high_or_critical_delta,
            current_lifecycle_gap_count=(
                change.current_lifecycle_gap_count
            ),
            previous_lifecycle_gap_count=(
                change.previous_lifecycle_gap_count
            ),
            lifecycle_gap_delta=change.lifecycle_gap_delta,
            current_needs_reparse_count=(
                change.current_needs_reparse_count
            ),
            previous_needs_reparse_count=(
                change.previous_needs_reparse_count
            ),
            needs_reparse_delta=change.needs_reparse_delta,
            current_needs_manual_review_count=(
                change.current_needs_manual_review_count
            ),
            previous_needs_manual_review_count=(
                change.previous_needs_manual_review_count
            ),
            needs_manual_review_delta=change.needs_manual_review_delta,
            trend_direction=change.trend_direction,
            trend_summary=change.trend_summary,
            recommended_review_action=change.recommended_review_action,
        )
        rows.append(row)

    if not rows:
        return None

    if not output_dir:
        output_dir = "data/exports"
    exports_path = Path(output_dir)
    exports_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"cross_site_lifecycle_health_trends_{timestamp}.csv"
    export_path = exports_path / filename

    with open(export_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=HEALTH_TREND_CSV_FIELDNAMES,
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "property_id": row.property_id,
                "candidate_id": row.candidate_id or "",
                "address": row.address,
                "city": row.city,
                "zip": row.zip_code,
                "current_health_score": row.current_health_score,
                "previous_health_score": row.previous_health_score,
                "health_score_delta": row.health_score_delta,
                "current_health_label": row.current_health_label,
                "previous_health_label": row.previous_health_label,
                "health_label_changed": row.health_label_changed,
                "current_open_alert_count": (
                    row.current_open_alert_count
                ),
                "previous_open_alert_count": (
                    row.previous_open_alert_count
                ),
                "open_alert_delta": row.open_alert_delta,
                "current_high_or_critical_open_alert_count": (
                    row.current_high_or_critical_open_alert_count
                ),
                "previous_high_or_critical_open_alert_count": (
                    row.previous_high_or_critical_open_alert_count
                ),
                "high_or_critical_delta": row.high_or_critical_delta,
                "current_lifecycle_gap_count": (
                    row.current_lifecycle_gap_count
                ),
                "previous_lifecycle_gap_count": (
                    row.previous_lifecycle_gap_count
                ),
                "lifecycle_gap_delta": row.lifecycle_gap_delta,
                "current_needs_reparse_count": (
                    row.current_needs_reparse_count
                ),
                "previous_needs_reparse_count": (
                    row.previous_needs_reparse_count
                ),
                "needs_reparse_delta": row.needs_reparse_delta,
                "current_needs_manual_review_count": (
                    row.current_needs_manual_review_count
                ),
                "previous_needs_manual_review_count": (
                    row.previous_needs_manual_review_count
                ),
                "needs_manual_review_delta": (
                    row.needs_manual_review_delta
                ),
                "trend_direction": row.trend_direction,
                "trend_summary": row.trend_summary,
                "recommended_review_action": (
                    row.recommended_review_action
                ),
            })

    logger.info(f"Health trend report exported to {export_path}")
    return str(export_path)
