"""County record CSV import and matching logic.

Imports manually supplied county records from CSV files and matches them
to candidates or watched properties.
"""

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from marketsentry.county_verification import normalize_county_record_type
from marketsentry.database import execute_query, execute_update
from marketsentry.logging_config import logger
from marketsentry.models import (
    CountyRecordImportResult,
    CountyRecordImportRow,
    CountyRecordObservation,
)
from marketsentry.normalization import normalize_address, normalize_apn


def import_county_records_csv(
    file_path: str | Path, database_path: Optional[str] = None
) -> CountyRecordImportResult:
    """
    Import county records from CSV file.

    Required columns:
    - source_type
    - record_date
    - record_type

    At least one identity field required:
    - apn
    - address
    - candidate_id
    - property_id

    Optional columns:
    - city, zip, document_number, document_title, grantor, grantee,
      sale_price, transfer_tax, assessed_value, owner_name,
      permit_number, permit_type, permit_status, notes, source_url

    Args:
        file_path: Path to CSV file
        database_path: Optional database path

    Returns:
        CountyRecordImportResult with counts and errors
    """
    file_path = Path(file_path)

    if not file_path.exists():
        logger.error(f"County records CSV file not found: {file_path}")
        return CountyRecordImportResult(
            errors=[f"File not found: {file_path}"],
        )

    result = CountyRecordImportResult()

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row_idx, row in enumerate(reader, start=1):
                result.total_rows_read += 1

                # Parse row
                import_row = _parse_import_row(row)

                # Validate row
                validation_error = _validate_import_row(import_row)
                if validation_error:
                    result.rows_rejected += 1
                    result.errors.append(f"Row {row_idx}: {validation_error}")
                    continue

                # Try to match to property or candidate
                match_result = _match_county_record(import_row, database_path)

                if match_result["matched"]:
                    result.rows_matched += 1
                else:
                    result.rows_unmatched += 1
                    if match_result.get("warning"):
                        result.warnings.append(f"Row {row_idx}: {match_result['warning']}")

                # Build county record observation
                county_record = _build_county_record_observation(
                    import_row,
                    match_result.get("property_id"),
                    match_result.get("candidate_id"),
                    match_result.get("match_method"),
                )

                # Insert county record
                inserted = _insert_county_record(county_record, database_path)
                if inserted:
                    result.rows_inserted += 1
                else:
                    result.errors.append(f"Row {row_idx}: Failed to insert county record")

        logger.info(
            f"County record import complete: {result.rows_inserted} inserted, "
            f"{result.rows_matched} matched, {result.rows_unmatched} unmatched, "
            f"{result.rows_rejected} rejected"
        )

    except Exception as e:
        logger.error(f"Error importing county records CSV: {e}")
        result.errors.append(f"Import exception: {str(e)}")

    return result


def _parse_import_row(row: dict) -> CountyRecordImportRow:
    """
    Parse a CSV row into CountyRecordImportRow.

    Args:
        row: CSV row dictionary

    Returns:
        CountyRecordImportRow
    """
    return CountyRecordImportRow(
        source_type=row.get("source_type", "").strip(),
        record_date=_parse_date_safe(row.get("record_date")),
        record_type=row.get("record_type", "").strip(),
        apn=row.get("apn", "").strip() or None,
        address=row.get("address", "").strip() or None,
        candidate_id=_parse_int_safe(row.get("candidate_id")),
        property_id=_parse_int_safe(row.get("property_id")),
        city=row.get("city", "").strip() or None,
        zip=row.get("zip", "").strip() or None,
        document_number=row.get("document_number", "").strip() or None,
        document_title=row.get("document_title", "").strip() or None,
        grantor=row.get("grantor", "").strip() or None,
        grantee=row.get("grantee", "").strip() or None,
        sale_price=_parse_float_safe(row.get("sale_price")),
        transfer_tax=_parse_float_safe(row.get("transfer_tax")),
        assessed_value=_parse_float_safe(row.get("assessed_value")),
        owner_name=row.get("owner_name", "").strip() or None,
        permit_number=row.get("permit_number", "").strip() or None,
        permit_type=row.get("permit_type", "").strip() or None,
        permit_status=row.get("permit_status", "").strip() or None,
        notes=row.get("notes", "").strip() or None,
        source_url=row.get("source_url", "").strip() or None,
    )


def _validate_import_row(import_row: CountyRecordImportRow) -> Optional[str]:
    """
    Validate import row.

    Args:
        import_row: CountyRecordImportRow

    Returns:
        Error message if invalid, None if valid
    """
    # Validate source_type
    valid_source_types = ["assessor", "recorder", "tax_collector", "permit"]
    if import_row.source_type not in valid_source_types:
        return f"Invalid source_type: {import_row.source_type}. Must be one of {valid_source_types}"

    # Validate record_type
    if not import_row.record_type:
        return "Missing required field: record_type"

    # Validate at least one identity field
    if not any(
        [
            import_row.property_id,
            import_row.candidate_id,
            import_row.apn,
            import_row.address,
        ]
    ):
        return "At least one identity field required: property_id, candidate_id, apn, or address"

    return None


def _match_county_record(
    import_row: CountyRecordImportRow, database_path: Optional[str]
) -> dict:
    """
    Match county record to property or candidate.

    Matching priority:
    1. property_id (exact match)
    2. candidate_id (exact match)
    3. APN (normalized match)
    4. address (normalized match)

    Args:
        import_row: CountyRecordImportRow
        database_path: Optional database path

    Returns:
        dict with matched: bool, property_id, candidate_id, match_method, warning
    """
    # 1. Try property_id
    if import_row.property_id:
        query = "SELECT property_id FROM watched_properties WHERE property_id = ?"
        results = execute_query(query, (import_row.property_id,), database_path=database_path)
        if results:
            return {
                "matched": True,
                "property_id": import_row.property_id,
                "candidate_id": None,
                "match_method": "property_id",
            }
        else:
            return {
                "matched": False,
                "warning": f"property_id {import_row.property_id} not found in watched_properties",
            }

    # 2. Try candidate_id
    if import_row.candidate_id:
        query = "SELECT candidate_id FROM candidate_review_queue WHERE candidate_id = ?"
        results = execute_query(query, (import_row.candidate_id,), database_path=database_path)
        if results:
            return {
                "matched": True,
                "property_id": None,
                "candidate_id": import_row.candidate_id,
                "match_method": "candidate_id",
            }
        else:
            return {
                "matched": False,
                "warning": f"candidate_id {import_row.candidate_id} not found in candidate_review_queue",
            }

    # 3. Try APN
    if import_row.apn:
        normalized_apn = normalize_apn(import_row.apn)

        # Try watched_properties first
        query = """
        SELECT property_id
        FROM watched_properties
        WHERE apn = ? OR apn = ?
        LIMIT 1
        """
        results = execute_query(
            query, (import_row.apn, normalized_apn), database_path=database_path
        )
        if results:
            return {
                "matched": True,
                "property_id": results[0]["property_id"],
                "candidate_id": None,
                "match_method": "apn",
            }

        # Try candidate_review_queue
        # Note: candidates don't have APN field yet, so skip for now

    # 4. Try normalized address
    if import_row.address:
        normalized_address = normalize_address(import_row.address)

        # Try watched_properties first
        query = """
        SELECT property_id
        FROM watched_properties
        WHERE normalized_address = ?
        LIMIT 1
        """
        results = execute_query(query, (normalized_address,), database_path=database_path)
        if results:
            return {
                "matched": True,
                "property_id": results[0]["property_id"],
                "candidate_id": None,
                "match_method": "normalized_address",
            }

        # Try candidate_review_queue
        query = """
        SELECT candidate_id
        FROM candidate_review_queue
        WHERE normalized_address = ?
        LIMIT 1
        """
        results = execute_query(query, (normalized_address,), database_path=database_path)
        if results:
            return {
                "matched": True,
                "property_id": None,
                "candidate_id": results[0]["candidate_id"],
                "match_method": "normalized_address",
            }

    # No match found
    return {
        "matched": False,
        "warning": "No property or candidate match found",
    }


def _build_county_record_observation(
    import_row: CountyRecordImportRow,
    property_id: Optional[int],
    candidate_id: Optional[int],
    match_method: Optional[str],
) -> CountyRecordObservation:
    """
    Build CountyRecordObservation from import row and match result.

    Args:
        import_row: CountyRecordImportRow
        property_id: Matched property ID or None
        candidate_id: Matched candidate ID or None
        match_method: Match method or None

    Returns:
        CountyRecordObservation
    """
    # Normalize fields
    normalized_apn = normalize_apn(import_row.apn) if import_row.apn else None
    normalized_address = normalize_address(import_row.address) if import_row.address else None
    normalized_record_type = normalize_county_record_type(import_row.record_type)

    return CountyRecordObservation(
        candidate_id=candidate_id,
        property_id=property_id,
        source_type=import_row.source_type,
        source_url=import_row.source_url,
        record_date=import_row.record_date,
        record_type=import_row.record_type,
        normalized_record_type=normalized_record_type,
        document_number=import_row.document_number,
        document_title=import_row.document_title,
        apn=import_row.apn,
        normalized_apn=normalized_apn,
        address=import_row.address,
        normalized_address=normalized_address,
        city=import_row.city,
        zip=import_row.zip,
        grantor=import_row.grantor,
        grantee=import_row.grantee,
        sale_price=import_row.sale_price,
        transfer_tax=import_row.transfer_tax,
        assessed_value=import_row.assessed_value,
        owner_name=import_row.owner_name,
        permit_number=import_row.permit_number,
        permit_type=import_row.permit_type,
        permit_status=import_row.permit_status,
        match_method=match_method,
        confidence="medium",
        notes=import_row.notes,
    )


def _insert_county_record(
    county_record: CountyRecordObservation, database_path: Optional[str]
) -> bool:
    """
    Insert county record observation into database.

    Args:
        county_record: CountyRecordObservation
        database_path: Optional database path

    Returns:
        True if inserted successfully, False otherwise
    """
    try:
        query = """
        INSERT INTO county_record_observations (
            candidate_id, property_id, source_type, county_name, source_url,
            record_date, record_type, normalized_record_type,
            document_number, document_title,
            apn, normalized_apn, address, normalized_address,
            city, state, zip,
            grantor, grantee, sale_price, transfer_tax, assessed_value,
            owner_name, permit_number, permit_type, permit_status,
            match_method, confidence, notes, created_at
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?
        )
        """

        params = (
            county_record.candidate_id,
            county_record.property_id,
            county_record.source_type,
            county_record.county_name,
            county_record.source_url,
            county_record.record_date,
            county_record.record_type,
            county_record.normalized_record_type,
            county_record.document_number,
            county_record.document_title,
            county_record.apn,
            county_record.normalized_apn,
            county_record.address,
            county_record.normalized_address,
            county_record.city,
            county_record.state,
            county_record.zip,
            county_record.grantor,
            county_record.grantee,
            county_record.sale_price,
            county_record.transfer_tax,
            county_record.assessed_value,
            county_record.owner_name,
            county_record.permit_number,
            county_record.permit_type,
            county_record.permit_status,
            county_record.match_method,
            county_record.confidence,
            county_record.notes,
            datetime.now(),
        )

        execute_update(query, params, database_path=database_path)
        return True

    except Exception as e:
        logger.error(f"Error inserting county record: {e}")
        return False


def _parse_date_safe(date_str: Optional[str]) -> Optional[date]:
    """
    Parse date string safely.

    Supports: YYYY-MM-DD, MM/DD/YYYY.

    Args:
        date_str: Date string

    Returns:
        date object or None
    """
    if not date_str or not date_str.strip():
        return None

    formats = ["%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue

    logger.warning(f"Could not parse date: {date_str}")
    return None


def _parse_int_safe(value: Optional[str]) -> Optional[int]:
    """
    Parse integer safely.

    Args:
        value: String value

    Returns:
        Integer or None
    """
    if not value or not value.strip():
        return None

    try:
        return int(value.strip())
    except ValueError:
        return None


def _parse_float_safe(value: Optional[str]) -> Optional[float]:
    """
    Parse float safely.

    Handles currency formatting.

    Args:
        value: String value

    Returns:
        Float or None
    """
    if not value or not value.strip():
        return None

    try:
        # Remove $ and commas
        clean_value = value.strip().replace("$", "").replace(",", "")
        return float(clean_value)
    except ValueError:
        return None
