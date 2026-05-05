"""Compare property data across multiple real estate sites."""

from typing import Dict, List, Optional

from marketsentry.database import execute_query
from marketsentry.logging_config import logger
from marketsentry.models import CrossSiteComparisonResult


def compare_property_cross_site(
    property_id: int, database_path: Optional[str] = None
) -> CrossSiteComparisonResult:
    """
    Compare property data across Redfin and cross-site observations.

    Detects discrepancies in:
    - Price (> $10,000 difference)
    - Listing status (conflicting statuses)
    - DOM (> 30 days difference)

    Args:
        property_id: Watched property ID
        database_path: Optional database path

    Returns:
        CrossSiteComparisonResult with comparison data and discrepancy flags
    """
    result = CrossSiteComparisonResult(property_id=property_id)

    try:
        # Get Redfin data from watched_properties
        redfin_data = _get_redfin_data(property_id, database_path)

        if redfin_data:
            result.redfin_price = redfin_data.get("current_price")
            result.redfin_dom = redfin_data.get("displayed_dom")
            result.redfin_status = "active"  # Assume active if in watchlist

        # Get cross-site observations
        cross_site_data = _get_cross_site_observations(property_id, database_path)

        # Extract data by source site
        for site, data in cross_site_data.items():
            if site == "zillow":
                result.zillow_price = data.get("price")
                result.zillow_dom = data.get("displayed_dom")
                result.zillow_status = data.get("listing_status")
            elif site == "realtor":
                result.realtor_price = data.get("price")
                result.realtor_dom = data.get("displayed_dom")
                result.realtor_status = data.get("listing_status")
            elif site == "homes":
                result.homes_price = data.get("price")
                result.homes_dom = data.get("displayed_dom")
                result.homes_status = data.get("listing_status")
            elif site == "compass":
                result.compass_price = data.get("price")
                result.compass_dom = data.get("displayed_dom")
                result.compass_status = data.get("listing_status")

        # Detect discrepancies
        result = detect_price_discrepancy(result)
        result = detect_status_discrepancy(result)
        result = detect_dom_discrepancy(result)

        # Build comparison notes
        notes = []
        if result.has_price_discrepancy:
            notes.append("Price discrepancy detected")
        if result.has_status_discrepancy:
            notes.append("Status discrepancy detected")
        if result.has_dom_discrepancy:
            notes.append("DOM discrepancy detected")

        if notes:
            result.comparison_notes = "; ".join(notes)

    except Exception as e:
        logger.error(f"Error comparing property {property_id} cross-site: {e}")
        result.comparison_notes = f"Comparison error: {str(e)}"

    return result


def detect_price_discrepancy(
    comparison: CrossSiteComparisonResult,
) -> CrossSiteComparisonResult:
    """
    Detect price discrepancies across sites.

    Flags discrepancy if any price differs from Redfin by > $10,000.

    Args:
        comparison: CrossSiteComparisonResult with price data

    Returns:
        Updated CrossSiteComparisonResult with price discrepancy flags
    """
    threshold = 10000.0

    if not comparison.redfin_price:
        return comparison

    discrepancies = []
    prices = {
        "Redfin": comparison.redfin_price,
        "Zillow": comparison.zillow_price,
        "Realtor": comparison.realtor_price,
        "Homes": comparison.homes_price,
        "Compass": comparison.compass_price,
    }

    # Compare each site to Redfin
    for site, price in prices.items():
        if site == "Redfin" or not price:
            continue

        diff = abs(price - comparison.redfin_price)
        if diff > threshold:
            discrepancies.append(
                f"{site} price ${price:,.0f} differs from Redfin by ${diff:,.0f}"
            )

    if discrepancies:
        comparison.has_price_discrepancy = True
        comparison.price_discrepancy_details = "; ".join(discrepancies)

    return comparison


def detect_status_discrepancy(
    comparison: CrossSiteComparisonResult,
) -> CrossSiteComparisonResult:
    """
    Detect listing status discrepancies across sites.

    Flags discrepancy if any status conflicts (e.g., active vs sold).

    Args:
        comparison: CrossSiteComparisonResult with status data

    Returns:
        Updated CrossSiteComparisonResult with status discrepancy flags
    """
    statuses = []

    if comparison.redfin_status:
        statuses.append(("Redfin", comparison.redfin_status))
    if comparison.zillow_status:
        statuses.append(("Zillow", comparison.zillow_status))
    if comparison.realtor_status:
        statuses.append(("Realtor", comparison.realtor_status))
    if comparison.homes_status:
        statuses.append(("Homes", comparison.homes_status))
    if comparison.compass_status:
        statuses.append(("Compass", comparison.compass_status))

    if len(statuses) < 2:
        return comparison  # Need at least 2 to compare

    # Normalize statuses for comparison
    normalized = [(site, _normalize_status(status)) for site, status in statuses]

    # Check for conflicts
    unique_statuses = set([status for _, status in normalized])

    # If we have both active and sold/pending, that's a discrepancy
    if "active" in unique_statuses and ("sold" in unique_statuses or "pending" in unique_statuses):
        comparison.has_status_discrepancy = True
        details = [f"{site}: {status}" for site, status in statuses]
        comparison.status_discrepancy_details = "; ".join(details)

    return comparison


def detect_dom_discrepancy(
    comparison: CrossSiteComparisonResult,
) -> CrossSiteComparisonResult:
    """
    Detect Days on Market discrepancies across sites.

    Flags discrepancy if any DOM differs from Redfin by > 30 days.

    Args:
        comparison: CrossSiteComparisonResult with DOM data

    Returns:
        Updated CrossSiteComparisonResult with DOM discrepancy flags
    """
    threshold = 30

    if not comparison.redfin_dom:
        return comparison

    discrepancies = []
    doms = {
        "Redfin": comparison.redfin_dom,
        "Zillow": comparison.zillow_dom,
        "Realtor": comparison.realtor_dom,
        "Homes": comparison.homes_dom,
        "Compass": comparison.compass_dom,
    }

    # Compare each site to Redfin
    for site, dom in doms.items():
        if site == "Redfin" or not dom:
            continue

        diff = abs(dom - comparison.redfin_dom)
        if diff > threshold:
            discrepancies.append(
                f"{site} DOM {dom} differs from Redfin by {diff} days"
            )

    if discrepancies:
        comparison.has_dom_discrepancy = True
        comparison.dom_discrepancy_details = "; ".join(discrepancies)

    return comparison


def _get_redfin_data(
    property_id: int, database_path: Optional[str] = None
) -> Optional[Dict]:
    """
    Get Redfin data for property from watched_properties table.

    Args:
        property_id: Property ID
        database_path: Optional database path

    Returns:
        Dictionary with Redfin data or None
    """
    try:
        query = """
        SELECT current_price, displayed_dom
        FROM watched_properties
        WHERE property_id = ?
        """

        result = execute_query(query, (property_id,), database_path=database_path)

        if result:
            return dict(result[0])

    except Exception as e:
        logger.error(f"Error getting Redfin data for property {property_id}: {e}")

    return None


def _get_cross_site_observations(
    property_id: int, database_path: Optional[str] = None
) -> Dict[str, Dict]:
    """
    Get latest cross-site observations for property.

    Args:
        property_id: Property ID
        database_path: Optional database path

    Returns:
        Dictionary mapping source_site to observation data
    """
    observations = {}

    try:
        # Get latest observation from each source site
        query = """
        SELECT source_site, price, displayed_dom, listing_status
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
                "displayed_dom": row["displayed_dom"],
                "listing_status": row["listing_status"],
            }

    except Exception as e:
        logger.error(
            f"Error getting cross-site observations for property {property_id}: {e}"
        )

    return observations


def _normalize_status(status: Optional[str]) -> str:
    """
    Normalize listing status for comparison.

    Args:
        status: Listing status string

    Returns:
        Normalized status (active, sold, pending, off_market)
    """
    if not status:
        return "unknown"

    status_lower = status.lower()

    if "sold" in status_lower:
        return "sold"
    elif "pending" in status_lower:
        return "pending"
    elif "rent" in status_lower:
        return "rental"
    elif "off" in status_lower:
        return "off_market"
    elif "sale" in status_lower or "active" in status_lower:
        return "active"
    else:
        return "unknown"
