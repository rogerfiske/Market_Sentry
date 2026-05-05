"""Parse Homes.com property detail pages from saved HTML fixtures."""

import re
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from marketsentry.gas_detection import detect_gas_service
from marketsentry.logging_config import logger
from marketsentry.models import CrossSiteParseResult, CrossSitePropertyFacts
from marketsentry.normalization import normalize_address


def parse_homes_detail_html(
    html: str, source_url: Optional[str] = None
) -> CrossSiteParseResult:
    """
    Parse a Homes.com property detail HTML page.

    Extracts: price, beds, baths, sqft, listing_status, displayed_dom,
    garage_spaces, gas evidence.

    Args:
        html: HTML content as string
        source_url: Optional source URL or file path

    Returns:
        CrossSiteParseResult with parsed property facts
    """
    result = CrossSiteParseResult(
        source_file=source_url,
        source_site="homes",
        parse_status="success",
    )

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Initialize property facts
        facts = CrossSitePropertyFacts()

        # Extract price
        facts.price = _extract_price(soup, result)

        # Extract beds
        facts.beds = _extract_beds(soup, result)

        # Extract baths
        facts.baths = _extract_baths(soup, result)

        # Extract sqft
        facts.sqft = _extract_sqft(soup, result)

        # Extract listing status
        facts.listing_status = _extract_listing_status(soup, result)

        # Extract displayed DOM
        facts.displayed_dom = _extract_displayed_dom(soup, result)

        # Extract garage spaces
        facts.garage_spaces = _extract_garage_spaces(soup, result)

        # Extract gas evidence
        gas_info = _extract_gas_evidence(soup, result)
        facts.gas_service = gas_info.get("gas_service")
        facts.gas_evidence = gas_info.get("gas_evidence")

        # Extract property description
        facts.property_description = _extract_description(soup, result)

        # Extract address information
        result.address = _extract_address(soup, result)
        result.city = _extract_city(soup, result)
        result.state = _extract_state(soup, result)
        result.zip = _extract_zip(soup, result)

        if result.address:
            result.normalized_address = normalize_address(result.address)

        # Extract source URL from page if available
        if not result.source_url:
            result.source_url = _extract_source_url(soup, result)

        result.property_facts = facts

        if result.warnings:
            result.parse_status = "partial"

    except Exception as e:
        logger.error(f"Error parsing Homes.com detail HTML: {e}")
        result.parse_status = "failed"
        result.errors.append(f"Parse error: {str(e)}")

    return result


def parse_homes_detail_file(file_path: Path) -> CrossSiteParseResult:
    """
    Parse a Homes.com property detail HTML file.

    Args:
        file_path: Path to HTML file

    Returns:
        CrossSiteParseResult with parsed property facts
    """
    if not file_path.exists():
        return CrossSiteParseResult(
            source_file=str(file_path),
            source_site="homes",
            parse_status="failed",
            errors=[f"File not found: {file_path}"],
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            html = f.read()

        return parse_homes_detail_html(html, str(file_path))

    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return CrossSiteParseResult(
            source_file=str(file_path),
            source_site="homes",
            parse_status="failed",
            errors=[f"File read error: {str(e)}"],
        )


# Helper functions for extraction


def _extract_price(soup: BeautifulSoup, result: CrossSiteParseResult) -> Optional[float]:
    """Extract property price from HTML."""
    try:
        # Try common price selectors
        price_elem = soup.find(class_=re.compile(r"price", re.I))

        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'\$([0-9,]+)', price_text)
            if price_match:
                return float(price_match.group(1).replace(",", ""))

    except Exception as e:
        result.warnings.append(f"Error extracting price: {str(e)}")

    return None


def _extract_beds(soup: BeautifulSoup, result: CrossSiteParseResult) -> Optional[int]:
    """Extract number of bedrooms from HTML."""
    try:
        text = soup.get_text()
        beds_match = re.search(r'(\d+)\s*(?:bd|bed|bedroom)', text, re.I)
        if beds_match:
            return int(beds_match.group(1))

    except Exception as e:
        result.warnings.append(f"Error extracting beds: {str(e)}")

    return None


def _extract_baths(soup: BeautifulSoup, result: CrossSiteParseResult) -> Optional[float]:
    """Extract number of bathrooms from HTML."""
    try:
        text = soup.get_text()
        baths_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ba|bath|bathroom)', text, re.I)
        if baths_match:
            return float(baths_match.group(1))

    except Exception as e:
        result.warnings.append(f"Error extracting baths: {str(e)}")

    return None


def _extract_sqft(soup: BeautifulSoup, result: CrossSiteParseResult) -> Optional[int]:
    """Extract square footage from HTML."""
    try:
        text = soup.get_text()
        sqft_match = re.search(r'([0-9,]+)\s*(?:sqft|sq\.?\s*ft)', text, re.I)
        if sqft_match:
            return int(sqft_match.group(1).replace(",", ""))

    except Exception as e:
        result.warnings.append(f"Error extracting sqft: {str(e)}")

    return None


def _extract_listing_status(
    soup: BeautifulSoup, result: CrossSiteParseResult
) -> Optional[str]:
    """Extract listing status from HTML."""
    try:
        text = soup.get_text().lower()

        # Look for status indicators
        if "for sale" in text:
            return "for_sale"
        elif "sold" in text:
            return "sold"
        elif "pending" in text:
            return "pending"
        elif "for rent" in text:
            return "for_rent"
        elif "off market" in text or "off-market" in text:
            return "off_market"

    except Exception as e:
        result.warnings.append(f"Error extracting listing status: {str(e)}")

    return None


def _extract_displayed_dom(
    soup: BeautifulSoup, result: CrossSiteParseResult
) -> Optional[int]:
    """Extract displayed Days on Market from HTML."""
    try:
        text = soup.get_text()

        # Look for "Days on Market" or similar
        dom_match = re.search(
            r'(\d+)\s*(?:days?\s*on\s*(?:market|homes)|DOM)',
            text,
            re.I,
        )
        if dom_match:
            return int(dom_match.group(1))

    except Exception as e:
        result.warnings.append(f"Error extracting displayed DOM: {str(e)}")

    return None


def _extract_garage_spaces(
    soup: BeautifulSoup, result: CrossSiteParseResult
) -> Optional[int]:
    """Extract garage spaces from HTML."""
    try:
        text = soup.get_text()
        garage_match = re.search(r'(\d+)\s*(?:car\s*)?garage', text, re.I)
        if garage_match:
            return int(garage_match.group(1))

    except Exception as e:
        result.warnings.append(f"Error extracting garage spaces: {str(e)}")

    return None


def _extract_gas_evidence(
    soup: BeautifulSoup, result: CrossSiteParseResult
) -> dict:
    """Extract gas service evidence from HTML."""
    gas_info = {
        "gas_service": None,
        "gas_evidence": None,
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
                return gas_info

        # Check full text
        full_text = soup.get_text()
        has_gas, evidence = detect_gas_service(full_text)
        if has_gas:
            gas_info["gas_service"] = True
            gas_info["gas_evidence"] = evidence

    except Exception as e:
        result.warnings.append(f"Error extracting gas evidence: {str(e)}")

    return gas_info


def _extract_description(
    soup: BeautifulSoup, result: CrossSiteParseResult
) -> Optional[str]:
    """Extract property description from HTML."""
    try:
        desc_elem = soup.find(class_=re.compile(r'description', re.I))
        if desc_elem:
            return desc_elem.get_text(strip=True)[:1000]  # Limit length

    except Exception as e:
        result.warnings.append(f"Error extracting description: {str(e)}")

    return None


def _extract_address(soup: BeautifulSoup, result: CrossSiteParseResult) -> Optional[str]:
    """Extract property address from HTML."""
    try:
        # Try common address selectors
        address_elem = soup.find("h1", class_=re.compile(r"address", re.I))
        if address_elem:
            return address_elem.get_text(strip=True)

        # Try meta tags
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            content = og_title.get("content")
            if "|" in content:
                address_part = content.split("|")[0].strip()
                return address_part

    except Exception as e:
        result.warnings.append(f"Error extracting address: {str(e)}")

    return None


def _extract_city(soup: BeautifulSoup, result: CrossSiteParseResult) -> Optional[str]:
    """Extract city from HTML."""
    try:
        # Try breadcrumb or location elements
        location_elem = soup.find(class_=re.compile(r"location|city", re.I))
        if location_elem:
            text = location_elem.get_text(strip=True)
            if "," in text:
                city = text.split(",")[0].strip()
                return city

    except Exception as e:
        result.warnings.append(f"Error extracting city: {str(e)}")

    return None


def _extract_state(soup: BeautifulSoup, result: CrossSiteParseResult) -> Optional[str]:
    """Extract state from HTML."""
    try:
        location_elem = soup.find(class_=re.compile(r"location", re.I))
        if location_elem:
            text = location_elem.get_text(strip=True)
            match = re.search(r",\s*([A-Z]{2})\s+\d{5}", text)
            if match:
                return match.group(1)

    except Exception as e:
        result.warnings.append(f"Error extracting state: {str(e)}")

    return "CA"  # Default to CA


def _extract_zip(soup: BeautifulSoup, result: CrossSiteParseResult) -> Optional[str]:
    """Extract ZIP code from HTML."""
    try:
        location_elem = soup.find(class_=re.compile(r"location", re.I))
        if location_elem:
            text = location_elem.get_text(strip=True)
            match = re.search(r'\b(\d{5})\b', text)
            if match:
                return match.group(1)

    except Exception as e:
        result.warnings.append(f"Error extracting ZIP: {str(e)}")

    return None


def _extract_source_url(soup: BeautifulSoup, result: CrossSiteParseResult) -> Optional[str]:
    """Extract source URL from page."""
    try:
        canonical_link = soup.find("link", rel="canonical")
        if canonical_link and canonical_link.get("href"):
            return canonical_link.get("href")

    except Exception as e:
        result.warnings.append(f"Error extracting source URL: {str(e)}")

    return None
