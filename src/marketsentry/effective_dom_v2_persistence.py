"""Effective DOM v2 persistence workflow.

Persists v2 metrics to watched_properties and candidate_review_queue tables.
This module operationalizes v2 by writing computed metrics back to the database
so they appear in normal monitoring and reporting workflows.

CRITICAL: County reset affects Effective DOM only. Churn metrics are NEVER zeroed.
User decisions, notes, active_watch_status, and watch_priority are always preserved.
"""

from typing import Optional

from marketsentry.database import column_exists, execute_query, execute_update
from marketsentry.effective_dom_v2_calculator import calculate_effective_dom_v2
from marketsentry.logging_config import logger
from marketsentry.models import (
    CountyRecordObservation,
    CountyResetIntegrationResult,
    ListingEvent,
)


def persist_effective_dom_v2(
    database_path: Optional[str] = None,
) -> CountyResetIntegrationResult:
    """
    Persist Effective DOM v2 metrics to watched_properties and candidate_review_queue.

    This workflow:
    1. Reads watched properties and candidates
    2. Reads listing events for each
    3. Reads county records for each
    4. Computes v2 metrics with county reset support
    5. Persists v2 fields to database tables
    6. Preserves user_decision, user_notes, active_watch_status, watch_priority
    7. Does not delete or rewrite listing history
    8. Does not zero churn metrics when county reset applies

    Args:
        database_path: Optional database path

    Returns:
        CountyResetIntegrationResult with persistence summary
    """
    result = CountyResetIntegrationResult()

    try:
        # Process watched properties
        _persist_v2_for_watched_properties(result, database_path)

        # Process candidates
        _persist_v2_for_candidates(result, database_path)

        logger.info(
            f"Effective DOM v2 persistence complete: {result.properties_scanned} properties, "
            f"{result.records_updated} updated, {result.county_resets_applied} resets applied"
        )

    except Exception as e:
        logger.error(f"Error in Effective DOM v2 persistence: {e}")
        result.errors.append(f"Persistence error: {str(e)}")

    return result


def _persist_v2_for_watched_properties(
    result: CountyResetIntegrationResult,
    database_path: Optional[str] = None,
) -> None:
    """
    Persist v2 metrics for all watched properties.

    Args:
        result: Result accumulator
        database_path: Optional database path
    """
    # Check if v2 columns exist
    if not column_exists("watched_properties", "effective_dom_v2", database_path):
        result.warnings.append("watched_properties missing v2 columns - run migrate first")
        return

    # Get all active watched properties
    query = """
    SELECT property_id, displayed_dom
    FROM watched_properties
    WHERE active_watch_status = 1
    """
    properties = execute_query(query, database_path=database_path)
    result.properties_scanned += len(properties)

    for prop in properties:
        property_id = prop["property_id"]
        displayed_dom = prop["displayed_dom"]

        try:
            # Get listing events
            events = _get_listing_events(property_id=property_id, database_path=database_path)

            # Get county records
            county_records = _get_county_records(property_id=property_id, database_path=database_path)

            if county_records:
                result.county_transfers_considered += len(county_records)

            # Calculate v2 metrics
            v2_metrics = calculate_effective_dom_v2(events, county_records, displayed_dom)

            # Persist to watched_properties
            _update_watched_property_v2(property_id, v2_metrics, database_path)
            result.records_updated += 1

            if v2_metrics.county_reset_applied:
                result.county_resets_applied += 1

            if v2_metrics.churn_preserved_after_transfer:
                result.churn_metrics_preserved += 1

        except Exception as e:
            logger.error(f"Error persisting v2 for watched property {property_id}: {e}")
            result.errors.append(f"Property {property_id}: {str(e)}")


def _persist_v2_for_candidates(
    result: CountyResetIntegrationResult,
    database_path: Optional[str] = None,
) -> None:
    """
    Persist v2 metrics for candidates that have linked listing events.

    Args:
        result: Result accumulator
        database_path: Optional database path
    """
    # Check if v2 columns exist
    if not column_exists("candidate_review_queue", "effective_dom_v2", database_path):
        result.warnings.append("candidate_review_queue missing v2 columns - run migrate first")
        return

    # Get candidates that have listing events
    query = """
    SELECT DISTINCT c.candidate_id, c.displayed_dom
    FROM candidate_review_queue c
    INNER JOIN listing_events le ON c.candidate_id = le.candidate_id
    """
    candidates = execute_query(query, database_path=database_path)

    candidates_scanned = len(candidates)

    for cand in candidates:
        candidate_id = cand["candidate_id"]
        displayed_dom = cand["displayed_dom"]

        try:
            # Get listing events
            events = _get_listing_events(candidate_id=candidate_id, database_path=database_path)

            # Get county records
            county_records = _get_county_records(candidate_id=candidate_id, database_path=database_path)

            if county_records:
                result.county_transfers_considered += len(county_records)

            # Calculate v2 metrics
            v2_metrics = calculate_effective_dom_v2(events, county_records, displayed_dom)

            # Persist to candidate_review_queue
            _update_candidate_v2(candidate_id, v2_metrics, database_path)
            result.records_updated += 1

            if v2_metrics.county_reset_applied:
                result.county_resets_applied += 1

            if v2_metrics.churn_preserved_after_transfer:
                result.churn_metrics_preserved += 1

        except Exception as e:
            logger.error(f"Error persisting v2 for candidate {candidate_id}: {e}")
            result.errors.append(f"Candidate {candidate_id}: {str(e)}")

    if candidates_scanned > 0:
        result.notes = (
            f"Watched properties: {result.properties_scanned}, "
            f"Candidates with events: {candidates_scanned}"
        )


def _get_listing_events(
    property_id: Optional[int] = None,
    candidate_id: Optional[int] = None,
    database_path: Optional[str] = None,
) -> list:
    """
    Get listing events for a property or candidate.

    Args:
        property_id: Optional property ID
        candidate_id: Optional candidate ID
        database_path: Optional database path

    Returns:
        List of ListingEvent objects
    """
    if property_id is not None:
        query = """
        SELECT * FROM listing_events
        WHERE property_id = ?
        ORDER BY event_date
        """
        rows = execute_query(query, (property_id,), database_path=database_path)
    elif candidate_id is not None:
        query = """
        SELECT * FROM listing_events
        WHERE candidate_id = ?
        ORDER BY event_date
        """
        rows = execute_query(query, (candidate_id,), database_path=database_path)
    else:
        return []

    return [ListingEvent(**dict(row)) for row in rows]


def _get_county_records(
    property_id: Optional[int] = None,
    candidate_id: Optional[int] = None,
    database_path: Optional[str] = None,
) -> list:
    """
    Get county record observations for a property or candidate.

    Args:
        property_id: Optional property ID
        candidate_id: Optional candidate ID
        database_path: Optional database path

    Returns:
        List of CountyRecordObservation objects
    """
    if property_id is not None:
        query = """
        SELECT * FROM county_record_observations
        WHERE property_id = ?
        ORDER BY record_date
        """
        rows = execute_query(query, (property_id,), database_path=database_path)
    elif candidate_id is not None:
        query = """
        SELECT * FROM county_record_observations
        WHERE candidate_id = ?
        ORDER BY record_date
        """
        rows = execute_query(query, (candidate_id,), database_path=database_path)
    else:
        return []

    return [CountyRecordObservation(**dict(row)) for row in rows]


def _update_watched_property_v2(
    property_id: int,
    v2_metrics: object,
    database_path: Optional[str] = None,
) -> None:
    """
    Update watched property with v2 metrics.

    Preserves user_notes, active_watch_status, watch_priority.

    Args:
        property_id: Property ID
        v2_metrics: EffectiveDomV2Metrics object
        database_path: Optional database path
    """
    query = """
    UPDATE watched_properties
    SET effective_dom_v1 = ?,
        effective_dom_v2 = ?,
        effective_dom_delta_v1 = ?,
        effective_dom_delta_v2 = ?,
        county_reset_applied = ?,
        county_reset_date = ?,
        county_reset_record_type = ?,
        county_reset_confidence = ?,
        recent_churn_index = ?,
        recent_churn_lookback_years = ?,
        recent_churn_event_count = ?,
        recent_dom_reset_count = ?,
        recent_sale_rent_alternation_count = ?,
        churn_preserved_after_transfer = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE property_id = ?
    """
    params = (
        v2_metrics.effective_dom_v1,
        v2_metrics.effective_dom_v2,
        v2_metrics.effective_dom_delta_v1,
        v2_metrics.effective_dom_delta_v2,
        v2_metrics.county_reset_applied,
        str(v2_metrics.county_reset_date) if v2_metrics.county_reset_date else None,
        v2_metrics.county_reset_record_type,
        v2_metrics.county_reset_confidence,
        v2_metrics.recent_churn_index,
        v2_metrics.recent_churn_lookback_years,
        v2_metrics.recent_churn_event_count,
        v2_metrics.recent_dom_reset_count,
        v2_metrics.recent_sale_rent_alternation_count,
        v2_metrics.churn_preserved_after_transfer,
        property_id,
    )
    execute_update(query, params, database_path=database_path)


def _update_candidate_v2(
    candidate_id: int,
    v2_metrics: object,
    database_path: Optional[str] = None,
) -> None:
    """
    Update candidate with v2 metrics.

    Preserves user_decision, user_notes, review_status.

    Args:
        candidate_id: Candidate ID
        v2_metrics: EffectiveDomV2Metrics object
        database_path: Optional database path
    """
    query = """
    UPDATE candidate_review_queue
    SET effective_dom_v1 = ?,
        effective_dom_v2 = ?,
        effective_dom_delta_v1 = ?,
        effective_dom_delta_v2 = ?,
        county_reset_applied = ?,
        county_reset_date = ?,
        county_reset_record_type = ?,
        county_reset_confidence = ?,
        recent_churn_index = ?,
        recent_churn_lookback_years = ?,
        recent_churn_event_count = ?,
        recent_dom_reset_count = ?,
        recent_sale_rent_alternation_count = ?,
        churn_preserved_after_transfer = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE candidate_id = ?
    """
    params = (
        v2_metrics.effective_dom_v1,
        v2_metrics.effective_dom_v2,
        v2_metrics.effective_dom_delta_v1,
        v2_metrics.effective_dom_delta_v2,
        v2_metrics.county_reset_applied,
        str(v2_metrics.county_reset_date) if v2_metrics.county_reset_date else None,
        v2_metrics.county_reset_record_type,
        v2_metrics.county_reset_confidence,
        v2_metrics.recent_churn_index,
        v2_metrics.recent_churn_lookback_years,
        v2_metrics.recent_churn_event_count,
        v2_metrics.recent_dom_reset_count,
        v2_metrics.recent_sale_rent_alternation_count,
        v2_metrics.churn_preserved_after_transfer,
        candidate_id,
    )
    execute_update(query, params, database_path=database_path)
