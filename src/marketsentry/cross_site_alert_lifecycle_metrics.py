"""Alert Lifecycle Trend Snapshots and Throughput Metrics.

Provides append-only lifecycle metric snapshots, time-to-action metrics,
throughput metrics, and trend change analysis. Read-only except for
writing append-only lifecycle metric snapshots.

Does not mutate alert status, watchlist status, or Redfin source-of-truth
fields.

Milestone 35.
"""

import csv
import logging
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from marketsentry.database import execute_query, get_connection, table_exists
from marketsentry.models import (
    CrossSiteAlertLifecycleSnapshot,
    CrossSiteAlertLifecycleSnapshotRunResult,
    CrossSiteAlertLifecycleTrendChange,
    CrossSiteAlertThroughputMetrics,
    CrossSiteAlertTimeToActionMetrics,
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


def _safe_float(val) -> Optional[float]:
    """Safely convert a value to float or return None."""
    if val is None:
        return None
    try:
        return float(val)
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


def _has_material_change(
    current: CrossSiteAlertLifecycleSnapshot,
    previous: CrossSiteAlertLifecycleSnapshot,
) -> bool:
    """Check if there is a material change between two snapshots.

    Material changes include: alert count, open count, gap count,
    stale backlog count, throughput, or material average
    time-to-resolution change (> 0.5 days).

    Args:
        current: The newly computed snapshot.
        previous: The most recent stored snapshot.

    Returns:
        True if material change detected, False otherwise.
    """
    if current.total_alerts != previous.total_alerts:
        return True
    if current.open_alerts != previous.open_alerts:
        return True
    if current.lifecycle_gap_count != previous.lifecycle_gap_count:
        return True
    if current.stale_open_alert_count != previous.stale_open_alert_count:
        return True
    if current.triage_throughput_7d != previous.triage_throughput_7d:
        return True
    if current.resolution_throughput_7d != previous.resolution_throughput_7d:
        return True
    if current.archive_throughput_7d != previous.archive_throughput_7d:
        return True

    cur_res = current.avg_time_to_resolution_days
    prev_res = previous.avg_time_to_resolution_days
    if cur_res is not None and prev_res is not None:
        if abs(cur_res - prev_res) > 0.5:
            return True
    elif cur_res != prev_res:
        return True

    return False


def _snapshot_from_row(d: dict) -> CrossSiteAlertLifecycleSnapshot:
    """Build a snapshot model from a database row dict."""
    return CrossSiteAlertLifecycleSnapshot(
        lifecycle_snapshot_id=d.get("lifecycle_snapshot_id", 0),
        captured_at=d.get("captured_at"),
        total_alerts=d.get("total_alerts", 0),
        open_alerts=d.get("open_alerts", 0),
        acknowledged_alerts=d.get("acknowledged_alerts", 0),
        resolved_alerts=d.get("resolved_alerts", 0),
        archived_alerts=d.get("archived_alerts", 0),
        high_or_critical_open_alerts=d.get("high_or_critical_open_alerts", 0),
        lifecycle_gap_count=d.get("lifecycle_gap_count", 0),
        stale_open_alert_count=d.get("stale_open_alert_count", 0),
        needs_reparse_count=d.get("needs_reparse_count", 0),
        needs_manual_review_count=d.get("needs_manual_review_count", 0),
        no_archive_count=d.get("no_archive_count", 0),
        total_lifecycle_events=d.get("total_lifecycle_events", 0),
        triage_actions_count=d.get("triage_actions_count", 0),
        archive_actions_count=d.get("archive_actions_count", 0),
        expiration_actions_count=d.get("expiration_actions_count", 0),
        avg_time_to_first_triage_days=_safe_float(
            d.get("avg_time_to_first_triage_days"),
        ),
        median_time_to_first_triage_days=_safe_float(
            d.get("median_time_to_first_triage_days"),
        ),
        avg_time_to_resolution_days=_safe_float(
            d.get("avg_time_to_resolution_days"),
        ),
        median_time_to_resolution_days=_safe_float(
            d.get("median_time_to_resolution_days"),
        ),
        avg_time_to_archive_days=_safe_float(d.get("avg_time_to_archive_days")),
        median_time_to_archive_days=_safe_float(
            d.get("median_time_to_archive_days"),
        ),
        triage_throughput_7d=d.get("triage_throughput_7d", 0),
        resolution_throughput_7d=d.get("resolution_throughput_7d", 0),
        archive_throughput_7d=d.get("archive_throughput_7d", 0),
        active_property_count=d.get("active_property_count", 0),
        property_count_with_open_alerts=d.get(
            "property_count_with_open_alerts", 0,
        ),
        property_count_with_lifecycle_gaps=d.get(
            "property_count_with_lifecycle_gaps", 0,
        ),
        notes=d.get("notes"),
        created_at=d.get("created_at"),
    )


def _ensure_snapshot_table(database_path: Optional[str] = None) -> None:
    """Ensure the lifecycle snapshots table exists."""
    if table_exists(
        "cross_site_alert_lifecycle_snapshots", database_path=database_path,
    ):
        return

    from marketsentry.schema import (
        CREATE_CROSS_SITE_ALERT_LIFECYCLE_SNAPSHOTS_TABLE,
    )

    conn = get_connection(database_path)
    cursor = conn.cursor()
    try:
        cursor.execute(CREATE_CROSS_SITE_ALERT_LIFECYCLE_SNAPSHOTS_TABLE)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating lifecycle snapshots table: {e}")
        raise
    finally:
        conn.close()


def _insert_lifecycle_snapshot(
    snapshot: CrossSiteAlertLifecycleSnapshot,
    database_path: Optional[str] = None,
) -> int:
    """Insert a lifecycle snapshot into the database and return its ID."""
    conn = get_connection(database_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO cross_site_alert_lifecycle_snapshots (
                captured_at, total_alerts, open_alerts, acknowledged_alerts,
                resolved_alerts, archived_alerts, high_or_critical_open_alerts,
                lifecycle_gap_count, stale_open_alert_count,
                needs_reparse_count, needs_manual_review_count,
                no_archive_count, total_lifecycle_events,
                triage_actions_count, archive_actions_count,
                expiration_actions_count,
                avg_time_to_first_triage_days,
                median_time_to_first_triage_days,
                avg_time_to_resolution_days,
                median_time_to_resolution_days,
                avg_time_to_archive_days,
                median_time_to_archive_days,
                triage_throughput_7d, resolution_throughput_7d,
                archive_throughput_7d,
                active_property_count, property_count_with_open_alerts,
                property_count_with_lifecycle_gaps, notes
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?, ?,
                ?,
                ?, ?,
                ?, ?
            )
            """,
            (
                snapshot.captured_at,
                snapshot.total_alerts,
                snapshot.open_alerts,
                snapshot.acknowledged_alerts,
                snapshot.resolved_alerts,
                snapshot.archived_alerts,
                snapshot.high_or_critical_open_alerts,
                snapshot.lifecycle_gap_count,
                snapshot.stale_open_alert_count,
                snapshot.needs_reparse_count,
                snapshot.needs_manual_review_count,
                snapshot.no_archive_count,
                snapshot.total_lifecycle_events,
                snapshot.triage_actions_count,
                snapshot.archive_actions_count,
                snapshot.expiration_actions_count,
                snapshot.avg_time_to_first_triage_days,
                snapshot.median_time_to_first_triage_days,
                snapshot.avg_time_to_resolution_days,
                snapshot.median_time_to_resolution_days,
                snapshot.avg_time_to_archive_days,
                snapshot.median_time_to_archive_days,
                snapshot.triage_throughput_7d,
                snapshot.resolution_throughput_7d,
                snapshot.archive_throughput_7d,
                snapshot.active_property_count,
                snapshot.property_count_with_open_alerts,
                snapshot.property_count_with_lifecycle_gaps,
                snapshot.notes,
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting lifecycle snapshot: {e}")
        raise
    finally:
        conn.close()


# ── Public API ──


def calculate_time_to_action_metrics(
    database_path: Optional[str] = None,
) -> CrossSiteAlertTimeToActionMetrics:
    """Calculate time-to-first-triage, time-to-resolution, and time-to-archive.

    Computes average and median days from alert creation to the first
    relevant action. Returns None/0 safely when no qualifying events exist.

    Args:
        database_path: Path to database file.

    Returns:
        CrossSiteAlertTimeToActionMetrics with avg/median/count/skipped.
    """
    metrics = CrossSiteAlertTimeToActionMetrics()

    if not table_exists("cross_site_trend_alerts", database_path=database_path):
        return metrics
    if not table_exists(
        "cross_site_alert_triage_actions", database_path=database_path,
    ):
        return metrics

    # Total alert count
    total_query = "SELECT COUNT(*) as cnt FROM cross_site_trend_alerts"
    total_rows = execute_query(total_query, database_path=database_path)
    total_alerts = (
        _row_to_dict(total_rows[0]).get("cnt", 0) if total_rows else 0
    )

    # Time-to-first-triage: alert created to first action of any type
    triage_query = """
        SELECT
            a.alert_id,
            a.created_at as alert_created_at,
            MIN(t.applied_at) as first_action_at
        FROM cross_site_trend_alerts a
        INNER JOIN cross_site_alert_triage_actions t
            ON a.alert_id = t.alert_id
        GROUP BY a.alert_id
    """
    triage_rows = execute_query(triage_query, database_path=database_path)
    triage_deltas: List[float] = []
    for row in triage_rows:
        d = _row_to_dict(row)
        created = _parse_datetime(d.get("alert_created_at"))
        first_action = _parse_datetime(d.get("first_action_at"))
        if created and first_action:
            delta = (first_action - created).total_seconds() / 86400.0
            triage_deltas.append(max(delta, 0.0))

    metrics.triage_count = len(triage_deltas)
    metrics.triage_skipped = total_alerts - metrics.triage_count
    if triage_deltas:
        metrics.avg_time_to_first_triage_days = round(
            sum(triage_deltas) / len(triage_deltas), 2,
        )
        metrics.median_time_to_first_triage_days = round(
            statistics.median(triage_deltas), 2,
        )

    # Time-to-resolution: alert created to first resolved action
    resolution_query = """
        SELECT
            a.alert_id,
            a.created_at as alert_created_at,
            MIN(t.applied_at) as first_resolved_at
        FROM cross_site_trend_alerts a
        INNER JOIN cross_site_alert_triage_actions t
            ON a.alert_id = t.alert_id
        WHERE t.new_status = 'resolved'
        GROUP BY a.alert_id
    """
    resolution_rows = execute_query(
        resolution_query, database_path=database_path,
    )
    resolution_deltas: List[float] = []
    for row in resolution_rows:
        d = _row_to_dict(row)
        created = _parse_datetime(d.get("alert_created_at"))
        first_resolved = _parse_datetime(d.get("first_resolved_at"))
        if created and first_resolved:
            delta = (first_resolved - created).total_seconds() / 86400.0
            resolution_deltas.append(max(delta, 0.0))

    metrics.resolution_count = len(resolution_deltas)
    metrics.resolution_skipped = total_alerts - metrics.resolution_count
    if resolution_deltas:
        metrics.avg_time_to_resolution_days = round(
            sum(resolution_deltas) / len(resolution_deltas), 2,
        )
        metrics.median_time_to_resolution_days = round(
            statistics.median(resolution_deltas), 2,
        )

    # Time-to-archive: alert created to first archived action
    archive_query = """
        SELECT
            a.alert_id,
            a.created_at as alert_created_at,
            MIN(t.applied_at) as first_archived_at
        FROM cross_site_trend_alerts a
        INNER JOIN cross_site_alert_triage_actions t
            ON a.alert_id = t.alert_id
        WHERE t.new_status = 'archived'
        GROUP BY a.alert_id
    """
    archive_rows = execute_query(archive_query, database_path=database_path)
    archive_deltas: List[float] = []
    for row in archive_rows:
        d = _row_to_dict(row)
        created = _parse_datetime(d.get("alert_created_at"))
        first_archived = _parse_datetime(d.get("first_archived_at"))
        if created and first_archived:
            delta = (first_archived - created).total_seconds() / 86400.0
            archive_deltas.append(max(delta, 0.0))

    metrics.archive_count = len(archive_deltas)
    metrics.archive_skipped = total_alerts - metrics.archive_count
    if archive_deltas:
        metrics.avg_time_to_archive_days = round(
            sum(archive_deltas) / len(archive_deltas), 2,
        )
        metrics.median_time_to_archive_days = round(
            statistics.median(archive_deltas), 2,
        )

    return metrics


def calculate_throughput_metrics(
    database_path: Optional[str] = None,
) -> CrossSiteAlertThroughputMetrics:
    """Calculate triage/resolution/archive throughput for recent periods.

    Counts lifecycle actions in the last 7 and 30 days.

    Args:
        database_path: Path to database file.

    Returns:
        CrossSiteAlertThroughputMetrics with 7-day and 30-day counts.
    """
    metrics = CrossSiteAlertThroughputMetrics()

    if not table_exists(
        "cross_site_alert_triage_actions", database_path=database_path,
    ):
        return metrics

    now = datetime.utcnow()
    cutoff_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

    # 7-day triage throughput
    q = """
        SELECT COUNT(*) as cnt FROM cross_site_alert_triage_actions
        WHERE applied_at >= ? AND triage_export_id LIKE 'triage_%'
    """
    rows = execute_query(q, (cutoff_7d,), database_path=database_path)
    metrics.triage_throughput_7d = (
        _row_to_dict(rows[0]).get("cnt", 0) if rows else 0
    )

    # 7-day resolution throughput
    q = """
        SELECT COUNT(*) as cnt FROM cross_site_alert_triage_actions
        WHERE applied_at >= ? AND new_status = 'resolved'
    """
    rows = execute_query(q, (cutoff_7d,), database_path=database_path)
    metrics.resolution_throughput_7d = (
        _row_to_dict(rows[0]).get("cnt", 0) if rows else 0
    )

    # 7-day archive throughput
    q = """
        SELECT COUNT(*) as cnt FROM cross_site_alert_triage_actions
        WHERE applied_at >= ? AND new_status = 'archived'
    """
    rows = execute_query(q, (cutoff_7d,), database_path=database_path)
    metrics.archive_throughput_7d = (
        _row_to_dict(rows[0]).get("cnt", 0) if rows else 0
    )

    # 30-day triage throughput
    q = """
        SELECT COUNT(*) as cnt FROM cross_site_alert_triage_actions
        WHERE applied_at >= ? AND triage_export_id LIKE 'triage_%'
    """
    rows = execute_query(q, (cutoff_30d,), database_path=database_path)
    metrics.triage_throughput_30d = (
        _row_to_dict(rows[0]).get("cnt", 0) if rows else 0
    )

    # 30-day resolution throughput
    q = """
        SELECT COUNT(*) as cnt FROM cross_site_alert_triage_actions
        WHERE applied_at >= ? AND new_status = 'resolved'
    """
    rows = execute_query(q, (cutoff_30d,), database_path=database_path)
    metrics.resolution_throughput_30d = (
        _row_to_dict(rows[0]).get("cnt", 0) if rows else 0
    )

    # 30-day archive throughput
    q = """
        SELECT COUNT(*) as cnt FROM cross_site_alert_triage_actions
        WHERE applied_at >= ? AND new_status = 'archived'
    """
    rows = execute_query(q, (cutoff_30d,), database_path=database_path)
    metrics.archive_throughput_30d = (
        _row_to_dict(rows[0]).get("cnt", 0) if rows else 0
    )

    return metrics


def calculate_lifecycle_snapshot_metrics(
    database_path: Optional[str] = None,
) -> CrossSiteAlertLifecycleSnapshot:
    """Gather current lifecycle data and compute snapshot metrics.

    Queries alert status counts, lifecycle event counts, stale/backlog
    indicators, time-to-action metrics, throughput metrics, and
    property-level counts. Does not write to the database.

    Args:
        database_path: Path to database file.

    Returns:
        CrossSiteAlertLifecycleSnapshot with computed metrics.
    """
    snapshot = CrossSiteAlertLifecycleSnapshot()
    snapshot.captured_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    alerts_exist = table_exists(
        "cross_site_trend_alerts", database_path=database_path,
    )
    actions_exist = table_exists(
        "cross_site_alert_triage_actions", database_path=database_path,
    )

    if not alerts_exist:
        return snapshot

    # Alert status counts
    status_query = """
        SELECT alert_status, COUNT(*) as cnt
        FROM cross_site_trend_alerts
        GROUP BY alert_status
    """
    status_rows = execute_query(status_query, database_path=database_path)
    total = 0
    for row in status_rows:
        d = _row_to_dict(row)
        status = d.get("alert_status", "")
        cnt = d.get("cnt", 0)
        total += cnt
        if status == "open":
            snapshot.open_alerts = cnt
        elif status == "acknowledged":
            snapshot.acknowledged_alerts = cnt
        elif status == "resolved":
            snapshot.resolved_alerts = cnt
        elif status == "archived":
            snapshot.archived_alerts = cnt
    snapshot.total_alerts = total

    # High/critical open alerts
    hc_query = """
        SELECT COUNT(*) as cnt FROM cross_site_trend_alerts
        WHERE severity IN ('high', 'critical') AND alert_status = 'open'
    """
    hc_rows = execute_query(hc_query, database_path=database_path)
    snapshot.high_or_critical_open_alerts = (
        _row_to_dict(hc_rows[0]).get("cnt", 0) if hc_rows else 0
    )

    # Stale open alerts (open for > 7 days)
    stale_query = """
        SELECT COUNT(*) as cnt FROM cross_site_trend_alerts
        WHERE alert_status = 'open'
        AND created_at <= datetime('now', '-7 days')
    """
    stale_rows = execute_query(stale_query, database_path=database_path)
    snapshot.stale_open_alert_count = (
        _row_to_dict(stale_rows[0]).get("cnt", 0) if stale_rows else 0
    )

    if actions_exist:
        # Total lifecycle events
        events_query = (
            "SELECT COUNT(*) as cnt FROM cross_site_alert_triage_actions"
        )
        event_rows = execute_query(events_query, database_path=database_path)
        snapshot.total_lifecycle_events = (
            _row_to_dict(event_rows[0]).get("cnt", 0) if event_rows else 0
        )

        # Action counts by workflow prefix
        for prefix, attr in [
            ("triage_%", "triage_actions_count"),
            ("archive_%", "archive_actions_count"),
            ("expiration_%", "expiration_actions_count"),
        ]:
            q = """
                SELECT COUNT(*) as cnt FROM cross_site_alert_triage_actions
                WHERE triage_export_id LIKE ?
            """
            rows = execute_query(q, (prefix,), database_path=database_path)
            setattr(
                snapshot, attr,
                _row_to_dict(rows[0]).get("cnt", 0) if rows else 0,
            )

        # Needs reparse count
        q = """
            SELECT COUNT(DISTINCT alert_id) as cnt
            FROM cross_site_alert_triage_actions
            WHERE LOWER(triage_notes) LIKE '%needs_reparse%'
        """
        rows = execute_query(q, database_path=database_path)
        snapshot.needs_reparse_count = (
            _row_to_dict(rows[0]).get("cnt", 0) if rows else 0
        )

        # Needs manual review count
        q = """
            SELECT COUNT(DISTINCT alert_id) as cnt
            FROM cross_site_alert_triage_actions
            WHERE LOWER(triage_notes) LIKE '%manual_review%'
        """
        rows = execute_query(q, database_path=database_path)
        snapshot.needs_manual_review_count = (
            _row_to_dict(rows[0]).get("cnt", 0) if rows else 0
        )

        # No archive count
        q = """
            SELECT COUNT(DISTINCT alert_id) as cnt
            FROM cross_site_alert_triage_actions
            WHERE LOWER(triage_notes) LIKE '%no_archive%'
        """
        rows = execute_query(q, database_path=database_path)
        snapshot.no_archive_count = (
            _row_to_dict(rows[0]).get("cnt", 0) if rows else 0
        )

    # Lifecycle gaps via M34 module
    try:
        from marketsentry.cross_site_alert_lifecycle import (
            detect_alert_lifecycle_gaps,
        )

        gaps = detect_alert_lifecycle_gaps(database_path=database_path)
        snapshot.lifecycle_gap_count = len(gaps)
    except Exception:
        snapshot.lifecycle_gap_count = 0

    # Time-to-action metrics
    tta = calculate_time_to_action_metrics(database_path=database_path)
    snapshot.avg_time_to_first_triage_days = tta.avg_time_to_first_triage_days
    snapshot.median_time_to_first_triage_days = (
        tta.median_time_to_first_triage_days
    )
    snapshot.avg_time_to_resolution_days = tta.avg_time_to_resolution_days
    snapshot.median_time_to_resolution_days = (
        tta.median_time_to_resolution_days
    )
    snapshot.avg_time_to_archive_days = tta.avg_time_to_archive_days
    snapshot.median_time_to_archive_days = tta.median_time_to_archive_days

    # Throughput metrics
    tp = calculate_throughput_metrics(database_path=database_path)
    snapshot.triage_throughput_7d = tp.triage_throughput_7d
    snapshot.resolution_throughput_7d = tp.resolution_throughput_7d
    snapshot.archive_throughput_7d = tp.archive_throughput_7d

    # Property counts
    if table_exists("watched_properties", database_path=database_path):
        q = """
            SELECT COUNT(*) as cnt FROM watched_properties
            WHERE active_watch_status = 1
        """
        rows = execute_query(q, database_path=database_path)
        snapshot.active_property_count = (
            _row_to_dict(rows[0]).get("cnt", 0) if rows else 0
        )

    q = """
        SELECT COUNT(DISTINCT property_id) as cnt FROM cross_site_trend_alerts
        WHERE alert_status = 'open'
    """
    rows = execute_query(q, database_path=database_path)
    snapshot.property_count_with_open_alerts = (
        _row_to_dict(rows[0]).get("cnt", 0) if rows else 0
    )

    # Properties with lifecycle gaps
    try:
        from marketsentry.cross_site_alert_lifecycle import (
            detect_alert_lifecycle_gaps,
        )

        gaps = detect_alert_lifecycle_gaps(database_path=database_path)
        gap_properties = set()
        for g in gaps:
            pid = (
                g.get("property_id")
                if isinstance(g, dict)
                else getattr(g, "property_id", None)
            )
            if pid:
                gap_properties.add(pid)
        snapshot.property_count_with_lifecycle_gaps = len(gap_properties)
    except Exception:
        snapshot.property_count_with_lifecycle_gaps = 0

    return snapshot


def create_alert_lifecycle_snapshot(
    database_path: Optional[str] = None,
    force: bool = False,
) -> CrossSiteAlertLifecycleSnapshotRunResult:
    """Create and store an append-only lifecycle snapshot.

    Computes current metrics and inserts a new row into the
    cross_site_alert_lifecycle_snapshots table. Skips same-day
    duplicates if no material change unless --force is used.

    Args:
        database_path: Path to database file.
        force: If True, create snapshot even if same-day with no change.

    Returns:
        CrossSiteAlertLifecycleSnapshotRunResult with snapshot and status.
    """
    result = CrossSiteAlertLifecycleSnapshotRunResult()

    _ensure_snapshot_table(database_path)

    snapshot = calculate_lifecycle_snapshot_metrics(
        database_path=database_path,
    )

    if not force:
        latest = get_latest_lifecycle_snapshot(database_path=database_path)
        if latest and _is_same_day(snapshot.captured_at, latest.captured_at):
            if not _has_material_change(snapshot, latest):
                result.was_skipped = True
                result.skip_reason = (
                    "Same-day snapshot with no material change. "
                    "Use --force to override."
                )
                result.snapshot = latest
                result.snapshot_id = latest.lifecycle_snapshot_id
                return result

    snapshot_id = _insert_lifecycle_snapshot(snapshot, database_path)
    snapshot.lifecycle_snapshot_id = snapshot_id
    result.snapshot = snapshot
    result.snapshot_id = snapshot_id

    latest_for_trend = get_latest_lifecycle_snapshot(
        database_path=database_path,
    )
    previous = get_previous_lifecycle_snapshot(database_path=database_path)
    if previous and latest_for_trend:
        result.trend_change = calculate_lifecycle_trend_change(
            latest_for_trend, previous,
        )

    return result


def get_latest_lifecycle_snapshot(
    database_path: Optional[str] = None,
) -> Optional[CrossSiteAlertLifecycleSnapshot]:
    """Retrieve the most recent lifecycle snapshot from the database.

    Args:
        database_path: Path to database file.

    Returns:
        CrossSiteAlertLifecycleSnapshot or None if no snapshots exist.
    """
    if not table_exists(
        "cross_site_alert_lifecycle_snapshots", database_path=database_path,
    ):
        return None

    query = """
        SELECT * FROM cross_site_alert_lifecycle_snapshots
        ORDER BY captured_at DESC LIMIT 1
    """
    rows = execute_query(query, database_path=database_path)
    if not rows:
        return None

    return _snapshot_from_row(_row_to_dict(rows[0]))


def get_previous_lifecycle_snapshot(
    database_path: Optional[str] = None,
) -> Optional[CrossSiteAlertLifecycleSnapshot]:
    """Retrieve the second-most-recent lifecycle snapshot.

    Args:
        database_path: Path to database file.

    Returns:
        CrossSiteAlertLifecycleSnapshot or None if fewer than two exist.
    """
    if not table_exists(
        "cross_site_alert_lifecycle_snapshots", database_path=database_path,
    ):
        return None

    query = """
        SELECT * FROM cross_site_alert_lifecycle_snapshots
        ORDER BY captured_at DESC LIMIT 1 OFFSET 1
    """
    rows = execute_query(query, database_path=database_path)
    if not rows:
        return None

    return _snapshot_from_row(_row_to_dict(rows[0]))


def calculate_lifecycle_trend_change(
    current: CrossSiteAlertLifecycleSnapshot,
    previous: CrossSiteAlertLifecycleSnapshot,
) -> CrossSiteAlertLifecycleTrendChange:
    """Compute deltas and trend direction between two snapshots.

    Determines whether the trend is improving, worsening, or stable
    based on open alerts, gaps, stale counts, and time-to-resolution.

    Args:
        current: The more recent snapshot.
        previous: The older snapshot.

    Returns:
        CrossSiteAlertLifecycleTrendChange with deltas and analysis.
    """
    change = CrossSiteAlertLifecycleTrendChange(
        current_snapshot_id=current.lifecycle_snapshot_id,
        current_captured_at=current.captured_at,
        previous_snapshot_id=previous.lifecycle_snapshot_id,
        previous_captured_at=previous.captured_at,
        total_alerts_current=current.total_alerts,
        total_alerts_previous=previous.total_alerts,
        total_alerts_delta=current.total_alerts - previous.total_alerts,
        open_alerts_current=current.open_alerts,
        open_alerts_previous=previous.open_alerts,
        open_alerts_delta=current.open_alerts - previous.open_alerts,
        lifecycle_gap_count_current=current.lifecycle_gap_count,
        lifecycle_gap_count_previous=previous.lifecycle_gap_count,
        lifecycle_gap_count_delta=(
            current.lifecycle_gap_count - previous.lifecycle_gap_count
        ),
        stale_open_alert_count_current=current.stale_open_alert_count,
        stale_open_alert_count_previous=previous.stale_open_alert_count,
        stale_open_alert_count_delta=(
            current.stale_open_alert_count - previous.stale_open_alert_count
        ),
        avg_time_to_resolution_current=current.avg_time_to_resolution_days,
        avg_time_to_resolution_previous=previous.avg_time_to_resolution_days,
        triage_throughput_7d_current=current.triage_throughput_7d,
        triage_throughput_7d_previous=previous.triage_throughput_7d,
        triage_throughput_7d_delta=(
            current.triage_throughput_7d - previous.triage_throughput_7d
        ),
        resolution_throughput_7d_current=current.resolution_throughput_7d,
        resolution_throughput_7d_previous=previous.resolution_throughput_7d,
        resolution_throughput_7d_delta=(
            current.resolution_throughput_7d
            - previous.resolution_throughput_7d
        ),
        archive_throughput_7d_current=current.archive_throughput_7d,
        archive_throughput_7d_previous=previous.archive_throughput_7d,
        archive_throughput_7d_delta=(
            current.archive_throughput_7d - previous.archive_throughput_7d
        ),
    )

    # Resolution time delta
    if (
        current.avg_time_to_resolution_days is not None
        and previous.avg_time_to_resolution_days is not None
    ):
        change.avg_time_to_resolution_delta = round(
            current.avg_time_to_resolution_days
            - previous.avg_time_to_resolution_days,
            2,
        )

    # Determine trend direction
    improving = 0
    worsening = 0

    if change.open_alerts_delta < 0:
        improving += 1
    elif change.open_alerts_delta > 0:
        worsening += 1

    if change.lifecycle_gap_count_delta < 0:
        improving += 1
    elif change.lifecycle_gap_count_delta > 0:
        worsening += 1

    if change.stale_open_alert_count_delta < 0:
        improving += 1
    elif change.stale_open_alert_count_delta > 0:
        worsening += 1

    if (
        change.avg_time_to_resolution_delta is not None
        and change.avg_time_to_resolution_delta < -0.5
    ):
        improving += 1
    elif (
        change.avg_time_to_resolution_delta is not None
        and change.avg_time_to_resolution_delta > 0.5
    ):
        worsening += 1

    if improving > worsening:
        change.trend_direction = "improving"
    elif worsening > improving:
        change.trend_direction = "worsening"
    else:
        change.trend_direction = "stable"

    # Generate summary
    parts = []
    if change.open_alerts_delta != 0:
        direction = (
            "increased" if change.open_alerts_delta > 0 else "decreased"
        )
        parts.append(
            f"Open alerts {direction} by {abs(change.open_alerts_delta)}",
        )
    if change.lifecycle_gap_count_delta != 0:
        direction = (
            "increased"
            if change.lifecycle_gap_count_delta > 0
            else "decreased"
        )
        parts.append(
            f"Lifecycle gaps {direction} "
            f"by {abs(change.lifecycle_gap_count_delta)}",
        )
    if change.stale_open_alert_count_delta != 0:
        direction = (
            "increased"
            if change.stale_open_alert_count_delta > 0
            else "decreased"
        )
        parts.append(
            f"Stale alerts {direction} "
            f"by {abs(change.stale_open_alert_count_delta)}",
        )

    change.trend_summary = (
        "; ".join(parts) if parts else "No material changes"
    )

    # Recommended action
    if change.trend_direction == "worsening":
        change.recommended_review_action = (
            "Review open alerts and lifecycle gaps. "
            "Consider triage session."
        )
    elif change.trend_direction == "improving":
        change.recommended_review_action = (
            "Trend improving. Continue current workflow."
        )
    else:
        change.recommended_review_action = (
            "No action needed. Metrics stable."
        )

    return change


TREND_REPORT_FIELDNAMES = [
    "current_snapshot_id",
    "current_captured_at",
    "previous_snapshot_id",
    "previous_captured_at",
    "total_alerts_current",
    "total_alerts_previous",
    "total_alerts_delta",
    "open_alerts_current",
    "open_alerts_previous",
    "open_alerts_delta",
    "lifecycle_gap_count_current",
    "lifecycle_gap_count_previous",
    "lifecycle_gap_count_delta",
    "stale_open_alert_count_current",
    "stale_open_alert_count_previous",
    "stale_open_alert_count_delta",
    "avg_time_to_resolution_current",
    "avg_time_to_resolution_previous",
    "avg_time_to_resolution_delta",
    "triage_throughput_7d_current",
    "triage_throughput_7d_previous",
    "triage_throughput_7d_delta",
    "resolution_throughput_7d_current",
    "resolution_throughput_7d_previous",
    "resolution_throughput_7d_delta",
    "archive_throughput_7d_current",
    "archive_throughput_7d_previous",
    "archive_throughput_7d_delta",
    "trend_direction",
    "trend_summary",
    "recommended_review_action",
]


def export_alert_lifecycle_trend_report(
    database_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Optional[str]:
    """Export lifecycle trend comparison to CSV.

    Compares the latest and previous snapshots, computes trend changes,
    and writes a single-row CSV to the output directory.

    Args:
        database_path: Path to database file.
        output_dir: Directory for export. Defaults to data/exports.

    Returns:
        Path to the exported CSV, or None if insufficient data.
    """
    latest = get_latest_lifecycle_snapshot(database_path=database_path)
    if not latest:
        logger.info(
            "No lifecycle snapshots found. Cannot export trend report.",
        )
        return None

    previous = get_previous_lifecycle_snapshot(database_path=database_path)

    if previous:
        change = calculate_lifecycle_trend_change(latest, previous)
    else:
        change = CrossSiteAlertLifecycleTrendChange(
            current_snapshot_id=latest.lifecycle_snapshot_id,
            current_captured_at=latest.captured_at,
            total_alerts_current=latest.total_alerts,
            open_alerts_current=latest.open_alerts,
            lifecycle_gap_count_current=latest.lifecycle_gap_count,
            stale_open_alert_count_current=latest.stale_open_alert_count,
            avg_time_to_resolution_current=(
                latest.avg_time_to_resolution_days
            ),
            triage_throughput_7d_current=latest.triage_throughput_7d,
            resolution_throughput_7d_current=latest.resolution_throughput_7d,
            archive_throughput_7d_current=latest.archive_throughput_7d,
            trend_direction="baseline",
            trend_summary="First snapshot. No comparison available.",
            recommended_review_action=(
                "Baseline established. Continue monitoring."
            ),
        )

    if not output_dir:
        output_dir = "data/exports"
    exports_path = Path(output_dir)
    exports_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"cross_site_alert_lifecycle_trends_{timestamp}.csv"
    export_path = exports_path / filename

    row_data = {
        "current_snapshot_id": change.current_snapshot_id,
        "current_captured_at": change.current_captured_at or "",
        "previous_snapshot_id": change.previous_snapshot_id or "",
        "previous_captured_at": change.previous_captured_at or "",
        "total_alerts_current": change.total_alerts_current,
        "total_alerts_previous": change.total_alerts_previous,
        "total_alerts_delta": change.total_alerts_delta,
        "open_alerts_current": change.open_alerts_current,
        "open_alerts_previous": change.open_alerts_previous,
        "open_alerts_delta": change.open_alerts_delta,
        "lifecycle_gap_count_current": change.lifecycle_gap_count_current,
        "lifecycle_gap_count_previous": change.lifecycle_gap_count_previous,
        "lifecycle_gap_count_delta": change.lifecycle_gap_count_delta,
        "stale_open_alert_count_current": (
            change.stale_open_alert_count_current
        ),
        "stale_open_alert_count_previous": (
            change.stale_open_alert_count_previous
        ),
        "stale_open_alert_count_delta": change.stale_open_alert_count_delta,
        "avg_time_to_resolution_current": (
            change.avg_time_to_resolution_current
            if change.avg_time_to_resolution_current is not None
            else ""
        ),
        "avg_time_to_resolution_previous": (
            change.avg_time_to_resolution_previous
            if change.avg_time_to_resolution_previous is not None
            else ""
        ),
        "avg_time_to_resolution_delta": (
            change.avg_time_to_resolution_delta
            if change.avg_time_to_resolution_delta is not None
            else ""
        ),
        "triage_throughput_7d_current": change.triage_throughput_7d_current,
        "triage_throughput_7d_previous": change.triage_throughput_7d_previous,
        "triage_throughput_7d_delta": change.triage_throughput_7d_delta,
        "resolution_throughput_7d_current": (
            change.resolution_throughput_7d_current
        ),
        "resolution_throughput_7d_previous": (
            change.resolution_throughput_7d_previous
        ),
        "resolution_throughput_7d_delta": (
            change.resolution_throughput_7d_delta
        ),
        "archive_throughput_7d_current": change.archive_throughput_7d_current,
        "archive_throughput_7d_previous": (
            change.archive_throughput_7d_previous
        ),
        "archive_throughput_7d_delta": change.archive_throughput_7d_delta,
        "trend_direction": change.trend_direction,
        "trend_summary": change.trend_summary,
        "recommended_review_action": change.recommended_review_action,
    }

    with open(export_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TREND_REPORT_FIELDNAMES)
        writer.writeheader()
        writer.writerow(row_data)

    logger.info(f"Lifecycle trend report exported to {export_path}")
    return str(export_path)
