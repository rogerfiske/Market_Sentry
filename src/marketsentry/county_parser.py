"""County record HTML fixture parser.

Parses saved/static county HTML fixtures (assessor, recorder, tax_collector, permits).
NO live network calls. NO browser automation.
"""

from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup

from marketsentry.logging_config import logger
from marketsentry.models import CountyRecordObservation, CountyRecordParseResult
from marketsentry.normalization import normalize_address, normalize_apn


def parse_county_record_html(
    html: str, source_type: str, source_url: Optional[str] = None
) -> CountyRecordParseResult:
    """
    Parse county record HTML.

    This function parses saved/static HTML fixtures from county sources.
    NO live network calls.

    Args:
        html: HTML content
        source_type: Source type (assessor, recorder, tax_collector, permit)
        source_url: Optional source URL

    Returns:
        CountyRecordParseResult with parsed data

    Raises:
        ValueError: If source_type is invalid
    """
    valid_source_types = ["assessor", "recorder", "tax_collector", "permit"]
    if source_type not in valid_source_types:
        return CountyRecordParseResult(
            source_type=source_type,
            parse_status="failed",
            errors=[f"Invalid source_type: {source_type}. Must be one of {valid_source_types}"],
        )

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Dispatch to specific parser based on source type
        if source_type == "assessor":
            return _parse_assessor_html(soup, source_url)
        elif source_type == "recorder":
            return _parse_recorder_html(soup, source_url)
        elif source_type == "tax_collector":
            return _parse_tax_collector_html(soup, source_url)
        elif source_type == "permit":
            return _parse_permit_html(soup, source_url)
        else:
            return CountyRecordParseResult(
                source_type=source_type,
                parse_status="failed",
                errors=[f"No parser implemented for source_type: {source_type}"],
            )

    except Exception as e:
        logger.error(f"Error parsing county HTML for {source_type}: {e}")
        return CountyRecordParseResult(
            source_type=source_type,
            parse_status="failed",
            errors=[f"Parse exception: {str(e)}"],
        )


def parse_county_record_file(file_path: Path, source_type: str) -> CountyRecordParseResult:
    """
    Parse a county record HTML file.

    Args:
        file_path: Path to HTML file
        source_type: Source type (assessor, recorder, tax_collector, permit)

    Returns:
        CountyRecordParseResult
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            html = f.read()

        result = parse_county_record_html(html, source_type)
        result.source_file = str(file_path)
        return result

    except FileNotFoundError:
        logger.error(f"County record file not found: {file_path}")
        return CountyRecordParseResult(
            source_file=str(file_path),
            source_type=source_type,
            parse_status="failed",
            errors=[f"File not found: {file_path}"],
        )
    except Exception as e:
        logger.error(f"Error reading county record file {file_path}: {e}")
        return CountyRecordParseResult(
            source_file=str(file_path),
            source_type=source_type,
            parse_status="failed",
            errors=[f"File read exception: {str(e)}"],
        )


def parse_county_record_directory(
    directory: Path, source_type: str
) -> List[CountyRecordParseResult]:
    """
    Parse all county record HTML files in a directory.

    Args:
        directory: Directory containing HTML files
        source_type: Source type (assessor, recorder, tax_collector, permit)

    Returns:
        List of CountyRecordParseResult objects
    """
    results = []

    if not directory.exists():
        logger.warning(f"County record directory does not exist: {directory}")
        return results

    if not directory.is_dir():
        logger.warning(f"Path is not a directory: {directory}")
        return results

    # Find all HTML files
    html_files = list(directory.glob("*.html")) + list(directory.glob("*.htm"))

    if not html_files:
        logger.warning(f"No HTML files found in {directory}")

    for file_path in html_files:
        logger.info(f"Parsing county record file: {file_path}")
        result = parse_county_record_file(file_path, source_type)
        results.append(result)

    return results


def _parse_assessor_html(soup: BeautifulSoup, source_url: Optional[str]) -> CountyRecordParseResult:
    """
    Parse assessor HTML fixture.

    Extracts: APN, address, assessed value, owner name.
    """
    warnings = []
    errors = []

    # Extract fields - these are minimal/synthetic fixtures, so use simple selectors
    apn_raw = _extract_text(soup, class_="apn-value")
    address = _extract_text(soup, class_="property-address")
    assessed_value_raw = _extract_text(soup, class_="assessed-value")
    owner_name = _extract_text(soup, class_="owner-name")

    # Parse assessed value
    assessed_value = _parse_currency(assessed_value_raw)
    if assessed_value_raw and not assessed_value:
        warnings.append(f"Could not parse assessed value: {assessed_value_raw}")

    # Normalize fields
    normalized_apn = normalize_apn(apn_raw) if apn_raw else None
    normalized_address = normalize_address(address) if address else None

    # Build county record
    county_record = CountyRecordObservation(
        source_type="assessor",
        source_url=source_url,
        record_type="assessment",
        normalized_record_type="assessment",
        apn=apn_raw,
        normalized_apn=normalized_apn,
        address=address,
        normalized_address=normalized_address,
        assessed_value=assessed_value,
        owner_name=owner_name,
        confidence="medium",
    )

    # Determine parse status
    if not apn_raw and not address:
        parse_status = "failed"
        errors.append("No APN or address found in assessor HTML")
    elif not assessed_value:
        parse_status = "partial"
        warnings.append("Assessed value not found")
    else:
        parse_status = "success"

    return CountyRecordParseResult(
        source_type="assessor",
        parse_status=parse_status,
        county_record=county_record,
        warnings=warnings,
        errors=errors,
    )


def _parse_recorder_html(soup: BeautifulSoup, source_url: Optional[str]) -> CountyRecordParseResult:
    """
    Parse recorder HTML fixture.

    Extracts: document number, record type, record date, apn, address, grantor, grantee, sale price.
    """
    warnings = []
    errors = []

    # Extract fields
    document_number = _extract_text(soup, class_="document-number")
    record_type_raw = _extract_text(soup, class_="record-type")
    document_title = _extract_text(soup, class_="document-title")
    record_date_raw = _extract_text(soup, class_="record-date")
    apn_raw = _extract_text(soup, class_="apn-value")
    address = _extract_text(soup, class_="property-address")
    grantor = _extract_text(soup, class_="grantor")
    grantee = _extract_text(soup, class_="grantee")
    sale_price_raw = _extract_text(soup, class_="sale-price")
    transfer_tax_raw = _extract_text(soup, class_="transfer-tax")

    # Parse date
    record_date = _parse_date(record_date_raw)
    if record_date_raw and not record_date:
        warnings.append(f"Could not parse record date: {record_date_raw}")

    # Parse currency
    sale_price = _parse_currency(sale_price_raw)
    if sale_price_raw and not sale_price:
        warnings.append(f"Could not parse sale price: {sale_price_raw}")

    transfer_tax = _parse_currency(transfer_tax_raw)
    if transfer_tax_raw and not transfer_tax:
        warnings.append(f"Could not parse transfer tax: {transfer_tax_raw}")

    # Normalize fields
    normalized_apn = normalize_apn(apn_raw) if apn_raw else None
    normalized_address = normalize_address(address) if address else None

    # Normalize record type (will be handled by county_verification module)
    normalized_record_type = record_type_raw.lower().replace(" ", "_") if record_type_raw else None

    # Build county record
    county_record = CountyRecordObservation(
        source_type="recorder",
        source_url=source_url,
        record_date=record_date,
        record_type=record_type_raw or "unknown",
        normalized_record_type=normalized_record_type,
        document_number=document_number,
        document_title=document_title,
        apn=apn_raw,
        normalized_apn=normalized_apn,
        address=address,
        normalized_address=normalized_address,
        grantor=grantor,
        grantee=grantee,
        sale_price=sale_price,
        transfer_tax=transfer_tax,
        confidence="medium",
    )

    # Determine parse status
    if not document_number and not apn_raw and not address:
        parse_status = "failed"
        errors.append("No document number, APN, or address found in recorder HTML")
    elif not record_type_raw:
        parse_status = "partial"
        warnings.append("Record type not found")
    else:
        parse_status = "success"

    return CountyRecordParseResult(
        source_type="recorder",
        parse_status=parse_status,
        county_record=county_record,
        warnings=warnings,
        errors=errors,
    )


def _parse_tax_collector_html(soup: BeautifulSoup, source_url: Optional[str]) -> CountyRecordParseResult:
    """
    Parse tax collector HTML fixture.

    Extracts: APN, address, tax status.
    """
    warnings = []
    errors = []

    # Extract fields
    apn_raw = _extract_text(soup, class_="apn-value")
    address = _extract_text(soup, class_="property-address")
    tax_status = _extract_text(soup, class_="tax-status")

    # Normalize fields
    normalized_apn = normalize_apn(apn_raw) if apn_raw else None
    normalized_address = normalize_address(address) if address else None

    # Build county record
    county_record = CountyRecordObservation(
        source_type="tax_collector",
        source_url=source_url,
        record_type="tax_record",
        normalized_record_type="tax_record",
        apn=apn_raw,
        normalized_apn=normalized_apn,
        address=address,
        normalized_address=normalized_address,
        notes=f"Tax status: {tax_status}" if tax_status else None,
        confidence="medium",
    )

    # Determine parse status
    if not apn_raw and not address:
        parse_status = "failed"
        errors.append("No APN or address found in tax collector HTML")
    else:
        parse_status = "success"

    return CountyRecordParseResult(
        source_type="tax_collector",
        parse_status=parse_status,
        county_record=county_record,
        warnings=warnings,
        errors=errors,
    )


def _parse_permit_html(soup: BeautifulSoup, source_url: Optional[str]) -> CountyRecordParseResult:
    """
    Parse permit HTML fixture.

    Extracts: permit number, permit type, permit status, apn, address.
    """
    warnings = []
    errors = []

    # Extract fields
    permit_number = _extract_text(soup, class_="permit-number")
    permit_type = _extract_text(soup, class_="permit-type")
    permit_status = _extract_text(soup, class_="permit-status")
    apn_raw = _extract_text(soup, class_="apn-value")
    address = _extract_text(soup, class_="property-address")

    # Normalize fields
    normalized_apn = normalize_apn(apn_raw) if apn_raw else None
    normalized_address = normalize_address(address) if address else None

    # Build county record
    county_record = CountyRecordObservation(
        source_type="permit",
        source_url=source_url,
        record_type="permit",
        normalized_record_type="permit",
        apn=apn_raw,
        normalized_apn=normalized_apn,
        address=address,
        normalized_address=normalized_address,
        permit_number=permit_number,
        permit_type=permit_type,
        permit_status=permit_status,
        confidence="medium",
    )

    # Determine parse status
    if not permit_number and not apn_raw and not address:
        parse_status = "failed"
        errors.append("No permit number, APN, or address found in permit HTML")
    else:
        parse_status = "success"

    return CountyRecordParseResult(
        source_type="permit",
        parse_status=parse_status,
        county_record=county_record,
        warnings=warnings,
        errors=errors,
    )


def _extract_text(soup: BeautifulSoup, class_: str) -> Optional[str]:
    """
    Extract text from HTML element by class.

    Args:
        soup: BeautifulSoup object
        class_: CSS class name

    Returns:
        Extracted text or None
    """
    element = soup.find(class_=class_)
    if element:
        text = element.get_text(strip=True)
        return text if text else None
    return None


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """
    Parse date string safely.

    Supports formats: YYYY-MM-DD, MM/DD/YYYY, M/D/YYYY.

    Args:
        date_str: Date string

    Returns:
        date object or None
    """
    if not date_str:
        return None

    # Try common date formats
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%-m/%-d/%Y",  # Unix strptime
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue

    # If all formats fail, return None
    return None


def _parse_currency(currency_str: Optional[str]) -> Optional[float]:
    """
    Parse currency string safely.

    Handles: "$1,234,567.89", "1234567.89", "$1234567", etc.

    Args:
        currency_str: Currency string

    Returns:
        Float value or None
    """
    if not currency_str:
        return None

    try:
        # Remove $ and commas
        clean_str = currency_str.strip().replace("$", "").replace(",", "")
        return float(clean_str)
    except ValueError:
        return None
