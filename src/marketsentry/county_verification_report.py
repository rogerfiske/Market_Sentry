"""County verification report generation.

Generates CSV reports showing county verification results, including:
- County transfer events that may support Effective DOM resets
- Churn Index metrics that remain reportable even when county_reset_supported is true

CRITICAL: County-confirmed transfers may reset Effective DOM, but churn metrics
are preserved separately and remain available for analysis.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from marketsentry.config import config
from marketsentry.county_verification import verify_effective_dom_reset
from marketsentry.database import execute_query
from marketsentry.logging_config import logger
from marketsentry.models import CountyVerificationReportRow


def export_county_verification_report(
    output_path: Optional[str] = None, database_path: Optional[str] = None
) -> int:
    """
    Export county verification report to CSV.

    The report includes:
    - Property identification and current data
    - Effective DOM and churn metrics
    - County transfer verification results
    - Churn Index (preserved even when county_reset_supported is true)

    Args:
        output_path: Optional output CSV path (auto-generated if not specified)
        database_path: Optional database path

    Returns:
        Number of properties exported
    """
    # Generate output path if not specified
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(
            Path(config.export_path) / f"county_verification_{timestamp}.csv"
        )

    # Ensure export directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Exporting county verification report to {output_path}")

    # Get watched properties with county verification
    properties = _get_properties_with_county_verification(database_path)

    if not properties:
        logger.warning("No watched properties found for county verification export")
        return 0

    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "property_id",
            "candidate_id",
            "address",
            "city",
            "zip",
            "apn",
            "redfin_url",
            "current_price",
            "effective_dom",
            "displayed_dom",
            "listing_churn_count",
            "dom_reset_count",
            "sale_rent_alternation_count",
            "recent_churn_index",
            "recent_churn_lookback_years",
            "recent_churn_event_count",
            "recent_dom_reset_count",
            "recent_sale_rent_alternation_count",
            "churn_preserved_after_transfer",
            "county_records_seen",
            "county_transfer_found",
            "county_transfer_date",
            "county_transfer_record_type",
            "county_transfer_document_number",
            "county_transfer_confidence",
            "county_reset_supported",
            "assessor_seen",
            "recorder_seen",
            "tax_collector_seen",
            "permit_seen",
            "assessed_value",
            "latest_permit_type",
            "latest_permit_status",
            "verification_notes",
            "user_notes",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for prop in properties:
            # Convert to dict for CSV writing
            row_dict = {
                "property_id": prop.property_id,
                "candidate_id": prop.candidate_id,
                "address": prop.address,
                "city": prop.city,
                "zip": prop.zip,
                "apn": prop.apn,
                "redfin_url": prop.redfin_url,
                "current_price": prop.current_price,
                "effective_dom": prop.effective_dom,
                "displayed_dom": prop.displayed_dom,
                "listing_churn_count": prop.listing_churn_count,
                "dom_reset_count": prop.dom_reset_count,
                "sale_rent_alternation_count": prop.sale_rent_alternation_count,
                "recent_churn_index": prop.recent_churn_index,
                "recent_churn_lookback_years": prop.recent_churn_lookback_years,
                "recent_churn_event_count": prop.recent_churn_event_count,
                "recent_dom_reset_count": prop.recent_dom_reset_count,
                "recent_sale_rent_alternation_count": prop.recent_sale_rent_alternation_count,
                "churn_preserved_after_transfer": prop.churn_preserved_after_transfer,
                "county_records_seen": prop.county_records_seen,
                "county_transfer_found": prop.county_transfer_found,
                "county_transfer_date": prop.county_transfer_date.isoformat()
                if prop.county_transfer_date
                else None,
                "county_transfer_record_type": prop.county_transfer_record_type,
                "county_transfer_document_number": prop.county_transfer_document_number,
                "county_transfer_confidence": prop.county_transfer_confidence,
                "county_reset_supported": prop.county_reset_supported,
                "assessor_seen": prop.assessor_seen,
                "recorder_seen": prop.recorder_seen,
                "tax_collector_seen": prop.tax_collector_seen,
                "permit_seen": prop.permit_seen,
                "assessed_value": prop.assessed_value,
                "latest_permit_type": prop.latest_permit_type,
                "latest_permit_status": prop.latest_permit_status,
                "verification_notes": prop.verification_notes,
                "user_notes": prop.user_notes,
            }

            writer.writerow(row_dict)

    logger.info(f"Exported {len(properties)} properties to {output_path}")
    return len(properties)


def _get_properties_with_county_verification(
    database_path: Optional[str] = None,
) -> List[CountyVerificationReportRow]:
    """
    Get watched properties with county verification data.

    Args:
        database_path: Optional database path

    Returns:
        List of CountyVerificationReportRow objects
    """
    try:
        # Get all active watched properties
        query = """
        SELECT
            p.property_id,
            NULL as candidate_id,
            p.address,
            p.city,
            p.zip,
            p.apn,
            p.redfin_url,
            p.current_price,
            p.effective_dom,
            p.displayed_dom,
            p.listing_churn_count,
            p.dom_reset_count,
            p.sale_rent_alternation_count,
            p.user_notes
        FROM watched_properties p
        WHERE p.active_watch_status = 1
        ORDER BY p.property_id
        """

        results = execute_query(query, database_path=database_path)
        properties = []

        for row in results:
            prop_data = dict(row)
            property_id = prop_data["property_id"]

            # Get county verification for this property
            # Use a reasonable lookback window (e.g., last 5 years)
            from datetime import date, timedelta

            cycle_end = date.today()
            cycle_start = cycle_end - timedelta(days=365 * 5)

            verification_result = verify_effective_dom_reset(
                property_id, cycle_start, cycle_end, database_path
            )

            # Calculate Churn Index placeholder
            churn_index_data = _calculate_churn_index_placeholder(prop_data)

            # Build report row
            report_row = CountyVerificationReportRow(
                property_id=property_id,
                candidate_id=prop_data.get("candidate_id"),
                address=prop_data.get("address"),
                city=prop_data.get("city"),
                zip=prop_data.get("zip"),
                apn=prop_data.get("apn"),
                redfin_url=prop_data.get("redfin_url"),
                current_price=prop_data.get("current_price"),
                effective_dom=prop_data.get("effective_dom"),
                displayed_dom=prop_data.get("displayed_dom"),
                listing_churn_count=prop_data.get("listing_churn_count"),
                dom_reset_count=prop_data.get("dom_reset_count"),
                sale_rent_alternation_count=prop_data.get("sale_rent_alternation_count"),
                recent_churn_index=churn_index_data["churn_index"],
                recent_churn_lookback_years=churn_index_data["lookback_years"],
                recent_churn_event_count=churn_index_data["event_count"],
                recent_dom_reset_count=churn_index_data["dom_reset_count"],
                recent_sale_rent_alternation_count=churn_index_data[
                    "sale_rent_alternation_count"
                ],
                churn_preserved_after_transfer=True,  # Always true - churn is never erased
                county_records_seen=verification_result.county_records_seen,
                county_transfer_found=verification_result.county_transfer_found,
                county_transfer_date=verification_result.county_transfer_date,
                county_transfer_record_type=verification_result.county_transfer_record_type,
                county_transfer_document_number=verification_result.county_transfer_document_number,
                county_transfer_confidence=verification_result.county_transfer_confidence,
                county_reset_supported=verification_result.county_reset_supported,
                assessor_seen=verification_result.assessor_seen,
                recorder_seen=verification_result.recorder_seen,
                tax_collector_seen=verification_result.tax_collector_seen,
                permit_seen=verification_result.permit_seen,
                assessed_value=verification_result.assessed_value,
                latest_permit_type=verification_result.latest_permit_type,
                latest_permit_status=verification_result.latest_permit_status,
                verification_notes=verification_result.verification_notes,
                user_notes=prop_data.get("user_notes"),
            )

            properties.append(report_row)

        return properties

    except Exception as e:
        logger.error(f"Error getting properties with county verification: {e}")
        return []


def _calculate_churn_index_placeholder(prop_data: dict) -> dict:
    """
    Calculate placeholder Churn Index from current metrics.

    This is a simple deterministic placeholder based on existing
    listing_churn_count, dom_reset_count, and sale_rent_alternation_count.

    A date-bounded Churn Index v1 (filtering events to a 3-year window)
    is deferred to a later milestone per the prompt's guidance.

    Args:
        prop_data: Property data dict

    Returns:
        dict with churn_index, lookback_years, event_count, etc.
    """
    listing_churn_count = prop_data.get("listing_churn_count") or 0
    dom_reset_count = prop_data.get("dom_reset_count") or 0
    sale_rent_alternation_count = prop_data.get("sale_rent_alternation_count") or 0

    # Total churn events
    total_churn_events = listing_churn_count + dom_reset_count + sale_rent_alternation_count

    # Simple churn index: weighted sum normalized to 0-10 scale
    # Higher values indicate more instability
    # Weights: listing_churn (1.0), dom_reset (1.5), sale_rent_alternation (2.0)
    weighted_churn = (
        listing_churn_count * 1.0
        + dom_reset_count * 1.5
        + sale_rent_alternation_count * 2.0
    )

    # Normalize to 0-10 scale (assuming max reasonable churn is ~20 weighted points)
    churn_index = min(10.0, (weighted_churn / 20.0) * 10.0)

    return {
        "churn_index": round(churn_index, 2) if churn_index > 0 else None,
        "lookback_years": 3,  # Placeholder - not date-bounded yet
        "event_count": total_churn_events,
        "dom_reset_count": dom_reset_count,
        "sale_rent_alternation_count": sale_rent_alternation_count,
    }
