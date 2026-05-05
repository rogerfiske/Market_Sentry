"""Effective DOM v2 recalculation workflow.

Computes v2 metrics for candidates and watched properties with county reset integration.
"""

from typing import Optional

from marketsentry.database import execute_query
from marketsentry.effective_dom_v2_calculator import calculate_effective_dom_v2
from marketsentry.logging_config import logger
from marketsentry.models import (
    CountyRecordObservation,
    CountyResetIntegrationResult,
    ListingEvent,
)


def recalc_effective_dom_v2(
    database_path: Optional[str] = None,
) -> CountyResetIntegrationResult:
    """
    Recalculate Effective DOM v2 for all watched properties.

    This workflow:
    1. Reads watched properties
    2. Reads listing events for each property
    3. Reads county records for each property
    4. Computes v2 metrics with county reset support
    5. Returns result summary (report-only, no database updates)

    Args:
        database_path: Optional database path

    Returns:
        CountyResetIntegrationResult with computation summary
    """
    result = CountyResetIntegrationResult()

    try:
        # Get all active watched properties
        query = """
        SELECT property_id, displayed_dom
        FROM watched_properties
        WHERE active_watch_status = 1
        """

        properties = execute_query(query, database_path=database_path)
        result.properties_scanned = len(properties)

        for prop in properties:
            property_id = prop["property_id"]
            displayed_dom = prop["displayed_dom"]

            # Get listing events
            events_query = """
            SELECT *
            FROM listing_events
            WHERE property_id = ?
            ORDER BY event_date
            """

            event_rows = execute_query(events_query, (property_id,), database_path=database_path)
            events = [ListingEvent(**dict(row)) for row in event_rows]

            # Get county records
            county_query = """
            SELECT *
            FROM county_record_observations
            WHERE property_id = ?
            ORDER BY record_date
            """

            county_rows = execute_query(county_query, (property_id,), database_path=database_path)
            county_records = [CountyRecordObservation(**dict(row)) for row in county_rows]

            if county_records:
                result.county_transfers_considered += len(county_records)

            # Calculate v2 metrics
            v2_metrics = calculate_effective_dom_v2(events, county_records, displayed_dom)

            if v2_metrics.county_reset_applied:
                result.county_resets_applied += 1

            # Count as record updated (report-only)
            result.records_updated += 1

            # Churn metrics are always preserved
            if v2_metrics.churn_preserved_after_transfer:
                result.churn_metrics_preserved += 1

        logger.info(
            f"Effective DOM v2 recalculation complete: {result.properties_scanned} scanned, "
            f"{result.county_resets_applied} resets applied"
        )

    except Exception as e:
        logger.error(f"Error in Effective DOM v2 recalculation: {e}")
        result.errors.append(f"Recalculation error: {str(e)}")

    return result
