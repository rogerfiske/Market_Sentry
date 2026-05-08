"""Cross-site alert aggregation and historical pattern analysis.

Aggregates individual cross-site trend alerts (Milestone 26) into
property-level burden metrics and repeated discrepancy patterns.

These are neutral analytical review signals only. They are not
purchase recommendations and must not infer seller intent.

Cross-site data remains validation/check data. It does not overwrite
Redfin source-of-truth fields, user decisions, watchlist status,
or Quiet Score gatekeeper results.
"""

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from marketsentry.database import execute_query, table_exists
from marketsentry.logging_config import logger
from marketsentry.models import (
    CrossSiteAlertAggregationResult,
    CrossSiteAlertAnalyticsReportRow,
    CrossSiteAlertBurdenMetrics,
    CrossSiteAlertHistorySummary,
    CrossSiteAlertPattern,
)


# ---------------------------------------------------------------------------
# Severity rank for burden scoring
# ---------------------------------------------------------------------------

_SEVERITY_WEIGHT = {"info": 1, "warning": 2, "high": 4, "critical": 8}


# ---------------------------------------------------------------------------
# Property-level alert burden
# ---------------------------------------------------------------------------


def calculate_alert_burden_for_property(
    property_id: int,
    database_path: Optional[str] = None,
) -> CrossSiteAlertBurdenMetrics:
    """Calculate alert burden metrics for a single property.

    Args:
        property_id: Watched property ID.
        database_path: Optional database path.

    Returns:
        CrossSiteAlertBurdenMetrics with burden score and label.
    """
    metrics = CrossSiteAlertBurdenMetrics(property_id=property_id)

    if not table_exists("cross_site_trend_alerts", database_path):
        return metrics

    try:
        alerts = _get_alerts_for_property(property_id, database_path)
        if not alerts:
            return metrics

        metrics.total_alert_count = len(alerts)

        # Candidate ID from first alert
        for a in alerts:
            if a.get("candidate_id"):
                metrics.candidate_id = a["candidate_id"]
                break

        # Status counts
        open_alerts = [a for a in alerts if a["alert_status"] == "open"]
        metrics.open_alert_count = len(open_alerts)
        metrics.acknowledged_alert_count = len(
            [a for a in alerts if a["alert_status"] == "acknowledged"]
        )
        metrics.resolved_alert_count = len(
            [a for a in alerts if a["alert_status"] == "resolved"]
        )

        # High/critical open
        metrics.high_or_critical_open_alert_count = len(
            [a for a in open_alerts if a["severity"] in ("high", "critical")]
        )

        # Oldest open alert age
        if open_alerts:
            metrics.oldest_open_alert_age_days = _oldest_alert_age_days(open_alerts)

        # Latest alert timestamp
        if alerts:
            latest = max(a.get("created_at", "") for a in alerts)
            metrics.latest_alert_at = latest if latest else None

        # Most common alert type and severity
        type_counter = Counter(a["alert_type"] for a in alerts)
        sev_counter = Counter(a["severity"] for a in alerts)

        if type_counter:
            metrics.most_common_alert_type = type_counter.most_common(1)[0][0]
        if sev_counter:
            metrics.most_common_severity = sev_counter.most_common(1)[0][0]

        # Repeated alert types (same type appears 2+ times)
        repeated = {t for t, c in type_counter.items() if c >= 2}
        metrics.repeated_alert_type_count = len(repeated)

        # Burden score and label
        metrics.alert_burden_score = _calculate_burden_score(alerts, open_alerts)
        critical_open = len(
            [a for a in open_alerts if a["severity"] == "critical"]
        )
        metrics.alert_burden_label = classify_alert_burden_level(
            metrics, _has_repeated_high_critical(alerts), critical_open
        )

    except Exception as e:
        logger.error(f"Error calculating burden for property {property_id}: {e}")

    return metrics


# ---------------------------------------------------------------------------
# Alert age
# ---------------------------------------------------------------------------


def calculate_alert_age_days(created_at_str: Optional[str]) -> Optional[int]:
    """Calculate age in days from a created_at timestamp string.

    Args:
        created_at_str: ISO timestamp string.

    Returns:
        Age in days, or None if parsing fails.
    """
    if not created_at_str:
        return None
    try:
        created = datetime.fromisoformat(str(created_at_str))
        delta = datetime.now() - created
        return max(0, delta.days)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Burden classification
# ---------------------------------------------------------------------------


def classify_alert_burden_level(
    metrics: CrossSiteAlertBurdenMetrics,
    has_repeated_high_critical: bool = False,
    critical_open_count: int = 0,
) -> str:
    """Classify alert burden level based on metrics.

    Args:
        metrics: Property-level burden metrics.
        has_repeated_high_critical: Whether high/critical alerts repeat over time.
        critical_open_count: Number of open alerts with critical severity.

    Returns:
        Burden label: none, low, moderate, high, or elevated_review.
    """
    if metrics.open_alert_count == 0:
        return "none"

    # Elevated review: repeated high/critical pattern
    if has_repeated_high_critical:
        return "elevated_review"

    # High: 2+ high/critical open alerts or any critical open alert
    if critical_open_count > 0:
        return "high"
    if metrics.high_or_critical_open_alert_count >= 2:
        return "high"

    # Moderate: 3+ open alerts or any high open alert
    if metrics.open_alert_count >= 3:
        return "moderate"
    if metrics.high_or_critical_open_alert_count >= 1:
        return "moderate"

    # Low: 1-2 low/warning open alerts
    return "low"


def _count_open_by_severity(
    metrics: CrossSiteAlertBurdenMetrics, severity: str,
) -> int:
    """Count open alerts by severity (uses high_or_critical count for high/critical)."""
    # We can't distinguish exactly, so use the combined field
    if severity == "critical":
        # Approximate: if any critical, high_or_critical > 0
        return metrics.high_or_critical_open_alert_count
    if severity == "high":
        return metrics.high_or_critical_open_alert_count
    return 0


# ---------------------------------------------------------------------------
# Pattern identification
# ---------------------------------------------------------------------------


_PATTERN_ALERT_TYPE_MAP = {
    "repeated_confidence_drop": "confidence_drop",
    "repeated_status_discrepancy": "status_agreement_degraded",
    "repeated_price_agreement_degraded": "price_agreement_degraded",
    "repeated_dom_agreement_degraded": "dom_agreement_degraded",
    "repeated_stale_sources": "stale_sources_increased",
    "repeated_low_confidence_sources": "low_confidence_sources_increased",
    "recurring_high_severity_alerts": None,  # special case
    "improving_source_quality_pattern": "source_quality_improved",
}

_PATTERN_MESSAGES = {
    "repeated_confidence_drop": "Recurring confidence drops may indicate unstable cross-site data",
    "repeated_status_discrepancy": "Recurring status disagreement across sources",
    "repeated_price_agreement_degraded": "Recurring price disagreement across sources",
    "repeated_dom_agreement_degraded": "Recurring DOM disagreement across sources",
    "repeated_stale_sources": "Recurring stale source data",
    "repeated_low_confidence_sources": "Recurring low-confidence source data",
    "recurring_high_severity_alerts": "Recurring high-severity or critical alerts",
    "improving_source_quality_pattern": "Source quality improving over time",
}

_PATTERN_ACTIONS = {
    "repeated_confidence_drop": "Review cross-site data quality and consider re-parsing fixtures",
    "repeated_status_discrepancy": "Verify listing status across sources manually",
    "repeated_price_agreement_degraded": "Verify listing price across sources manually",
    "repeated_dom_agreement_degraded": "Verify DOM values across sources manually",
    "repeated_stale_sources": "Consider refreshing cross-site fixture data",
    "repeated_low_confidence_sources": "Consider re-parsing or updating cross-site fixtures",
    "recurring_high_severity_alerts": "Prioritize review of this property's cross-site data",
    "improving_source_quality_pattern": "Continue monitoring; cross-site data improving",
}


def identify_repeated_alert_patterns(
    property_id: int,
    database_path: Optional[str] = None,
) -> List[CrossSiteAlertPattern]:
    """Identify repeated alert patterns for a property.

    A pattern requires at least 2 matching events.

    Args:
        property_id: Watched property ID.
        database_path: Optional database path.

    Returns:
        List of CrossSiteAlertPattern.
    """
    patterns: List[CrossSiteAlertPattern] = []

    if not table_exists("cross_site_trend_alerts", database_path):
        return patterns

    try:
        alerts = _get_alerts_for_property(property_id, database_path)
        if not alerts:
            return patterns

        # Group alerts by type
        by_type: Dict[str, list] = {}
        for a in alerts:
            by_type.setdefault(a["alert_type"], []).append(a)

        # Check each pattern type
        for pattern_type, alert_type in _PATTERN_ALERT_TYPE_MAP.items():
            if pattern_type == "recurring_high_severity_alerts":
                # Special case: 2+ high or critical alerts of any type
                high_crit = [
                    a for a in alerts if a["severity"] in ("high", "critical")
                ]
                if len(high_crit) >= 2:
                    patterns.append(_build_pattern(
                        property_id, pattern_type, high_crit
                    ))
                continue

            if alert_type and alert_type in by_type:
                matching = by_type[alert_type]
                if len(matching) >= 2:
                    patterns.append(_build_pattern(
                        property_id, pattern_type, matching
                    ))

    except Exception as e:
        logger.error(
            f"Error identifying patterns for property {property_id}: {e}"
        )

    return patterns


def _build_pattern(
    property_id: int,
    pattern_type: str,
    matching_alerts: List[dict],
) -> CrossSiteAlertPattern:
    """Build a CrossSiteAlertPattern from matching alerts."""
    timestamps = sorted(
        a.get("created_at", "") for a in matching_alerts if a.get("created_at")
    )
    severities = Counter(a["severity"] for a in matching_alerts)
    statuses = Counter(a["alert_status"] for a in matching_alerts)

    return CrossSiteAlertPattern(
        property_id=property_id,
        pattern_type=pattern_type,
        count=len(matching_alerts),
        first_seen=timestamps[0] if timestamps else None,
        latest_seen=timestamps[-1] if timestamps else None,
        severity_summary=", ".join(
            f"{k}:{v}" for k, v in severities.most_common()
        ),
        status_summary=", ".join(
            f"{k}:{v}" for k, v in statuses.most_common()
        ),
        message=_PATTERN_MESSAGES.get(pattern_type, ""),
        recommended_review_action=_PATTERN_ACTIONS.get(pattern_type, ""),
    )


# ---------------------------------------------------------------------------
# Property-level history summary
# ---------------------------------------------------------------------------


def summarize_alert_history_for_property(
    property_id: int,
    prop: Optional[Dict] = None,
    database_path: Optional[str] = None,
) -> CrossSiteAlertHistorySummary:
    """Build full alert history summary for a property.

    Combines burden metrics and repeated patterns.

    Args:
        property_id: Watched property ID.
        prop: Optional property dict with address/city/zip.
        database_path: Optional database path.

    Returns:
        CrossSiteAlertHistorySummary.
    """
    burden = calculate_alert_burden_for_property(property_id, database_path)
    patterns = identify_repeated_alert_patterns(property_id, database_path)

    summary = CrossSiteAlertHistorySummary(
        property_id=property_id,
        candidate_id=burden.candidate_id,
        address=prop.get("address") if prop else None,
        city=prop.get("city") if prop else None,
        zip=prop.get("zip") if prop else None,
        burden=burden,
        patterns=patterns,
    )

    # Determine recommended review action
    summary.recommended_review_action = _determine_review_action(burden, patterns)

    return summary


# ---------------------------------------------------------------------------
# All-property aggregation
# ---------------------------------------------------------------------------


def summarize_alert_history_for_all_properties(
    database_path: Optional[str] = None,
    include_resolved: bool = True,
) -> CrossSiteAlertAggregationResult:
    """Aggregate alert analytics across all properties with alerts.

    Args:
        database_path: Optional database path.
        include_resolved: Include resolved alerts in analysis.

    Returns:
        CrossSiteAlertAggregationResult.
    """
    result = CrossSiteAlertAggregationResult()

    if not table_exists("cross_site_trend_alerts", database_path):
        return result

    try:
        # Get all properties that have alerts
        props = _get_properties_with_alerts(database_path)
        result.total_properties_with_alerts = len(props)

        if not props:
            return result

        all_type_counts: Counter = Counter()
        oldest_age: Optional[int] = None

        for prop in props:
            pid = prop["property_id"]
            summary = summarize_alert_history_for_property(pid, prop, database_path)
            result.summaries.append(summary)

            burden = summary.burden
            if burden.open_alert_count > 0:
                result.properties_with_open_alerts += 1
            if burden.high_or_critical_open_alert_count > 0:
                result.properties_with_high_critical_alerts += 1
            if summary.patterns:
                result.properties_with_repeated_patterns += 1

            # Track types
            alerts = _get_alerts_for_property(pid, database_path)
            for a in alerts:
                all_type_counts[a["alert_type"]] += 1

            # Oldest open alert
            if burden.oldest_open_alert_age_days is not None:
                if oldest_age is None or burden.oldest_open_alert_age_days > oldest_age:
                    oldest_age = burden.oldest_open_alert_age_days

        result.oldest_open_alert_age_days = oldest_age

        # Top alert types (up to 5)
        result.top_alert_types = [
            t for t, _ in all_type_counts.most_common(5)
        ]

        # Top properties by burden score (up to 5)
        sorted_summaries = sorted(
            result.summaries,
            key=lambda s: s.burden.alert_burden_score,
            reverse=True,
        )
        result.top_burden_properties = [
            s.property_id for s in sorted_summaries[:5]
            if s.burden.alert_burden_score > 0
        ]

    except Exception as e:
        msg = f"Error in alert aggregation: {e}"
        logger.error(msg)
        result.errors.append(msg)

    return result


# ---------------------------------------------------------------------------
# Report export
# ---------------------------------------------------------------------------

REPORT_FIELDNAMES = [
    "property_id",
    "candidate_id",
    "address",
    "city",
    "zip",
    "total_alert_count",
    "open_alert_count",
    "high_or_critical_open_alert_count",
    "oldest_open_alert_age_days",
    "latest_alert_at",
    "most_common_alert_type",
    "most_common_severity",
    "repeated_patterns",
    "alert_burden_score",
    "alert_burden_label",
    "recommended_review_action",
    "unresolved_alert_types",
    "resolved_alert_count",
    "acknowledged_alert_count",
]


def export_cross_site_alert_analytics_report(
    database_path: Optional[str] = None,
    output_path: Optional[str] = None,
    include_resolved: bool = True,
) -> str:
    """Export cross-site alert analytics report to CSV.

    Args:
        database_path: Optional database path.
        output_path: Optional output file path.
        include_resolved: Include resolved alerts in analysis.

    Returns:
        Path to the generated CSV file.
    """
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/exports")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"cross_site_alert_analytics_{ts}.csv")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Generating cross-site alert analytics report: {output_path}")

    try:
        agg = summarize_alert_history_for_all_properties(
            database_path, include_resolved
        )

        rows = []
        for summary in agg.summaries:
            burden = summary.burden
            pattern_strs = [p.pattern_type for p in summary.patterns]
            unresolved = _get_unresolved_alert_types(
                summary.property_id, database_path
            )

            rows.append({
                "property_id": summary.property_id,
                "candidate_id": summary.candidate_id,
                "address": summary.address,
                "city": summary.city,
                "zip": summary.zip,
                "total_alert_count": burden.total_alert_count,
                "open_alert_count": burden.open_alert_count,
                "high_or_critical_open_alert_count": burden.high_or_critical_open_alert_count,
                "oldest_open_alert_age_days": burden.oldest_open_alert_age_days,
                "latest_alert_at": burden.latest_alert_at,
                "most_common_alert_type": burden.most_common_alert_type,
                "most_common_severity": burden.most_common_severity,
                "repeated_patterns": "; ".join(pattern_strs) if pattern_strs else "",
                "alert_burden_score": f"{burden.alert_burden_score:.2f}",
                "alert_burden_label": burden.alert_burden_label,
                "recommended_review_action": summary.recommended_review_action or "",
                "unresolved_alert_types": "; ".join(unresolved) if unresolved else "",
                "resolved_alert_count": burden.resolved_alert_count,
                "acknowledged_alert_count": burden.acknowledged_alert_count,
            })

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=REPORT_FIELDNAMES)
            writer.writeheader()
            if rows:
                writer.writerows(rows)

        logger.info(f"Exported {len(rows)} properties to {output_path}")
        return str(output_file)

    except Exception as e:
        logger.error(f"Error exporting alert analytics report: {e}")
        raise


# ---------------------------------------------------------------------------
# Watchlist monitoring integration
# ---------------------------------------------------------------------------


def get_alert_analytics_for_property(
    property_id: int,
    database_path: Optional[str] = None,
) -> Dict:
    """Get alert analytics fields for watchlist monitoring reports.

    Args:
        property_id: Watched property ID.
        database_path: Optional database path.

    Returns:
        Dict with alert aggregation fields for report integration.
    """
    result: Dict = {
        "cross_site_alert_burden_label": "none",
        "cross_site_alert_burden_score": 0.0,
        "cross_site_repeated_patterns": "",
        "cross_site_oldest_open_alert_age_days": None,
    }

    if not table_exists("cross_site_trend_alerts", database_path):
        return result

    try:
        burden = calculate_alert_burden_for_property(property_id, database_path)
        patterns = identify_repeated_alert_patterns(property_id, database_path)

        result["cross_site_alert_burden_label"] = burden.alert_burden_label
        result["cross_site_alert_burden_score"] = burden.alert_burden_score
        result["cross_site_repeated_patterns"] = "; ".join(
            p.pattern_type for p in patterns
        )
        result["cross_site_oldest_open_alert_age_days"] = (
            burden.oldest_open_alert_age_days
        )

    except Exception as e:
        logger.error(
            f"Error getting alert analytics for property {property_id}: {e}"
        )

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_alerts_for_property(
    property_id: int,
    database_path: Optional[str] = None,
) -> List[dict]:
    """Get all alerts for a property from the database."""
    try:
        query = """
        SELECT alert_id, property_id, candidate_id, snapshot_id,
               alert_type, severity, alert_status, trend_direction,
               current_value, previous_value, delta_value,
               message, recommended_action, source_context,
               created_at, notes
        FROM cross_site_trend_alerts
        WHERE property_id = ?
        ORDER BY created_at ASC
        """
        results = execute_query(query, (property_id,), database_path=database_path)
        return [dict(r) for r in results]
    except Exception as e:
        logger.error(f"Error getting alerts for property {property_id}: {e}")
        return []


def _get_properties_with_alerts(
    database_path: Optional[str] = None,
) -> List[dict]:
    """Get all properties that have alerts, with address context."""
    try:
        query = """
        SELECT DISTINCT a.property_id, wp.address, wp.city, wp.zip
        FROM cross_site_trend_alerts a
        LEFT JOIN watched_properties wp ON a.property_id = wp.property_id
        ORDER BY a.property_id
        """
        results = execute_query(query, database_path=database_path)
        return [dict(r) for r in results]
    except Exception as e:
        logger.error(f"Error getting properties with alerts: {e}")
        return []


def _oldest_alert_age_days(alerts: List[dict]) -> Optional[int]:
    """Calculate oldest alert age in days from a list of alert dicts."""
    oldest = None
    for a in alerts:
        age = calculate_alert_age_days(a.get("created_at"))
        if age is not None:
            if oldest is None or age > oldest:
                oldest = age
    return oldest


def _calculate_burden_score(
    all_alerts: List[dict], open_alerts: List[dict],
) -> float:
    """Calculate numeric burden score.

    Scoring heuristic:
    - Each open alert: base 1 point * severity weight
    - Each acknowledged alert: 0.5 * severity weight
    - Each resolved alert: 0.1 * severity weight
    """
    score = 0.0
    for a in all_alerts:
        weight = _SEVERITY_WEIGHT.get(a["severity"], 1)
        status = a["alert_status"]
        if status == "open":
            score += 1.0 * weight
        elif status == "acknowledged":
            score += 0.5 * weight
        elif status == "resolved":
            score += 0.1 * weight
    return round(score, 2)


def _has_repeated_high_critical(alerts: List[dict]) -> bool:
    """Check if high/critical alerts repeat over multiple snapshots."""
    high_crit = [a for a in alerts if a["severity"] in ("high", "critical")]
    if len(high_crit) < 2:
        return False
    # Check they come from different snapshots
    snapshot_ids = set(a.get("snapshot_id") for a in high_crit)
    return len(snapshot_ids) >= 2


def _get_unresolved_alert_types(
    property_id: int,
    database_path: Optional[str] = None,
) -> List[str]:
    """Get distinct unresolved (open or acknowledged) alert types."""
    try:
        query = """
        SELECT DISTINCT alert_type FROM cross_site_trend_alerts
        WHERE property_id = ? AND alert_status IN ('open', 'acknowledged')
        ORDER BY alert_type
        """
        results = execute_query(query, (property_id,), database_path=database_path)
        return [r["alert_type"] for r in results]
    except Exception:
        return []


def _determine_review_action(
    burden: CrossSiteAlertBurdenMetrics,
    patterns: List[CrossSiteAlertPattern],
) -> str:
    """Determine recommended review action based on burden and patterns."""
    if burden.alert_burden_label == "elevated_review":
        return "Prioritize review: recurring high-severity cross-site discrepancies"
    if burden.alert_burden_label == "high":
        return "Review cross-site data: multiple high-severity alerts open"
    if burden.alert_burden_label == "moderate":
        return "Monitor cross-site data: moderate alert burden"
    if any(p.pattern_type == "improving_source_quality_pattern" for p in patterns):
        return "Cross-site data improving; continue monitoring"
    if burden.alert_burden_label == "low":
        return "Low alert burden; routine monitoring sufficient"
    return "No alert burden; no action needed"
