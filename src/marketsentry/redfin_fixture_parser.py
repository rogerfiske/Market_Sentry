"""Parse saved Redfin HTML fixtures to extract candidate property URLs."""

import hashlib
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup

from marketsentry.database import execute_insert, insert_candidate
from marketsentry.logging_config import logger
from marketsentry.models import (
    CandidateProperty,
    DiscoveryRunResult,
    RedfinCandidateSummary,
    RedfinParseResult,
)
from marketsentry.normalization import normalize_address
from marketsentry.redfin_url_utils import (
    extract_address_from_redfin_url,
    extract_city_from_redfin_url,
    extract_zip_from_redfin_url,
    is_redfin_url,
    normalize_redfin_url,
)


def parse_redfin_html_fixture(html_file_path: str) -> RedfinParseResult:
    """
    Parse a saved Redfin HTML fixture to extract property URLs and data.

    This function is resilient to missing fields and does not perform
    any network calls.

    Args:
        html_file_path: Path to HTML fixture file

    Returns:
        RedfinParseResult with extracted candidates and status
    """
    html_path = Path(html_file_path)

    if not html_path.exists():
        return RedfinParseResult(
            source_file=html_file_path,
            parse_status="failed",
            errors=[f"File not found: {html_file_path}"],
        )

    logger.info(f"Parsing Redfin HTML fixture: {html_file_path}")

    result = RedfinParseResult(
        source_file=html_file_path,
        parse_status="success",
    )

    try:
        # Read HTML content
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Parse HTML
        soup = BeautifulSoup(html_content, "html.parser")

        # Find all links
        all_links = soup.find_all("a", href=True)

        # Extract Redfin property URLs
        property_urls = set()

        for link in all_links:
            href = link.get("href", "")

            # Handle relative URLs
            if href.startswith("/"):
                href = f"https://www.redfin.com{href}"

            # Validate and normalize
            if is_redfin_url(href):
                normalized_url = normalize_redfin_url(href)
                if normalized_url:
                    property_urls.add(normalized_url)

        if not property_urls:
            result.parse_status = "partial"
            result.warnings.append("No valid Redfin property URLs found in fixture")
            logger.warning(f"No property URLs found in {html_file_path}")
            return result

        # Create candidate summaries
        for url in property_urls:
            try:
                # Extract basic info from URL
                address = extract_address_from_redfin_url(url)
                city = extract_city_from_redfin_url(url)
                zip_code = extract_zip_from_redfin_url(url)

                # Create summary
                summary = RedfinCandidateSummary(
                    redfin_url=url,
                    source_site="redfin",
                    source_search_url=html_file_path,  # Reference to fixture file
                    address=address,
                    normalized_address=normalize_address(address) if address else None,
                    city=city,
                    zip=zip_code,
                )

                result.candidates.append(summary)
                result.candidates_found += 1

            except Exception as e:
                logger.warning(f"Error creating summary for {url}: {e}")
                result.warnings.append(f"Failed to create summary for {url}: {str(e)}")
                continue

        if result.candidates_found == 0:
            result.parse_status = "failed"
            result.errors.append("No valid candidates could be created from URLs")
        elif result.warnings:
            result.parse_status = "partial"

        logger.info(
            f"Parsed {html_file_path}: found {result.candidates_found} candidates"
        )

    except Exception as e:
        logger.error(f"Error parsing {html_file_path}: {e}")
        result.parse_status = "failed"
        result.errors.append(f"Parse error: {str(e)}")

    return result


def parse_redfin_fixtures_from_directory(
    directory_path: str,
    database_path: Optional[str] = None,
    record_source_pages: bool = True,
) -> DiscoveryRunResult:
    """
    Parse all Redfin HTML fixtures in a directory and insert candidates.

    Args:
        directory_path: Path to directory containing HTML fixtures
        database_path: Database path (optional)
        record_source_pages: Whether to record source page audit entries

    Returns:
        DiscoveryRunResult with parsing and insertion statistics
    """
    dir_path = Path(directory_path)

    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")

    if not dir_path.is_dir():
        raise ValueError(f"Not a directory: {directory_path}")

    logger.info(f"Parsing Redfin fixtures from {directory_path}")

    # Initialize result
    result = DiscoveryRunResult(
        source_type="saved_fixture",
        source_identifier=directory_path,
    )

    # Find HTML files
    html_files = list(dir_path.glob("*.html")) + list(dir_path.glob("*.htm"))

    if not html_files:
        logger.warning(f"No HTML files found in {directory_path}")
        result.notes = "No HTML files found in directory"
        return result

    result.total_rows_read = len(html_files)

    # Process each file
    for html_file in html_files:
        try:
            # Parse fixture
            parse_result = parse_redfin_html_fixture(str(html_file))

            result.parse_warnings += len(parse_result.warnings)
            result.parse_errors += len(parse_result.errors)

            # Insert candidates
            for summary in parse_result.candidates:
                try:
                    # Create candidate property
                    candidate = CandidateProperty(
                        discovery_date=date.today(),
                        source_site=summary.source_site,
                        source_search_url=summary.source_search_url or "",
                        redfin_url=summary.redfin_url,
                        address=summary.address or "",
                        normalized_address=summary.normalized_address,
                        city=summary.city or "",
                        zip=summary.zip or "",
                        price=summary.price,
                        beds=summary.beds,
                        baths=summary.baths,
                        sqft=summary.sqft,
                        lot_size=summary.lot_size,
                        displayed_dom=summary.displayed_dom,
                        quiet_score=summary.quiet_score,
                        vibrancy_score=summary.vibrancy_score,
                        quiet_gatekeeper_result=summary.quiet_gatekeeper_result,
                        garage_spaces=summary.garage_spaces,
                        gas_service=summary.gas_service,
                        gas_evidence=summary.gas_evidence,
                        user_notes=summary.basic_notes,
                    )

                    # Insert candidate
                    candidate_id = insert_candidate(
                        candidate, skip_if_exists=True, database_path=database_path
                    )

                    if candidate_id:
                        result.candidates_inserted += 1

                        # Record source page if requested
                        if record_source_pages:
                            try:
                                _record_source_page(
                                    candidate_id=candidate_id,
                                    source_file=str(html_file),
                                    database_path=database_path,
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to record source page for candidate {candidate_id}: {e}"
                                )

                    else:
                        result.candidates_skipped += 1

                except Exception as e:
                    logger.error(f"Error inserting candidate from {html_file}: {e}")
                    result.rows_rejected += 1
                    result.parse_errors += 1
                    continue

        except Exception as e:
            logger.error(f"Error processing {html_file}: {e}")
            result.rows_rejected += 1
            result.parse_errors += 1
            continue

    logger.info(
        f"Fixture parsing complete: {result.candidates_inserted} inserted, "
        f"{result.candidates_skipped} skipped, {result.rows_rejected} rejected"
    )

    return result


def _record_source_page(
    candidate_id: int,
    source_file: str,
    database_path: Optional[str] = None,
) -> None:
    """
    Record a source page audit entry for a parsed fixture.

    Args:
        candidate_id: Candidate ID
        source_file: Path to source HTML file
        database_path: Database path (optional)
    """
    try:
        # Calculate content hash
        file_path = Path(source_file)
        if file_path.exists():
            with open(file_path, "rb") as f:
                content = f.read()
                content_hash = hashlib.sha256(content).hexdigest()
        else:
            content_hash = None

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
            "saved_fixture",
            content_hash,
            "1.0",  # Parser version
            "success",
        )

        execute_insert(query, params, database_path=database_path)

    except Exception as e:
        logger.warning(f"Failed to record source page: {e}")
        # Don't raise - this is non-critical
