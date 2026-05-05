"""Utilities for Redfin URL validation, normalization, and parsing."""

import re
from typing import Optional
from urllib.parse import urlparse, urlunparse


def is_redfin_url(url: str) -> bool:
    """
    Check if a URL is a valid Redfin property URL.

    Args:
        url: URL to check

    Returns:
        True if URL is a Redfin property URL, False otherwise
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)

        # Check domain
        if parsed.netloc not in ["www.redfin.com", "redfin.com"]:
            return False

        # Check for property page pattern
        # Expected pattern: /CA/City/Address/home/ID
        path_parts = [p for p in parsed.path.split("/") if p]

        # Must have at least: state, city, address-slug, 'home', home_id
        if len(path_parts) < 5:
            return False

        # Should contain 'home' keyword
        if "home" not in path_parts:
            return False

        return True

    except Exception:
        return False


def normalize_redfin_url(url: str) -> Optional[str]:
    """
    Normalize a Redfin URL by removing query parameters and fragments.

    Args:
        url: Redfin URL to normalize

    Returns:
        Normalized URL or None if invalid
    """
    if not url:
        return None

    if not is_redfin_url(url):
        return None

    try:
        parsed = urlparse(url)

        # Ensure https
        scheme = "https"

        # Ensure www subdomain
        netloc = "www.redfin.com"

        # Remove trailing slash from path
        path = parsed.path.rstrip("/")

        # Remove query string and fragment
        normalized = urlunparse((scheme, netloc, path, "", "", ""))

        return normalized

    except Exception:
        return None


def extract_redfin_home_id(url: str) -> Optional[str]:
    """
    Extract the Redfin home ID from a property URL.

    Expected URL pattern: /CA/City/Address/home/ID

    Args:
        url: Redfin property URL

    Returns:
        Home ID as string or None if not found
    """
    if not url:
        return None

    try:
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split("/") if p]

        # Find 'home' keyword and get the next part
        for i, part in enumerate(path_parts):
            if part == "home" and i + 1 < len(path_parts):
                home_id = path_parts[i + 1]
                # Verify it's numeric
                if home_id.isdigit():
                    return home_id

        return None

    except Exception:
        return None


def extract_address_from_redfin_url(url: str) -> Optional[str]:
    """
    Extract and reconstruct address from Redfin URL slug.

    Expected URL pattern: /CA/City/Address-Slug/home/ID

    Args:
        url: Redfin property URL

    Returns:
        Reconstructed address or None if not found
    """
    if not url:
        return None

    try:
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split("/") if p]

        # Expected: [state, city, address_slug, 'home', home_id]
        if len(path_parts) < 5:
            return None

        # Find 'home' keyword
        home_index = None
        for i, part in enumerate(path_parts):
            if part == "home":
                home_index = i
                break

        if home_index is None or home_index < 1:
            return None

        # Address slug should be the part before 'home'
        address_slug = path_parts[home_index - 1]

        # Convert slug to readable address
        # Example: "46197-Via-La-Tranquila-92592" -> "46197 Via La Tranquila 92592"
        address = address_slug.replace("-", " ")

        return address

    except Exception:
        return None


def extract_city_from_redfin_url(url: str) -> Optional[str]:
    """
    Extract city from Redfin URL.

    Expected URL pattern: /CA/City/Address-Slug/home/ID

    Args:
        url: Redfin property URL

    Returns:
        City name or None if not found
    """
    if not url:
        return None

    try:
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split("/") if p]

        # Expected: [state, city, address_slug, 'home', home_id]
        if len(path_parts) < 5:
            return None

        # City should be the second part (index 1)
        city = path_parts[1]

        return city

    except Exception:
        return None


def extract_zip_from_redfin_url(url: str) -> Optional[str]:
    """
    Extract ZIP code from Redfin URL address slug.

    Expected URL pattern: /CA/City/Address-Slug-ZIP/home/ID

    Args:
        url: Redfin property URL

    Returns:
        ZIP code or None if not found
    """
    if not url:
        return None

    try:
        address = extract_address_from_redfin_url(url)
        if not address:
            return None

        # Look for 5-digit ZIP at the end (last 5-digit sequence in the string)
        # Use negative lookahead to ensure it's the last 5-digit number
        zip_match = re.search(r'\b(\d{5})(?!.*\d{5})\b', address)
        if zip_match:
            return zip_match.group(1)

        return None

    except Exception:
        return None
