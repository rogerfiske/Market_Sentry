"""Portfolio Trend Alert History and Persistence.

Provides append-only persistence of portfolio trend alert evaluation
results, enabling comparison of current vs. previous runs, recurring
alert detection, and history reporting.

This module is local-only operational history. It writes append-only
alert evaluation snapshots and history rows but does not change
candidate decisions, watchlist status, alert status, Redfin
source-of-truth fields, or retrieval behavior.

No outbound notifications are sent.
"""

import csv
import hashlib
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

logger = logging.getLogger("marketsentry")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PortfolioTrendAlertRunRecord(BaseModel):
    """A single alert evaluation run record."""

    run_id: int = 0
    run_key: str = ""
    evaluated_at: str = ""
    rule_config_path: str = ""
    rule_config_mode: str = ""
    rules_evaluated_count: int = 0
    alerts_generated_count: int = 0
    high_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    portfolio_alert_count: int = 0
    property_alert_count: int = 0
    source_pack_count: int = 0
    source_date_range_start: str = ""
    source_date_range_end: str = ""
    digest_csv_path: str = ""
    digest_md_path: str = ""
    notes: str = ""
    created_at: str = ""


class PortfolioTrendAlertHistoryRecord(BaseModel):
    """A single persisted alert history row."""

    history_id: int = 0
    run_id: int = 0
    alert_key: str = ""
    alert_scope: str = ""
    property_id: int = 0
    candidate_id: int = 0
    address: str = ""
    severity: str = ""
    alert_type: str = ""
    rule_id: str = ""
    rule_name: str = ""
    metric_name: str = ""
    previous_value: str = ""
    current_value: str = ""
    delta_value: str = ""
    message: str = ""
    recommended_local_action: str = ""
    source_pack_file: str = ""
    generated_at: str = ""
    created_at: str = ""


class PortfolioTrendAlertHistorySummary(BaseModel):
    """Summary of alert history over a time period."""

    run_count: int = 0
    total_history_rows: int = 0
    recurring_alert_count: int = 0
    most_frequent_alert_types: List[Dict[str, object]] = Field(
        default_factory=list
    )
    properties_with_repeated_alerts: List[Dict[str, object]] = Field(
        default_factory=list
    )
    persistent_high_alerts: List[Dict[str, object]] = Field(
        default_factory=list
    )
    days: int = 30


class PortfolioTrendAlertPersistenceSummary(BaseModel):
    """Summary of persistence result from a single run."""

    run_id: int = 0
    run_key: str = ""
    alerts_persisted: int = 0
    high_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    portfolio_alert_count: int = 0
    property_alert_count: int = 0
    digest_csv_path: str = ""
    digest_md_path: str = ""


class PortfolioTrendAlertComparisonRow(BaseModel):
    """A single row in a current-vs-previous run comparison."""

    alert_key: str = ""
    property_id: str = ""
    address: str = ""
    alert_type: str = ""
    rule_id: str = ""
    metric_name: str = ""
    previous_severity: str = ""
    current_severity: str = ""
    comparison_status: str = ""
    previous_value: str = ""
    current_value: str = ""
    delta_value: str = ""
    summary: str = ""
    recommended_local_action: str = ""


class PortfolioTrendAlertHistoryRunResult(BaseModel):
    """Result container for history operations."""

    run_record: Optional[PortfolioTrendAlertRunRecord] = None
    persistence_summary: Optional[
        PortfolioTrendAlertPersistenceSummary
    ] = None
    comparison_rows: List[PortfolioTrendAlertComparisonRow] = Field(
        default_factory=list
    )
    export_paths: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Alert key generation
# ---------------------------------------------------------------------------

def generate_alert_key(
    alert_scope: str,
    property_id: str,
    alert_type: str,
    rule_id: str,
    metric_name: str,
) -> str:
    """Generate a deterministic alert key for comparison across runs.

    Uses SHA-256 hash of normalized key fields to create a stable
    identifier. Human-readable fields are preserved in report rows.

    Args:
        alert_scope: portfolio or property.
        property_id: Property ID or empty string for portfolio.
        alert_type: Alert type string.
        rule_id: Rule ID or empty string.
        metric_name: Metric name string.

    Returns:
        Hex digest alert key string.
    """
    parts = [
        alert_scope.strip().lower(),
        str(property_id).strip(),
        alert_type.strip().lower(),
        rule_id.strip().lower(),
        metric_name.strip().lower(),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def create_portfolio_trend_alert_run(
    db_path: str,
    evaluated_at: str,
    rule_config_path: str = "",
    rule_config_mode: str = "",
    rules_evaluated_count: int = 0,
    alerts_generated_count: int = 0,
    high_count: int = 0,
    warning_count: int = 0,
    info_count: int = 0,
    portfolio_alert_count: int = 0,
    property_alert_count: int = 0,
    source_pack_count: int = 0,
    source_date_range_start: str = "",
    source_date_range_end: str = "",
    digest_csv_path: str = "",
    digest_md_path: str = "",
    notes: str = "",
) -> int:
    """Create a new alert evaluation run record.

    Inserts a single row into portfolio_trend_alert_runs.
    This is append-only. No existing rows are modified.

    Args:
        db_path: Path to SQLite database.
        evaluated_at: Timestamp of evaluation.
        rule_config_path: Path to rule config used.
        rule_config_mode: Config mode (merge/replace/builtin).
        rules_evaluated_count: Number of rules evaluated.
        alerts_generated_count: Total alerts generated.
        high_count: High severity alert count.
        warning_count: Warning severity alert count.
        info_count: Info severity alert count.
        portfolio_alert_count: Portfolio-scope alert count.
        property_alert_count: Property-scope alert count.
        source_pack_count: Number of source pack files.
        source_date_range_start: Earliest pack date.
        source_date_range_end: Latest pack date.
        digest_csv_path: Path to exported CSV digest.
        digest_md_path: Path to exported MD digest.
        notes: Optional notes.

    Returns:
        The run_id of the inserted row.
    """
    run_key = (
        f"{evaluated_at}_{alerts_generated_count}"
        f"_{rule_config_mode or 'builtin'}"
    )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO portfolio_trend_alert_runs (
                run_key, evaluated_at, rule_config_path,
                rule_config_mode, rules_evaluated_count,
                alerts_generated_count, high_count,
                warning_count, info_count,
                portfolio_alert_count, property_alert_count,
                source_pack_count, source_date_range_start,
                source_date_range_end, digest_csv_path,
                digest_md_path, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_key, evaluated_at, rule_config_path,
                rule_config_mode, rules_evaluated_count,
                alerts_generated_count, high_count,
                warning_count, info_count,
                portfolio_alert_count, property_alert_count,
                source_pack_count, source_date_range_start,
                source_date_range_end, digest_csv_path,
                digest_md_path, notes,
            ),
        )
        conn.commit()
        run_id = cursor.lastrowid
        logger.info(
            f"Created alert run {run_id} with "
            f"{alerts_generated_count} alerts."
        )
        return run_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating alert run: {e}")
        raise
    finally:
        conn.close()


def persist_portfolio_trend_alerts(
    db_path: str,
    exports_dir: str = "data/exports",
    output_dir: str = "data/exports",
    rule_config: Optional[Union[Path, str]] = None,
    write_digest: bool = True,
) -> PortfolioTrendAlertPersistenceSummary:
    """Evaluate and persist portfolio trend alerts.

    Evaluates alerts using M43/M44 logic, optionally exports
    digest files, then inserts one run row and one history row
    per alert. This is append-only operational history.

    No candidate/watchlist/alert mutation.
    No outbound notifications.

    Args:
        db_path: Path to SQLite database.
        exports_dir: Directory with review pack CSV exports.
        output_dir: Directory for output digest files.
        rule_config: Optional path to custom rule config JSON.
        write_digest: Whether to export digest files.

    Returns:
        PortfolioTrendAlertPersistenceSummary with run details.
    """
    from marketsentry.portfolio_trend_alerts import (
        evaluate_portfolio_trend_alerts,
        export_portfolio_trend_alert_digest,
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = PortfolioTrendAlertPersistenceSummary()

    # Evaluate alerts
    digest = evaluate_portfolio_trend_alerts(
        exports_dir, rule_config=rule_config,
    )

    # Optionally export digest
    digest_csv = ""
    digest_md = ""
    if write_digest and digest.alerts:
        run_result = export_portfolio_trend_alert_digest(
            exports_dir=exports_dir,
            output_dir=output_dir,
            fmt="both",
            rule_config=rule_config,
        )
        for p in run_result.export_paths:
            if p.endswith(".csv"):
                digest_csv = p
            elif p.endswith(".md"):
                digest_md = p

    # Determine rule config info
    config_path_str = str(rule_config) if rule_config else ""
    config_mode = "builtin"
    rules_count = 0
    if rule_config:
        from marketsentry.portfolio_trend_alerts import (
            get_active_portfolio_trend_alert_rules,
        )
        active, mode, _, _, _ = (
            get_active_portfolio_trend_alert_rules(rule_config)
        )
        config_mode = mode
        rules_count = len(active)
    else:
        from marketsentry.portfolio_trend_alerts import (
            get_default_portfolio_trend_alert_rules,
        )
        rules_count = len(
            get_default_portfolio_trend_alert_rules()
        )

    # Count by severity and scope
    high = sum(
        1 for a in digest.alerts if a.severity == "high"
    )
    warning = sum(
        1 for a in digest.alerts if a.severity == "warning"
    )
    info = sum(
        1 for a in digest.alerts if a.severity == "info"
    )
    portfolio_count = sum(
        1 for a in digest.alerts
        if a.alert_scope == "portfolio"
    )
    property_count = sum(
        1 for a in digest.alerts
        if a.alert_scope == "property"
    )

    # Source pack info
    pack_count = digest.summary.pack_count if digest.summary else 0
    start = (
        digest.summary.first_pack_date
        if digest.summary else ""
    )
    end = (
        digest.summary.latest_pack_date
        if digest.summary else ""
    )

    # Create run row
    run_id = create_portfolio_trend_alert_run(
        db_path=db_path,
        evaluated_at=now,
        rule_config_path=config_path_str,
        rule_config_mode=config_mode,
        rules_evaluated_count=rules_count,
        alerts_generated_count=len(digest.alerts),
        high_count=high,
        warning_count=warning,
        info_count=info,
        portfolio_alert_count=portfolio_count,
        property_alert_count=property_count,
        source_pack_count=pack_count,
        source_date_range_start=start,
        source_date_range_end=end,
        digest_csv_path=digest_csv,
        digest_md_path=digest_md,
    )

    # Persist each alert as history row
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        for a in digest.alerts:
            alert_key = generate_alert_key(
                alert_scope=a.alert_scope,
                property_id=a.property_id,
                alert_type=a.alert_type,
                rule_id=a.alert_id,
                metric_name=a.metric_name,
            )

            prop_id = None
            if a.property_id:
                try:
                    prop_id = int(a.property_id)
                except (ValueError, TypeError):
                    prop_id = None

            cand_id = None
            if a.candidate_id:
                try:
                    cand_id = int(a.candidate_id)
                except (ValueError, TypeError):
                    cand_id = None

            cursor.execute(
                """INSERT INTO portfolio_trend_alert_history (
                    run_id, alert_key, alert_scope,
                    property_id, candidate_id, address,
                    severity, alert_type, rule_id,
                    rule_name, metric_name, previous_value,
                    current_value, delta_value, message,
                    recommended_local_action,
                    source_pack_file, generated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )""",
                (
                    run_id, alert_key, a.alert_scope,
                    prop_id, cand_id, a.address,
                    a.severity, a.alert_type, a.alert_id,
                    "", a.metric_name, a.previous_value,
                    a.current_value, a.delta_value, a.message,
                    a.recommended_local_action,
                    a.source_pack_file, a.generated_at,
                ),
            )

        conn.commit()
        logger.info(
            f"Persisted {len(digest.alerts)} alerts "
            f"for run {run_id}."
        )
    except Exception as e:
        conn.rollback()
        logger.error(f"Error persisting alert history: {e}")
        raise
    finally:
        conn.close()

    summary.run_id = run_id
    summary.run_key = (
        f"{now}_{len(digest.alerts)}"
        f"_{config_mode}"
    )
    summary.alerts_persisted = len(digest.alerts)
    summary.high_count = high
    summary.warning_count = warning
    summary.info_count = info
    summary.portfolio_alert_count = portfolio_count
    summary.property_alert_count = property_count
    summary.digest_csv_path = digest_csv
    summary.digest_md_path = digest_md

    return summary


def get_latest_portfolio_trend_alert_run(
    db_path: str,
) -> Optional[PortfolioTrendAlertRunRecord]:
    """Get the most recent alert evaluation run.

    Args:
        db_path: Path to SQLite database.

    Returns:
        PortfolioTrendAlertRunRecord or None if no runs exist.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT * FROM portfolio_trend_alert_runs
               ORDER BY run_id DESC LIMIT 1"""
        )
        row = cursor.fetchone()
        if not row:
            return None
        return _row_to_run_record(row)
    finally:
        conn.close()


def get_previous_portfolio_trend_alert_run(
    db_path: str,
    current_run_id: Optional[int] = None,
) -> Optional[PortfolioTrendAlertRunRecord]:
    """Get the run before the current (or latest) run.

    Args:
        db_path: Path to SQLite database.
        current_run_id: The current run ID. If None, uses latest.

    Returns:
        PortfolioTrendAlertRunRecord or None.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        if current_run_id is None:
            # Get latest first
            cursor.execute(
                """SELECT run_id FROM portfolio_trend_alert_runs
                   ORDER BY run_id DESC LIMIT 1"""
            )
            row = cursor.fetchone()
            if not row:
                return None
            current_run_id = row["run_id"]

        cursor.execute(
            """SELECT * FROM portfolio_trend_alert_runs
               WHERE run_id < ?
               ORDER BY run_id DESC LIMIT 1""",
            (current_run_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return _row_to_run_record(row)
    finally:
        conn.close()


def compare_portfolio_trend_alert_runs(
    db_path: str,
    current_run_id: Optional[int] = None,
    previous_run_id: Optional[int] = None,
    limit: int = 20,
) -> Tuple[
    List[PortfolioTrendAlertComparisonRow],
    Dict[str, int],
]:
    """Compare two alert evaluation runs.

    Identifies new, persistent, disappeared, worsened, improved,
    and unchanged alerts between runs.

    Args:
        db_path: Path to SQLite database.
        current_run_id: Current run ID. None = latest.
        previous_run_id: Previous run ID. None = auto-detect.
        limit: Maximum comparison rows to return.

    Returns:
        Tuple of (comparison_rows, summary_counts).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Resolve current run
        if current_run_id is None:
            cursor.execute(
                """SELECT run_id FROM portfolio_trend_alert_runs
                   ORDER BY run_id DESC LIMIT 1"""
            )
            row = cursor.fetchone()
            if not row:
                return [], {"current_run_id": 0, "previous_run_id": 0}
            current_run_id = row["run_id"]

        # Resolve previous run
        if previous_run_id is None:
            cursor.execute(
                """SELECT run_id FROM portfolio_trend_alert_runs
                   WHERE run_id < ?
                   ORDER BY run_id DESC LIMIT 1""",
                (current_run_id,),
            )
            row = cursor.fetchone()
            if not row:
                # First run - all alerts are "new"
                return _first_run_comparison(
                    cursor, current_run_id, limit
                )

            previous_run_id = row["run_id"]

        # Get alerts from both runs indexed by alert_key
        current_alerts = _get_run_alerts(
            cursor, current_run_id
        )
        previous_alerts = _get_run_alerts(
            cursor, previous_run_id
        )

        rows: List[PortfolioTrendAlertComparisonRow] = []
        counts = {
            "current_run_id": current_run_id,
            "previous_run_id": previous_run_id,
            "new": 0,
            "persistent": 0,
            "disappeared": 0,
            "worsened": 0,
            "improved": 0,
            "unchanged": 0,
        }

        all_keys = set(current_alerts.keys()) | set(
            previous_alerts.keys()
        )

        for key in sorted(all_keys):
            curr = current_alerts.get(key)
            prev = previous_alerts.get(key)

            if curr and not prev:
                # New alert
                status = "new"
                counts["new"] += 1
                rows.append(_make_comparison_row(
                    curr, None, status
                ))
            elif prev and not curr:
                # Disappeared
                status = "disappeared"
                counts["disappeared"] += 1
                rows.append(_make_comparison_row(
                    None, prev, status
                ))
            elif curr and prev:
                # Both present - check severity changes
                severity_order = {
                    "info": 0, "warning": 1, "high": 2,
                }
                curr_sev = severity_order.get(
                    curr["severity"], 0
                )
                prev_sev = severity_order.get(
                    prev["severity"], 0
                )

                if curr_sev > prev_sev:
                    status = "worsened"
                    counts["worsened"] += 1
                elif curr_sev < prev_sev:
                    status = "improved"
                    counts["improved"] += 1
                elif curr["current_value"] != prev["current_value"]:
                    status = "persistent"
                    counts["persistent"] += 1
                else:
                    status = "unchanged"
                    counts["unchanged"] += 1

                rows.append(_make_comparison_row(
                    curr, prev, status
                ))

            if len(rows) >= limit:
                break

        return rows, counts

    finally:
        conn.close()


def summarize_portfolio_trend_alert_history(
    db_path: str,
    property_id: Optional[int] = None,
    days: int = 30,
) -> PortfolioTrendAlertHistorySummary:
    """Summarize alert history over a time period.

    Args:
        db_path: Path to SQLite database.
        property_id: Optional property ID filter.
        days: Number of days to look back.

    Returns:
        PortfolioTrendAlertHistorySummary.
    """
    summary = PortfolioTrendAlertHistorySummary(days=days)

    cutoff = (
        datetime.now() - timedelta(days=days)
    ).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Run count
        cursor.execute(
            """SELECT COUNT(*) as cnt
               FROM portfolio_trend_alert_runs
               WHERE evaluated_at >= ?""",
            (cutoff,),
        )
        summary.run_count = cursor.fetchone()["cnt"]

        # History rows
        base_where = "WHERE h.generated_at >= ?"
        params: list = [cutoff]
        if property_id is not None:
            base_where += " AND h.property_id = ?"
            params.append(property_id)

        cursor.execute(
            f"""SELECT COUNT(*) as cnt
                FROM portfolio_trend_alert_history h
                {base_where}""",
            params,
        )
        summary.total_history_rows = cursor.fetchone()["cnt"]

        # Recurring alerts (alert_key seen in > 1 run)
        cursor.execute(
            f"""SELECT alert_key, COUNT(DISTINCT run_id) as run_cnt
                FROM portfolio_trend_alert_history h
                {base_where}
                GROUP BY alert_key
                HAVING run_cnt > 1
                ORDER BY run_cnt DESC
                LIMIT 10""",
            params,
        )
        recurring = cursor.fetchall()
        summary.recurring_alert_count = len(recurring)

        # Most frequent alert types
        cursor.execute(
            f"""SELECT alert_type,
                       COUNT(*) as cnt
                FROM portfolio_trend_alert_history h
                {base_where}
                GROUP BY alert_type
                ORDER BY cnt DESC
                LIMIT 10""",
            params,
        )
        summary.most_frequent_alert_types = [
            {"alert_type": r["alert_type"], "count": r["cnt"]}
            for r in cursor.fetchall()
        ]

        # Properties with repeated alerts
        cursor.execute(
            f"""SELECT property_id, address,
                       COUNT(*) as cnt,
                       COUNT(DISTINCT run_id) as run_cnt
                FROM portfolio_trend_alert_history h
                {base_where}
                AND property_id IS NOT NULL
                AND property_id > 0
                GROUP BY property_id
                HAVING run_cnt > 1
                ORDER BY cnt DESC
                LIMIT 10""",
            params,
        )
        summary.properties_with_repeated_alerts = [
            {
                "property_id": r["property_id"],
                "address": r["address"],
                "alert_count": r["cnt"],
                "run_count": r["run_cnt"],
            }
            for r in cursor.fetchall()
        ]

        # Persistent high alerts
        cursor.execute(
            f"""SELECT alert_key, alert_type, address,
                       metric_name, severity,
                       COUNT(DISTINCT run_id) as run_cnt,
                       MIN(h.generated_at) as first_seen,
                       MAX(h.generated_at) as latest_seen
                FROM portfolio_trend_alert_history h
                {base_where}
                AND severity = 'high'
                GROUP BY alert_key
                HAVING run_cnt > 1
                ORDER BY run_cnt DESC
                LIMIT 10""",
            params,
        )
        summary.persistent_high_alerts = [
            {
                "alert_key": r["alert_key"],
                "alert_type": r["alert_type"],
                "address": r["address"] or "",
                "metric_name": r["metric_name"],
                "severity": r["severity"],
                "run_count": r["run_cnt"],
                "first_seen": r["first_seen"],
                "latest_seen": r["latest_seen"],
            }
            for r in cursor.fetchall()
        ]

        return summary
    finally:
        conn.close()


def export_portfolio_trend_alert_history_report(
    db_path: str,
    output_dir: str = "data/exports",
    fmt: str = "both",
    days: int = 30,
) -> List[str]:
    """Export alert history report as CSV and/or Markdown.

    Args:
        db_path: Path to SQLite database.
        output_dir: Output directory.
        fmt: Export format: csv, md, or both.
        days: Lookback period in days.

    Returns:
        List of exported file paths.
    """
    cutoff = (
        datetime.now() - timedelta(days=days)
    ).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(
            """SELECT h.alert_key, h.alert_scope,
                      h.property_id, h.address,
                      h.severity, h.alert_type,
                      h.rule_id, h.metric_name,
                      h.message,
                      h.recommended_local_action,
                      COUNT(DISTINCT h.run_id) as count_seen,
                      MIN(h.generated_at) as first_seen,
                      MAX(h.generated_at) as latest_seen,
                      GROUP_CONCAT(DISTINCT h.run_id) as run_ids
               FROM portfolio_trend_alert_history h
               WHERE h.generated_at >= ?
               GROUP BY h.alert_key
               ORDER BY count_seen DESC, h.severity DESC""",
            (cutoff,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: List[str] = []

    if fmt in ("csv", "both"):
        csv_path = os.path.join(
            output_dir,
            f"portfolio_trend_alert_history_{ts}.csv",
        )
        _write_history_csv(csv_path, rows)
        paths.append(csv_path)

    if fmt in ("md", "both"):
        md_path = os.path.join(
            output_dir,
            f"portfolio_trend_alert_history_{ts}.md",
        )
        _write_history_md(md_path, rows, days)
        paths.append(md_path)

    return paths


def export_portfolio_trend_alert_comparison_report(
    db_path: str,
    output_dir: str = "data/exports",
    fmt: str = "both",
    current_run_id: Optional[int] = None,
    previous_run_id: Optional[int] = None,
) -> List[str]:
    """Export current-vs-previous run comparison report.

    Args:
        db_path: Path to SQLite database.
        output_dir: Output directory.
        fmt: Export format: csv, md, or both.
        current_run_id: Current run ID. None = latest.
        previous_run_id: Previous run ID. None = auto.

    Returns:
        List of exported file paths.
    """
    comparison_rows, counts = compare_portfolio_trend_alert_runs(
        db_path,
        current_run_id=current_run_id,
        previous_run_id=previous_run_id,
        limit=1000,
    )

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: List[str] = []

    if fmt in ("csv", "both"):
        csv_path = os.path.join(
            output_dir,
            f"portfolio_trend_alert_run_comparison_{ts}.csv",
        )
        _write_comparison_csv(csv_path, comparison_rows, counts)
        paths.append(csv_path)

    if fmt in ("md", "both"):
        md_path = os.path.join(
            output_dir,
            f"portfolio_trend_alert_run_comparison_{ts}.md",
        )
        _write_comparison_md(md_path, comparison_rows, counts)
        paths.append(md_path)

    return paths


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row_to_run_record(
    row: sqlite3.Row,
) -> PortfolioTrendAlertRunRecord:
    """Convert a database row to a run record model."""
    return PortfolioTrendAlertRunRecord(
        run_id=row["run_id"],
        run_key=row["run_key"] or "",
        evaluated_at=row["evaluated_at"] or "",
        rule_config_path=row["rule_config_path"] or "",
        rule_config_mode=row["rule_config_mode"] or "",
        rules_evaluated_count=row["rules_evaluated_count"] or 0,
        alerts_generated_count=row["alerts_generated_count"] or 0,
        high_count=row["high_count"] or 0,
        warning_count=row["warning_count"] or 0,
        info_count=row["info_count"] or 0,
        portfolio_alert_count=row["portfolio_alert_count"] or 0,
        property_alert_count=row["property_alert_count"] or 0,
        source_pack_count=row["source_pack_count"] or 0,
        source_date_range_start=(
            row["source_date_range_start"] or ""
        ),
        source_date_range_end=(
            row["source_date_range_end"] or ""
        ),
        digest_csv_path=row["digest_csv_path"] or "",
        digest_md_path=row["digest_md_path"] or "",
        notes=row["notes"] or "",
        created_at=row["created_at"] or "",
    )


def _get_run_alerts(
    cursor: sqlite3.Cursor,
    run_id: int,
) -> Dict[str, dict]:
    """Get all alert history rows for a run, keyed by alert_key."""
    cursor.execute(
        """SELECT * FROM portfolio_trend_alert_history
           WHERE run_id = ?""",
        (run_id,),
    )
    result: Dict[str, dict] = {}
    for row in cursor.fetchall():
        key = row["alert_key"]
        result[key] = dict(row)
    return result


def _first_run_comparison(
    cursor: sqlite3.Cursor,
    run_id: int,
    limit: int,
) -> Tuple[
    List[PortfolioTrendAlertComparisonRow],
    Dict[str, int],
]:
    """Handle comparison when there is only one run.

    All alerts are labeled 'new'.
    """
    current_alerts = _get_run_alerts(cursor, run_id)
    rows: List[PortfolioTrendAlertComparisonRow] = []
    counts = {
        "current_run_id": run_id,
        "previous_run_id": 0,
        "new": 0,
        "persistent": 0,
        "disappeared": 0,
        "worsened": 0,
        "improved": 0,
        "unchanged": 0,
    }

    for key in sorted(current_alerts.keys()):
        curr = current_alerts[key]
        rows.append(_make_comparison_row(curr, None, "new"))
        counts["new"] += 1
        if len(rows) >= limit:
            break

    return rows, counts


def _make_comparison_row(
    current: Optional[dict],
    previous: Optional[dict],
    status: str,
) -> PortfolioTrendAlertComparisonRow:
    """Create a comparison row from current and/or previous alert."""
    row = PortfolioTrendAlertComparisonRow(
        comparison_status=status,
    )

    if current:
        row.alert_key = current.get("alert_key", "")
        row.property_id = str(current.get("property_id", "") or "")
        row.address = current.get("address", "") or ""
        row.alert_type = current.get("alert_type", "") or ""
        row.rule_id = current.get("rule_id", "") or ""
        row.metric_name = current.get("metric_name", "") or ""
        row.current_severity = current.get("severity", "") or ""
        row.current_value = current.get("current_value", "") or ""
        row.delta_value = current.get("delta_value", "") or ""
        row.recommended_local_action = (
            current.get("recommended_local_action", "") or ""
        )
    if previous:
        if not current:
            row.alert_key = previous.get("alert_key", "")
            row.property_id = str(
                previous.get("property_id", "") or ""
            )
            row.address = previous.get("address", "") or ""
            row.alert_type = previous.get("alert_type", "") or ""
            row.rule_id = previous.get("rule_id", "") or ""
            row.metric_name = previous.get("metric_name", "") or ""
            row.recommended_local_action = (
                previous.get("recommended_local_action", "") or ""
            )
        row.previous_severity = (
            previous.get("severity", "") or ""
        )
        row.previous_value = (
            previous.get("current_value", "") or ""
        )

    # Summary text
    if status == "new":
        row.summary = (
            f"New alert: {row.alert_type}"
        )
    elif status == "disappeared":
        row.summary = (
            f"Not present in latest evaluation: "
            f"{row.alert_type}"
        )
    elif status == "worsened":
        row.summary = (
            f"Severity increased from "
            f"{row.previous_severity} to "
            f"{row.current_severity}"
        )
    elif status == "improved":
        row.summary = (
            f"Severity decreased from "
            f"{row.previous_severity} to "
            f"{row.current_severity}"
        )
    elif status == "persistent":
        row.summary = (
            f"Persistent alert: {row.alert_type}"
        )
    else:
        row.summary = f"Unchanged: {row.alert_type}"

    return row


# ---------------------------------------------------------------------------
# History report writers
# ---------------------------------------------------------------------------

HISTORY_CSV_FIELDNAMES = [
    "alert_key", "alert_scope", "property_id", "address",
    "severity", "alert_type", "rule_id", "metric_name",
    "count_seen", "first_seen", "latest_seen",
    "message", "recommended_local_action", "run_ids",
]

COMPARISON_CSV_FIELDNAMES = [
    "alert_key", "property_id", "address", "alert_type",
    "rule_id", "metric_name", "previous_severity",
    "current_severity", "comparison_status",
    "previous_value", "current_value", "delta_value",
    "summary", "recommended_local_action",
]


def _write_history_csv(
    path: str,
    rows: list,
) -> None:
    """Write history report to CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=HISTORY_CSV_FIELDNAMES
        )
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "alert_key": r["alert_key"],
                "alert_scope": r["alert_scope"],
                "property_id": r["property_id"] or "",
                "address": r["address"] or "",
                "severity": r["severity"],
                "alert_type": r["alert_type"],
                "rule_id": r["rule_id"] or "",
                "metric_name": r["metric_name"] or "",
                "count_seen": r["count_seen"],
                "first_seen": r["first_seen"],
                "latest_seen": r["latest_seen"],
                "message": r["message"] or "",
                "recommended_local_action": (
                    r["recommended_local_action"] or ""
                ),
                "run_ids": r["run_ids"] or "",
            })


def _write_history_md(
    path: str,
    rows: list,
    days: int,
) -> None:
    """Write history report to Markdown."""
    lines: List[str] = []
    lines.append(
        "# Portfolio Trend Alert History Report"
    )
    lines.append("")
    lines.append(
        f"Generated: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    lines.append(f"Lookback: {days} days")
    lines.append(f"Total unique alerts: {len(rows)}")
    lines.append("")
    lines.append(
        "*This report is a local analytical review aid. "
        "It does not make purchase recommendations, infer "
        "seller intent, or mutate candidate/watchlist/alert "
        "state. No outbound notifications are sent.*"
    )
    lines.append("")

    if rows:
        lines.append("## Alert History")
        lines.append("")
        lines.append(
            "| Alert Key | Scope | Address | Severity "
            "| Type | Seen | First | Latest |"
        )
        lines.append(
            "| --- | --- | --- | --- | --- | --- | --- | --- |"
        )
        for r in rows:
            addr = (r["address"] or "")[:30]
            lines.append(
                f"| {r['alert_key'][:8]}..."
                f" | {r['alert_scope']}"
                f" | {addr}"
                f" | {r['severity']}"
                f" | {r['alert_type'][:25]}"
                f" | {r['count_seen']}"
                f" | {r['first_seen'][:10]}"
                f" | {r['latest_seen'][:10]} |"
            )
        lines.append("")
    else:
        lines.append(
            "No alert history found for the specified period."
        )
        lines.append("")

    lines.append(
        "*No outbound notifications sent. "
        "No candidate/watchlist/alert state modified.*"
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _write_comparison_csv(
    path: str,
    rows: List[PortfolioTrendAlertComparisonRow],
    counts: Dict[str, int],
) -> None:
    """Write comparison report to CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=COMPARISON_CSV_FIELDNAMES
        )
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "alert_key": r.alert_key,
                "property_id": r.property_id,
                "address": r.address,
                "alert_type": r.alert_type,
                "rule_id": r.rule_id,
                "metric_name": r.metric_name,
                "previous_severity": r.previous_severity,
                "current_severity": r.current_severity,
                "comparison_status": r.comparison_status,
                "previous_value": r.previous_value,
                "current_value": r.current_value,
                "delta_value": r.delta_value,
                "summary": r.summary,
                "recommended_local_action": (
                    r.recommended_local_action
                ),
            })


def _write_comparison_md(
    path: str,
    rows: List[PortfolioTrendAlertComparisonRow],
    counts: Dict[str, int],
) -> None:
    """Write comparison report to Markdown."""
    lines: List[str] = []
    lines.append(
        "# Portfolio Trend Alert Run Comparison"
    )
    lines.append("")
    lines.append(
        f"Generated: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    lines.append(
        f"Current run: {counts.get('current_run_id', 'N/A')}"
    )
    lines.append(
        f"Previous run: {counts.get('previous_run_id', 'N/A')}"
    )
    lines.append("")
    lines.append(
        "*This report is a local analytical review aid. "
        "It does not make purchase recommendations, infer "
        "seller intent, or mutate candidate/watchlist/alert "
        "state. No outbound notifications are sent.*"
    )
    lines.append("")

    lines.append("## Comparison Summary")
    lines.append("")
    lines.append(
        f"- New: {counts.get('new', 0)}"
    )
    lines.append(
        f"- Persistent: {counts.get('persistent', 0)}"
    )
    lines.append(
        f"- Disappeared (not present in latest evaluation): "
        f"{counts.get('disappeared', 0)}"
    )
    lines.append(
        f"- Severity increased: {counts.get('worsened', 0)}"
    )
    lines.append(
        f"- Severity decreased: {counts.get('improved', 0)}"
    )
    lines.append(
        f"- Unchanged: {counts.get('unchanged', 0)}"
    )
    lines.append("")

    if rows:
        lines.append("## Comparison Details")
        lines.append("")
        lines.append(
            "| Status | Address | Type | Prev Sev "
            "| Curr Sev | Summary |"
        )
        lines.append(
            "| --- | --- | --- | --- | --- | --- |"
        )
        for r in rows:
            addr = r.address[:25] if r.address else ""
            lines.append(
                f"| {r.comparison_status}"
                f" | {addr}"
                f" | {r.alert_type[:20]}"
                f" | {r.previous_severity}"
                f" | {r.current_severity}"
                f" | {r.summary[:40]} |"
            )
        lines.append("")
    else:
        lines.append("No comparison data available.")
        lines.append("")

    lines.append(
        "*No outbound notifications sent. "
        "No candidate/watchlist/alert state modified.*"
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
