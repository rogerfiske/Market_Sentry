"""Portfolio Alert Focus Preferences and Dashboard Focus Views.

Provides local alert highlight preferences that let the operator
configure which alert categories should be emphasized in reports
and dashboard views. Focus preferences are display-only and do
not mutate candidate, watchlist, or alert state.

Input sources:
- Latest persisted alert history from Milestone 45
- Latest trend alert digest from Milestone 43
- Latest run comparison from Milestone 45 if available

No outbound notifications are sent.
No database writes are performed.
No live retrieval is performed.
"""

import csv
import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

logger = logging.getLogger("marketsentry")


# ---------------------------------------------------------------------------
# Config constants
# ---------------------------------------------------------------------------

DEFAULT_HIGHLIGHT_PREFERENCES_PATH = Path(
    "config/portfolio_alert_highlight_preferences.json"
)
EXAMPLE_HIGHLIGHT_PREFERENCES_PATH = Path(
    "config/portfolio_alert_highlight_preferences.example.json"
)

ALLOWED_SEVERITIES = ("info", "warning", "high")
ALLOWED_SORT_ORDERS = (
    "severity_then_persistence",
    "persistence_then_severity",
    "newest_first",
    "property_then_severity",
)

# Keys that must not appear in the config file
FORBIDDEN_CONFIG_KEYS = (
    "live_retrieval",
    "scrape",
    "playwright",
    "selenium",
    "captcha",
    "notification",
    "email",
    "sms",
    "webhook",
    "walkability",
    "walk_score",
    "transit_score",
)

SEVERITY_ORDER = {"high": 3, "warning": 2, "info": 1}

EXAMPLE_HIGHLIGHT_PREFERENCES: Dict[str, Any] = {
    "profile_name": "default_focus",
    "description": (
        "Local display preferences for portfolio trend "
        "alert focus views."
    ),
    "include_severities": ["high", "warning"],
    "exclude_severities": ["info"],
    "include_alert_types": [
        "aggregate_burden_high",
        "aggregate_burden_increase",
        "property_degraded",
        "lifecycle_health_drop",
        "cross_site_confidence_drop",
        "churn_increase",
    ],
    "exclude_alert_types": [],
    "minimum_persistence_count": 1,
    "include_persistent_only": False,
    "include_property_alerts": True,
    "include_portfolio_alerts": True,
    "max_items": 25,
    "sort_order": "severity_then_persistence",
    "notes": (
        "Local display preferences only. "
        "No notifications are sent."
    ),
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PortfolioAlertHighlightPreferences(BaseModel):
    """Local display preferences for portfolio alert focus views.

    These preferences affect display/focus only. They do not change
    alert evaluation, history, candidate/watchlist/alert state,
    or trigger outbound notifications.
    """

    profile_name: str = "default_focus"
    description: str = ""
    include_severities: List[str] = Field(
        default_factory=lambda: ["high", "warning"]
    )
    exclude_severities: List[str] = Field(
        default_factory=lambda: ["info"]
    )
    include_alert_types: List[str] = Field(
        default_factory=list
    )
    exclude_alert_types: List[str] = Field(
        default_factory=list
    )
    minimum_persistence_count: int = 1
    include_persistent_only: bool = False
    include_property_alerts: bool = True
    include_portfolio_alerts: bool = True
    max_items: int = 25
    sort_order: str = "severity_then_persistence"
    notes: str = ""
    source_path: str = ""
    is_valid: bool = True
    errors: List[str] = Field(default_factory=list)


class PortfolioAlertFocusItem(BaseModel):
    """A single focused alert item for display.

    Each focus item represents an alert that has been
    selected for emphasis based on the highlight preferences.
    """

    focus_key: str = ""
    alert_key: str = ""
    alert_scope: str = ""
    property_id: str = ""
    candidate_id: str = ""
    address: str = ""
    severity: str = ""
    alert_type: str = ""
    persistence_count: int = 0
    run_count: int = 0
    latest_seen_at: str = ""
    trend_state: str = ""
    message: str = ""
    recommended_local_action: str = ""
    focus_reason: str = ""
    source: str = ""


class PortfolioAlertFocusSummary(BaseModel):
    """Summary of focused alert items."""

    profile_name: str = ""
    total_focus_items: int = 0
    high_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    portfolio_items: int = 0
    property_items: int = 0
    persistent_items: int = 0
    focus_reasons: List[str] = Field(default_factory=list)


class PortfolioAlertFocusDigest(BaseModel):
    """A complete focus digest for export."""

    items: List[PortfolioAlertFocusItem] = Field(
        default_factory=list
    )
    summary: PortfolioAlertFocusSummary = Field(
        default_factory=PortfolioAlertFocusSummary
    )
    preferences: Optional[PortfolioAlertHighlightPreferences] = None
    generated_at: str = ""
    export_paths: List[str] = Field(default_factory=list)


class PortfolioAlertFocusRunResult(BaseModel):
    """Result container for focus operations."""

    digest: Optional[PortfolioAlertFocusDigest] = None
    export_paths: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def load_portfolio_alert_highlight_preferences(
    config_path: Optional[Union[str, Path]] = None,
) -> PortfolioAlertHighlightPreferences:
    """Load highlight preferences from a JSON config file.

    If no config path is provided, returns safe default preferences.
    Invalid configs return a preferences object with is_valid=False
    and error messages.

    Args:
        config_path: Optional path to JSON config file.

    Returns:
        PortfolioAlertHighlightPreferences with loaded or default values.
    """
    if config_path is None:
        logger.info(
            "No highlight preferences config provided. "
            "Using safe defaults."
        )
        return _get_default_preferences()

    path = Path(config_path)
    if not path.is_file():
        logger.warning(
            f"Highlight preferences config not found: {path}"
        )
        prefs = _get_default_preferences()
        prefs.is_valid = False
        prefs.errors.append(f"Config file not found: {path}")
        return prefs

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(
            f"Invalid JSON in highlight preferences: {e}"
        )
        prefs = _get_default_preferences()
        prefs.is_valid = False
        prefs.errors.append(f"Invalid JSON: {e}")
        prefs.source_path = str(path)
        return prefs

    return _parse_preferences(data, str(path))


def validate_portfolio_alert_highlight_preferences(
    config_path: Union[str, Path],
) -> PortfolioAlertHighlightPreferences:
    """Validate a highlight preferences config file.

    Loads and validates the config, returning a preferences object
    with is_valid status and any error messages.

    Args:
        config_path: Path to JSON config file.

    Returns:
        PortfolioAlertHighlightPreferences with validation results.
    """
    return load_portfolio_alert_highlight_preferences(config_path)


def write_portfolio_alert_highlight_template(
    output_path: Optional[Union[str, Path]] = None,
    overwrite: bool = False,
) -> Tuple[str, bool]:
    """Write an example highlight preferences config file.

    Args:
        output_path: Output path. Defaults to example config path.
        overwrite: Whether to overwrite existing file.

    Returns:
        Tuple of (path_written, was_written).
    """
    if output_path is None:
        output_path = str(EXAMPLE_HIGHLIGHT_PREFERENCES_PATH)

    path = Path(output_path)
    if path.is_file() and not overwrite:
        logger.info(
            f"Template already exists at {path}. "
            f"Use overwrite=True to replace."
        )
        return str(path), False

    os.makedirs(path.parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            EXAMPLE_HIGHLIGHT_PREFERENCES,
            f,
            indent=2,
        )
        f.write("\n")

    logger.info(f"Wrote highlight preferences template to {path}")
    return str(path), True


def build_portfolio_alert_focus_items(
    prefs: Optional[PortfolioAlertHighlightPreferences] = None,
    db_path: Optional[str] = None,
    exports_dir: str = "data/exports",
) -> List[PortfolioAlertFocusItem]:
    """Build focused alert items based on highlight preferences.

    Reads from persisted alert history (M45) if database is
    available, falling back to latest trend alert digest CSV
    files (M43) if history is empty.

    Focus items are display-only. No database writes. No mutations.
    No outbound notifications.

    Args:
        prefs: Highlight preferences. None uses defaults.
        db_path: Optional path to SQLite database for history.
        exports_dir: Directory with export CSV files.

    Returns:
        List of PortfolioAlertFocusItem sorted per preferences.
    """
    if prefs is None:
        prefs = _get_default_preferences()

    items: List[PortfolioAlertFocusItem] = []

    # Try to load from alert history database first
    if db_path and os.path.isfile(db_path):
        items = _load_focus_items_from_history(db_path, prefs)

    # Fall back to latest trend alert digest CSV if no history items
    if not items:
        items = _load_focus_items_from_digest_csv(
            exports_dir, prefs
        )

    # Apply preference filters
    items = _apply_preference_filters(items, prefs)

    # Sort
    items = _sort_focus_items(items, prefs.sort_order)

    # Limit
    if prefs.max_items > 0 and len(items) > prefs.max_items:
        items = items[: prefs.max_items]

    return items


def summarize_portfolio_alert_focus(
    items: List[PortfolioAlertFocusItem],
    prefs: Optional[PortfolioAlertHighlightPreferences] = None,
) -> PortfolioAlertFocusSummary:
    """Summarize focused alert items.

    Args:
        items: List of focus items.
        prefs: Highlight preferences for profile name.

    Returns:
        PortfolioAlertFocusSummary with counts and reasons.
    """
    summary = PortfolioAlertFocusSummary()

    if prefs:
        summary.profile_name = prefs.profile_name

    summary.total_focus_items = len(items)
    summary.high_count = sum(
        1 for i in items if i.severity == "high"
    )
    summary.warning_count = sum(
        1 for i in items if i.severity == "warning"
    )
    summary.info_count = sum(
        1 for i in items if i.severity == "info"
    )
    summary.portfolio_items = sum(
        1 for i in items if i.alert_scope == "portfolio"
    )
    summary.property_items = sum(
        1 for i in items if i.alert_scope == "property"
    )
    summary.persistent_items = sum(
        1 for i in items if i.persistence_count > 1
    )

    # Collect unique focus reasons
    reasons = set()
    for i in items:
        if i.focus_reason:
            reasons.add(i.focus_reason)
    summary.focus_reasons = sorted(reasons)

    return summary


def export_portfolio_alert_focus_digest(
    prefs: Optional[PortfolioAlertHighlightPreferences] = None,
    db_path: Optional[str] = None,
    exports_dir: str = "data/exports",
    output_dir: Optional[str] = None,
    fmt: str = "both",
) -> PortfolioAlertFocusRunResult:
    """Export a focused alert digest as CSV and/or Markdown.

    Builds focus items, summarizes, and exports to the specified
    format. No database writes. No mutations. No notifications.

    Args:
        prefs: Highlight preferences. None uses defaults.
        db_path: Optional path to SQLite database.
        exports_dir: Directory with export files.
        output_dir: Output directory. Defaults to exports_dir.
        fmt: Export format: csv, md, or both.

    Returns:
        PortfolioAlertFocusRunResult with digest and paths.
    """
    if output_dir is None:
        output_dir = exports_dir

    if prefs is None:
        prefs = _get_default_preferences()

    result = PortfolioAlertFocusRunResult()

    items = build_portfolio_alert_focus_items(
        prefs=prefs,
        db_path=db_path,
        exports_dir=exports_dir,
    )

    summary = summarize_portfolio_alert_focus(items, prefs)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    digest = PortfolioAlertFocusDigest(
        items=items,
        summary=summary,
        preferences=prefs,
        generated_at=now,
    )

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: List[str] = []

    if fmt in ("csv", "both"):
        csv_path = os.path.join(
            output_dir,
            f"portfolio_alert_focus_digest_{ts}.csv",
        )
        _write_focus_csv(csv_path, items)
        paths.append(csv_path)

    if fmt in ("md", "both"):
        md_path = os.path.join(
            output_dir,
            f"portfolio_alert_focus_digest_{ts}.md",
        )
        _write_focus_md(md_path, items, summary, prefs)
        paths.append(md_path)

    digest.export_paths = paths
    result.digest = digest
    result.export_paths = paths

    if not items:
        result.warnings.append(
            "No focus items matched current preferences."
        )

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_default_preferences() -> PortfolioAlertHighlightPreferences:
    """Return safe default highlight preferences."""
    return PortfolioAlertHighlightPreferences(
        profile_name="default_focus",
        description=(
            "Local display preferences for portfolio trend "
            "alert focus views."
        ),
        include_severities=["high", "warning"],
        exclude_severities=["info"],
        include_alert_types=[],
        exclude_alert_types=[],
        minimum_persistence_count=1,
        include_persistent_only=False,
        include_property_alerts=True,
        include_portfolio_alerts=True,
        max_items=25,
        sort_order="severity_then_persistence",
        notes=(
            "Local display preferences only. "
            "No notifications are sent."
        ),
    )


def _parse_preferences(
    data: dict,
    source_path: str,
) -> PortfolioAlertHighlightPreferences:
    """Parse and validate preferences from a dict.

    Args:
        data: Parsed JSON data.
        source_path: Path the data was loaded from.

    Returns:
        PortfolioAlertHighlightPreferences with validation results.
    """
    prefs = PortfolioAlertHighlightPreferences()
    prefs.source_path = source_path
    errors: List[str] = []

    # Check for forbidden keys
    for key in data:
        key_lower = key.lower()
        for forbidden in FORBIDDEN_CONFIG_KEYS:
            if forbidden in key_lower:
                errors.append(
                    f"Forbidden key in config: '{key}' "
                    f"(contains '{forbidden}')"
                )

    # profile_name required
    if "profile_name" not in data or not data["profile_name"]:
        errors.append("profile_name is required")
    else:
        prefs.profile_name = str(data["profile_name"])

    # description
    if "description" in data:
        prefs.description = str(data["description"])

    # include_severities
    if "include_severities" in data:
        inc_sev = data["include_severities"]
        if not isinstance(inc_sev, list):
            errors.append("include_severities must be a list")
        else:
            for s in inc_sev:
                if s not in ALLOWED_SEVERITIES:
                    errors.append(
                        f"Invalid severity in include_severities: "
                        f"'{s}'. Allowed: {ALLOWED_SEVERITIES}"
                    )
            prefs.include_severities = inc_sev

    # exclude_severities
    if "exclude_severities" in data:
        exc_sev = data["exclude_severities"]
        if not isinstance(exc_sev, list):
            errors.append("exclude_severities must be a list")
        else:
            for s in exc_sev:
                if s not in ALLOWED_SEVERITIES:
                    errors.append(
                        f"Invalid severity in exclude_severities: "
                        f"'{s}'. Allowed: {ALLOWED_SEVERITIES}"
                    )
            prefs.exclude_severities = exc_sev

    # include_alert_types
    if "include_alert_types" in data:
        inc_types = data["include_alert_types"]
        if not isinstance(inc_types, list):
            errors.append("include_alert_types must be a list")
        else:
            prefs.include_alert_types = [
                str(t) for t in inc_types
            ]

    # exclude_alert_types
    if "exclude_alert_types" in data:
        exc_types = data["exclude_alert_types"]
        if not isinstance(exc_types, list):
            errors.append("exclude_alert_types must be a list")
        else:
            prefs.exclude_alert_types = [
                str(t) for t in exc_types
            ]

    # minimum_persistence_count
    if "minimum_persistence_count" in data:
        mpc = data["minimum_persistence_count"]
        if not isinstance(mpc, int) or mpc < 0:
            errors.append(
                "minimum_persistence_count must be a "
                "non-negative integer"
            )
        else:
            prefs.minimum_persistence_count = mpc

    # include_persistent_only
    if "include_persistent_only" in data:
        ipo = data["include_persistent_only"]
        if not isinstance(ipo, bool):
            errors.append(
                "include_persistent_only must be a boolean"
            )
        else:
            prefs.include_persistent_only = ipo

    # include_property_alerts
    if "include_property_alerts" in data:
        ipa = data["include_property_alerts"]
        if not isinstance(ipa, bool):
            errors.append(
                "include_property_alerts must be a boolean"
            )
        else:
            prefs.include_property_alerts = ipa

    # include_portfolio_alerts
    if "include_portfolio_alerts" in data:
        ipoa = data["include_portfolio_alerts"]
        if not isinstance(ipoa, bool):
            errors.append(
                "include_portfolio_alerts must be a boolean"
            )
        else:
            prefs.include_portfolio_alerts = ipoa

    # max_items
    if "max_items" in data:
        mi = data["max_items"]
        if not isinstance(mi, int) or mi < 1:
            errors.append(
                "max_items must be a positive integer"
            )
        else:
            prefs.max_items = mi

    # sort_order
    if "sort_order" in data:
        so = data["sort_order"]
        if so not in ALLOWED_SORT_ORDERS:
            errors.append(
                f"Invalid sort_order: '{so}'. "
                f"Allowed: {ALLOWED_SORT_ORDERS}"
            )
        else:
            prefs.sort_order = so

    # notes
    if "notes" in data:
        prefs.notes = str(data["notes"])

    if errors:
        prefs.is_valid = False
        prefs.errors = errors
    else:
        prefs.is_valid = True

    return prefs


def _load_focus_items_from_history(
    db_path: str,
    prefs: PortfolioAlertHighlightPreferences,
) -> List[PortfolioAlertFocusItem]:
    """Load focus items from persisted alert history (M45).

    Reads the alert history tables to build focus items with
    persistence counts, trend states, and focus reasons.

    Args:
        db_path: Path to SQLite database.
        prefs: Highlight preferences.

    Returns:
        List of PortfolioAlertFocusItem from history.
    """
    import sqlite3

    items: List[PortfolioAlertFocusItem] = []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if history tables exist
        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND "
            "name='portfolio_trend_alert_history'"
        )
        if not cursor.fetchone():
            conn.close()
            return items

        # Get latest run ID
        cursor.execute(
            "SELECT MAX(run_id) as max_id "
            "FROM portfolio_trend_alert_runs"
        )
        max_row = cursor.fetchone()
        if not max_row or max_row["max_id"] is None:
            conn.close()
            return items

        latest_run_id = max_row["max_id"]

        # Get alert history grouped by alert_key with persistence
        cursor.execute(
            """SELECT
                h.alert_key,
                h.alert_scope,
                h.property_id,
                h.candidate_id,
                h.address,
                h.severity,
                h.alert_type,
                h.rule_id,
                h.metric_name,
                h.message,
                h.recommended_local_action,
                COUNT(DISTINCT h.run_id) as persistence_count,
                MAX(h.generated_at) as latest_seen_at,
                MAX(h.run_id) as max_run_id
            FROM portfolio_trend_alert_history h
            GROUP BY h.alert_key
            ORDER BY persistence_count DESC, h.severity DESC""",
        )

        rows = cursor.fetchall()

        # Also get comparison info if previous run exists
        comparison_map: Dict[str, str] = {}
        cursor.execute(
            "SELECT run_id FROM portfolio_trend_alert_runs "
            "WHERE run_id < ? "
            "ORDER BY run_id DESC LIMIT 1",
            (latest_run_id,),
        )
        prev_row = cursor.fetchone()
        if prev_row:
            prev_run_id = prev_row["run_id"]
            # Get alert keys from current run
            cursor.execute(
                "SELECT DISTINCT alert_key FROM "
                "portfolio_trend_alert_history "
                "WHERE run_id = ?",
                (latest_run_id,),
            )
            current_keys = {
                r["alert_key"] for r in cursor.fetchall()
            }
            # Get alert keys from previous run
            cursor.execute(
                "SELECT DISTINCT alert_key FROM "
                "portfolio_trend_alert_history "
                "WHERE run_id = ?",
                (prev_run_id,),
            )
            prev_keys = {
                r["alert_key"] for r in cursor.fetchall()
            }

            for key in current_keys | prev_keys:
                if key in current_keys and key not in prev_keys:
                    comparison_map[key] = "new"
                elif key in prev_keys and key not in current_keys:
                    comparison_map[key] = "disappeared"
                else:
                    comparison_map[key] = "persistent"

        # Get total run count for run_count field
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM "
            "portfolio_trend_alert_runs"
        )
        total_runs = cursor.fetchone()["cnt"]

        conn.close()

        for row in rows:
            focus_reason = _determine_focus_reason(
                severity=row["severity"],
                alert_type=row["alert_type"] or "",
                persistence_count=row["persistence_count"],
                trend_state=comparison_map.get(
                    row["alert_key"], ""
                ),
            )

            focus_key = hashlib.sha256(
                f"focus_{row['alert_key']}".encode("utf-8")
            ).hexdigest()[:16]

            item = PortfolioAlertFocusItem(
                focus_key=focus_key,
                alert_key=row["alert_key"] or "",
                alert_scope=row["alert_scope"] or "",
                property_id=str(row["property_id"] or ""),
                candidate_id=str(row["candidate_id"] or ""),
                address=row["address"] or "",
                severity=row["severity"] or "",
                alert_type=row["alert_type"] or "",
                persistence_count=row["persistence_count"],
                run_count=total_runs,
                latest_seen_at=row["latest_seen_at"] or "",
                trend_state=comparison_map.get(
                    row["alert_key"], "unchanged"
                ),
                message=row["message"] or "",
                recommended_local_action=(
                    row["recommended_local_action"] or ""
                ),
                focus_reason=focus_reason,
                source="alert_history",
            )
            items.append(item)

    except Exception as e:
        logger.warning(
            f"Could not load focus items from history: {e}"
        )

    return items


def _load_focus_items_from_digest_csv(
    exports_dir: str,
    prefs: PortfolioAlertHighlightPreferences,
) -> List[PortfolioAlertFocusItem]:
    """Load focus items from latest trend alert digest CSV (M43).

    Fallback when no alert history database is available.

    Args:
        exports_dir: Directory with export CSV files.
        prefs: Highlight preferences.

    Returns:
        List of PortfolioAlertFocusItem from CSV digest.
    """
    items: List[PortfolioAlertFocusItem] = []

    exports_path = Path(exports_dir)
    if not exports_path.is_dir():
        return items

    # Find latest trend alert digest CSV
    csv_files = sorted(
        [
            f for f in exports_path.iterdir()
            if f.name.startswith(
                "portfolio_trend_alert_digest_"
            )
            and f.name.endswith(".csv")
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not csv_files:
        return items

    latest_csv = csv_files[0]
    try:
        with open(latest_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                alert_type = row.get("alert_type", "")
                severity = row.get("severity", "info")

                focus_reason = _determine_focus_reason(
                    severity=severity,
                    alert_type=alert_type,
                    persistence_count=0,
                    trend_state="",
                )

                raw_key = (
                    f"{row.get('alert_scope', '')}"
                    f"|{row.get('property_id', '')}"
                    f"|{alert_type}"
                    f"|{row.get('alert_id', '')}"
                    f"|{row.get('metric_name', '')}"
                )
                alert_key = hashlib.sha256(
                    raw_key.encode("utf-8")
                ).hexdigest()[:16]

                focus_key = hashlib.sha256(
                    f"focus_{alert_key}".encode("utf-8")
                ).hexdigest()[:16]

                item = PortfolioAlertFocusItem(
                    focus_key=focus_key,
                    alert_key=alert_key,
                    alert_scope=row.get("alert_scope", ""),
                    property_id=row.get("property_id", ""),
                    candidate_id=row.get("candidate_id", ""),
                    address=row.get("address", ""),
                    severity=severity,
                    alert_type=alert_type,
                    persistence_count=0,
                    run_count=0,
                    latest_seen_at=row.get(
                        "generated_at", ""
                    ),
                    trend_state="",
                    message=row.get("message", ""),
                    recommended_local_action=row.get(
                        "recommended_local_action", ""
                    ),
                    focus_reason=focus_reason,
                    source="digest_csv",
                )
                items.append(item)

    except Exception as e:
        logger.warning(
            f"Could not load focus items from digest CSV: {e}"
        )

    return items


def _determine_focus_reason(
    severity: str,
    alert_type: str,
    persistence_count: int,
    trend_state: str,
) -> str:
    """Determine the focus reason for an alert item.

    Args:
        severity: Alert severity level.
        alert_type: Alert type string.
        persistence_count: Number of runs alert appeared in.
        trend_state: Trend state from comparison.

    Returns:
        Human-readable focus reason string.
    """
    if severity == "high":
        return "high severity"

    if persistence_count > 1:
        return "persistent across runs"

    alert_lower = alert_type.lower()

    if "aggregate_burden" in alert_lower:
        return "aggregate burden alert"

    if "lifecycle_health" in alert_lower or "health" in alert_lower:
        return "lifecycle degradation"

    if "cross_site_confidence" in alert_lower:
        return "cross-site confidence decrease"

    if "churn" in alert_lower:
        return "Churn Index increase"

    if "property" in alert_lower or "degraded" in alert_lower:
        return "recurring property alert"

    if trend_state == "worsened":
        return "alert severity increased"

    if severity == "warning":
        return "warning severity"

    return "included by preference filter"


def _apply_preference_filters(
    items: List[PortfolioAlertFocusItem],
    prefs: PortfolioAlertHighlightPreferences,
) -> List[PortfolioAlertFocusItem]:
    """Apply preference filters to focus items.

    Args:
        items: Unfiltered focus items.
        prefs: Highlight preferences.

    Returns:
        Filtered list of focus items.
    """
    filtered: List[PortfolioAlertFocusItem] = []

    for item in items:
        # Severity filter: include
        if prefs.include_severities:
            if item.severity not in prefs.include_severities:
                continue

        # Severity filter: exclude
        if prefs.exclude_severities:
            if item.severity in prefs.exclude_severities:
                continue

        # Alert type filter: include (if specified)
        if prefs.include_alert_types:
            if item.alert_type not in prefs.include_alert_types:
                continue

        # Alert type filter: exclude
        if prefs.exclude_alert_types:
            if item.alert_type in prefs.exclude_alert_types:
                continue

        # Scope filter
        if item.alert_scope == "property":
            if not prefs.include_property_alerts:
                continue
        elif item.alert_scope == "portfolio":
            if not prefs.include_portfolio_alerts:
                continue

        # Persistence filter
        if prefs.include_persistent_only:
            if item.persistence_count < 2:
                continue

        # Minimum persistence count
        if prefs.minimum_persistence_count > 0:
            if item.persistence_count < prefs.minimum_persistence_count:
                # Only apply persistence filter for history-sourced
                # items (digest CSV items have persistence_count=0)
                if item.source == "alert_history":
                    continue

        filtered.append(item)

    return filtered


def _sort_focus_items(
    items: List[PortfolioAlertFocusItem],
    sort_order: str,
) -> List[PortfolioAlertFocusItem]:
    """Sort focus items by the specified order.

    Args:
        items: Focus items to sort.
        sort_order: Sort order string.

    Returns:
        Sorted list of focus items.
    """
    if sort_order == "severity_then_persistence":
        return sorted(
            items,
            key=lambda x: (
                -SEVERITY_ORDER.get(x.severity, 0),
                -x.persistence_count,
            ),
        )
    elif sort_order == "persistence_then_severity":
        return sorted(
            items,
            key=lambda x: (
                -x.persistence_count,
                -SEVERITY_ORDER.get(x.severity, 0),
            ),
        )
    elif sort_order == "newest_first":
        return sorted(
            items,
            key=lambda x: x.latest_seen_at or "",
            reverse=True,
        )
    elif sort_order == "property_then_severity":
        return sorted(
            items,
            key=lambda x: (
                x.address or "",
                -SEVERITY_ORDER.get(x.severity, 0),
            ),
        )
    else:
        return sorted(
            items,
            key=lambda x: (
                -SEVERITY_ORDER.get(x.severity, 0),
                -x.persistence_count,
            ),
        )


# ---------------------------------------------------------------------------
# Export writers
# ---------------------------------------------------------------------------

FOCUS_CSV_FIELDNAMES = [
    "focus_key",
    "alert_key",
    "alert_scope",
    "property_id",
    "candidate_id",
    "address",
    "severity",
    "alert_type",
    "persistence_count",
    "run_count",
    "latest_seen_at",
    "trend_state",
    "message",
    "recommended_local_action",
    "focus_reason",
    "source",
]


def _write_focus_csv(
    path: str,
    items: List[PortfolioAlertFocusItem],
) -> None:
    """Write focus digest to CSV.

    Args:
        path: Output file path.
        items: Focus items to write.
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=FOCUS_CSV_FIELDNAMES
        )
        writer.writeheader()
        for item in items:
            writer.writerow({
                "focus_key": item.focus_key,
                "alert_key": item.alert_key,
                "alert_scope": item.alert_scope,
                "property_id": item.property_id,
                "candidate_id": item.candidate_id,
                "address": item.address,
                "severity": item.severity,
                "alert_type": item.alert_type,
                "persistence_count": item.persistence_count,
                "run_count": item.run_count,
                "latest_seen_at": item.latest_seen_at,
                "trend_state": item.trend_state,
                "message": item.message,
                "recommended_local_action": (
                    item.recommended_local_action
                ),
                "focus_reason": item.focus_reason,
                "source": item.source,
            })


def _write_focus_md(
    path: str,
    items: List[PortfolioAlertFocusItem],
    summary: PortfolioAlertFocusSummary,
    prefs: PortfolioAlertHighlightPreferences,
) -> None:
    """Write focus digest to Markdown.

    Args:
        path: Output file path.
        items: Focus items to write.
        summary: Focus summary.
        prefs: Highlight preferences used.
    """
    lines: List[str] = []
    lines.append("# Portfolio Alert Focus Digest")
    lines.append("")
    lines.append(
        f"Generated: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    lines.append(f"Profile: {prefs.profile_name}")
    lines.append(f"Total focus items: {summary.total_focus_items}")
    lines.append("")
    lines.append(
        "*This report is a local analytical review aid. "
        "It does not make purchase recommendations, infer "
        "seller intent, or mutate candidate/watchlist/alert "
        "state. No outbound notifications are sent.*"
    )
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- High: {summary.high_count}")
    lines.append(f"- Warning: {summary.warning_count}")
    lines.append(f"- Info: {summary.info_count}")
    lines.append(f"- Portfolio items: {summary.portfolio_items}")
    lines.append(f"- Property items: {summary.property_items}")
    lines.append(
        f"- Persistent items: {summary.persistent_items}"
    )
    lines.append("")

    if items:
        lines.append("## Focus Items")
        lines.append("")
        lines.append(
            "| Severity | Address | Type "
            "| Persistence | Trend | Reason |"
        )
        lines.append(
            "| --- | --- | --- | --- | --- | --- |"
        )
        for item in items:
            addr = item.address[:30] if item.address else ""
            lines.append(
                f"| {item.severity}"
                f" | {addr}"
                f" | {item.alert_type[:25]}"
                f" | {item.persistence_count}"
                f" | {item.trend_state or 'N/A'}"
                f" | {item.focus_reason[:30]} |"
            )
        lines.append("")
    else:
        lines.append(
            "No focus items matched the current preferences."
        )
        lines.append("")

    lines.append(
        "*No outbound notifications sent. "
        "No candidate/watchlist/alert state modified.*"
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
