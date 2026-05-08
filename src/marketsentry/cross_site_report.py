"""Generate cross-site comparison reports."""

import csv
from pathlib import Path
from typing import List, Optional

from marketsentry.cross_site_comparison import compare_property_cross_site
from marketsentry.database import execute_query
from marketsentry.logging_config import logger


def export_cross_site_comparison_report(
    output_path: str, database_path: Optional[str] = None
) -> int:
    """
    Export cross-site comparison report to CSV.

    Generates a comprehensive CSV with:
    - Property information (address, city, zip)
    - Redfin data (price, beds, baths, sqft, DOM, status)
    - Zillow data (price, beds, baths, sqft, DOM, status)
    - Realtor data (price, beds, baths, sqft, DOM, status)
    - Homes data (price, beds, baths, sqft, DOM, status)
    - Compass data (price, beds, baths, sqft, DOM, status)
    - Discrepancy flags (price, status, DOM)

    Args:
        output_path: Path to output CSV file
        database_path: Optional database path

    Returns:
        Number of properties exported
    """
    output_file = Path(output_path)

    logger.info(f"Generating cross-site comparison report: {output_path}")

    try:
        # Get all active watched properties
        properties = _get_watched_properties(database_path)

        if not properties:
            logger.warning("No watched properties found")
            return 0

        # Get cross-site observations for each property
        rows = []
        for prop in properties:
            property_id = prop["property_id"]

            # Get comparison data
            comparison = compare_property_cross_site(property_id, database_path)

            # Get cross-site observations details
            cross_site_obs = _get_cross_site_observation_details(
                property_id, database_path
            )

            # Build row
            row = {
                # Property info
                "property_id": property_id,
                "address": prop["address"],
                "city": prop["city"],
                "zip": prop["zip"],
                # Redfin data
                "redfin_price": comparison.redfin_price,
                "redfin_beds": prop.get("beds"),
                "redfin_baths": prop.get("baths"),
                "redfin_sqft": prop.get("sqft"),
                "redfin_dom": comparison.redfin_dom,
                "redfin_status": comparison.redfin_status,
                # Zillow data
                "zillow_price": comparison.zillow_price,
                "zillow_beds": cross_site_obs.get("zillow", {}).get("beds"),
                "zillow_baths": cross_site_obs.get("zillow", {}).get("baths"),
                "zillow_sqft": cross_site_obs.get("zillow", {}).get("sqft"),
                "zillow_dom": comparison.zillow_dom,
                "zillow_status": comparison.zillow_status,
                # Realtor data
                "realtor_price": comparison.realtor_price,
                "realtor_beds": cross_site_obs.get("realtor", {}).get("beds"),
                "realtor_baths": cross_site_obs.get("realtor", {}).get("baths"),
                "realtor_sqft": cross_site_obs.get("realtor", {}).get("sqft"),
                "realtor_dom": comparison.realtor_dom,
                "realtor_status": comparison.realtor_status,
                # Homes data
                "homes_price": comparison.homes_price,
                "homes_beds": cross_site_obs.get("homes", {}).get("beds"),
                "homes_baths": cross_site_obs.get("homes", {}).get("baths"),
                "homes_sqft": cross_site_obs.get("homes", {}).get("sqft"),
                "homes_dom": comparison.homes_dom,
                "homes_status": comparison.homes_status,
                # Compass data
                "compass_price": comparison.compass_price,
                "compass_beds": cross_site_obs.get("compass", {}).get("beds"),
                "compass_baths": cross_site_obs.get("compass", {}).get("baths"),
                "compass_sqft": cross_site_obs.get("compass", {}).get("sqft"),
                "compass_dom": comparison.compass_dom,
                "compass_status": comparison.compass_status,
                # Discrepancy flags
                "has_price_discrepancy": comparison.has_price_discrepancy,
                "has_status_discrepancy": comparison.has_status_discrepancy,
                "has_dom_discrepancy": comparison.has_dom_discrepancy,
                "price_discrepancy_details": comparison.price_discrepancy_details,
                "status_discrepancy_details": comparison.status_discrepancy_details,
                "dom_discrepancy_details": comparison.dom_discrepancy_details,
                "comparison_notes": comparison.comparison_notes,
                # Parse quality summary
                "lowest_parse_confidence": comparison.lowest_parse_confidence,
                "sources_with_parse_warnings": (
                    "; ".join(comparison.sources_with_parse_warnings)
                    if comparison.sources_with_parse_warnings else None
                ),
                "sources_with_partial_parse": (
                    "; ".join(comparison.sources_with_partial_parse)
                    if comparison.sources_with_partial_parse else None
                ),
            }

            rows.append(row)

        # Write to CSV
        if rows:
            _write_csv(output_file, rows)
            logger.info(f"Exported {len(rows)} properties to {output_path}")

        return len(rows)

    except Exception as e:
        logger.error(f"Error generating cross-site comparison report: {e}")
        raise


def _get_watched_properties(database_path: Optional[str] = None) -> List[dict]:
    """
    Get all active watched properties.

    Args:
        database_path: Optional database path

    Returns:
        List of property dictionaries
    """
    try:
        query = """
        SELECT property_id, address, city, zip, beds, baths, sqft,
               current_price, displayed_dom
        FROM watched_properties
        WHERE active_watch_status = 1
        ORDER BY address
        """

        results = execute_query(query, database_path=database_path)
        return [dict(row) for row in results]

    except Exception as e:
        logger.error(f"Error getting watched properties: {e}")
        return []


def _get_cross_site_observation_details(
    property_id: int, database_path: Optional[str] = None
) -> dict:
    """
    Get detailed cross-site observations for a property.

    Args:
        property_id: Property ID
        database_path: Optional database path

    Returns:
        Dictionary mapping source_site to observation details
    """
    observations = {}

    try:
        # Get latest observation from each source site
        query = """
        SELECT source_site, price, beds, baths, sqft, displayed_dom,
               listing_status, observed_at
        FROM cross_site_observations
        WHERE property_id = ?
        AND observed_at = (
            SELECT MAX(observed_at)
            FROM cross_site_observations
            WHERE property_id = ? AND source_site = cross_site_observations.source_site
        )
        ORDER BY source_site
        """

        results = execute_query(
            query, (property_id, property_id), database_path=database_path
        )

        for row in results:
            observations[row["source_site"]] = {
                "price": row["price"],
                "beds": row["beds"],
                "baths": row["baths"],
                "sqft": row["sqft"],
                "displayed_dom": row["displayed_dom"],
                "listing_status": row["listing_status"],
                "observed_at": row["observed_at"],
            }

    except Exception as e:
        logger.error(
            f"Error getting cross-site observation details for property {property_id}: {e}"
        )

    return observations


def _write_csv(output_file: Path, rows: List[dict]) -> None:
    """
    Write rows to CSV file.

    Args:
        output_file: Path to output CSV file
        rows: List of row dictionaries
    """
    if not rows:
        return

    # Define column order
    fieldnames = [
        # Property info
        "property_id",
        "address",
        "city",
        "zip",
        # Redfin data
        "redfin_price",
        "redfin_beds",
        "redfin_baths",
        "redfin_sqft",
        "redfin_dom",
        "redfin_status",
        # Zillow data
        "zillow_price",
        "zillow_beds",
        "zillow_baths",
        "zillow_sqft",
        "zillow_dom",
        "zillow_status",
        # Realtor data
        "realtor_price",
        "realtor_beds",
        "realtor_baths",
        "realtor_sqft",
        "realtor_dom",
        "realtor_status",
        # Homes data
        "homes_price",
        "homes_beds",
        "homes_baths",
        "homes_sqft",
        "homes_dom",
        "homes_status",
        # Compass data
        "compass_price",
        "compass_beds",
        "compass_baths",
        "compass_sqft",
        "compass_dom",
        "compass_status",
        # Discrepancy flags
        "has_price_discrepancy",
        "has_status_discrepancy",
        "has_dom_discrepancy",
        "price_discrepancy_details",
        "status_discrepancy_details",
        "dom_discrepancy_details",
        "comparison_notes",
        # Parse quality summary
        "lowest_parse_confidence",
        "sources_with_parse_warnings",
        "sources_with_partial_parse",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
