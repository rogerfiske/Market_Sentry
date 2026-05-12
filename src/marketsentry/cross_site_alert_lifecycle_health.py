"""Property-Level Lifecycle Health Scoring.

Translates lifecycle/alert metrics into a read-only operator-facing health
score (0-100) for each watched property. Higher scores indicate better
operational lifecycle health.

This is an alert-management/operator-health metric only. It does not
indicate property desirability or investment quality. It does not mutate
alert status, watchlist status, or Redfin source-of-truth fields.

Milestone 36.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from marketsentry.models import (
    CrossSiteLifecycleHealthComponent,
    CrossSiteLifecycleHealthReportRow,
    CrossSiteLifecycleHealthRunResult,
    CrossSiteLifecycleHealthScore,
    CrossSiteLifecycleHealthSummary,
)

logger = logging.getLogger(__name__)

# Health label thresholds
_LABEL_EXCELLENT = "excellent"
_LABEL_GOOD = "good"
_LABEL_WATCH = "watch"
_LABEL_NEEDS_REVIEW = "needs_review"
_LABEL_ATTENTION_REQUIRED = "attention_required"

# Alert burden labels
_BURDEN_NONE = "none"
_BURDEN_LOW = "low"
_BURDEN_MODERATE = "moderate"
_BURDEN_HIGH = "high"

# Stale threshold (days)
_STALE_OPEN_DAYS = 7

HEALTH_CSV_FIELDNAMES = [
    "property_id",
    "candidate_id",
    "address",
    "city",
    "zip",
    "lifecycle_health_score",
    "lifecycle_health_label",
    "open_alert_count",
    "high_or_critical_open_alert_count",
    "lifecycle_gap_count",
    "stale_open_alert_count",
    "needs_reparse_count",
    "needs_manual_review_count",
    "alert_burden_label",
    "repeated_patterns",
    "oldest_open_alert_age_days",
    "avg_time_to_resolution_days",
    "latest_lifecycle_event_at",
    "component_summary",
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


def _classify_alert_burden(total_alerts: int, open_alerts: int) -> str:
    """Classify alert burden based on total and open counts."""
    if total_alerts == 0:
        return _BURDEN_NONE
    if open_alerts == 0:
        return _BURDEN_LOW
    if open_alerts <= 2:
        return _BURDEN_LOW
    if open_alerts <= 5:
        return _BURDEN_MODERATE
    return _BURDEN_HIGH


def _count_stale_open_alerts(
    alerts: List[dict],
    stale_days: int = _STALE_OPEN_DAYS,
) -> int:
    """Count open alerts older than stale_days threshold."""
    now = datetime.now()
    count = 0
    for alert in alerts:
        status = (alert.get("alert_status") or "").lower()
        if status != "open":
            continue
        created = alert.get("created_at", "")
        if not created:
            continue
        try:
            dt = datetime.fromisoformat(created)
            age = (now - dt).days
            if age >= stale_days:
                count += 1
        except (ValueError, TypeError):
            continue
    return count


def _count_repeated_patterns(alerts: List[dict]) -> int:
    """Count repeated unresolved alert type patterns for a property.

    A repeated pattern is when the same alert_type appears more than
    once with an open or acknowledged status.
    """
    type_counts: Dict[str, int] = {}
    for alert in alerts:
        status = (alert.get("alert_status") or "").lower()
        if status not in ("open", "acknowledged"):
            continue
        atype = (alert.get("alert_type") or "").lower()
        if atype:
            type_counts[atype] = type_counts.get(atype, 0) + 1
    return sum(1 for c in type_counts.values() if c > 1)


def _compute_avg_time_to_resolution(
    alerts: List[dict],
    triage_actions: Dict[int, List[dict]],
) -> Optional[float]:
    """Compute average time-to-resolution in days for resolved alerts."""
    deltas: List[float] = []
    for alert in alerts:
        aid = alert.get("alert_id")
        if not aid:
            continue
        status = (alert.get("alert_status") or "").lower()
        if status not in ("resolved", "archived"):
            continue
        created = alert.get("created_at", "")
        if not created:
            continue
        actions = triage_actions.get(aid, [])
        resolved_at = None
        for act in actions:
            ns = (act.get("new_status") or "").lower()
            if ns in ("resolved", "archived"):
                resolved_at = act.get("applied_at")
                break
        if not resolved_at:
            continue
        try:
            c_dt = datetime.fromisoformat(created)
            r_dt = datetime.fromisoformat(resolved_at)
            delta = (r_dt - c_dt).total_seconds() / 86400.0
            deltas.append(max(delta, 0.0))
        except (ValueError, TypeError):
            continue
    if deltas:
        return round(sum(deltas) / len(deltas), 2)
    return None


def classify_lifecycle_health_label(score: float) -> str:
    """Classify a numeric health score into a label.

    Args:
        score: Numeric health score 0-100.

    Returns:
        Health label string: excellent, good, watch,
        needs_review, or attention_required.
    """
    if score >= 90:
        return _LABEL_EXCELLENT
    if score >= 75:
        return _LABEL_GOOD
    if score >= 60:
        return _LABEL_WATCH
    if score >= 40:
        return _LABEL_NEEDS_REVIEW
    return _LABEL_ATTENTION_REQUIRED


def build_lifecycle_health_components(
    property_summary: "CrossSiteAlertLifecyclePropertySummary",
    stale_open_count: int,
    repeated_patterns: int,
    alert_burden_label: str,
) -> List[CrossSiteLifecycleHealthComponent]:
    """Build component breakdown for a property's health score.

    Each component represents a factor contributing to the score.
    Negative deltas indicate score reductions.

    Args:
        property_summary: The lifecycle summary for a property.
        stale_open_count: Count of stale open alerts.
        repeated_patterns: Count of repeated unresolved patterns.
        alert_burden_label: The burden classification.

    Returns:
        List of health score components.
    """
    from marketsentry.models import CrossSiteAlertLifecyclePropertySummary

    components: List[CrossSiteLifecycleHealthComponent] = []
    ps = property_summary

    # Open high/critical alerts: -10 each
    if ps.unresolved_high_or_critical_count > 0:
        delta = -10.0 * ps.unresolved_high_or_critical_count
        components.append(CrossSiteLifecycleHealthComponent(
            component_name="open_high_critical_alerts",
            component_score_delta=delta,
            severity="high",
            explanation=(
                f"{ps.unresolved_high_or_critical_count} open "
                f"high/critical alert(s) reduce operational health."
            ),
            supporting_count=ps.unresolved_high_or_critical_count,
        ))

    # Lifecycle gaps: -5 each
    if ps.lifecycle_gap_count > 0:
        delta = -5.0 * ps.lifecycle_gap_count
        components.append(CrossSiteLifecycleHealthComponent(
            component_name="lifecycle_gaps",
            component_score_delta=delta,
            severity="medium",
            explanation=(
                f"{ps.lifecycle_gap_count} lifecycle gap(s) "
                f"indicate pending workflow actions."
            ),
            supporting_count=ps.lifecycle_gap_count,
        ))

    # Stale open alerts: -4 each
    if stale_open_count > 0:
        delta = -4.0 * stale_open_count
        components.append(CrossSiteLifecycleHealthComponent(
            component_name="stale_open_alerts",
            component_score_delta=delta,
            severity="medium",
            explanation=(
                f"{stale_open_count} open alert(s) older than "
                f"{_STALE_OPEN_DAYS} days without triage action."
            ),
            supporting_count=stale_open_count,
        ))

    # Needs reparse backlog: -6 each
    if ps.needs_reparse_count > 0:
        delta = -6.0 * ps.needs_reparse_count
        components.append(CrossSiteLifecycleHealthComponent(
            component_name="needs_reparse_backlog",
            component_score_delta=delta,
            severity="medium",
            explanation=(
                f"{ps.needs_reparse_count} alert(s) marked "
                f"needs_reparse without resolution."
            ),
            supporting_count=ps.needs_reparse_count,
        ))

    # Needs manual review backlog: -6 each
    if ps.needs_manual_review_count > 0:
        delta = -6.0 * ps.needs_manual_review_count
        components.append(CrossSiteLifecycleHealthComponent(
            component_name="needs_manual_review_backlog",
            component_score_delta=delta,
            severity="medium",
            explanation=(
                f"{ps.needs_manual_review_count} alert(s) marked "
                f"needs_manual_review without follow-up."
            ),
            supporting_count=ps.needs_manual_review_count,
        ))

    # Repeated patterns: -3 each
    if repeated_patterns > 0:
        delta = -3.0 * repeated_patterns
        components.append(CrossSiteLifecycleHealthComponent(
            component_name="repeated_patterns",
            component_score_delta=delta,
            severity="low",
            explanation=(
                f"{repeated_patterns} repeated unresolved alert "
                f"type pattern(s) detected."
            ),
            supporting_count=repeated_patterns,
        ))

    # Old acknowledged alerts: -2 each
    if ps.acknowledged_alerts > 0:
        delta = -2.0 * ps.acknowledged_alerts
        components.append(CrossSiteLifecycleHealthComponent(
            component_name="old_acknowledged_alerts",
            component_score_delta=delta,
            severity="low",
            explanation=(
                f"{ps.acknowledged_alerts} acknowledged alert(s) "
                f"still pending resolution."
            ),
            supporting_count=ps.acknowledged_alerts,
        ))

    # High alert burden: -5
    if alert_burden_label == _BURDEN_HIGH:
        components.append(CrossSiteLifecycleHealthComponent(
            component_name="high_alert_burden",
            component_score_delta=-5.0,
            severity="medium",
            explanation="High alert burden indicates elevated workload.",
            supporting_count=ps.open_alerts,
        ))

    # Resolved archive candidates: +0 (neutral context)
    resolved_not_archived = ps.resolved_alerts
    if resolved_not_archived > 0:
        components.append(CrossSiteLifecycleHealthComponent(
            component_name="resolved_archive_candidates",
            component_score_delta=0.0,
            severity="info",
            explanation=(
                f"{resolved_not_archived} resolved alert(s) "
                f"may be candidates for archiving."
            ),
            supporting_count=resolved_not_archived,
        ))

    # Archived history: +0 (neutral context, score preserved)
    if ps.archived_alerts > 0:
        components.append(CrossSiteLifecycleHealthComponent(
            component_name="archived_history",
            component_score_delta=0.0,
            severity="info",
            explanation=(
                f"{ps.archived_alerts} archived alert(s). "
                f"Lifecycle history maintained."
            ),
            supporting_count=ps.archived_alerts,
        ))

    return components


def calculate_lifecycle_health_score_for_property(
    property_id: int,
    database_path: Optional[str] = None,
) -> CrossSiteLifecycleHealthScore:
    """Calculate the lifecycle health score for a single property.

    Starts at 100 and subtracts for operational health indicators
    such as open high/critical alerts, lifecycle gaps, stale alerts,
    unresolved backlogs, and repeated patterns. Read-only.

    Args:
        property_id: The property ID to score.
        database_path: Path to the SQLite database.

    Returns:
        CrossSiteLifecycleHealthScore with score, label, and components.
    """
    from marketsentry.cross_site_alert_lifecycle import (
        summarize_alert_lifecycle_for_property,
    )
    from marketsentry.database import execute_query, table_exists

    ps = summarize_alert_lifecycle_for_property(
        property_id=property_id,
        database_path=database_path,
    )

    score_obj = CrossSiteLifecycleHealthScore(
        property_id=property_id,
        address=ps.address,
        city=ps.city,
        zip_code=ps.zip_code,
        latest_lifecycle_event_at=ps.latest_event_at,
        oldest_open_alert_age_days=ps.oldest_open_alert_age_days,
    )

    # Get candidate_id if available
    if table_exists("cross_site_trend_alerts", database_path):
        try:
            rows = execute_query(
                "SELECT candidate_id FROM cross_site_trend_alerts "
                "WHERE property_id = ? AND candidate_id IS NOT NULL "
                "LIMIT 1",
                (property_id,),
                database_path,
            )
            if rows:
                d = _row_to_dict(rows[0])
                score_obj.candidate_id = d.get("candidate_id")
        except Exception:
            pass

    # Get raw alerts for stale/repeated pattern analysis
    raw_alerts: List[dict] = []
    if table_exists("cross_site_trend_alerts", database_path):
        try:
            rows = execute_query(
                "SELECT alert_id, alert_type, severity, alert_status, "
                "created_at, notes "
                "FROM cross_site_trend_alerts WHERE property_id = ?",
                (property_id,),
                database_path,
            )
            raw_alerts = [_row_to_dict(r) for r in rows]
        except Exception:
            pass

    # Get triage actions for time-to-resolution
    triage_actions: Dict[int, List[dict]] = {}
    if table_exists("cross_site_alert_triage_actions", database_path):
        try:
            rows = execute_query(
                "SELECT alert_id, action, new_status, applied_at "
                "FROM cross_site_alert_triage_actions "
                "WHERE property_id = ?",
                (property_id,),
                database_path,
            )
            for r in rows:
                d = _row_to_dict(r)
                aid = d.get("alert_id")
                if aid is not None:
                    if aid not in triage_actions:
                        triage_actions[aid] = []
                    triage_actions[aid].append(d)
        except Exception:
            pass

    # Compute derived metrics
    stale_count = _count_stale_open_alerts(raw_alerts)
    repeated = _count_repeated_patterns(raw_alerts)
    burden = _classify_alert_burden(ps.total_alerts, ps.open_alerts)
    avg_res = _compute_avg_time_to_resolution(raw_alerts, triage_actions)

    score_obj.open_alert_count = ps.open_alerts
    score_obj.high_or_critical_open_alert_count = (
        ps.unresolved_high_or_critical_count
    )
    score_obj.lifecycle_gap_count = ps.lifecycle_gap_count
    score_obj.stale_open_alert_count = stale_count
    score_obj.needs_reparse_count = ps.needs_reparse_count
    score_obj.needs_manual_review_count = ps.needs_manual_review_count
    score_obj.alert_burden_label = burden
    score_obj.repeated_patterns = repeated
    score_obj.avg_time_to_resolution_days = avg_res

    # Build components
    components = build_lifecycle_health_components(
        property_summary=ps,
        stale_open_count=stale_count,
        repeated_patterns=repeated,
        alert_burden_label=burden,
    )
    score_obj.components = components

    # Calculate score: start at 100, apply deltas, clamp 0-100
    raw_score = 100.0
    for comp in components:
        raw_score += comp.component_score_delta
    raw_score = max(0.0, min(100.0, raw_score))
    score_obj.lifecycle_health_score = round(raw_score, 1)
    score_obj.lifecycle_health_label = classify_lifecycle_health_label(
        raw_score,
    )

    # Recommended action
    score_obj.recommended_review_action = _compute_health_action(
        score_obj,
    )

    return score_obj


def _compute_health_action(
    score: CrossSiteLifecycleHealthScore,
) -> str:
    """Determine the recommended review action based on health score."""
    if score.lifecycle_health_label == _LABEL_ATTENTION_REQUIRED:
        return (
            "Immediate review recommended. "
            "Address open high-severity alerts and lifecycle gaps."
        )
    if score.lifecycle_health_label == _LABEL_NEEDS_REVIEW:
        return (
            "Review recommended. "
            "Triage open alerts and resolve backlogs."
        )
    if score.lifecycle_health_label == _LABEL_WATCH:
        return "Monitor. Address lifecycle gaps when possible."
    if score.lifecycle_health_label == _LABEL_GOOD:
        return "No immediate action needed. Continue monitoring."
    return "No action needed."


def calculate_lifecycle_health_scores(
    database_path: Optional[str] = None,
) -> List[CrossSiteLifecycleHealthScore]:
    """Calculate lifecycle health scores for all watched properties.

    Scores every property that has at least one alert in the
    cross_site_trend_alerts table. Read-only.

    Args:
        database_path: Path to the SQLite database.

    Returns:
        List of health scores, one per scored property.
    """
    from marketsentry.database import execute_query, table_exists

    scores: List[CrossSiteLifecycleHealthScore] = []

    if not table_exists("cross_site_trend_alerts", database_path):
        return scores

    try:
        raw = execute_query(
            "SELECT DISTINCT property_id FROM cross_site_trend_alerts",
            database_path=database_path,
        )
    except Exception:
        return scores

    property_ids = [
        _row_to_dict(r)["property_id"]
        for r in raw
        if _row_to_dict(r).get("property_id")
    ]

    for pid in property_ids:
        score = calculate_lifecycle_health_score_for_property(
            property_id=pid,
            database_path=database_path,
        )
        scores.append(score)

    # Sort by score ascending (worst first)
    scores.sort(key=lambda s: s.lifecycle_health_score)
    return scores


def summarize_lifecycle_health_scores(
    scores: List[CrossSiteLifecycleHealthScore],
) -> CrossSiteLifecycleHealthSummary:
    """Build an aggregate summary from a list of health scores.

    Args:
        scores: List of per-property health scores.

    Returns:
        CrossSiteLifecycleHealthSummary with label counts and top properties.
    """
    summary = CrossSiteLifecycleHealthSummary()
    summary.properties_scored = len(scores)

    label_counts: Dict[str, int] = {
        _LABEL_EXCELLENT: 0,
        _LABEL_GOOD: 0,
        _LABEL_WATCH: 0,
        _LABEL_NEEDS_REVIEW: 0,
        _LABEL_ATTENTION_REQUIRED: 0,
    }

    for sc in scores:
        label = sc.lifecycle_health_label
        if label in label_counts:
            label_counts[label] += 1

    summary.label_counts = label_counts
    summary.attention_required_count = label_counts[_LABEL_ATTENTION_REQUIRED]
    summary.needs_review_count = label_counts[_LABEL_NEEDS_REVIEW]

    # Top properties by lowest health score (already sorted ascending)
    summary.lowest_health_properties = scores[:5]

    # Recommended next actions
    if summary.attention_required_count > 0:
        summary.recommended_next_actions.append(
            f"Review {summary.attention_required_count} property(ies) "
            f"with attention_required status."
        )
    if summary.needs_review_count > 0:
        summary.recommended_next_actions.append(
            f"Review {summary.needs_review_count} property(ies) "
            f"with needs_review status."
        )
    if not summary.recommended_next_actions:
        summary.recommended_next_actions.append(
            "No immediate actions needed. Continue monitoring."
        )

    return summary


def export_lifecycle_health_report(
    database_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    format: str = "csv",
) -> CrossSiteLifecycleHealthRunResult:
    """Export lifecycle health scores report.

    Calculates health scores for all properties and writes a CSV
    and/or Markdown report. Read-only. Does not mutate alerts.

    Args:
        database_path: Path to the SQLite database.
        output_dir: Directory for output files.
        format: Report format - 'csv', 'md', or 'both'.

    Returns:
        CrossSiteLifecycleHealthRunResult with scores and export paths.
    """
    result = CrossSiteLifecycleHealthRunResult()

    scores = calculate_lifecycle_health_scores(
        database_path=database_path,
    )
    result.scores = scores

    summary = summarize_lifecycle_health_scores(scores)
    result.summary = summary

    if not scores:
        result.warnings.append("No properties with alerts found to score.")
        return result

    out_dir = Path(output_dir) if output_dir else Path("data/exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Build report rows
    report_rows: List[CrossSiteLifecycleHealthReportRow] = []
    for sc in scores:
        comp_parts = []
        for c in sc.components:
            if c.component_score_delta != 0:
                comp_parts.append(
                    f"{c.component_name}:{c.component_score_delta:+.0f}"
                )
        comp_summary = "; ".join(comp_parts) if comp_parts else "no deductions"

        row = CrossSiteLifecycleHealthReportRow(
            property_id=sc.property_id,
            candidate_id=sc.candidate_id,
            address=sc.address,
            city=sc.city,
            zip_code=sc.zip_code,
            lifecycle_health_score=sc.lifecycle_health_score,
            lifecycle_health_label=sc.lifecycle_health_label,
            open_alert_count=sc.open_alert_count,
            high_or_critical_open_alert_count=(
                sc.high_or_critical_open_alert_count
            ),
            lifecycle_gap_count=sc.lifecycle_gap_count,
            stale_open_alert_count=sc.stale_open_alert_count,
            needs_reparse_count=sc.needs_reparse_count,
            needs_manual_review_count=sc.needs_manual_review_count,
            alert_burden_label=sc.alert_burden_label,
            repeated_patterns=sc.repeated_patterns,
            oldest_open_alert_age_days=sc.oldest_open_alert_age_days,
            avg_time_to_resolution_days=sc.avg_time_to_resolution_days,
            latest_lifecycle_event_at=sc.latest_lifecycle_event_at,
            component_summary=comp_summary,
            recommended_review_action=sc.recommended_review_action,
        )
        report_rows.append(row)

    if format in ("csv", "both"):
        csv_path = out_dir / f"cross_site_lifecycle_health_{ts}.csv"
        _write_health_csv(csv_path, report_rows)
        result.export_paths.append(str(csv_path))

    if format in ("md", "both"):
        md_path = out_dir / f"cross_site_lifecycle_health_{ts}.md"
        _write_health_md(md_path, scores, summary)
        result.export_paths.append(str(md_path))

    return result


def _write_health_csv(
    path: Path,
    rows: List[CrossSiteLifecycleHealthReportRow],
) -> None:
    """Write health report rows to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEALTH_CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "property_id": row.property_id,
                "candidate_id": row.candidate_id or "",
                "address": row.address,
                "city": row.city,
                "zip": row.zip_code,
                "lifecycle_health_score": row.lifecycle_health_score,
                "lifecycle_health_label": row.lifecycle_health_label,
                "open_alert_count": row.open_alert_count,
                "high_or_critical_open_alert_count": (
                    row.high_or_critical_open_alert_count
                ),
                "lifecycle_gap_count": row.lifecycle_gap_count,
                "stale_open_alert_count": row.stale_open_alert_count,
                "needs_reparse_count": row.needs_reparse_count,
                "needs_manual_review_count": row.needs_manual_review_count,
                "alert_burden_label": row.alert_burden_label,
                "repeated_patterns": row.repeated_patterns,
                "oldest_open_alert_age_days": (
                    row.oldest_open_alert_age_days
                    if row.oldest_open_alert_age_days is not None
                    else ""
                ),
                "avg_time_to_resolution_days": (
                    row.avg_time_to_resolution_days
                    if row.avg_time_to_resolution_days is not None
                    else ""
                ),
                "latest_lifecycle_event_at": (
                    row.latest_lifecycle_event_at or ""
                ),
                "component_summary": row.component_summary,
                "recommended_review_action": row.recommended_review_action,
            })


def _write_health_md(
    path: Path,
    scores: List[CrossSiteLifecycleHealthScore],
    summary: CrossSiteLifecycleHealthSummary,
) -> None:
    """Write health report as Markdown."""
    lines = [
        "# Cross-Site Lifecycle Health Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- Properties scored: {summary.properties_scored}",
    ]

    for label, count in summary.label_counts.items():
        lines.append(f"- {label}: {count}")

    lines.append("")

    if summary.recommended_next_actions:
        lines.append("## Recommended Next Actions")
        lines.append("")
        for action in summary.recommended_next_actions:
            lines.append(f"- {action}")
        lines.append("")

    if summary.lowest_health_properties:
        lines.append("## Lowest Health Score Properties")
        lines.append("")
        lines.append(
            "| Property ID | Address | Score | Label | Action |"
        )
        lines.append(
            "|-------------|---------|-------|-------|--------|"
        )
        for sc in summary.lowest_health_properties:
            lines.append(
                f"| {sc.property_id} "
                f"| {sc.address} "
                f"| {sc.lifecycle_health_score} "
                f"| {sc.lifecycle_health_label} "
                f"| {sc.recommended_review_action} |"
            )
        lines.append("")

    lines.append("## All Properties")
    lines.append("")
    lines.append(
        "| Property ID | Address | Score | Label "
        "| Open | High/Crit | Gaps | Action |"
    )
    lines.append(
        "|-------------|---------|-------|-------"
        "|------|-----------|------|--------|"
    )
    for sc in scores:
        lines.append(
            f"| {sc.property_id} "
            f"| {sc.address} "
            f"| {sc.lifecycle_health_score} "
            f"| {sc.lifecycle_health_label} "
            f"| {sc.open_alert_count} "
            f"| {sc.high_or_critical_open_alert_count} "
            f"| {sc.lifecycle_gap_count} "
            f"| {sc.recommended_review_action} |"
        )

    lines.append("")
    lines.append(
        "*This report is read-only. "
        "It does not mutate alert or watchlist state.*"
    )

    path.write_text("\n".join(lines), encoding="utf-8")
