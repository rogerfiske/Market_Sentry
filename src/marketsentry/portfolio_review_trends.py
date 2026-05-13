"""Portfolio Review Pack Trend Visualization and Aggregate Trend Scoring.

Analyze multiple portfolio review pack CSV exports over time to produce
portfolio-level trend series, per-property trend series, aggregate
review burden scoring, and static dashboard-ready CSV/Markdown outputs.

This module is entirely read-only. It does not mutate candidate,
watchlist, alert, or property state. It reads exported CSV files
and produces trend reports.
"""

import csv
import glob
import logging
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger("marketsentry")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PortfolioReviewTrendPoint(BaseModel):
    """One point in the portfolio-level trend series."""

    pack_file: str = ""
    captured_at: str = ""
    property_count: int = 0
    immediate_review_count: int = 0
    high_review_count: int = 0
    normal_review_count: int = 0
    monitor_count: int = 0
    low_current_activity_count: int = 0
    quiet_fail_count: int = 0
    quiet_missing_count: int = 0
    lifecycle_attention_required_count: int = 0
    lifecycle_needs_review_count: int = 0
    open_alert_total: int = 0
    high_critical_alert_total: int = 0
    avg_lifecycle_health_score: Optional[float] = None
    avg_cross_site_confidence: Optional[float] = None
    avg_recent_churn_index: Optional[float] = None
    avg_effective_dom_v2: Optional[float] = None
    high_churn_count: int = 0
    high_effective_dom_delta_count: int = 0
    aggregate_review_burden_score: int = 0
    aggregate_review_status_label: str = "low_burden"


class PortfolioReviewPropertyTrendPoint(BaseModel):
    """Per-property trend across multiple packs."""

    property_id: int = 0
    candidate_id: int = 0
    address: str = ""
    first_seen_at: str = ""
    latest_seen_at: str = ""
    times_seen: int = 0
    latest_priority_label: str = ""
    priority_label_changes: int = 0
    latest_lifecycle_health_label: str = ""
    lifecycle_health_label_changes: int = 0
    latest_lifecycle_health_score: Optional[float] = None
    lifecycle_health_score_delta_first_to_latest: Optional[float] = None
    latest_open_alert_count: int = 0
    open_alert_delta_first_to_latest: int = 0
    latest_effective_dom_v2: Optional[int] = None
    effective_dom_v2_delta_first_to_latest: Optional[int] = None
    latest_recent_churn_index: Optional[float] = None
    churn_index_delta_first_to_latest: Optional[float] = None
    latest_cross_site_confidence: Optional[float] = None
    cross_site_confidence_delta_first_to_latest: Optional[float] = None
    trend_direction: str = "insufficient_data"
    trend_summary: str = ""
    recommended_review_action: str = ""


class PortfolioReviewTrendSummary(BaseModel):
    """Summary of portfolio review trends."""

    pack_count: int = 0
    first_pack_date: str = ""
    latest_pack_date: str = ""
    latest_burden_score: int = 0
    latest_burden_label: str = ""
    burden_trend_direction: str = "insufficient_data"
    total_properties_tracked: int = 0
    improved_count: int = 0
    degraded_count: int = 0
    stable_count: int = 0
    new_count: int = 0
    insufficient_data_count: int = 0


class PortfolioReviewTrendReportRow(BaseModel):
    """One row in the trend report CSV."""

    row_type: str = ""
    captured_at: str = ""
    pack_file: str = ""
    property_id: str = ""
    candidate_id: str = ""
    address: str = ""
    metric_name: str = ""
    metric_value: str = ""
    trend_direction: str = ""
    trend_summary: str = ""
    recommended_review_action: str = ""


class PortfolioReviewTrendRunResult(BaseModel):
    """Result of a trend analysis run."""

    export_paths: List[str] = Field(default_factory=list)
    source_file_count: int = 0
    portfolio_trend_points: int = 0
    property_trend_rows: int = 0
    summary: Optional[PortfolioReviewTrendSummary] = None
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# CSV field names for trend report
# ---------------------------------------------------------------------------

TREND_CSV_FIELDNAMES = [
    "row_type",
    "captured_at",
    "pack_file",
    "property_id",
    "candidate_id",
    "address",
    "metric_name",
    "metric_value",
    "trend_direction",
    "trend_summary",
    "recommended_review_action",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_int(value) -> Optional[int]:
    """Parse to int, returning None for empty/invalid."""
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _safe_float(value) -> Optional[float]:
    """Parse to float, returning None for empty/invalid."""
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _opt_str(value) -> str:
    """Convert optional value to string, empty for None."""
    if value is None:
        return ""
    return str(value)


_TS_PATTERN = re.compile(
    r"portfolio_review_pack_(\d{8}_\d{6})\.csv$"
)


def _parse_timestamp_from_filename(filename: str) -> Optional[str]:
    """Extract timestamp from portfolio_review_pack_YYYYMMDD_HHMMSS.csv.

    Args:
        filename: CSV filename.

    Returns:
        ISO-formatted timestamp string, or None.
    """
    m = _TS_PATTERN.search(filename)
    if not m:
        return None
    raw = m.group(1)
    try:
        dt = datetime.strptime(raw, "%Y%m%d_%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _burden_label(score: int) -> str:
    """Map aggregate burden score to label.

    Args:
        score: Burden score 0-100.

    Returns:
        Burden label string.
    """
    if score >= 70:
        return "high_burden"
    if score >= 45:
        return "elevated_burden"
    if score >= 20:
        return "moderate_burden"
    return "low_burden"


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def discover_portfolio_review_pack_exports(
    exports_dir: str = "data/exports",
) -> List[Tuple[str, str]]:
    """Discover all portfolio review pack CSV exports.

    Args:
        exports_dir: Directory to search.

    Returns:
        List of (file_path, captured_at) tuples sorted chronologically.
    """
    pattern = os.path.join(exports_dir, "portfolio_review_pack_*.csv")
    files = glob.glob(pattern)
    if not files:
        return []

    results: List[Tuple[str, str]] = []
    for f in files:
        ts = _parse_timestamp_from_filename(os.path.basename(f))
        if ts is None:
            # Fall back to file modification time
            mtime = os.path.getmtime(f)
            ts = datetime.fromtimestamp(mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        results.append((f, ts))

    results.sort(key=lambda x: x[1])
    return results


def load_portfolio_review_pack_series(
    exports_dir: str = "data/exports",
) -> List[Tuple[str, str, List[Dict[str, str]]]]:
    """Load all portfolio review pack CSVs as a time series.

    Args:
        exports_dir: Directory with CSV exports.

    Returns:
        List of (file_path, captured_at, rows) tuples sorted
        chronologically.
    """
    discovered = discover_portfolio_review_pack_exports(exports_dir)
    series: List[Tuple[str, str, List[Dict[str, str]]]] = []

    for file_path, captured_at in discovered:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                series.append((file_path, captured_at, rows))
        except Exception as e:
            logger.warning(
                f"Error loading pack CSV {file_path}: {e}"
            )

    return series


def build_portfolio_trend_series(
    series: List[Tuple[str, str, List[Dict[str, str]]]],
) -> List[PortfolioReviewTrendPoint]:
    """Build portfolio-level trend series from loaded packs.

    Args:
        series: List of (file_path, captured_at, rows) tuples.

    Returns:
        List of PortfolioReviewTrendPoint, one per pack.
    """
    points: List[PortfolioReviewTrendPoint] = []

    for file_path, captured_at, rows in series:
        point = PortfolioReviewTrendPoint(
            pack_file=file_path,
            captured_at=captured_at,
            property_count=len(rows),
        )

        lh_scores: List[float] = []
        cs_scores: List[float] = []
        ci_values: List[float] = []
        dom_values: List[float] = []

        for row in rows:
            # Priority counts
            prl = row.get("review_priority_label", "")
            if prl == "immediate_review":
                point.immediate_review_count += 1
            elif prl == "high_review":
                point.high_review_count += 1
            elif prl == "normal_review":
                point.normal_review_count += 1
            elif prl == "monitor":
                point.monitor_count += 1
            elif prl == "low_current_activity":
                point.low_current_activity_count += 1

            # Quiet
            gk = row.get("quiet_gatekeeper_result", "")
            if gk == "fail":
                point.quiet_fail_count += 1
            qs = row.get("quiet_score", "")
            if qs == "" or qs is None:
                point.quiet_missing_count += 1

            # Lifecycle health
            lhl = row.get("lifecycle_health_label", "")
            if lhl == "attention_required":
                point.lifecycle_attention_required_count += 1
            elif lhl == "needs_review":
                point.lifecycle_needs_review_count += 1

            lhs = _safe_float(row.get("lifecycle_health_score", ""))
            if lhs is not None:
                lh_scores.append(lhs)

            # Alerts
            oac = _safe_int(row.get("open_alert_count", "0")) or 0
            hcac = _safe_int(
                row.get("high_critical_alert_count", "0")
            ) or 0
            point.open_alert_total += oac
            point.high_critical_alert_total += hcac

            # Cross-site confidence
            cs = _safe_float(
                row.get("cross_site_confidence_score", "")
            )
            if cs is not None:
                cs_scores.append(cs)

            # Churn
            ci = _safe_float(row.get("recent_churn_index", ""))
            if ci is not None:
                ci_values.append(ci)
                if ci > 3.0:
                    point.high_churn_count += 1

            # Effective DOM v2
            dom = _safe_float(row.get("effective_dom_v2", ""))
            if dom is not None:
                dom_values.append(dom)

            # High effective DOM delta
            dom_delta = _safe_int(
                row.get("effective_dom_delta", "")
            )
            if dom_delta is not None and abs(dom_delta) > 60:
                point.high_effective_dom_delta_count += 1

        # Averages
        if lh_scores:
            point.avg_lifecycle_health_score = round(
                sum(lh_scores) / len(lh_scores), 1
            )
        if cs_scores:
            point.avg_cross_site_confidence = round(
                sum(cs_scores) / len(cs_scores), 1
            )
        if ci_values:
            point.avg_recent_churn_index = round(
                sum(ci_values) / len(ci_values), 2
            )
        if dom_values:
            point.avg_effective_dom_v2 = round(
                sum(dom_values) / len(dom_values), 1
            )

        # Aggregate review burden score
        point.aggregate_review_burden_score = (
            calculate_portfolio_trend_score(point)
        )
        point.aggregate_review_status_label = _burden_label(
            point.aggregate_review_burden_score
        )

        points.append(point)

    return points


def build_property_trend_series(
    series: List[Tuple[str, str, List[Dict[str, str]]]],
) -> List[PortfolioReviewPropertyTrendPoint]:
    """Build per-property trend series across all packs.

    Args:
        series: List of (file_path, captured_at, rows) tuples.

    Returns:
        List of PortfolioReviewPropertyTrendPoint, one per property.
    """
    # Collect observations per property_id
    # Each observation: (captured_at, row_dict)
    obs_by_pid: Dict[str, List[Tuple[str, Dict[str, str]]]] = {}

    for _file_path, captured_at, rows in series:
        for row in rows:
            pid = row.get("property_id", "")
            if not pid:
                continue
            if pid not in obs_by_pid:
                obs_by_pid[pid] = []
            obs_by_pid[pid].append((captured_at, row))

    results: List[PortfolioReviewPropertyTrendPoint] = []

    for pid in sorted(obs_by_pid.keys(), key=lambda x: _safe_int(x) or 0):
        observations = obs_by_pid[pid]
        first_ts, first_row = observations[0]
        latest_ts, latest_row = observations[-1]

        pt = PortfolioReviewPropertyTrendPoint(
            property_id=_safe_int(pid) or 0,
            address=latest_row.get("address", ""),
            first_seen_at=first_ts,
            latest_seen_at=latest_ts,
            times_seen=len(observations),
        )

        # Latest values
        pt.latest_priority_label = latest_row.get(
            "review_priority_label", ""
        )
        pt.latest_lifecycle_health_label = latest_row.get(
            "lifecycle_health_label", ""
        )
        pt.latest_lifecycle_health_score = _safe_float(
            latest_row.get("lifecycle_health_score", "")
        )
        pt.latest_open_alert_count = _safe_int(
            latest_row.get("open_alert_count", "0")
        ) or 0
        pt.latest_effective_dom_v2 = _safe_int(
            latest_row.get("effective_dom_v2", "")
        )
        pt.latest_recent_churn_index = _safe_float(
            latest_row.get("recent_churn_index", "")
        )
        pt.latest_cross_site_confidence = _safe_float(
            latest_row.get("cross_site_confidence_score", "")
        )
        pt.recommended_review_action = latest_row.get(
            "recommended_review_action", ""
        )

        # Label change counts
        priority_labels = [
            r.get("review_priority_label", "")
            for _, r in observations
        ]
        pt.priority_label_changes = _count_changes(priority_labels)

        lh_labels = [
            r.get("lifecycle_health_label", "")
            for _, r in observations
        ]
        pt.lifecycle_health_label_changes = _count_changes(lh_labels)

        # Deltas (first to latest)
        first_lhs = _safe_float(
            first_row.get("lifecycle_health_score", "")
        )
        if first_lhs is not None and pt.latest_lifecycle_health_score is not None:
            pt.lifecycle_health_score_delta_first_to_latest = round(
                pt.latest_lifecycle_health_score - first_lhs, 2
            )

        first_oac = _safe_int(
            first_row.get("open_alert_count", "0")
        ) or 0
        pt.open_alert_delta_first_to_latest = (
            pt.latest_open_alert_count - first_oac
        )

        first_dom = _safe_int(
            first_row.get("effective_dom_v2", "")
        )
        if first_dom is not None and pt.latest_effective_dom_v2 is not None:
            pt.effective_dom_v2_delta_first_to_latest = (
                pt.latest_effective_dom_v2 - first_dom
            )

        first_ci = _safe_float(
            first_row.get("recent_churn_index", "")
        )
        if first_ci is not None and pt.latest_recent_churn_index is not None:
            pt.churn_index_delta_first_to_latest = round(
                pt.latest_recent_churn_index - first_ci, 2
            )

        first_cs = _safe_float(
            first_row.get("cross_site_confidence_score", "")
        )
        if first_cs is not None and pt.latest_cross_site_confidence is not None:
            pt.cross_site_confidence_delta_first_to_latest = round(
                pt.latest_cross_site_confidence - first_cs, 2
            )

        # Trend direction
        pt.trend_direction = _determine_property_trend(pt)
        pt.trend_summary = _build_trend_summary(pt)

        results.append(pt)

    return results


def _count_changes(labels: List[str]) -> int:
    """Count the number of label transitions in a sequence.

    Args:
        labels: Ordered list of label values.

    Returns:
        Number of times the label changed.
    """
    changes = 0
    for i in range(1, len(labels)):
        if labels[i] != labels[i - 1]:
            changes += 1
    return changes


def _determine_property_trend(
    pt: PortfolioReviewPropertyTrendPoint,
) -> str:
    """Determine the overall trend direction for a property.

    Args:
        pt: Property trend point with deltas computed.

    Returns:
        Trend direction string.
    """
    if pt.times_seen < 2:
        if pt.times_seen == 1:
            return "new"
        return "insufficient_data"

    improved = 0
    degraded = 0

    # Lifecycle health: higher = better
    d = pt.lifecycle_health_score_delta_first_to_latest
    if d is not None:
        if d > 5:
            improved += 1
        elif d < -5:
            degraded += 1

    # Open alerts: fewer = better
    if pt.open_alert_delta_first_to_latest < -1:
        improved += 1
    elif pt.open_alert_delta_first_to_latest > 1:
        degraded += 1

    # Cross-site confidence: higher = better
    cd = pt.cross_site_confidence_delta_first_to_latest
    if cd is not None:
        if cd > 10:
            improved += 1
        elif cd < -10:
            degraded += 1

    # Churn: lower = better
    chi = pt.churn_index_delta_first_to_latest
    if chi is not None:
        if chi < -1.0:
            improved += 1
        elif chi > 1.0:
            degraded += 1

    if improved > 0 and degraded == 0:
        return "improved"
    if degraded > 0 and improved == 0:
        return "degraded"
    if improved > 0 or degraded > 0:
        return "degraded" if degraded > improved else "improved"
    return "stable"


def _build_trend_summary(
    pt: PortfolioReviewPropertyTrendPoint,
) -> str:
    """Build a human-readable trend summary for a property.

    Args:
        pt: Property trend point.

    Returns:
        Summary string.
    """
    parts: List[str] = []

    if pt.times_seen < 2:
        return f"Seen {pt.times_seen} time(s); insufficient data for trend"

    parts.append(f"Seen {pt.times_seen} times")

    if pt.priority_label_changes > 0:
        parts.append(
            f"priority changed {pt.priority_label_changes}x"
        )

    if pt.lifecycle_health_label_changes > 0:
        parts.append(
            f"health label changed"
            f" {pt.lifecycle_health_label_changes}x"
        )

    d = pt.lifecycle_health_score_delta_first_to_latest
    if d is not None and abs(d) >= 5:
        parts.append(f"health score delta: {d:+.1f}")

    if abs(pt.open_alert_delta_first_to_latest) >= 1:
        parts.append(
            f"alert delta: {pt.open_alert_delta_first_to_latest:+d}"
        )

    dd = pt.effective_dom_v2_delta_first_to_latest
    if dd is not None and abs(dd) >= 14:
        parts.append(f"DOM v2 delta: {dd:+d} days")

    chi = pt.churn_index_delta_first_to_latest
    if chi is not None and abs(chi) >= 1.0:
        parts.append(f"churn delta: {chi:+.2f}")

    cs = pt.cross_site_confidence_delta_first_to_latest
    if cs is not None and abs(cs) >= 10:
        parts.append(f"confidence delta: {cs:+.1f}")

    return "; ".join(parts) if parts else "No significant changes"


def calculate_portfolio_trend_score(
    point: PortfolioReviewTrendPoint,
) -> int:
    """Calculate aggregate review burden score for a trend point.

    Higher = more review burden. Capped at 100.
    This is a neutral operational metric, not a purchase score.

    Args:
        point: Portfolio-level trend point.

    Returns:
        Aggregate review burden score (0-100).
    """
    score = 0
    n = point.property_count
    if n == 0:
        return 0

    # Immediate review properties
    score += point.immediate_review_count * 8

    # High review properties
    score += point.high_review_count * 5

    # Normal review properties
    score += point.normal_review_count * 2

    # Lifecycle attention required
    score += point.lifecycle_attention_required_count * 5

    # Lifecycle needs review
    score += point.lifecycle_needs_review_count * 2

    # High/critical alerts
    score += point.high_critical_alert_total * 3

    # Quiet gatekeeper failures
    score += point.quiet_fail_count * 2

    # High churn properties
    score += point.high_churn_count * 2

    # High DOM delta properties
    score += point.high_effective_dom_delta_count * 2

    return min(100, score)


def summarize_portfolio_review_trends(
    portfolio_points: List[PortfolioReviewTrendPoint],
    property_points: List[PortfolioReviewPropertyTrendPoint],
) -> PortfolioReviewTrendSummary:
    """Summarize portfolio review trends.

    Args:
        portfolio_points: Portfolio-level trend series.
        property_points: Per-property trend series.

    Returns:
        PortfolioReviewTrendSummary with aggregate metrics.
    """
    summary = PortfolioReviewTrendSummary(
        pack_count=len(portfolio_points),
        total_properties_tracked=len(property_points),
    )

    if portfolio_points:
        summary.first_pack_date = portfolio_points[0].captured_at
        summary.latest_pack_date = portfolio_points[-1].captured_at
        summary.latest_burden_score = (
            portfolio_points[-1].aggregate_review_burden_score
        )
        summary.latest_burden_label = (
            portfolio_points[-1].aggregate_review_status_label
        )

        # Burden trend direction
        if len(portfolio_points) >= 2:
            first_score = (
                portfolio_points[0].aggregate_review_burden_score
            )
            latest_score = (
                portfolio_points[-1].aggregate_review_burden_score
            )
            delta = latest_score - first_score
            if delta > 5:
                summary.burden_trend_direction = "degraded"
            elif delta < -5:
                summary.burden_trend_direction = "improved"
            else:
                summary.burden_trend_direction = "stable"

    for pt in property_points:
        if pt.trend_direction == "improved":
            summary.improved_count += 1
        elif pt.trend_direction == "degraded":
            summary.degraded_count += 1
        elif pt.trend_direction == "stable":
            summary.stable_count += 1
        elif pt.trend_direction == "new":
            summary.new_count += 1
        else:
            summary.insufficient_data_count += 1

    return summary


def export_portfolio_review_trend_report(
    exports_dir: str = "data/exports",
    output_dir: str = "data/exports",
    fmt: str = "both",
) -> PortfolioReviewTrendRunResult:
    """Build and export the portfolio review trend report.

    Args:
        exports_dir: Directory with review pack CSV exports.
        output_dir: Directory for output reports.
        fmt: Export format: csv, md, or both.

    Returns:
        PortfolioReviewTrendRunResult with paths and summary.
    """
    result = PortfolioReviewTrendRunResult()

    series = load_portfolio_review_pack_series(exports_dir)
    result.source_file_count = len(series)

    if not series:
        result.warnings.append(
            "No portfolio review pack CSV files found."
        )
        return result

    portfolio_points = build_portfolio_trend_series(series)
    property_points = build_property_trend_series(series)
    summary = summarize_portfolio_review_trends(
        portfolio_points, property_points
    )

    result.portfolio_trend_points = len(portfolio_points)
    result.property_trend_rows = len(property_points)
    result.summary = summary

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if fmt in ("csv", "both"):
        csv_path = os.path.join(
            output_dir,
            f"portfolio_review_trends_{ts}.csv",
        )
        _write_trend_csv(
            csv_path, portfolio_points, property_points
        )
        result.export_paths.append(csv_path)

    if fmt in ("md", "both"):
        md_path = os.path.join(
            output_dir,
            f"portfolio_review_trends_{ts}.md",
        )
        _write_trend_md(
            md_path, portfolio_points, property_points, summary
        )
        result.export_paths.append(md_path)

    return result


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

def _write_trend_csv(
    path: str,
    portfolio_points: List[PortfolioReviewTrendPoint],
    property_points: List[PortfolioReviewPropertyTrendPoint],
) -> None:
    """Write trend report to CSV.

    Args:
        path: Output CSV file path.
        portfolio_points: Portfolio-level trend points.
        property_points: Per-property trend points.
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=TREND_CSV_FIELDNAMES
        )
        writer.writeheader()

        # Portfolio summary rows
        for pt in portfolio_points:
            writer.writerow({
                "row_type": "portfolio_summary",
                "captured_at": pt.captured_at,
                "pack_file": pt.pack_file,
                "property_id": "",
                "candidate_id": "",
                "address": "",
                "metric_name": "aggregate_review_burden_score",
                "metric_value": str(pt.aggregate_review_burden_score),
                "trend_direction": pt.aggregate_review_status_label,
                "trend_summary": (
                    f"properties={pt.property_count},"
                    f" immediate={pt.immediate_review_count},"
                    f" high={pt.high_review_count},"
                    f" alerts={pt.open_alert_total}"
                ),
                "recommended_review_action": "",
            })

        # Property trend rows
        for pt in property_points:
            writer.writerow({
                "row_type": "property_trend",
                "captured_at": pt.latest_seen_at,
                "pack_file": "",
                "property_id": str(pt.property_id),
                "candidate_id": str(pt.candidate_id),
                "address": pt.address,
                "metric_name": "property_trend",
                "metric_value": pt.latest_priority_label,
                "trend_direction": pt.trend_direction,
                "trend_summary": pt.trend_summary,
                "recommended_review_action":
                    pt.recommended_review_action,
            })


# ---------------------------------------------------------------------------
# Markdown writer
# ---------------------------------------------------------------------------

def _write_trend_md(
    path: str,
    portfolio_points: List[PortfolioReviewTrendPoint],
    property_points: List[PortfolioReviewPropertyTrendPoint],
    summary: PortfolioReviewTrendSummary,
) -> None:
    """Write trend report to Markdown.

    Args:
        path: Output Markdown file path.
        portfolio_points: Portfolio-level trend points.
        property_points: Per-property trend points.
        summary: Trend summary.
    """
    lines: List[str] = []

    lines.append("# Portfolio Review Pack Trend Report")
    lines.append("")
    lines.append(
        f"Generated: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    lines.append("")

    # Source files
    lines.append("## Source Files Analyzed")
    lines.append("")
    lines.append(f"Pack files: {summary.pack_count}")
    lines.append(
        f"Date range: {summary.first_pack_date}"
        f" to {summary.latest_pack_date}"
    )
    lines.append("")
    for pt in portfolio_points:
        lines.append(f"- {pt.pack_file} ({pt.captured_at})")
    lines.append("")

    # Portfolio trend summary
    lines.append("## Portfolio Trend Summary")
    lines.append("")
    lines.append(
        f"Latest burden score: {summary.latest_burden_score}"
        f" ({summary.latest_burden_label})"
    )
    lines.append(
        f"Burden trend: {summary.burden_trend_direction}"
    )
    lines.append(
        f"Properties tracked: {summary.total_properties_tracked}"
    )
    lines.append(
        f"Improved: {summary.improved_count}"
        f" | Degraded: {summary.degraded_count}"
        f" | Stable: {summary.stable_count}"
        f" | New: {summary.new_count}"
    )
    lines.append("")

    # Aggregate burden over time
    if portfolio_points:
        lines.append("## Aggregate Burden Over Time")
        lines.append("")
        lines.append("| Date | Properties | Burden | Label |")
        lines.append("| --- | --- | --- | --- |")
        for pt in portfolio_points:
            lines.append(
                f"| {pt.captured_at}"
                f" | {pt.property_count}"
                f" | {pt.aggregate_review_burden_score}"
                f" | {pt.aggregate_review_status_label} |"
            )
        lines.append("")

    # Priority count trend
    if portfolio_points:
        lines.append("## Priority Count Trend")
        lines.append("")
        lines.append(
            "| Date | Immediate | High | Normal"
            " | Monitor | Low |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for pt in portfolio_points:
            lines.append(
                f"| {pt.captured_at}"
                f" | {pt.immediate_review_count}"
                f" | {pt.high_review_count}"
                f" | {pt.normal_review_count}"
                f" | {pt.monitor_count}"
                f" | {pt.low_current_activity_count} |"
            )
        lines.append("")

    # Lifecycle health trend
    if portfolio_points:
        lines.append("## Lifecycle Health Trend")
        lines.append("")
        lines.append(
            "| Date | Attention Required | Needs Review"
            " | Avg Score |"
        )
        lines.append("| --- | --- | --- | --- |")
        for pt in portfolio_points:
            avg = (
                f"{pt.avg_lifecycle_health_score:.1f}"
                if pt.avg_lifecycle_health_score is not None
                else "-"
            )
            lines.append(
                f"| {pt.captured_at}"
                f" | {pt.lifecycle_attention_required_count}"
                f" | {pt.lifecycle_needs_review_count}"
                f" | {avg} |"
            )
        lines.append("")

    # Alert burden trend
    if portfolio_points:
        lines.append("## Alert Burden Trend")
        lines.append("")
        lines.append(
            "| Date | Open Alerts | High/Critical |"
        )
        lines.append("| --- | --- | --- |")
        for pt in portfolio_points:
            lines.append(
                f"| {pt.captured_at}"
                f" | {pt.open_alert_total}"
                f" | {pt.high_critical_alert_total} |"
            )
        lines.append("")

    # Top property trend changes
    changed = [
        pt for pt in property_points
        if pt.trend_direction in ("improved", "degraded")
    ]
    if changed:
        changed.sort(
            key=lambda x: 0 if x.trend_direction == "degraded" else 1
        )
        lines.append("## Top Property Trend Changes")
        lines.append("")
        lines.append(
            "| Address | Trend | Priority | Health"
            " | Alert Delta | Summary |"
        )
        lines.append(
            "| --- | --- | --- | --- | --- | --- |"
        )
        for pt in changed[:20]:
            lines.append(
                f"| {pt.address}"
                f" | {pt.trend_direction}"
                f" | {pt.latest_priority_label}"
                f" | {pt.latest_lifecycle_health_label}"
                f" | {pt.open_alert_delta_first_to_latest:+d}"
                f" | {pt.trend_summary[:60]} |"
            )
        lines.append("")

    # Local next actions
    action_pts = [
        pt for pt in property_points
        if pt.recommended_review_action
        and pt.trend_direction in ("degraded", "improved")
    ]
    if action_pts:
        lines.append("## Local Review Actions")
        lines.append("")
        for pt in action_pts[:10]:
            lines.append(
                f"- **{pt.address}** ({pt.trend_direction}):"
                f" {pt.recommended_review_action}"
            )
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(
        "*This trend report is a local analytical review aid. "
        "It does not make purchase recommendations, infer seller "
        "intent, or mutate candidate/watchlist/alert state.*"
    )
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
