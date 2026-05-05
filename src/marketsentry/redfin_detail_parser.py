"""Parse Redfin property detail pages from saved HTML fixtures."""

import hashlib
import re
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup

from marketsentry.gas_detection import detect_gas_service, extract_gas_evidence
from marketsentry.logging_config import logger
from marketsentry.models import (
    RedfinDetailEnrichmentResult,
    RedfinDetailParseResult,
    RedfinLifestyleScores,
    RedfinListingHistoryEvent,
    RedfinPropertyDetail,
    RedfinPropertyFacts,
)
from marketsentry.normalization import normalize_address
from marketsentry.quiet_vibrancy import apply_quiet_gatekeeper
from marketsentry.redfin_url_utils import (
    extract_address_from_redfin_url,
    extract_city_from_redfin_url,
    extract_redfin_home_id,
    extract_zip_from_redfin_url,
    is_redfin_url,
    normalize_redfin_url,
)


def parse_redfin_detail_html(
    html: str, source_url: Optional[str] = None
) -> RedfinDetailParseResult:
    """
    Parse a Redfin property detail HTML page.

    Args:
        html: HTML content as string
        source_url: Optional source URL or file path

    Returns:
        RedfinDetailParseResult with parsed property details
    """
    result = RedfinDetailParseResult(
        source_file=source_url,
        parse_status="success",
    )

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Initialize property detail
        detail = RedfinPropertyDetail()

        # Extract property URL from page if available
        canonical_link = soup.find("link", rel="canonical")
        if canonical_link and canonical_link.get("href"):
            url = canonical_link.get("href")
            if is_redfin_url(url):
                detail.redfin_url = normalize_redfin_url(url)
                detail.redfin_home_id = extract_redfin_home_id(url)

        # Extract address information
        detail.address = _extract_address(soup, result)
        detail.city = _extract_city(soup, result)
        detail.state = _extract_state(soup, result)
        detail.zip = _extract_zip(soup, result)

        if detail.address:
            detail.normalized_address = normalize_address(detail.address)

        # Extract APN
        detail.apn = _extract_apn(soup, result)

        # Extract property facts
        detail.facts = _extract_property_facts(soup, result)

        # Extract lifestyle scores (Quiet/Vibrancy)
        detail.lifestyle_scores = _extract_lifestyle_scores(soup, result)

        # Apply quiet gatekeeper if scores available (for reference, not stored in detail)
        # Gatekeeper result will be applied during candidate enrichment

        # Extract gas evidence
        gas_info = _extract_gas_evidence(soup, result)
        detail.gas_service = gas_info.get("gas_service")
        detail.gas_evidence = gas_info.get("gas_evidence")
        detail.gas_evidence_source = gas_info.get("gas_evidence_source")

        # Extract MLS information
        mls_info = _extract_mls_info(soup, result)
        detail.mls_number = mls_info.get("mls_number")
        detail.source_mls = mls_info.get("source_mls")

        # Parse listing history
        detail.listing_history = _parse_listing_history(soup, result)

        # Extract displayed DOM if available
        detail.displayed_dom = _extract_displayed_dom(soup, result)

        result.property_detail = detail

        if result.warnings:
            result.parse_status = "partial"

    except Exception as e:
        logger.error(f"Error parsing Redfin detail HTML: {e}")
        result.parse_status = "failed"
        result.errors.append(f"Parse error: {str(e)}")

    return result


def parse_redfin_detail_file(file_path: Path) -> RedfinDetailParseResult:
    """
    Parse a Redfin property detail HTML file.

    Args:
        file_path: Path to HTML file

    Returns:
        RedfinDetailParseResult with parsed property details
    """
    if not file_path.exists():
        return RedfinDetailParseResult(
            source_file=str(file_path),
            parse_status="failed",
            errors=[f"File not found: {file_path}"],
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            html = f.read()

        return parse_redfin_detail_html(html, str(file_path))

    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return RedfinDetailParseResult(
            source_file=str(file_path),
            parse_status="failed",
            errors=[f"File read error: {str(e)}"],
        )


def parse_redfin_detail_directory(directory: Path) -> List[RedfinDetailParseResult]:
    """
    Parse all Redfin detail HTML files in a directory.

    Args:
        directory: Path to directory containing HTML files

    Returns:
        List of RedfinDetailParseResult for each file
    """
    if not directory.exists():
        logger.error(f"Directory not found: {directory}")
        return []

    if not directory.is_dir():
        logger.error(f"Not a directory: {directory}")
        return []

    results = []
    html_files = list(directory.glob("*.html")) + list(directory.glob("*.htm"))

    for html_file in html_files:
        result = parse_redfin_detail_file(html_file)
        results.append(result)

    return results


# Helper functions for extraction


def _extract_address(soup: BeautifulSoup, result: RedfinDetailParseResult) -> Optional[str]:
    """Extract property address from HTML."""
    try:
        # Try common address selectors
        address_elem = soup.find("h1", class_=re.compile(r"address", re.I))
        if address_elem:
            return address_elem.get_text(strip=True)

        # Try meta tags
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            # Often contains "Address | City, State ZIP"
            content = og_title.get("content")
            if "|" in content:
                address_part = content.split("|")[0].strip()
                return address_part

    except Exception as e:
        result.warnings.append(f"Error extracting address: {str(e)}")

    return None


def _extract_city(soup: BeautifulSoup, result: RedfinDetailParseResult) -> Optional[str]:
    """Extract city from HTML."""
    try:
        # Try breadcrumb or location elements
        location_elem = soup.find(class_=re.compile(r"location|city", re.I))
        if location_elem:
            text = location_elem.get_text(strip=True)
            # Parse "City, State ZIP" format
            if "," in text:
                city = text.split(",")[0].strip()
                return city

    except Exception as e:
        result.warnings.append(f"Error extracting city: {str(e)}")

    return None


def _extract_state(soup: BeautifulSoup, result: RedfinDetailParseResult) -> Optional[str]:
    """Extract state from HTML."""
    try:
        location_elem = soup.find(class_=re.compile(r"location", re.I))
        if location_elem:
            text = location_elem.get_text(strip=True)
            # Parse "City, State ZIP" format
            match = re.search(r",\s*([A-Z]{2})\s+\d{5}", text)
            if match:
                return match.group(1)

    except Exception as e:
        result.warnings.append(f"Error extracting state: {str(e)}")

    return "CA"  # Default to CA for Temecula/Murrieta


def _extract_zip(soup: BeautifulSoup, result: RedfinDetailParseResult) -> Optional[str]:
    """Extract ZIP code from HTML."""
    try:
        location_elem = soup.find(class_=re.compile(r"location", re.I))
        if location_elem:
            text = location_elem.get_text(strip=True)
            # Look for 5-digit ZIP
            match = re.search(r'\b(\d{5})\b', text)
            if match:
                return match.group(1)

    except Exception as e:
        result.warnings.append(f"Error extracting ZIP: {str(e)}")

    return None


def _extract_apn(soup: BeautifulSoup, result: RedfinDetailParseResult) -> Optional[str]:
    """Extract APN (Assessor Parcel Number) from HTML."""
    try:
        # Look for APN in property facts or details
        text = soup.get_text()
        match = re.search(r'APN[:\s]*([0-9-]+)', text, re.I)
        if match:
            return match.group(1)

    except Exception as e:
        result.warnings.append(f"Error extracting APN: {str(e)}")

    return None


def _extract_property_facts(
    soup: BeautifulSoup, result: RedfinDetailParseResult
) -> RedfinPropertyFacts:
    """Extract property facts from HTML."""
    facts = RedfinPropertyFacts()

    try:
        text = soup.get_text()

        # Extract price
        price_match = re.search(r'\$([0-9,]+)', text)
        if price_match:
            try:
                facts.price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Extract beds
        beds_match = re.search(r'(\d+)\s*(?:Bed|Bedroom)', text, re.I)
        if beds_match:
            try:
                facts.beds = int(beds_match.group(1))
            except ValueError:
                pass

        # Extract baths
        baths_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:Bath|Bathroom)', text, re.I)
        if baths_match:
            try:
                facts.baths = float(baths_match.group(1))
            except ValueError:
                pass

        # Extract sqft
        sqft_match = re.search(r'([0-9,]+)\s*(?:Sq\.?\s*Ft|Square Feet)', text, re.I)
        if sqft_match:
            try:
                facts.sqft = int(sqft_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Extract lot size
        lot_match = re.search(r'([0-9,]+)\s*(?:Sq\.?\s*Ft\.?\s*Lot|Lot Size)', text, re.I)
        if lot_match:
            try:
                facts.lot_size = float(lot_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Extract year built
        year_match = re.search(r'(?:Built|Year Built)(?:\s+in)?[:\s]*(\d{4})', text, re.I)
        if year_match:
            try:
                facts.year_built = int(year_match.group(1))
            except ValueError:
                pass

        # Extract garage spaces
        garage_match = re.search(r'(\d+)\s*(?:Car\s*)?Garage', text, re.I)
        if garage_match:
            try:
                facts.garage_spaces = int(garage_match.group(1))
            except ValueError:
                pass

        # Extract property description
        desc_elem = soup.find(class_=re.compile(r'description', re.I))
        if desc_elem:
            facts.property_description = desc_elem.get_text(strip=True)[:1000]  # Limit length

    except Exception as e:
        result.warnings.append(f"Error extracting property facts: {str(e)}")

    return facts


def _extract_lifestyle_scores(
    soup: BeautifulSoup, result: RedfinDetailParseResult
) -> Optional[RedfinLifestyleScores]:
    """Extract Quiet and Vibrancy scores from HTML."""
    scores = RedfinLifestyleScores()
    found_any = False

    try:
        text = soup.get_text()

        # Extract Quiet score
        quiet_match = re.search(r'Quiet[:\s]*(\d+(?:\.\d+)?)/10', text, re.I)
        if quiet_match:
            try:
                scores.quiet_score = float(quiet_match.group(1))
                scores.quiet_label = _score_to_label(scores.quiet_score)
                found_any = True
            except ValueError:
                pass

        # Extract Vibrancy score
        vibrancy_match = re.search(r'Vibrancy[:\s]*(\d+(?:\.\d+)?)/10', text, re.I)
        if vibrancy_match:
            try:
                scores.vibrancy_score = float(vibrancy_match.group(1))
                scores.vibrancy_label = _score_to_label(scores.vibrancy_score)
                found_any = True
            except ValueError:
                pass

    except Exception as e:
        result.warnings.append(f"Error extracting lifestyle scores: {str(e)}")

    return scores if found_any else None


def _score_to_label(score: float) -> str:
    """Convert numeric score to label."""
    if score >= 8.0:
        return "excellent"
    elif score >= 6.0:
        return "good"
    elif score >= 4.0:
        return "fair"
    else:
        return "poor"


def _extract_gas_evidence(
    soup: BeautifulSoup, result: RedfinDetailParseResult
) -> dict:
    """Extract gas service evidence from HTML."""
    gas_info = {
        "gas_service": None,
        "gas_evidence": None,
        "gas_evidence_source": None,
    }

    try:
        # Check property description
        desc_elem = soup.find(class_=re.compile(r'description', re.I))
        if desc_elem:
            desc_text = desc_elem.get_text()
            has_gas, evidence = detect_gas_service(desc_text)
            if has_gas:
                gas_info["gas_service"] = True
                gas_info["gas_evidence"] = evidence
                gas_info["gas_evidence_source"] = "property_description"
                return gas_info

        # Check full text
        full_text = soup.get_text()
        has_gas, evidence = detect_gas_service(full_text)
        if has_gas:
            gas_info["gas_service"] = True
            gas_info["gas_evidence"] = evidence
            gas_info["gas_evidence_source"] = "page_content"

    except Exception as e:
        result.warnings.append(f"Error extracting gas evidence: {str(e)}")

    return gas_info


def _extract_mls_info(soup: BeautifulSoup, result: RedfinDetailParseResult) -> dict:
    """Extract MLS information from HTML."""
    mls_info = {"mls_number": None, "source_mls": None}

    try:
        text = soup.get_text()

        # Look for MLS number patterns (more specific patterns first)
        mls_match = re.search(r'(?:SDMLS|CRMLS|MLS)\s*#?\s*(\d+)', text, re.I)
        if mls_match:
            full_match = mls_match.group(0)
            mls_info["mls_number"] = mls_match.group(1)

            # Determine source MLS
            if "SDMLS" in full_match.upper():
                mls_info["source_mls"] = "SDMLS"
            elif "CRMLS" in full_match.upper():
                mls_info["source_mls"] = "CRMLS"
            else:
                mls_info["source_mls"] = "MLS"

    except Exception as e:
        result.warnings.append(f"Error extracting MLS info: {str(e)}")

    return mls_info


def _parse_listing_history(
    soup: BeautifulSoup, result: RedfinDetailParseResult
) -> List[RedfinListingHistoryEvent]:
    """Parse listing history events from HTML."""
    events = []

    try:
        # Find listing history section
        history_section = soup.find(class_=re.compile(r'history|timeline', re.I))
        if not history_section:
            # Try to find in full text
            text_lines = soup.get_text().split('\n')
            history_lines = [line.strip() for line in text_lines if _looks_like_listing_event(line)]
        else:
            history_lines = history_section.get_text().split('\n')
            history_lines = [line.strip() for line in history_lines if line.strip()]

        for line in history_lines:
            if not line or len(line) < 10:
                continue

            # Skip obvious headers
            if re.match(r'^(?:Listing )?History$', line, re.I):
                continue

            event = _parse_listing_event_line(line)
            if event:
                events.append(event)

    except Exception as e:
        result.warnings.append(f"Error parsing listing history: {str(e)}")

    return events


def _looks_like_listing_event(line: str) -> bool:
    """Check if a line looks like a listing event."""
    line = line.strip()
    if len(line) < 10:
        return False

    # Look for date patterns and listing keywords
    has_date = bool(re.search(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}', line, re.I))
    has_keyword = bool(re.search(r'(?:list|price|sold|removed|pending|rent)', line, re.I))

    return has_date and has_keyword


def _parse_listing_event_line(line: str) -> Optional[RedfinListingHistoryEvent]:
    """Parse a single listing history event line."""
    try:
        # Example: "Apr. 12, 2026 Listed $879,000 SDMLS #260008641"

        # Extract date
        date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})', line, re.I)
        event_date = None
        if date_match:
            try:
                month_str = date_match.group(1)[:3].capitalize()
                day = int(date_match.group(2))
                year = int(date_match.group(3))
                month_num = {
                    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                }[month_str]
                event_date = date(year, month_num, day)
            except (ValueError, KeyError):
                pass

        # Extract price
        price_match = re.search(r'\$([0-9,]+)', line)
        price = None
        if price_match:
            try:
                price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Extract MLS info
        mls_match = re.search(r'(?:SDMLS|CRMLS|MLS)\s*#?\s*(\d+)', line, re.I)
        mls_number = None
        source_mls = None
        if mls_match:
            full_match = mls_match.group(0)
            mls_number = mls_match.group(1)
            if "SDMLS" in full_match.upper():
                source_mls = "SDMLS"
            elif "CRMLS" in full_match.upper():
                source_mls = "CRMLS"
            else:
                source_mls = "MLS"

        # Classify event type
        event_type = _classify_event_type(line)

        return RedfinListingHistoryEvent(
            event_date=event_date,
            event_type=event_type,
            price=price,
            raw_text=line,
            mls_number=mls_number,
            source_mls=source_mls,
            confidence="medium" if event_date else "low",
        )

    except Exception:
        return None


def _classify_event_type(line: str) -> str:
    """Classify listing event type from text."""
    line_lower = line.lower()

    if "sold" in line_lower:
        return "sold"
    elif "rental removed" in line_lower or "rent removed" in line_lower:
        return "rental_removed"
    elif "listed for rent" in line_lower or "rental listed" in line_lower:
        return "rental_listed"
    elif "price changed" in line_lower or "price change" in line_lower:
        return "price_changed"
    elif "removed" in line_lower or "delisted" in line_lower:
        return "removed"
    elif "relisted" in line_lower:
        return "relisted"
    elif "back on market" in line_lower:
        return "back_on_market"
    elif "pending" in line_lower:
        return "pending"
    elif "listed" in line_lower:
        return "listed"
    else:
        return "unknown"


def _extract_displayed_dom(
    soup: BeautifulSoup, result: RedfinDetailParseResult
) -> Optional[int]:
    """Extract displayed Days on Market from HTML."""
    try:
        text = soup.get_text()

        # Look for "Days on Market" or "DOM" patterns
        dom_match = re.search(r'(\d+)\s*(?:Days?\s*on\s*Market|DOM)', text, re.I)
        if dom_match:
            try:
                return int(dom_match.group(1))
            except ValueError:
                pass

    except Exception as e:
        result.warnings.append(f"Error extracting displayed DOM: {str(e)}")

    return None
