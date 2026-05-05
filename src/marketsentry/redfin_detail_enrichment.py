"""Enrich candidate records with parsed Redfin detail data."""

import hashlib
from datetime import date
from pathlib import Path
from typing import List, Optional

from marketsentry.database import (
    execute_insert,
    execute_query,
    execute_update,
    find_candidate_by_address,
    find_candidate_by_url,
    get_connection,
)
from marketsentry.effective_dom import (
    calculate_dom_reset_count,
    calculate_listing_churn_count,
    calculate_sale_rent_alternation_count,
)
from marketsentry.logging_config import logger
from marketsentry.models import (
    ListingEvent,
    RedfinDetailEnrichmentResult,
    RedfinDetailParseResult,
    RedfinPropertyDetail,
)
from marketsentry.quiet_vibrancy import apply_quiet_gatekeeper
from marketsentry.redfin_detail_parser import parse_redfin_detail_directory


def enrich_candidates_from_detail_directory(
    directory_path: str, database_path: Optional[str] = None
) -> RedfinDetailEnrichmentResult:
    """
    Parse Redfin detail files and enrich candidate records.

    Args:
        directory_path: Path to directory containing detail HTML files
        database_path: Database path (optional)

    Returns:
        RedfinDetailEnrichmentResult with enrichment statistics
    """
    dir_path = Path(directory_path)

    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")

    if not dir_path.is_dir():
        raise ValueError(f"Not a directory: {directory_path}")

    logger.info(f"Enriching candidates from detail files in {directory_path}")

    # Parse all detail files
    parse_results = parse_redfin_detail_directory(dir_path)

    # Initialize result
    result = RedfinDetailEnrichmentResult(
        total_files_processed=len(parse_results)
    )

    # Process each parsed detail
    for parse_result in parse_results:
        # Count parsing status
        if parse_result.parse_status in ["success", "partial"]:
            result.details_parsed += 1
        result.parse_warnings += len(parse_result.warnings)
        result.parse_errors += len(parse_result.errors)

        # Skip if parsing failed or no detail
        if not parse_result.property_detail:
            continue

        detail = parse_result.property_detail

        # Try to match to existing candidate
        candidate_id = _find_candidate_for_detail(detail, database_path)

        if candidate_id:
            result.candidates_matched += 1

            # Update candidate with detail data
            updated = _update_candidate_with_detail(
                candidate_id, detail, database_path
            )
            if updated:
                result.candidates_updated += 1

            # Insert listing events
            events_inserted = _insert_listing_events(
                candidate_id, detail.listing_history, database_path
            )
            result.listing_events_inserted += events_inserted

            # Record source page
            if parse_result.source_file:
                _record_detail_source_page(
                    candidate_id, parse_result.source_file, database_path
                )

    logger.info(
        f"Enrichment complete: {result.candidates_updated} candidates updated, "
        f"{result.listing_events_inserted} listing events inserted"
    )

    return result


def _find_candidate_for_detail(
    detail: RedfinPropertyDetail, database_path: Optional[str] = None
) -> Optional[int]:
    """
    Find candidate ID for a property detail.

    Matches by:
    1. Redfin URL
    2. Normalized address

    Args:
        detail: Property detail to match
        database_path: Database path

    Returns:
        Candidate ID or None
    """
    # Try matching by URL first
    if detail.redfin_url:
        candidate = find_candidate_by_url(detail.redfin_url, database_path)
        if candidate:
            return candidate["candidate_id"]

    # Try matching by normalized address
    if detail.normalized_address:
        candidate = find_candidate_by_address(detail.normalized_address, database_path)
        if candidate:
            return candidate["candidate_id"]

    return None


def _update_candidate_with_detail(
    candidate_id: int,
    detail: RedfinPropertyDetail,
    database_path: Optional[str] = None,
) -> bool:
    """
    Update candidate record with detail data.

    Preserves user_decision, user_notes, and review_status.
    Only updates fields where parsed data is available.

    Args:
        candidate_id: Candidate ID to update
        detail: Property detail with data to apply
        database_path: Database path

    Returns:
        True if updated successfully
    """
    try:
        # Build update query dynamically
        updates = []
        params = []

        # Address fields
        if detail.address:
            updates.append("address = ?")
            params.append(detail.address)
        if detail.normalized_address:
            updates.append("normalized_address = ?")
            params.append(detail.normalized_address)
        if detail.city:
            updates.append("city = ?")
            params.append(detail.city)
        if detail.zip:
            updates.append("zip = ?")
            params.append(detail.zip)

        # Property facts
        if detail.facts:
            if detail.facts.price is not None:
                updates.append("price = ?")
                params.append(detail.facts.price)
            if detail.facts.beds is not None:
                updates.append("beds = ?")
                params.append(detail.facts.beds)
            if detail.facts.baths is not None:
                updates.append("baths = ?")
                params.append(detail.facts.baths)
            if detail.facts.sqft is not None:
                updates.append("sqft = ?")
                params.append(detail.facts.sqft)
            if detail.facts.lot_size is not None:
                updates.append("lot_size = ?")
                params.append(detail.facts.lot_size)
            if detail.facts.garage_spaces is not None:
                updates.append("garage_spaces = ?")
                params.append(detail.facts.garage_spaces)

        # Displayed DOM
        if detail.displayed_dom is not None:
            updates.append("displayed_dom = ?")
            params.append(detail.displayed_dom)

        # Lifestyle scores
        if detail.lifestyle_scores:
            if detail.lifestyle_scores.quiet_score is not None:
                updates.append("quiet_score = ?")
                params.append(detail.lifestyle_scores.quiet_score)

            if detail.lifestyle_scores.vibrancy_score is not None:
                updates.append("vibrancy_score = ?")
                params.append(detail.lifestyle_scores.vibrancy_score)

            # Apply quiet gatekeeper if both scores available
            if (detail.lifestyle_scores.quiet_score is not None and
                detail.lifestyle_scores.vibrancy_score is not None):
                gatekeeper_result, _ = apply_quiet_gatekeeper(
                    detail.lifestyle_scores.quiet_score,
                    detail.lifestyle_scores.vibrancy_score
                )
                updates.append("quiet_gatekeeper_result = ?")
                params.append(gatekeeper_result)

        # Gas evidence
        if detail.gas_service is not None:
            updates.append("gas_service = ?")
            params.append(detail.gas_service)
        if detail.gas_evidence:
            updates.append("gas_evidence = ?")
            params.append(detail.gas_evidence)

        # Calculate preliminary Effective DOM metrics from listing history
        if detail.listing_history:
            # Convert to ListingEvent format for calculation
            listing_events = _convert_to_listing_events(detail.listing_history)

            listing_churn = calculate_listing_churn_count(listing_events)
            dom_reset = calculate_dom_reset_count(listing_events)
            sale_rent_alt = calculate_sale_rent_alternation_count(listing_events)

            updates.append("listing_churn_count = ?")
            params.append(listing_churn)
            updates.append("dom_reset_count = ?")
            params.append(dom_reset)
            updates.append("sale_rent_alternation_count = ?")
            params.append(sale_rent_alt)

            # Calculate preliminary effective DOM estimate
            # Simple approach: days from earliest listing event to latest or today
            effective_dom_est = _calculate_preliminary_effective_dom(detail.listing_history)
            if effective_dom_est is not None:
                updates.append("effective_dom_estimate = ?")
                params.append(effective_dom_est)

        if not updates:
            return False  # Nothing to update

        # Always update the updated_at timestamp
        updates.append("updated_at = CURRENT_TIMESTAMP")

        # Build and execute query
        query = f"""
        UPDATE candidate_review_queue
        SET {', '.join(updates)}
        WHERE candidate_id = ?
        """
        params.append(candidate_id)

        execute_update(query, tuple(params), database_path=database_path)
        logger.info(f"Updated candidate {candidate_id} with detail data")
        return True

    except Exception as e:
        logger.error(f"Error updating candidate {candidate_id}: {e}")
        return False


def _convert_to_listing_events(
    redfin_events: list
) -> List[ListingEvent]:
    """Convert Redfin listing history events to ListingEvent format."""
    events = []
    for redfin_event in redfin_events:
        events.append(
            ListingEvent(
                event_date=redfin_event.event_date or date.today(),
                source_site="redfin",
                event_type=redfin_event.event_type,
                old_value=None,
                new_value=str(redfin_event.price) if redfin_event.price else None,
                source_listing_id=redfin_event.source_listing_id,
                mls_number=redfin_event.mls_number,
                confidence=redfin_event.confidence,
                notes=redfin_event.raw_text,
            )
        )
    return events


def _calculate_preliminary_effective_dom(
    listing_history: list
) -> Optional[int]:
    """
    Calculate preliminary Effective DOM estimate from listing history.

    Simple approach: calendar days from earliest non-sold listing event
    to latest listing event or today.

    Args:
        listing_history: List of listing history events

    Returns:
        Preliminary Effective DOM estimate in days
    """
    if not listing_history:
        return None

    # Filter out sold events for the current cycle
    active_events = [
        event for event in listing_history
        if event.event_date and event.event_type not in ["sold"]
    ]

    if not active_events:
        return None

    # Get earliest and latest event dates
    dates = [event.event_date for event in active_events]
    earliest_date = min(dates)
    latest_date = max(dates)

    # Calculate days between earliest and latest (or today)
    current_date = date.today()
    end_date = max(latest_date, current_date)

    effective_dom = (end_date - earliest_date).days
    return max(0, effective_dom)


def _insert_listing_events(
    candidate_id: int,
    listing_history: list,
    database_path: Optional[str] = None,
) -> int:
    """
    Insert listing events into database.

    Avoids duplicates by checking existing events.

    Args:
        candidate_id: Candidate ID
        listing_history: List of listing history events
        database_path: Database path

    Returns:
        Number of events inserted
    """
    if not listing_history:
        return 0

    inserted_count = 0

    for event in listing_history:
        try:
            # Check for duplicate
            if _listing_event_exists(candidate_id, event, database_path):
                continue

            # Insert event
            query = """
            INSERT INTO listing_events (
                candidate_id, event_date, source_site, event_type,
                new_value, source_listing_id, mls_number, confidence, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            params = (
                candidate_id,
                event.event_date,
                "redfin",
                event.event_type,
                str(event.price) if event.price else None,
                event.source_listing_id,
                event.mls_number,
                event.confidence,
                event.raw_text,
            )

            execute_insert(query, params, database_path=database_path)
            inserted_count += 1

        except Exception as e:
            logger.warning(f"Error inserting listing event: {e}")
            continue

    return inserted_count


def _listing_event_exists(
    candidate_id: int,
    event,
    database_path: Optional[str] = None,
) -> bool:
    """Check if a listing event already exists in the database."""
    try:
        query = """
        SELECT COUNT(*) as count FROM listing_events
        WHERE candidate_id = ?
        AND event_date = ?
        AND event_type = ?
        AND source_site = ?
        """

        params = (candidate_id, event.event_date, event.event_type, "redfin")
        result = execute_query(query, params, database_path=database_path)

        return result[0]["count"] > 0 if result else False

    except Exception:
        return False


def _record_detail_source_page(
    candidate_id: int,
    source_file: str,
    database_path: Optional[str] = None,
) -> None:
    """Record source page provenance for detail parsing."""
    try:
        # Calculate content hash if file exists
        file_path = Path(source_file)
        content_hash = None
        if file_path.exists():
            with open(file_path, "rb") as f:
                content = f.read()
                content_hash = hashlib.sha256(content).hexdigest()

        # Insert source page record
        query = """
        INSERT INTO source_pages (
            candidate_id, source_site, source_url, retrieval_method,
            content_hash, parser_version, parse_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            candidate_id,
            "redfin",
            source_file,
            "saved_detail_fixture",
            content_hash,
            "1.0",  # Parser version
            "success",
        )

        execute_insert(query, params, database_path=database_path)

    except Exception as e:
        logger.warning(f"Failed to record source page: {e}")
        # Don't raise - this is non-critical
