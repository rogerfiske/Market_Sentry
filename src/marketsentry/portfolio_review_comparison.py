"""Portfolio Review Pack Historical Comparison Reports.

Compare portfolio review pack CSV exports over time to detect
property-level changes in priority, lifecycle health, alert burden,
Effective DOM, Churn Index, and cross-site confidence.

This module is entirely read-only. It does not mutate candidate,
watchlist, alert, or property state. It reads exported CSV files
and produces comparison reports.
"""

import csv
import glob
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("marketsentry")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PortfolioReviewPackSnapshot(BaseModel):
    """A loaded portfolio review pack CSV snapshot."""

    file_path: str = ""
    loaded_at: str = ""
    property_count: int = 0
    rows: List[Dict[str, str]] = Field(default_factory=list)


class PortfolioReviewPropertyChange(BaseModel):
    """A per-property change between two review packs."""

    property_id: int = 0
    candidate_id: int = 0
    address: str = ""
    city: str = ""
    zip_code: str = ""
    change_type: str = ""  # added, removed, changed, unchanged
    trend_label: str = ""  # improved, degraded, changed, unchanged, new, removed
    previous_priority_label: str = ""
    current_priority_label: str = ""
    priority_score_delta: int = 0
    previous_lifecycle_health_label: str = ""
    current_lifecycle_health_label: str = ""
    lifecycle_health_score_delta: float = 0.0
    previous_open_alert_count: int = 0
    current_open_alert_count: int = 0
    open_alert_delta: int = 0
    previous_effective_dom_v2: Optional[int] = None
    current_effective_dom_v2: Optional[int] = None
    effective_dom_v2_delta: Optional[int] = None
    previous_recent_churn_index: Optional[float] = None
    current_recent_churn_index: Optional[float] = None
    churn_index_delta: Optional[float] = None
    previous_cross_site_confidence: Optional[float] = None
    current_cross_site_confidence: Optional[float] = None
    cross_site_confidence_delta: Optional[float] = None
    change_summary: str = ""
    recommended_review_action: str = ""


class PortfolioReviewComparisonSummary(BaseModel):
    """Summary metrics for a portfolio review comparison."""

    current_file: str = ""
    previous_file: str = ""
    compared_at: str = ""
    total_properties_current: int = 0
    total_properties_previous: int = 0
    added_count: int = 0
    removed_count: int = 0
    priority_up_count: int = 0
    priority_down_count: int = 0
    lifecycle_health_improved_count: int = 0
    lifecycle_health_degraded_count: int = 0
    alert_burden_increased_count: int = 0
    alert_burden_decreased_count: int = 0
    effective_dom_increased_count: int = 0
    effective_dom_decreased_count: int = 0
    churn_increased_count: int = 0
    churn_decreased_count: int = 0
    cross_site_confidence_improved_count: int = 0
    cross_site_confidence_degraded_count: int = 0
    no_change_count: int = 0


class PortfolioReviewComparisonReportRow(BaseModel):
    """One row in the comparison report CSV."""

    property_id: int = 0
    candidate_id: int = 0
    address: str = ""
    city: str = ""
    zip: str = ""
    change_type: str = ""
    trend_label: str = ""
    previous_priority_label: str = ""
    current_priority_label: str = ""
    priority_score_delta: int = 0
    previous_lifecycle_health_label: str = ""
    current_lifecycle_health_label: str = ""
    lifecycle_health_score_delta: float = 0.0
    previous_open_alert_count: int = 0
    current_open_alert_count: int = 0
    open_alert_delta: int = 0
    previous_effective_dom_v2: str = ""
    current_effective_dom_v2: str = ""
    effective_dom_v2_delta: str = ""
    previous_recent_churn_index: str = ""
    current_recent_churn_index: str = ""
    churn_index_delta: str = ""
    previous_cross_site_confidence: str = ""
    current_cross_site_confidence: str = ""
    cross_site_confidence_delta: str = ""
    change_summary: str = ""
    recommended_review_action: str = ""


class PortfolioReviewComparisonRunResult(BaseModel):
    """Result of a comparison run."""

    current_file: str = ""
    previous_file: str = ""
    export_paths: List[str] = Field(default_factory=list)
    row_count: int = 0
    summary: Optional[PortfolioReviewComparisonSummary] = None
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# CSV field names for comparison report
# ---------------------------------------------------------------------------

COMPARISON_CSV_FIELDNAMES = [
    "property_id",
    "candidate_id",
    "address",
    "city",
    "zip",
    "change_type",
    "trend_label",
    "previous_priority_label",
    "current_priority_label",
    "priority_score_delta",
    "previous_lifecycle_health_label",
    "current_lifecycle_health_label",
    "lifecycle_health_score_delta",
    "previous_open_alert_count",
    "current_open_alert_count",
    "open_alert_delta",
    "previous_effective_dom_v2",
    "current_effective_dom_v2",
    "effective_dom_v2_delta",
    "previous_recent_churn_index",
    "current_recent_churn_index",
    "churn_index_delta",
    "previous_cross_site_confidence",
    "current_cross_site_confidence",
    "cross_site_confidence_delta",
    "change_summary",
    "recommended_review_action",
]


# ---------------------------------------------------------------------------
# Priority label ordering (higher index = higher priority)
# ---------------------------------------------------------------------------

_PRIORITY_ORDER = {
    "low_current_activity": 0,
    "monitor": 1,
    "normal_review": 2,
    "high_review": 3,
    "immediate_review": 4,
}


# ---------------------------------------------------------------------------
# Material change thresholds
# ---------------------------------------------------------------------------

_SCORE_THRESHOLD = 5
_DOM_THRESHOLD = 14
_CHURN_THRESHOLD = 1.0
_CONFIDENCE_THRESHOLD = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_int(value: str) -> Optional[int]:
    """Parse string to int, returning None for empty/invalid."""
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _safe_float(value: str) -> Optional[float]:
    """Parse string to float, returning None for empty/invalid."""
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _opt_str(value) -> str:
    """Convert optional value to string for CSV, empty for None."""
    if value is None:
        return ""
    return str(value)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def load_portfolio_review_pack_csv(
    file_path: str,
) -> PortfolioReviewPackSnapshot:
    """Load a portfolio review pack CSV export.

    Args:
        file_path: Path to the CSV file.

    Returns:
        PortfolioReviewPackSnapshot with rows loaded.
    """
    snapshot = PortfolioReviewPackSnapshot(
        file_path=file_path,
        loaded_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    if not os.path.isfile(file_path):
        logger.warning(f"Portfolio review pack CSV not found: {file_path}")
        return snapshot

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            snapshot.rows = rows
            snapshot.property_count = len(rows)
    except Exception as e:
        logger.error(f"Error loading portfolio review pack CSV: {e}")

    return snapshot


def find_latest_portfolio_review_pack(
    exports_dir: str = "data/exports",
) -> Optional[str]:
    """Find the latest portfolio review pack CSV export.

    Args:
        exports_dir: Directory to search for CSV files.

    Returns:
        Path to the latest CSV file, or None if not found.
    """
    pattern = os.path.join(exports_dir, "portfolio_review_pack_*.csv")
    files = glob.glob(pattern)
    if not files:
        return None
    # Sort by modification time, newest first
    files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    return files[0]


def find_previous_portfolio_review_pack(
    exports_dir: str = "data/exports",
) -> Optional[str]:
    """Find the previous (second most recent) portfolio review pack CSV export.

    Args:
        exports_dir: Directory to search for CSV files.

    Returns:
        Path to the previous CSV file, or None if fewer than 2 exist.
    """
    pattern = os.path.join(exports_dir, "portfolio_review_pack_*.csv")
    files = glob.glob(pattern)
    if len(files) < 2:
        return None
    files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    return files[1]


def compare_portfolio_review_packs(
    current: PortfolioReviewPackSnapshot,
    previous: PortfolioReviewPackSnapshot,
) -> List[PortfolioReviewPropertyChange]:
    """Compare two portfolio review pack snapshots.

    Detects per-property changes: added, removed, unchanged, changed.
    Includes material change detection for scores, DOM, churn,
    confidence, alerts, and lifecycle health.

    Args:
        current: The current (newer) review pack snapshot.
        previous: The previous (older) review pack snapshot.

    Returns:
        List of per-property changes.
    """
    changes: List[PortfolioReviewPropertyChange] = []

    # Index by property_id
    curr_by_id: Dict[str, Dict[str, str]] = {}
    prev_by_id: Dict[str, Dict[str, str]] = {}

    for row in current.rows:
        pid = row.get("property_id", "")
        if pid:
            curr_by_id[pid] = row

    for row in previous.rows:
        pid = row.get("property_id", "")
        if pid:
            prev_by_id[pid] = row

    all_ids = set(curr_by_id.keys()) | set(prev_by_id.keys())

    for pid in sorted(all_ids, key=lambda x: _safe_int(x) or 0):
        curr_row = curr_by_id.get(pid)
        prev_row = prev_by_id.get(pid)

        change = _compare_property(pid, curr_row, prev_row)
        changes.append(change)

    return changes


def _compare_property(
    pid: str,
    curr_row: Optional[Dict[str, str]],
    prev_row: Optional[Dict[str, str]],
) -> PortfolioReviewPropertyChange:
    """Compare a single property between two snapshots.

    Args:
        pid: Property ID string.
        curr_row: Current snapshot row dict, or None if removed.
        prev_row: Previous snapshot row dict, or None if added.

    Returns:
        PortfolioReviewPropertyChange describing the change.
    """
    change = PortfolioReviewPropertyChange(
        property_id=_safe_int(pid) or 0,
    )

    # Added property
    if curr_row and not prev_row:
        change.change_type = "added"
        change.trend_label = "new"
        change.address = curr_row.get("address", "")
        change.city = curr_row.get("city", "")
        change.zip_code = curr_row.get("zip", "")
        change.current_priority_label = curr_row.get(
            "review_priority_label", ""
        )
        change.current_lifecycle_health_label = curr_row.get(
            "lifecycle_health_label", ""
        )
        change.current_open_alert_count = _safe_int(
            curr_row.get("open_alert_count", "0")
        ) or 0
        change.current_effective_dom_v2 = _safe_int(
            curr_row.get("effective_dom_v2", "")
        )
        change.current_recent_churn_index = _safe_float(
            curr_row.get("recent_churn_index", "")
        )
        change.current_cross_site_confidence = _safe_float(
            curr_row.get("cross_site_confidence_score", "")
        )
        change.recommended_review_action = curr_row.get(
            "recommended_review_action", ""
        )
        change.change_summary = "Property added to review pack"
        return change

    # Removed property
    if prev_row and not curr_row:
        change.change_type = "removed"
        change.trend_label = "removed"
        change.address = prev_row.get("address", "")
        change.city = prev_row.get("city", "")
        change.zip_code = prev_row.get("zip", "")
        change.previous_priority_label = prev_row.get(
            "review_priority_label", ""
        )
        change.previous_lifecycle_health_label = prev_row.get(
            "lifecycle_health_label", ""
        )
        change.previous_open_alert_count = _safe_int(
            prev_row.get("open_alert_count", "0")
        ) or 0
        change.previous_effective_dom_v2 = _safe_int(
            prev_row.get("effective_dom_v2", "")
        )
        change.previous_recent_churn_index = _safe_float(
            prev_row.get("recent_churn_index", "")
        )
        change.previous_cross_site_confidence = _safe_float(
            prev_row.get("cross_site_confidence_score", "")
        )
        change.change_summary = "Property removed from review pack"
        return change

    # Both exist - compare
    assert curr_row is not None and prev_row is not None

    change.address = curr_row.get("address", "")
    change.city = curr_row.get("city", "")
    change.zip_code = curr_row.get("zip", "")
    change.recommended_review_action = curr_row.get(
        "recommended_review_action", ""
    )

    # Priority
    change.previous_priority_label = prev_row.get(
        "review_priority_label", ""
    )
    change.current_priority_label = curr_row.get(
        "review_priority_label", ""
    )
    prev_score = _safe_int(prev_row.get("review_priority_score", "0")) or 0
    curr_score = _safe_int(curr_row.get("review_priority_score", "0")) or 0
    change.priority_score_delta = curr_score - prev_score

    # Lifecycle health
    change.previous_lifecycle_health_label = prev_row.get(
        "lifecycle_health_label", ""
    )
    change.current_lifecycle_health_label = curr_row.get(
        "lifecycle_health_label", ""
    )
    prev_lh = _safe_float(
        prev_row.get("lifecycle_health_score", "")
    )
    curr_lh = _safe_float(
        curr_row.get("lifecycle_health_score", "")
    )
    if prev_lh is not None and curr_lh is not None:
        change.lifecycle_health_score_delta = round(
            curr_lh - prev_lh, 2
        )

    # Open alerts
    change.previous_open_alert_count = _safe_int(
        prev_row.get("open_alert_count", "0")
    ) or 0
    change.current_open_alert_count = _safe_int(
        curr_row.get("open_alert_count", "0")
    ) or 0
    change.open_alert_delta = (
        change.current_open_alert_count - change.previous_open_alert_count
    )

    # Effective DOM v2
    change.previous_effective_dom_v2 = _safe_int(
        prev_row.get("effective_dom_v2", "")
    )
    change.current_effective_dom_v2 = _safe_int(
        curr_row.get("effective_dom_v2", "")
    )
    if (change.previous_effective_dom_v2 is not None
            and change.current_effective_dom_v2 is not None):
        change.effective_dom_v2_delta = (
            change.current_effective_dom_v2
            - change.previous_effective_dom_v2
        )

    # Churn index
    change.previous_recent_churn_index = _safe_float(
        prev_row.get("recent_churn_index", "")
    )
    change.current_recent_churn_index = _safe_float(
        curr_row.get("recent_churn_index", "")
    )
    if (change.previous_recent_churn_index is not None
            and change.current_recent_churn_index is not None):
        change.churn_index_delta = round(
            change.current_recent_churn_index
            - change.previous_recent_churn_index,
            2,
        )

    # Cross-site confidence
    change.previous_cross_site_confidence = _safe_float(
        prev_row.get("cross_site_confidence_score", "")
    )
    change.current_cross_site_confidence = _safe_float(
        curr_row.get("cross_site_confidence_score", "")
    )
    if (change.previous_cross_site_confidence is not None
            and change.current_cross_site_confidence is not None):
        change.cross_site_confidence_delta = round(
            change.current_cross_site_confidence
            - change.previous_cross_site_confidence,
            2,
        )

    # Determine change type and trend
    change_reasons = _detect_changes(change, curr_row, prev_row)
    if change_reasons:
        change.change_type = "changed"
        change.change_summary = "; ".join(change_reasons)
        change.trend_label = _determine_trend(change)
    else:
        change.change_type = "unchanged"
        change.trend_label = "unchanged"
        change.change_summary = "No material changes detected"

    return change


def _detect_changes(
    change: PortfolioReviewPropertyChange,
    curr_row: Dict[str, str],
    prev_row: Dict[str, str],
) -> List[str]:
    """Detect material changes between current and previous rows.

    Args:
        change: The property change object being built.
        curr_row: Current CSV row.
        prev_row: Previous CSV row.

    Returns:
        List of change reason strings.
    """
    reasons: List[str] = []

    # Active/inactive status
    curr_active = curr_row.get("active_watch_status", "")
    prev_active = prev_row.get("active_watch_status", "")
    if curr_active != prev_active:
        reasons.append(
            f"active status changed: {prev_active} -> {curr_active}"
        )

    # Priority label change
    if change.current_priority_label != change.previous_priority_label:
        reasons.append(
            f"priority changed: {change.previous_priority_label}"
            f" -> {change.current_priority_label}"
        )

    # Priority score change (material)
    if abs(change.priority_score_delta) >= _SCORE_THRESHOLD:
        reasons.append(
            f"priority score delta: {change.priority_score_delta:+d}"
        )

    # Quiet gatekeeper change
    curr_gk = curr_row.get("quiet_gatekeeper_result", "")
    prev_gk = prev_row.get("quiet_gatekeeper_result", "")
    if curr_gk != prev_gk:
        reasons.append(
            f"quiet gatekeeper changed: {prev_gk} -> {curr_gk}"
        )

    # Quiet score material change
    curr_qs = _safe_float(curr_row.get("quiet_score", ""))
    prev_qs = _safe_float(prev_row.get("quiet_score", ""))
    if curr_qs is not None and prev_qs is not None:
        if abs(curr_qs - prev_qs) >= _SCORE_THRESHOLD:
            reasons.append(
                f"quiet score delta: {curr_qs - prev_qs:+.1f}"
            )

    # Vibrancy score material change
    curr_vs = _safe_float(curr_row.get("vibrancy_score", ""))
    prev_vs = _safe_float(prev_row.get("vibrancy_score", ""))
    if curr_vs is not None and prev_vs is not None:
        if abs(curr_vs - prev_vs) >= _SCORE_THRESHOLD:
            reasons.append(
                f"vibrancy score delta: {curr_vs - prev_vs:+.1f}"
            )

    # Effective DOM v2 material change
    if (change.effective_dom_v2_delta is not None
            and abs(change.effective_dom_v2_delta) >= _DOM_THRESHOLD):
        reasons.append(
            f"effective DOM v2 delta: {change.effective_dom_v2_delta:+d} days"
        )

    # Churn index material change
    if (change.churn_index_delta is not None
            and abs(change.churn_index_delta) >= _CHURN_THRESHOLD):
        reasons.append(
            f"churn index delta: {change.churn_index_delta:+.2f}"
        )

    # Cross-site confidence material change
    if (change.cross_site_confidence_delta is not None
            and abs(change.cross_site_confidence_delta)
            >= _CONFIDENCE_THRESHOLD):
        reasons.append(
            f"cross-site confidence delta:"
            f" {change.cross_site_confidence_delta:+.1f}"
        )

    # Discrepancy severity change
    curr_disc = curr_row.get("discrepancy_severity_label", "")
    prev_disc = prev_row.get("discrepancy_severity_label", "")
    if curr_disc != prev_disc:
        reasons.append(
            f"discrepancy severity changed: {prev_disc} -> {curr_disc}"
        )

    # Open alert count change
    if abs(change.open_alert_delta) >= 1:
        reasons.append(
            f"open alert count delta: {change.open_alert_delta:+d}"
        )

    # High/critical alert count change
    curr_hc = _safe_int(
        curr_row.get("high_critical_alert_count", "0")
    ) or 0
    prev_hc = _safe_int(
        prev_row.get("high_critical_alert_count", "0")
    ) or 0
    if abs(curr_hc - prev_hc) >= 1:
        reasons.append(
            f"high/critical alert delta: {curr_hc - prev_hc:+d}"
        )

    # Lifecycle health label change
    if (change.current_lifecycle_health_label
            != change.previous_lifecycle_health_label):
        reasons.append(
            f"lifecycle health changed:"
            f" {change.previous_lifecycle_health_label}"
            f" -> {change.current_lifecycle_health_label}"
        )

    # Lifecycle health score material change
    if abs(change.lifecycle_health_score_delta) >= _SCORE_THRESHOLD:
        reasons.append(
            f"lifecycle health score delta:"
            f" {change.lifecycle_health_score_delta:+.1f}"
        )

    # Recommended review action change
    curr_act = curr_row.get("recommended_review_action", "")
    prev_act = prev_row.get("recommended_review_action", "")
    if curr_act != prev_act:
        reasons.append("recommended review action changed")

    return reasons


def _determine_trend(
    change: PortfolioReviewPropertyChange,
) -> str:
    """Determine the overall trend label for a property change.

    Uses priority movement, lifecycle health movement, and alert
    burden movement to determine whether changes are overall
    improved, degraded, or mixed (changed).

    Args:
        change: The property change with deltas computed.

    Returns:
        Trend label: improved, degraded, or changed.
    """
    improved_signals = 0
    degraded_signals = 0

    # Priority: lower score = improved (fewer concerns)
    if change.priority_score_delta < -_SCORE_THRESHOLD:
        improved_signals += 1
    elif change.priority_score_delta > _SCORE_THRESHOLD:
        degraded_signals += 1

    # Lifecycle health: higher score = improved
    if change.lifecycle_health_score_delta > _SCORE_THRESHOLD:
        improved_signals += 1
    elif change.lifecycle_health_score_delta < -_SCORE_THRESHOLD:
        degraded_signals += 1

    # Alerts: fewer = improved
    if change.open_alert_delta < 0:
        improved_signals += 1
    elif change.open_alert_delta > 0:
        degraded_signals += 1

    # Cross-site confidence: higher = improved
    if (change.cross_site_confidence_delta is not None
            and change.cross_site_confidence_delta > _CONFIDENCE_THRESHOLD):
        improved_signals += 1
    elif (change.cross_site_confidence_delta is not None
            and change.cross_site_confidence_delta < -_CONFIDENCE_THRESHOLD):
        degraded_signals += 1

    if improved_signals > 0 and degraded_signals == 0:
        return "improved"
    if degraded_signals > 0 and improved_signals == 0:
        return "degraded"
    if improved_signals > 0 or degraded_signals > 0:
        return "changed"
    return "changed"


def compare_current_to_previous_portfolio_pack(
    exports_dir: str = "data/exports",
    current_path: Optional[str] = None,
    previous_path: Optional[str] = None,
) -> tuple:
    """Compare current and previous portfolio review packs.

    Automatically finds latest and previous CSVs if paths not provided.

    Args:
        exports_dir: Directory with CSV exports.
        current_path: Optional explicit path to current CSV.
        previous_path: Optional explicit path to previous CSV.

    Returns:
        Tuple of (changes, summary, current_snapshot, previous_snapshot).
    """
    if current_path is None:
        current_path = find_latest_portfolio_review_pack(exports_dir)
    if current_path is None:
        return (
            [],
            PortfolioReviewComparisonSummary(
                compared_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
            PortfolioReviewPackSnapshot(),
            PortfolioReviewPackSnapshot(),
        )

    if previous_path is None:
        previous_path = find_previous_portfolio_review_pack(exports_dir)

    current_snap = load_portfolio_review_pack_csv(current_path)

    if previous_path is None:
        # No previous pack - all properties are "new"
        prev_snap = PortfolioReviewPackSnapshot()
        changes = compare_portfolio_review_packs(current_snap, prev_snap)
        summary = summarize_portfolio_review_changes(
            changes, current_snap, prev_snap
        )
        return (changes, summary, current_snap, prev_snap)

    prev_snap = load_portfolio_review_pack_csv(previous_path)
    changes = compare_portfolio_review_packs(current_snap, prev_snap)
    summary = summarize_portfolio_review_changes(
        changes, current_snap, prev_snap
    )
    return (changes, summary, current_snap, prev_snap)


def summarize_portfolio_review_changes(
    changes: List[PortfolioReviewPropertyChange],
    current: PortfolioReviewPackSnapshot,
    previous: PortfolioReviewPackSnapshot,
) -> PortfolioReviewComparisonSummary:
    """Summarize per-property changes into aggregate metrics.

    Args:
        changes: List of property changes.
        current: Current snapshot metadata.
        previous: Previous snapshot metadata.

    Returns:
        PortfolioReviewComparisonSummary with aggregate counts.
    """
    summary = PortfolioReviewComparisonSummary(
        current_file=current.file_path,
        previous_file=previous.file_path,
        compared_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_properties_current=current.property_count,
        total_properties_previous=previous.property_count,
    )

    for c in changes:
        if c.change_type == "added":
            summary.added_count += 1
        elif c.change_type == "removed":
            summary.removed_count += 1
        elif c.change_type == "unchanged":
            summary.no_change_count += 1
        elif c.change_type == "changed":
            # Priority movement
            prev_ord = _PRIORITY_ORDER.get(c.previous_priority_label, -1)
            curr_ord = _PRIORITY_ORDER.get(c.current_priority_label, -1)
            if curr_ord > prev_ord and prev_ord >= 0:
                summary.priority_up_count += 1
            elif curr_ord < prev_ord and curr_ord >= 0:
                summary.priority_down_count += 1

            # Lifecycle health
            if c.lifecycle_health_score_delta > _SCORE_THRESHOLD:
                summary.lifecycle_health_improved_count += 1
            elif c.lifecycle_health_score_delta < -_SCORE_THRESHOLD:
                summary.lifecycle_health_degraded_count += 1

            # Alert burden
            if c.open_alert_delta > 0:
                summary.alert_burden_increased_count += 1
            elif c.open_alert_delta < 0:
                summary.alert_burden_decreased_count += 1

            # Effective DOM v2
            if (c.effective_dom_v2_delta is not None
                    and c.effective_dom_v2_delta >= _DOM_THRESHOLD):
                summary.effective_dom_increased_count += 1
            elif (c.effective_dom_v2_delta is not None
                    and c.effective_dom_v2_delta <= -_DOM_THRESHOLD):
                summary.effective_dom_decreased_count += 1

            # Churn
            if (c.churn_index_delta is not None
                    and c.churn_index_delta >= _CHURN_THRESHOLD):
                summary.churn_increased_count += 1
            elif (c.churn_index_delta is not None
                    and c.churn_index_delta <= -_CHURN_THRESHOLD):
                summary.churn_decreased_count += 1

            # Cross-site confidence
            if (c.cross_site_confidence_delta is not None
                    and c.cross_site_confidence_delta
                    >= _CONFIDENCE_THRESHOLD):
                summary.cross_site_confidence_improved_count += 1
            elif (c.cross_site_confidence_delta is not None
                    and c.cross_site_confidence_delta
                    <= -_CONFIDENCE_THRESHOLD):
                summary.cross_site_confidence_degraded_count += 1

    return summary


def export_portfolio_review_comparison(
    exports_dir: str = "data/exports",
    output_dir: str = "data/exports",
    fmt: str = "both",
    current_path: Optional[str] = None,
    previous_path: Optional[str] = None,
) -> PortfolioReviewComparisonRunResult:
    """Compare review packs and export comparison report.

    Args:
        exports_dir: Directory to search for pack CSVs.
        output_dir: Directory for output reports.
        fmt: Export format: csv, md, or both.
        current_path: Optional explicit path to current CSV.
        previous_path: Optional explicit path to previous CSV.

    Returns:
        PortfolioReviewComparisonRunResult with paths and summary.
    """
    result = PortfolioReviewComparisonRunResult()

    changes, summary, curr_snap, prev_snap = (
        compare_current_to_previous_portfolio_pack(
            exports_dir=exports_dir,
            current_path=current_path,
            previous_path=previous_path,
        )
    )

    result.current_file = curr_snap.file_path
    result.previous_file = prev_snap.file_path
    result.summary = summary
    result.row_count = len(changes)

    if not curr_snap.file_path:
        result.warnings.append(
            "No portfolio review pack CSV found in exports directory."
        )
        return result

    if not prev_snap.file_path:
        result.warnings.append(
            "No previous portfolio review pack CSV found. "
            "All properties shown as new."
        )

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if fmt in ("csv", "both"):
        csv_path = os.path.join(
            output_dir,
            f"portfolio_review_comparison_{ts}.csv",
        )
        _write_comparison_csv(csv_path, changes)
        result.export_paths.append(csv_path)

    if fmt in ("md", "both"):
        md_path = os.path.join(
            output_dir,
            f"portfolio_review_comparison_{ts}.md",
        )
        _write_comparison_md(md_path, changes, summary)
        result.export_paths.append(md_path)

    return result


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

def _write_comparison_csv(
    path: str,
    changes: List[PortfolioReviewPropertyChange],
) -> None:
    """Write comparison report to CSV.

    Args:
        path: Output CSV file path.
        changes: List of property changes.
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COMPARISON_CSV_FIELDNAMES)
        writer.writeheader()

        for c in changes:
            writer.writerow({
                "property_id": c.property_id,
                "candidate_id": c.candidate_id,
                "address": c.address,
                "city": c.city,
                "zip": c.zip_code,
                "change_type": c.change_type,
                "trend_label": c.trend_label,
                "previous_priority_label": c.previous_priority_label,
                "current_priority_label": c.current_priority_label,
                "priority_score_delta": c.priority_score_delta,
                "previous_lifecycle_health_label":
                    c.previous_lifecycle_health_label,
                "current_lifecycle_health_label":
                    c.current_lifecycle_health_label,
                "lifecycle_health_score_delta":
                    c.lifecycle_health_score_delta,
                "previous_open_alert_count":
                    c.previous_open_alert_count,
                "current_open_alert_count":
                    c.current_open_alert_count,
                "open_alert_delta": c.open_alert_delta,
                "previous_effective_dom_v2":
                    _opt_str(c.previous_effective_dom_v2),
                "current_effective_dom_v2":
                    _opt_str(c.current_effective_dom_v2),
                "effective_dom_v2_delta":
                    _opt_str(c.effective_dom_v2_delta),
                "previous_recent_churn_index":
                    _opt_str(c.previous_recent_churn_index),
                "current_recent_churn_index":
                    _opt_str(c.current_recent_churn_index),
                "churn_index_delta":
                    _opt_str(c.churn_index_delta),
                "previous_cross_site_confidence":
                    _opt_str(c.previous_cross_site_confidence),
                "current_cross_site_confidence":
                    _opt_str(c.current_cross_site_confidence),
                "cross_site_confidence_delta":
                    _opt_str(c.cross_site_confidence_delta),
                "change_summary": c.change_summary,
                "recommended_review_action":
                    c.recommended_review_action,
            })


# ---------------------------------------------------------------------------
# Markdown writer
# ---------------------------------------------------------------------------

def _write_comparison_md(
    path: str,
    changes: List[PortfolioReviewPropertyChange],
    summary: PortfolioReviewComparisonSummary,
) -> None:
    """Write comparison report to Markdown.

    Args:
        path: Output Markdown file path.
        changes: List of property changes.
        summary: Comparison summary metrics.
    """
    lines: List[str] = []

    lines.append("# Portfolio Review Pack Comparison Report")
    lines.append("")
    lines.append(f"Generated: {summary.compared_at}")
    lines.append("")

    # Source files
    lines.append("## Source Files")
    lines.append("")
    lines.append(f"- Current: {summary.current_file or 'None'}")
    lines.append(f"- Previous: {summary.previous_file or 'None'}")
    lines.append("")

    # Summary metrics
    lines.append("## Summary Metrics")
    lines.append("")
    lines.append(
        f"| Metric | Count |"
    )
    lines.append("| --- | --- |")
    lines.append(
        f"| Current properties | {summary.total_properties_current} |"
    )
    lines.append(
        f"| Previous properties | {summary.total_properties_previous} |"
    )
    lines.append(f"| Added | {summary.added_count} |")
    lines.append(f"| Removed | {summary.removed_count} |")
    lines.append(f"| Priority increased | {summary.priority_up_count} |")
    lines.append(
        f"| Priority decreased | {summary.priority_down_count} |"
    )
    lines.append(
        f"| Lifecycle health improved"
        f" | {summary.lifecycle_health_improved_count} |"
    )
    lines.append(
        f"| Lifecycle health degraded"
        f" | {summary.lifecycle_health_degraded_count} |"
    )
    lines.append(
        f"| Alert burden increased"
        f" | {summary.alert_burden_increased_count} |"
    )
    lines.append(
        f"| Alert burden decreased"
        f" | {summary.alert_burden_decreased_count} |"
    )
    lines.append(
        f"| Effective DOM increased"
        f" | {summary.effective_dom_increased_count} |"
    )
    lines.append(
        f"| Effective DOM decreased"
        f" | {summary.effective_dom_decreased_count} |"
    )
    lines.append(
        f"| Churn increased | {summary.churn_increased_count} |"
    )
    lines.append(
        f"| Churn decreased | {summary.churn_decreased_count} |"
    )
    lines.append(
        f"| Cross-site confidence improved"
        f" | {summary.cross_site_confidence_improved_count} |"
    )
    lines.append(
        f"| Cross-site confidence degraded"
        f" | {summary.cross_site_confidence_degraded_count} |"
    )
    lines.append(f"| No change | {summary.no_change_count} |")
    lines.append("")

    # Added properties
    added = [c for c in changes if c.change_type == "added"]
    if added:
        lines.append("## Added Properties")
        lines.append("")
        for c in added:
            lines.append(
                f"- **{c.address}**, {c.city} {c.zip_code}"
                f" - priority: {c.current_priority_label}"
            )
        lines.append("")

    # Removed properties
    removed = [c for c in changes if c.change_type == "removed"]
    if removed:
        lines.append("## Removed Properties")
        lines.append("")
        for c in removed:
            lines.append(
                f"- **{c.address}**, {c.city} {c.zip_code}"
                f" - was: {c.previous_priority_label}"
            )
        lines.append("")

    # Priority changes
    priority_changes = [
        c for c in changes
        if c.change_type == "changed"
        and c.current_priority_label != c.previous_priority_label
    ]
    if priority_changes:
        lines.append("## Priority Changes")
        lines.append("")
        lines.append(
            "| Address | Previous | Current | Score Delta |"
        )
        lines.append("| --- | --- | --- | --- |")
        for c in priority_changes:
            lines.append(
                f"| {c.address}"
                f" | {c.previous_priority_label}"
                f" | {c.current_priority_label}"
                f" | {c.priority_score_delta:+d} |"
            )
        lines.append("")

    # Lifecycle health changes
    lh_changes = [
        c for c in changes
        if c.change_type == "changed"
        and c.current_lifecycle_health_label
        != c.previous_lifecycle_health_label
    ]
    if lh_changes:
        lines.append("## Lifecycle Health Changes")
        lines.append("")
        lines.append(
            "| Address | Previous | Current | Score Delta |"
        )
        lines.append("| --- | --- | --- | --- |")
        for c in lh_changes:
            lines.append(
                f"| {c.address}"
                f" | {c.previous_lifecycle_health_label}"
                f" | {c.current_lifecycle_health_label}"
                f" | {c.lifecycle_health_score_delta:+.1f} |"
            )
        lines.append("")

    # Alert burden changes
    alert_changes = [
        c for c in changes
        if c.change_type == "changed"
        and c.open_alert_delta != 0
    ]
    if alert_changes:
        lines.append("## Alert Burden Changes")
        lines.append("")
        lines.append(
            "| Address | Previous Alerts | Current Alerts | Delta |"
        )
        lines.append("| --- | --- | --- | --- |")
        for c in alert_changes:
            lines.append(
                f"| {c.address}"
                f" | {c.previous_open_alert_count}"
                f" | {c.current_open_alert_count}"
                f" | {c.open_alert_delta:+d} |"
            )
        lines.append("")

    # DOM/Churn highlights
    dom_churn_changes = [
        c for c in changes
        if c.change_type == "changed"
        and (
            (c.effective_dom_v2_delta is not None
             and abs(c.effective_dom_v2_delta) >= _DOM_THRESHOLD)
            or (c.churn_index_delta is not None
                and abs(c.churn_index_delta) >= _CHURN_THRESHOLD)
        )
    ]
    if dom_churn_changes:
        lines.append("## Effective DOM / Churn Highlights")
        lines.append("")
        lines.append(
            "| Address | DOM v2 Delta | Churn Delta |"
        )
        lines.append("| --- | --- | --- |")
        for c in dom_churn_changes:
            dom_str = (
                f"{c.effective_dom_v2_delta:+d}"
                if c.effective_dom_v2_delta is not None
                else "-"
            )
            churn_str = (
                f"{c.churn_index_delta:+.2f}"
                if c.churn_index_delta is not None
                else "-"
            )
            lines.append(
                f"| {c.address} | {dom_str} | {churn_str} |"
            )
        lines.append("")

    # Local review actions
    action_changes = [
        c for c in changes
        if c.change_type in ("changed", "added")
        and c.recommended_review_action
    ]
    if action_changes:
        lines.append("## Local Review Actions")
        lines.append("")
        for c in action_changes:
            lines.append(
                f"- **{c.address}**: {c.recommended_review_action}"
            )
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(
        "*This comparison report is a local analytical review aid. "
        "It does not make purchase recommendations, infer seller intent, "
        "or mutate candidate/watchlist/alert state.*"
    )
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
