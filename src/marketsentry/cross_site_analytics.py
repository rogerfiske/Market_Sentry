"""Confidence-weighted cross-site comparison analytics.

Produces improved cross-site validation metrics by weighting source
observations according to parse confidence, data freshness, source
agreement, and field completeness.

Cross-site data remains validation/check data. It does not overwrite
Redfin source-of-truth fields.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from marketsentry.database import execute_query
from marketsentry.logging_config import logger
from marketsentry.models import (
    CrossSiteAnalyticsResult,
    CrossSiteConfidenceMetrics,
    CrossSiteDiscrepancySeverity,
    CrossSiteFieldAgreement,
    CrossSiteSourceWeight,
)


# ---------------------------------------------------------------------------
# Weight calculation functions
# ---------------------------------------------------------------------------


def confidence_to_weight(parse_confidence: Optional[str]) -> float:
    """Convert parse confidence level to a numeric weight.

    Args:
        parse_confidence: Confidence level (high, medium, low) or None.

    Returns:
        Weight between 0.0 and 1.0.
    """
    weights = {
        "high": 1.0,
        "medium": 0.7,
        "low": 0.4,
    }
    if not parse_confidence:
        return 0.4
    return weights.get(parse_confidence.lower(), 0.4)


def freshness_to_weight(
    observed_at: Optional[datetime],
    analysis_date: Optional[datetime] = None,
) -> float:
    """Convert observation age to a freshness weight.

    Args:
        observed_at: When the observation was recorded.
        analysis_date: Analysis reference date (defaults to now).

    Returns:
        Weight between 0.0 and 1.0.
    """
    if not observed_at:
        return 0.2

    if analysis_date is None:
        analysis_date = datetime.now()

    # Handle string timestamps from SQLite
    if isinstance(observed_at, str):
        try:
            observed_at = datetime.fromisoformat(observed_at)
        except (ValueError, TypeError):
            return 0.2

    age = analysis_date - observed_at
    days = age.days

    if days <= 7:
        return 1.0
    elif days <= 30:
        return 0.8
    elif days <= 90:
        return 0.5
    else:
        return 0.2


def completeness_to_weight(observation: Dict[str, Any]) -> float:
    """Calculate a completeness weight based on field availability.

    Args:
        observation: Observation dictionary with property fields.

    Returns:
        Weight between 0.0 and 1.0.
    """
    required_fields = ["price", "listing_status", "beds", "baths", "sqft"]
    present = sum(1 for f in required_fields if observation.get(f) is not None)
    if not required_fields:
        return 1.0
    return round(present / len(required_fields), 2)


def calculate_source_weight(
    parse_confidence: Optional[str],
    parse_status: Optional[str],
    observed_at: Optional[datetime],
    observation: Dict[str, Any],
    analysis_date: Optional[datetime] = None,
) -> CrossSiteSourceWeight:
    """Calculate combined weight for a single source observation.

    Args:
        parse_confidence: Confidence level from parser.
        parse_status: Parse status (success, partial, failed).
        observed_at: When the observation was recorded.
        observation: Observation data dictionary.
        analysis_date: Analysis reference date.

    Returns:
        CrossSiteSourceWeight with individual and combined weights.
    """
    source_site = observation.get("source_site", "unknown")

    # Failed parse gets zero weight
    if parse_status == "failed":
        return CrossSiteSourceWeight(
            source_site=source_site,
            confidence_weight=0.0,
            freshness_weight=0.0,
            completeness_weight=0.0,
            combined_weight=0.0,
            is_stale=True,
            is_low_confidence=True,
            has_parse_warnings=bool(observation.get("parse_warnings")),
            observed_at=observed_at if isinstance(observed_at, datetime) else None,
            parse_confidence=parse_confidence,
            parse_status=parse_status,
        )

    conf_w = confidence_to_weight(parse_confidence)
    fresh_w = freshness_to_weight(observed_at, analysis_date)
    comp_w = completeness_to_weight(observation)

    # Combined weight is product of individual weights
    combined = round(conf_w * fresh_w * comp_w, 4)

    is_stale = fresh_w <= 0.5
    is_low_conf = parse_confidence in ("low", None)

    return CrossSiteSourceWeight(
        source_site=source_site,
        confidence_weight=conf_w,
        freshness_weight=fresh_w,
        completeness_weight=comp_w,
        combined_weight=combined,
        is_stale=is_stale,
        is_low_confidence=is_low_conf,
        has_parse_warnings=bool(observation.get("parse_warnings")),
        observed_at=observed_at if isinstance(observed_at, datetime) else None,
        parse_confidence=parse_confidence,
        parse_status=parse_status,
    )


# ---------------------------------------------------------------------------
# Field agreement functions
# ---------------------------------------------------------------------------


def calculate_field_agreement(
    field_name: str,
    redfin_value: Any,
    source_values: Dict[str, Any],
    source_weights: Dict[str, float],
    tolerance: float = 0.0,
) -> CrossSiteFieldAgreement:
    """Calculate weighted agreement for a single field.

    Sources that agree with Redfin (within tolerance) contribute their
    weight positively.  The score is the weighted fraction of agreeing
    sources.

    Args:
        field_name: Name of the field.
        redfin_value: Redfin reference value.
        source_values: Mapping of source_site to value.
        source_weights: Mapping of source_site to combined weight.
        tolerance: Absolute tolerance for numeric comparison.

    Returns:
        CrossSiteFieldAgreement with score and details.
    """
    contributing = 0
    agreeing = 0
    total_weight = 0.0
    agreeing_weight = 0.0
    str_values: Dict[str, str] = {}

    for site, value in source_values.items():
        if value is None:
            continue
        weight = source_weights.get(site, 0.0)
        if weight <= 0.0:
            continue

        contributing += 1
        total_weight += weight
        str_values[site] = str(value)

        if redfin_value is None:
            # No Redfin baseline; can only compare sources to each other
            continue

        # Check agreement
        if _values_agree(redfin_value, value, tolerance):
            agreeing += 1
            agreeing_weight += weight

    score = 0.0
    if total_weight > 0 and redfin_value is not None:
        score = round(agreeing_weight / total_weight, 4)

    return CrossSiteFieldAgreement(
        field_name=field_name,
        agreement_score=score,
        contributing_sources=contributing,
        agreeing_sources=agreeing,
        redfin_value=str(redfin_value) if redfin_value is not None else None,
        source_values=str_values,
    )


def _values_agree(redfin_value: Any, source_value: Any, tolerance: float) -> bool:
    """Check whether two values agree within tolerance.

    For numeric values uses absolute tolerance.
    For strings uses case-insensitive equality after normalization.
    """
    if redfin_value is None or source_value is None:
        return False

    # Numeric comparison
    try:
        r = float(redfin_value)
        s = float(source_value)
        return abs(r - s) <= tolerance
    except (ValueError, TypeError):
        pass

    # String comparison
    return str(redfin_value).lower().strip() == str(source_value).lower().strip()


def calculate_price_agreement(
    redfin_price: Optional[float],
    source_prices: Dict[str, Optional[float]],
    source_weights: Dict[str, float],
) -> CrossSiteFieldAgreement:
    """Calculate weighted price agreement across sources.

    Prices within $10,000 of Redfin are considered agreeing.

    Args:
        redfin_price: Redfin reference price.
        source_prices: Mapping of source_site to price.
        source_weights: Mapping of source_site to combined weight.

    Returns:
        CrossSiteFieldAgreement for price.
    """
    values = {s: p for s, p in source_prices.items() if p is not None}
    return calculate_field_agreement(
        "price", redfin_price, values, source_weights, tolerance=10000.0
    )


def calculate_status_agreement(
    redfin_status: Optional[str],
    source_statuses: Dict[str, Optional[str]],
    source_weights: Dict[str, float],
) -> CrossSiteFieldAgreement:
    """Calculate weighted status agreement across sources.

    Statuses must match exactly after normalization.

    Args:
        redfin_status: Redfin reference status.
        source_statuses: Mapping of source_site to status.
        source_weights: Mapping of source_site to combined weight.

    Returns:
        CrossSiteFieldAgreement for status.
    """
    # Normalize for comparison
    norm_redfin = _normalize_status_for_agreement(redfin_status)
    norm_sources = {
        s: _normalize_status_for_agreement(v)
        for s, v in source_statuses.items()
        if v is not None
    }
    return calculate_field_agreement(
        "status", norm_redfin, norm_sources, source_weights, tolerance=0.0
    )


def _normalize_status_for_agreement(status: Optional[str]) -> Optional[str]:
    """Normalize status string for agreement comparison."""
    if not status:
        return None
    s = status.lower().strip()
    if "sold" in s:
        return "sold"
    if "pending" in s:
        return "pending"
    if "contingent" in s:
        return "pending"
    if "off" in s:
        return "off_market"
    if "coming" in s:
        return "coming_soon"
    if "rent" in s:
        return "rental"
    if "sale" in s or "active" in s or s == "for_sale":
        return "active"
    return s


def calculate_dom_agreement(
    redfin_dom: Optional[int],
    source_doms: Dict[str, Optional[int]],
    source_weights: Dict[str, float],
) -> CrossSiteFieldAgreement:
    """Calculate weighted DOM agreement across sources.

    DOMs within 30 days of Redfin are considered agreeing.

    Args:
        redfin_dom: Redfin reference DOM.
        source_doms: Mapping of source_site to DOM.
        source_weights: Mapping of source_site to combined weight.

    Returns:
        CrossSiteFieldAgreement for DOM.
    """
    values = {s: d for s, d in source_doms.items() if d is not None}
    return calculate_field_agreement(
        "dom", redfin_dom, values, source_weights, tolerance=30.0
    )


def calculate_garage_agreement(
    redfin_garage: Optional[int],
    source_garages: Dict[str, Optional[int]],
    source_weights: Dict[str, float],
) -> CrossSiteFieldAgreement:
    """Calculate weighted garage agreement across sources.

    Garage spaces must match exactly.

    Args:
        redfin_garage: Redfin reference garage spaces.
        source_garages: Mapping of source_site to garage spaces.
        source_weights: Mapping of source_site to combined weight.

    Returns:
        CrossSiteFieldAgreement for garage.
    """
    values = {s: g for s, g in source_garages.items() if g is not None}
    return calculate_field_agreement(
        "garage", redfin_garage, values, source_weights, tolerance=0.0
    )


def calculate_gas_agreement(
    redfin_gas: Optional[bool],
    source_gas: Dict[str, Optional[bool]],
    source_weights: Dict[str, float],
) -> CrossSiteFieldAgreement:
    """Calculate weighted gas-service agreement across sources.

    Boolean gas_service must match exactly.

    Args:
        redfin_gas: Redfin gas service flag.
        source_gas: Mapping of source_site to gas_service.
        source_weights: Mapping of source_site to combined weight.

    Returns:
        CrossSiteFieldAgreement for gas.
    """
    # Convert booleans to comparable strings
    redfin_str = str(redfin_gas).lower() if redfin_gas is not None else None
    source_str = {
        s: str(v).lower() for s, v in source_gas.items() if v is not None
    }
    return calculate_field_agreement(
        "gas", redfin_str, source_str, source_weights, tolerance=0.0
    )


# ---------------------------------------------------------------------------
# Confidence metrics
# ---------------------------------------------------------------------------


def calculate_cross_site_confidence_metrics(
    source_weights: List[CrossSiteSourceWeight],
    field_agreements: List[CrossSiteFieldAgreement],
) -> CrossSiteConfidenceMetrics:
    """Calculate aggregated confidence metrics.

    Args:
        source_weights: Weights for each source.
        field_agreements: Agreement scores for each field.

    Returns:
        CrossSiteConfidenceMetrics with aggregated scores.
    """
    # Source freshness: average freshness weight
    freshness_vals = [w.freshness_weight for w in source_weights if w.combined_weight > 0]
    freshness_score = round(sum(freshness_vals) / len(freshness_vals), 4) if freshness_vals else 0.0

    # Source completeness: average completeness weight
    comp_vals = [w.completeness_weight for w in source_weights if w.combined_weight > 0]
    completeness_score = round(sum(comp_vals) / len(comp_vals), 4) if comp_vals else 0.0

    # Source agreement: average field agreement scores
    agreement_vals = [fa.agreement_score for fa in field_agreements if fa.contributing_sources > 0]
    agreement_score = round(sum(agreement_vals) / len(agreement_vals), 4) if agreement_vals else 0.0

    # Overall: weighted combination (freshness 25%, completeness 25%, agreement 50%)
    overall = round(
        freshness_score * 0.25 + completeness_score * 0.25 + agreement_score * 0.50,
        4,
    )

    contributing = [w.source_site for w in source_weights if w.combined_weight > 0]
    low_conf = [w.source_site for w in source_weights if w.is_low_confidence]
    stale = [w.source_site for w in source_weights if w.is_stale]
    warnings = [w.source_site for w in source_weights if w.has_parse_warnings]

    return CrossSiteConfidenceMetrics(
        source_freshness_score=freshness_score,
        source_completeness_score=completeness_score,
        source_agreement_score=agreement_score,
        overall_cross_site_confidence_score=overall,
        contributing_sources=contributing,
        low_confidence_sources=low_conf,
        stale_sources=stale,
        parse_warning_sources=warnings,
    )


# ---------------------------------------------------------------------------
# Discrepancy severity
# ---------------------------------------------------------------------------


def calculate_discrepancy_severity(
    redfin_price: Optional[float],
    redfin_status: Optional[str],
    redfin_dom: Optional[int],
    redfin_garage: Optional[int],
    redfin_gas: Optional[bool],
    source_data: Dict[str, Dict[str, Any]],
    source_weights: Dict[str, float],
) -> CrossSiteDiscrepancySeverity:
    """Calculate neutral discrepancy severity scoring.

    Low-confidence sources reduce severity certainty rather than
    exaggerating it.

    Args:
        redfin_price: Redfin price.
        redfin_status: Redfin listing status.
        redfin_dom: Redfin DOM.
        redfin_garage: Redfin garage spaces.
        redfin_gas: Redfin gas service.
        source_data: Per-source observation dicts.
        source_weights: Per-source combined weights.

    Returns:
        CrossSiteDiscrepancySeverity with severity labels and flags.
    """
    severity = CrossSiteDiscrepancySeverity()
    flags: List[str] = []

    # Price severity
    price_sev = _calculate_price_severity(redfin_price, source_data, source_weights)
    severity.price_severity = price_sev
    if price_sev != "none":
        flags.append("price_discrepancy")

    # Status severity
    status_sev = _calculate_status_severity(redfin_status, source_data, source_weights)
    severity.status_severity = status_sev
    if status_sev != "none":
        flags.append("status_discrepancy")

    # DOM severity
    dom_sev = _calculate_dom_severity(redfin_dom, source_data, source_weights)
    severity.dom_severity = dom_sev
    if dom_sev != "none":
        flags.append("dom_discrepancy")

    # Gas severity
    gas_sev = _calculate_gas_severity(redfin_gas, source_data, source_weights)
    severity.gas_severity = gas_sev
    if gas_sev != "none":
        flags.append("gas_disagreement")

    # Garage severity
    garage_sev = _calculate_garage_severity(redfin_garage, source_data, source_weights)
    severity.garage_severity = garage_sev
    if garage_sev != "none":
        flags.append("garage_disagreement")

    # Low-confidence source flag
    low_conf_sites = [s for s, w in source_weights.items() if w < 0.5 and w > 0]
    if low_conf_sites:
        flags.append("low_confidence_source")

    severity.flags = flags

    # Overall severity is the worst individual severity
    all_sevs = [price_sev, status_sev, dom_sev, gas_sev, garage_sev]
    severity_rank = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    max_sev = max(all_sevs, key=lambda s: severity_rank.get(s, 0))
    severity.severity_label = max_sev
    severity.severity_score = round(severity_rank.get(max_sev, 0) / 4.0, 2)

    return severity


def _calculate_price_severity(
    redfin_price: Optional[float],
    source_data: Dict[str, Dict],
    source_weights: Dict[str, float],
) -> str:
    """Calculate price discrepancy severity."""
    if redfin_price is None:
        return "none"

    max_diff = 0.0
    max_weight = 0.0

    for site, data in source_data.items():
        price = data.get("price")
        if price is None:
            continue
        weight = source_weights.get(site, 0.0)
        if weight <= 0.0:
            continue

        diff = abs(price - redfin_price)
        if diff > max_diff:
            max_diff = diff
            max_weight = weight

    if max_diff <= 10000:
        return "none"

    # Low-confidence reduces severity certainty
    confidence_factor = min(1.0, max_weight / 0.7) if max_weight > 0 else 0.5

    if max_diff > 50000:
        base = "high"
    elif max_diff > 25000:
        base = "medium"
    else:
        base = "low"

    # Downgrade by one level if source weight is very low
    if confidence_factor < 0.5 and base != "low":
        downgrade = {"high": "medium", "medium": "low", "critical": "high"}
        base = downgrade.get(base, base)

    return base


def _calculate_status_severity(
    redfin_status: Optional[str],
    source_data: Dict[str, Dict],
    source_weights: Dict[str, float],
) -> str:
    """Calculate status discrepancy severity."""
    if redfin_status is None:
        return "none"

    norm_redfin = _normalize_status_for_agreement(redfin_status)
    has_conflict = False
    max_weight = 0.0

    for site, data in source_data.items():
        status = data.get("listing_status")
        if status is None:
            continue
        weight = source_weights.get(site, 0.0)
        if weight <= 0.0:
            continue

        norm = _normalize_status_for_agreement(status)
        if norm != norm_redfin:
            has_conflict = True
            if weight > max_weight:
                max_weight = weight

    if not has_conflict:
        return "none"

    # Active vs sold/pending/off_market is high severity
    conflict_statuses = set()
    conflict_statuses.add(norm_redfin or "")
    for site, data in source_data.items():
        s = _normalize_status_for_agreement(data.get("listing_status"))
        if s:
            conflict_statuses.add(s)

    active_present = "active" in conflict_statuses
    terminal_present = bool(conflict_statuses & {"sold", "pending", "off_market"})

    if active_present and terminal_present:
        base = "high"
    else:
        base = "medium"

    # Downgrade if low confidence
    if max_weight < 0.5 and base == "high":
        base = "medium"

    return base


def _calculate_dom_severity(
    redfin_dom: Optional[int],
    source_data: Dict[str, Dict],
    source_weights: Dict[str, float],
) -> str:
    """Calculate DOM discrepancy severity."""
    if redfin_dom is None:
        return "none"

    max_diff = 0
    max_weight = 0.0

    for site, data in source_data.items():
        dom = data.get("displayed_dom")
        if dom is None:
            continue
        weight = source_weights.get(site, 0.0)
        if weight <= 0.0:
            continue

        diff = abs(dom - redfin_dom)
        if diff > max_diff:
            max_diff = diff
            max_weight = weight

    if max_diff <= 30:
        return "none"

    if max_diff > 90:
        base = "high"
    else:
        base = "medium"

    if max_weight < 0.5 and base == "high":
        base = "medium"

    return base


def _calculate_gas_severity(
    redfin_gas: Optional[bool],
    source_data: Dict[str, Dict],
    source_weights: Dict[str, float],
) -> str:
    """Calculate gas-service disagreement severity."""
    if redfin_gas is None:
        return "none"

    has_disagreement = False

    for site, data in source_data.items():
        gas = data.get("gas_service")
        if gas is None:
            continue
        weight = source_weights.get(site, 0.0)
        if weight <= 0.0:
            continue

        if bool(gas) != bool(redfin_gas):
            has_disagreement = True

    return "low" if has_disagreement else "none"


def _calculate_garage_severity(
    redfin_garage: Optional[int],
    source_data: Dict[str, Dict],
    source_weights: Dict[str, float],
) -> str:
    """Calculate garage disagreement severity."""
    if redfin_garage is None:
        return "none"

    has_disagreement = False

    for site, data in source_data.items():
        garage = data.get("garage_spaces")
        if garage is None:
            continue
        weight = source_weights.get(site, 0.0)
        if weight <= 0.0:
            continue

        if garage != redfin_garage:
            has_disagreement = True

    return "low" if has_disagreement else "none"


# ---------------------------------------------------------------------------
# Manual review priority
# ---------------------------------------------------------------------------


def _determine_review_priority(
    severity: CrossSiteDiscrepancySeverity,
    confidence: CrossSiteConfidenceMetrics,
) -> str:
    """Determine manual review priority from severity and confidence.

    Args:
        severity: Discrepancy severity assessment.
        confidence: Confidence metrics.

    Returns:
        Priority label: none, low, medium, high.
    """
    sev_rank = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    sev_val = sev_rank.get(severity.severity_label, 0)

    if sev_val >= 3:
        return "high"
    if sev_val == 2:
        return "medium"
    if sev_val == 1:
        # Low severity + low confidence => medium priority (uncertain data)
        if confidence.low_confidence_sources:
            return "medium"
        return "low"

    # No discrepancy
    if confidence.low_confidence_sources or confidence.stale_sources:
        return "low"

    return "none"


# ---------------------------------------------------------------------------
# High-level analysis functions
# ---------------------------------------------------------------------------


def analyze_cross_site_observations(
    property_id: int,
    database_path: Optional[str] = None,
    analysis_date: Optional[datetime] = None,
) -> CrossSiteAnalyticsResult:
    """Analyze cross-site observations for a single property.

    Queries the database for Redfin data and cross-site observations,
    then produces confidence-weighted analytics.

    Args:
        property_id: Watched property ID.
        database_path: Optional database path.
        analysis_date: Analysis reference date (defaults to now).

    Returns:
        CrossSiteAnalyticsResult with full analytics.
    """
    result = CrossSiteAnalyticsResult(property_id=property_id)

    try:
        # Get Redfin data
        redfin = _get_redfin_property_data(property_id, database_path)
        if redfin:
            result.address = redfin.get("address")
            result.city = redfin.get("city")
            result.zip = redfin.get("zip")

        # Get cross-site observations (all fields)
        observations = _get_full_cross_site_observations(property_id, database_path)

        if not observations:
            return result

        result = analyze_property_cross_site_metrics(
            property_id=property_id,
            redfin_data=redfin or {},
            observations=observations,
            analysis_date=analysis_date,
        )
        # Restore property info
        if redfin:
            result.address = redfin.get("address")
            result.city = redfin.get("city")
            result.zip = redfin.get("zip")

    except Exception as e:
        logger.error(f"Error analyzing cross-site for property {property_id}: {e}")
        result.notes = f"Analysis error: {str(e)}"

    return result


def analyze_property_cross_site_metrics(
    property_id: int,
    redfin_data: Dict[str, Any],
    observations: Dict[str, Dict[str, Any]],
    analysis_date: Optional[datetime] = None,
) -> CrossSiteAnalyticsResult:
    """Analyze cross-site metrics from pre-fetched data.

    This is the core analytics engine. It does not query the database
    itself, making it easy to test with synthetic data.

    Args:
        property_id: Property ID.
        redfin_data: Redfin property data dict.
        observations: Per-source observation dicts.
        analysis_date: Analysis reference date.

    Returns:
        CrossSiteAnalyticsResult with full analytics.
    """
    result = CrossSiteAnalyticsResult(property_id=property_id)

    # 1. Calculate source weights
    weights: List[CrossSiteSourceWeight] = []
    weight_map: Dict[str, float] = {}

    for site, obs in observations.items():
        observed_at = obs.get("observed_at")
        # Parse string timestamps
        if isinstance(observed_at, str):
            try:
                observed_at = datetime.fromisoformat(observed_at)
            except (ValueError, TypeError):
                observed_at = None

        sw = calculate_source_weight(
            parse_confidence=obs.get("parse_confidence"),
            parse_status=obs.get("parse_status", "success"),
            observed_at=observed_at,
            observation={**obs, "source_site": site},
            analysis_date=analysis_date,
        )
        sw.source_site = site
        weights.append(sw)
        weight_map[site] = sw.combined_weight

    result.source_weights = weights

    # 2. Calculate field agreements
    redfin_price = redfin_data.get("current_price")
    redfin_dom = redfin_data.get("displayed_dom")
    redfin_status = redfin_data.get("listing_status", "active")
    redfin_garage = redfin_data.get("garage_spaces")
    redfin_gas = redfin_data.get("gas_service")

    source_prices = {s: obs.get("price") for s, obs in observations.items()}
    source_statuses = {s: obs.get("listing_status") for s, obs in observations.items()}
    source_doms = {s: obs.get("displayed_dom") for s, obs in observations.items()}
    source_garages = {s: obs.get("garage_spaces") for s, obs in observations.items()}
    source_gas = {s: obs.get("gas_service") for s, obs in observations.items()}

    result.price_agreement = calculate_price_agreement(redfin_price, source_prices, weight_map)
    result.status_agreement = calculate_status_agreement(redfin_status, source_statuses, weight_map)
    result.dom_agreement = calculate_dom_agreement(redfin_dom, source_doms, weight_map)
    result.garage_agreement = calculate_garage_agreement(redfin_garage, source_garages, weight_map)
    result.gas_agreement = calculate_gas_agreement(redfin_gas, source_gas, weight_map)

    # 3. Confidence metrics
    field_agreements = [
        fa for fa in [
            result.price_agreement, result.status_agreement, result.dom_agreement,
            result.garage_agreement, result.gas_agreement,
        ] if fa is not None
    ]
    result.confidence_metrics = calculate_cross_site_confidence_metrics(weights, field_agreements)

    # 4. Discrepancy severity
    result.discrepancy_severity = calculate_discrepancy_severity(
        redfin_price=redfin_price,
        redfin_status=redfin_status,
        redfin_dom=redfin_dom,
        redfin_garage=redfin_garage,
        redfin_gas=redfin_gas,
        source_data=observations,
        source_weights=weight_map,
    )

    # 5. Manual review priority
    result.cross_site_manual_review_priority = _determine_review_priority(
        result.discrepancy_severity, result.confidence_metrics
    )

    return result


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _get_redfin_property_data(
    property_id: int, database_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Get Redfin property data from watched_properties.

    Args:
        property_id: Property ID.
        database_path: Optional database path.

    Returns:
        Property data dict or None.
    """
    try:
        query = """
        SELECT property_id, address, city, zip,
               current_price, displayed_dom, garage_spaces, gas_service
        FROM watched_properties
        WHERE property_id = ?
        """
        results = execute_query(query, (property_id,), database_path=database_path)
        if results:
            return dict(results[0])
    except Exception as e:
        logger.error(f"Error getting Redfin data for property {property_id}: {e}")
    return None


def _get_full_cross_site_observations(
    property_id: int, database_path: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """Get latest cross-site observations with all fields.

    Args:
        property_id: Property ID.
        database_path: Optional database path.

    Returns:
        Mapping of source_site to observation data.
    """
    observations: Dict[str, Dict[str, Any]] = {}

    try:
        query = """
        SELECT source_site, price, beds, baths, sqft, displayed_dom,
               listing_status, garage_spaces, gas_service, gas_evidence,
               parse_status, parse_warnings, observed_at
        FROM cross_site_observations
        WHERE property_id = ?
        AND observed_at = (
            SELECT MAX(observed_at)
            FROM cross_site_observations
            WHERE property_id = ? AND source_site = cross_site_observations.source_site
        )
        ORDER BY source_site
        """
        results = execute_query(
            query, (property_id, property_id), database_path=database_path
        )
        for row in results:
            row_dict = dict(row)
            site = row_dict.pop("source_site")
            # Infer parse_confidence from parse_status heuristically
            parse_status = row_dict.get("parse_status", "success")
            if parse_status == "success":
                row_dict["parse_confidence"] = "high"
            elif parse_status == "partial":
                row_dict["parse_confidence"] = "medium"
            elif parse_status == "failed":
                row_dict["parse_confidence"] = "low"
            else:
                row_dict["parse_confidence"] = "high"
            observations[site] = row_dict

    except Exception as e:
        logger.error(
            f"Error getting full cross-site observations for property {property_id}: {e}"
        )

    return observations
