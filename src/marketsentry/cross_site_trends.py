"""Cross-site analytics trend snapshots.

Tracks how cross-site analytics change over time for watched properties.
Snapshots are append-only and preserve historical analytics data.

Cross-site trend data remains validation/check data. It does not overwrite
Redfin source-of-truth fields, user decisions, or watchlist status.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from marketsentry.cross_site_analytics import analyze_cross_site_observations
from marketsentry.database import execute_query, get_connection, init_db, table_exists
from marketsentry.logging_config import logger
from marketsentry.models import (
    CrossSiteAnalyticsResult,
    CrossSiteAnalyticsSnapshot,
    CrossSiteTrendChange,
    CrossSiteTrendReportRow,
    CrossSiteTrendRunResult,
    CrossSiteTrendSummary,
)


# ---------------------------------------------------------------------------
# Snapshot creation
# ---------------------------------------------------------------------------


def create_cross_site_analytics_snapshots(
    database_path: Optional[str] = None,
    force: bool = False,
) -> CrossSiteTrendRunResult:
    """Create analytics snapshots for all active watched properties.

    Computes current analytics using Milestone 24 logic and persists
    one snapshot per property when analytics exist. Avoids duplicate
    same-day/no-change snapshots by default.

    Args:
        database_path: Optional database path.
        force: If True, create snapshot even when no material change.

    Returns:
        CrossSiteTrendRunResult with counts and diagnostics.
    """
    result = CrossSiteTrendRunResult()

    try:
        # Ensure table exists
        _ensure_snapshots_table(database_path)

        # Get active watched properties
        properties = _get_active_properties(database_path)
        result.properties_scanned = len(properties)

        if not properties:
            result.notes = "No active watched properties found"
            return result

        for prop in properties:
            property_id = prop["property_id"]

            try:
                # Compute current analytics
                analytics = analyze_cross_site_observations(
                    property_id, database_path
                )

                # Skip if no meaningful analytics (no cross-site data)
                if not analytics.confidence_metrics:
                    continue

                result.analytics_computed += 1

                # Build snapshot from analytics
                snapshot = _analytics_to_snapshot(analytics, prop)

                # Check for material change vs previous
                previous = get_latest_cross_site_analytics_snapshot(
                    property_id, database_path
                )

                if previous and not force:
                    if not _has_material_change(snapshot, previous):
                        result.snapshots_skipped_no_change += 1
                        continue

                # Persist snapshot
                snapshot_id = _insert_snapshot(snapshot, database_path)
                snapshot.snapshot_id = snapshot_id
                result.snapshots_created += 1

                # Check trend change
                if previous:
                    change = calculate_cross_site_trend_change(
                        snapshot, previous, prop
                    )
                    if change.has_material_change:
                        result.trend_changes_detected += 1

            except Exception as e:
                msg = f"Error processing property {property_id}: {e}"
                logger.error(msg)
                result.errors.append(msg)

    except Exception as e:
        msg = f"Error creating cross-site analytics snapshots: {e}"
        logger.error(msg)
        result.errors.append(msg)

    return result


# ---------------------------------------------------------------------------
# Snapshot retrieval
# ---------------------------------------------------------------------------


def get_latest_cross_site_analytics_snapshot(
    property_id: int,
    database_path: Optional[str] = None,
) -> Optional[CrossSiteAnalyticsSnapshot]:
    """Get the most recent analytics snapshot for a property.

    Args:
        property_id: Watched property ID.
        database_path: Optional database path.

    Returns:
        CrossSiteAnalyticsSnapshot or None.
    """
    try:
        if not table_exists("cross_site_analytics_snapshots", database_path):
            return None

        query = """
        SELECT *
        FROM cross_site_analytics_snapshots
        WHERE property_id = ?
        ORDER BY captured_at DESC
        LIMIT 1
        """
        results = execute_query(query, (property_id,), database_path=database_path)
        if results:
            return _row_to_snapshot(dict(results[0]))
    except Exception as e:
        logger.error(
            f"Error getting latest snapshot for property {property_id}: {e}"
        )
    return None


def get_previous_cross_site_analytics_snapshot(
    property_id: int,
    database_path: Optional[str] = None,
) -> Optional[CrossSiteAnalyticsSnapshot]:
    """Get the second-most-recent analytics snapshot for a property.

    Args:
        property_id: Watched property ID.
        database_path: Optional database path.

    Returns:
        CrossSiteAnalyticsSnapshot or None.
    """
    try:
        if not table_exists("cross_site_analytics_snapshots", database_path):
            return None

        query = """
        SELECT *
        FROM cross_site_analytics_snapshots
        WHERE property_id = ?
        ORDER BY captured_at DESC
        LIMIT 1 OFFSET 1
        """
        results = execute_query(query, (property_id,), database_path=database_path)
        if results:
            return _row_to_snapshot(dict(results[0]))
    except Exception as e:
        logger.error(
            f"Error getting previous snapshot for property {property_id}: {e}"
        )
    return None


# ---------------------------------------------------------------------------
# Trend change calculation
# ---------------------------------------------------------------------------


def calculate_cross_site_trend_change(
    current: CrossSiteAnalyticsSnapshot,
    previous: CrossSiteAnalyticsSnapshot,
    prop: Optional[Dict] = None,
) -> CrossSiteTrendChange:
    """Calculate trend change between two snapshots.

    Args:
        current: Current (newer) snapshot.
        previous: Previous (older) snapshot.
        prop: Optional property dict for address/city/zip.

    Returns:
        CrossSiteTrendChange with change details.
    """
    change = CrossSiteTrendChange(
        property_id=current.property_id,
        current_snapshot_id=current.snapshot_id,
        previous_snapshot_id=previous.snapshot_id,
        current_captured_at=current.captured_at,
        previous_captured_at=previous.captured_at,
    )

    if prop:
        change.address = prop.get("address")
        change.city = prop.get("city")
        change.zip = prop.get("zip")

    # Overall confidence change
    if (
        current.overall_cross_site_confidence_score is not None
        and previous.overall_cross_site_confidence_score is not None
    ):
        change.overall_confidence_change = round(
            current.overall_cross_site_confidence_score
            - previous.overall_cross_site_confidence_score,
            4,
        )

    # Severity label change
    change.current_severity_label = current.discrepancy_severity_label
    change.previous_severity_label = previous.discrepancy_severity_label
    change.severity_label_changed = (
        current.discrepancy_severity_label != previous.discrepancy_severity_label
    )

    # Manual review priority change
    change.current_manual_review_priority = current.cross_site_manual_review_priority
    change.previous_manual_review_priority = previous.cross_site_manual_review_priority
    change.manual_review_priority_changed = (
        current.cross_site_manual_review_priority
        != previous.cross_site_manual_review_priority
    )

    # Agreement score changes
    change.price_agreement_change = _score_delta(
        current.weighted_price_agreement_score,
        previous.weighted_price_agreement_score,
    )
    change.status_agreement_change = _score_delta(
        current.weighted_status_agreement_score,
        previous.weighted_status_agreement_score,
    )
    change.dom_agreement_change = _score_delta(
        current.weighted_dom_agreement_score,
        previous.weighted_dom_agreement_score,
    )

    # Source count changes
    change.low_confidence_source_count_changed = (
        current.low_confidence_source_count != previous.low_confidence_source_count
    )
    change.stale_source_count_changed = (
        current.stale_source_count != previous.stale_source_count
    )

    # Discrepancy flag changes
    current_flags = (
        current.price_discrepancy_flag,
        current.status_discrepancy_flag,
        current.dom_discrepancy_flag,
    )
    previous_flags = (
        previous.price_discrepancy_flag,
        previous.status_discrepancy_flag,
        previous.dom_discrepancy_flag,
    )
    change.discrepancy_flag_changed = current_flags != previous_flags

    # Material change check
    change.has_material_change = _has_material_change(current, previous)

    # Determine trend direction
    change.trend_direction = _determine_trend_direction(change)
    change.trend_summary = _build_trend_summary(change)
    change.recommended_next_action = _build_recommended_action(change)

    return change


# ---------------------------------------------------------------------------
# Trend summary
# ---------------------------------------------------------------------------


def summarize_cross_site_trends(
    database_path: Optional[str] = None,
) -> CrossSiteTrendSummary:
    """Summarize trend changes across all properties with snapshots.

    Args:
        database_path: Optional database path.

    Returns:
        CrossSiteTrendSummary with aggregate counts.
    """
    summary = CrossSiteTrendSummary()

    try:
        if not table_exists("cross_site_analytics_snapshots", database_path):
            return summary

        # Get properties with at least one snapshot
        query = """
        SELECT DISTINCT property_id
        FROM cross_site_analytics_snapshots
        ORDER BY property_id
        """
        results = execute_query(query, database_path=database_path)
        property_ids = [r["property_id"] for r in results]
        summary.total_properties = len(property_ids)

        sev_rank = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        pri_rank = {"none": 0, "low": 1, "medium": 2, "high": 3}

        for pid in property_ids:
            current = get_latest_cross_site_analytics_snapshot(pid, database_path)
            previous = get_previous_cross_site_analytics_snapshot(pid, database_path)

            if not current or not previous:
                continue

            summary.properties_with_trends += 1
            change = calculate_cross_site_trend_change(current, previous)

            if change.trend_direction == "improving":
                summary.properties_improving += 1
            elif change.trend_direction == "degrading":
                summary.properties_degrading += 1
            else:
                summary.properties_stable += 1

            # Severity changes
            cur_sev = sev_rank.get(current.discrepancy_severity_label or "none", 0)
            prev_sev = sev_rank.get(previous.discrepancy_severity_label or "none", 0)
            if cur_sev < prev_sev:
                summary.severity_downgrades += 1
            elif cur_sev > prev_sev:
                summary.severity_upgrades += 1

            # Priority changes
            cur_pri = pri_rank.get(current.cross_site_manual_review_priority or "none", 0)
            prev_pri = pri_rank.get(previous.cross_site_manual_review_priority or "none", 0)
            if cur_pri < prev_pri:
                summary.priority_downgrades += 1
            elif cur_pri > prev_pri:
                summary.priority_upgrades += 1

            # Discrepancy flag changes
            cur_flags = sum([
                current.price_discrepancy_flag,
                current.status_discrepancy_flag,
                current.dom_discrepancy_flag,
            ])
            prev_flags = sum([
                previous.price_discrepancy_flag,
                previous.status_discrepancy_flag,
                previous.dom_discrepancy_flag,
            ])
            if cur_flags > prev_flags:
                summary.new_discrepancy_flags += cur_flags - prev_flags
            elif cur_flags < prev_flags:
                summary.resolved_discrepancy_flags += prev_flags - cur_flags

    except Exception as e:
        logger.error(f"Error summarizing cross-site trends: {e}")

    return summary


# ---------------------------------------------------------------------------
# Report export
# ---------------------------------------------------------------------------


TREND_REPORT_FIELDNAMES = [
    "property_id",
    "candidate_id",
    "address",
    "city",
    "zip",
    "current_overall_cross_site_confidence_score",
    "previous_overall_cross_site_confidence_score",
    "overall_cross_site_confidence_change",
    "current_discrepancy_severity_label",
    "previous_discrepancy_severity_label",
    "discrepancy_severity_changed",
    "current_manual_review_priority",
    "previous_manual_review_priority",
    "manual_review_priority_changed",
    "current_weighted_price_agreement_score",
    "previous_weighted_price_agreement_score",
    "price_agreement_change",
    "current_weighted_status_agreement_score",
    "previous_weighted_status_agreement_score",
    "status_agreement_change",
    "current_weighted_dom_agreement_score",
    "previous_weighted_dom_agreement_score",
    "dom_agreement_change",
    "current_low_confidence_sources",
    "previous_low_confidence_sources",
    "current_stale_sources",
    "previous_stale_sources",
    "trend_direction",
    "trend_summary",
    "recommended_next_action",
]


def export_cross_site_trend_report(
    database_path: Optional[str] = None,
    output_path: Optional[str] = None,
) -> str:
    """Export cross-site trend report to CSV.

    Generates a CSV comparing current vs previous snapshots for all
    properties with trend data.

    Args:
        database_path: Optional database path.
        output_path: Optional output file path.

    Returns:
        Path to the generated CSV file.
    """
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/exports")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"cross_site_trends_{ts}.csv")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Generating cross-site trend report: {output_path}")

    try:
        if not table_exists("cross_site_analytics_snapshots", database_path):
            _write_trend_csv(output_file, [])
            return str(output_file)

        # Get properties with snapshots
        properties = _get_properties_with_snapshots(database_path)

        rows: List[dict] = []
        for prop in properties:
            property_id = prop["property_id"]
            current = get_latest_cross_site_analytics_snapshot(
                property_id, database_path
            )
            previous = get_previous_cross_site_analytics_snapshot(
                property_id, database_path
            )

            if not current:
                continue

            row = _build_trend_report_row(current, previous, prop)
            rows.append(row)

        _write_trend_csv(output_file, rows)
        logger.info(f"Exported {len(rows)} properties to {output_path}")
        return str(output_file)

    except Exception as e:
        logger.error(f"Error generating cross-site trend report: {e}")
        raise


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_snapshots_table(database_path: Optional[str] = None) -> None:
    """Ensure the cross_site_analytics_snapshots table exists."""
    if not table_exists("cross_site_analytics_snapshots", database_path):
        init_db(database_path)


def _get_active_properties(
    database_path: Optional[str] = None,
) -> List[Dict]:
    """Get all active watched properties."""
    try:
        query = """
        SELECT property_id, address, city, zip,
               current_price, displayed_dom
        FROM watched_properties
        WHERE active_watch_status = 1
        ORDER BY address
        """
        results = execute_query(query, database_path=database_path)
        return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"Error getting active properties: {e}")
        return []


def _get_properties_with_snapshots(
    database_path: Optional[str] = None,
) -> List[Dict]:
    """Get properties that have at least one analytics snapshot."""
    try:
        query = """
        SELECT DISTINCT wp.property_id, wp.address, wp.city, wp.zip
        FROM watched_properties wp
        INNER JOIN cross_site_analytics_snapshots cs
            ON wp.property_id = cs.property_id
        ORDER BY wp.address
        """
        results = execute_query(query, database_path=database_path)
        return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"Error getting properties with snapshots: {e}")
        return []


def _analytics_to_snapshot(
    analytics: CrossSiteAnalyticsResult,
    prop: Dict,
) -> CrossSiteAnalyticsSnapshot:
    """Convert analytics result to a snapshot model."""
    cm = analytics.confidence_metrics
    ds = analytics.discrepancy_severity
    sw = analytics.source_weights

    source_count = len([w for w in sw if w.combined_weight > 0]) if sw else 0
    high_conf_count = len([w for w in sw if not w.is_low_confidence and w.combined_weight > 0]) if sw else 0
    low_conf_count = len([w for w in sw if w.is_low_confidence]) if sw else 0
    stale_count = len([w for w in sw if w.is_stale]) if sw else 0

    return CrossSiteAnalyticsSnapshot(
        property_id=analytics.property_id,
        overall_cross_site_confidence_score=(
            cm.overall_cross_site_confidence_score if cm else None
        ),
        discrepancy_severity_score=ds.severity_score if ds else None,
        discrepancy_severity_label=ds.severity_label if ds else None,
        cross_site_manual_review_priority=analytics.cross_site_manual_review_priority,
        weighted_price_agreement_score=(
            analytics.price_agreement.agreement_score
            if analytics.price_agreement else None
        ),
        weighted_status_agreement_score=(
            analytics.status_agreement.agreement_score
            if analytics.status_agreement else None
        ),
        weighted_dom_agreement_score=(
            analytics.dom_agreement.agreement_score
            if analytics.dom_agreement else None
        ),
        weighted_garage_agreement_score=(
            analytics.garage_agreement.agreement_score
            if analytics.garage_agreement else None
        ),
        weighted_gas_agreement_score=(
            analytics.gas_agreement.agreement_score
            if analytics.gas_agreement else None
        ),
        source_freshness_score=cm.source_freshness_score if cm else None,
        source_completeness_score=cm.source_completeness_score if cm else None,
        source_agreement_score=cm.source_agreement_score if cm else None,
        contributing_sources=(
            "; ".join(cm.contributing_sources) if cm and cm.contributing_sources else None
        ),
        low_confidence_sources=(
            "; ".join(cm.low_confidence_sources) if cm and cm.low_confidence_sources else None
        ),
        stale_sources=(
            "; ".join(cm.stale_sources) if cm and cm.stale_sources else None
        ),
        parse_warning_sources=(
            "; ".join(cm.parse_warning_sources) if cm and cm.parse_warning_sources else None
        ),
        source_count=source_count,
        high_confidence_source_count=high_conf_count,
        low_confidence_source_count=low_conf_count,
        stale_source_count=stale_count,
        price_discrepancy_flag="price_discrepancy" in (ds.flags if ds else []),
        status_discrepancy_flag="status_discrepancy" in (ds.flags if ds else []),
        dom_discrepancy_flag="dom_discrepancy" in (ds.flags if ds else []),
    )


def _has_material_change(
    current: CrossSiteAnalyticsSnapshot,
    previous: CrossSiteAnalyticsSnapshot,
) -> bool:
    """Determine if there is a material change between snapshots.

    Material changes include:
    - Severity label changed
    - Manual review priority changed
    - Overall confidence changed by >= 0.10
    - Any agreement score changed by >= 0.10
    - Stale/low-confidence source count changed
    - Discrepancy flag changed
    """
    # Severity label
    if current.discrepancy_severity_label != previous.discrepancy_severity_label:
        return True

    # Manual review priority
    if current.cross_site_manual_review_priority != previous.cross_site_manual_review_priority:
        return True

    # Overall confidence delta >= 0.10
    delta = _score_delta(
        current.overall_cross_site_confidence_score,
        previous.overall_cross_site_confidence_score,
    )
    if delta is not None and abs(delta) >= 0.10:
        return True

    # Agreement score deltas >= 0.10
    for cur_val, prev_val in [
        (current.weighted_price_agreement_score, previous.weighted_price_agreement_score),
        (current.weighted_status_agreement_score, previous.weighted_status_agreement_score),
        (current.weighted_dom_agreement_score, previous.weighted_dom_agreement_score),
    ]:
        d = _score_delta(cur_val, prev_val)
        if d is not None and abs(d) >= 0.10:
            return True

    # Source count changes
    if current.low_confidence_source_count != previous.low_confidence_source_count:
        return True
    if current.stale_source_count != previous.stale_source_count:
        return True

    # Discrepancy flag changes
    if (
        current.price_discrepancy_flag != previous.price_discrepancy_flag
        or current.status_discrepancy_flag != previous.status_discrepancy_flag
        or current.dom_discrepancy_flag != previous.dom_discrepancy_flag
    ):
        return True

    return False


def _score_delta(
    current: Optional[float], previous: Optional[float]
) -> Optional[float]:
    """Calculate delta between two score values."""
    if current is not None and previous is not None:
        return round(current - previous, 4)
    return None


def _determine_trend_direction(change: CrossSiteTrendChange) -> str:
    """Determine overall trend direction from change data."""
    improving_signals = 0
    degrading_signals = 0

    # Confidence change
    if change.overall_confidence_change is not None:
        if change.overall_confidence_change > 0.05:
            improving_signals += 1
        elif change.overall_confidence_change < -0.05:
            degrading_signals += 1

    # Severity change
    sev_rank = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    if change.severity_label_changed:
        cur_rank = sev_rank.get(change.current_severity_label or "none", 0)
        prev_rank = sev_rank.get(change.previous_severity_label or "none", 0)
        if cur_rank < prev_rank:
            improving_signals += 1
        elif cur_rank > prev_rank:
            degrading_signals += 1

    # Priority change
    pri_rank = {"none": 0, "low": 1, "medium": 2, "high": 3}
    if change.manual_review_priority_changed:
        cur_rank = pri_rank.get(change.current_manual_review_priority or "none", 0)
        prev_rank = pri_rank.get(change.previous_manual_review_priority or "none", 0)
        if cur_rank < prev_rank:
            improving_signals += 1
        elif cur_rank > prev_rank:
            degrading_signals += 1

    # Agreement score changes
    for delta in [
        change.price_agreement_change,
        change.status_agreement_change,
        change.dom_agreement_change,
    ]:
        if delta is not None:
            if delta > 0.05:
                improving_signals += 1
            elif delta < -0.05:
                degrading_signals += 1

    if improving_signals > degrading_signals:
        return "improving"
    elif degrading_signals > improving_signals:
        return "degrading"
    return "stable"


def _build_trend_summary(change: CrossSiteTrendChange) -> str:
    """Build a human-readable trend summary."""
    parts: List[str] = []

    if change.overall_confidence_change is not None:
        direction = "increased" if change.overall_confidence_change > 0 else "decreased"
        parts.append(
            f"Confidence {direction} by {abs(change.overall_confidence_change):.2f}"
        )

    if change.severity_label_changed:
        parts.append(
            f"Severity changed from {change.previous_severity_label} "
            f"to {change.current_severity_label}"
        )

    if change.manual_review_priority_changed:
        parts.append(
            f"Review priority changed from {change.previous_manual_review_priority} "
            f"to {change.current_manual_review_priority}"
        )

    if change.discrepancy_flag_changed:
        parts.append("Discrepancy flags changed")

    if not parts:
        parts.append("No material change")

    return "; ".join(parts)


def _build_recommended_action(change: CrossSiteTrendChange) -> str:
    """Build a recommended next action based on trend."""
    if change.trend_direction == "degrading":
        if change.severity_label_changed:
            return "Review cross-site data; severity increased"
        if change.manual_review_priority_changed:
            return "Review cross-site data; priority increased"
        return "Monitor cross-site data; trend degrading"

    if change.trend_direction == "improving":
        return "Cross-site data improving; continue monitoring"

    return "No action needed; trend stable"


def _insert_snapshot(
    snapshot: CrossSiteAnalyticsSnapshot,
    database_path: Optional[str] = None,
) -> int:
    """Insert a snapshot into the database and return snapshot_id."""
    conn = get_connection(database_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO cross_site_analytics_snapshots (
                property_id, candidate_id, captured_at,
                overall_cross_site_confidence_score,
                discrepancy_severity_score, discrepancy_severity_label,
                cross_site_manual_review_priority,
                weighted_price_agreement_score,
                weighted_status_agreement_score,
                weighted_dom_agreement_score,
                weighted_garage_agreement_score,
                weighted_gas_agreement_score,
                source_freshness_score, source_completeness_score,
                source_agreement_score,
                contributing_sources, low_confidence_sources,
                stale_sources, parse_warning_sources,
                source_count, high_confidence_source_count,
                low_confidence_source_count, stale_source_count,
                price_discrepancy_flag, status_discrepancy_flag,
                dom_discrepancy_flag, notes
            ) VALUES (
                ?, ?, ?,
                ?, ?, ?,
                ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            """,
            (
                snapshot.property_id,
                snapshot.candidate_id,
                snapshot.captured_at.isoformat(),
                snapshot.overall_cross_site_confidence_score,
                snapshot.discrepancy_severity_score,
                snapshot.discrepancy_severity_label,
                snapshot.cross_site_manual_review_priority,
                snapshot.weighted_price_agreement_score,
                snapshot.weighted_status_agreement_score,
                snapshot.weighted_dom_agreement_score,
                snapshot.weighted_garage_agreement_score,
                snapshot.weighted_gas_agreement_score,
                snapshot.source_freshness_score,
                snapshot.source_completeness_score,
                snapshot.source_agreement_score,
                snapshot.contributing_sources,
                snapshot.low_confidence_sources,
                snapshot.stale_sources,
                snapshot.parse_warning_sources,
                snapshot.source_count,
                snapshot.high_confidence_source_count,
                snapshot.low_confidence_source_count,
                snapshot.stale_source_count,
                int(snapshot.price_discrepancy_flag),
                int(snapshot.status_discrepancy_flag),
                int(snapshot.dom_discrepancy_flag),
                snapshot.notes,
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0

    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting snapshot: {e}")
        raise
    finally:
        conn.close()


def _row_to_snapshot(row: Dict) -> CrossSiteAnalyticsSnapshot:
    """Convert a database row dict to a CrossSiteAnalyticsSnapshot."""
    captured_at = row.get("captured_at")
    if isinstance(captured_at, str):
        try:
            captured_at = datetime.fromisoformat(captured_at)
        except (ValueError, TypeError):
            captured_at = datetime.now()

    created_at = row.get("created_at")
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at)
        except (ValueError, TypeError):
            created_at = datetime.now()

    return CrossSiteAnalyticsSnapshot(
        snapshot_id=row.get("snapshot_id"),
        property_id=row["property_id"],
        candidate_id=row.get("candidate_id"),
        captured_at=captured_at or datetime.now(),
        overall_cross_site_confidence_score=row.get("overall_cross_site_confidence_score"),
        discrepancy_severity_score=row.get("discrepancy_severity_score"),
        discrepancy_severity_label=row.get("discrepancy_severity_label"),
        cross_site_manual_review_priority=row.get("cross_site_manual_review_priority"),
        weighted_price_agreement_score=row.get("weighted_price_agreement_score"),
        weighted_status_agreement_score=row.get("weighted_status_agreement_score"),
        weighted_dom_agreement_score=row.get("weighted_dom_agreement_score"),
        weighted_garage_agreement_score=row.get("weighted_garage_agreement_score"),
        weighted_gas_agreement_score=row.get("weighted_gas_agreement_score"),
        source_freshness_score=row.get("source_freshness_score"),
        source_completeness_score=row.get("source_completeness_score"),
        source_agreement_score=row.get("source_agreement_score"),
        contributing_sources=row.get("contributing_sources"),
        low_confidence_sources=row.get("low_confidence_sources"),
        stale_sources=row.get("stale_sources"),
        parse_warning_sources=row.get("parse_warning_sources"),
        source_count=row.get("source_count", 0),
        high_confidence_source_count=row.get("high_confidence_source_count", 0),
        low_confidence_source_count=row.get("low_confidence_source_count", 0),
        stale_source_count=row.get("stale_source_count", 0),
        price_discrepancy_flag=bool(row.get("price_discrepancy_flag", 0)),
        status_discrepancy_flag=bool(row.get("status_discrepancy_flag", 0)),
        dom_discrepancy_flag=bool(row.get("dom_discrepancy_flag", 0)),
        notes=row.get("notes"),
        created_at=created_at or datetime.now(),
    )


def _build_trend_report_row(
    current: CrossSiteAnalyticsSnapshot,
    previous: Optional[CrossSiteAnalyticsSnapshot],
    prop: Dict,
) -> dict:
    """Build a flat CSV row dict for the trend report."""
    row: dict = {
        "property_id": current.property_id,
        "candidate_id": current.candidate_id,
        "address": prop.get("address"),
        "city": prop.get("city"),
        "zip": prop.get("zip"),
        "current_overall_cross_site_confidence_score": current.overall_cross_site_confidence_score,
        "current_discrepancy_severity_label": current.discrepancy_severity_label,
        "current_manual_review_priority": current.cross_site_manual_review_priority,
        "current_weighted_price_agreement_score": current.weighted_price_agreement_score,
        "current_weighted_status_agreement_score": current.weighted_status_agreement_score,
        "current_weighted_dom_agreement_score": current.weighted_dom_agreement_score,
        "current_low_confidence_sources": current.low_confidence_sources,
        "current_stale_sources": current.stale_sources,
    }

    if previous:
        change = calculate_cross_site_trend_change(current, previous, prop)
        row.update({
            "previous_overall_cross_site_confidence_score": previous.overall_cross_site_confidence_score,
            "overall_cross_site_confidence_change": change.overall_confidence_change,
            "previous_discrepancy_severity_label": previous.discrepancy_severity_label,
            "discrepancy_severity_changed": change.severity_label_changed,
            "previous_manual_review_priority": previous.cross_site_manual_review_priority,
            "manual_review_priority_changed": change.manual_review_priority_changed,
            "previous_weighted_price_agreement_score": previous.weighted_price_agreement_score,
            "price_agreement_change": change.price_agreement_change,
            "previous_weighted_status_agreement_score": previous.weighted_status_agreement_score,
            "status_agreement_change": change.status_agreement_change,
            "previous_weighted_dom_agreement_score": previous.weighted_dom_agreement_score,
            "dom_agreement_change": change.dom_agreement_change,
            "previous_low_confidence_sources": previous.low_confidence_sources,
            "previous_stale_sources": previous.stale_sources,
            "trend_direction": change.trend_direction,
            "trend_summary": change.trend_summary,
            "recommended_next_action": change.recommended_next_action,
        })
    else:
        row.update({
            "previous_overall_cross_site_confidence_score": None,
            "overall_cross_site_confidence_change": None,
            "previous_discrepancy_severity_label": None,
            "discrepancy_severity_changed": False,
            "previous_manual_review_priority": None,
            "manual_review_priority_changed": False,
            "previous_weighted_price_agreement_score": None,
            "price_agreement_change": None,
            "previous_weighted_status_agreement_score": None,
            "status_agreement_change": None,
            "previous_weighted_dom_agreement_score": None,
            "dom_agreement_change": None,
            "previous_low_confidence_sources": None,
            "previous_stale_sources": None,
            "trend_direction": "stable",
            "trend_summary": "First snapshot; no trend data yet",
            "recommended_next_action": "Continue monitoring",
        })

    return row


def _write_trend_csv(output_file: Path, rows: List[dict]) -> None:
    """Write trend report rows to CSV."""
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TREND_REPORT_FIELDNAMES)
        writer.writeheader()
        if rows:
            writer.writerows(rows)
