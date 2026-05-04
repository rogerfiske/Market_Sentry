"""Property scoring engine."""

from typing import Optional, Tuple

from marketsentry.models import CandidateProperty, ScoreResult, WatchedProperty
from marketsentry.quiet_vibrancy import (
    apply_quiet_gatekeeper,
    calculate_location_fit_score,
)


def score_property(
    property_data: CandidateProperty | WatchedProperty,
) -> ScoreResult:
    """
    Score a property based on multiple factors.

    Args:
        property_data: Property to score (candidate or watched)

    Returns:
        ScoreResult with individual and overall scores
    """
    result = ScoreResult()

    # Apply Quiet gatekeeper (critical domain rule)
    gatekeeper_result, gatekeeper_reason = apply_quiet_gatekeeper(
        property_data.quiet_score, property_data.vibrancy_score
    )
    result.quiet_gatekeeper_result = gatekeeper_result

    # If gatekeeper fails, heavily penalize overall score
    if gatekeeper_result != "pass":
        result.location_fit_score = 0.0
        result.overall_score = 0.0
        result.scoring_notes = gatekeeper_reason
        return result

    # Calculate location fit score
    location_score = calculate_location_fit_score(
        property_data.quiet_score, property_data.vibrancy_score
    )
    result.location_fit_score = location_score

    # Calculate property fit score
    property_score = calculate_property_fit_score(
        gas_service=property_data.gas_service,
        garage_spaces=property_data.garage_spaces,
        beds=property_data.beds,
        baths=property_data.baths,
        sqft=property_data.sqft,
    )
    result.property_fit_score = property_score

    # Calculate effective DOM leverage score
    dom_leverage_score = calculate_effective_dom_leverage_score(
        effective_dom=getattr(property_data, "effective_dom", None),
        displayed_dom=property_data.displayed_dom,
        listing_churn_count=property_data.listing_churn_count,
    )
    result.effective_dom_leverage_score = dom_leverage_score

    # Calculate data confidence score
    confidence_score = calculate_data_confidence_score(property_data)
    result.data_confidence_score = confidence_score

    # Calculate overall score (weighted average)
    scores = [
        (location_score, 0.40) if location_score is not None else None,
        (property_score, 0.25) if property_score is not None else None,
        (dom_leverage_score, 0.25) if dom_leverage_score is not None else None,
        (confidence_score, 0.10) if confidence_score is not None else None,
    ]

    valid_scores = [s for s in scores if s is not None]
    if valid_scores:
        total_weight = sum(weight for _, weight in valid_scores)
        weighted_sum = sum(score * weight for score, weight in valid_scores)
        result.overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
    else:
        result.overall_score = 0.0

    return result


def calculate_property_fit_score(
    gas_service: Optional[bool],
    garage_spaces: Optional[int],
    beds: Optional[int],
    baths: Optional[float],
    sqft: Optional[int],
) -> Optional[float]:
    """
    Calculate property fit score based on basic property features.

    Args:
        gas_service: Whether property has natural gas service
        garage_spaces: Number of garage spaces
        beds: Number of bedrooms
        baths: Number of bathrooms
        sqft: Square footage

    Returns:
        Property fit score (0-10 scale) or None if insufficient data
    """
    score = 5.0  # Base score

    # Gas service is preferred
    if gas_service is True:
        score += 2.0
    elif gas_service is False:
        score -= 1.0

    # Garage spaces (minimum 2 required by search filter)
    if garage_spaces is not None:
        if garage_spaces >= 2:
            score += 1.0
        if garage_spaces >= 3:
            score += 0.5

    # Bedroom count (minimum 2 required by search filter)
    if beds is not None and beds >= 3:
        score += 0.5

    # Bathroom count (minimum 2 required by search filter)
    if baths is not None and baths >= 2.5:
        score += 0.5

    # Square footage bonus for larger homes
    if sqft is not None and sqft >= 2000:
        score += 0.5

    # Cap at 10.0
    return min(10.0, max(0.0, score))


def calculate_effective_dom_leverage_score(
    effective_dom: Optional[int],
    displayed_dom: Optional[int],
    listing_churn_count: Optional[int],
) -> Optional[float]:
    """
    Calculate leverage score based on effective DOM divergence.

    Higher scores indicate properties with significant DOM divergence,
    suggesting potential negotiation leverage.

    Args:
        effective_dom: Calculated effective DOM
        displayed_dom: Displayed DOM on listing site
        listing_churn_count: Number of listing churn events

    Returns:
        DOM leverage score (0-10 scale) or None if insufficient data
    """
    if effective_dom is None or displayed_dom is None:
        return None

    # Calculate DOM delta
    dom_delta = effective_dom - displayed_dom

    # Base score from DOM delta
    if dom_delta <= 0:
        score = 0.0
    elif dom_delta < 30:
        score = 2.0
    elif dom_delta < 60:
        score = 4.0
    elif dom_delta < 90:
        score = 6.0
    elif dom_delta < 120:
        score = 8.0
    else:
        score = 10.0

    # Bonus for listing churn
    if listing_churn_count is not None and listing_churn_count > 0:
        score += min(2.0, listing_churn_count * 0.5)

    return min(10.0, max(0.0, score))


def calculate_data_confidence_score(
    property_data: CandidateProperty | WatchedProperty,
) -> float:
    """
    Calculate data confidence score based on available fields.

    Args:
        property_data: Property data

    Returns:
        Data confidence score (0-10 scale)
    """
    fields_to_check = [
        property_data.quiet_score,
        property_data.vibrancy_score,
        property_data.displayed_dom,
        property_data.garage_spaces,
        property_data.gas_service,
        property_data.beds,
        property_data.baths,
        property_data.sqft,
        property_data.price,
    ]

    fields_present = sum(1 for field in fields_to_check if field is not None)
    total_fields = len(fields_to_check)

    # Convert to 0-10 scale
    return (fields_present / total_fields) * 10.0
