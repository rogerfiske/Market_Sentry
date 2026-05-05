"""County ownership transfer verification logic.

Supports classifying county record types and identifying ownership transfer events
that may support Effective DOM resets.

IMPORTANT: County-confirmed ownership transfer may reset Effective DOM for the current
ownership cycle, but churn must remain available as a separate analytical factor.
"""

from datetime import date
from pathlib import Path
from typing import List, Optional

from marketsentry.database import execute_query
from marketsentry.logging_config import logger
from marketsentry.models import CountyTransferEvent, CountyVerificationResult


def normalize_county_record_type(record_type: str) -> str:
    """
    Normalize county record type to standard values.

    Args:
        record_type: Raw record type string

    Returns:
        Normalized record type
    """
    if not record_type:
        return "unknown"

    # Convert to lowercase and remove extra spaces
    normalized = record_type.lower().strip().replace("  ", " ")

    # Map to standard types
    if "grant deed" in normalized or "grantdeed" in normalized:
        return "grant_deed"
    elif "quitclaim" in normalized or "quit claim" in normalized:
        return "quitclaim_deed"
    elif "trustee" in normalized and "deed" in normalized:
        return "trustee_deed"
    elif "warranty deed" in normalized:
        return "warranty_deed"
    elif "deed of trust" in normalized or "trust deed" in normalized:
        return "deed_of_trust"
    elif "reconveyance" in normalized:
        return "reconveyance"
    elif "lien" in normalized:
        return "lien"
    elif "tax" in normalized:
        return "tax_record"
    elif "assessment" in normalized or "assessor" in normalized:
        return "assessment"
    elif "permit" in normalized:
        return "permit"
    else:
        return "unknown"


def is_ownership_transfer_record(
    record_type: str, document_title: Optional[str] = None
) -> bool:
    """
    Determine if a county record type indicates an ownership transfer.

    Ownership transfer records:
    - grant_deed
    - quitclaim_deed
    - trustee_deed
    - warranty_deed

    NOT ownership transfer records:
    - deed_of_trust (financing, not transfer)
    - reconveyance (loan payoff, not transfer)
    - lien (encumbrance, not transfer)
    - assessment (valuation, not transfer)
    - permit (construction, not transfer)
    - tax_record (taxation, not transfer)

    Args:
        record_type: Record type string (raw or normalized)
        document_title: Optional document title for additional context

    Returns:
        True if record indicates ownership transfer
    """
    # Define ownership transfer types
    transfer_types = {
        "grant_deed",
        "quitclaim_deed",
        "trustee_deed",
        "warranty_deed",
    }

    # Check if already normalized (lowercase with underscores)
    record_type_lower = record_type.lower().strip()
    if record_type_lower in transfer_types:
        return True

    # Normalize the record type and check again
    normalized_type = normalize_county_record_type(record_type)
    if normalized_type in transfer_types:
        return True

    # Check document title for additional evidence (conservative)
    if document_title:
        title_lower = document_title.lower()
        if "grant deed" in title_lower and "trust" not in title_lower:
            return True

    return False


def is_sale_or_deed_record(
    record_type: str, document_title: Optional[str] = None
) -> bool:
    """
    Determine if a county record type indicates a sale or deed.

    This is a broader category than ownership transfer, used for
    detecting potential sale events.

    Args:
        record_type: Record type string (raw or normalized)
        document_title: Optional document title

    Returns:
        True if record indicates sale or deed
    """
    # Ownership transfers are always sale/deed records
    if is_ownership_transfer_record(record_type, document_title):
        return True

    # Additional sale-related types
    normalized_type = normalize_county_record_type(record_type)
    sale_types = {
        "deed_of_trust",  # May indicate sale with financing
    }

    return normalized_type in sale_types


def find_confirmed_transfers(
    property_id: int, db_path: Optional[Path | str] = None
) -> List[CountyTransferEvent]:
    """
    Find confirmed ownership transfer events for a property.

    Args:
        property_id: Property ID
        db_path: Optional database path

    Returns:
        List of CountyTransferEvent objects
    """
    try:
        query = """
        SELECT
            county_record_id,
            property_id,
            candidate_id,
            record_date as transfer_date,
            record_type,
            normalized_record_type,
            document_number,
            sale_price,
            transfer_tax,
            grantor,
            grantee,
            confidence,
            notes
        FROM county_record_observations
        WHERE property_id = ?
        AND normalized_record_type IN ('grant_deed', 'quitclaim_deed', 'trustee_deed', 'warranty_deed')
        ORDER BY record_date DESC
        """

        results = execute_query(query, (property_id,), database_path=db_path)

        transfers = []
        for row in results:
            transfer = CountyTransferEvent(
                county_record_id=row["county_record_id"],
                property_id=row["property_id"],
                candidate_id=row["candidate_id"],
                transfer_date=_parse_date_from_db(row["transfer_date"]),
                record_type=row["record_type"],
                normalized_record_type=row["normalized_record_type"],
                document_number=row["document_number"],
                sale_price=row["sale_price"],
                transfer_tax=row["transfer_tax"],
                grantor=row["grantor"],
                grantee=row["grantee"],
                confidence=row["confidence"] or "medium",
                notes=row["notes"],
            )
            transfers.append(transfer)

        return transfers

    except Exception as e:
        logger.error(f"Error finding confirmed transfers for property {property_id}: {e}")
        return []


def verify_effective_dom_reset(
    property_id: int,
    cycle_start: date,
    cycle_end: date,
    db_path: Optional[Path | str] = None,
) -> CountyVerificationResult:
    """
    Verify whether a confirmed county ownership transfer exists within a date range.

    This function provides foundation support for Effective DOM v2 integration.
    It does NOT automatically reset Effective DOM in this milestone.

    IMPORTANT: County-confirmed transfer may support Effective DOM reset,
    but it does NOT erase or zero out recent churn metrics.

    Args:
        property_id: Property ID
        cycle_start: Start of date range
        cycle_end: End of date range
        db_path: Optional database path

    Returns:
        CountyVerificationResult with verification details
    """
    try:
        # Find all ownership transfer records within date range
        query = """
        SELECT
            county_record_id,
            record_date,
            record_type,
            normalized_record_type,
            document_number,
            sale_price,
            transfer_tax,
            confidence
        FROM county_record_observations
        WHERE property_id = ?
        AND record_date >= ?
        AND record_date <= ?
        AND normalized_record_type IN ('grant_deed', 'quitclaim_deed', 'trustee_deed', 'warranty_deed')
        ORDER BY record_date DESC
        LIMIT 1
        """

        results = execute_query(
            query, (property_id, cycle_start, cycle_end), database_path=db_path
        )

        # Build verification result
        result = CountyVerificationResult(
            property_id=property_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )

        if results:
            row = results[0]
            result.county_transfer_found = True
            result.county_transfer_date = _parse_date_from_db(row["record_date"])
            result.county_transfer_record_type = row["normalized_record_type"]
            result.county_transfer_document_number = row["document_number"]
            result.county_transfer_confidence = row["confidence"] or "medium"
            result.county_reset_supported = True
            result.verification_notes = f"Confirmed ownership transfer: {row['record_type']}"

        # Get all county records for this property (for reporting)
        all_records_query = """
        SELECT source_type, COUNT(*) as count
        FROM county_record_observations
        WHERE property_id = ?
        GROUP BY source_type
        """

        all_results = execute_query(all_records_query, (property_id,), database_path=db_path)

        for row in all_results:
            result.county_records_seen += row["count"]
            source_type = row["source_type"]
            if source_type == "assessor":
                result.assessor_seen = True
            elif source_type == "recorder":
                result.recorder_seen = True
            elif source_type == "tax_collector":
                result.tax_collector_seen = True
            elif source_type == "permit":
                result.permit_seen = True

        # Get assessed value if available
        assessor_query = """
        SELECT assessed_value
        FROM county_record_observations
        WHERE property_id = ?
        AND source_type = 'assessor'
        AND assessed_value IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 1
        """

        assessor_results = execute_query(assessor_query, (property_id,), database_path=db_path)
        if assessor_results:
            result.assessed_value = assessor_results[0]["assessed_value"]

        # Get latest permit if available
        permit_query = """
        SELECT permit_type, permit_status
        FROM county_record_observations
        WHERE property_id = ?
        AND source_type = 'permit'
        AND permit_type IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 1
        """

        permit_results = execute_query(permit_query, (property_id,), database_path=db_path)
        if permit_results:
            result.latest_permit_type = permit_results[0]["permit_type"]
            result.latest_permit_status = permit_results[0]["permit_status"]

        return result

    except Exception as e:
        logger.error(f"Error verifying Effective DOM reset for property {property_id}: {e}")
        return CountyVerificationResult(
            property_id=property_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            verification_notes=f"Verification error: {str(e)}",
        )


def _parse_date_from_db(date_value: any) -> Optional[date]:
    """
    Parse date from database value.

    Args:
        date_value: Date value from database (string or date object)

    Returns:
        date object or None
    """
    if not date_value:
        return None

    if isinstance(date_value, date):
        return date_value

    if isinstance(date_value, str):
        try:
            # Try ISO format
            from datetime import datetime

            return datetime.fromisoformat(date_value).date()
        except ValueError:
            pass

    return None
