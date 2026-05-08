"""Parse cross-site HTML fixtures and insert observations into database."""

from pathlib import Path
from typing import List, Optional

from marketsentry.compass_parser import parse_compass_detail_file
from marketsentry.database import execute_insert, execute_query
from marketsentry.homes_parser import parse_homes_detail_file
from marketsentry.logging_config import logger
from marketsentry.models import (
    CrossSiteEnrichmentResult,
    CrossSiteObservation,
    CrossSiteParseResult,
)
from marketsentry.realtor_parser import parse_realtor_detail_file
from marketsentry.zillow_parser import parse_zillow_detail_file


def parse_cross_site_directory(
    directory_path: str,
    source_site: str,
    database_path: Optional[str] = None,
) -> CrossSiteEnrichmentResult:
    """
    Parse cross-site HTML fixtures from directory and insert observations.

    Args:
        directory_path: Path to directory containing HTML files
        source_site: Source site (zillow, realtor, homes, compass)
        database_path: Optional database path

    Returns:
        CrossSiteEnrichmentResult with enrichment statistics
    """
    dir_path = Path(directory_path)

    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")

    if not dir_path.is_dir():
        raise ValueError(f"Not a directory: {directory_path}")

    logger.info(f"Parsing {source_site} fixtures from {directory_path}")

    # Parse all HTML files
    parse_results = _parse_directory_by_site(dir_path, source_site)

    # Initialize result
    result = CrossSiteEnrichmentResult(
        total_files_processed=len(parse_results)
    )

    # Process each parsed result
    for parse_result in parse_results:
        # Count parsing status
        if parse_result.parse_status in ["success", "partial"]:
            result.observations_parsed += 1
        result.parse_warnings += len(parse_result.warnings)
        result.parse_errors += len(parse_result.errors)

        # Skip if parsing failed or no facts
        if not parse_result.property_facts:
            continue

        # Try to match to watched property
        property_id = _find_watched_property_for_observation(
            parse_result, database_path
        )

        if property_id:
            result.properties_matched += 1

            # Insert observation
            inserted = insert_cross_site_observation(
                property_id, parse_result, database_path
            )

            if inserted:
                result.observations_inserted += 1

    result.notes = (
        f"Processed {result.total_files_processed} files, "
        f"inserted {result.observations_inserted} observations"
    )

    logger.info(result.notes)

    return result


def _parse_directory_by_site(
    directory: Path, source_site: str
) -> List[CrossSiteParseResult]:
    """
    Parse all HTML files in directory using appropriate parser.

    Args:
        directory: Directory containing HTML files
        source_site: Source site (zillow, realtor, homes, compass)

    Returns:
        List of CrossSiteParseResult
    """
    results = []
    html_files = list(directory.glob("*.html")) + list(directory.glob("*.htm"))

    for html_file in html_files:
        try:
            if source_site == "zillow":
                result = parse_zillow_detail_file(html_file)
            elif source_site == "realtor":
                result = parse_realtor_detail_file(html_file)
            elif source_site == "homes":
                result = parse_homes_detail_file(html_file)
            elif source_site == "compass":
                result = parse_compass_detail_file(html_file)
            else:
                logger.warning(f"Unknown source site: {source_site}")
                continue

            results.append(result)

        except Exception as e:
            logger.error(f"Error parsing file {html_file}: {e}")
            continue

    return results


def _find_watched_property_for_observation(
    parse_result: CrossSiteParseResult, database_path: Optional[str] = None
) -> Optional[int]:
    """
    Find watched property ID for a cross-site observation.

    Matches by:
    1. Source site URL (zillow_url, realtor_url, etc.)
    2. Normalized address

    Args:
        parse_result: Parse result with property data
        database_path: Optional database path

    Returns:
        property_id or None
    """
    try:
        source_site = parse_result.source_site

        # Try matching by source URL
        if parse_result.source_url:
            url_column = f"{source_site}_url"
            query = f"""
            SELECT property_id
            FROM watched_properties
            WHERE {url_column} = ?
            AND active_watch_status = 1
            """
            result = execute_query(
                query, (parse_result.source_url,), database_path=database_path
            )

            if result:
                return result[0]["property_id"]

        # Try matching by normalized address
        if parse_result.normalized_address:
            query = """
            SELECT property_id
            FROM watched_properties
            WHERE normalized_address = ?
            AND active_watch_status = 1
            """
            result = execute_query(
                query,
                (parse_result.normalized_address,),
                database_path=database_path,
            )

            if result:
                return result[0]["property_id"]

    except Exception as e:
        logger.error(f"Error finding watched property: {e}")

    return None


def insert_cross_site_observation(
    property_id: int,
    parse_result: CrossSiteParseResult,
    database_path: Optional[str] = None,
) -> bool:
    """
    Insert cross-site observation into database.

    Args:
        property_id: Watched property ID
        parse_result: Parse result with observation data
        database_path: Optional database path

    Returns:
        True if inserted successfully
    """
    try:
        facts = parse_result.property_facts

        # Check for duplicate observation
        if _observation_exists(
            property_id, parse_result.source_site, database_path
        ):
            logger.debug(
                f"Observation already exists for property {property_id} "
                f"from {parse_result.source_site}"
            )
            return False

        # Build insert query
        query = """
        INSERT INTO cross_site_observations (
            property_id, source_site, source_url, normalized_source_url,
            match_method, address, normalized_address, city, state, zip,
            price, beds, baths, sqft, lot_size, listing_status,
            displayed_dom, garage_spaces, gas_service, gas_evidence,
            listing_agent, listing_broker, mls_number, source_mls,
            property_description, parse_status, parse_warnings, notes
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?
        )
        """

        # Prepare parse warnings
        parse_warnings = None
        if parse_result.warnings:
            parse_warnings = "; ".join(parse_result.warnings[:3])  # Limit length

        params = (
            property_id,
            parse_result.source_site,
            parse_result.source_url,
            parse_result.source_url,  # normalized_source_url (same for now)
            "html_parse",  # match_method
            parse_result.address,
            parse_result.normalized_address,
            parse_result.city,
            parse_result.state,
            parse_result.zip,
            facts.price,
            facts.beds,
            facts.baths,
            facts.sqft,
            facts.lot_size,
            facts.listing_status,
            facts.displayed_dom,
            facts.garage_spaces,
            facts.gas_service,
            facts.gas_evidence,
            facts.listing_agent,
            facts.listing_broker,
            facts.mls_number,
            facts.source_mls,
            facts.property_description,
            parse_result.parse_status,
            parse_warnings,
            None,  # notes
        )

        execute_insert(query, params, database_path=database_path)
        logger.info(
            f"Inserted cross-site observation for property {property_id} "
            f"from {parse_result.source_site}"
        )
        return True

    except Exception as e:
        logger.error(
            f"Error inserting cross-site observation for property {property_id}: {e}"
        )
        return False


def _observation_exists(
    property_id: int, source_site: str, database_path: Optional[str] = None
) -> bool:
    """
    Check if a cross-site observation already exists.

    Checks for existing observation from same source site within last 24 hours.

    Args:
        property_id: Property ID
        source_site: Source site
        database_path: Optional database path

    Returns:
        True if observation exists
    """
    try:
        query = """
        SELECT COUNT(*) as count
        FROM cross_site_observations
        WHERE property_id = ?
        AND source_site = ?
        AND observed_at >= datetime('now', '-24 hours')
        """

        result = execute_query(
            query, (property_id, source_site), database_path=database_path
        )

        return result[0]["count"] > 0 if result else False

    except Exception:
        return False
