"""Gas service detection utilities."""

import re
from typing import Optional, Tuple


# Gas-related keywords and phrases
GAS_KEYWORDS = [
    "gas fireplace",
    "gas range",
    "gas cooktop",
    "gas oven",
    "gas heating",
    "gas dryer hookup",
    "natural gas connected",
    "gas utility",
    "gas appliances",
    "gas stove",
    "gas furnace",
    "gas water heater",
    "natural gas",
    "gas line",
    "gas service",
]


def detect_gas_service(text: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Detect if property has natural gas service based on text evidence.

    Per domain rule: Any mention of gas means the property has natural gas supply/service.

    Args:
        text: Property description or details text

    Returns:
        Tuple of (has_gas_service: bool, gas_evidence: Optional[str])
    """
    if not text:
        return False, None

    # Convert to lowercase for case-insensitive matching
    text_lower = text.lower()

    # Look for gas keywords
    evidence_found = []
    for keyword in GAS_KEYWORDS:
        if keyword in text_lower:
            # Find the context around the keyword
            pattern = r".{0,50}" + re.escape(keyword) + r".{0,50}"
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                evidence_found.append(match.group().strip())

    if evidence_found:
        # Deduplicate and join evidence
        unique_evidence = list(set(evidence_found))
        evidence_string = "; ".join(unique_evidence[:3])  # Limit to first 3 pieces of evidence
        return True, evidence_string

    return False, None


def extract_gas_evidence(property_details: Optional[str]) -> Optional[str]:
    """
    Extract gas-related evidence from property details.

    Args:
        property_details: Property description or details text

    Returns:
        Gas evidence string or None
    """
    has_gas, evidence = detect_gas_service(property_details)
    return evidence if has_gas else None
