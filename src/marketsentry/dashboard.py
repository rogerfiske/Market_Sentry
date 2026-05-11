"""Dashboard data loading and preparation for Market_Sentry.

Provides functions to load data from the local SQLite database,
CSV reports, report manifest, and workflow summaries for display
in the local dashboard/report viewer.

No live network calls. Reads local files only.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from marketsentry.config import config
from marketsentry.database import column_exists, execute_query, get_table_count, table_exists
from marketsentry.logging_config import logger


# ---------------------------------------------------------------------------
# Dashboard models
# ---------------------------------------------------------------------------


class ReportManifestRow(BaseModel):
    """A single row from report_manifest.csv."""

    created_at: str = ""
    workflow_name: str = ""
    report_type: str = ""
    file_path: str = ""
    row_count: str = ""
    notes: str = ""


class DashboardSummary(BaseModel):
    """Summary counts for the dashboard overview."""

    database_path: str = ""
    database_exists: bool = False
    candidates_total: int = 0
    watched_total: int = 0
    watched_active: int = 0
    snapshots_total: int = 0
    cross_site_observations: int = 0
    county_records: int = 0
    listing_events: int = 0
    reports_in_manifest: int = 0
    high_priority_watched: int = 0
    quiet_gatekeeper_failures: int = 0
    strong_review_candidates: int = 0
    county_reset_applied_count: int = 0
    high_churn_count: int = 0


class DashboardTableSpec(BaseModel):
    """Specification for a dashboard data table."""

    title: str = ""
    description: str = ""
    columns: List[str] = Field(default_factory=list)
    row_count: int = 0


class DashboardData(BaseModel):
    """All data needed for the dashboard."""

    summary: DashboardSummary = Field(default_factory=DashboardSummary)
    candidates: Optional[pd.DataFrame] = None
    watched: Optional[pd.DataFrame] = None
    monitoring: Optional[pd.DataFrame] = None
    effective_dom_v2: Optional[pd.DataFrame] = None
    county_verification: Optional[pd.DataFrame] = None
    cross_site: Optional[pd.DataFrame] = None
    manifest: List[ReportManifestRow] = Field(default_factory=list)
    workflow_summaries: List[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)


# ---------------------------------------------------------------------------
# Summary loading
# ---------------------------------------------------------------------------


def get_dashboard_summary(
    db_path: Optional[Union[Path, str]] = None,
) -> DashboardSummary:
    """Build a summary of current database state for the dashboard overview.

    Args:
        db_path: Path to SQLite database (default: from config).

    Returns:
        DashboardSummary with counts for each table and metric.
    """
    database = str(db_path) if db_path else config.database_path
    summary = DashboardSummary(
        database_path=database,
        database_exists=Path(database).exists(),
    )

    if not summary.database_exists:
        return summary

    # Table counts
    table_map = {
        "candidate_review_queue": "candidates_total",
        "watched_properties": "watched_total",
        "property_observation_snapshots": "snapshots_total",
        "cross_site_observations": "cross_site_observations",
        "county_record_observations": "county_records",
        "listing_events": "listing_events",
    }

    for table_name, attr in table_map.items():
        if table_exists(table_name, database):
            setattr(summary, attr, get_table_count(table_name, database))

    # Active watched
    if table_exists("watched_properties", database):
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM watched_properties WHERE active_watch_status = 1",
            database_path=database,
        )
        summary.watched_active = rows[0]["cnt"] if rows else 0

        # High priority (watch_priority = 1)
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM watched_properties WHERE watch_priority = 1",
            database_path=database,
        )
        summary.high_priority_watched = rows[0]["cnt"] if rows else 0

        # County reset applied (v2 column, may not exist)
        if column_exists("watched_properties", "county_reset_applied", database):
            rows = execute_query(
                "SELECT COUNT(*) AS cnt FROM watched_properties WHERE county_reset_applied = 1",
                database_path=database,
            )
            summary.county_reset_applied_count = rows[0]["cnt"] if rows else 0

        # High churn (>= 6.0, v2 column)
        if column_exists("watched_properties", "recent_churn_index", database):
            rows = execute_query(
                "SELECT COUNT(*) AS cnt FROM watched_properties WHERE recent_churn_index >= 6.0",
                database_path=database,
            )
            summary.high_churn_count = rows[0]["cnt"] if rows else 0

    # Candidate metrics
    if table_exists("candidate_review_queue", database):
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM candidate_review_queue "
            "WHERE quiet_gatekeeper_result = 'fail_noise_risk'",
            database_path=database,
        )
        summary.quiet_gatekeeper_failures = rows[0]["cnt"] if rows else 0

        # Approximate strong review candidates (overall score not in DB, use review_status)
        # We check for candidates that would score well - high quiet + gas + low vibrancy
        rows = execute_query(
            "SELECT COUNT(*) AS cnt FROM candidate_review_queue "
            "WHERE quiet_score >= 8.0 AND (vibrancy_score IS NULL OR vibrancy_score <= 2.5)",
            database_path=database,
        )
        summary.strong_review_candidates = rows[0]["cnt"] if rows else 0

    # Report manifest count
    manifest = load_latest_report_manifest()
    summary.reports_in_manifest = len(manifest)

    return summary


# ---------------------------------------------------------------------------
# Report manifest
# ---------------------------------------------------------------------------


def load_latest_report_manifest(
    exports_dir: Optional[Union[Path, str]] = None,
) -> List[ReportManifestRow]:
    """Load the report manifest CSV.

    Args:
        exports_dir: Directory containing report_manifest.csv.

    Returns:
        List of ReportManifestRow entries.
    """
    out_dir = Path(exports_dir) if exports_dir else Path(config.data_exports_dir)
    manifest_path = out_dir / "report_manifest.csv"

    if not manifest_path.exists():
        return []

    rows: List[ReportManifestRow] = []
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(ReportManifestRow(
                    created_at=row.get("created_at", ""),
                    workflow_name=row.get("workflow_name", ""),
                    report_type=row.get("report_type", ""),
                    file_path=row.get("file_path", ""),
                    row_count=row.get("row_count", ""),
                    notes=row.get("notes", ""),
                ))
    except Exception as e:
        logger.warning(f"Could not load report manifest: {e}")

    return rows


# ---------------------------------------------------------------------------
# Report discovery
# ---------------------------------------------------------------------------


def find_latest_report(
    report_type: str,
    exports_dir: Optional[Union[Path, str]] = None,
) -> Optional[Path]:
    """Find the latest report file of a given type.

    Searches by filename pattern in the exports directory.

    Args:
        report_type: Type of report (candidate_review, candidate_analysis,
            watchlist_monitoring, effective_dom_v2, county_verification,
            cross_site_report, workflow_summary).
        exports_dir: Directory to search.

    Returns:
        Path to the latest report file, or None if not found.
    """
    out_dir = Path(exports_dir) if exports_dir else Path(config.data_exports_dir)

    if not out_dir.exists():
        return None

    pattern_map = {
        "candidate_review": "candidate_review_*.csv",
        "candidate_analysis": "candidate_analysis_*.csv",
        "watchlist_monitoring": "watchlist_monitoring_*.csv",
        "effective_dom_v2": "effective_dom_v2_*.csv",
        "county_verification": "county_verification_*.csv",
        "cross_site_report": "cross_site_report_*.csv",
        "cross_site_analytics": "cross_site_analytics_*.csv",
        "cross_site_trends": "cross_site_trends_*.csv",
        "cross_site_trend_alerts": "cross_site_trend_alerts_*.csv",
        "cross_site_alert_analytics": "cross_site_alert_analytics_*.csv",
        "cross_site_alert_triage": "cross_site_alert_triage_*.csv",
        "cross_site_alert_hygiene": "cross_site_alert_hygiene_*.csv",
        "cross_site_alert_archive_candidates": "cross_site_alert_archive_candidates_*.csv",
        "cross_site_alert_expiration_approval": "cross_site_alert_expiration_approval_*.csv",
        "workflow_summary": "workflow_summary_*.md",
    }

    # Also check demo prefixed reports
    demo_pattern_map = {
        "candidate_review": "demo_candidate_review_*.csv",
        "candidate_analysis": "demo_candidate_analysis_*.csv",
        "watchlist_monitoring": "demo_watchlist_monitoring_*.csv",
        "effective_dom_v2": "demo_effective_dom_v2_*.csv",
        "county_verification": "demo_county_verification_*.csv",
    }

    pattern = pattern_map.get(report_type)
    if not pattern:
        return None

    files = sorted(out_dir.glob(pattern), key=_file_mtime, reverse=True)

    # Also check demo prefix
    demo_pattern = demo_pattern_map.get(report_type)
    if demo_pattern:
        demo_files = sorted(out_dir.glob(demo_pattern), key=_file_mtime, reverse=True)
        files.extend(demo_files)

    if not files:
        return None

    # Return most recently modified
    files.sort(key=_file_mtime, reverse=True)
    return files[0]


def _file_mtime(path: Path) -> float:
    """Get file modification time, returning 0 on error."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def find_workflow_summaries(
    exports_dir: Optional[Union[Path, str]] = None,
) -> List[Path]:
    """Find all workflow summary markdown files.

    Args:
        exports_dir: Directory to search.

    Returns:
        List of Path objects sorted by modification time (newest first).
    """
    out_dir = Path(exports_dir) if exports_dir else Path(config.data_exports_dir)

    if not out_dir.exists():
        return []

    files = sorted(out_dir.glob("workflow_summary_*.md"), key=_file_mtime, reverse=True)
    return files


# ---------------------------------------------------------------------------
# CSV report loading
# ---------------------------------------------------------------------------


def load_report_csv(report_path: Path) -> pd.DataFrame:
    """Load a CSV report into a pandas DataFrame.

    Args:
        report_path: Path to the CSV file.

    Returns:
        DataFrame with the report data, or empty DataFrame on error.
    """
    try:
        return pd.read_csv(report_path, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not load report CSV {report_path}: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Table builders - prepare DataFrames for dashboard display
# ---------------------------------------------------------------------------


def build_candidate_table(
    db_path: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build candidate review table from database.

    Args:
        db_path: Path to database.

    Returns:
        DataFrame with candidate review data.
    """
    database = str(db_path) if db_path else config.database_path

    if not Path(database).exists() or not table_exists("candidate_review_queue", database):
        return pd.DataFrame()

    base_cols = [
        "candidate_id", "address", "city", "zip", "price",
        "quiet_score", "vibrancy_score", "quiet_gatekeeper_result",
        "garage_spaces", "gas_service", "displayed_dom",
        "user_decision", "redfin_url", "effective_dom_estimate", "review_status",
    ]
    v2_cols = [
        "effective_dom_v1", "effective_dom_v2",
        "effective_dom_delta_v2", "recent_churn_index", "county_reset_applied",
    ]
    cols = list(base_cols)
    for col in v2_cols:
        if column_exists("candidate_review_queue", col, database):
            cols.append(col)

    select_clause = ", ".join(cols)
    rows = execute_query(
        f"SELECT {select_clause} FROM candidate_review_queue ORDER BY candidate_id",
        database_path=database,
    )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame([dict(row) for row in rows])


def build_watchlist_table(
    db_path: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build watchlist table from database.

    Args:
        db_path: Path to database.

    Returns:
        DataFrame with watched property data.
    """
    database = str(db_path) if db_path else config.database_path

    if not Path(database).exists() or not table_exists("watched_properties", database):
        return pd.DataFrame()

    base_cols = [
        "property_id", "watch_priority", "active_watch_status",
        "address", "city", "zip", "current_price",
        "quiet_score", "vibrancy_score", "gas_service", "garage_spaces",
        "last_checked_date", "user_notes", "redfin_url",
    ]
    v2_cols = [
        "effective_dom_v1", "effective_dom_v2", "recent_churn_index",
        "county_reset_applied",
    ]
    cols = list(base_cols)
    for col in v2_cols:
        if column_exists("watched_properties", col, database):
            cols.append(col)

    select_clause = ", ".join(cols)
    rows = execute_query(
        f"SELECT {select_clause} FROM watched_properties ORDER BY watch_priority, property_id",
        database_path=database,
    )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame([dict(row) for row in rows])


def build_monitoring_table(
    exports_dir: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build monitoring table from latest monitoring report CSV.

    Args:
        exports_dir: Directory containing reports.

    Returns:
        DataFrame with monitoring data, or empty DataFrame.
    """
    report_path = find_latest_report("watchlist_monitoring", exports_dir)
    if not report_path:
        return pd.DataFrame()

    df = load_report_csv(report_path)
    if df.empty:
        return df

    # Select key columns if available
    desired = [
        "property_id", "address", "current_price", "previous_price",
        "price_change", "listing_status", "previous_listing_status",
        "effective_dom_v2", "previous_effective_dom_v2",
        "effective_dom_v2_change", "recent_churn_index",
        "recent_churn_index_change", "change_summary",
        "warning_flags", "positive_flags",
    ]
    available = [c for c in desired if c in df.columns]
    if available:
        return df[available]
    return df


def build_effective_dom_v2_table(
    exports_dir: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build Effective DOM v2 comparison table from latest report.

    Args:
        exports_dir: Directory containing reports.

    Returns:
        DataFrame with v2 comparison data, or empty DataFrame.
    """
    report_path = find_latest_report("effective_dom_v2", exports_dir)
    if not report_path:
        return pd.DataFrame()

    df = load_report_csv(report_path)
    if df.empty:
        return df

    desired = [
        "property_id", "address", "city",
        "effective_dom_v1", "effective_dom_v2",
        "effective_dom_delta_v1", "effective_dom_delta_v2",
        "county_reset_applied", "county_reset_date",
        "county_reset_record_type", "county_reset_confidence",
        "recent_churn_index", "churn_preserved_after_transfer",
        "pre_reset_calendar_exposure_dom", "post_reset_calendar_exposure_dom",
    ]
    available = [c for c in desired if c in df.columns]
    if available:
        return df[available]
    return df


def build_county_verification_table(
    exports_dir: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build county verification table from latest report.

    Args:
        exports_dir: Directory containing reports.

    Returns:
        DataFrame with county verification data, or empty DataFrame.
    """
    report_path = find_latest_report("county_verification", exports_dir)
    if not report_path:
        return pd.DataFrame()

    df = load_report_csv(report_path)
    if df.empty:
        return df

    desired = [
        "property_id", "address", "city",
        "county_records_seen", "county_transfer_found",
        "county_reset_supported", "county_transfer_date",
        "county_transfer_record_type", "recent_churn_index",
        "churn_preserved_after_transfer",
    ]
    available = [c for c in desired if c in df.columns]
    if available:
        return df[available]
    return df


def build_cross_site_table(
    exports_dir: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build cross-site comparison table from latest report.

    Args:
        exports_dir: Directory containing reports.

    Returns:
        DataFrame with cross-site data, or empty DataFrame.
    """
    report_path = find_latest_report("cross_site_report", exports_dir)
    if not report_path:
        return pd.DataFrame()

    df = load_report_csv(report_path)
    if df.empty:
        return df

    desired = [
        "property_id", "address", "city",
        "has_price_discrepancy", "has_status_discrepancy",
        "has_dom_discrepancy",
        "redfin_price", "zillow_price", "realtor_price",
        "homes_price", "compass_price",
    ]
    available = [c for c in desired if c in df.columns]
    if available:
        return df[available]
    return df


def build_cross_site_analytics_table(
    exports_dir: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build cross-site analytics table from latest analytics report.

    Args:
        exports_dir: Directory containing reports.

    Returns:
        DataFrame with analytics data, or empty DataFrame.
    """
    report_path = find_latest_report("cross_site_analytics", exports_dir)
    if not report_path:
        return pd.DataFrame()

    df = load_report_csv(report_path)
    if df.empty:
        return df

    desired = [
        "property_id", "address", "city",
        "overall_cross_site_confidence_score",
        "discrepancy_severity_label",
        "cross_site_manual_review_priority",
        "contributing_sources",
        "low_confidence_sources",
        "stale_sources",
        "parse_warning_sources",
    ]
    available = [c for c in desired if c in df.columns]
    if available:
        return df[available]
    return df


def build_cross_site_trends_table(
    exports_dir: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build cross-site trends table from latest trend report.

    Args:
        exports_dir: Directory containing reports.

    Returns:
        DataFrame with trend data, or empty DataFrame.
    """
    report_path = find_latest_report("cross_site_trends", exports_dir)
    if not report_path:
        return pd.DataFrame()

    df = load_report_csv(report_path)
    if df.empty:
        return df

    desired = [
        "property_id", "address", "city",
        "current_overall_cross_site_confidence_score",
        "overall_cross_site_confidence_change",
        "current_discrepancy_severity_label",
        "discrepancy_severity_changed",
        "current_manual_review_priority",
        "manual_review_priority_changed",
        "price_agreement_change",
        "status_agreement_change",
        "dom_agreement_change",
        "current_low_confidence_sources",
        "current_stale_sources",
        "trend_direction",
        "trend_summary",
        "recommended_next_action",
    ]
    available = [c for c in desired if c in df.columns]
    if available:
        return df[available]
    return df


def build_cross_site_trend_alerts_table(
    exports_dir: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build cross-site trend alerts table from latest alerts report.

    Args:
        exports_dir: Directory containing reports.

    Returns:
        DataFrame with trend alert data, or empty DataFrame.
    """
    report_path = find_latest_report("cross_site_trend_alerts", exports_dir)
    if not report_path:
        return pd.DataFrame()

    df = load_report_csv(report_path)
    if df.empty:
        return df

    desired = [
        "alert_id", "property_id", "address", "city",
        "alert_type", "severity", "alert_status",
        "trend_direction", "current_value", "previous_value",
        "delta_value", "message", "recommended_action",
        "created_at",
    ]
    available = [c for c in desired if c in df.columns]
    if available:
        return df[available]
    return df


def build_cross_site_alert_analytics_table(
    exports_dir: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build cross-site alert analytics table from latest analytics report.

    Args:
        exports_dir: Directory containing reports.

    Returns:
        DataFrame with alert analytics data, or empty DataFrame.
    """
    report_path = find_latest_report("cross_site_alert_analytics", exports_dir)
    if not report_path:
        return pd.DataFrame()

    df = load_report_csv(report_path)
    if df.empty:
        return df

    desired = [
        "property_id", "address", "city",
        "total_alert_count", "open_alert_count",
        "high_or_critical_open_alert_count",
        "oldest_open_alert_age_days",
        "most_common_alert_type",
        "repeated_patterns",
        "alert_burden_score", "alert_burden_label",
        "recommended_review_action",
    ]
    available = [c for c in desired if c in df.columns]
    if available:
        return df[available]
    return df


def build_cross_site_alert_triage_table(
    exports_dir: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build cross-site alert triage table from latest triage CSV.

    Args:
        exports_dir: Directory containing reports.

    Returns:
        DataFrame with triage data, or empty DataFrame.
    """
    report_path = find_latest_report("cross_site_alert_triage", exports_dir)
    if not report_path:
        return pd.DataFrame()

    df = load_report_csv(report_path)
    if df.empty:
        return df

    desired = [
        "alert_id", "property_id", "address", "city",
        "alert_type", "severity", "current_status",
        "alert_age_days", "alert_burden_label",
        "triage_decision", "triage_notes",
    ]
    available = [c for c in desired if c in df.columns]
    if available:
        return df[available]
    return df


def build_cross_site_alert_hygiene_table(
    exports_dir: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build cross-site alert hygiene table from latest hygiene CSV.

    Args:
        exports_dir: Directory containing reports.

    Returns:
        DataFrame with hygiene data, or empty DataFrame.
    """
    report_path = find_latest_report("cross_site_alert_hygiene", exports_dir)
    if not report_path:
        return pd.DataFrame()

    df = load_report_csv(report_path)
    if df.empty:
        return df

    desired = [
        "issue_id", "category", "severity",
        "property_id", "alert_id", "alert_type",
        "alert_status", "alert_age_days", "burden_label",
        "message", "recommended_action",
    ]
    available = [c for c in desired if c in df.columns]
    if available:
        return df[available]
    return df


def build_cross_site_alert_archive_policy_table(
    exports_dir: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build cross-site alert archive policy table from latest CSV.

    Args:
        exports_dir: Directory containing reports.

    Returns:
        DataFrame with archive candidate data, or empty DataFrame.
    """
    report_path = find_latest_report(
        "cross_site_alert_archive_candidates", exports_dir,
    )
    if not report_path:
        return pd.DataFrame()

    df = load_report_csv(report_path)
    if df.empty:
        return df

    desired = [
        "alert_id", "property_id", "address", "city",
        "alert_type", "severity", "current_status",
        "alert_age_days", "archive_decision", "archive_notes",
    ]
    available = [c for c in desired if c in df.columns]
    if available:
        return df[available]
    return df


def build_cross_site_alert_expiration_policy_table(
    exports_dir: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build cross-site alert expiration policy table from latest CSV.

    Args:
        exports_dir: Directory containing reports.

    Returns:
        DataFrame with expiration candidate data, or empty DataFrame.
    """
    report_path = find_latest_report(
        "cross_site_alert_expiration_approval", exports_dir,
    )
    if not report_path:
        return pd.DataFrame()

    df = load_report_csv(report_path)
    if df.empty:
        return df

    desired = [
        "alert_id", "property_id", "address", "city",
        "alert_type", "severity", "current_status",
        "alert_age_days", "proposed_action", "approval_decision",
    ]
    available = [c for c in desired if c in df.columns]
    if available:
        return df[available]
    return df


def build_cross_site_trend_alerts_from_db(
    db_path: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """Build cross-site trend alerts table directly from database.

    Args:
        db_path: Path to database.

    Returns:
        DataFrame with open alert data, or empty DataFrame.
    """
    database = str(db_path) if db_path else config.database_path

    if not Path(database).exists() or not table_exists("cross_site_trend_alerts", database):
        return pd.DataFrame()

    query = """
    SELECT a.alert_id, a.property_id, wp.address, wp.city,
           a.alert_type, a.severity, a.alert_status,
           a.trend_direction, a.message, a.recommended_action,
           a.created_at
    FROM cross_site_trend_alerts a
    LEFT JOIN watched_properties wp ON a.property_id = wp.property_id
    ORDER BY a.created_at DESC
    """
    try:
        rows = execute_query(query, database_path=database)
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(row) for row in rows])
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Full dashboard data loader
# ---------------------------------------------------------------------------


def load_dashboard_data(
    db_path: Optional[Union[Path, str]] = None,
    exports_dir: Optional[Union[Path, str]] = None,
) -> DashboardData:
    """Load all dashboard data from local sources.

    Reads the local SQLite database and CSV reports. No network calls.

    Args:
        db_path: Path to SQLite database.
        exports_dir: Directory containing exported reports.

    Returns:
        DashboardData with all tables and summary.
    """
    database = str(db_path) if db_path else config.database_path
    exp_dir = str(exports_dir) if exports_dir else config.data_exports_dir

    data = DashboardData()
    data.summary = get_dashboard_summary(database)
    data.candidates = build_candidate_table(database)
    data.watched = build_watchlist_table(database)
    data.monitoring = build_monitoring_table(exp_dir)
    data.effective_dom_v2 = build_effective_dom_v2_table(exp_dir)
    data.county_verification = build_county_verification_table(exp_dir)
    data.cross_site = build_cross_site_table(exp_dir)
    data.manifest = load_latest_report_manifest(exp_dir)

    # Workflow summaries
    summary_paths = find_workflow_summaries(exp_dir)
    data.workflow_summaries = [str(p) for p in summary_paths]

    return data
