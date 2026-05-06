"""Retrieval audit report for Market_Sentry.

Summarizes retrieval audit logs from logs/retrieval_audit/ into
a structured report with counts of decisions, modes, and reasons.

No network calls are performed by this module.
"""

import csv
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Optional

from marketsentry.logging_config import logger


# ---------------------------------------------------------------------------
# Audit report
# ---------------------------------------------------------------------------


def generate_audit_report(
    audit_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a summary report of retrieval audit logs.

    Args:
        audit_dir: Directory containing audit CSV files.
            Defaults to logs/retrieval_audit/.

    Returns:
        Dict with report fields including counts and summaries.
    """
    dir_path = Path(audit_dir or "logs/retrieval_audit")

    report: Dict[str, Any] = {
        "audit_dir": str(dir_path),
        "total_decisions": 0,
        "allowed_count": 0,
        "blocked_count": 0,
        "dry_run_count": 0,
        "live_attempt_count": 0,
        "network_call_true_count": 0,
        "network_call_false_count": 0,
        "sources": Counter(),
        "modes": Counter(),
        "blocked_reasons": Counter(),
        "files_scanned": 0,
    }

    if not dir_path.exists():
        return report

    # Scan all audit CSV files
    audit_files = sorted(dir_path.glob("retrieval_audit_*.csv"))
    report["files_scanned"] = len(audit_files)

    for audit_file in audit_files:
        try:
            with open(audit_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    report["total_decisions"] += 1

                    # Allowed / blocked counts
                    if row.get("allowed", "").lower() == "true":
                        report["allowed_count"] += 1
                    if row.get("blocked", "").lower() == "true":
                        report["blocked_count"] += 1

                    # Dry-run vs live
                    if row.get("dry_run", "").lower() == "true":
                        report["dry_run_count"] += 1
                    else:
                        report["live_attempt_count"] += 1

                    # Network call
                    if row.get("network_call_performed", "").lower() == "true":
                        report["network_call_true_count"] += 1
                    else:
                        report["network_call_false_count"] += 1

                    # Source
                    source = row.get("source_site", "unknown")
                    report["sources"][source] += 1

                    # Mode
                    mode = row.get("retrieval_mode", "unknown")
                    report["modes"][mode] += 1

                    # Blocked reasons
                    if row.get("blocked", "").lower() == "true":
                        reason = row.get("reason", "unspecified")
                        report["blocked_reasons"][reason] += 1

        except (OSError, csv.Error) as e:
            logger.warning(f"Error reading audit file {audit_file}: {e}")
            continue

    # Also scan dry-run approval files
    approval_files = sorted(dir_path.glob("dry_run_approvals_*.csv"))
    for approval_file in approval_files:
        try:
            with open(approval_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    report["total_decisions"] += 1
                    report["dry_run_count"] += 1

                    if row.get("allowed", "").lower() == "true":
                        report["allowed_count"] += 1
                    if row.get("blocked", "").lower() == "true":
                        report["blocked_count"] += 1

                    report["network_call_false_count"] += 1

                    source = row.get("source_site", "unknown")
                    report["sources"][source] += 1
                    report["modes"]["dry_run_approval"] += 1

        except (OSError, csv.Error) as e:
            logger.warning(f"Error reading approval file {approval_file}: {e}")
            continue

    # Convert Counters to dicts for serialization
    report["sources"] = dict(report["sources"])
    report["modes"] = dict(report["modes"])
    report["blocked_reasons"] = dict(report["blocked_reasons"])

    return report
