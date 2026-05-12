"""Local Portfolio Review Pack and Print-Ready Property Briefs (Milestone 40).

This module generates a practical local review packet that can be printed
or viewed offline.  It is entirely read-only except for writing export
files.  It does not mutate candidate, watchlist, alert, or property state.
It does not make purchase recommendations.
"""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from marketsentry.database import execute_query, get_connection, table_exists

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class PortfolioReviewMetric(BaseModel):
    """One summary metric for the portfolio."""

    metric_name: str = ""
    metric_value: str = ""
    severity: str = "info"
    notes: str = ""


class PortfolioReviewFlag(BaseModel):
    """A review flag on a property brief."""

    flag_name: str = ""
    flag_value: str = ""
    severity: str = "info"


class PortfolioReviewNextAction(BaseModel):
    """A recommended local review action."""

    action: str = ""
    command: str = ""
    priority: str = "normal"
    notes: str = ""


class PortfolioReviewPropertyBrief(BaseModel):
    """Per-property review brief."""

    property_id: int = 0
    candidate_id: int = 0
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    current_price: Optional[float] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    watch_priority: int = 0
    watch_priority_label: str = "normal"
    active_watch_status: bool = True
    redfin_url: str = ""
    quiet_score: Optional[float] = None
    quiet_gatekeeper_result: str = "unknown"
    vibrancy_score: Optional[float] = None
    gas_evidence: str = ""
    garage_spaces: int = 0
    effective_dom_v1: Optional[int] = None
    effective_dom_v2: Optional[int] = None
    effective_dom_delta: Optional[int] = None
    county_reset_applied: bool = False
    county_reset_date: str = ""
    recent_churn_index: Optional[float] = None
    listing_churn_count: int = 0
    dom_reset_count: int = 0
    sale_rent_alternation_count: int = 0
    cross_site_confidence_score: Optional[float] = None
    discrepancy_severity_label: str = ""
    open_alert_count: int = 0
    high_critical_alert_count: int = 0
    alert_burden_label: str = "none"
    lifecycle_health_score: Optional[float] = None
    lifecycle_health_label: str = ""
    lifecycle_gap_count: int = 0
    latest_alert_event: str = ""
    recommended_review_action: str = ""
    review_priority_label: str = "monitor"
    review_priority_score: int = 0
    flags: List[PortfolioReviewFlag] = Field(default_factory=list)


class PortfolioReviewPackSummary(BaseModel):
    """Portfolio-level summary."""

    generated_at: str = ""
    total_watched: int = 0
    active_watched: int = 0
    high_priority_watched: int = 0
    quiet_gatekeeper_pass: int = 0
    quiet_gatekeeper_fail: int = 0
    quiet_score_missing: int = 0
    gas_evidence_count: int = 0
    garage_evidence_count: int = 0
    county_reset_applied_count: int = 0
    high_churn_count: int = 0
    high_effective_dom_delta_count: int = 0
    low_cross_site_confidence_count: int = 0
    high_discrepancy_severity_count: int = 0
    open_alert_count: int = 0
    high_critical_alert_count: int = 0
    lifecycle_attention_required_count: int = 0
    lifecycle_needs_review_count: int = 0
    digest_score: Optional[int] = None
    digest_status: str = ""
    metrics: List[PortfolioReviewMetric] = Field(default_factory=list)


class PortfolioReviewPackRunResult(BaseModel):
    """Result of building and exporting a review pack."""

    property_count: int = 0
    priority_count: int = 0
    next_action_count: int = 0
    export_paths: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _row_to_dict(row: Any) -> Dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return {}
    return dict(row)


def _quiet_gatekeeper_result(quiet_score: Optional[float]) -> str:
    """Determine Quiet gatekeeper pass/fail/unknown.

    Args:
        quiet_score: The property's Quiet Score.

    Returns:
        'pass', 'fail', or 'unknown'.
    """
    if quiet_score is None:
        return "unknown"
    return "pass" if quiet_score >= 70.0 else "fail"


def _watch_priority_label(priority: int) -> str:
    """Map numeric watch priority to a label.

    Args:
        priority: Integer priority (1=high, 0=normal).

    Returns:
        'high' or 'normal'.
    """
    return "high" if priority == 1 else "normal"


def _alert_burden_label(open_count: int, high_crit: int) -> str:
    """Determine alert burden label.

    Args:
        open_count: Total open alerts.
        high_crit: High/critical open alerts.

    Returns:
        Alert burden label string.
    """
    if high_crit >= 3:
        return "critical"
    if high_crit >= 1:
        return "high"
    if open_count >= 5:
        return "moderate"
    if open_count >= 1:
        return "light"
    return "none"


# ---------------------------------------------------------------------------
# Property brief builder
# ---------------------------------------------------------------------------

def build_property_review_brief(
    property_row: Dict[str, Any],
    db_path: Optional[str] = None,
) -> PortfolioReviewPropertyBrief:
    """Build a review brief for a single watched property.

    Args:
        property_row: Dictionary from the watched_properties table.
        db_path: Database path for querying related tables.

    Returns:
        Populated PortfolioReviewPropertyBrief.
    """
    pid = _safe_int(property_row.get("property_id"))
    qs = property_row.get("quiet_score")
    quiet = _safe_float(qs) if qs is not None else None
    vs = property_row.get("vibrancy_score")
    vibrancy = _safe_float(vs) if vs is not None else None

    # Gas evidence: combine boolean and text
    gas_svc = property_row.get("gas_service")
    gas_ev = property_row.get("gas_evidence") or ""
    gas_str = ""
    if gas_svc and int(gas_svc) == 1:
        gas_str = "Yes"
    if gas_ev:
        gas_str = gas_ev if not gas_str else f"{gas_str}; {gas_ev}"

    # Effective DOM columns (base schema has effective_dom; migrations add
    # effective_dom_v1 and effective_dom_v2)
    edom = property_row.get("effective_dom")
    edom_v1 = property_row.get("effective_dom_v1")
    edom_v2 = property_row.get("effective_dom_v2")
    # Use effective_dom_v1 if available, else fall back to effective_dom
    v1_val = edom_v1 if edom_v1 is not None else edom
    v1 = _safe_int(v1_val) if v1_val is not None else None
    v2 = _safe_int(edom_v2) if edom_v2 is not None else None

    ed_delta_raw = property_row.get("effective_dom_delta")
    ed_delta = _safe_int(ed_delta_raw) if ed_delta_raw is not None else None

    cr_applied = bool(_safe_int(property_row.get("county_reset_applied")))

    ci_raw = property_row.get("recent_churn_index")
    ci = _safe_float(ci_raw) if ci_raw is not None else None

    brief = PortfolioReviewPropertyBrief(
        property_id=pid,
        candidate_id=_safe_int(property_row.get("candidate_id")),
        address=str(property_row.get("address", "")),
        city=str(property_row.get("city", "")),
        state="CA",
        zip_code=str(property_row.get("zip", "")),
        current_price=(
            _safe_float(property_row.get("current_price"))
            if property_row.get("current_price") is not None else None
        ),
        beds=(
            _safe_int(property_row.get("beds"))
            if property_row.get("beds") is not None else None
        ),
        baths=(
            _safe_float(property_row.get("baths"))
            if property_row.get("baths") is not None else None
        ),
        sqft=(
            _safe_int(property_row.get("sqft"))
            if property_row.get("sqft") is not None else None
        ),
        watch_priority=_safe_int(property_row.get("watch_priority")),
        watch_priority_label=_watch_priority_label(
            _safe_int(property_row.get("watch_priority"))
        ),
        active_watch_status=bool(
            _safe_int(property_row.get("active_watch_status", 1))
        ),
        redfin_url=str(property_row.get("redfin_url") or ""),
        quiet_score=quiet,
        quiet_gatekeeper_result=_quiet_gatekeeper_result(quiet),
        vibrancy_score=vibrancy,
        gas_evidence=gas_str,
        garage_spaces=_safe_int(property_row.get("garage_spaces")),
        effective_dom_v1=v1,
        effective_dom_v2=v2,
        effective_dom_delta=ed_delta,
        county_reset_applied=cr_applied,
        recent_churn_index=ci,
        listing_churn_count=_safe_int(
            property_row.get("listing_churn_count")
        ),
        dom_reset_count=_safe_int(property_row.get("dom_reset_count")),
        sale_rent_alternation_count=_safe_int(
            property_row.get("sale_rent_alternation_count")
        ),
    )

    # --- Cross-site confidence ---
    try:
        rows = execute_query(
            "SELECT overall_cross_site_confidence_score, "
            "discrepancy_severity_label "
            "FROM cross_site_analytics_snapshots "
            "WHERE property_id = ? "
            "ORDER BY captured_at DESC LIMIT 1",
            (pid,),
            database_path=db_path,
        )
        if rows:
            d = _row_to_dict(rows[0])
            conf = d.get("overall_cross_site_confidence_score")
            brief.cross_site_confidence_score = (
                _safe_float(conf) if conf is not None else None
            )
            brief.discrepancy_severity_label = str(
                d.get("discrepancy_severity_label") or ""
            )
    except Exception:
        pass

    # --- Alerts ---
    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM cross_site_trend_alerts "
            "WHERE property_id = ? AND alert_status = 'open'",
            (pid,),
            database_path=db_path,
        )
        brief.open_alert_count = _safe_int(
            _row_to_dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        pass

    try:
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM cross_site_trend_alerts "
            "WHERE property_id = ? AND alert_status = 'open' "
            "AND severity IN ('high', 'critical')",
            (pid,),
            database_path=db_path,
        )
        brief.high_critical_alert_count = _safe_int(
            _row_to_dict(rows[0]).get("cnt") if rows else 0
        )
    except Exception:
        pass

    brief.alert_burden_label = _alert_burden_label(
        brief.open_alert_count, brief.high_critical_alert_count
    )

    # --- Lifecycle health ---
    try:
        rows = execute_query(
            "SELECT lifecycle_health_score, lifecycle_health_label, "
            "lifecycle_gap_count, recommended_review_action "
            "FROM cross_site_lifecycle_health_snapshots "
            "WHERE property_id = ? "
            "ORDER BY captured_at DESC LIMIT 1",
            (pid,),
            database_path=db_path,
        )
        if rows:
            d = _row_to_dict(rows[0])
            hs = d.get("lifecycle_health_score")
            brief.lifecycle_health_score = (
                _safe_float(hs) if hs is not None else None
            )
            brief.lifecycle_health_label = str(
                d.get("lifecycle_health_label") or ""
            )
            brief.lifecycle_gap_count = _safe_int(
                d.get("lifecycle_gap_count")
            )
            brief.recommended_review_action = str(
                d.get("recommended_review_action") or ""
            )
    except Exception:
        pass

    # --- Latest alert event ---
    try:
        rows = execute_query(
            "SELECT message, created_at FROM cross_site_trend_alerts "
            "WHERE property_id = ? ORDER BY created_at DESC LIMIT 1",
            (pid,),
            database_path=db_path,
        )
        if rows:
            d = _row_to_dict(rows[0])
            brief.latest_alert_event = str(d.get("message") or "")
    except Exception:
        pass

    # --- Flags ---
    flags: List[PortfolioReviewFlag] = []
    if brief.quiet_gatekeeper_result == "fail":
        flags.append(PortfolioReviewFlag(
            flag_name="Quiet Gatekeeper",
            flag_value="FAIL",
            severity="warning",
        ))
    if brief.quiet_gatekeeper_result == "unknown":
        flags.append(PortfolioReviewFlag(
            flag_name="Quiet Score",
            flag_value="Missing",
            severity="info",
        ))
    if brief.high_critical_alert_count > 0:
        flags.append(PortfolioReviewFlag(
            flag_name="High/Critical Alerts",
            flag_value=str(brief.high_critical_alert_count),
            severity="warning",
        ))
    if brief.lifecycle_health_label == "attention_required":
        flags.append(PortfolioReviewFlag(
            flag_name="Lifecycle Health",
            flag_value="Attention Required",
            severity="warning",
        ))
    if ci is not None and ci > 3:
        flags.append(PortfolioReviewFlag(
            flag_name="High Churn",
            flag_value=f"{ci:.1f}",
            severity="warning",
        ))
    if (brief.cross_site_confidence_score is not None
            and brief.cross_site_confidence_score < 50):
        flags.append(PortfolioReviewFlag(
            flag_name="Low Cross-Site Confidence",
            flag_value=f"{brief.cross_site_confidence_score:.1f}",
            severity="warning",
        ))
    if brief.discrepancy_severity_label in ("high", "critical"):
        flags.append(PortfolioReviewFlag(
            flag_name="Discrepancy Severity",
            flag_value=brief.discrepancy_severity_label,
            severity="warning",
        ))
    brief.flags = flags

    return brief


# ---------------------------------------------------------------------------
# Review priority ranking
# ---------------------------------------------------------------------------

def rank_portfolio_review_briefs(
    briefs: List[PortfolioReviewPropertyBrief],
) -> List[PortfolioReviewPropertyBrief]:
    """Rank property briefs by review priority.

    Args:
        briefs: List of property briefs.

    Returns:
        Sorted list with review_priority_label and review_priority_score set.
    """
    for b in briefs:
        score = 0

        # Lifecycle health
        if b.lifecycle_health_label == "attention_required":
            score += 40
        elif b.lifecycle_health_label == "needs_review":
            score += 20

        # Alerts
        if b.high_critical_alert_count >= 2:
            score += 35
        elif b.high_critical_alert_count >= 1:
            score += 25

        # Discrepancy severity
        if b.discrepancy_severity_label in ("high", "critical"):
            score += 15

        # Low cross-site confidence
        if (b.cross_site_confidence_score is not None
                and b.cross_site_confidence_score < 50):
            score += 10

        # High churn
        if b.recent_churn_index is not None and b.recent_churn_index > 3:
            score += 10

        # High Effective DOM delta
        if (b.effective_dom_delta is not None
                and abs(b.effective_dom_delta) > 60):
            score += 10

        # Missing key data
        if b.quiet_score is None:
            score += 5

        # Watch priority boost
        if b.watch_priority == 1:
            score += 5

        # Active watch status
        if not b.active_watch_status:
            score -= 10

        b.review_priority_score = max(0, score)

        # Label assignment
        if score >= 40:
            b.review_priority_label = "immediate_review"
        elif score >= 25:
            b.review_priority_label = "high_review"
        elif score >= 10:
            b.review_priority_label = "normal_review"
        elif score >= 1:
            b.review_priority_label = "monitor"
        else:
            b.review_priority_label = "low_current_activity"

    return sorted(briefs, key=lambda x: x.review_priority_score, reverse=True)


# ---------------------------------------------------------------------------
# Next actions
# ---------------------------------------------------------------------------

def generate_property_next_actions(
    briefs: List[PortfolioReviewPropertyBrief],
) -> List[PortfolioReviewNextAction]:
    """Generate recommended local review actions from property briefs.

    Args:
        briefs: List of ranked property briefs.

    Returns:
        List of next actions.
    """
    actions: List[PortfolioReviewNextAction] = []

    has_pending_alerts = any(b.high_critical_alert_count > 0 for b in briefs)
    has_lifecycle_attention = any(
        b.lifecycle_health_label == "attention_required" for b in briefs
    )
    has_stale = any(b.open_alert_count > 3 for b in briefs)
    has_missing_quiet = any(b.quiet_score is None for b in briefs)
    has_high_churn = any(
        b.recent_churn_index is not None and b.recent_churn_index > 3
        for b in briefs
    )

    if has_pending_alerts:
        actions.append(PortfolioReviewNextAction(
            action="Triage high/critical alerts",
            command="marketsentry export-cross-site-alert-triage",
            priority="high",
        ))
    if has_lifecycle_attention:
        actions.append(PortfolioReviewNextAction(
            action="Address lifecycle attention-required properties",
            command="marketsentry export-lifecycle-health-report",
            priority="high",
        ))
    if has_stale:
        actions.append(PortfolioReviewNextAction(
            action="Review open alert backlog",
            command=(
                "marketsentry export-cross-site-alert-lifecycle-report"
            ),
            priority="normal",
        ))
    if has_missing_quiet:
        actions.append(PortfolioReviewNextAction(
            action="Investigate properties with missing Quiet Score",
            command="marketsentry export-operations-digest",
            priority="normal",
        ))
    if has_high_churn:
        actions.append(PortfolioReviewNextAction(
            action="Review high churn properties",
            command="marketsentry export-operations-digest",
            priority="normal",
        ))
    if not actions:
        actions.append(PortfolioReviewNextAction(
            action="No immediate actions required. Portfolio is clear.",
            command="",
            priority="low",
        ))

    return actions


# ---------------------------------------------------------------------------
# Portfolio summary builder
# ---------------------------------------------------------------------------

def build_portfolio_summary(
    briefs: List[PortfolioReviewPropertyBrief],
    db_path: Optional[str] = None,
) -> PortfolioReviewPackSummary:
    """Build a portfolio-level summary from property briefs.

    Args:
        briefs: List of property briefs.
        db_path: Database path for digest score lookup.

    Returns:
        PortfolioReviewPackSummary with aggregate metrics.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = PortfolioReviewPackSummary(generated_at=now)

    summary.total_watched = len(briefs)
    summary.active_watched = sum(1 for b in briefs if b.active_watch_status)
    summary.high_priority_watched = sum(
        1 for b in briefs if b.watch_priority == 1
    )
    summary.quiet_gatekeeper_pass = sum(
        1 for b in briefs if b.quiet_gatekeeper_result == "pass"
    )
    summary.quiet_gatekeeper_fail = sum(
        1 for b in briefs if b.quiet_gatekeeper_result == "fail"
    )
    summary.quiet_score_missing = sum(
        1 for b in briefs if b.quiet_gatekeeper_result == "unknown"
    )
    summary.gas_evidence_count = sum(
        1 for b in briefs if b.gas_evidence
    )
    summary.garage_evidence_count = sum(
        1 for b in briefs if b.garage_spaces > 0
    )
    summary.county_reset_applied_count = sum(
        1 for b in briefs if b.county_reset_applied
    )
    summary.high_churn_count = sum(
        1 for b in briefs
        if b.recent_churn_index is not None and b.recent_churn_index > 3
    )
    summary.high_effective_dom_delta_count = sum(
        1 for b in briefs
        if b.effective_dom_delta is not None
        and abs(b.effective_dom_delta) > 60
    )
    summary.low_cross_site_confidence_count = sum(
        1 for b in briefs
        if b.cross_site_confidence_score is not None
        and b.cross_site_confidence_score < 50
    )
    summary.high_discrepancy_severity_count = sum(
        1 for b in briefs
        if b.discrepancy_severity_label in ("high", "critical")
    )
    summary.open_alert_count = sum(b.open_alert_count for b in briefs)
    summary.high_critical_alert_count = sum(
        b.high_critical_alert_count for b in briefs
    )
    summary.lifecycle_attention_required_count = sum(
        1 for b in briefs
        if b.lifecycle_health_label == "attention_required"
    )
    summary.lifecycle_needs_review_count = sum(
        1 for b in briefs
        if b.lifecycle_health_label == "needs_review"
    )

    # Digest score from latest snapshot
    try:
        from marketsentry.operations_digest_history import (
            get_latest_operations_digest_snapshot,
        )
        snap = get_latest_operations_digest_snapshot(db_path)
        if snap and snap.digest_snapshot_id:
            summary.digest_score = snap.digest_score
            summary.digest_status = snap.digest_status_label
    except Exception:
        pass

    return summary


# ---------------------------------------------------------------------------
# Pack builder
# ---------------------------------------------------------------------------

def build_portfolio_review_pack(
    db_path: Optional[str] = None,
    include_inactive: bool = False,
) -> tuple[
    PortfolioReviewPackSummary,
    List[PortfolioReviewPropertyBrief],
    List[PortfolioReviewNextAction],
]:
    """Build the full portfolio review pack.

    Args:
        db_path: Database path.
        include_inactive: Include inactive watched properties.

    Returns:
        Tuple of (summary, ranked briefs, next actions).
    """
    # Query watched properties
    where = "" if include_inactive else " WHERE active_watch_status = 1"
    try:
        rows = execute_query(
            f"SELECT * FROM watched_properties{where}",
            database_path=db_path,
        )
    except Exception:
        rows = []

    briefs: List[PortfolioReviewPropertyBrief] = []
    for row in rows:
        d = _row_to_dict(row)
        brief = build_property_review_brief(d, db_path)
        briefs.append(brief)

    briefs = rank_portfolio_review_briefs(briefs)
    summary = build_portfolio_summary(briefs, db_path)
    actions = generate_property_next_actions(briefs)

    return summary, briefs, actions


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

REVIEW_CSV_FIELDNAMES = [
    "property_id",
    "address",
    "city",
    "zip",
    "current_price",
    "beds",
    "baths",
    "sqft",
    "watch_priority_label",
    "active_watch_status",
    "quiet_score",
    "quiet_gatekeeper_result",
    "vibrancy_score",
    "gas_evidence",
    "garage_spaces",
    "effective_dom_v1",
    "effective_dom_v2",
    "effective_dom_delta",
    "county_reset_applied",
    "recent_churn_index",
    "listing_churn_count",
    "dom_reset_count",
    "sale_rent_alternation_count",
    "cross_site_confidence_score",
    "discrepancy_severity_label",
    "open_alert_count",
    "high_critical_alert_count",
    "alert_burden_label",
    "lifecycle_health_score",
    "lifecycle_health_label",
    "lifecycle_gap_count",
    "review_priority_label",
    "review_priority_score",
    "recommended_review_action",
    "redfin_url",
]


def export_portfolio_review_pack(
    db_path: Optional[str] = None,
    output_dir: str = "data/exports",
    fmt: str = "both",
    include_inactive: bool = False,
) -> PortfolioReviewPackRunResult:
    """Build and export the portfolio review pack.

    Args:
        db_path: Database path.
        output_dir: Directory to write export files.
        fmt: Export format - 'md', 'csv', or 'both'.
        include_inactive: Include inactive watched properties.

    Returns:
        PortfolioReviewPackRunResult with paths and counts.
    """
    summary, briefs, actions = build_portfolio_review_pack(
        db_path, include_inactive
    )
    result = PortfolioReviewPackRunResult(
        property_count=len(briefs),
        priority_count=sum(
            1 for b in briefs
            if b.review_priority_label in (
                "immediate_review", "high_review"
            )
        ),
        next_action_count=len(actions),
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    if fmt in ("md", "both"):
        md_path = os.path.join(
            output_dir, f"portfolio_review_pack_{ts}.md"
        )
        _write_md(summary, briefs, actions, md_path)
        result.export_paths.append(md_path)

    if fmt in ("csv", "both"):
        csv_path = os.path.join(
            output_dir, f"portfolio_review_pack_{ts}.csv"
        )
        _write_csv(briefs, csv_path)
        result.export_paths.append(csv_path)

    return result


def _write_md(
    summary: PortfolioReviewPackSummary,
    briefs: List[PortfolioReviewPropertyBrief],
    actions: List[PortfolioReviewNextAction],
    path: str,
) -> None:
    """Write the Markdown review pack.

    Args:
        summary: Portfolio summary.
        briefs: Ranked property briefs.
        actions: Next actions.
        path: Output file path.
    """
    lines: List[str] = []
    lines.append("# Portfolio Review Pack")
    lines.append("")
    lines.append(f"Generated: {summary.generated_at}")
    lines.append("")
    lines.append(
        "> Local analytical review aid. "
        "Not a purchase recommendation. "
        "Not investment advice."
    )
    lines.append("")

    # Portfolio summary
    lines.append("## Portfolio Summary")
    lines.append("")
    lines.append(f"- Total watched properties: {summary.total_watched}")
    lines.append(f"- Active watched: {summary.active_watched}")
    lines.append(
        f"- High priority watched: {summary.high_priority_watched}"
    )
    lines.append(
        f"- Quiet gatekeeper pass: {summary.quiet_gatekeeper_pass}"
    )
    lines.append(
        f"- Quiet gatekeeper fail: {summary.quiet_gatekeeper_fail}"
    )
    lines.append(
        f"- Quiet score missing: {summary.quiet_score_missing}"
    )
    lines.append(
        f"- Gas evidence: {summary.gas_evidence_count}"
    )
    lines.append(
        f"- Garage evidence: {summary.garage_evidence_count}"
    )
    lines.append(
        f"- County reset applied: {summary.county_reset_applied_count}"
    )
    lines.append(f"- High Churn Index: {summary.high_churn_count}")
    lines.append(
        f"- High Effective DOM delta: "
        f"{summary.high_effective_dom_delta_count}"
    )
    lines.append(
        f"- Low cross-site confidence: "
        f"{summary.low_cross_site_confidence_count}"
    )
    lines.append(
        f"- High discrepancy severity: "
        f"{summary.high_discrepancy_severity_count}"
    )
    lines.append(f"- Open alerts: {summary.open_alert_count}")
    lines.append(
        f"- High/critical alerts: {summary.high_critical_alert_count}"
    )
    lines.append(
        f"- Lifecycle attention required: "
        f"{summary.lifecycle_attention_required_count}"
    )
    lines.append(
        f"- Lifecycle needs review: "
        f"{summary.lifecycle_needs_review_count}"
    )
    if summary.digest_score is not None:
        lines.append(
            f"- Digest score: {summary.digest_score} "
            f"({summary.digest_status})"
        )
    lines.append("")

    # Top review priorities
    priority_briefs = [
        b for b in briefs
        if b.review_priority_label in (
            "immediate_review", "high_review", "normal_review"
        )
    ]
    if priority_briefs:
        lines.append("## Top Review Priorities")
        lines.append("")
        lines.append(
            "| Property | Address | Priority | Score | Flags |"
        )
        lines.append(
            "| ------- | ------- | ------- | ------- | ------- |"
        )
        for b in priority_briefs:
            flag_str = ", ".join(f.flag_name for f in b.flags) or "-"
            lines.append(
                f"| {b.property_id} | {b.address}, {b.city} | "
                f"{b.review_priority_label} | {b.review_priority_score} | "
                f"{flag_str} |"
            )
        lines.append("")

    # Per-property briefs
    if briefs:
        lines.append("## Property Briefs")
        lines.append("")
        for b in briefs:
            lines.append(f"### Property {b.property_id}: {b.address}")
            lines.append("")
            lines.append(
                f"- Location: {b.address}, {b.city}, {b.state} {b.zip_code}"
            )
            if b.current_price is not None:
                lines.append(f"- Current price: ${b.current_price:,.0f}")
            specs = []
            if b.beds is not None:
                specs.append(f"{b.beds} beds")
            if b.baths is not None:
                specs.append(f"{b.baths} baths")
            if b.sqft is not None:
                specs.append(f"{b.sqft:,} sqft")
            if specs:
                lines.append(f"- Specs: {', '.join(specs)}")
            lines.append(
                f"- Watch priority: {b.watch_priority_label} | "
                f"Active: {'Yes' if b.active_watch_status else 'No'}"
            )
            if b.redfin_url:
                lines.append(f"- Redfin: {b.redfin_url}")
            lines.append(
                f"- Quiet Score: "
                f"{b.quiet_score if b.quiet_score is not None else 'N/A'} | "
                f"Gatekeeper: {b.quiet_gatekeeper_result}"
            )
            lines.append(
                f"- Vibrancy Score: "
                f"{b.vibrancy_score if b.vibrancy_score is not None else 'N/A'}"
            )
            lines.append(f"- Gas evidence: {b.gas_evidence or 'None'}")
            lines.append(f"- Garage spaces: {b.garage_spaces}")
            lines.append(
                f"- Effective DOM v1: "
                f"{b.effective_dom_v1 if b.effective_dom_v1 is not None else 'N/A'}"
            )
            lines.append(
                f"- Effective DOM v2: "
                f"{b.effective_dom_v2 if b.effective_dom_v2 is not None else 'N/A'}"
            )
            lines.append(
                f"- Effective DOM delta: "
                f"{b.effective_dom_delta if b.effective_dom_delta is not None else 'N/A'}"
            )
            lines.append(
                f"- County reset: "
                f"{'Applied' if b.county_reset_applied else 'No'}"
            )
            lines.append(
                f"- Churn Index: "
                f"{b.recent_churn_index if b.recent_churn_index is not None else 'N/A'}"
            )
            lines.append(
                f"- Listing churn: {b.listing_churn_count} | "
                f"DOM resets: {b.dom_reset_count} | "
                f"Sale/rent alternation: {b.sale_rent_alternation_count}"
            )
            lines.append(
                f"- Cross-site confidence: "
                f"{b.cross_site_confidence_score if b.cross_site_confidence_score is not None else 'N/A'}"
            )
            lines.append(
                f"- Discrepancy severity: "
                f"{b.discrepancy_severity_label or 'N/A'}"
            )
            lines.append(
                f"- Open alerts: {b.open_alert_count} | "
                f"High/critical: {b.high_critical_alert_count} | "
                f"Burden: {b.alert_burden_label}"
            )
            lines.append(
                f"- Lifecycle health: "
                f"{b.lifecycle_health_score if b.lifecycle_health_score is not None else 'N/A'} "
                f"({b.lifecycle_health_label or 'N/A'})"
            )
            lines.append(
                f"- Lifecycle gaps: {b.lifecycle_gap_count}"
            )
            if b.latest_alert_event:
                lines.append(
                    f"- Latest alert: {b.latest_alert_event}"
                )
            if b.recommended_review_action:
                lines.append(
                    f"- Recommended action: "
                    f"{b.recommended_review_action}"
                )
            lines.append(
                f"- Review priority: {b.review_priority_label} "
                f"(score: {b.review_priority_score})"
            )
            if b.flags:
                flag_strs = [
                    f"{f.flag_name}: {f.flag_value}" for f in b.flags
                ]
                lines.append(f"- Flags: {'; '.join(flag_strs)}")
            lines.append("")

    # Next actions
    if actions:
        lines.append("## Local Next Actions")
        lines.append("")
        for i, a in enumerate(actions, 1):
            lines.append(f"{i}. {a.action}")
            if a.command:
                lines.append(f"   `{a.command}`")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(
        "Source: Local database and export files. "
        "Report freshness depends on last retrieval and digest run."
    )
    lines.append("")
    lines.append(
        "*Read-only review pack. No mutations performed. "
        "Not a purchase recommendation.*"
    )
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_csv(
    briefs: List[PortfolioReviewPropertyBrief],
    path: str,
) -> None:
    """Write the CSV review pack.

    Args:
        briefs: Ranked property briefs.
        path: Output file path.
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_CSV_FIELDNAMES)
        writer.writeheader()
        for b in briefs:
            writer.writerow({
                "property_id": b.property_id,
                "address": b.address,
                "city": b.city,
                "zip": b.zip_code,
                "current_price": (
                    b.current_price if b.current_price is not None else ""
                ),
                "beds": b.beds if b.beds is not None else "",
                "baths": b.baths if b.baths is not None else "",
                "sqft": b.sqft if b.sqft is not None else "",
                "watch_priority_label": b.watch_priority_label,
                "active_watch_status": b.active_watch_status,
                "quiet_score": (
                    b.quiet_score if b.quiet_score is not None else ""
                ),
                "quiet_gatekeeper_result": b.quiet_gatekeeper_result,
                "vibrancy_score": (
                    b.vibrancy_score
                    if b.vibrancy_score is not None else ""
                ),
                "gas_evidence": b.gas_evidence,
                "garage_spaces": b.garage_spaces,
                "effective_dom_v1": (
                    b.effective_dom_v1
                    if b.effective_dom_v1 is not None else ""
                ),
                "effective_dom_v2": (
                    b.effective_dom_v2
                    if b.effective_dom_v2 is not None else ""
                ),
                "effective_dom_delta": (
                    b.effective_dom_delta
                    if b.effective_dom_delta is not None else ""
                ),
                "county_reset_applied": b.county_reset_applied,
                "recent_churn_index": (
                    b.recent_churn_index
                    if b.recent_churn_index is not None else ""
                ),
                "listing_churn_count": b.listing_churn_count,
                "dom_reset_count": b.dom_reset_count,
                "sale_rent_alternation_count": b.sale_rent_alternation_count,
                "cross_site_confidence_score": (
                    b.cross_site_confidence_score
                    if b.cross_site_confidence_score is not None else ""
                ),
                "discrepancy_severity_label": b.discrepancy_severity_label,
                "open_alert_count": b.open_alert_count,
                "high_critical_alert_count": b.high_critical_alert_count,
                "alert_burden_label": b.alert_burden_label,
                "lifecycle_health_score": (
                    b.lifecycle_health_score
                    if b.lifecycle_health_score is not None else ""
                ),
                "lifecycle_health_label": b.lifecycle_health_label,
                "lifecycle_gap_count": b.lifecycle_gap_count,
                "review_priority_label": b.review_priority_label,
                "review_priority_score": b.review_priority_score,
                "recommended_review_action": b.recommended_review_action,
                "redfin_url": b.redfin_url,
            })
