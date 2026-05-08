"""Cross-site trend alerts and watchlist monitoring integration.

Generates, manages, and exports alerts based on cross-site analytics
trend snapshot changes. Alerts are neutral review signals -- they are
not purchase recommendations and must not infer seller intent.

Cross-site alert data remains validation/check data. It does not
overwrite Redfin source-of-truth fields, user decisions, watchlist
status, or Quiet Score gatekeeper results.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from marketsentry.cross_site_trends import (
    calculate_cross_site_trend_change,
    get_latest_cross_site_analytics_snapshot,
    get_previous_cross_site_analytics_snapshot,
)
from marketsentry.database import execute_query, get_connection, init_db, table_exists
from marketsentry.logging_config import logger
from marketsentry.models import (
    CrossSiteAnalyticsSnapshot,
    CrossSiteTrendAlert,
    CrossSiteTrendAlertReportRow,
    CrossSiteTrendAlertRule,
    CrossSiteTrendAlertRunResult,
    CrossSiteTrendChange,
)


# ---------------------------------------------------------------------------
# Severity rank helpers
# ---------------------------------------------------------------------------

SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
PRIORITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


# ---------------------------------------------------------------------------
# Centralized alert rules
# ---------------------------------------------------------------------------


def _build_default_rules() -> List[CrossSiteTrendAlertRule]:
    """Build the default set of alert rules.

    Rules are centralized here for easy adjustment.

    Returns:
        List of CrossSiteTrendAlertRule.
    """
    return [
        CrossSiteTrendAlertRule(
            alert_type="confidence_drop",
            description="Overall confidence score dropped materially",
            field_name="overall_cross_site_confidence_score",
            threshold=0.10,
            direction="decrease",
            default_severity="warning",
            message_template="Confidence dropped by {delta:.2f} (from {prev} to {curr})",
        ),
        CrossSiteTrendAlertRule(
            alert_type="confidence_improvement",
            description="Overall confidence score improved materially",
            field_name="overall_cross_site_confidence_score",
            threshold=0.10,
            direction="increase",
            default_severity="info",
            message_template="Confidence improved by {delta:.2f} (from {prev} to {curr})",
        ),
        CrossSiteTrendAlertRule(
            alert_type="severity_increase",
            description="Discrepancy severity level increased",
            field_name="discrepancy_severity_label",
            threshold=None,
            direction="increase",
            default_severity="warning",
            message_template="Severity increased from {prev} to {curr}",
        ),
        CrossSiteTrendAlertRule(
            alert_type="severity_decrease",
            description="Discrepancy severity level decreased",
            field_name="discrepancy_severity_label",
            threshold=None,
            direction="decrease",
            default_severity="info",
            message_template="Severity decreased from {prev} to {curr}",
        ),
        CrossSiteTrendAlertRule(
            alert_type="manual_review_priority_increase",
            description="Manual review priority increased",
            field_name="cross_site_manual_review_priority",
            threshold=None,
            direction="increase",
            default_severity="high",
            message_template="Review priority increased from {prev} to {curr}",
        ),
        CrossSiteTrendAlertRule(
            alert_type="manual_review_priority_decrease",
            description="Manual review priority decreased",
            field_name="cross_site_manual_review_priority",
            threshold=None,
            direction="decrease",
            default_severity="info",
            message_template="Review priority decreased from {prev} to {curr}",
        ),
        CrossSiteTrendAlertRule(
            alert_type="price_agreement_degraded",
            description="Price agreement score dropped materially",
            field_name="weighted_price_agreement_score",
            threshold=0.25,
            direction="decrease",
            default_severity="warning",
            message_template="Price agreement dropped by {delta:.2f} (from {prev} to {curr})",
        ),
        CrossSiteTrendAlertRule(
            alert_type="status_agreement_degraded",
            description="Status agreement score dropped materially",
            field_name="weighted_status_agreement_score",
            threshold=0.25,
            direction="decrease",
            default_severity="high",
            message_template="Status agreement dropped by {delta:.2f} (from {prev} to {curr})",
        ),
        CrossSiteTrendAlertRule(
            alert_type="dom_agreement_degraded",
            description="DOM agreement score dropped materially",
            field_name="weighted_dom_agreement_score",
            threshold=0.25,
            direction="decrease",
            default_severity="warning",
            message_template="DOM agreement dropped by {delta:.2f} (from {prev} to {curr})",
        ),
        CrossSiteTrendAlertRule(
            alert_type="stale_sources_increased",
            description="Stale source count increased",
            field_name="stale_source_count",
            threshold=None,
            direction="increase",
            default_severity="warning",
            message_template="Stale source count increased from {prev} to {curr}",
        ),
        CrossSiteTrendAlertRule(
            alert_type="low_confidence_sources_increased",
            description="Low-confidence source count increased",
            field_name="low_confidence_source_count",
            threshold=None,
            direction="increase",
            default_severity="warning",
            message_template="Low-confidence source count increased from {prev} to {curr}",
        ),
        CrossSiteTrendAlertRule(
            alert_type="source_quality_improved",
            description="Source quality improved (stale or low-confidence count decreased)",
            field_name="source_quality",
            threshold=None,
            direction="decrease",
            default_severity="info",
            message_template="Source quality improved: {detail}",
        ),
    ]


DEFAULT_RULES = _build_default_rules()


# ---------------------------------------------------------------------------
# Alert generation
# ---------------------------------------------------------------------------


def generate_cross_site_trend_alerts(
    database_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> CrossSiteTrendAlertRunResult:
    """Generate cross-site trend alerts for all active watched properties.

    Reads latest and previous trend snapshots, applies alert rules,
    and persists new alerts. Deduplicates against existing open alerts.

    Args:
        database_path: Optional database path.
        output_dir: Optional output directory (unused in generation).

    Returns:
        CrossSiteTrendAlertRunResult with counts and diagnostics.
    """
    result = CrossSiteTrendAlertRunResult()

    try:
        _ensure_alerts_table(database_path)

        properties = _get_active_properties(database_path)
        result.properties_scanned = len(properties)

        if not properties:
            result.notes = "No active watched properties found"
            return result

        for prop in properties:
            property_id = prop["property_id"]

            try:
                alerts, dups = generate_alerts_for_property(
                    property_id, prop, database_path
                )
                result.alerts_generated += len(alerts)
                result.duplicates_skipped += dups

            except Exception as e:
                msg = f"Error generating alerts for property {property_id}: {e}"
                logger.error(msg)
                result.errors.append(msg)

    except Exception as e:
        msg = f"Error generating cross-site trend alerts: {e}"
        logger.error(msg)
        result.errors.append(msg)

    return result


def generate_alerts_for_property(
    property_id: int,
    prop: Optional[Dict] = None,
    database_path: Optional[str] = None,
) -> Tuple[List[CrossSiteTrendAlert], int]:
    """Generate alerts for a single property based on trend snapshots.

    Args:
        property_id: Watched property ID.
        prop: Optional property dict with address/city/zip.
        database_path: Optional database path.

    Returns:
        Tuple of (list of generated alerts, duplicate count).
    """
    current = get_latest_cross_site_analytics_snapshot(property_id, database_path)
    previous = get_previous_cross_site_analytics_snapshot(property_id, database_path)

    if not current or not previous:
        return [], 0

    change = calculate_cross_site_trend_change(current, previous, prop)

    alerts: List[CrossSiteTrendAlert] = []
    duplicates = 0

    for rule in DEFAULT_RULES:
        alert = _evaluate_rule(rule, current, previous, change, prop)
        if alert is None:
            continue

        # Deduplication check
        if _is_duplicate_open_alert(
            property_id, alert.alert_type, current.snapshot_id, database_path
        ):
            duplicates += 1
            continue

        # Persist alert
        alert_id = _insert_alert(alert, database_path)
        alert.alert_id = alert_id
        alerts.append(alert)

    return alerts, duplicates


# ---------------------------------------------------------------------------
# Alert severity classification
# ---------------------------------------------------------------------------


def classify_trend_alert_severity(
    alert_type: str,
    current: CrossSiteAnalyticsSnapshot,
    previous: CrossSiteAnalyticsSnapshot,
    change: CrossSiteTrendChange,
) -> str:
    """Classify alert severity based on alert type and magnitude.

    Args:
        alert_type: The type of alert being generated.
        current: Current snapshot.
        previous: Previous snapshot.
        change: Trend change data.

    Returns:
        Severity string: info, warning, high, or critical.
    """
    # Confidence drop severity tiers
    if alert_type == "confidence_drop":
        delta = abs(change.overall_confidence_change or 0)
        if delta >= 0.25:
            return "high"
        return "warning"

    # Confidence improvement
    if alert_type == "confidence_improvement":
        return "info"

    # Severity increase
    if alert_type == "severity_increase":
        cur_label = current.discrepancy_severity_label or "none"
        if cur_label == "critical":
            return "critical"
        if cur_label == "high":
            return "high"
        return "warning"

    # Severity decrease
    if alert_type == "severity_decrease":
        return "info"

    # Manual review priority increase
    if alert_type == "manual_review_priority_increase":
        cur_pri = current.cross_site_manual_review_priority or "none"
        if cur_pri == "high":
            return "high"
        return "warning"

    # Manual review priority decrease
    if alert_type == "manual_review_priority_decrease":
        return "info"

    # Status agreement degraded
    if alert_type == "status_agreement_degraded":
        return "high"

    # Price agreement degraded
    if alert_type == "price_agreement_degraded":
        cur_sev = current.discrepancy_severity_label or "none"
        if cur_sev in ("high", "critical"):
            return "high"
        return "warning"

    # DOM agreement degraded
    if alert_type == "dom_agreement_degraded":
        return "warning"

    # Stale/low-confidence source count increases
    if alert_type in ("stale_sources_increased", "low_confidence_sources_increased"):
        return "warning"

    # Source quality improved
    if alert_type == "source_quality_improved":
        return "info"

    return "info"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def deduplicate_open_alerts(
    property_id: int,
    alert_type: str,
    snapshot_id: Optional[int],
    database_path: Optional[str] = None,
) -> bool:
    """Check if an open alert already exists for this property/type/snapshot.

    Args:
        property_id: Watched property ID.
        alert_type: Alert type string.
        snapshot_id: Current snapshot ID.
        database_path: Optional database path.

    Returns:
        True if a duplicate open alert exists.
    """
    return _is_duplicate_open_alert(property_id, alert_type, snapshot_id, database_path)


# ---------------------------------------------------------------------------
# Alert lifecycle
# ---------------------------------------------------------------------------


def acknowledge_cross_site_trend_alert(
    alert_id: int,
    notes: Optional[str] = None,
    database_path: Optional[str] = None,
) -> bool:
    """Acknowledge an open alert.

    Args:
        alert_id: Alert ID to acknowledge.
        notes: Optional notes to append.
        database_path: Optional database path.

    Returns:
        True if the alert was updated.
    """
    return _update_alert_status(alert_id, "acknowledged", notes, database_path)


def resolve_cross_site_trend_alert(
    alert_id: int,
    notes: Optional[str] = None,
    database_path: Optional[str] = None,
) -> bool:
    """Resolve an alert.

    Args:
        alert_id: Alert ID to resolve.
        notes: Optional notes to append.
        database_path: Optional database path.

    Returns:
        True if the alert was updated.
    """
    return _update_alert_status(alert_id, "resolved", notes, database_path)


# ---------------------------------------------------------------------------
# Report export
# ---------------------------------------------------------------------------

ALERT_REPORT_FIELDNAMES = [
    "alert_id",
    "property_id",
    "candidate_id",
    "address",
    "city",
    "zip",
    "alert_type",
    "severity",
    "alert_status",
    "trend_direction",
    "current_value",
    "previous_value",
    "delta_value",
    "message",
    "recommended_action",
    "source_context",
    "created_at",
    "notes",
]


def export_cross_site_trend_alerts_report(
    database_path: Optional[str] = None,
    output_path: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> str:
    """Export cross-site trend alerts to CSV.

    Args:
        database_path: Optional database path.
        output_path: Optional output file path.
        status_filter: Optional alert_status filter.

    Returns:
        Path to the generated CSV file.
    """
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/exports")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"cross_site_trend_alerts_{ts}.csv")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Generating cross-site trend alerts report: {output_path}")

    try:
        rows = _get_alert_report_rows(database_path, status_filter)

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ALERT_REPORT_FIELDNAMES)
            writer.writeheader()
            if rows:
                writer.writerows(rows)

        logger.info(f"Exported {len(rows)} alerts to {output_path}")
        return str(output_file)

    except Exception as e:
        logger.error(f"Error generating cross-site trend alerts report: {e}")
        raise


# ---------------------------------------------------------------------------
# Alert listing/querying
# ---------------------------------------------------------------------------


def list_cross_site_trend_alerts(
    database_path: Optional[str] = None,
    status_filter: Optional[str] = None,
    severity_filter: Optional[str] = None,
    property_id: Optional[int] = None,
) -> List[CrossSiteTrendAlert]:
    """List cross-site trend alerts with optional filters.

    Args:
        database_path: Optional database path.
        status_filter: Filter by alert_status (default: 'open').
        severity_filter: Filter by severity.
        property_id: Filter by property_id.

    Returns:
        List of CrossSiteTrendAlert.
    """
    if not table_exists("cross_site_trend_alerts", database_path):
        return []

    conditions = []
    params: list = []

    if status_filter:
        conditions.append("alert_status = ?")
        params.append(status_filter)
    else:
        conditions.append("alert_status = 'open'")

    if severity_filter:
        conditions.append("severity = ?")
        params.append(severity_filter)

    if property_id is not None:
        conditions.append("property_id = ?")
        params.append(property_id)

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    query = f"""
    SELECT * FROM cross_site_trend_alerts
    WHERE {where_clause}
    ORDER BY created_at DESC
    """

    try:
        results = execute_query(query, tuple(params), database_path=database_path)
        return [_row_to_alert(dict(row)) for row in results]
    except Exception as e:
        logger.error(f"Error listing cross-site trend alerts: {e}")
        return []


# ---------------------------------------------------------------------------
# Watchlist monitoring integration helpers
# ---------------------------------------------------------------------------


def get_alert_summary_for_property(
    property_id: int,
    database_path: Optional[str] = None,
) -> Dict:
    """Get alert summary fields for watchlist monitoring reports.

    Args:
        property_id: Watched property ID.
        database_path: Optional database path.

    Returns:
        Dict with alert summary fields for report integration.
    """
    summary: Dict = {
        "open_cross_site_alert_count": 0,
        "highest_cross_site_alert_severity": None,
        "latest_cross_site_alert_type": None,
        "latest_cross_site_alert_message": None,
        "cross_site_alert_recommended_action": None,
    }

    if not table_exists("cross_site_trend_alerts", database_path):
        return summary

    try:
        # Open alert count
        count_query = """
        SELECT COUNT(*) AS cnt
        FROM cross_site_trend_alerts
        WHERE property_id = ? AND alert_status = 'open'
        """
        count_rows = execute_query(
            count_query, (property_id,), database_path=database_path
        )
        summary["open_cross_site_alert_count"] = (
            count_rows[0]["cnt"] if count_rows else 0
        )

        if summary["open_cross_site_alert_count"] == 0:
            return summary

        # Highest severity among open alerts
        sev_query = """
        SELECT severity FROM cross_site_trend_alerts
        WHERE property_id = ? AND alert_status = 'open'
        """
        sev_rows = execute_query(
            sev_query, (property_id,), database_path=database_path
        )
        if sev_rows:
            severities = [r["severity"] for r in sev_rows]
            max_sev = max(severities, key=lambda s: SEVERITY_RANK.get(s, 0))
            summary["highest_cross_site_alert_severity"] = max_sev

        # Latest alert
        latest_query = """
        SELECT alert_type, message, recommended_action
        FROM cross_site_trend_alerts
        WHERE property_id = ? AND alert_status = 'open'
        ORDER BY created_at DESC
        LIMIT 1
        """
        latest_rows = execute_query(
            latest_query, (property_id,), database_path=database_path
        )
        if latest_rows:
            row = latest_rows[0]
            summary["latest_cross_site_alert_type"] = row["alert_type"]
            summary["latest_cross_site_alert_message"] = row["message"]
            summary["cross_site_alert_recommended_action"] = row[
                "recommended_action"
            ]

    except Exception as e:
        logger.error(
            f"Error getting alert summary for property {property_id}: {e}"
        )

    return summary


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_alerts_table(database_path: Optional[str] = None) -> None:
    """Ensure the cross_site_trend_alerts table exists."""
    if not table_exists("cross_site_trend_alerts", database_path):
        init_db(database_path)


def _get_active_properties(
    database_path: Optional[str] = None,
) -> List[Dict]:
    """Get all active watched properties."""
    try:
        query = """
        SELECT property_id, address, city, zip, current_price
        FROM watched_properties
        WHERE active_watch_status = 1
        ORDER BY address
        """
        results = execute_query(query, database_path=database_path)
        return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"Error getting active properties: {e}")
        return []


def _evaluate_rule(
    rule: CrossSiteTrendAlertRule,
    current: CrossSiteAnalyticsSnapshot,
    previous: CrossSiteAnalyticsSnapshot,
    change: CrossSiteTrendChange,
    prop: Optional[Dict] = None,
) -> Optional[CrossSiteTrendAlert]:
    """Evaluate a single rule against current/previous snapshots.

    Args:
        rule: The alert rule to evaluate.
        current: Current snapshot.
        previous: Previous snapshot.
        change: Trend change data.
        prop: Optional property dict.

    Returns:
        CrossSiteTrendAlert if rule triggered, None otherwise.
    """
    triggered = False
    curr_str = ""
    prev_str = ""
    delta_str = ""
    message = ""

    if rule.alert_type == "confidence_drop":
        delta = change.overall_confidence_change
        if delta is not None and delta < 0 and abs(delta) >= (rule.threshold or 0.10):
            triggered = True
            curr_str = f"{current.overall_cross_site_confidence_score:.2f}" if current.overall_cross_site_confidence_score is not None else ""
            prev_str = f"{previous.overall_cross_site_confidence_score:.2f}" if previous.overall_cross_site_confidence_score is not None else ""
            delta_str = f"{delta:.4f}"
            message = rule.message_template.format(
                delta=abs(delta), prev=prev_str, curr=curr_str
            )

    elif rule.alert_type == "confidence_improvement":
        delta = change.overall_confidence_change
        if delta is not None and delta > 0 and abs(delta) >= (rule.threshold or 0.10):
            triggered = True
            curr_str = f"{current.overall_cross_site_confidence_score:.2f}" if current.overall_cross_site_confidence_score is not None else ""
            prev_str = f"{previous.overall_cross_site_confidence_score:.2f}" if previous.overall_cross_site_confidence_score is not None else ""
            delta_str = f"{delta:.4f}"
            message = rule.message_template.format(
                delta=abs(delta), prev=prev_str, curr=curr_str
            )

    elif rule.alert_type == "severity_increase":
        if change.severity_label_changed:
            cur_rank = SEVERITY_RANK.get(current.discrepancy_severity_label or "none", 0)
            prev_rank = SEVERITY_RANK.get(previous.discrepancy_severity_label or "none", 0)
            if cur_rank > prev_rank:
                triggered = True
                curr_str = current.discrepancy_severity_label or "none"
                prev_str = previous.discrepancy_severity_label or "none"
                message = rule.message_template.format(prev=prev_str, curr=curr_str)

    elif rule.alert_type == "severity_decrease":
        if change.severity_label_changed:
            cur_rank = SEVERITY_RANK.get(current.discrepancy_severity_label or "none", 0)
            prev_rank = SEVERITY_RANK.get(previous.discrepancy_severity_label or "none", 0)
            if cur_rank < prev_rank:
                triggered = True
                curr_str = current.discrepancy_severity_label or "none"
                prev_str = previous.discrepancy_severity_label or "none"
                message = rule.message_template.format(prev=prev_str, curr=curr_str)

    elif rule.alert_type == "manual_review_priority_increase":
        if change.manual_review_priority_changed:
            cur_rank = PRIORITY_RANK.get(current.cross_site_manual_review_priority or "none", 0)
            prev_rank = PRIORITY_RANK.get(previous.cross_site_manual_review_priority or "none", 0)
            if cur_rank > prev_rank:
                triggered = True
                curr_str = current.cross_site_manual_review_priority or "none"
                prev_str = previous.cross_site_manual_review_priority or "none"
                message = rule.message_template.format(prev=prev_str, curr=curr_str)

    elif rule.alert_type == "manual_review_priority_decrease":
        if change.manual_review_priority_changed:
            cur_rank = PRIORITY_RANK.get(current.cross_site_manual_review_priority or "none", 0)
            prev_rank = PRIORITY_RANK.get(previous.cross_site_manual_review_priority or "none", 0)
            if cur_rank < prev_rank:
                triggered = True
                curr_str = current.cross_site_manual_review_priority or "none"
                prev_str = previous.cross_site_manual_review_priority or "none"
                message = rule.message_template.format(prev=prev_str, curr=curr_str)

    elif rule.alert_type == "price_agreement_degraded":
        delta = change.price_agreement_change
        if delta is not None and delta < 0 and abs(delta) >= (rule.threshold or 0.25):
            triggered = True
            curr_str = f"{current.weighted_price_agreement_score:.2f}" if current.weighted_price_agreement_score is not None else ""
            prev_str = f"{previous.weighted_price_agreement_score:.2f}" if previous.weighted_price_agreement_score is not None else ""
            delta_str = f"{delta:.4f}"
            message = rule.message_template.format(
                delta=abs(delta), prev=prev_str, curr=curr_str
            )

    elif rule.alert_type == "status_agreement_degraded":
        delta = change.status_agreement_change
        if delta is not None and delta < 0 and abs(delta) >= (rule.threshold or 0.25):
            triggered = True
            curr_str = f"{current.weighted_status_agreement_score:.2f}" if current.weighted_status_agreement_score is not None else ""
            prev_str = f"{previous.weighted_status_agreement_score:.2f}" if previous.weighted_status_agreement_score is not None else ""
            delta_str = f"{delta:.4f}"
            message = rule.message_template.format(
                delta=abs(delta), prev=prev_str, curr=curr_str
            )

    elif rule.alert_type == "dom_agreement_degraded":
        delta = change.dom_agreement_change
        if delta is not None and delta < 0 and abs(delta) >= (rule.threshold or 0.25):
            triggered = True
            curr_str = f"{current.weighted_dom_agreement_score:.2f}" if current.weighted_dom_agreement_score is not None else ""
            prev_str = f"{previous.weighted_dom_agreement_score:.2f}" if previous.weighted_dom_agreement_score is not None else ""
            delta_str = f"{delta:.4f}"
            message = rule.message_template.format(
                delta=abs(delta), prev=prev_str, curr=curr_str
            )

    elif rule.alert_type == "stale_sources_increased":
        if current.stale_source_count > previous.stale_source_count:
            triggered = True
            curr_str = str(current.stale_source_count)
            prev_str = str(previous.stale_source_count)
            delta_str = str(current.stale_source_count - previous.stale_source_count)
            message = rule.message_template.format(prev=prev_str, curr=curr_str)

    elif rule.alert_type == "low_confidence_sources_increased":
        if current.low_confidence_source_count > previous.low_confidence_source_count:
            triggered = True
            curr_str = str(current.low_confidence_source_count)
            prev_str = str(previous.low_confidence_source_count)
            delta_str = str(
                current.low_confidence_source_count
                - previous.low_confidence_source_count
            )
            message = rule.message_template.format(prev=prev_str, curr=curr_str)

    elif rule.alert_type == "source_quality_improved":
        stale_improved = current.stale_source_count < previous.stale_source_count
        low_conf_improved = (
            current.low_confidence_source_count < previous.low_confidence_source_count
        )
        if stale_improved or low_conf_improved:
            triggered = True
            details = []
            if stale_improved:
                details.append(
                    f"stale sources {previous.stale_source_count} -> {current.stale_source_count}"
                )
            if low_conf_improved:
                details.append(
                    f"low-confidence sources {previous.low_confidence_source_count} -> {current.low_confidence_source_count}"
                )
            message = rule.message_template.format(detail="; ".join(details))
            curr_str = f"stale={current.stale_source_count}, low_conf={current.low_confidence_source_count}"
            prev_str = f"stale={previous.stale_source_count}, low_conf={previous.low_confidence_source_count}"

    if not triggered:
        return None

    # Classify severity
    severity = classify_trend_alert_severity(
        rule.alert_type, current, previous, change
    )

    # Build recommended action
    recommended_action = _build_alert_recommended_action(rule.alert_type, severity)

    # Build source context
    source_context = _build_source_context(current, previous)

    return CrossSiteTrendAlert(
        property_id=current.property_id,
        candidate_id=current.candidate_id,
        snapshot_id=current.snapshot_id,
        previous_snapshot_id=previous.snapshot_id,
        alert_type=rule.alert_type,
        severity=severity,
        alert_status="open",
        trend_direction=change.trend_direction,
        current_value=curr_str,
        previous_value=prev_str,
        delta_value=delta_str,
        message=message,
        recommended_action=recommended_action,
        source_context=source_context,
    )


def _build_alert_recommended_action(alert_type: str, severity: str) -> str:
    """Build a recommended action string for an alert."""
    if severity in ("high", "critical"):
        return "Review cross-site data and validate against Redfin source"
    if severity == "warning":
        return "Monitor cross-site data for further changes"
    # info
    if alert_type in (
        "confidence_improvement",
        "severity_decrease",
        "manual_review_priority_decrease",
        "source_quality_improved",
    ):
        return "Cross-site data improving; continue monitoring"
    return "No immediate action needed"


def _build_source_context(
    current: CrossSiteAnalyticsSnapshot,
    previous: CrossSiteAnalyticsSnapshot,
) -> str:
    """Build source context string for an alert."""
    parts: List[str] = []
    if current.contributing_sources:
        parts.append(f"Current sources: {current.contributing_sources}")
    if current.low_confidence_sources:
        parts.append(f"Low confidence: {current.low_confidence_sources}")
    if current.stale_sources:
        parts.append(f"Stale: {current.stale_sources}")
    return "; ".join(parts) if parts else ""


def _is_duplicate_open_alert(
    property_id: int,
    alert_type: str,
    snapshot_id: Optional[int],
    database_path: Optional[str] = None,
) -> bool:
    """Check if a duplicate open alert exists."""
    if not table_exists("cross_site_trend_alerts", database_path):
        return False

    try:
        query = """
        SELECT COUNT(*) AS cnt FROM cross_site_trend_alerts
        WHERE property_id = ?
          AND alert_type = ?
          AND snapshot_id = ?
          AND alert_status = 'open'
        """
        results = execute_query(
            query, (property_id, alert_type, snapshot_id), database_path=database_path
        )
        return results[0]["cnt"] > 0 if results else False
    except Exception as e:
        logger.error(f"Error checking duplicate alert: {e}")
        return False


def _insert_alert(
    alert: CrossSiteTrendAlert,
    database_path: Optional[str] = None,
) -> int:
    """Insert an alert into the database and return alert_id."""
    conn = get_connection(database_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO cross_site_trend_alerts (
                property_id, candidate_id, snapshot_id,
                previous_snapshot_id, alert_type, severity,
                alert_status, trend_direction,
                current_value, previous_value, delta_value,
                message, recommended_action, source_context, notes
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                alert.property_id,
                alert.candidate_id,
                alert.snapshot_id,
                alert.previous_snapshot_id,
                alert.alert_type,
                alert.severity,
                alert.alert_status,
                alert.trend_direction,
                alert.current_value,
                alert.previous_value,
                alert.delta_value,
                alert.message,
                alert.recommended_action,
                alert.source_context,
                alert.notes,
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0

    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting alert: {e}")
        raise
    finally:
        conn.close()


def _update_alert_status(
    alert_id: int,
    new_status: str,
    notes: Optional[str] = None,
    database_path: Optional[str] = None,
) -> bool:
    """Update alert status and optionally append notes."""
    if not table_exists("cross_site_trend_alerts", database_path):
        return False

    conn = get_connection(database_path)
    cursor = conn.cursor()

    try:
        if notes:
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
                (new_status, notes, notes, alert_id),
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
        return cursor.rowcount > 0

    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating alert status: {e}")
        return False
    finally:
        conn.close()


def _row_to_alert(row: Dict) -> CrossSiteTrendAlert:
    """Convert a database row dict to a CrossSiteTrendAlert."""
    created_at = row.get("created_at")
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at)
        except (ValueError, TypeError):
            created_at = datetime.now()

    return CrossSiteTrendAlert(
        alert_id=row.get("alert_id"),
        property_id=row["property_id"],
        candidate_id=row.get("candidate_id"),
        snapshot_id=row.get("snapshot_id"),
        previous_snapshot_id=row.get("previous_snapshot_id"),
        created_at=created_at or datetime.now(),
        alert_type=row.get("alert_type", ""),
        severity=row.get("severity", "info"),
        alert_status=row.get("alert_status", "open"),
        trend_direction=row.get("trend_direction"),
        current_value=row.get("current_value"),
        previous_value=row.get("previous_value"),
        delta_value=row.get("delta_value"),
        message=row.get("message"),
        recommended_action=row.get("recommended_action"),
        source_context=row.get("source_context"),
        notes=row.get("notes"),
    )


def _get_alert_report_rows(
    database_path: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> List[dict]:
    """Get alert report rows with property address context."""
    if not table_exists("cross_site_trend_alerts", database_path):
        return []

    try:
        conditions = []
        params: list = []

        if status_filter:
            conditions.append("a.alert_status = ?")
            params.append(status_filter)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
        SELECT a.*, wp.address, wp.city, wp.zip
        FROM cross_site_trend_alerts a
        LEFT JOIN watched_properties wp ON a.property_id = wp.property_id
        WHERE {where_clause}
        ORDER BY a.created_at DESC
        """

        results = execute_query(query, tuple(params), database_path=database_path)

        rows = []
        for r in results:
            row_dict = dict(r)
            rows.append({
                "alert_id": row_dict.get("alert_id"),
                "property_id": row_dict.get("property_id"),
                "candidate_id": row_dict.get("candidate_id"),
                "address": row_dict.get("address"),
                "city": row_dict.get("city"),
                "zip": row_dict.get("zip"),
                "alert_type": row_dict.get("alert_type"),
                "severity": row_dict.get("severity"),
                "alert_status": row_dict.get("alert_status"),
                "trend_direction": row_dict.get("trend_direction"),
                "current_value": row_dict.get("current_value"),
                "previous_value": row_dict.get("previous_value"),
                "delta_value": row_dict.get("delta_value"),
                "message": row_dict.get("message"),
                "recommended_action": row_dict.get("recommended_action"),
                "source_context": row_dict.get("source_context"),
                "created_at": row_dict.get("created_at"),
                "notes": row_dict.get("notes"),
            })

        return rows

    except Exception as e:
        logger.error(f"Error getting alert report rows: {e}")
        return []
