"""Property scoring engine - Version 1."""

from typing import List, Optional, Tuple

from marketsentry.models import CandidateProperty, WatchedProperty
from marketsentry.quiet_vibrancy import (
    apply_quiet_gatekeeper,
    calculate_location_fit_score,
    evaluate_location_fit,
)


class CandidateScore:
    """Consolidated candidate scoring result."""

    def __init__(self):
        """Initialize scoring result."""
        self.quiet_gatekeeper_result: Optional[str] = None
        self.location_fit_label: Optional[str] = None
        self.location_fit_score: Optional[float] = None
        self.property_fit_score: Optional[float] = None
        self.effective_dom_leverage_score: Optional[float] = None
        self.data_confidence_score: Optional[float] = None
        self.overall_review_score: Optional[float] = None
        self.review_recommendation: str = "needs_more_data"
        self.warning_flags: List[str] = []
        self.positive_flags: List[str] = []
        self.explanation: str = ""
        # v2-aware scoring flags (Milestone 10)
        self.churn_review_flag: bool = False
        self.county_reset_with_churn_flag: bool = False
        self.v2_leverage_flag: bool = False


def score_candidate(
    candidate: CandidateProperty | WatchedProperty,
) -> CandidateScore:
    """
    Score a candidate with comprehensive v1 scoring.

    Args:
        candidate: Candidate or watched property to score

    Returns:
        CandidateScore with all scoring fields
    """
    result = CandidateScore()

    # 1. Apply Quiet Gatekeeper (critical domain rule)
    result.quiet_gatekeeper_result, gatekeeper_reason = apply_quiet_gatekeeper(
        candidate.quiet_score, candidate.vibrancy_score
    )

    # 2. Determine location fit label
    # If gatekeeper fails, location fit is automatically fail_noise_risk
    if result.quiet_gatekeeper_result == "fail_noise_risk":
        result.location_fit_label = "fail_noise_risk"
    elif candidate.quiet_score is not None and candidate.vibrancy_score is not None:
        fit_label, _ = evaluate_location_fit(
            candidate.quiet_score, candidate.vibrancy_score
        )
        # Map to v1 label format
        label_map = {
            "excellent": "excellent_location_fit",
            "target": "target_location_fit",
            "acceptable": "quiet_but_review_vibrancy",
            "poor": "borderline_quiet",
            "no_data": "needs_manual_location_review",
        }
        result.location_fit_label = label_map.get(fit_label, "needs_manual_location_review")
    else:
        result.location_fit_label = "needs_manual_location_review"

    # 3. Calculate location fit score
    result.location_fit_score = _calculate_location_fit_score_v1(
        result.location_fit_label
    )

    # 4. Calculate property fit score
    result.property_fit_score = calculate_property_fit_score(
        gas_service=candidate.gas_service,
        garage_spaces=candidate.garage_spaces,
        price=candidate.price,
        beds=candidate.beds,
        baths=candidate.baths,
        sqft=candidate.sqft,
    )

    # 5. Calculate effective DOM leverage score
    result.effective_dom_leverage_score = calculate_effective_dom_leverage_score_v1(
        effective_dom=getattr(candidate, "effective_dom_estimate", None),
        displayed_dom=candidate.displayed_dom,
        listing_churn_count=candidate.listing_churn_count,
        dom_reset_count=candidate.dom_reset_count,
        sale_rent_alternation_count=candidate.sale_rent_alternation_count,
        price_change_count=getattr(candidate, "price_change_count", None),
    )

    # 6. Calculate data confidence score
    result.data_confidence_score = calculate_data_confidence_score_v1(candidate)

    # 7. Calculate overall review score (weighted average)
    result.overall_review_score = _calculate_overall_review_score(result)

    # 8. Collect warning and positive flags
    result.warning_flags = _collect_warning_flags(candidate, result)
    result.positive_flags = _collect_positive_flags(candidate, result)

    # 9. Apply v2-aware scoring flags (Milestone 10)
    _apply_v2_scoring_flags(candidate, result)

    # 10. Determine review recommendation
    result.review_recommendation = _determine_review_recommendation(result)

    # 11. Generate explanation
    result.explanation = _generate_explanation(result)

    return result


def _calculate_location_fit_score_v1(location_fit_label: Optional[str]) -> Optional[float]:
    """
    Calculate location fit score from label.

    Args:
        location_fit_label: Location fit label

    Returns:
        Location fit score (0-100) or None
    """
    score_map = {
        "excellent_location_fit": 100.0,
        "target_location_fit": 85.0,
        "quiet_but_review_vibrancy": 70.0,
        "borderline_quiet": 50.0,
        "fail_noise_risk": 0.0,
        "needs_manual_location_review": 40.0,
    }
    return score_map.get(location_fit_label)


def calculate_property_fit_score(
    gas_service: Optional[bool],
    garage_spaces: Optional[int],
    price: Optional[float],
    beds: Optional[int],
    baths: Optional[float],
    sqft: Optional[int],
) -> Optional[float]:
    """
    Calculate property fit score based on property features.

    Args:
        gas_service: Whether property has natural gas service
        garage_spaces: Number of garage spaces
        price: Property price
        beds: Number of bedrooms
        baths: Number of bathrooms
        sqft: Square footage

    Returns:
        Property fit score (0-100 scale) or None if insufficient data
    """
    score = 50.0  # Base score

    # Gas service is a strong positive (user preference)
    if gas_service is True:
        score += 20.0
    elif gas_service is False:
        score -= 10.0

    # Garage spaces (minimum 2 required by filter)
    if garage_spaces is not None:
        if garage_spaces >= 2:
            score += 10.0
        if garage_spaces >= 3:
            score += 5.0

    # Price within configured range is positive
    if price is not None:
        if 550000 <= price <= 990000:
            score += 5.0
        else:
            score -= 5.0  # Outside target range

    # Bedroom count (minimum 2 required by filter)
    if beds is not None and beds >= 3:
        score += 5.0

    # Bathroom count (minimum 2 required by filter)
    if baths is not None and baths >= 2.5:
        score += 5.0

    # Square footage
    if sqft is not None and sqft >= 2000:
        score += 5.0

    # Cap at 0-100
    return min(100.0, max(0.0, score))


def calculate_effective_dom_leverage_score_v1(
    effective_dom: Optional[int],
    displayed_dom: Optional[int],
    listing_churn_count: Optional[int],
    dom_reset_count: Optional[int],
    sale_rent_alternation_count: Optional[int],
    price_change_count: Optional[int],
) -> Optional[float]:
    """
    Calculate leverage score based on Effective DOM divergence and activity.

    Positive signals:
    - effective_dom_delta >= 90
    - dom_reset_count >= 1
    - listing_churn_count >= 3
    - sale_rent_alternation_count >= 1
    - price_change_count >= 1

    Args:
        effective_dom: Calculated effective DOM
        displayed_dom: Displayed DOM on listing site
        listing_churn_count: Number of listing churn events
        dom_reset_count: Number of DOM reset events
        sale_rent_alternation_count: Number of sale/rent alternations
        price_change_count: Number of price changes

    Returns:
        DOM leverage score (0-100 scale) or None if insufficient data
    """
    if effective_dom is None or displayed_dom is None:
        return None

    score = 0.0

    # Calculate DOM delta
    dom_delta = effective_dom - displayed_dom

    # DOM delta scoring
    if dom_delta >= 120:
        score += 40.0
    elif dom_delta >= 90:
        score += 30.0
    elif dom_delta >= 60:
        score += 20.0
    elif dom_delta >= 30:
        score += 10.0

    # DOM reset count
    if dom_reset_count and dom_reset_count >= 1:
        score += min(20.0, dom_reset_count * 10.0)

    # Listing churn count
    if listing_churn_count and listing_churn_count >= 3:
        score += min(20.0, (listing_churn_count - 2) * 5.0)

    # Sale/rent alternation
    if sale_rent_alternation_count and sale_rent_alternation_count >= 1:
        score += 15.0

    # Price changes
    if price_change_count and price_change_count >= 1:
        score += min(10.0, price_change_count * 5.0)

    return min(100.0, max(0.0, score))


def calculate_data_confidence_score_v1(
    candidate: CandidateProperty | WatchedProperty,
) -> float:
    """
    Calculate data confidence score based on available fields.

    Positive signals:
    - Redfin URL present
    - Address present
    - Price present
    - Quiet/Vibrancy present
    - Garage/gas fields present
    - Listing events present
    - Effective DOM calculable

    Args:
        candidate: Candidate data

    Returns:
        Data confidence score (0-100 scale)
    """
    score = 0.0
    total_weight = 0.0

    # Redfin URL (10%)
    if candidate.redfin_url:
        score += 10.0
    total_weight += 10.0

    # Address (10%)
    if candidate.address:
        score += 10.0
    total_weight += 10.0

    # Price (15%)
    if candidate.price is not None:
        score += 15.0
    total_weight += 15.0

    # Quiet/Vibrancy (20%)
    if candidate.quiet_score is not None:
        score += 10.0
    if candidate.vibrancy_score is not None:
        score += 10.0
    total_weight += 20.0

    # Garage/gas (15%)
    if candidate.garage_spaces is not None:
        score += 7.5
    if candidate.gas_service is not None:
        score += 7.5
    total_weight += 15.0

    # Listing events (15%)
    if candidate.listing_churn_count and candidate.listing_churn_count > 0:
        score += 15.0
    total_weight += 15.0

    # Effective DOM (15%)
    effective_dom = getattr(candidate, "effective_dom_estimate", None)
    if effective_dom is not None:
        score += 15.0
    total_weight += 15.0

    return score


def _calculate_overall_review_score(result: CandidateScore) -> Optional[float]:
    """
    Calculate weighted overall review score.

    Weights:
    - Location fit: 40%
    - Property fit: 25%
    - DOM leverage: 25%
    - Data confidence: 10%

    Args:
        result: CandidateScore object

    Returns:
        Overall review score (0-100) or None
    """
    scores = []

    if result.location_fit_score is not None:
        scores.append((result.location_fit_score, 0.40))

    if result.property_fit_score is not None:
        scores.append((result.property_fit_score, 0.25))

    if result.effective_dom_leverage_score is not None:
        scores.append((result.effective_dom_leverage_score, 0.25))

    if result.data_confidence_score is not None:
        scores.append((result.data_confidence_score, 0.10))

    if not scores:
        return None

    total_weight = sum(weight for _, weight in scores)
    weighted_sum = sum(score * weight for score, weight in scores)

    return weighted_sum / total_weight if total_weight > 0 else 0.0


def _collect_warning_flags(
    candidate: CandidateProperty | WatchedProperty,
    result: CandidateScore,
) -> List[str]:
    """
    Collect warning flags for the candidate.

    Args:
        candidate: Candidate data
        result: Scoring result

    Returns:
        List of warning flag strings
    """
    flags = []

    # Location warnings
    if result.quiet_gatekeeper_result == "fail_noise_risk":
        flags.append("fail_quiet_gatekeeper")

    if candidate.quiet_score is not None and candidate.quiet_score < 7.0:
        flags.append("low_quiet_score")

    # Property warnings
    if candidate.gas_service is False:
        flags.append("no_gas_service")

    if candidate.garage_spaces is not None and candidate.garage_spaces < 2:
        flags.append("insufficient_garage")

    # Price warnings
    if candidate.price is not None:
        if candidate.price < 550000:
            flags.append("below_min_price")
        elif candidate.price > 990000:
            flags.append("above_max_price")

    # Data warnings
    if result.data_confidence_score and result.data_confidence_score < 50.0:
        flags.append("low_data_confidence")

    if candidate.quiet_score is None:
        flags.append("missing_quiet_score")

    return flags


def _collect_positive_flags(
    candidate: CandidateProperty | WatchedProperty,
    result: CandidateScore,
) -> List[str]:
    """
    Collect positive flags for the candidate.

    Args:
        candidate: Candidate data
        result: Scoring result

    Returns:
        List of positive flag strings
    """
    flags = []

    # Location positives
    if result.location_fit_label == "excellent_location_fit":
        flags.append("excellent_location")
    elif result.location_fit_label == "target_location_fit":
        flags.append("target_location")

    # Property positives
    if candidate.gas_service is True:
        flags.append("has_gas_service")

    if candidate.garage_spaces and candidate.garage_spaces >= 3:
        flags.append("three_plus_garage")

    # DOM leverage positives
    effective_dom = getattr(candidate, "effective_dom_estimate", None)
    if effective_dom and candidate.displayed_dom:
        delta = effective_dom - candidate.displayed_dom
        if delta >= 90:
            flags.append("high_dom_delta")

    if candidate.dom_reset_count and candidate.dom_reset_count >= 1:
        flags.append("has_dom_resets")

    if candidate.listing_churn_count and candidate.listing_churn_count >= 3:
        flags.append("high_listing_churn")

    if candidate.sale_rent_alternation_count and candidate.sale_rent_alternation_count >= 1:
        flags.append("sale_rent_alternation")

    return flags


def _apply_v2_scoring_flags(
    candidate: CandidateProperty | WatchedProperty,
    result: CandidateScore,
) -> None:
    """
    Apply v2-aware scoring flags based on Effective DOM v2 and Churn Index.

    Sets neutral review/leverage flags. Does NOT override Quiet gatekeeper.
    High churn is a review signal, not a rejection or accusation.

    Positive buyer-review signals:
    - effective_dom_delta_v2 >= 90
    - county_reset_applied true but recent_churn_index >= 5
    - recent_churn_index >= 6
    - dom_reset_count >= 1
    - sale_rent_alternation_count >= 1
    - price_change_count >= 1

    Args:
        candidate: Candidate or watched property
        result: CandidateScore to update
    """
    # Get v2 fields if available
    effective_dom_delta_v2 = getattr(candidate, "effective_dom_delta_v2", None)
    county_reset_applied = getattr(candidate, "county_reset_applied", None)
    recent_churn_index = getattr(candidate, "recent_churn_index", None)
    recent_dom_reset_count = getattr(candidate, "recent_dom_reset_count", None)
    recent_sale_rent_alternation_count = getattr(
        candidate, "recent_sale_rent_alternation_count", None
    )

    # churn_review_flag: high recent churn (neutral review signal)
    if recent_churn_index is not None and recent_churn_index >= 6:
        result.churn_review_flag = True
        result.positive_flags.append("high_recent_churn")

    # county_reset_with_churn_flag: county reset applied but churn preserved
    if county_reset_applied and recent_churn_index is not None and recent_churn_index >= 5:
        result.county_reset_with_churn_flag = True
        result.positive_flags.append("county_reset_with_preserved_churn")

    # v2_leverage_flag: v2 delta signals buyer leverage
    if effective_dom_delta_v2 is not None and effective_dom_delta_v2 >= 90:
        result.v2_leverage_flag = True
        result.positive_flags.append("high_v2_dom_delta")

    # Additional v2 review signals added to positive flags
    if recent_dom_reset_count is not None and recent_dom_reset_count >= 1:
        if "has_dom_resets" not in result.positive_flags:
            result.positive_flags.append("review_listing_history")

    if recent_sale_rent_alternation_count is not None and recent_sale_rent_alternation_count >= 1:
        if "sale_rent_alternation" not in result.positive_flags:
            result.positive_flags.append("review_listing_history")


def _determine_review_recommendation(result: CandidateScore) -> str:
    """
    Determine review recommendation based on scoring.

    Values:
    - strong_review
    - review
    - maybe_review
    - reject_location_noise
    - needs_more_data

    Args:
        result: CandidateScore object

    Returns:
        Review recommendation string
    """
    # Reject if gatekeeper fails
    if result.quiet_gatekeeper_result == "fail_noise_risk":
        return "reject_location_noise"

    # Need more data if confidence is very low
    if result.data_confidence_score and result.data_confidence_score < 30.0:
        return "needs_more_data"

    # Strong review if overall score is high
    if result.overall_review_score and result.overall_review_score >= 80.0:
        return "strong_review"

    # Review if overall score is good
    if result.overall_review_score and result.overall_review_score >= 60.0:
        return "review"

    # Maybe review if overall score is moderate
    if result.overall_review_score and result.overall_review_score >= 40.0:
        return "maybe_review"

    # Need more data otherwise
    return "needs_more_data"


def _generate_explanation(result: CandidateScore) -> str:
    """
    Generate human-readable explanation of scoring.

    Args:
        result: CandidateScore object

    Returns:
        Explanation string
    """
    parts = []

    # Location explanation
    if result.location_fit_label:
        parts.append(f"Location: {result.location_fit_label.replace('_', ' ').title()}")

    # Recommendation explanation
    parts.append(f"Recommendation: {result.review_recommendation.replace('_', ' ').title()}")

    # Warnings
    if result.warning_flags:
        parts.append(f"Warnings: {', '.join(result.warning_flags)}")

    # Positives
    if result.positive_flags:
        parts.append(f"Positives: {', '.join(result.positive_flags)}")

    return ". ".join(parts) + "."


# Legacy compatibility function
def score_property(
    property_data: CandidateProperty | WatchedProperty,
):
    """
    Legacy scoring function (maintained for backwards compatibility).

    Use score_candidate() for v1 comprehensive scoring.

    Args:
        property_data: Property to score

    Returns:
        ScoreResult object (legacy format)
    """
    from marketsentry.models import ScoreResult

    result = ScoreResult()

    # Apply Quiet gatekeeper
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
        price=property_data.price,
        beds=property_data.beds,
        baths=property_data.baths,
        sqft=property_data.sqft,
    )
    result.property_fit_score = property_score

    # Calculate effective DOM leverage score
    dom_leverage_score = calculate_effective_dom_leverage_score_v1(
        effective_dom=getattr(property_data, "effective_dom", None),
        displayed_dom=property_data.displayed_dom,
        listing_churn_count=property_data.listing_churn_count,
        dom_reset_count=property_data.dom_reset_count,
        sale_rent_alternation_count=property_data.sale_rent_alternation_count,
        price_change_count=None,
    )
    result.effective_dom_leverage_score = dom_leverage_score

    # Calculate data confidence score
    confidence_score = calculate_data_confidence_score_v1(property_data)
    result.data_confidence_score = confidence_score

    # Calculate overall score (0-10 scale for legacy compatibility)
    overall = _calculate_overall_review_score(
        type('obj', (object,), {
            'location_fit_score': location_score,
            'property_fit_score': property_score,
            'effective_dom_leverage_score': dom_leverage_score,
            'data_confidence_score': confidence_score,
        })()
    )
    result.overall_score = (overall / 10.0) if overall is not None else 0.0

    return result


# Backward compatibility aliases
calculate_effective_dom_leverage_score = calculate_effective_dom_leverage_score_v1
calculate_data_confidence_score = calculate_data_confidence_score_v1
