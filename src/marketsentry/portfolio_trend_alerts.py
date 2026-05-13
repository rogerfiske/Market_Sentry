"""Portfolio Trend Threshold Alerts and Local Notification Digest.

Converts portfolio trend analysis from Milestone 42 into local,
read-only operational flags. Generates a notification-style Markdown
and CSV digest of threshold alerts without mutating candidate,
watchlist, or alert state.

No outbound notifications are sent. All alerts are local review
prompts only.
"""

import csv
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("marketsentry")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PortfolioTrendAlert(BaseModel):
    """One trend threshold alert."""

    alert_id: str = ""
    alert_scope: str = ""  # portfolio / property
    property_id: str = ""
    candidate_id: str = ""
    address: str = ""
    severity: str = "info"  # info / warning / high
    alert_type: str = ""
    message: str = ""
    metric_name: str = ""
    previous_value: str = ""
    current_value: str = ""
    delta_value: str = ""
    recommended_local_action: str = ""
    source_pack_file: str = ""
    generated_at: str = ""


class PortfolioTrendAlertRule(BaseModel):
    """A threshold rule for generating trend alerts."""

    rule_id: str = ""
    alert_scope: str = ""  # portfolio / property
    alert_type: str = ""
    metric_name: str = ""
    threshold: float = 0.0
    severity: str = "info"
    description: str = ""


class PortfolioTrendAlertSummary(BaseModel):
    """Summary of trend alerts by severity."""

    total_alerts: int = 0
    info_count: int = 0
    warning_count: int = 0
    high_count: int = 0
    pack_count: int = 0
    first_pack_date: str = ""
    latest_pack_date: str = ""


class PortfolioTrendAlertDigest(BaseModel):
    """A complete digest of trend alerts."""

    alerts: List[PortfolioTrendAlert] = Field(default_factory=list)
    summary: PortfolioTrendAlertSummary = Field(
        default_factory=PortfolioTrendAlertSummary
    )
    generated_at: str = ""
    source_pack_files: List[str] = Field(default_factory=list)


class PortfolioTrendAlertRunResult(BaseModel):
    """Result of a trend alert evaluation and export run."""

    export_paths: List[str] = Field(default_factory=list)
    alert_count: int = 0
    summary: Optional[PortfolioTrendAlertSummary] = None
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# CSV field names for alert digest
# ---------------------------------------------------------------------------

ALERT_DIGEST_CSV_FIELDNAMES = [
    "alert_id",
    "alert_scope",
    "property_id",
    "candidate_id",
    "address",
    "severity",
    "alert_type",
    "message",
    "metric_name",
    "previous_value",
    "current_value",
    "delta_value",
    "recommended_local_action",
    "source_pack_file",
    "generated_at",
]


# ---------------------------------------------------------------------------
# Default alert rules
# ---------------------------------------------------------------------------

def get_default_portfolio_trend_alert_rules() -> List[PortfolioTrendAlertRule]:
    """Return the default set of portfolio trend alert rules.

    Returns:
        List of PortfolioTrendAlertRule with default thresholds.
    """
    return [
        # Aggregate burden rules
        PortfolioTrendAlertRule(
            rule_id="burden_high_80",
            alert_scope="portfolio",
            alert_type="aggregate_burden_high",
            metric_name="aggregate_review_burden_score",
            threshold=80.0,
            severity="high",
            description=(
                "Aggregate review burden score >= 80"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="burden_warning_60",
            alert_scope="portfolio",
            alert_type="aggregate_burden_warning",
            metric_name="aggregate_review_burden_score",
            threshold=60.0,
            severity="warning",
            description=(
                "Aggregate review burden score >= 60"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="burden_increase_15",
            alert_scope="portfolio",
            alert_type="aggregate_burden_increase",
            metric_name="aggregate_burden_delta",
            threshold=15.0,
            severity="warning",
            description=(
                "Aggregate burden increased by >= 15"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="burden_label_worsening",
            alert_scope="portfolio",
            alert_type="burden_label_worsening",
            metric_name="aggregate_review_status_label",
            threshold=0.0,
            severity="warning",
            description=(
                "Burden label changed to elevated_burden "
                "or high_burden"
            ),
        ),
        # Backlog rules
        PortfolioTrendAlertRule(
            rule_id="immediate_review_increase",
            alert_scope="portfolio",
            alert_type="backlog_immediate_increase",
            metric_name="immediate_review_count",
            threshold=1.0,
            severity="warning",
            description=(
                "Immediate review count increased"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="high_review_increase_2",
            alert_scope="portfolio",
            alert_type="backlog_high_increase",
            metric_name="high_review_count",
            threshold=2.0,
            severity="warning",
            description=(
                "High review count increased by >= 2"
            ),
        ),
        # Property degradation rules
        PortfolioTrendAlertRule(
            rule_id="property_degraded",
            alert_scope="property",
            alert_type="property_trend_degraded",
            metric_name="trend_direction",
            threshold=0.0,
            severity="warning",
            description="Property trend direction is degraded",
        ),
        PortfolioTrendAlertRule(
            rule_id="health_score_drop_15",
            alert_scope="property",
            alert_type="lifecycle_health_drop",
            metric_name="lifecycle_health_score_delta",
            threshold=-15.0,
            severity="warning",
            description=(
                "Lifecycle health score decreased by >= 15"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="health_label_attention",
            alert_scope="property",
            alert_type="lifecycle_label_worsening",
            metric_name="lifecycle_health_label",
            threshold=0.0,
            severity="high",
            description=(
                "Health label changed to needs_review "
                "or attention_required"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="open_alert_increase_2",
            alert_scope="property",
            alert_type="open_alert_increase",
            metric_name="open_alert_delta",
            threshold=2.0,
            severity="warning",
            description=(
                "Open alert count increased by >= 2"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="confidence_drop_15",
            alert_scope="property",
            alert_type="cross_site_confidence_drop",
            metric_name="cross_site_confidence_delta",
            threshold=-15.0,
            severity="warning",
            description=(
                "Cross-site confidence decreased by >= 15"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="churn_increase_1_5",
            alert_scope="property",
            alert_type="churn_index_increase",
            metric_name="churn_index_delta",
            threshold=1.5,
            severity="warning",
            description=(
                "Churn Index increased by >= 1.5"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="dom_v2_increase_30",
            alert_scope="property",
            alert_type="effective_dom_v2_increase",
            metric_name="effective_dom_v2_delta",
            threshold=30.0,
            severity="info",
            description=(
                "Effective DOM v2 increased by >= 30 days"
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def evaluate_portfolio_trend_alerts(
    exports_dir: str = "data/exports",
) -> PortfolioTrendAlertDigest:
    """Evaluate all portfolio trend alert rules against trend data.

    Loads trend data from existing portfolio review pack CSV exports,
    evaluates aggregate and property-level alert rules, and returns
    a complete digest.

    Args:
        exports_dir: Directory with review pack CSV exports.

    Returns:
        PortfolioTrendAlertDigest with all triggered alerts.
    """
    from marketsentry.portfolio_review_trends import (
        build_portfolio_trend_series,
        build_property_trend_series,
        load_portfolio_review_pack_series,
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    digest = PortfolioTrendAlertDigest(generated_at=now)

    series = load_portfolio_review_pack_series(exports_dir)
    if not series:
        digest.alerts.append(PortfolioTrendAlert(
            alert_id="no_pack_data",
            alert_scope="portfolio",
            severity="info",
            alert_type="no_data",
            message="No portfolio review pack CSV files found.",
            generated_at=now,
        ))
        digest.summary = summarize_portfolio_trend_alerts(
            digest.alerts
        )
        return digest

    digest.source_pack_files = [fp for fp, _, _ in series]

    portfolio_points = build_portfolio_trend_series(series)
    property_points = build_property_trend_series(series)

    # Evaluate aggregate alerts
    agg_alerts = evaluate_aggregate_burden_alerts(
        portfolio_points, now
    )
    digest.alerts.extend(agg_alerts)

    # Evaluate property alerts
    prop_alerts = evaluate_property_trend_alerts(
        property_points, now
    )
    digest.alerts.extend(prop_alerts)

    # Summarize
    digest.summary = summarize_portfolio_trend_alerts(
        digest.alerts
    )
    if portfolio_points:
        digest.summary.pack_count = len(portfolio_points)
        digest.summary.first_pack_date = (
            portfolio_points[0].captured_at
        )
        digest.summary.latest_pack_date = (
            portfolio_points[-1].captured_at
        )

    return digest


def evaluate_aggregate_burden_alerts(
    portfolio_points: list,
    generated_at: str,
) -> List[PortfolioTrendAlert]:
    """Evaluate aggregate burden threshold alerts.

    Args:
        portfolio_points: Portfolio-level trend points from M42.
        generated_at: Timestamp for alert generation.

    Returns:
        List of triggered PortfolioTrendAlert instances.
    """
    alerts: List[PortfolioTrendAlert] = []
    if not portfolio_points:
        return alerts

    latest = portfolio_points[-1]
    source = latest.pack_file

    # Absolute burden thresholds
    score = latest.aggregate_review_burden_score
    if score >= 80:
        alerts.append(PortfolioTrendAlert(
            alert_id="burden_high_80",
            alert_scope="portfolio",
            severity="high",
            alert_type="aggregate_burden_high",
            message=(
                f"Aggregate review burden score is {score} "
                f"(high_burden threshold: 80)."
            ),
            metric_name="aggregate_review_burden_score",
            current_value=str(score),
            source_pack_file=source,
            generated_at=generated_at,
            recommended_local_action=(
                "Review portfolio for immediate triage "
                "opportunities."
            ),
        ))
    elif score >= 60:
        alerts.append(PortfolioTrendAlert(
            alert_id="burden_warning_60",
            alert_scope="portfolio",
            severity="warning",
            alert_type="aggregate_burden_warning",
            message=(
                f"Aggregate review burden score is {score} "
                f"(warning threshold: 60)."
            ),
            metric_name="aggregate_review_burden_score",
            current_value=str(score),
            source_pack_file=source,
            generated_at=generated_at,
            recommended_local_action=(
                "Monitor burden trend. Review high-priority "
                "properties."
            ),
        ))

    # Burden increase alert (requires >= 2 packs)
    if len(portfolio_points) >= 2:
        prev = portfolio_points[-2]
        prev_score = prev.aggregate_review_burden_score
        delta = score - prev_score
        if delta >= 15:
            alerts.append(PortfolioTrendAlert(
                alert_id="burden_increase_15",
                alert_scope="portfolio",
                severity="warning",
                alert_type="aggregate_burden_increase",
                message=(
                    f"Aggregate burden increased by {delta} "
                    f"(from {prev_score} to {score})."
                ),
                metric_name="aggregate_burden_delta",
                previous_value=str(prev_score),
                current_value=str(score),
                delta_value=str(delta),
                source_pack_file=source,
                generated_at=generated_at,
                recommended_local_action=(
                    "Investigate properties driving burden "
                    "increase."
                ),
            ))

        # Burden label worsening
        prev_label = prev.aggregate_review_status_label
        curr_label = latest.aggregate_review_status_label
        if curr_label in ("elevated_burden", "high_burden") and (
            curr_label != prev_label
        ):
            sev = (
                "high" if curr_label == "high_burden"
                else "warning"
            )
            alerts.append(PortfolioTrendAlert(
                alert_id="burden_label_worsening",
                alert_scope="portfolio",
                severity=sev,
                alert_type="burden_label_worsening",
                message=(
                    f"Burden label changed from {prev_label} "
                    f"to {curr_label}."
                ),
                metric_name="aggregate_review_status_label",
                previous_value=prev_label,
                current_value=curr_label,
                source_pack_file=source,
                generated_at=generated_at,
                recommended_local_action=(
                    "Review portfolio burden drivers."
                ),
            ))

        # Backlog alerts
        prev_imm = prev.immediate_review_count
        curr_imm = latest.immediate_review_count
        if curr_imm > prev_imm:
            alerts.append(PortfolioTrendAlert(
                alert_id="immediate_review_increase",
                alert_scope="portfolio",
                severity="warning",
                alert_type="backlog_immediate_increase",
                message=(
                    f"Immediate review count increased from "
                    f"{prev_imm} to {curr_imm}."
                ),
                metric_name="immediate_review_count",
                previous_value=str(prev_imm),
                current_value=str(curr_imm),
                delta_value=str(curr_imm - prev_imm),
                source_pack_file=source,
                generated_at=generated_at,
                recommended_local_action=(
                    "Prioritize immediate review backlog."
                ),
            ))

        prev_high = prev.high_review_count
        curr_high = latest.high_review_count
        h_delta = curr_high - prev_high
        if h_delta >= 2:
            alerts.append(PortfolioTrendAlert(
                alert_id="high_review_increase_2",
                alert_scope="portfolio",
                severity="warning",
                alert_type="backlog_high_increase",
                message=(
                    f"High review count increased by {h_delta} "
                    f"(from {prev_high} to {curr_high})."
                ),
                metric_name="high_review_count",
                previous_value=str(prev_high),
                current_value=str(curr_high),
                delta_value=str(h_delta),
                source_pack_file=source,
                generated_at=generated_at,
                recommended_local_action=(
                    "Review growing high-priority backlog."
                ),
            ))

        # Rising high/critical alert burden
        prev_hca = prev.high_critical_alert_total
        curr_hca = latest.high_critical_alert_total
        hca_delta = curr_hca - prev_hca
        if hca_delta >= 1:
            alerts.append(PortfolioTrendAlert(
                alert_id="high_critical_alert_increase",
                alert_scope="portfolio",
                severity="high",
                alert_type="high_critical_alert_increase",
                message=(
                    f"High/critical alert total increased by "
                    f"{hca_delta} (from {prev_hca} to "
                    f"{curr_hca})."
                ),
                metric_name="high_critical_alert_total",
                previous_value=str(prev_hca),
                current_value=str(curr_hca),
                delta_value=str(hca_delta),
                source_pack_file=source,
                generated_at=generated_at,
                recommended_local_action=(
                    "Review properties with new high/critical "
                    "alerts."
                ),
            ))

        # Rising lifecycle attention/needs_review burden
        prev_att = prev.lifecycle_attention_required_count
        curr_att = latest.lifecycle_attention_required_count
        prev_nr = prev.lifecycle_needs_review_count
        curr_nr = latest.lifecycle_needs_review_count
        lc_delta = (curr_att + curr_nr) - (prev_att + prev_nr)
        if lc_delta >= 2:
            alerts.append(PortfolioTrendAlert(
                alert_id="lifecycle_burden_increase",
                alert_scope="portfolio",
                severity="warning",
                alert_type="lifecycle_burden_increase",
                message=(
                    f"Lifecycle attention/needs_review count "
                    f"increased by {lc_delta}."
                ),
                metric_name="lifecycle_burden_count",
                previous_value=str(prev_att + prev_nr),
                current_value=str(curr_att + curr_nr),
                delta_value=str(lc_delta),
                source_pack_file=source,
                generated_at=generated_at,
                recommended_local_action=(
                    "Review properties with worsening "
                    "lifecycle health."
                ),
            ))

        # Worsening cross-site confidence trend
        prev_cs = prev.avg_cross_site_confidence
        curr_cs = latest.avg_cross_site_confidence
        if prev_cs is not None and curr_cs is not None:
            cs_delta = curr_cs - prev_cs
            if cs_delta <= -15:
                alerts.append(PortfolioTrendAlert(
                    alert_id="avg_confidence_drop",
                    alert_scope="portfolio",
                    severity="warning",
                    alert_type="cross_site_confidence_drop",
                    message=(
                        f"Avg cross-site confidence dropped "
                        f"by {abs(cs_delta):.1f} "
                        f"(from {prev_cs:.1f} to "
                        f"{curr_cs:.1f})."
                    ),
                    metric_name="avg_cross_site_confidence",
                    previous_value=f"{prev_cs:.1f}",
                    current_value=f"{curr_cs:.1f}",
                    delta_value=f"{cs_delta:.1f}",
                    source_pack_file=source,
                    generated_at=generated_at,
                    recommended_local_action=(
                        "Investigate cross-site confidence "
                        "decline."
                    ),
                ))

        # High churn trend
        prev_hc = prev.high_churn_count
        curr_hc = latest.high_churn_count
        hc_delta = curr_hc - prev_hc
        if hc_delta >= 2:
            alerts.append(PortfolioTrendAlert(
                alert_id="high_churn_increase",
                alert_scope="portfolio",
                severity="warning",
                alert_type="high_churn_trend",
                message=(
                    f"High churn property count increased by "
                    f"{hc_delta} (from {prev_hc} to "
                    f"{curr_hc})."
                ),
                metric_name="high_churn_count",
                previous_value=str(prev_hc),
                current_value=str(curr_hc),
                delta_value=str(hc_delta),
                source_pack_file=source,
                generated_at=generated_at,
                recommended_local_action=(
                    "Review properties with high churn."
                ),
            ))

    return alerts


def evaluate_property_trend_alerts(
    property_points: list,
    generated_at: str,
) -> List[PortfolioTrendAlert]:
    """Evaluate property-level trend threshold alerts.

    Args:
        property_points: Per-property trend points from M42.
        generated_at: Timestamp for alert generation.

    Returns:
        List of triggered PortfolioTrendAlert instances.
    """
    alerts: List[PortfolioTrendAlert] = []

    for pt in property_points:
        base_id = f"prop_{pt.property_id}"

        # Property trend degraded
        if pt.trend_direction == "degraded":
            alerts.append(PortfolioTrendAlert(
                alert_id=f"{base_id}_degraded",
                alert_scope="property",
                property_id=str(pt.property_id),
                candidate_id=str(pt.candidate_id),
                address=pt.address,
                severity="warning",
                alert_type="property_trend_degraded",
                message=(
                    f"{pt.address}: trend direction is "
                    f"degraded. {pt.trend_summary}"
                ),
                metric_name="trend_direction",
                current_value="degraded",
                recommended_local_action=(
                    pt.recommended_review_action
                    or "Review property trend details."
                ),
                generated_at=generated_at,
            ))

        # Lifecycle health score drop >= 15
        d = pt.lifecycle_health_score_delta_first_to_latest
        if d is not None and d <= -15:
            alerts.append(PortfolioTrendAlert(
                alert_id=f"{base_id}_health_drop",
                alert_scope="property",
                property_id=str(pt.property_id),
                candidate_id=str(pt.candidate_id),
                address=pt.address,
                severity="warning",
                alert_type="lifecycle_health_drop",
                message=(
                    f"{pt.address}: lifecycle health score "
                    f"decreased by {abs(d):.1f}."
                ),
                metric_name="lifecycle_health_score_delta",
                current_value=(
                    str(pt.latest_lifecycle_health_score)
                    if pt.latest_lifecycle_health_score
                    is not None else ""
                ),
                delta_value=f"{d:.1f}",
                recommended_local_action=(
                    "Review lifecycle health factors."
                ),
                generated_at=generated_at,
            ))

        # Lifecycle label worsening
        lbl = pt.latest_lifecycle_health_label
        if (
            lbl in ("needs_review", "attention_required")
            and pt.lifecycle_health_label_changes > 0
        ):
            alerts.append(PortfolioTrendAlert(
                alert_id=f"{base_id}_health_label",
                alert_scope="property",
                property_id=str(pt.property_id),
                candidate_id=str(pt.candidate_id),
                address=pt.address,
                severity="high",
                alert_type="lifecycle_label_worsening",
                message=(
                    f"{pt.address}: lifecycle health label "
                    f"is {lbl} (changed "
                    f"{pt.lifecycle_health_label_changes}x)."
                ),
                metric_name="lifecycle_health_label",
                current_value=lbl,
                recommended_local_action=(
                    "Prioritize lifecycle health review."
                ),
                generated_at=generated_at,
            ))

        # Open alert count increase >= 2
        if pt.open_alert_delta_first_to_latest >= 2:
            alerts.append(PortfolioTrendAlert(
                alert_id=f"{base_id}_alert_increase",
                alert_scope="property",
                property_id=str(pt.property_id),
                candidate_id=str(pt.candidate_id),
                address=pt.address,
                severity="warning",
                alert_type="open_alert_increase",
                message=(
                    f"{pt.address}: open alert count "
                    f"increased by "
                    f"{pt.open_alert_delta_first_to_latest}."
                ),
                metric_name="open_alert_delta",
                current_value=str(pt.latest_open_alert_count),
                delta_value=str(
                    pt.open_alert_delta_first_to_latest
                ),
                recommended_local_action=(
                    "Review new open alerts."
                ),
                generated_at=generated_at,
            ))

        # Cross-site confidence drop >= 15
        cd = pt.cross_site_confidence_delta_first_to_latest
        if cd is not None and cd <= -15:
            alerts.append(PortfolioTrendAlert(
                alert_id=f"{base_id}_confidence_drop",
                alert_scope="property",
                property_id=str(pt.property_id),
                candidate_id=str(pt.candidate_id),
                address=pt.address,
                severity="warning",
                alert_type="cross_site_confidence_drop",
                message=(
                    f"{pt.address}: cross-site confidence "
                    f"decreased by {abs(cd):.1f}."
                ),
                metric_name="cross_site_confidence_delta",
                current_value=(
                    f"{pt.latest_cross_site_confidence:.1f}"
                    if pt.latest_cross_site_confidence
                    is not None else ""
                ),
                delta_value=f"{cd:.1f}",
                recommended_local_action=(
                    "Investigate cross-site confidence "
                    "decline."
                ),
                generated_at=generated_at,
            ))

        # Churn Index increase >= 1.5
        chi = pt.churn_index_delta_first_to_latest
        if chi is not None and chi >= 1.5:
            alerts.append(PortfolioTrendAlert(
                alert_id=f"{base_id}_churn_increase",
                alert_scope="property",
                property_id=str(pt.property_id),
                candidate_id=str(pt.candidate_id),
                address=pt.address,
                severity="warning",
                alert_type="churn_index_increase",
                message=(
                    f"{pt.address}: Churn Index increased "
                    f"by {chi:.2f}."
                ),
                metric_name="churn_index_delta",
                current_value=(
                    f"{pt.latest_recent_churn_index:.2f}"
                    if pt.latest_recent_churn_index
                    is not None else ""
                ),
                delta_value=f"{chi:.2f}",
                recommended_local_action=(
                    "Review listing churn history."
                ),
                generated_at=generated_at,
            ))

        # Effective DOM v2 increase >= 30
        dd = pt.effective_dom_v2_delta_first_to_latest
        if dd is not None and dd >= 30:
            alerts.append(PortfolioTrendAlert(
                alert_id=f"{base_id}_dom_increase",
                alert_scope="property",
                property_id=str(pt.property_id),
                candidate_id=str(pt.candidate_id),
                address=pt.address,
                severity="info",
                alert_type="effective_dom_v2_increase",
                message=(
                    f"{pt.address}: Effective DOM v2 "
                    f"increased by {dd} days."
                ),
                metric_name="effective_dom_v2_delta",
                current_value=(
                    str(pt.latest_effective_dom_v2)
                    if pt.latest_effective_dom_v2
                    is not None else ""
                ),
                delta_value=str(dd),
                recommended_local_action=(
                    "Note extended market exposure."
                ),
                generated_at=generated_at,
            ))

    return alerts


def summarize_portfolio_trend_alerts(
    alerts: List[PortfolioTrendAlert],
) -> PortfolioTrendAlertSummary:
    """Summarize trend alerts by severity.

    Args:
        alerts: List of triggered alerts.

    Returns:
        PortfolioTrendAlertSummary with counts.
    """
    summary = PortfolioTrendAlertSummary(
        total_alerts=len(alerts),
    )
    for a in alerts:
        if a.severity == "info":
            summary.info_count += 1
        elif a.severity == "warning":
            summary.warning_count += 1
        elif a.severity == "high":
            summary.high_count += 1
    return summary


def export_portfolio_trend_alert_digest(
    exports_dir: str = "data/exports",
    output_dir: str = "data/exports",
    fmt: str = "both",
) -> PortfolioTrendAlertRunResult:
    """Evaluate trend alerts and export digest.

    Args:
        exports_dir: Directory with review pack CSV exports.
        output_dir: Directory for output digest files.
        fmt: Export format: csv, md, or both.

    Returns:
        PortfolioTrendAlertRunResult with paths and summary.
    """
    result = PortfolioTrendAlertRunResult()

    digest = evaluate_portfolio_trend_alerts(exports_dir)
    result.alert_count = len(digest.alerts)
    result.summary = digest.summary

    if not digest.alerts:
        result.warnings.append("No trend alerts triggered.")
        return result

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if fmt in ("csv", "both"):
        csv_path = os.path.join(
            output_dir,
            f"portfolio_trend_alert_digest_{ts}.csv",
        )
        _write_alert_csv(csv_path, digest)
        result.export_paths.append(csv_path)

    if fmt in ("md", "both"):
        md_path = os.path.join(
            output_dir,
            f"portfolio_trend_alert_digest_{ts}.md",
        )
        _write_alert_md(md_path, digest)
        result.export_paths.append(md_path)

    return result


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

def _write_alert_csv(
    path: str,
    digest: PortfolioTrendAlertDigest,
) -> None:
    """Write alert digest to CSV.

    Args:
        path: Output CSV file path.
        digest: Alert digest to write.
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=ALERT_DIGEST_CSV_FIELDNAMES
        )
        writer.writeheader()
        for a in digest.alerts:
            writer.writerow({
                "alert_id": a.alert_id,
                "alert_scope": a.alert_scope,
                "property_id": a.property_id,
                "candidate_id": a.candidate_id,
                "address": a.address,
                "severity": a.severity,
                "alert_type": a.alert_type,
                "message": a.message,
                "metric_name": a.metric_name,
                "previous_value": a.previous_value,
                "current_value": a.current_value,
                "delta_value": a.delta_value,
                "recommended_local_action":
                    a.recommended_local_action,
                "source_pack_file": a.source_pack_file,
                "generated_at": a.generated_at,
            })


# ---------------------------------------------------------------------------
# Markdown writer
# ---------------------------------------------------------------------------

def _write_alert_md(
    path: str,
    digest: PortfolioTrendAlertDigest,
) -> None:
    """Write alert digest to Markdown.

    Args:
        path: Output Markdown file path.
        digest: Alert digest to write.
    """
    lines: List[str] = []
    s = digest.summary

    lines.append(
        "# Portfolio Trend Alert Digest"
    )
    lines.append("")
    lines.append(f"Generated: {digest.generated_at}")
    lines.append("")

    # Safety note
    lines.append(
        "*This alert digest is a local analytical review aid. "
        "It does not make purchase recommendations, infer seller "
        "intent, or mutate candidate/watchlist/alert state. "
        "No outbound notifications are sent.*"
    )
    lines.append("")

    # Summary
    lines.append("## Alert Summary")
    lines.append("")
    lines.append(f"Total alerts: {s.total_alerts}")
    lines.append(f"High: {s.high_count}")
    lines.append(f"Warning: {s.warning_count}")
    lines.append(f"Info: {s.info_count}")
    if s.pack_count:
        lines.append(
            f"Packs analyzed: {s.pack_count} "
            f"({s.first_pack_date} to {s.latest_pack_date})"
        )
    lines.append("")

    # Aggregate portfolio alerts
    agg_alerts = [
        a for a in digest.alerts if a.alert_scope == "portfolio"
    ]
    if agg_alerts:
        lines.append("## Aggregate Portfolio Trend Alerts")
        lines.append("")
        lines.append(
            "| Severity | Type | Message | Action |"
        )
        lines.append("| --- | --- | --- | --- |")
        for a in agg_alerts:
            lines.append(
                f"| {a.severity}"
                f" | {a.alert_type}"
                f" | {a.message[:80]}"
                f" | {a.recommended_local_action[:60]} |"
            )
        lines.append("")

    # Property-level alerts
    prop_alerts = [
        a for a in digest.alerts if a.alert_scope == "property"
    ]
    if prop_alerts:
        lines.append("## Property-Level Trend Alerts")
        lines.append("")
        lines.append(
            "| Severity | Address | Type | Message | Action |"
        )
        lines.append("| --- | --- | --- | --- | --- |")
        for a in prop_alerts[:30]:
            lines.append(
                f"| {a.severity}"
                f" | {a.address}"
                f" | {a.alert_type}"
                f" | {a.message[:60]}"
                f" | {a.recommended_local_action[:50]} |"
            )
        lines.append("")

    # Recommended local review actions
    actionable = [
        a for a in digest.alerts
        if a.recommended_local_action
        and a.severity in ("warning", "high")
    ]
    if actionable:
        lines.append("## Recommended Local Review Actions")
        lines.append("")
        for a in actionable[:15]:
            prefix = (
                f"{a.address}: " if a.address else "Portfolio: "
            )
            lines.append(
                f"- **{prefix}** [{a.severity}] "
                f"{a.recommended_local_action}"
            )
        lines.append("")

    # Source pack files
    if digest.source_pack_files:
        lines.append("## Source Pack Files Analyzed")
        lines.append("")
        for fp in digest.source_pack_files:
            lines.append(f"- {fp}")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(
        "*No outbound notifications were sent. "
        "This digest is for local review only.*"
    )
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
