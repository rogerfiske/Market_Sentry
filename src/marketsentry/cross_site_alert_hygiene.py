"""Cross-site alert hygiene checks and reports.

Identifies stale alerts, old acknowledged/resolved alerts,
pending reparse/manual review items, high-burden properties,
and repeated unresolved patterns. Generates CSV and Markdown
reports with recommended next actions.

Hygiene reports are read-only review aids. They do not
auto-archive alerts, change watchlist status, overwrite
Redfin source-of-truth fields, or modify Quiet Score
gatekeeper results. They do not infer seller intent
or make purchase recommendations.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from marketsentry.database import execute_query, table_exists
from marketsentry.logging_config import logger
from marketsentry.models import (
    CrossSiteAlertHygieneConfig,
    CrossSiteAlertHygieneIssue,
    CrossSiteAlertHygieneReportRow,
    CrossSiteAlertHygieneRunResult,
    CrossSiteAlertHygieneSummary,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HYGIENE_CSV_FIELDNAMES = [
    "issue_id",
    "category",
    "severity",
    "property_id",
    "candidate_id",
    "alert_id",
    "alert_type",
    "alert_status",
    "alert_age_days",
    "burden_label",
    "repeated_pattern",
    "message",
    "recommended_action",
    "source_context",
    "created_at",
]

_SEVERITY_ORDER = {"critical": 0, "high": 1, "warning": 2, "info": 3}


# ---------------------------------------------------------------------------
# Individual hygiene checks
# ---------------------------------------------------------------------------


def identify_stale_open_alerts(
    database_path: Optional[str] = None,
    stale_days: int = 7,
) -> List[CrossSiteAlertHygieneIssue]:
    """Identify open alerts older than stale_days.

    Args:
        database_path: Optional database path.
        stale_days: Days after which an open alert is stale.

    Returns:
        List of hygiene issues for stale open alerts.
    """
    if not table_exists("cross_site_trend_alerts", database_path):
        return []

    query = """
    SELECT a.alert_id, a.property_id, a.candidate_id, a.alert_type,
           a.alert_status, a.severity, a.created_at, a.source_context,
           wp.address
    FROM cross_site_trend_alerts a
    LEFT JOIN watched_properties wp ON a.property_id = wp.property_id
    WHERE a.alert_status = 'open'
    ORDER BY a.created_at ASC
    """
    issues: List[CrossSiteAlertHygieneIssue] = []
    try:
        rows = execute_query(query, database_path=database_path)
        for row in rows:
            age = _age_days(row["created_at"])
            if age is not None and age >= stale_days:
                addr = row["address"] or f"property {row['property_id']}"
                issues.append(CrossSiteAlertHygieneIssue(
                    category="stale_open_alert",
                    severity="warning" if age < 14 else "high",
                    property_id=row["property_id"],
                    candidate_id=row["candidate_id"],
                    alert_id=row["alert_id"],
                    alert_type=row["alert_type"],
                    alert_status="open",
                    alert_age_days=age,
                    message=f"Open alert for {addr} is {age} days old",
                    recommended_action=(
                        "Export triage CSV, review, and acknowledge or resolve"
                    ),
                    source_context=row["source_context"],
                    created_at=row["created_at"],
                ))
    except Exception as e:
        logger.error(f"Error identifying stale open alerts: {e}")
    return issues


def identify_old_acknowledged_alerts(
    database_path: Optional[str] = None,
    stale_days: int = 14,
) -> List[CrossSiteAlertHygieneIssue]:
    """Identify acknowledged alerts older than stale_days.

    Args:
        database_path: Optional database path.
        stale_days: Days after which an acknowledged alert is stale.

    Returns:
        List of hygiene issues for stale acknowledged alerts.
    """
    if not table_exists("cross_site_trend_alerts", database_path):
        return []

    query = """
    SELECT a.alert_id, a.property_id, a.candidate_id, a.alert_type,
           a.alert_status, a.created_at, a.source_context, wp.address
    FROM cross_site_trend_alerts a
    LEFT JOIN watched_properties wp ON a.property_id = wp.property_id
    WHERE a.alert_status = 'acknowledged'
    ORDER BY a.created_at ASC
    """
    issues: List[CrossSiteAlertHygieneIssue] = []
    try:
        rows = execute_query(query, database_path=database_path)
        for row in rows:
            age = _age_days(row["created_at"])
            if age is not None and age >= stale_days:
                addr = row["address"] or f"property {row['property_id']}"
                issues.append(CrossSiteAlertHygieneIssue(
                    category="stale_acknowledged_alert",
                    severity="info",
                    property_id=row["property_id"],
                    candidate_id=row["candidate_id"],
                    alert_id=row["alert_id"],
                    alert_type=row["alert_type"],
                    alert_status="acknowledged",
                    alert_age_days=age,
                    message=(
                        f"Acknowledged alert for {addr} is "
                        f"{age} days old without resolution"
                    ),
                    recommended_action="Resolve or archive via triage CSV",
                    source_context=row["source_context"],
                    created_at=row["created_at"],
                ))
    except Exception as e:
        logger.error(f"Error identifying old acknowledged alerts: {e}")
    return issues


def identify_old_resolved_alerts(
    database_path: Optional[str] = None,
    archive_days: int = 30,
) -> List[CrossSiteAlertHygieneIssue]:
    """Identify resolved alerts older than archive_days.

    Args:
        database_path: Optional database path.
        archive_days: Days after which a resolved alert is an archive candidate.

    Returns:
        List of hygiene issues for archive candidate alerts.
    """
    if not table_exists("cross_site_trend_alerts", database_path):
        return []

    query = """
    SELECT a.alert_id, a.property_id, a.candidate_id, a.alert_type,
           a.alert_status, a.created_at, a.source_context, wp.address
    FROM cross_site_trend_alerts a
    LEFT JOIN watched_properties wp ON a.property_id = wp.property_id
    WHERE a.alert_status = 'resolved'
    ORDER BY a.created_at ASC
    """
    issues: List[CrossSiteAlertHygieneIssue] = []
    try:
        rows = execute_query(query, database_path=database_path)
        for row in rows:
            age = _age_days(row["created_at"])
            if age is not None and age >= archive_days:
                addr = row["address"] or f"property {row['property_id']}"
                issues.append(CrossSiteAlertHygieneIssue(
                    category="resolved_archive_candidate",
                    severity="info",
                    property_id=row["property_id"],
                    candidate_id=row["candidate_id"],
                    alert_id=row["alert_id"],
                    alert_type=row["alert_type"],
                    alert_status="resolved",
                    alert_age_days=age,
                    message=(
                        f"Resolved alert for {addr} is "
                        f"{age} days old and may be archived"
                    ),
                    recommended_action=(
                        "Export archive candidates CSV and "
                        "set archive_decision to archive"
                    ),
                    source_context=row["source_context"],
                    created_at=row["created_at"],
                ))
    except Exception as e:
        logger.error(f"Error identifying old resolved alerts: {e}")
    return issues


def identify_needs_reparse_alerts(
    database_path: Optional[str] = None,
    stale_days: int = 7,
) -> List[CrossSiteAlertHygieneIssue]:
    """Identify alerts marked needs_reparse that are still open.

    Args:
        database_path: Optional database path.
        stale_days: Days before needs_reparse is considered stale.

    Returns:
        List of hygiene issues for needs_reparse alerts.
    """
    if not table_exists("cross_site_trend_alerts", database_path):
        return []

    query = """
    SELECT a.alert_id, a.property_id, a.candidate_id, a.alert_type,
           a.alert_status, a.created_at, a.source_context, a.notes,
           wp.address
    FROM cross_site_trend_alerts a
    LEFT JOIN watched_properties wp ON a.property_id = wp.property_id
    WHERE a.notes LIKE '%[triage:needs_reparse]%'
      AND a.alert_status IN ('open', 'acknowledged')
    ORDER BY a.created_at ASC
    """
    issues: List[CrossSiteAlertHygieneIssue] = []
    try:
        rows = execute_query(query, database_path=database_path)
        for row in rows:
            age = _age_days(row["created_at"])
            sev = "warning" if (age or 0) >= stale_days else "info"
            addr = row["address"] or f"property {row['property_id']}"
            issues.append(CrossSiteAlertHygieneIssue(
                category="needs_reparse_pending",
                severity=sev,
                property_id=row["property_id"],
                candidate_id=row["candidate_id"],
                alert_id=row["alert_id"],
                alert_type=row["alert_type"],
                alert_status=row["alert_status"],
                alert_age_days=age,
                message=(
                    f"Alert for {addr} marked needs_reparse "
                    f"but not yet resolved"
                ),
                recommended_action=(
                    "Re-parse the relevant cross-site fixture, "
                    "then resolve via triage"
                ),
                source_context=row["source_context"],
                created_at=row["created_at"],
            ))
    except Exception as e:
        logger.error(f"Error identifying needs_reparse alerts: {e}")
    return issues


def identify_needs_manual_review_alerts(
    database_path: Optional[str] = None,
    stale_days: int = 7,
) -> List[CrossSiteAlertHygieneIssue]:
    """Identify alerts marked needs_manual_review that are still open.

    Args:
        database_path: Optional database path.
        stale_days: Days before needs_manual_review is considered stale.

    Returns:
        List of hygiene issues for needs_manual_review alerts.
    """
    if not table_exists("cross_site_trend_alerts", database_path):
        return []

    query = """
    SELECT a.alert_id, a.property_id, a.candidate_id, a.alert_type,
           a.alert_status, a.created_at, a.source_context, a.notes,
           wp.address
    FROM cross_site_trend_alerts a
    LEFT JOIN watched_properties wp ON a.property_id = wp.property_id
    WHERE a.notes LIKE '%[triage:needs_manual_review]%'
      AND a.alert_status IN ('open', 'acknowledged')
    ORDER BY a.created_at ASC
    """
    issues: List[CrossSiteAlertHygieneIssue] = []
    try:
        rows = execute_query(query, database_path=database_path)
        for row in rows:
            age = _age_days(row["created_at"])
            sev = "warning" if (age or 0) >= stale_days else "info"
            addr = row["address"] or f"property {row['property_id']}"
            issues.append(CrossSiteAlertHygieneIssue(
                category="needs_manual_review_pending",
                severity=sev,
                property_id=row["property_id"],
                candidate_id=row["candidate_id"],
                alert_id=row["alert_id"],
                alert_type=row["alert_type"],
                alert_status=row["alert_status"],
                alert_age_days=age,
                message=(
                    f"Alert for {addr} marked needs_manual_review "
                    f"but not yet resolved"
                ),
                recommended_action=(
                    "Review cross-site data manually, "
                    "then resolve via triage"
                ),
                source_context=row["source_context"],
                created_at=row["created_at"],
            ))
    except Exception as e:
        logger.error(f"Error identifying needs_manual_review alerts: {e}")
    return issues


def identify_high_burden_properties(
    database_path: Optional[str] = None,
    high_burden_labels: Optional[List[str]] = None,
) -> List[CrossSiteAlertHygieneIssue]:
    """Identify properties with high alert burden.

    Args:
        database_path: Optional database path.
        high_burden_labels: Labels considered high burden.

    Returns:
        List of hygiene issues for high-burden properties.
    """
    if high_burden_labels is None:
        high_burden_labels = ["high", "elevated_review"]

    if not table_exists("cross_site_trend_alerts", database_path):
        return []

    issues: List[CrossSiteAlertHygieneIssue] = []
    try:
        from marketsentry.cross_site_alert_analytics import (
            calculate_alert_burden_for_property,
        )

        props = execute_query(
            """
            SELECT DISTINCT a.property_id, wp.address
            FROM cross_site_trend_alerts a
            LEFT JOIN watched_properties wp ON a.property_id = wp.property_id
            WHERE a.alert_status IN ('open', 'acknowledged')
            """,
            database_path=database_path,
        )
        for row in props:
            pid = row["property_id"]
            burden = calculate_alert_burden_for_property(pid, database_path)
            if burden.alert_burden_label in high_burden_labels:
                addr = row["address"] or f"property {pid}"
                issues.append(CrossSiteAlertHygieneIssue(
                    category="high_alert_burden_property",
                    severity="high",
                    property_id=pid,
                    burden_label=burden.alert_burden_label,
                    alert_age_days=burden.oldest_open_alert_age_days,
                    message=(
                        f"Property {addr} has {burden.alert_burden_label} "
                        f"alert burden ({burden.open_alert_count} open)"
                    ),
                    recommended_action=(
                        "Export triage CSV for this property and "
                        "batch-review open alerts"
                    ),
                ))
    except Exception as e:
        logger.error(f"Error identifying high burden properties: {e}")
    return issues


def identify_repeated_unresolved_patterns(
    database_path: Optional[str] = None,
    threshold: int = 2,
) -> List[CrossSiteAlertHygieneIssue]:
    """Identify repeated unresolved alert patterns.

    Args:
        database_path: Optional database path.
        threshold: Minimum count to flag a repeated pattern.

    Returns:
        List of hygiene issues for repeated unresolved patterns.
    """
    if not table_exists("cross_site_trend_alerts", database_path):
        return []

    issues: List[CrossSiteAlertHygieneIssue] = []
    try:
        # Find properties with open/acknowledged alerts grouped by type
        query = """
        SELECT a.property_id, a.alert_type, COUNT(*) as cnt,
               wp.address
        FROM cross_site_trend_alerts a
        LEFT JOIN watched_properties wp ON a.property_id = wp.property_id
        WHERE a.alert_status IN ('open', 'acknowledged')
        GROUP BY a.property_id, a.alert_type
        HAVING cnt >= ?
        ORDER BY cnt DESC
        """
        rows = execute_query(query, (threshold,), database_path=database_path)
        for row in rows:
            addr = row["address"] or f"property {row['property_id']}"
            issues.append(CrossSiteAlertHygieneIssue(
                category="repeated_unresolved_pattern",
                severity="warning",
                property_id=row["property_id"],
                alert_type=row["alert_type"],
                repeated_pattern=row["alert_type"],
                message=(
                    f"Property {addr} has {row['cnt']} unresolved "
                    f"{row['alert_type']} alerts"
                ),
                recommended_action=(
                    "Investigate recurring pattern and resolve "
                    "root cause via fixture update"
                ),
            ))
    except Exception as e:
        logger.error(f"Error identifying repeated unresolved patterns: {e}")
    return issues


# ---------------------------------------------------------------------------
# Next actions
# ---------------------------------------------------------------------------


def generate_alert_hygiene_next_actions(
    summary: CrossSiteAlertHygieneSummary,
) -> List[str]:
    """Generate recommended next actions from hygiene summary.

    Args:
        summary: Hygiene check summary.

    Returns:
        List of recommended next action strings.
    """
    actions: List[str] = []

    if summary.stale_open_alerts > 0:
        actions.append(
            f"Export triage CSV to review {summary.stale_open_alerts} "
            f"stale open alert(s): "
            f"marketsentry export-cross-site-alert-triage --status open"
        )

    if summary.high_burden_properties > 0:
        actions.append(
            f"Review {summary.high_burden_properties} high-burden "
            f"property/properties: "
            f"marketsentry cross-site-alert-analytics-summary"
        )

    if summary.needs_reparse_pending > 0:
        actions.append(
            f"Re-parse fixtures for {summary.needs_reparse_pending} "
            f"alert(s) marked needs_reparse"
        )

    if summary.needs_manual_review_pending > 0:
        actions.append(
            f"Manually review {summary.needs_manual_review_pending} "
            f"alert(s) marked needs_manual_review"
        )

    if summary.stale_acknowledged_alerts > 0:
        actions.append(
            f"Resolve or archive {summary.stale_acknowledged_alerts} "
            f"old acknowledged alert(s)"
        )

    if summary.resolved_archive_candidates > 0:
        actions.append(
            f"Review {summary.resolved_archive_candidates} old resolved "
            f"alert(s) for archive: "
            f"marketsentry export-cross-site-alert-archive-candidates "
            f"or marketsentry export-cross-site-alert-expiration-approval"
        )

    if summary.repeated_unresolved_patterns > 0:
        actions.append(
            f"Investigate {summary.repeated_unresolved_patterns} "
            f"repeated unresolved pattern(s)"
        )

    if not actions:
        actions.append("No hygiene issues found. Alert state is healthy.")

    return actions


# ---------------------------------------------------------------------------
# Main hygiene check
# ---------------------------------------------------------------------------


def run_cross_site_alert_hygiene_check(
    database_path: Optional[str] = None,
    config: Optional[CrossSiteAlertHygieneConfig] = None,
    exports_dir: Optional[str] = None,
) -> CrossSiteAlertHygieneRunResult:
    """Run a full alert hygiene check.

    Args:
        database_path: Optional database path.
        config: Optional hygiene configuration.
        exports_dir: Optional exports directory.

    Returns:
        CrossSiteAlertHygieneRunResult with issues and summary.
    """
    if config is None:
        config = CrossSiteAlertHygieneConfig()

    result = CrossSiteAlertHygieneRunResult()
    all_issues: List[CrossSiteAlertHygieneIssue] = []

    # Collect issues from each check
    all_issues.extend(
        identify_stale_open_alerts(database_path, config.open_stale_days)
    )
    all_issues.extend(
        identify_old_acknowledged_alerts(
            database_path, config.acknowledged_stale_days
        )
    )
    all_issues.extend(
        identify_old_resolved_alerts(
            database_path, config.resolved_archive_days
        )
    )
    all_issues.extend(
        identify_needs_reparse_alerts(
            database_path, config.needs_reparse_stale_days
        )
    )
    all_issues.extend(
        identify_needs_manual_review_alerts(
            database_path, config.needs_manual_review_stale_days
        )
    )
    all_issues.extend(
        identify_high_burden_properties(
            database_path, config.high_burden_labels
        )
    )
    all_issues.extend(
        identify_repeated_unresolved_patterns(
            database_path, config.repeated_unresolved_threshold
        )
    )

    # Assign issue IDs
    for i, issue in enumerate(all_issues, 1):
        issue.issue_id = i

    result.issues = all_issues

    # Build summary
    summary = CrossSiteAlertHygieneSummary()
    summary.total_issues = len(all_issues)

    sev_counts: Dict[str, int] = {}
    cat_counts: Dict[str, int] = {}

    for issue in all_issues:
        sev_counts[issue.severity] = sev_counts.get(issue.severity, 0) + 1
        cat_counts[issue.category] = cat_counts.get(issue.category, 0) + 1

        if issue.category == "stale_open_alert":
            summary.stale_open_alerts += 1
        elif issue.category == "stale_acknowledged_alert":
            summary.stale_acknowledged_alerts += 1
        elif issue.category == "resolved_archive_candidate":
            summary.resolved_archive_candidates += 1
        elif issue.category == "needs_reparse_pending":
            summary.needs_reparse_pending += 1
        elif issue.category == "needs_manual_review_pending":
            summary.needs_manual_review_pending += 1
        elif issue.category == "high_alert_burden_property":
            summary.high_burden_properties += 1
        elif issue.category == "repeated_unresolved_pattern":
            summary.repeated_unresolved_patterns += 1

    summary.issues_by_severity = sev_counts
    summary.issues_by_category = cat_counts
    summary.next_actions = generate_alert_hygiene_next_actions(summary)

    result.summary = summary
    return result


# ---------------------------------------------------------------------------
# Report export
# ---------------------------------------------------------------------------


def export_cross_site_alert_hygiene_report(
    database_path: Optional[str] = None,
    output_path: Optional[str] = None,
    config: Optional[CrossSiteAlertHygieneConfig] = None,
    exports_dir: Optional[str] = None,
    report_format: str = "csv",
) -> CrossSiteAlertHygieneRunResult:
    """Run hygiene check and export report.

    Args:
        database_path: Optional database path.
        output_path: Optional output file path.
        config: Optional hygiene configuration.
        exports_dir: Optional exports directory.
        report_format: csv, md, or both.

    Returns:
        CrossSiteAlertHygieneRunResult with report paths.
    """
    result = run_cross_site_alert_hygiene_check(
        database_path, config, exports_dir,
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(exports_dir) if exports_dir else Path("data/exports")
    out_dir.mkdir(parents=True, exist_ok=True)

    # CSV export
    if report_format in ("csv", "both"):
        csv_path = output_path or str(
            out_dir / f"cross_site_alert_hygiene_{ts}.csv"
        )
        _write_csv(result.issues, csv_path)
        result.csv_path = csv_path
        logger.info(
            f"Exported {len(result.issues)} hygiene issues to {csv_path}"
        )

    # Markdown export
    if report_format in ("md", "both"):
        md_path = str(out_dir / f"cross_site_alert_hygiene_{ts}.md")
        _write_markdown(result, md_path)
        result.md_path = md_path
        logger.info(f"Exported hygiene report to {md_path}")

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _age_days(created_at_str: Optional[str]) -> Optional[int]:
    """Calculate age in days from a timestamp string."""
    if not created_at_str:
        return None
    try:
        created = datetime.fromisoformat(str(created_at_str))
        delta = datetime.now() - created
        return max(0, delta.days)
    except (ValueError, TypeError):
        return None


def _write_csv(issues: List[CrossSiteAlertHygieneIssue], path: str) -> None:
    """Write hygiene issues to CSV."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HYGIENE_CSV_FIELDNAMES)
        writer.writeheader()
        for issue in issues:
            writer.writerow({
                "issue_id": issue.issue_id,
                "category": issue.category,
                "severity": issue.severity,
                "property_id": issue.property_id or "",
                "candidate_id": issue.candidate_id or "",
                "alert_id": issue.alert_id or "",
                "alert_type": issue.alert_type or "",
                "alert_status": issue.alert_status or "",
                "alert_age_days": issue.alert_age_days if issue.alert_age_days is not None else "",
                "burden_label": issue.burden_label or "",
                "repeated_pattern": issue.repeated_pattern or "",
                "message": issue.message,
                "recommended_action": issue.recommended_action,
                "source_context": issue.source_context or "",
                "created_at": issue.created_at or "",
            })


def _write_markdown(
    result: CrossSiteAlertHygieneRunResult,
    path: str,
) -> None:
    """Write hygiene report as Markdown."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    s = result.summary
    lines = [
        "# Cross-Site Alert Hygiene Report",
        "",
        f"Generated: {result.run_date.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- Total issues: {s.total_issues}",
        f"- Stale open alerts: {s.stale_open_alerts}",
        f"- Stale acknowledged alerts: {s.stale_acknowledged_alerts}",
        f"- Resolved archive candidates: {s.resolved_archive_candidates}",
        f"- Needs reparse pending: {s.needs_reparse_pending}",
        f"- Needs manual review pending: {s.needs_manual_review_pending}",
        f"- High burden properties: {s.high_burden_properties}",
        f"- Repeated unresolved patterns: {s.repeated_unresolved_patterns}",
        "",
    ]

    if s.issues_by_severity:
        lines.append("## Issues by Severity")
        lines.append("")
        for sev in ["critical", "high", "warning", "info"]:
            if sev in s.issues_by_severity:
                lines.append(f"- {sev}: {s.issues_by_severity[sev]}")
        lines.append("")

    # High-priority issues
    high_issues = [
        i for i in result.issues
        if i.severity in ("critical", "high")
    ]
    if high_issues:
        lines.append("## High-Priority Issues")
        lines.append("")
        for issue in high_issues:
            lines.append(
                f"- [{issue.severity}] {issue.message}"
            )
        lines.append("")

    # Recommended next actions
    if s.next_actions:
        lines.append("## Recommended Next Actions")
        lines.append("")
        for action in s.next_actions:
            lines.append(f"- {action}")
        lines.append("")

    # Affected properties
    pids = sorted(set(
        i.property_id for i in result.issues
        if i.property_id is not None
    ))
    if pids:
        lines.append("## Affected Properties")
        lines.append("")
        for pid in pids:
            lines.append(f"- Property {pid}")
        lines.append("")

    lines.append(
        "---\n\nThis is a neutral operational review aid. "
        "It is not a purchase recommendation.\n"
    )

    with open(output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
