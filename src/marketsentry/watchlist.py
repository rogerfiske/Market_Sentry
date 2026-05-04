"""Watchlist promotion and management."""

from datetime import date
from typing import Dict, List, Optional

from marketsentry.database import (
    execute_query,
    find_watched_by_address,
    insert_watched_property,
    record_review_action,
    update_candidate_decision,
)
from marketsentry.effective_dom import calculate_effective_dom_delta
from marketsentry.logging_config import logger
from marketsentry.models import WatchedProperty
from marketsentry.normalization import normalize_address


def calculate_watch_priority(
    quiet_score: Optional[float],
    effective_dom_estimate: Optional[int],
    listing_churn_count: Optional[int],
    quiet_gatekeeper_result: Optional[str],
) -> int:
    """
    Calculate watch priority for a property.

    Priority levels:
    - 3 (high): Quiet passes strongly AND has DOM/churn leverage signals
    - 2 (medium): Normal saved candidates
    - 1 (low): Missing important data

    Args:
        quiet_score: Quiet score
        effective_dom_estimate: Effective DOM estimate
        listing_churn_count: Listing churn count
        quiet_gatekeeper_result: Quiet gatekeeper result

    Returns:
        Priority level (1-3)
    """
    # Low priority if missing critical data
    if quiet_score is None or quiet_gatekeeper_result != "pass":
        return 1

    # High priority if strong quiet score and leverage signals
    has_leverage_signal = False
    if effective_dom_estimate and effective_dom_estimate > 60:
        has_leverage_signal = True
    if listing_churn_count and listing_churn_count >= 2:
        has_leverage_signal = True

    if quiet_score >= 8.5 and has_leverage_signal:
        return 3

    # Medium priority for normal candidates
    return 2


def promote_candidate_to_watchlist(
    candidate_id: int, database_path: Optional[str] = None
) -> Optional[int]:
    """
    Promote a candidate from review queue to watched properties.

    Args:
        candidate_id: Candidate ID to promote
        database_path: Path to database file

    Returns:
        Property ID of promoted property, or None if already promoted or candidate not found
    """
    # Get candidate data
    query = "SELECT * FROM candidate_review_queue WHERE candidate_id = ?"
    results = execute_query(query, (candidate_id,), database_path=database_path)

    if not results:
        logger.warning(f"Candidate {candidate_id} not found")
        return None

    candidate = dict(results[0])

    # Normalize address if needed
    normalized_addr = candidate.get("normalized_address")
    if not normalized_addr and candidate.get("address"):
        normalized_addr = normalize_address(candidate["address"])

    # Check if already in watchlist
    if normalized_addr:
        existing = find_watched_by_address(normalized_addr, database_path)
        if existing:
            logger.info(
                f"Candidate {candidate_id} already promoted to watched property {existing['property_id']}"
            )
            return existing["property_id"]

    # Calculate watch priority
    priority = calculate_watch_priority(
        candidate.get("quiet_score"),
        candidate.get("effective_dom_estimate"),
        candidate.get("listing_churn_count"),
        candidate.get("quiet_gatekeeper_result"),
    )

    # Calculate effective DOM delta if both values available
    effective_dom_delta = calculate_effective_dom_delta(
        candidate.get("displayed_dom"), candidate.get("effective_dom_estimate")
    )

    # Create watched property
    watched = WatchedProperty(
        first_saved_date=date.today(),
        active_watch_status=True,
        redfin_url=candidate.get("redfin_url"),
        address=candidate["address"],
        normalized_address=normalized_addr,
        city=candidate["city"],
        zip=candidate["zip"],
        current_price=candidate.get("price"),
        original_observed_price=candidate.get("price"),
        beds=candidate.get("beds"),
        baths=candidate.get("baths"),
        sqft=candidate.get("sqft"),
        lot_size=candidate.get("lot_size"),
        garage_spaces=candidate.get("garage_spaces"),
        gas_service=candidate.get("gas_service"),
        gas_evidence=candidate.get("gas_evidence"),
        quiet_score=candidate.get("quiet_score"),
        vibrancy_score=candidate.get("vibrancy_score"),
        displayed_dom=candidate.get("displayed_dom"),
        effective_dom=candidate.get("effective_dom_estimate"),
        effective_dom_delta=effective_dom_delta,
        listing_churn_count=candidate.get("listing_churn_count"),
        dom_reset_count=candidate.get("dom_reset_count"),
        sale_rent_alternation_count=candidate.get("sale_rent_alternation_count"),
        watch_priority=priority,
        user_notes=candidate.get("user_notes"),
    )

    # Insert into watched_properties
    property_id = insert_watched_property(watched, database_path=database_path)

    logger.info(
        f"Promoted candidate {candidate_id} to watched property {property_id} with priority {priority}"
    )

    return property_id


def promote_candidates_to_watchlist(
    candidate_ids: List[int], database_path: Optional[str] = None
) -> Dict[int, Optional[int]]:
    """
    Promote multiple candidates to watchlist.

    Args:
        candidate_ids: List of candidate IDs to promote
        database_path: Path to database file

    Returns:
        Dict mapping candidate_id to property_id (or None if promotion failed)
    """
    results = {}
    for candidate_id in candidate_ids:
        property_id = promote_candidate_to_watchlist(candidate_id, database_path)
        results[candidate_id] = property_id
    return results
