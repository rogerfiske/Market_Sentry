"""Generate cross-site analytics reports.

Exports confidence-weighted cross-site comparison analytics to CSV.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from marketsentry.cross_site_analytics import analyze_cross_site_observations
from marketsentry.database import execute_query
from marketsentry.logging_config import logger


def export_cross_site_analytics_report(
    database_path: Optional[str] = None,
    output_path: Optional[str] = None,
) -> str:
    """Export cross-site analytics report to CSV.

    Generates a CSV with confidence-weighted agreement scores,
    discrepancy severity, freshness, completeness, and manual
    review priority for all active watched properties.

    Args:
        database_path: Optional database path.
        output_path: Optional output file path.  If None, a
            timestamped file is created in ``data/exports/``.

    Returns:
        Path to the generated CSV file.
    """
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/exports")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"cross_site_analytics_{ts}.csv")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Generating cross-site analytics report: {output_path}")

    try:
        # Get all active watched properties
        properties = _get_active_properties(database_path)

        if not properties:
            logger.warning("No watched properties found for analytics report")
            # Write empty CSV with headers
            _write_csv(output_file, [])
            return str(output_file)

        rows: List[dict] = []
        for prop in properties:
            property_id = prop["property_id"]
            analytics = analyze_cross_site_observations(property_id, database_path)

            row = _analytics_to_row(analytics, prop)
            rows.append(row)

        _write_csv(output_file, rows)
        logger.info(f"Exported {len(rows)} properties to {output_path}")
        return str(output_file)

    except Exception as e:
        logger.error(f"Error generating cross-site analytics report: {e}")
        raise


def _get_active_properties(database_path: Optional[str] = None) -> List[dict]:
    """Get all active watched properties.

    Args:
        database_path: Optional database path.

    Returns:
        List of property dicts.
    """
    try:
        query = """
        SELECT property_id, address, city, zip,
               current_price, displayed_dom
        FROM watched_properties
        WHERE active_watch_status = 1
        ORDER BY address
        """
        results = execute_query(query, database_path=database_path)
        return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"Error getting active properties: {e}")
        return []


def _analytics_to_row(analytics, prop: dict) -> dict:
    """Convert analytics result to a flat CSV row dict.

    Args:
        analytics: CrossSiteAnalyticsResult.
        prop: Property dict from database.

    Returns:
        Flat dictionary suitable for CSV export.
    """
    cm = analytics.confidence_metrics
    ds = analytics.discrepancy_severity

    return {
        "property_id": analytics.property_id,
        "address": analytics.address or prop.get("address"),
        "city": analytics.city or prop.get("city"),
        "zip": analytics.zip or prop.get("zip"),
        "redfin_price": prop.get("current_price"),
        "redfin_dom": prop.get("displayed_dom"),
        "redfin_status": prop.get("listing_status"),
        "weighted_price_agreement_score": (
            analytics.price_agreement.agreement_score
            if analytics.price_agreement else None
        ),
        "weighted_status_agreement_score": (
            analytics.status_agreement.agreement_score
            if analytics.status_agreement else None
        ),
        "weighted_dom_agreement_score": (
            analytics.dom_agreement.agreement_score
            if analytics.dom_agreement else None
        ),
        "weighted_garage_agreement_score": (
            analytics.garage_agreement.agreement_score
            if analytics.garage_agreement else None
        ),
        "weighted_gas_agreement_score": (
            analytics.gas_agreement.agreement_score
            if analytics.gas_agreement else None
        ),
        "source_freshness_score": cm.source_freshness_score if cm else None,
        "source_completeness_score": cm.source_completeness_score if cm else None,
        "source_agreement_score": cm.source_agreement_score if cm else None,
        "overall_cross_site_confidence_score": (
            cm.overall_cross_site_confidence_score if cm else None
        ),
        "discrepancy_severity_score": ds.severity_score if ds else None,
        "discrepancy_severity_label": ds.severity_label if ds else None,
        "cross_site_manual_review_priority": analytics.cross_site_manual_review_priority,
        "contributing_sources": (
            "; ".join(cm.contributing_sources) if cm and cm.contributing_sources else None
        ),
        "low_confidence_sources": (
            "; ".join(cm.low_confidence_sources) if cm and cm.low_confidence_sources else None
        ),
        "stale_sources": (
            "; ".join(cm.stale_sources) if cm and cm.stale_sources else None
        ),
        "parse_warning_sources": (
            "; ".join(cm.parse_warning_sources) if cm and cm.parse_warning_sources else None
        ),
    }


FIELDNAMES = [
    "property_id",
    "address",
    "city",
    "zip",
    "redfin_price",
    "redfin_dom",
    "redfin_status",
    "weighted_price_agreement_score",
    "weighted_status_agreement_score",
    "weighted_dom_agreement_score",
    "weighted_garage_agreement_score",
    "weighted_gas_agreement_score",
    "source_freshness_score",
    "source_completeness_score",
    "source_agreement_score",
    "overall_cross_site_confidence_score",
    "discrepancy_severity_score",
    "discrepancy_severity_label",
    "cross_site_manual_review_priority",
    "contributing_sources",
    "low_confidence_sources",
    "stale_sources",
    "parse_warning_sources",
]


def _write_csv(output_file: Path, rows: List[dict]) -> None:
    """Write analytics rows to CSV.

    Args:
        output_file: Output file path.
        rows: List of row dicts.
    """
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        if rows:
            writer.writerows(rows)
