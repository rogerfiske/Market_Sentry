"""Address, price, and property data normalization utilities."""

import re
from typing import Optional


def normalize_address(address: str) -> str:
    """
    Normalize a property address for comparison and deduplication.

    Args:
        address: Raw address string

    Returns:
        Normalized address string
    """
    if not address:
        return ""

    # Convert to uppercase
    normalized = address.upper()

    # Remove extra whitespace
    normalized = " ".join(normalized.split())

    # Standardize common abbreviations
    abbreviations = {
        " STREET": " ST",
        " AVENUE": " AVE",
        " ROAD": " RD",
        " DRIVE": " DR",
        " LANE": " LN",
        " COURT": " CT",
        " CIRCLE": " CIR",
        " BOULEVARD": " BLVD",
        " PARKWAY": " PKWY",
        " PLACE": " PL",
        " TERRACE": " TER",
        " NORTH ": " N ",
        " SOUTH ": " S ",
        " EAST ": " E ",
        " WEST ": " W ",
    }

    for full, abbr in abbreviations.items():
        normalized = normalized.replace(full, abbr)

    # Remove punctuation except hyphens
    normalized = re.sub(r"[^\w\s\-]", "", normalized)

    # Collapse multiple spaces
    normalized = " ".join(normalized.split())

    return normalized.strip()


def normalize_url(url: str) -> str:
    """
    Normalize a URL for comparison.

    Args:
        url: Raw URL string

    Returns:
        Normalized URL string
    """
    if not url:
        return ""

    # Remove trailing slashes
    normalized = url.rstrip("/")

    # Remove common tracking parameters
    if "?" in normalized:
        base_url = normalized.split("?")[0]
        return base_url

    return normalized


def extract_numeric_value(value: Optional[str]) -> Optional[float]:
    """
    Extract numeric value from a string.

    Args:
        value: String potentially containing a number

    Returns:
        Extracted numeric value or None
    """
    if not value:
        return None

    # Remove common non-numeric characters
    cleaned = re.sub(r"[$,\s]", "", str(value))

    # Try to extract a number
    match = re.search(r"[\d.]+", cleaned)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None

    return None


def extract_integer_value(value: Optional[str]) -> Optional[int]:
    """
    Extract integer value from a string.

    Args:
        value: String potentially containing an integer

    Returns:
        Extracted integer value or None
    """
    numeric = extract_numeric_value(value)
    if numeric is not None:
        return int(numeric)
    return None


def normalize_apn(apn: str) -> str:
    """
    Normalize an APN (Assessor Parcel Number) for comparison.

    Removes hyphens, spaces, and other common separators.

    Args:
        apn: Raw APN string

    Returns:
        Normalized APN string (digits only)
    """
    if not apn:
        return ""

    # Remove all non-alphanumeric characters
    normalized = re.sub(r"[^\w]", "", apn)

    return normalized.strip()


def normalize_price(value: Optional[str]) -> Optional[float]:
    """
    Parse and normalize a price string to a float value.

    Handles formats: $850,000 / $850K / $1.2M / 850000

    Args:
        value: Price string to normalize.

    Returns:
        Price as float, or None if unparseable.
    """
    if not value:
        return None

    text = str(value).strip()
    # Remove dollar sign and commas
    text = text.replace("$", "").replace(",", "").strip()

    # Handle K/M suffixes
    m_match = re.match(r"^([\d.]+)\s*[Mm]$", text)
    if m_match:
        try:
            return float(m_match.group(1)) * 1_000_000
        except ValueError:
            return None

    k_match = re.match(r"^([\d.]+)\s*[Kk]$", text)
    if k_match:
        try:
            return float(k_match.group(1)) * 1_000
        except ValueError:
            return None

    # Plain number
    num_match = re.match(r"^[\d.]+$", text)
    if num_match:
        try:
            return float(text)
        except ValueError:
            return None

    return None


def normalize_sqft(value: Optional[str]) -> Optional[int]:
    """
    Parse and normalize a square footage string.

    Handles: "2,450 sqft", "2450 square feet", "2450 sq ft", "2450"

    Args:
        value: Square footage string.

    Returns:
        Square footage as int, or None.
    """
    if not value:
        return None

    text = str(value).strip()
    match = re.search(r"([0-9,]+)\s*(?:sqft|sq\.?\s*ft|square\s*feet)?", text, re.I)
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return None

    return None


def normalize_lot_size(value: Optional[str]) -> Optional[float]:
    """
    Parse and normalize a lot size string to acres.

    Handles: "0.25 acres", "7,405 sqft lot", "10890 sq ft"

    Args:
        value: Lot size string.

    Returns:
        Lot size in acres as float, or None.
    """
    if not value:
        return None

    text = str(value).strip().lower()

    # Try acres first
    acres_match = re.search(r"([\d,.]+)\s*acres?", text)
    if acres_match:
        try:
            return float(acres_match.group(1).replace(",", ""))
        except ValueError:
            return None

    # Try sqft lot - convert to acres (1 acre = 43560 sqft)
    sqft_match = re.search(
        r"([\d,]+)\s*(?:sqft|sq\.?\s*ft|square\s*feet)\s*(?:lot)?", text
    )
    if sqft_match:
        try:
            sqft = float(sqft_match.group(1).replace(",", ""))
            return round(sqft / 43560.0, 4)
        except ValueError:
            return None

    return None


def normalize_dom(value: Optional[str]) -> Optional[int]:
    """
    Parse and normalize Days on Market from various formats.

    Handles: "12 days on market", "Listed 45 days ago",
    "On site 17 days", "12 DOM", "15 Days on Zillow"

    Args:
        value: DOM string.

    Returns:
        DOM as int, or None.
    """
    if not value:
        return None

    text = str(value).strip()

    # "N days on market/zillow/site/homes/realtor/compass"
    m = re.search(
        r"(\d+)\s*days?\s*(?:on\s*(?:market|zillow|site|homes|realtor|compass))?",
        text,
        re.I,
    )
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None

    # "Listed N days ago"
    m = re.search(r"listed\s+(\d+)\s+days?\s+ago", text, re.I)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None

    # "On site N days"
    m = re.search(r"on\s+site\s+(\d+)\s+days?", text, re.I)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None

    # "N DOM"
    m = re.search(r"(\d+)\s*DOM", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None

    return None


def normalize_listing_status(value: Optional[str]) -> Optional[str]:
    """
    Normalize a listing status string to a canonical form.

    Maps common variants to: for_sale, pending, contingent,
    sold, off_market, coming_soon, for_rent.

    Args:
        value: Raw status string.

    Returns:
        Normalized status string, or None.
    """
    if not value:
        return None

    text = str(value).strip().lower()

    status_map = {
        "for sale": "for_sale",
        "for_sale": "for_sale",
        "active": "for_sale",
        "pending": "pending",
        "contingent": "contingent",
        "sold": "sold",
        "off market": "off_market",
        "off-market": "off_market",
        "off_market": "off_market",
        "coming soon": "coming_soon",
        "coming_soon": "coming_soon",
        "for rent": "for_rent",
        "for_rent": "for_rent",
    }

    for pattern, normalized in status_map.items():
        if pattern in text:
            return normalized

    return text


def normalize_garage(value: Optional[str]) -> Optional[int]:
    """
    Parse and normalize garage spaces from text.

    Handles: "2 garage spaces", "3-car garage", "attached garage",
    "2 car garage", "3 Car Garage"

    Args:
        value: Garage description string.

    Returns:
        Number of garage spaces as int, or None.
    """
    if not value:
        return None

    text = str(value).strip()

    # "N-car garage" or "N car garage" or "N garage spaces"
    m = re.search(r"(\d+)\s*[-\s]?\s*(?:car\s+)?garage", text, re.I)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None

    # "N garage spaces"
    m = re.search(r"(\d+)\s*garage\s*spaces?", text, re.I)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None

    # "attached garage" or just "garage" without number implies 1
    if re.search(r"(?:attached|detached)?\s*garage", text, re.I):
        return 1

    return None


def detect_gas_keywords(text: Optional[str]) -> Optional[str]:
    """
    Detect gas service evidence keywords in text.

    Looks for: gas fireplace, gas range, natural gas, gas dryer hookup,
    gas heating, gas cooktop, gas stove, gas water heater.

    Any mention of gas means gas service/supply evidence.

    Args:
        text: Text to search for gas keywords.

    Returns:
        Matched gas evidence string, or None.
    """
    if not text:
        return None

    patterns = [
        r"gas\s+fireplace",
        r"gas\s+range",
        r"natural\s+gas",
        r"gas\s+dryer\s+hookup",
        r"gas\s+heating",
        r"gas\s+cooktop",
        r"gas\s+stove",
        r"gas\s+water\s+heater",
        r"gas\s+furnace",
        r"gas\s+line",
        r"gas\s+hookup",
    ]

    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text, re.I)
        matches.extend(found)

    if matches:
        return "; ".join(sorted(set(m.lower() for m in matches)))

    return None
