"""Import cross-site URLs from CSV and update watched properties."""

import csv
from pathlib import Path
from typing import Optional

from marketsentry.database import execute_query, execute_update
from marketsentry.logging_config import logger
from marketsentry.models import CrossSiteUrlImportResult, CrossSiteUrlImportRow
from marketsentry.normalization import normalize_address


def import_cross_site_urls_from_csv(
    csv_path: str, database_path: Optional[str] = None
) -> CrossSiteUrlImportResult:
    """
    Import cross-site URLs from CSV and update watched_properties table.

    Matches properties by:
    1. redfin_url (if provided)
    2. normalized_address (if redfin_url not provided or no match)

    Updates zillow_url, realtor_url, homes_url, compass_url fields.

    CSV Format:
        redfin_url, address, zillow_url, realtor_url, homes_url, compass_url, notes
        (at least one of redfin_url or address must be provided)

    Args:
        csv_path: Path to CSV file with cross-site URLs
        database_path: Optional database path

    Returns:
        CrossSiteUrlImportResult with import statistics
    """
    csv_file = Path(csv_path)

    if not csv_file.exists():
        return CrossSiteUrlImportResult(
            errors=[f"CSV file not found: {csv_path}"]
        )

    logger.info(f"Importing cross-site URLs from {csv_path}")

    result = CrossSiteUrlImportResult()

    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                result.total_rows_read += 1

                try:
                    # Parse row
                    import_row = _parse_import_row(row)

                    if not import_row:
                        result.rows_skipped += 1
                        result.errors.append(f"Row {row_num}: Could not parse row")
                        continue

                    # Find matching property
                    property_id = _find_watched_property(
                        import_row, database_path
                    )

                    if not property_id:
                        result.rows_skipped += 1
                        logger.debug(
                            f"Row {row_num}: No matching property for "
                            f"{import_row.redfin_url or import_row.address}"
                        )
                        continue

                    result.properties_matched += 1

                    # Update property with cross-site URLs
                    updated = _update_property_urls(
                        property_id, import_row, database_path
                    )

                    if updated:
                        result.properties_updated += 1
                        logger.info(
                            f"Updated property {property_id} with cross-site URLs"
                        )

                except Exception as e:
                    result.errors.append(f"Row {row_num}: {str(e)}")
                    logger.error(f"Error processing row {row_num}: {e}")
                    continue

        result.notes = (
            f"Processed {result.total_rows_read} rows, "
            f"updated {result.properties_updated} properties"
        )

        logger.info(result.notes)

    except Exception as e:
        result.errors.append(f"File processing error: {str(e)}")
        logger.error(f"Error reading CSV file: {e}")

    return result


def _parse_import_row(row: dict) -> Optional[CrossSiteUrlImportRow]:
    """
    Parse a CSV row into a CrossSiteUrlImportRow.

    Args:
        row: Dictionary from CSV reader

    Returns:
        CrossSiteUrlImportRow or None if invalid
    """
    try:
        # Clean and extract fields
        redfin_url = row.get("redfin_url", "").strip() or None
        address = row.get("address", "").strip() or None
        zillow_url = row.get("zillow_url", "").strip() or None
        realtor_url = row.get("realtor_url", "").strip() or None
        homes_url = row.get("homes_url", "").strip() or None
        compass_url = row.get("compass_url", "").strip() or None
        notes = row.get("notes", "").strip() or None

        # Must have at least redfin_url or address
        if not redfin_url and not address:
            return None

        # Normalize address if provided
        normalized_address = None
        if address:
            normalized_address = normalize_address(address)

        return CrossSiteUrlImportRow(
            redfin_url=redfin_url,
            address=address,
            normalized_address=normalized_address,
            zillow_url=zillow_url,
            realtor_url=realtor_url,
            homes_url=homes_url,
            compass_url=compass_url,
            notes=notes,
        )

    except Exception as e:
        logger.warning(f"Error parsing row: {e}")
        return None


def _find_watched_property(
    import_row: CrossSiteUrlImportRow, database_path: Optional[str] = None
) -> Optional[int]:
    """
    Find watched property ID by redfin_url or normalized_address.

    Args:
        import_row: Import row with matching criteria
        database_path: Optional database path

    Returns:
        property_id or None
    """
    try:
        # Try matching by redfin_url first
        if import_row.redfin_url:
            query = """
            SELECT property_id
            FROM watched_properties
            WHERE redfin_url = ?
            AND active_watch_status = 1
            """
            result = execute_query(
                query, (import_row.redfin_url,), database_path=database_path
            )

            if result:
                return result[0]["property_id"]

        # Try matching by normalized_address
        if import_row.normalized_address:
            query = """
            SELECT property_id
            FROM watched_properties
            WHERE normalized_address = ?
            AND active_watch_status = 1
            """
            result = execute_query(
                query,
                (import_row.normalized_address,),
                database_path=database_path,
            )

            if result:
                return result[0]["property_id"]

    except Exception as e:
        logger.error(f"Error finding watched property: {e}")

    return None


def _update_property_urls(
    property_id: int,
    import_row: CrossSiteUrlImportRow,
    database_path: Optional[str] = None,
) -> bool:
    """
    Update watched property with cross-site URLs.

    Args:
        property_id: Property ID to update
        import_row: Import row with URLs
        database_path: Optional database path

    Returns:
        True if updated successfully
    """
    try:
        # Build update query dynamically
        updates = []
        params = []

        if import_row.zillow_url:
            updates.append("zillow_url = ?")
            params.append(import_row.zillow_url)

        if import_row.realtor_url:
            updates.append("realtor_url = ?")
            params.append(import_row.realtor_url)

        if import_row.homes_url:
            updates.append("homes_url = ?")
            params.append(import_row.homes_url)

        if import_row.compass_url:
            updates.append("compass_url = ?")
            params.append(import_row.compass_url)

        if not updates:
            return False  # Nothing to update

        # Always update the updated_at timestamp
        updates.append("updated_at = CURRENT_TIMESTAMP")

        # Build and execute query
        query = f"""
        UPDATE watched_properties
        SET {', '.join(updates)}
        WHERE property_id = ?
        """
        params.append(property_id)

        execute_update(query, tuple(params), database_path=database_path)
        return True

    except Exception as e:
        logger.error(f"Error updating property {property_id}: {e}")
        return False
