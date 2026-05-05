"""Candidate recalculation workflow."""

from typing import Optional

from marketsentry.config import config
from marketsentry.database import get_connection
from marketsentry.effective_dom import calculate_all_effective_dom_metrics
from marketsentry.models import ListingEvent
from marketsentry.quiet_vibrancy import apply_quiet_gatekeeper


class RecalculationResult:
    """Result of candidate recalculation."""

    def __init__(self):
        """Initialize result."""
        self.candidates_scanned: int = 0
        self.candidates_updated: int = 0
        self.listing_events_used: int = 0
        self.warnings: list[str] = []
        self.errors: list[str] = []


def recalculate_candidates(
    database_path: Optional[str] = None,
) -> RecalculationResult:
    """
    Recalculate Effective DOM and scoring fields for all candidates.

    This operation:
    - Reads candidates and listing_events from database
    - Recalculates Effective DOM metrics
    - Updates candidate_review_queue with new metrics
    - Preserves user_decision and user_notes
    - Is idempotent (safe to run multiple times)

    Args:
        database_path: Path to database (defaults to config)

    Returns:
        RecalculationResult with statistics
    """
    database_path = database_path or config.database_path
    result = RecalculationResult()

    conn = get_connection(database_path)
    cursor = conn.cursor()

    try:
        # Get all candidates
        cursor.execute("""
            SELECT
                candidate_id,
                displayed_dom,
                quiet_score,
                vibrancy_score
            FROM candidate_review_queue
            ORDER BY candidate_id
        """)

        candidates = cursor.fetchall()
        result.candidates_scanned = len(candidates)

        for row in candidates:
            candidate_id = row[0]
            displayed_dom = row[1]
            quiet_score = row[2]
            vibrancy_score = row[3]

            try:
                # Load listing events
                cursor.execute("""
                    SELECT
                        event_date,
                        source_site,
                        event_type,
                        new_value,
                        mls_number
                    FROM listing_events
                    WHERE candidate_id = ?
                    ORDER BY event_date
                """, (candidate_id,))

                event_rows = cursor.fetchall()
                result.listing_events_used += len(event_rows)

                listing_events = []
                for row in event_rows:
                    # Try to parse price from new_value (may be None or non-numeric)
                    price_value = None
                    if row[3]:
                        try:
                            price_value = float(row[3])
                        except (ValueError, TypeError):
                            pass

                    listing_events.append(
                        ListingEvent(
                            event_date=row[0],
                            source_site=row[1] or "redfin",
                            event_type=row[2] or "unknown",
                            price=price_value,
                            source_mls=row[4],  # Using mls_number as source_mls
                        )
                    )

                # Calculate effective DOM metrics
                metrics = calculate_all_effective_dom_metrics(
                    listing_events,
                    displayed_dom=displayed_dom,
                )

                # Apply quiet gatekeeper if scores available
                gatekeeper_result = None
                if quiet_score is not None and vibrancy_score is not None:
                    gatekeeper_result, _ = apply_quiet_gatekeeper(
                        quiet_score, vibrancy_score
                    )

                # Update candidate with new metrics
                # Preserve user_decision and user_notes
                cursor.execute("""
                    UPDATE candidate_review_queue
                    SET
                        effective_dom_estimate = ?,
                        listing_churn_count = ?,
                        dom_reset_count = ?,
                        sale_rent_alternation_count = ?,
                        quiet_gatekeeper_result = ?
                    WHERE candidate_id = ?
                """, (
                    metrics.effective_dom,
                    metrics.listing_churn_count,
                    metrics.dom_reset_count,
                    metrics.sale_rent_alternation_count,
                    gatekeeper_result,
                    candidate_id,
                ))

                result.candidates_updated += 1

            except Exception as e:
                error_msg = f"Error processing candidate {candidate_id}: {str(e)}"
                result.errors.append(error_msg)

        conn.commit()

    except Exception as e:
        conn.rollback()
        result.errors.append(f"Database error: {str(e)}")

    finally:
        conn.close()

    return result
