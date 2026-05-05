"""Watchlist monitoring snapshots and change detection."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from marketsentry.cross_site_comparison import compare_property_cross_site
from marketsentry.database import execute_insert, execute_query, execute_update
from marketsentry.logging_config import logger
from marketsentry.models import (
    MonitoringRunResult,
    MonitoringSnapshotResult,
    ObservationSnapshot,
    SnapshotChangeResult,
)


def create_snapshot_for_property(
    property_id: int, database_path: Optional[str] = None
) -> MonitoringSnapshotResult:
    """
    Create a monitoring snapshot for a single watched property.

    This function reads current property data from watched_properties,
    listing_events, and cross_site_observations tables, creates a new
    snapshot, detects changes from the previous snapshot, and stores the
    result.

    Args:
        property_id: Watched property ID
        database_path: Optional database path

    Returns:
        MonitoringSnapshotResult with snapshot creation status and change detection
    """
    result = MonitoringSnapshotResult(property_id=property_id)

    try:
        # Get current property data
        property_data = _get_current_property_data(property_id, database_path)

        if not property_data:
            result.snapshot_skipped = True
            result.skip_reason = "Property not found or inactive"
            result.warnings.append(f"Property {property_id} not found or not active")
            return result

        # Get latest snapshot for comparison
        previous_snapshot = get_latest_snapshot(property_id, database_path)

        # Create current snapshot
        current_snapshot = _build_snapshot_from_property_data(
            property_id, property_data, database_path
        )

        # Check for same-day duplicate if idempotency is enabled
        if previous_snapshot and _is_same_day(
            previous_snapshot.snapshot_date, current_snapshot.snapshot_date
        ):
            # Check if material fields changed
            if not _has_material_changes(previous_snapshot, current_snapshot):
                result.snapshot_skipped = True
                result.skip_reason = "No material changes since last snapshot today"
                logger.info(
                    f"Skipping snapshot for property {property_id}: no material changes"
                )
                return result

        # Store snapshot
        snapshot_id = _store_snapshot(current_snapshot, database_path)
        current_snapshot.snapshot_id = snapshot_id

        result.snapshot_id = snapshot_id
        result.snapshot_created = True

        # Detect changes
        if previous_snapshot:
            change_result = compare_snapshots(previous_snapshot, current_snapshot)
            result.changes_detected = change_result

            # Update watched property last_checked_date
            _update_last_checked_date(property_id, database_path)

            logger.info(
                f"Created snapshot {snapshot_id} for property {property_id} with changes detected"
            )
        else:
            logger.info(
                f"Created initial snapshot {snapshot_id} for property {property_id}"
            )

    except Exception as e:
        logger.error(f"Error creating snapshot for property {property_id}: {e}")
        result.snapshot_skipped = True
        result.skip_reason = f"Error: {str(e)}"
        result.errors.append(str(e))

    return result


def create_snapshots_for_all_watched(
    database_path: Optional[str] = None,
) -> MonitoringRunResult:
    """
    Create monitoring snapshots for all active watched properties.

    Args:
        database_path: Optional database path

    Returns:
        MonitoringRunResult with run statistics
    """
    result = MonitoringRunResult()

    try:
        # Get all active watched properties
        query = """
        SELECT property_id
        FROM watched_properties
        WHERE active_watch_status = 1
        ORDER BY property_id
        """
        properties = execute_query(query, database_path=database_path)

        result.properties_scanned = len(properties)

        for row in properties:
            property_id = row["property_id"]

            # Create snapshot for this property
            snapshot_result = create_snapshot_for_property(property_id, database_path)

            if snapshot_result.snapshot_created:
                result.snapshots_created += 1

                if snapshot_result.changes_detected and snapshot_result.changes_detected.has_changes:
                    result.changes_detected_count += 1

            elif snapshot_result.snapshot_skipped:
                result.snapshots_skipped += 1

            # Collect warnings and errors
            result.warnings.extend(snapshot_result.warnings)
            result.errors.extend(snapshot_result.errors)

        logger.info(
            f"Monitoring run complete: {result.snapshots_created} created, "
            f"{result.snapshots_skipped} skipped, {result.changes_detected_count} with changes"
        )

    except Exception as e:
        logger.error(f"Error in monitoring run: {e}")
        result.errors.append(str(e))

    return result


def get_latest_snapshot(
    property_id: int, database_path: Optional[str] = None
) -> Optional[ObservationSnapshot]:
    """
    Get the latest snapshot for a property.

    Args:
        property_id: Watched property ID
        database_path: Optional database path

    Returns:
        ObservationSnapshot or None if no snapshots exist
    """
    try:
        query = """
        SELECT *
        FROM property_observation_snapshots
        WHERE property_id = ?
        ORDER BY snapshot_date DESC
        LIMIT 1
        """
        results = execute_query(query, (property_id,), database_path=database_path)

        if results:
            row = dict(results[0])
            return ObservationSnapshot(**row)

    except Exception as e:
        logger.error(f"Error getting latest snapshot for property {property_id}: {e}")

    return None


def compare_snapshots(
    previous: Optional[ObservationSnapshot], current: ObservationSnapshot
) -> SnapshotChangeResult:
    """
    Compare two snapshots and detect changes.

    Detects changes in:
    - Price (any difference, direction, and amount)
    - Listing status
    - Displayed DOM
    - Effective DOM
    - Quiet/Vibrancy scores (>= 0.5 difference)
    - Garage spaces
    - Gas service
    - Discrepancy flags

    Args:
        previous: Previous snapshot (can be None for initial snapshot)
        current: Current snapshot

    Returns:
        SnapshotChangeResult with detected changes
    """
    result = SnapshotChangeResult(property_id=current.property_id)

    if not previous:
        result.change_summary = "Initial snapshot"
        return result

    changes = []

    # Price change detection
    if previous.price != current.price:
        result.price_changed = True

        if previous.price and current.price:
            result.price_change_amount = current.price - previous.price

            if result.price_change_amount > 0:
                result.price_increased = True
                changes.append(
                    f"Price increased by ${abs(result.price_change_amount):,.0f} "
                    f"(${previous.price:,.0f} -> ${current.price:,.0f})"
                )
            else:
                result.price_decreased = True
                changes.append(
                    f"Price decreased by ${abs(result.price_change_amount):,.0f} "
                    f"(${previous.price:,.0f} -> ${current.price:,.0f})"
                )
        else:
            changes.append(
                f"Price changed (${previous.price} -> ${current.price})"
            )

    # Status change detection
    if previous.listing_status != current.listing_status:
        result.status_changed = True
        changes.append(
            f"Listing status changed ({previous.listing_status} -> {current.listing_status})"
        )

    # Displayed DOM change detection
    if previous.displayed_dom != current.displayed_dom:
        result.displayed_dom_changed = True
        changes.append(
            f"Displayed DOM changed ({previous.displayed_dom} -> {current.displayed_dom})"
        )

    # Effective DOM change detection
    if previous.effective_dom != current.effective_dom:
        result.effective_dom_changed = True
        changes.append(
            f"Effective DOM changed ({previous.effective_dom} -> {current.effective_dom})"
        )

    # Quiet score change detection (>= 0.5 threshold)
    if previous.quiet_score and current.quiet_score:
        quiet_diff = abs(current.quiet_score - previous.quiet_score)
        if quiet_diff >= 0.5:
            result.quiet_score_changed = True
            changes.append(
                f"Quiet score changed ({previous.quiet_score} -> {current.quiet_score})"
            )

    # Vibrancy score change detection (>= 0.5 threshold)
    if previous.vibrancy_score and current.vibrancy_score:
        vibrancy_diff = abs(current.vibrancy_score - previous.vibrancy_score)
        if vibrancy_diff >= 0.5:
            result.vibrancy_score_changed = True
            changes.append(
                f"Vibrancy score changed ({previous.vibrancy_score} -> {current.vibrancy_score})"
            )

    # Garage spaces change detection
    if previous.garage_spaces != current.garage_spaces:
        result.garage_spaces_changed = True
        changes.append(
            f"Garage spaces changed ({previous.garage_spaces} -> {current.garage_spaces})"
        )

    # Gas service change detection
    if previous.gas_service != current.gas_service:
        result.gas_service_changed = True
        changes.append(
            f"Gas service changed ({previous.gas_service} -> {current.gas_service})"
        )

    # Discrepancy flag change detection
    if (
        previous.price_discrepancy_flag != current.price_discrepancy_flag
        or previous.status_discrepancy_flag != current.status_discrepancy_flag
        or previous.dom_discrepancy_flag != current.dom_discrepancy_flag
    ):
        result.discrepancy_flag_changed = True
        changes.append("Cross-site discrepancy flags changed")

    # Effective DOM v2 change detection
    if previous.effective_dom_v2 != current.effective_dom_v2:
        result.effective_dom_v2_changed = True
        changes.append(
            f"Effective DOM v2 changed ({previous.effective_dom_v2} -> {current.effective_dom_v2})"
        )

    # Recent Churn Index change detection
    if previous.recent_churn_index != current.recent_churn_index:
        result.recent_churn_index_changed = True
        changes.append(
            f"Recent Churn Index changed ({previous.recent_churn_index} -> {current.recent_churn_index})"
        )

    # County reset applied change detection
    prev_reset = previous.county_reset_applied or False
    curr_reset = current.county_reset_applied or False
    if prev_reset != curr_reset:
        result.county_reset_applied_changed = True
        changes.append(
            f"County reset applied changed ({prev_reset} -> {curr_reset})"
        )

    # Set has_changes flag
    result.has_changes = len(changes) > 0

    if result.has_changes:
        result.change_summary = "; ".join(changes)
        result.change_details = changes
    else:
        result.change_summary = "No material changes detected"

    return result


def _get_current_property_data(
    property_id: int, database_path: Optional[str] = None
) -> Optional[dict]:
    """
    Get current property data from watched_properties table.

    Args:
        property_id: Property ID
        database_path: Optional database path

    Returns:
        Dictionary with property data or None
    """
    try:
        query = """
        SELECT *
        FROM watched_properties
        WHERE property_id = ? AND active_watch_status = 1
        """
        results = execute_query(query, (property_id,), database_path=database_path)

        if results:
            return dict(results[0])

    except Exception as e:
        logger.error(f"Error getting property data for {property_id}: {e}")

    return None


def _build_snapshot_from_property_data(
    property_id: int, property_data: dict, database_path: Optional[str] = None
) -> ObservationSnapshot:
    """
    Build a snapshot from property data and cross-site observations.

    Args:
        property_id: Property ID
        property_data: Dictionary with property data
        database_path: Optional database path

    Returns:
        ObservationSnapshot
    """
    # Get cross-site comparison results
    cross_site_comparison = compare_property_cross_site(property_id, database_path)

    # Calculate cross-site confidence score
    cross_site_confidence = _calculate_cross_site_confidence(cross_site_comparison)

    # Build listing history hash
    listing_history_hash = _calculate_listing_history_hash(property_id, database_path)

    # Build property detail hash
    property_detail_hash = _calculate_property_detail_hash(property_data)

    # Count price changes
    price_change_count = _count_price_changes(property_id, database_path)

    snapshot = ObservationSnapshot(
        property_id=property_id,
        snapshot_date=datetime.now(),
        source_site="redfin",
        listing_status=property_data.get("listing_status") or "active",
        price=property_data.get("current_price"),
        displayed_dom=property_data.get("displayed_dom"),
        effective_dom=property_data.get("effective_dom"),
        effective_dom_delta=property_data.get("effective_dom_delta"),
        quiet_score=property_data.get("quiet_score"),
        vibrancy_score=property_data.get("vibrancy_score"),
        garage_spaces=property_data.get("garage_spaces"),
        gas_service=property_data.get("gas_service"),
        listing_churn_count=property_data.get("listing_churn_count"),
        dom_reset_count=property_data.get("dom_reset_count"),
        sale_rent_alternation_count=property_data.get("sale_rent_alternation_count"),
        cross_site_confidence_score=cross_site_confidence,
        price_discrepancy_flag=cross_site_comparison.has_price_discrepancy,
        status_discrepancy_flag=cross_site_comparison.has_status_discrepancy,
        dom_discrepancy_flag=cross_site_comparison.has_dom_discrepancy,
        price_change_count=price_change_count,
        listing_history_hash=listing_history_hash,
        property_detail_hash=property_detail_hash,
        raw_source_url=property_data.get("redfin_url"),
        notes=None,
        # Effective DOM v2 operational fields
        effective_dom_v1=property_data.get("effective_dom_v1"),
        effective_dom_v2=property_data.get("effective_dom_v2"),
        effective_dom_delta_v1=property_data.get("effective_dom_delta_v1"),
        effective_dom_delta_v2=property_data.get("effective_dom_delta_v2"),
        county_reset_applied=property_data.get("county_reset_applied") or False,
        county_reset_date=property_data.get("county_reset_date"),
        county_reset_record_type=property_data.get("county_reset_record_type"),
        county_reset_confidence=property_data.get("county_reset_confidence"),
        recent_churn_index=property_data.get("recent_churn_index"),
        recent_churn_lookback_years=property_data.get("recent_churn_lookback_years") or 3,
        recent_churn_event_count=property_data.get("recent_churn_event_count"),
        recent_dom_reset_count=property_data.get("recent_dom_reset_count"),
        recent_sale_rent_alternation_count=property_data.get("recent_sale_rent_alternation_count"),
        churn_preserved_after_transfer=property_data.get("churn_preserved_after_transfer") or True,
    )

    return snapshot


def _store_snapshot(
    snapshot: ObservationSnapshot, database_path: Optional[str] = None
) -> int:
    """
    Store a snapshot in the database.

    Args:
        snapshot: ObservationSnapshot to store
        database_path: Optional database path

    Returns:
        Snapshot ID
    """
    query = """
    INSERT INTO property_observation_snapshots (
        property_id, snapshot_date, source_site, listing_status, price,
        displayed_dom, effective_dom, effective_dom_delta, quiet_score,
        vibrancy_score, garage_spaces, gas_service, listing_churn_count,
        dom_reset_count, sale_rent_alternation_count, cross_site_confidence_score,
        price_discrepancy_flag, status_discrepancy_flag, dom_discrepancy_flag,
        price_change_count, listing_history_hash, property_detail_hash,
        raw_source_url, notes,
        effective_dom_v1, effective_dom_v2, effective_dom_delta_v1,
        effective_dom_delta_v2, county_reset_applied, county_reset_date,
        county_reset_record_type, county_reset_confidence,
        recent_churn_index, recent_churn_lookback_years,
        recent_churn_event_count, recent_dom_reset_count,
        recent_sale_rent_alternation_count, churn_preserved_after_transfer
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    params = (
        snapshot.property_id,
        snapshot.snapshot_date,
        snapshot.source_site,
        snapshot.listing_status,
        snapshot.price,
        snapshot.displayed_dom,
        snapshot.effective_dom,
        snapshot.effective_dom_delta,
        snapshot.quiet_score,
        snapshot.vibrancy_score,
        snapshot.garage_spaces,
        snapshot.gas_service,
        snapshot.listing_churn_count,
        snapshot.dom_reset_count,
        snapshot.sale_rent_alternation_count,
        snapshot.cross_site_confidence_score,
        snapshot.price_discrepancy_flag,
        snapshot.status_discrepancy_flag,
        snapshot.dom_discrepancy_flag,
        snapshot.price_change_count,
        snapshot.listing_history_hash,
        snapshot.property_detail_hash,
        snapshot.raw_source_url,
        snapshot.notes,
        snapshot.effective_dom_v1,
        snapshot.effective_dom_v2,
        snapshot.effective_dom_delta_v1,
        snapshot.effective_dom_delta_v2,
        snapshot.county_reset_applied,
        str(snapshot.county_reset_date) if snapshot.county_reset_date else None,
        snapshot.county_reset_record_type,
        snapshot.county_reset_confidence,
        snapshot.recent_churn_index,
        snapshot.recent_churn_lookback_years,
        snapshot.recent_churn_event_count,
        snapshot.recent_dom_reset_count,
        snapshot.recent_sale_rent_alternation_count,
        snapshot.churn_preserved_after_transfer,
    )

    return execute_insert(query, params, database_path=database_path)


def _is_same_day(dt1: datetime, dt2: datetime) -> bool:
    """
    Check if two datetimes are on the same day.

    Args:
        dt1: First datetime
        dt2: Second datetime

    Returns:
        True if same day
    """
    return dt1.date() == dt2.date()


def _has_material_changes(
    previous: ObservationSnapshot, current: ObservationSnapshot
) -> bool:
    """
    Check if there are material changes between two snapshots.

    Material changes include:
    - Price change
    - Status change
    - Displayed DOM change
    - Effective DOM change
    - Quiet/Vibrancy score changes (>= 0.5 threshold)
    - Discrepancy flag changes

    Args:
        previous: Previous snapshot
        current: Current snapshot

    Returns:
        True if material changes detected
    """
    # Check basic field changes
    if (
        previous.price != current.price
        or previous.listing_status != current.listing_status
        or previous.displayed_dom != current.displayed_dom
        or previous.effective_dom != current.effective_dom
        or previous.price_discrepancy_flag != current.price_discrepancy_flag
        or previous.status_discrepancy_flag != current.status_discrepancy_flag
        or previous.dom_discrepancy_flag != current.dom_discrepancy_flag
    ):
        return True

    # Check quiet score change (>= 0.5 threshold)
    if previous.quiet_score and current.quiet_score:
        quiet_diff = abs(current.quiet_score - previous.quiet_score)
        if quiet_diff >= 0.5:
            return True

    # Check vibrancy score change (>= 0.5 threshold)
    if previous.vibrancy_score and current.vibrancy_score:
        vibrancy_diff = abs(current.vibrancy_score - previous.vibrancy_score)
        if vibrancy_diff >= 0.5:
            return True

    return False


def _update_last_checked_date(
    property_id: int, database_path: Optional[str] = None
) -> None:
    """
    Update the last_checked_date for a watched property.

    Args:
        property_id: Property ID
        database_path: Optional database path
    """
    query = """
    UPDATE watched_properties
    SET last_checked_date = CURRENT_DATE, updated_at = CURRENT_TIMESTAMP
    WHERE property_id = ?
    """
    execute_update(query, (property_id,), database_path=database_path)


def _calculate_cross_site_confidence(cross_site_comparison) -> float:
    """
    Calculate cross-site confidence score.

    Higher score = more cross-site sources agree with Redfin data.

    Args:
        cross_site_comparison: CrossSiteComparisonResult

    Returns:
        Confidence score (0.0 to 1.0)
    """
    if not cross_site_comparison:
        return 0.0

    # Count how many cross-site sources have data
    sources_with_data = 0
    sources_agreeing = 0

    for site in ["zillow", "realtor", "homes", "compass"]:
        price_attr = f"{site}_price"
        if hasattr(cross_site_comparison, price_attr):
            price = getattr(cross_site_comparison, price_attr)
            if price is not None:
                sources_with_data += 1

                # Check if this source agrees with Redfin (within $10k)
                if cross_site_comparison.redfin_price:
                    diff = abs(price - cross_site_comparison.redfin_price)
                    if diff <= 10000:
                        sources_agreeing += 1

    if sources_with_data == 0:
        return 0.0

    return sources_agreeing / sources_with_data


def _calculate_listing_history_hash(
    property_id: int, database_path: Optional[str] = None
) -> str:
    """
    Calculate a hash of the listing history for change detection.

    Args:
        property_id: Property ID
        database_path: Optional database path

    Returns:
        Hash string
    """
    try:
        query = """
        SELECT event_type, event_date, old_value, new_value
        FROM listing_events
        WHERE property_id = ?
        ORDER BY event_date DESC
        LIMIT 50
        """
        results = execute_query(query, (property_id,), database_path=database_path)

        events = [dict(row) for row in results]
        events_json = json.dumps(events, sort_keys=True, default=str)

        return hashlib.sha256(events_json.encode()).hexdigest()[:16]

    except Exception:
        return ""


def _calculate_property_detail_hash(property_data: dict) -> str:
    """
    Calculate a hash of property details for change detection.

    Args:
        property_data: Dictionary with property data

    Returns:
        Hash string
    """
    try:
        # Include key immutable fields
        detail_fields = {
            "address": property_data.get("address"),
            "beds": property_data.get("beds"),
            "baths": property_data.get("baths"),
            "sqft": property_data.get("sqft"),
            "lot_size": property_data.get("lot_size"),
            "garage_spaces": property_data.get("garage_spaces"),
            "gas_service": property_data.get("gas_service"),
        }

        details_json = json.dumps(detail_fields, sort_keys=True, default=str)
        return hashlib.sha256(details_json.encode()).hexdigest()[:16]

    except Exception:
        return ""


def _count_price_changes(
    property_id: int, database_path: Optional[str] = None
) -> int:
    """
    Count the number of price changes for a property.

    Args:
        property_id: Property ID
        database_path: Optional database path

    Returns:
        Number of price change events
    """
    try:
        query = """
        SELECT COUNT(*) as count
        FROM listing_events
        WHERE property_id = ? AND event_type = 'price_changed'
        """
        results = execute_query(query, (property_id,), database_path=database_path)

        if results:
            return results[0]["count"]

    except Exception:
        pass

    return 0
