"""Watchlist monitoring report generation and export."""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from marketsentry.config import config
from marketsentry.database import execute_query
from marketsentry.logging_config import logger
from marketsentry.monitoring import get_latest_snapshot


def export_watchlist_monitoring_report(
    output_path: Optional[str] = None, database_path: Optional[str] = None
) -> int:
    """
    Export watchlist monitoring report to CSV.

    The report includes current property data, previous snapshot data,
    changes detected, and monitoring metadata.

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
            Path(config.data_exports_dir) / f"watchlist_monitoring_{timestamp}.csv"
        )

    # Ensure export directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Exporting watchlist monitoring report to {output_path}")

    # Get watched properties with current data
    properties = _get_watched_properties_with_snapshots(database_path)

    if not properties:
        logger.warning("No watched properties found for export")
        return 0

    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "property_id",
            "watch_priority",
            "active_watch_status",
            "address",
            "city",
            "zip",
            "redfin_url",
            "current_price",
            "previous_price",
            "price_change",
            "price_change_direction",
            "listing_status",
            "previous_listing_status",
            "status_changed",
            "displayed_dom",
            "previous_displayed_dom",
            "effective_dom",
            "previous_effective_dom",
            "effective_dom_delta",
            "effective_dom_v1",
            "effective_dom_v2",
            "effective_dom_delta_v1",
            "effective_dom_delta_v2",
            "previous_effective_dom_v2",
            "effective_dom_v2_change",
            "county_reset_applied",
            "county_reset_date",
            "county_reset_record_type",
            "county_reset_confidence",
            "recent_churn_index",
            "previous_recent_churn_index",
            "recent_churn_index_change",
            "recent_churn_lookback_years",
            "recent_churn_event_count",
            "recent_dom_reset_count",
            "recent_sale_rent_alternation_count",
            "churn_preserved_after_transfer",
            "quiet_score",
            "vibrancy_score",
            "quiet_gatekeeper_result",
            "garage_spaces",
            "gas_service",
            "listing_churn_count",
            "dom_reset_count",
            "sale_rent_alternation_count",
            "price_discrepancy_flag",
            "status_discrepancy_flag",
            "dom_discrepancy_flag",
            "cross_site_confidence_score",
            "change_summary",
            "warning_flags",
            "positive_flags",
            "user_notes",
            "last_checked_date",
            "snapshot_date",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for prop in properties:
            writer.writerow(prop)

    logger.info(f"Exported {len(properties)} properties to {output_path}")
    return len(properties)


def _get_watched_properties_with_snapshots(
    database_path: Optional[str] = None,
) -> List[dict]:
    """
    Get watched properties with current and previous snapshot data.

    Args:
        database_path: Optional database path

    Returns:
        List of property dicts with monitoring data
    """
    try:
        # Get all active watched properties
        query = """
        SELECT
            p.*
        FROM watched_properties p
        WHERE p.active_watch_status = 1
        ORDER BY p.watch_priority DESC NULLS LAST, p.property_id
        """

        results = execute_query(query, database_path=database_path)
        properties = []

        for row in results:
            prop_data = dict(row)
            property_id = prop_data["property_id"]

            # Get latest and previous snapshots
            latest_snapshot = get_latest_snapshot(property_id, database_path)
            previous_snapshot = _get_previous_snapshot(property_id, database_path)

            # Build monitoring row
            monitoring_row = _build_monitoring_row(
                prop_data, latest_snapshot, previous_snapshot
            )
            properties.append(monitoring_row)

        return properties

    except Exception as e:
        logger.error(f"Error getting watched properties with snapshots: {e}")
        return []


def _get_previous_snapshot(
    property_id: int, database_path: Optional[str] = None
) -> Optional[dict]:
    """
    Get the second-most-recent snapshot (previous snapshot).

    Args:
        property_id: Property ID
        database_path: Optional database path

    Returns:
        Previous snapshot dict or None
    """
    try:
        query = """
        SELECT *
        FROM property_observation_snapshots
        WHERE property_id = ?
        ORDER BY snapshot_date DESC
        LIMIT 1 OFFSET 1
        """
        results = execute_query(query, (property_id,), database_path=database_path)

        if results:
            return dict(results[0])

    except Exception as e:
        logger.error(f"Error getting previous snapshot for property {property_id}: {e}")

    return None


def _build_monitoring_row(
    prop_data: dict, latest_snapshot: Optional[object], previous_snapshot: Optional[dict]
) -> dict:
    """
    Build a monitoring report row from property and snapshot data.

    Args:
        prop_data: Current property data from watched_properties
        latest_snapshot: Latest snapshot (ObservationSnapshot or None)
        previous_snapshot: Previous snapshot dict or None

    Returns:
        Dictionary with monitoring report columns
    """
    # Calculate price change
    current_price = prop_data.get("current_price")
    previous_price = (
        previous_snapshot.get("price") if previous_snapshot else None
    )
    price_change = None
    price_change_direction = None

    if current_price and previous_price:
        price_change = current_price - previous_price
        if price_change > 0:
            price_change_direction = "increased"
        elif price_change < 0:
            price_change_direction = "decreased"
        else:
            price_change_direction = "unchanged"

    # Calculate status change
    current_status = (
        latest_snapshot.listing_status if latest_snapshot else None
    )
    previous_status = (
        previous_snapshot.get("listing_status") if previous_snapshot else None
    )
    status_changed = current_status != previous_status if both_not_none(
        current_status, previous_status
    ) else False

    # Calculate DOM changes
    current_displayed_dom = prop_data.get("displayed_dom")
    previous_displayed_dom = (
        previous_snapshot.get("displayed_dom") if previous_snapshot else None
    )
    current_effective_dom = prop_data.get("effective_dom")
    previous_effective_dom = (
        previous_snapshot.get("effective_dom") if previous_snapshot else None
    )

    # Determine quiet gatekeeper result
    quiet_score = prop_data.get("quiet_score")
    quiet_gatekeeper_result = _determine_quiet_gatekeeper(quiet_score)

    # Get discrepancy flags from latest snapshot
    price_discrepancy_flag = (
        latest_snapshot.price_discrepancy_flag if latest_snapshot else False
    )
    status_discrepancy_flag = (
        latest_snapshot.status_discrepancy_flag if latest_snapshot else False
    )
    dom_discrepancy_flag = (
        latest_snapshot.dom_discrepancy_flag if latest_snapshot else False
    )
    cross_site_confidence_score = (
        latest_snapshot.cross_site_confidence_score if latest_snapshot else None
    )

    # Build change summary
    change_summary = _build_change_summary(
        price_change,
        price_change_direction,
        status_changed,
        current_status,
        previous_status,
    )

    # Build warning flags
    warning_flags = _build_warning_flags(
        price_discrepancy_flag,
        status_discrepancy_flag,
        dom_discrepancy_flag,
        quiet_score,
    )

    # Build positive flags
    positive_flags = _build_positive_flags(
        prop_data.get("gas_service"),
        prop_data.get("garage_spaces"),
        quiet_score,
        prop_data.get("vibrancy_score"),
    )

    # Snapshot date
    snapshot_date = (
        latest_snapshot.snapshot_date.isoformat() if latest_snapshot else None
    )

    # Effective DOM v2 fields
    current_effective_dom_v2 = prop_data.get("effective_dom_v2")
    previous_effective_dom_v2 = (
        previous_snapshot.get("effective_dom_v2") if previous_snapshot else None
    )
    effective_dom_v2_change = None
    if current_effective_dom_v2 is not None and previous_effective_dom_v2 is not None:
        effective_dom_v2_change = current_effective_dom_v2 - previous_effective_dom_v2

    # Churn Index change tracking
    current_churn_index = prop_data.get("recent_churn_index")
    previous_churn_index = (
        previous_snapshot.get("recent_churn_index") if previous_snapshot else None
    )
    churn_index_change = None
    if current_churn_index is not None and previous_churn_index is not None:
        churn_index_change = round(current_churn_index - previous_churn_index, 2)

    return {
        "property_id": prop_data.get("property_id"),
        "watch_priority": prop_data.get("watch_priority"),
        "active_watch_status": prop_data.get("active_watch_status"),
        "address": prop_data.get("address"),
        "city": prop_data.get("city"),
        "zip": prop_data.get("zip"),
        "redfin_url": prop_data.get("redfin_url"),
        "current_price": current_price,
        "previous_price": previous_price,
        "price_change": price_change,
        "price_change_direction": price_change_direction,
        "listing_status": current_status,
        "previous_listing_status": previous_status,
        "status_changed": status_changed,
        "displayed_dom": current_displayed_dom,
        "previous_displayed_dom": previous_displayed_dom,
        "effective_dom": current_effective_dom,
        "previous_effective_dom": previous_effective_dom,
        "effective_dom_delta": prop_data.get("effective_dom_delta"),
        "effective_dom_v1": prop_data.get("effective_dom_v1"),
        "effective_dom_v2": current_effective_dom_v2,
        "effective_dom_delta_v1": prop_data.get("effective_dom_delta_v1"),
        "effective_dom_delta_v2": prop_data.get("effective_dom_delta_v2"),
        "previous_effective_dom_v2": previous_effective_dom_v2,
        "effective_dom_v2_change": effective_dom_v2_change,
        "county_reset_applied": prop_data.get("county_reset_applied"),
        "county_reset_date": prop_data.get("county_reset_date"),
        "county_reset_record_type": prop_data.get("county_reset_record_type"),
        "county_reset_confidence": prop_data.get("county_reset_confidence"),
        "recent_churn_index": current_churn_index,
        "previous_recent_churn_index": previous_churn_index,
        "recent_churn_index_change": churn_index_change,
        "recent_churn_lookback_years": prop_data.get("recent_churn_lookback_years"),
        "recent_churn_event_count": prop_data.get("recent_churn_event_count"),
        "recent_dom_reset_count": prop_data.get("recent_dom_reset_count"),
        "recent_sale_rent_alternation_count": prop_data.get("recent_sale_rent_alternation_count"),
        "churn_preserved_after_transfer": prop_data.get("churn_preserved_after_transfer"),
        "quiet_score": quiet_score,
        "vibrancy_score": prop_data.get("vibrancy_score"),
        "quiet_gatekeeper_result": quiet_gatekeeper_result,
        "garage_spaces": prop_data.get("garage_spaces"),
        "gas_service": prop_data.get("gas_service"),
        "listing_churn_count": prop_data.get("listing_churn_count"),
        "dom_reset_count": prop_data.get("dom_reset_count"),
        "sale_rent_alternation_count": prop_data.get("sale_rent_alternation_count"),
        "price_discrepancy_flag": price_discrepancy_flag,
        "status_discrepancy_flag": status_discrepancy_flag,
        "dom_discrepancy_flag": dom_discrepancy_flag,
        "cross_site_confidence_score": cross_site_confidence_score,
        "change_summary": change_summary,
        "warning_flags": warning_flags,
        "positive_flags": positive_flags,
        "user_notes": prop_data.get("user_notes"),
        "last_checked_date": prop_data.get("last_checked_date"),
        "snapshot_date": snapshot_date,
    }


def _determine_quiet_gatekeeper(quiet_score: Optional[float]) -> str:
    """
    Determine quiet gatekeeper result.

    Args:
        quiet_score: Quiet score (0-10)

    Returns:
        Gatekeeper result string
    """
    if quiet_score is None:
        return "unknown"
    elif quiet_score < 7.0:
        return "fail_noise_risk"
    elif quiet_score >= 8.0:
        return "pass_target"
    else:
        return "pass_marginal"


def _build_change_summary(
    price_change: Optional[float],
    price_change_direction: Optional[str],
    status_changed: bool,
    current_status: Optional[str],
    previous_status: Optional[str],
) -> str:
    """
    Build a human-readable change summary.

    Args:
        price_change: Price change amount
        price_change_direction: Price change direction
        status_changed: Whether status changed
        current_status: Current listing status
        previous_status: Previous listing status

    Returns:
        Change summary string
    """
    changes = []

    if price_change and price_change_direction:
        if price_change_direction == "increased":
            changes.append(f"Price +${abs(price_change):,.0f}")
        elif price_change_direction == "decreased":
            changes.append(f"Price -${abs(price_change):,.0f}")

    if status_changed:
        changes.append(f"Status: {previous_status} -> {current_status}")

    if not changes:
        return "No recent changes"

    return "; ".join(changes)


def _build_warning_flags(
    price_discrepancy: bool,
    status_discrepancy: bool,
    dom_discrepancy: bool,
    quiet_score: Optional[float],
) -> str:
    """
    Build warning flags string.

    Args:
        price_discrepancy: Price discrepancy flag
        status_discrepancy: Status discrepancy flag
        dom_discrepancy: DOM discrepancy flag
        quiet_score: Quiet score

    Returns:
        Warning flags string
    """
    warnings = []

    if price_discrepancy:
        warnings.append("Price discrepancy across sites")

    if status_discrepancy:
        warnings.append("Status discrepancy across sites")

    if dom_discrepancy:
        warnings.append("DOM discrepancy across sites")

    if quiet_score is not None and quiet_score < 7.0:
        warnings.append("Quiet score below threshold")

    if not warnings:
        return ""

    return "; ".join(warnings)


def _build_positive_flags(
    gas_service: Optional[bool],
    garage_spaces: Optional[int],
    quiet_score: Optional[float],
    vibrancy_score: Optional[float],
) -> str:
    """
    Build positive flags string.

    Args:
        gas_service: Gas service boolean
        garage_spaces: Number of garage spaces
        quiet_score: Quiet score
        vibrancy_score: Vibrancy score

    Returns:
        Positive flags string
    """
    flags = []

    if gas_service:
        flags.append("Gas service")

    if garage_spaces and garage_spaces >= 2:
        flags.append(f"{garage_spaces}-car garage")

    if quiet_score is not None and quiet_score >= 8.0:
        if vibrancy_score is not None and vibrancy_score <= 2.5:
            flags.append("Excellent quiet/vibrancy")
        else:
            flags.append("High quiet score")

    if not flags:
        return ""

    return "; ".join(flags)


def both_not_none(a, b) -> bool:
    """Check if both values are not None."""
    return a is not None and b is not None
