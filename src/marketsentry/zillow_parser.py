"""Parse Zillow property detail pages from saved HTML fixtures."""

import re
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from marketsentry.gas_detection import detect_gas_service
from marketsentry.logging_config import logger
from marketsentry.models import CrossSiteParseResult, CrossSitePropertyFacts
from marketsentry.normalization import normalize_address, normalize_price


def parse_zillow_detail_html(
    html: str, source_url: Optional[str] = None
) -> CrossSiteParseResult:
    """
    Parse a Zillow property detail HTML page.

    Extracts: price, beds, baths, sqft, lot_size, listing_status,
    displayed_dom, garage_spaces, gas evidence, listing agent/broker,
    MLS number, source MLS, property description.

    Args:
        html: HTML content as string
        source_url: Optional source URL or file path

    Returns:
        CrossSiteParseResult with parsed property facts
    """
    result = CrossSiteParseResult(
        source_file=source_url,
        source_site="zillow",
        parse_status="success",
    )

    try:
        soup = BeautifulSoup(html, "html.parser")

        facts = CrossSitePropertyFacts()

        facts.price = _extract_price(soup, result)
        facts.beds = _extract_beds(soup, result)
        facts.baths = _extract_baths(soup, result)
        facts.sqft = _extract_sqft(soup, result)
        facts.lot_size = _extract_lot_size(soup, result)
        facts.listing_status = _extract_listing_status(soup, result)
        facts.displayed_dom = _extract_displayed_dom(soup, result)
        facts.garage_spaces = _extract_garage_spaces(soup, result)

        gas_info = _extract_gas_evidence(soup, result)
        facts.gas_service = gas_info.get("gas_service")
        facts.gas_evidence = gas_info.get("gas_evidence")

        facts.listing_agent = _extract_listing_agent(soup, result)
        facts.listing_broker = _extract_listing_broker(soup, result)
        facts.mls_number = _extract_mls_number(soup, result)
        facts.source_mls = _extract_source_mls(soup, result)

        facts.property_description = _extract_description(soup, result)

        result.address = _extract_address(soup, result)
        result.city = _extract_city(soup, result)
        result.state = _extract_state(soup, result)
        result.zip = _extract_zip(soup, result)

        if result.address:
            result.normalized_address = normalize_address(result.address)

        if not result.source_url:
            result.source_url = _extract_source_url(soup, result)

        result.property_facts = facts

        if result.warnings:
            result.parse_status = "partial"

        _compute_confidence(result)

    except Exception as e:
        logger.error(f"Error parsing Zillow detail HTML: {e}")
        result.parse_status = "failed"
        result.parse_confidence = "low"
        result.errors.append(f"Parse error: {str(e)}")

    return result


def parse_zillow_detail_file(file_path: Path) -> CrossSiteParseResult:
    """
    Parse a Zillow property detail HTML file.

    Args:
        file_path: Path to HTML file

    Returns:
        CrossSiteParseResult with parsed property facts
    """
    if not file_path.exists():
        return CrossSiteParseResult(
            source_file=str(file_path),
            source_site="zillow",
            parse_status="failed",
            parse_confidence="low",
            errors=[f"File not found: {file_path}"],
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            html = f.read()

        return parse_zillow_detail_html(html, str(file_path))

    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return CrossSiteParseResult(
            source_file=str(file_path),
            source_site="zillow",
            parse_status="failed",
            parse_confidence="low",
            errors=[f"File read error: {str(e)}"],
        )


def _compute_confidence(result: CrossSiteParseResult) -> None:
    """Compute parse confidence and track missing required fields.

    Confidence levels:
    - high: address and at least price/status/property facts extracted
    - medium: address and some facts, but important fields missing
    - low: sparse or uncertain parse

    Args:
        result: Parse result to update in place.
    """
    if result.parse_status == "failed":
        result.parse_confidence = "low"
        return

    missing = []
    facts = result.property_facts

    if not result.address:
        missing.append("address")
    if not facts or facts.price is None:
        missing.append("price")
    if not facts or facts.listing_status is None:
        missing.append("listing_status")
    if not facts or facts.beds is None:
        missing.append("beds")
    if not facts or facts.baths is None:
        missing.append("baths")
    if not facts or facts.sqft is None:
        missing.append("sqft")

    result.missing_required_fields = missing

    has_address = result.address is not None
    has_price = facts is not None and facts.price is not None
    has_status = facts is not None and facts.listing_status is not None
    has_some_facts = facts is not None and any([
        facts.beds is not None,
        facts.baths is not None,
        facts.sqft is not None,
    ])

    if has_address and has_price and (has_status or has_some_facts):
        result.parse_confidence = "high"
    elif has_address and (has_price or has_some_facts):
        result.parse_confidence = "medium"
    else:
        result.parse_confidence = "low"


# Helper functions for extraction


def _extract_price(soup: BeautifulSoup, result: CrossSiteParseResult) -> Optional[float]:
    """Extract property price from HTML."""
    try:
        price_elem = soup.find("span", {"data-testid": "price"})
        if not price_elem:
            price_elem = soup.find(class_=re.compile(r"price", re.I))

        if price_elem:
            price_text = price_elem.get_text(strip=True)
            parsed = normalize_price(price_text)
            if parsed is not None:
                return parsed
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
        beds_match = re.search(r'(\d+)\s*(?:bd|bed|bedroom)s?', text, re.I)
        if beds_match:
            return int(beds_match.group(1))

    except Exception as e:
        result.warnings.append(f"Error extracting beds: {str(e)}")

    return None


def _extract_baths(soup: BeautifulSoup, result: CrossSiteParseResult) -> Optional[float]:
    """Extract number of bathrooms from HTML."""
    try:
        text = soup.get_text()
        baths_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ba|bath|bathroom)s?', text, re.I)
        if baths_match:
            return float(baths_match.group(1))

    except Exception as e:
        result.warnings.append(f"Error extracting baths: {str(e)}")

    return None


def _extract_sqft(soup: BeautifulSoup, result: CrossSiteParseResult) -> Optional[int]:
    """Extract square footage from HTML."""
    try:
        text = soup.get_text()
        sqft_match = re.search(
            r'([0-9,]+)\s*(?:sqft|sq\.?\s*ft|square\s*feet)', text, re.I
        )
        if sqft_match:
            return int(sqft_match.group(1).replace(",", ""))

    except Exception as e:
        result.warnings.append(f"Error extracting sqft: {str(e)}")

    return None


def _extract_lot_size(
    soup: BeautifulSoup, result: CrossSiteParseResult
) -> Optional[float]:
    """Extract lot size in acres from HTML."""
    try:
        text = soup.get_text()
        acres_match = re.search(r'([\d,.]+)\s*acres?', text, re.I)
        if acres_match:
            return float(acres_match.group(1).replace(",", ""))

        lot_match = re.search(
            r'(?:lot|land)[:\s]*([0-9,]+)\s*(?:sqft|sq\.?\s*ft|square\s*feet)',
            text, re.I
        )
        if lot_match:
            sqft_val = float(lot_match.group(1).replace(",", ""))
            return round(sqft_val / 43560.0, 4)

    except Exception as e:
        result.warnings.append(f"Error extracting lot size: {str(e)}")

    return None


def _extract_listing_status(
    soup: BeautifulSoup, result: CrossSiteParseResult
) -> Optional[str]:
    """Extract listing status from HTML."""
    try:
        status_elem = soup.find(class_=re.compile(r"listing[-_]?status", re.I))
        if status_elem:
            return _normalize_status(status_elem.get_text(strip=True))

        text = soup.get_text().lower()
        if "coming soon" in text:
            return "coming_soon"
        if "contingent" in text:
            return "contingent"
        if "pending" in text:
            return "pending"
        if "sold" in text:
            return "sold"
        if "off market" in text or "off-market" in text:
            return "off_market"
        if "for sale" in text:
            return "for_sale"
        if "for rent" in text:
            return "for_rent"

    except Exception as e:
        result.warnings.append(f"Error extracting listing status: {str(e)}")

    return None


def _normalize_status(text: str) -> str:
    """Normalize a status string to canonical form."""
    text = text.strip().lower()
    status_map = {
        "for sale": "for_sale",
        "active": "for_sale",
        "pending": "pending",
        "contingent": "contingent",
        "sold": "sold",
        "off market": "off_market",
        "off-market": "off_market",
        "coming soon": "coming_soon",
        "for rent": "for_rent",
    }
    for pattern, normalized in status_map.items():
        if pattern in text:
            return normalized
    return text


def _extract_displayed_dom(
    soup: BeautifulSoup, result: CrossSiteParseResult
) -> Optional[int]:
    """Extract displayed Days on Market from HTML."""
    try:
        text = soup.get_text()

        dom_match = re.search(
            r'(\d+)\s*days?\s*on\s*(?:zillow|market)',
            text,
            re.I,
        )
        if dom_match:
            return int(dom_match.group(1))

        dom_match = re.search(r'listed\s+(\d+)\s+days?\s+ago', text, re.I)
        if dom_match:
            return int(dom_match.group(1))

        dom_match = re.search(r'(\d+)\s*DOM', text)
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
        garage_match = re.search(r'(\d+)\s*[-\s]?\s*car\s+garage', text, re.I)
        if garage_match:
            return int(garage_match.group(1))

        garage_match = re.search(r'(\d+)\s*garage\s*spaces?', text, re.I)
        if garage_match:
            return int(garage_match.group(1))

        if re.search(r'(?:attached|detached)\s+garage', text, re.I):
            return 1

    except Exception as e:
        result.warnings.append(f"Error extracting garage spaces: {str(e)}")

    return None


def _extract_gas_evidence(
    soup: BeautifulSoup, result: CrossSiteParseResult
) -> dict:
    """Extract gas service evidence from HTML."""
    gas_info = {"gas_service": None, "gas_evidence": None}

    try:
        desc_elem = soup.find(class_=re.compile(r'description', re.I))
        if desc_elem:
            desc_text = desc_elem.get_text()
            has_gas, evidence = detect_gas_service(desc_text)
            if has_gas:
                gas_info["gas_service"] = True
                gas_info["gas_evidence"] = evidence
                return gas_info

        full_text = soup.get_text()
        has_gas, evidence = detect_gas_service(full_text)
        if has_gas:
            gas_info["gas_service"] = True
            gas_info["gas_evidence"] = evidence

    except Exception as e:
        result.warnings.append(f"Error extracting gas evidence: {str(e)}")

    return gas_info


def _extract_listing_agent(
    soup: BeautifulSoup, result: CrossSiteParseResult
) -> Optional[str]:
    """Extract listing agent name from HTML."""
    try:
        agent_elem = soup.find(class_=re.compile(r"listing[-_]?agent", re.I))
        if agent_elem:
            text = agent_elem.get_text(strip=True)
            text = re.sub(r'^listed\s+by\s+', '', text, flags=re.I)
            return text if text else None

    except Exception as e:
        result.warnings.append(f"Error extracting listing agent: {str(e)}")

    return None


def _extract_listing_broker(
    soup: BeautifulSoup, result: CrossSiteParseResult
) -> Optional[str]:
    """Extract listing broker name from HTML."""
    try:
        broker_elem = soup.find(class_=re.compile(r"listing[-_]?broker", re.I))
        if broker_elem:
            text = broker_elem.get_text(strip=True)
            return text if text else None

    except Exception as e:
        result.warnings.append(f"Error extracting listing broker: {str(e)}")

    return None


def _extract_mls_number(
    soup: BeautifulSoup, result: CrossSiteParseResult
) -> Optional[str]:
    """Extract MLS number from HTML."""
    try:
        mls_elem = soup.find(class_=re.compile(r"mls[-_]?info|mls[-_]?number", re.I))
        if mls_elem:
            text = mls_elem.get_text(strip=True)
            text = re.sub(r'^MLS#?\s*', '', text, flags=re.I)
            return text if text else None

        full_text = soup.get_text()
        mls_match = re.search(r'MLS#?\s*([A-Z0-9]+)', full_text)
        if mls_match:
            return mls_match.group(1)

    except Exception as e:
        result.warnings.append(f"Error extracting MLS number: {str(e)}")

    return None


def _extract_source_mls(
    soup: BeautifulSoup, result: CrossSiteParseResult
) -> Optional[str]:
    """Extract source MLS name from HTML."""
    try:
        mls_elem = soup.find(class_=re.compile(r"source[-_]?mls", re.I))
        if mls_elem:
            text = mls_elem.get_text(strip=True)
            return text if text else None

    except Exception as e:
        result.warnings.append(f"Error extracting source MLS: {str(e)}")

    return None


def _extract_description(
    soup: BeautifulSoup, result: CrossSiteParseResult
) -> Optional[str]:
    """Extract property description from HTML."""
    try:
        desc_elem = soup.find(class_=re.compile(r'description', re.I))
        if desc_elem:
            return desc_elem.get_text(strip=True)[:1000]

    except Exception as e:
        result.warnings.append(f"Error extracting description: {str(e)}")

    return None


def _extract_address(soup: BeautifulSoup, result: CrossSiteParseResult) -> Optional[str]:
    """Extract property address from HTML."""
    try:
        address_elem = soup.find("h1", class_=re.compile(r"address", re.I))
        if address_elem:
            return address_elem.get_text(strip=True)

        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            content = og_title.get("content")
            if "|" in content:
                return content.split("|")[0].strip()

    except Exception as e:
        result.warnings.append(f"Error extracting address: {str(e)}")

    return None


def _extract_city(soup: BeautifulSoup, result: CrossSiteParseResult) -> Optional[str]:
    """Extract city from HTML."""
    try:
        location_elem = soup.find(class_=re.compile(r"location|city", re.I))
        if location_elem:
            text = location_elem.get_text(strip=True)
            if "," in text:
                return text.split(",")[0].strip()

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

    return "CA"


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
