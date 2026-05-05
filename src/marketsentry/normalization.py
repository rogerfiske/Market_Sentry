"""Address and data normalization utilities."""

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
