"""Effective DOM v2 report generation with county reset integration.

Generates CSV reports showing v1 vs v2 metrics, county reset information,
and preserved churn metrics.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from marketsentry.config import config
from marketsentry.database import execute_query
from marketsentry.effective_dom_v2_calculator import calculate_effective_dom_v2
from marketsentry.logging_config import logger
from marketsentry.models import (
    CountyRecordObservation,
    EffectiveDomComparisonRow,
    ListingEvent,
)


def export_effective_dom_v2_report(
    output_path: Optional[str] = None, database_path: Optional[str] = None
) -> int:
    """
    Export Effective DOM v2 comparison report to CSV.

    The report includes:
    - Property identification
    - Effective DOM v1 and v2 metrics
    - County reset information
    - Pre/post reset exposure metrics
    - Churn Index (preserved after reset)
    - Quiet/Vibrancy scores

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
            Path(config.export_path) / f"effective_dom_v2_{timestamp}.csv"
        )

    # Ensure export directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Exporting Effective DOM v2 report to {output_path}")

    # Get properties with v2 metrics
    properties = _get_properties_with_v2_metrics(database_path)

    if not properties:
        logger.warning("No properties found for Effective DOM v2 export")
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
            "displayed_dom",
            "effective_dom_v1",
            "effective_dom_v2",
            "effective_dom_delta_v1",
            "effective_dom_delta_v2",
            "county_reset_applied",
            "county_reset_date",
            "county_reset_record_type",
            "county_reset_record_id",
            "county_reset_confidence",
            "pre_reset_calendar_exposure_dom",
            "post_reset_calendar_exposure_dom",
            "pre_reset_sale_cycle_dom",
            "post_reset_sale_cycle_dom",
            "pre_reset_rent_sale_exposure_dom",
            "post_reset_rent_sale_exposure_dom",
            "listing_churn_count",
            "dom_reset_count",
            "sale_rent_alternation_count",
            "price_change_count",
            "recent_churn_index",
            "recent_churn_lookback_years",
            "recent_churn_event_count",
            "recent_dom_reset_count",
            "recent_sale_rent_alternation_count",
            "churn_preserved_after_transfer",
            "quiet_score",
            "vibrancy_score",
            "quiet_gatekeeper_result",
            "gas_service",
            "garage_spaces",
            "user_notes",
            "notes",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for prop in properties:
            # Convert model to dict for CSV writing
            row_dict = {
                "property_id": prop.property_id,
                "candidate_id": prop.candidate_id,
                "address": prop.address,
                "city": prop.city,
                "zip": prop.zip,
                "apn": prop.apn,
                "redfin_url": prop.redfin_url,
                "current_price": prop.current_price,
                "displayed_dom": prop.displayed_dom,
                "effective_dom_v1": prop.effective_dom_v1,
                "effective_dom_v2": prop.effective_dom_v2,
                "effective_dom_delta_v1": prop.effective_dom_delta_v1,
                "effective_dom_delta_v2": prop.effective_dom_delta_v2,
                "county_reset_applied": prop.county_reset_applied,
                "county_reset_date": prop.county_reset_date.isoformat()
                if prop.county_reset_date
                else None,
                "county_reset_record_type": prop.county_reset_record_type,
                "county_reset_record_id": prop.county_reset_record_id,
                "county_reset_confidence": prop.county_reset_confidence,
                "pre_reset_calendar_exposure_dom": prop.pre_reset_calendar_exposure_dom,
                "post_reset_calendar_exposure_dom": prop.post_reset_calendar_exposure_dom,
                "pre_reset_sale_cycle_dom": prop.pre_reset_sale_cycle_dom,
                "post_reset_sale_cycle_dom": prop.post_reset_sale_cycle_dom,
                "pre_reset_rent_sale_exposure_dom": prop.pre_reset_rent_sale_exposure_dom,
                "post_reset_rent_sale_exposure_dom": prop.post_reset_rent_sale_exposure_dom,
                "listing_churn_count": prop.listing_churn_count,
                "dom_reset_count": prop.dom_reset_count,
                "sale_rent_alternation_count": prop.sale_rent_alternation_count,
                "price_change_count": prop.price_change_count,
                "recent_churn_index": prop.recent_churn_index,
                "recent_churn_lookback_years": prop.recent_churn_lookback_years,
                "recent_churn_event_count": prop.recent_churn_event_count,
                "recent_dom_reset_count": prop.recent_dom_reset_count,
                "recent_sale_rent_alternation_count": prop.recent_sale_rent_alternation_count,
                "churn_preserved_after_transfer": prop.churn_preserved_after_transfer,
                "quiet_score": prop.quiet_score,
                "vibrancy_score": prop.vibrancy_score,
                "quiet_gatekeeper_result": prop.quiet_gatekeeper_result,
                "gas_service": prop.gas_service,
                "garage_spaces": prop.garage_spaces,
                "user_notes": prop.user_notes,
                "notes": prop.notes,
            }

            writer.writerow(row_dict)

    logger.info(f"Exported {len(properties)} properties to {output_path}")
    return len(properties)


def _get_properties_with_v2_metrics(
    database_path: Optional[str] = None,
) -> List[EffectiveDomComparisonRow]:
    """
    Get watched properties with v2 metrics calculated.

    Args:
        database_path: Optional database path

    Returns:
        List of EffectiveDomComparisonRow objects
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
            p.displayed_dom,
            p.effective_dom,
            p.listing_churn_count,
            p.dom_reset_count,
            p.sale_rent_alternation_count,
            p.quiet_score,
            p.vibrancy_score,
            p.gas_service,
            p.garage_spaces,
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

            # Get listing events
            events_query = """
            SELECT *
            FROM listing_events
            WHERE property_id = ?
            ORDER BY event_date
            """

            event_rows = execute_query(events_query, (property_id,), database_path=database_path)
            events = [ListingEvent(**dict(e)) for e in event_rows]

            # Get county records
            county_query = """
            SELECT *
            FROM county_record_observations
            WHERE property_id = ?
            ORDER BY record_date
            """

            county_rows = execute_query(county_query, (property_id,), database_path=database_path)
            county_records = [CountyRecordObservation(**dict(c)) for c in county_rows]

            # Calculate v2 metrics
            v2_metrics = calculate_effective_dom_v2(
                events, county_records, prop_data.get("displayed_dom")
            )

            # Determine quiet gatekeeper result
            quiet_score = prop_data.get("quiet_score")
            if quiet_score is None:
                quiet_gatekeeper_result = "unknown"
            elif quiet_score < 7.0:
                quiet_gatekeeper_result = "fail_noise_risk"
            elif quiet_score >= 8.0:
                quiet_gatekeeper_result = "pass_target"
            else:
                quiet_gatekeeper_result = "pass_marginal"

            # Count price changes from events
            price_change_count = len([e for e in events if e.event_type and "price" in e.event_type.lower()])

            # Build comparison row
            comparison_row = EffectiveDomComparisonRow(
                property_id=property_id,
                candidate_id=prop_data.get("candidate_id"),
                address=prop_data.get("address"),
                city=prop_data.get("city"),
                zip=prop_data.get("zip"),
                apn=prop_data.get("apn"),
                redfin_url=prop_data.get("redfin_url"),
                current_price=prop_data.get("current_price"),
                displayed_dom=v2_metrics.displayed_dom,
                effective_dom_v1=v2_metrics.effective_dom_v1,
                effective_dom_v2=v2_metrics.effective_dom_v2,
                effective_dom_delta_v1=v2_metrics.effective_dom_delta_v1,
                effective_dom_delta_v2=v2_metrics.effective_dom_delta_v2,
                county_reset_applied=v2_metrics.county_reset_applied,
                county_reset_date=v2_metrics.county_reset_date,
                county_reset_record_type=v2_metrics.county_reset_record_type,
                county_reset_record_id=v2_metrics.county_reset_record_id,
                county_reset_confidence=v2_metrics.county_reset_confidence,
                pre_reset_calendar_exposure_dom=v2_metrics.pre_reset_calendar_exposure_dom,
                post_reset_calendar_exposure_dom=v2_metrics.post_reset_calendar_exposure_dom,
                pre_reset_sale_cycle_dom=v2_metrics.pre_reset_sale_cycle_dom,
                post_reset_sale_cycle_dom=v2_metrics.post_reset_sale_cycle_dom,
                pre_reset_rent_sale_exposure_dom=v2_metrics.pre_reset_rent_sale_exposure_dom,
                post_reset_rent_sale_exposure_dom=v2_metrics.post_reset_rent_sale_exposure_dom,
                listing_churn_count=v2_metrics.listing_churn_count,
                dom_reset_count=v2_metrics.dom_reset_count,
                sale_rent_alternation_count=v2_metrics.sale_rent_alternation_count,
                price_change_count=price_change_count,
                recent_churn_index=v2_metrics.recent_churn_index,
                recent_churn_lookback_years=v2_metrics.recent_churn_lookback_years,
                recent_churn_event_count=v2_metrics.recent_churn_event_count,
                recent_dom_reset_count=v2_metrics.recent_dom_reset_count,
                recent_sale_rent_alternation_count=v2_metrics.recent_sale_rent_alternation_count,
                churn_preserved_after_transfer=v2_metrics.churn_preserved_after_transfer,
                quiet_score=prop_data.get("quiet_score"),
                vibrancy_score=prop_data.get("vibrancy_score"),
                quiet_gatekeeper_result=quiet_gatekeeper_result,
                gas_service=prop_data.get("gas_service"),
                garage_spaces=prop_data.get("garage_spaces"),
                user_notes=prop_data.get("user_notes"),
            )

            properties.append(comparison_row)

        return properties

    except Exception as e:
        logger.error(f"Error getting properties with v2 metrics: {e}")
        return []
