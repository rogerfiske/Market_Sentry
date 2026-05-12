"""Watchlist Operations Digest and Executive Summary Reports (Milestone 38).

This module consolidates all local reports into a single concise operator
digest.  It is entirely read-only except for writing export files.  It does
not mutate candidate, watchlist, alert, or property state.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from marketsentry.database import execute_query, get_connection, table_exists
from marketsentry.models import (
    OperationsDigestMetric,
    OperationsDigestNextAction,
    OperationsDigestPropertyPriority,
    OperationsDigestReportRow,
    OperationsDigestRunResult,
    OperationsDigestSection,
    OperationsDigestSummary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row: Any) -> Dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return {}
    return dict(row)


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert *val* to int."""
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert *val* to float."""
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _latest_file(directory: str, prefix: str, suffix: str) -> str:
    """Return the path of the most-recently modified file matching pattern."""
    d = Path(directory)
    if not d.is_dir():
        return ""
    matches = sorted(
        [f for f in d.iterdir() if f.name.startswith(prefix) and f.name.endswith(suffix)],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return str(matches[0]) if matches else ""


def _metric(name: str, value: Any, severity: str = "info",
            notes: str = "", path: str = "") -> OperationsDigestMetric:
    """Shorthand to build a metric."""
    return OperationsDigestMetric(
        metric_name=name,
        metric_value=str(value),
        severity=severity,
        notes=notes,
        source_report_path=path,
    )


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_candidate_review_digest(
    db_path: Optional[str] = None,
    exports_dir: str = "data/exports",
) -> OperationsDigestSection:
    """Build the candidate review queue section of the digest.

    Args:
        db_path: Database path.
        exports_dir: Directory containing exported reports.

    Returns:
        OperationsDigestSection with candidate metrics.
    """
    section = OperationsDigestSection(section_name="Candidate Review")
    metrics: List[OperationsDigestMetric] = []

    if not table_exists("candidate_review_queue", db_path):
        metrics.append(_metric("candidate_count", 0, notes="Table not found"))
        section.metrics = metrics
        return section

    rows = execute_query(
        "SELECT COUNT(*) AS cnt FROM candidate_review_queue", database_path=db_path
    )
    total = _safe_int(_row_to_dict(rows[0]).get("cnt")) if rows else 0
    metrics.append(_metric("candidate_count", total))

    for label in ("strong_review", "review", "maybe", "needs_more_data",
                  "reject_location_noise"):
        r = execute_query(
            "SELECT COUNT(*) AS cnt FROM candidate_review_queue "
            "WHERE user_decision = ?",
            (label,),
            database_path=db_path,
        )
        cnt = _safe_int(_row_to_dict(r[0]).get("cnt")) if r else 0
        metrics.append(_metric(f"{label}_count", cnt))

    pending = execute_query(
        "SELECT COUNT(*) AS cnt FROM candidate_review_queue "
        "WHERE user_decision IS NULL OR user_decision = ''",
        database_path=db_path,
    )
    pcnt = _safe_int(_row_to_dict(pending[0]).get("cnt")) if pending else 0
    sev = "warning" if pcnt > 0 else "info"
    metrics.append(_metric("pending_user_decision_count", pcnt, severity=sev))

    report_path = _latest_file(exports_dir, "candidate_analysis", ".csv")
    if report_path:
        metrics.append(_metric("latest_candidate_report", report_path))

    section.metrics = metrics
    return section


def build_watchlist_digest(
    db_path: Optional[str] = None,
    exports_dir: str = "data/exports",
) -> OperationsDigestSection:
    """Build the watchlist status section of the digest.

    Args:
        db_path: Database path.
        exports_dir: Directory containing exported reports.

    Returns:
        OperationsDigestSection with watchlist metrics.
    """
    section = OperationsDigestSection(section_name="Watchlist")
    metrics: List[OperationsDigestMetric] = []

    if not table_exists("watched_properties", db_path):
        metrics.append(_metric("watched_property_count", 0, notes="Table not found"))
        section.metrics = metrics
        return section

    total = execute_query(
        "SELECT COUNT(*) AS cnt FROM watched_properties", database_path=db_path
    )
    metrics.append(_metric("watched_property_count",
                           _safe_int(_row_to_dict(total[0]).get("cnt")) if total else 0))

    active = execute_query(
        "SELECT COUNT(*) AS cnt FROM watched_properties WHERE active_watch_status = 1",
        database_path=db_path,
    )
    metrics.append(_metric("active_watched_count",
                           _safe_int(_row_to_dict(active[0]).get("cnt")) if active else 0))

    high_pri = execute_query(
        "SELECT COUNT(*) AS cnt FROM watched_properties WHERE watch_priority = 1",
        database_path=db_path,
    )
    metrics.append(_metric("high_priority_count",
                           _safe_int(_row_to_dict(high_pri[0]).get("cnt")) if high_pri else 0))

    gas = execute_query(
        "SELECT COUNT(*) AS cnt FROM watched_properties WHERE gas_service = 1",
        database_path=db_path,
    )
    metrics.append(_metric("gas_evidence_count",
                           _safe_int(_row_to_dict(gas[0]).get("cnt")) if gas else 0))

    garage = execute_query(
        "SELECT COUNT(*) AS cnt FROM watched_properties WHERE garage_spaces IS NOT NULL AND garage_spaces > 0",
        database_path=db_path,
    )
    metrics.append(_metric("garage_evidence_count",
                           _safe_int(_row_to_dict(garage[0]).get("cnt")) if garage else 0))

    report_path = _latest_file(exports_dir, "watchlist_monitoring", ".csv")
    if report_path:
        metrics.append(_metric("latest_monitoring_report", report_path))

    section.metrics = metrics
    return section


def build_effective_dom_digest(
    db_path: Optional[str] = None,
    exports_dir: str = "data/exports",
) -> OperationsDigestSection:
    """Build the Effective DOM / Churn section of the digest.

    Args:
        db_path: Database path.
        exports_dir: Directory containing exported reports.

    Returns:
        OperationsDigestSection with DOM/churn metrics.
    """
    section = OperationsDigestSection(section_name="Effective DOM / Churn")
    metrics: List[OperationsDigestMetric] = []

    if not table_exists("watched_properties", db_path):
        section.metrics = metrics
        return section

    # These columns may come from migrations; handle gracefully if absent.
    try:
        county_reset = execute_query(
            "SELECT COUNT(*) AS cnt FROM watched_properties "
            "WHERE county_reset_applied = 1",
            database_path=db_path,
        )
        metrics.append(_metric("county_reset_applied_count",
                               _safe_int(_row_to_dict(county_reset[0]).get("cnt")) if county_reset else 0))
    except Exception:
        metrics.append(_metric("county_reset_applied_count", 0,
                               notes="Column not available"))

    try:
        high_churn = execute_query(
            "SELECT COUNT(*) AS cnt FROM watched_properties "
            "WHERE recent_churn_index IS NOT NULL AND recent_churn_index >= 5",
            database_path=db_path,
        )
        hc = _safe_int(_row_to_dict(high_churn[0]).get("cnt")) if high_churn else 0
        sev = "warning" if hc > 0 else "info"
        metrics.append(_metric("high_recent_churn_count", hc, severity=sev))
    except Exception:
        metrics.append(_metric("high_recent_churn_count", 0,
                               notes="Column not available"))

    try:
        dom_delta = execute_query(
            "SELECT COUNT(*) AS cnt FROM watched_properties "
            "WHERE effective_dom_v2 IS NOT NULL AND effective_dom IS NOT NULL "
            "AND effective_dom_v2 < effective_dom - 30",
            database_path=db_path,
        )
        metrics.append(_metric("v2_materially_below_v1_count",
                               _safe_int(_row_to_dict(dom_delta[0]).get("cnt")) if dom_delta else 0))
    except Exception:
        metrics.append(_metric("v2_materially_below_v1_count", 0,
                               notes="Column not available"))

    high_delta = execute_query(
        "SELECT COUNT(*) AS cnt FROM watched_properties "
        "WHERE effective_dom_delta IS NOT NULL AND effective_dom_delta > 60",
        database_path=db_path,
    )
    hd = _safe_int(_row_to_dict(high_delta[0]).get("cnt")) if high_delta else 0
    sev2 = "warning" if hd > 0 else "info"
    metrics.append(_metric("high_effective_dom_delta_count", hd, severity=sev2))

    report_path = _latest_file(exports_dir, "effective_dom_v2", ".csv")
    if report_path:
        metrics.append(_metric("latest_dom_v2_report", report_path))

    section.metrics = metrics
    return section


def build_cross_site_digest(
    db_path: Optional[str] = None,
    exports_dir: str = "data/exports",
) -> OperationsDigestSection:
    """Build the cross-site confidence and discrepancy section.

    Args:
        db_path: Database path.
        exports_dir: Directory containing exported reports.

    Returns:
        OperationsDigestSection with cross-site metrics.
    """
    section = OperationsDigestSection(section_name="Cross-Site Validation")
    metrics: List[OperationsDigestMetric] = []

    if table_exists("cross_site_observations", db_path):
        obs = execute_query(
            "SELECT COUNT(DISTINCT property_id) AS cnt FROM cross_site_observations",
            database_path=db_path,
        )
        metrics.append(_metric("properties_with_observations",
                               _safe_int(_row_to_dict(obs[0]).get("cnt")) if obs else 0))

    if table_exists("cross_site_analytics_snapshots", db_path):
        try:
            low_conf = execute_query(
                "SELECT COUNT(*) AS cnt FROM cross_site_analytics_snapshots "
                "WHERE overall_cross_site_confidence_score IS NOT NULL "
                "AND overall_cross_site_confidence_score < 0.5 "
                "AND snapshot_id IN ("
                "  SELECT MAX(snapshot_id) FROM cross_site_analytics_snapshots "
                "  GROUP BY property_id"
                ")",
                database_path=db_path,
            )
            lc = _safe_int(_row_to_dict(low_conf[0]).get("cnt")) if low_conf else 0
            sev = "warning" if lc > 0 else "info"
            metrics.append(_metric("low_cross_site_confidence_count", lc, severity=sev))
        except Exception:
            pass

        try:
            high_sev = execute_query(
                "SELECT COUNT(*) AS cnt FROM cross_site_analytics_snapshots "
                "WHERE discrepancy_severity_label IN ('high', 'critical') "
                "AND snapshot_id IN ("
                "  SELECT MAX(snapshot_id) FROM cross_site_analytics_snapshots "
                "  GROUP BY property_id"
                ")",
                database_path=db_path,
            )
            hs = _safe_int(_row_to_dict(high_sev[0]).get("cnt")) if high_sev else 0
            sev2 = "warning" if hs > 0 else "info"
            metrics.append(_metric("high_discrepancy_severity_count", hs, severity=sev2))
        except Exception:
            pass

    analytics_path = _latest_file(exports_dir, "cross_site_analytics", ".csv")
    if analytics_path:
        metrics.append(_metric("latest_analytics_report", analytics_path))

    trend_path = _latest_file(exports_dir, "cross_site_trend", ".csv")
    if trend_path:
        metrics.append(_metric("latest_trend_report", trend_path))

    section.metrics = metrics
    return section


def build_alert_digest(
    db_path: Optional[str] = None,
    exports_dir: str = "data/exports",
) -> OperationsDigestSection:
    """Build the alerts and hygiene section.

    Args:
        db_path: Database path.
        exports_dir: Directory containing exported reports.

    Returns:
        OperationsDigestSection with alert/hygiene metrics.
    """
    section = OperationsDigestSection(section_name="Alerts and Hygiene")
    metrics: List[OperationsDigestMetric] = []

    if not table_exists("cross_site_trend_alerts", db_path):
        section.metrics = metrics
        return section

    open_alerts = execute_query(
        "SELECT COUNT(*) AS cnt FROM cross_site_trend_alerts "
        "WHERE alert_status = 'open'",
        database_path=db_path,
    )
    oa = _safe_int(_row_to_dict(open_alerts[0]).get("cnt")) if open_alerts else 0
    sev = "warning" if oa > 5 else "info"
    metrics.append(_metric("open_alert_count", oa, severity=sev))

    hc_alerts = execute_query(
        "SELECT COUNT(*) AS cnt FROM cross_site_trend_alerts "
        "WHERE alert_status = 'open' AND severity IN ('high', 'critical')",
        database_path=db_path,
    )
    hca = _safe_int(_row_to_dict(hc_alerts[0]).get("cnt")) if hc_alerts else 0
    sev2 = "warning" if hca > 0 else "info"
    metrics.append(_metric("high_critical_open_alert_count", hca, severity=sev2))

    stale = execute_query(
        "SELECT COUNT(*) AS cnt FROM cross_site_trend_alerts "
        "WHERE alert_status = 'open' "
        "AND created_at <= datetime('now', '-7 days')",
        database_path=db_path,
    )
    sc = _safe_int(_row_to_dict(stale[0]).get("cnt")) if stale else 0
    sev3 = "warning" if sc > 0 else "info"
    metrics.append(_metric("stale_open_alert_count", sc, severity=sev3))

    if table_exists("cross_site_alert_triage_actions", db_path):
        reparse = execute_query(
            "SELECT COUNT(*) AS cnt FROM cross_site_alert_triage_actions "
            "WHERE action = 'needs_reparse'",
            database_path=db_path,
        )
        metrics.append(_metric("needs_reparse_count",
                               _safe_int(_row_to_dict(reparse[0]).get("cnt")) if reparse else 0))

        manual = execute_query(
            "SELECT COUNT(*) AS cnt FROM cross_site_alert_triage_actions "
            "WHERE action = 'needs_manual_review'",
            database_path=db_path,
        )
        metrics.append(_metric("needs_manual_review_count",
                               _safe_int(_row_to_dict(manual[0]).get("cnt")) if manual else 0))

    archive_candidates = execute_query(
        "SELECT COUNT(*) AS cnt FROM cross_site_trend_alerts "
        "WHERE alert_status = 'resolved' "
        "AND created_at <= datetime('now', '-30 days')",
        database_path=db_path,
    )
    metrics.append(_metric("archive_candidates_count",
                           _safe_int(_row_to_dict(archive_candidates[0]).get("cnt")) if archive_candidates else 0))

    hygiene_path = _latest_file(exports_dir, "cross_site_alert_hygiene", ".csv")
    if hygiene_path:
        metrics.append(_metric("latest_hygiene_report", hygiene_path))

    triage_path = _latest_file(exports_dir, "cross_site_alert_triage", ".csv")
    if triage_path:
        metrics.append(_metric("latest_triage_report", triage_path))

    section.metrics = metrics
    return section


def build_lifecycle_digest(
    db_path: Optional[str] = None,
    exports_dir: str = "data/exports",
) -> OperationsDigestSection:
    """Build the lifecycle health and trend section.

    Args:
        db_path: Database path.
        exports_dir: Directory containing exported reports.

    Returns:
        OperationsDigestSection with lifecycle metrics.
    """
    section = OperationsDigestSection(section_name="Lifecycle Health")
    metrics: List[OperationsDigestMetric] = []

    if table_exists("cross_site_lifecycle_health_snapshots", db_path):
        scored = execute_query(
            "SELECT COUNT(DISTINCT property_id) AS cnt "
            "FROM cross_site_lifecycle_health_snapshots",
            database_path=db_path,
        )
        metrics.append(_metric("properties_scored",
                               _safe_int(_row_to_dict(scored[0]).get("cnt")) if scored else 0))

        attn = execute_query(
            "SELECT COUNT(*) AS cnt FROM cross_site_lifecycle_health_snapshots "
            "WHERE lifecycle_health_label = 'attention_required' "
            "AND health_snapshot_id IN ("
            "  SELECT MAX(health_snapshot_id) "
            "  FROM cross_site_lifecycle_health_snapshots GROUP BY property_id"
            ")",
            database_path=db_path,
        )
        ac = _safe_int(_row_to_dict(attn[0]).get("cnt")) if attn else 0
        sev = "warning" if ac > 0 else "info"
        metrics.append(_metric("attention_required_count", ac, severity=sev))

        nr = execute_query(
            "SELECT COUNT(*) AS cnt FROM cross_site_lifecycle_health_snapshots "
            "WHERE lifecycle_health_label = 'needs_review' "
            "AND health_snapshot_id IN ("
            "  SELECT MAX(health_snapshot_id) "
            "  FROM cross_site_lifecycle_health_snapshots GROUP BY property_id"
            ")",
            database_path=db_path,
        )
        nrc = _safe_int(_row_to_dict(nr[0]).get("cnt")) if nr else 0
        sev2 = "warning" if nrc > 0 else "info"
        metrics.append(_metric("needs_review_count", nrc, severity=sev2))

    # Trend counts from latest trend report file or DB
    health_trend_path = _latest_file(exports_dir, "cross_site_lifecycle_health_trends", ".csv")
    if health_trend_path:
        try:
            improved = degraded = gap_total = 0
            with open(health_trend_path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    td = row.get("trend_direction", "")
                    if td == "improved":
                        improved += 1
                    elif td == "degraded":
                        degraded += 1
                    gc = row.get("current_lifecycle_gap_count")
                    if gc:
                        gap_total += _safe_int(gc)
            metrics.append(_metric("improved_trend_count", improved))
            dgd_sev = "warning" if degraded > 0 else "info"
            metrics.append(_metric("degraded_trend_count", degraded, severity=dgd_sev))
            metrics.append(_metric("lifecycle_gap_count", gap_total))
        except Exception:
            pass
        metrics.append(_metric("latest_health_trend_report", health_trend_path))

    health_path = _latest_file(exports_dir, "cross_site_lifecycle_health_", ".csv")
    if health_path and "trends" not in health_path:
        metrics.append(_metric("latest_health_report", health_path))

    section.metrics = metrics
    return section


def build_retrieval_operations_digest(
    db_path: Optional[str] = None,
    exports_dir: str = "data/exports",
) -> OperationsDigestSection:
    """Build the retrieval operations section.

    Args:
        db_path: Database path.
        exports_dir: Directory containing exported reports.

    Returns:
        OperationsDigestSection with retrieval metrics.
    """
    section = OperationsDigestSection(section_name="Retrieval Operations")
    metrics: List[OperationsDigestMetric] = []

    if table_exists("fixture_capture_queue", db_path):
        pending = execute_query(
            "SELECT COUNT(*) AS cnt FROM fixture_capture_queue "
            "WHERE status = 'pending'",
            database_path=db_path,
        )
        pc = _safe_int(_row_to_dict(pending[0]).get("cnt")) if pending else 0
        metrics.append(_metric("pending_capture_queue_count", pc))

        stale = execute_query(
            "SELECT COUNT(*) AS cnt FROM fixture_capture_queue "
            "WHERE status = 'pending' "
            "AND created_at <= datetime('now', '-7 days')",
            database_path=db_path,
        )
        sc = _safe_int(_row_to_dict(stale[0]).get("cnt")) if stale else 0
        sev = "warning" if sc > 0 else "info"
        metrics.append(_metric("stale_pending_capture_count", sc, severity=sev))

    live_enabled = os.environ.get("MARKETSENTRY_LIVE_RETRIEVAL_ENABLED", "false")
    metrics.append(_metric("live_retrieval_enabled", live_enabled))
    metrics.append(_metric(
        "digest_network_calls", "none",
        notes="This digest performs no network calls",
    ))

    health_path = _latest_file(exports_dir, "retrieval_health", ".csv")
    if health_path:
        metrics.append(_metric("latest_retrieval_health_report", health_path))

    section.metrics = metrics
    return section


# ---------------------------------------------------------------------------
# Priority ranking
# ---------------------------------------------------------------------------

def rank_operations_review_priorities(
    db_path: Optional[str] = None,
) -> List[OperationsDigestPropertyPriority]:
    """Rank watched properties by review urgency.

    Args:
        db_path: Database path.

    Returns:
        Sorted list of property priority entries.
    """
    priorities: List[OperationsDigestPropertyPriority] = []

    if not table_exists("watched_properties", db_path):
        return priorities

    props = execute_query(
        "SELECT property_id, address, city, zip FROM watched_properties",
        database_path=db_path,
    )

    has_alerts = table_exists("cross_site_trend_alerts", db_path)
    has_snapshots = table_exists("cross_site_lifecycle_health_snapshots", db_path)

    for pr in props:
        d = _row_to_dict(pr)
        pid = _safe_int(d.get("property_id"))
        reasons: List[str] = []
        score = 0

        # Check lifecycle health
        if has_snapshots:
            snap = execute_query(
                "SELECT lifecycle_health_label, lifecycle_health_score "
                "FROM cross_site_lifecycle_health_snapshots "
                "WHERE property_id = ? "
                "ORDER BY health_snapshot_id DESC LIMIT 1",
                (pid,),
                database_path=db_path,
            )
            if snap:
                sd = _row_to_dict(snap[0])
                label = sd.get("lifecycle_health_label", "")
                if label == "attention_required":
                    reasons.append("Lifecycle health: attention_required")
                    score += 40
                elif label == "needs_review":
                    reasons.append("Lifecycle health: needs_review")
                    score += 20

        # Check open alerts
        if has_alerts:
            alerts = execute_query(
                "SELECT COUNT(*) AS cnt FROM cross_site_trend_alerts "
                "WHERE property_id = ? AND alert_status = 'open' "
                "AND severity IN ('high', 'critical')",
                (pid,),
                database_path=db_path,
            )
            hca = _safe_int(_row_to_dict(alerts[0]).get("cnt")) if alerts else 0
            if hca > 0:
                reasons.append(f"{hca} high/critical open alert(s)")
                score += 30

            stale = execute_query(
                "SELECT COUNT(*) AS cnt FROM cross_site_trend_alerts "
                "WHERE property_id = ? AND alert_status = 'open' "
                "AND created_at <= datetime('now', '-7 days')",
                (pid,),
                database_path=db_path,
            )
            sc = _safe_int(_row_to_dict(stale[0]).get("cnt")) if stale else 0
            if sc > 0:
                reasons.append(f"{sc} stale open alert(s)")
                score += 15

        # Check churn (columns may be from migrations)
        try:
            churn_rows = execute_query(
                "SELECT recent_churn_index, effective_dom_delta "
                "FROM watched_properties WHERE property_id = ?",
                (pid,),
                database_path=db_path,
            )
            if churn_rows:
                cd = _row_to_dict(churn_rows[0])
                ci = _safe_float(cd.get("recent_churn_index"))
                if ci >= 5:
                    reasons.append(f"High recent churn index ({ci:.1f})")
                    score += 10
                ed = _safe_float(cd.get("effective_dom_delta"))
                if ed > 60:
                    reasons.append(f"High Effective DOM delta ({ed:.0f})")
                    score += 10
        except Exception:
            pass

        if not reasons:
            continue

        # Classify
        if score >= 40:
            label = "immediate_review"
        elif score >= 25:
            label = "high_review"
        elif score >= 15:
            label = "normal_review"
        else:
            label = "monitor"

        action = "Review lifecycle health and open alerts"
        if "attention_required" in " ".join(reasons):
            action = "Immediate review of lifecycle health gaps and alerts"
        elif "high/critical" in " ".join(reasons):
            action = "Review high/critical open alerts"

        priorities.append(OperationsDigestPropertyPriority(
            property_id=pid,
            address=d.get("address", ""),
            city=d.get("city", ""),
            zip_code=d.get("zip", ""),
            priority_label=label,
            reasons=reasons,
            recommended_action=action,
        ))

    priorities.sort(key=lambda p: (
        {"immediate_review": 0, "high_review": 1, "normal_review": 2,
         "monitor": 3, "no_current_action": 4}.get(p.priority_label, 5)
    ))

    return priorities


# ---------------------------------------------------------------------------
# Next actions
# ---------------------------------------------------------------------------

def generate_operations_next_actions(
    digest: OperationsDigestSummary,
) -> List[OperationsDigestNextAction]:
    """Generate recommended next local actions from the digest.

    Args:
        digest: The built digest summary.

    Returns:
        List of recommended actions.
    """
    actions: List[OperationsDigestNextAction] = []

    # Scan section metrics for actionable items
    for sec in digest.sections:
        for m in sec.metrics:
            if m.metric_name == "pending_user_decision_count" and _safe_int(m.metric_value) > 0:
                actions.append(OperationsDigestNextAction(
                    action="Export candidate review CSV and complete pending decisions",
                    command="marketsentry export-review",
                    priority="high",
                ))
            if m.metric_name == "stale_open_alert_count" and _safe_int(m.metric_value) > 0:
                actions.append(OperationsDigestNextAction(
                    action="Run alert hygiene check to identify stale alerts",
                    command="marketsentry cross-site-alert-hygiene-check",
                    priority="high",
                ))
            if m.metric_name == "high_critical_open_alert_count" and _safe_int(m.metric_value) > 0:
                actions.append(OperationsDigestNextAction(
                    action="Export triage CSV to review high/critical alerts",
                    command="marketsentry export-cross-site-alert-triage --severity high",
                    priority="high",
                ))
            if m.metric_name == "attention_required_count" and _safe_int(m.metric_value) > 0:
                actions.append(OperationsDigestNextAction(
                    action="Review lifecycle health report for attention-required properties",
                    command="marketsentry cross-site-lifecycle-health-summary",
                    priority="high",
                ))
            if m.metric_name == "pending_capture_queue_count" and _safe_int(m.metric_value) > 0:
                actions.append(OperationsDigestNextAction(
                    action="Save missing fixtures manually for pending capture queue items",
                    command="marketsentry list-fixture-capture-queue",
                    priority="normal",
                ))
            if m.metric_name == "degraded_trend_count" and _safe_int(m.metric_value) > 0:
                actions.append(OperationsDigestNextAction(
                    action="Review lifecycle health trend report for degraded properties",
                    command="marketsentry cross-site-lifecycle-health-trend-summary",
                    priority="normal",
                ))
            if m.metric_name == "archive_candidates_count" and _safe_int(m.metric_value) > 0:
                actions.append(OperationsDigestNextAction(
                    action="Export archive candidates for old resolved alerts",
                    command="marketsentry export-cross-site-alert-archive-candidates",
                    priority="normal",
                ))

    # Always suggest running dashboard
    actions.append(OperationsDigestNextAction(
        action="Run dashboard locally for full interactive review",
        command="marketsentry launch-dashboard",
        priority="normal",
    ))

    # Deduplicate by action text
    seen: set[str] = set()
    unique: List[OperationsDigestNextAction] = []
    for a in actions:
        if a.action not in seen:
            seen.add(a.action)
            unique.append(a)

    # Sort: high first
    unique.sort(key=lambda x: {"high": 0, "normal": 1}.get(x.priority, 2))

    return unique


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_operations_digest(
    db_path: Optional[str] = None,
    exports_dir: str = "data/exports",
) -> OperationsDigestSummary:
    """Build the full operations digest summary.

    Args:
        db_path: Database path.
        exports_dir: Directory containing exported reports.

    Returns:
        Complete OperationsDigestSummary.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sections = [
        build_candidate_review_digest(db_path, exports_dir),
        build_watchlist_digest(db_path, exports_dir),
        build_effective_dom_digest(db_path, exports_dir),
        build_cross_site_digest(db_path, exports_dir),
        build_alert_digest(db_path, exports_dir),
        build_lifecycle_digest(db_path, exports_dir),
        build_retrieval_operations_digest(db_path, exports_dir),
    ]

    digest = OperationsDigestSummary(
        generated_at=now,
        sections=sections,
    )

    # Build priorities and actions
    digest.top_priorities = rank_operations_review_priorities(db_path)
    digest.next_actions = generate_operations_next_actions(digest)

    return digest


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

DIGEST_CSV_FIELDNAMES = [
    "section",
    "metric_name",
    "metric_value",
    "severity",
    "notes",
    "source_report_path",
]


def export_operations_digest(
    db_path: Optional[str] = None,
    output_dir: str = "data/exports",
    exports_dir: str = "data/exports",
    fmt: str = "both",
) -> OperationsDigestRunResult:
    """Build and export the operations digest.

    Args:
        db_path: Database path.
        output_dir: Directory to write export files.
        exports_dir: Directory containing existing reports for scanning.
        fmt: Export format - 'md', 'csv', or 'both'.

    Returns:
        OperationsDigestRunResult with paths and counts.
    """
    digest = build_operations_digest(db_path, exports_dir)
    result = OperationsDigestRunResult()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    metric_count = sum(len(s.metrics) for s in digest.sections)
    result.sections_built = len(digest.sections)
    result.metric_count = metric_count
    result.priority_count = len(digest.top_priorities)
    result.next_action_count = len(digest.next_actions)

    if fmt in ("csv", "both"):
        csv_path = os.path.join(output_dir, f"operations_digest_{ts}.csv")
        rows: List[Dict[str, str]] = []
        for sec in digest.sections:
            for m in sec.metrics:
                rows.append({
                    "section": sec.section_name,
                    "metric_name": m.metric_name,
                    "metric_value": m.metric_value,
                    "severity": m.severity,
                    "notes": m.notes,
                    "source_report_path": m.source_report_path,
                })
        # Add priority rows
        for p in digest.top_priorities:
            rows.append({
                "section": "Top Priorities",
                "metric_name": f"property_{p.property_id}",
                "metric_value": p.priority_label,
                "severity": "info",
                "notes": "; ".join(p.reasons),
                "source_report_path": "",
            })
        # Add next action rows
        for a in digest.next_actions:
            rows.append({
                "section": "Next Actions",
                "metric_name": a.action,
                "metric_value": a.command,
                "severity": "info",
                "notes": a.notes,
                "source_report_path": "",
            })
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=DIGEST_CSV_FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        result.export_paths.append(csv_path)

    if fmt in ("md", "both"):
        md_path = os.path.join(output_dir, f"operations_digest_{ts}.md")
        lines: List[str] = []
        lines.append("# Watchlist Operations Digest")
        lines.append("")
        lines.append(f"Generated: {digest.generated_at}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for sec in digest.sections:
            lines.append(f"## {sec.section_name}")
            lines.append("")
            if sec.metrics:
                lines.append("| Metric | Value | Severity | Notes |")
                lines.append("|--------|-------|----------|-------|")
                for m in sec.metrics:
                    notes = m.notes or ""
                    lines.append(f"| {m.metric_name} | {m.metric_value} | {m.severity} | {notes} |")
            else:
                lines.append("No data available.")
            lines.append("")

        if digest.top_priorities:
            lines.append("## Top Review Priorities")
            lines.append("")
            lines.append("| Property | Address | Priority | Reasons | Action |")
            lines.append("|----------|---------|----------|---------|--------|")
            for p in digest.top_priorities:
                reasons = "; ".join(p.reasons)
                lines.append(
                    f"| {p.property_id} | {p.address}, {p.city} {p.zip_code} "
                    f"| {p.priority_label} | {reasons} | {p.recommended_action} |"
                )
            lines.append("")

        if digest.next_actions:
            lines.append("## Recommended Next Local Actions")
            lines.append("")
            for i, a in enumerate(digest.next_actions, 1):
                lines.append(f"{i}. **{a.action}**")
                lines.append(f"   - Command: `{a.command}`")
                lines.append(f"   - Priority: {a.priority}")
                if a.notes:
                    lines.append(f"   - Notes: {a.notes}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("*This digest is a read-only summary. No mutations were performed.*")
        lines.append("")

        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        result.export_paths.append(md_path)

    return result
