"""Tests for scoring functionality."""

from datetime import date

import pytest

from marketsentry.models import CandidateProperty
from marketsentry.scoring import (
    calculate_data_confidence_score,
    calculate_effective_dom_leverage_score,
    calculate_property_fit_score,
    score_property,
)


def test_score_property_gatekeeper_pass() -> None:
    """Test property scoring when gatekeeper passes."""
    candidate = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="http://example.com",
        redfin_url="http://redfin.com/property/1",
        address="123 Main St",
        city="Temecula",
        zip="92592",
        quiet_score=8.5,
        vibrancy_score=2.0,
        gas_service=True,
        garage_spaces=2,
        beds=3,
        baths=2.0,
        sqft=1800,
        displayed_dom=30,
    )

    result = score_property(candidate)

    assert result.quiet_gatekeeper_result == "pass"
    assert result.location_fit_score is not None
    assert result.location_fit_score > 0
    assert result.overall_score is not None
    assert result.overall_score > 0


def test_score_property_gatekeeper_fail() -> None:
    """Test property scoring when gatekeeper fails."""
    candidate = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="http://example.com",
        redfin_url="http://redfin.com/property/1",
        address="123 Main St",
        city="Temecula",
        zip="92592",
        quiet_score=5.0,  # Below threshold
        vibrancy_score=5.0,
    )

    result = score_property(candidate)

    assert result.quiet_gatekeeper_result == "fail_noise_risk"
    assert result.location_fit_score == 0.0
    assert result.overall_score == 0.0


def test_calculate_property_fit_score_with_gas() -> None:
    """Test property fit score with gas service."""
    score = calculate_property_fit_score(
        gas_service=True, garage_spaces=2, beds=3, baths=2.5, sqft=2000
    )

    assert score is not None
    assert score >= 5.0


def test_calculate_property_fit_score_without_gas() -> None:
    """Test property fit score without gas service."""
    score = calculate_property_fit_score(
        gas_service=False, garage_spaces=2, beds=2, baths=2.0, sqft=1500
    )

    assert score is not None
    assert score >= 4.0


def test_calculate_property_fit_score_none_values() -> None:
    """Test property fit score with None values."""
    score = calculate_property_fit_score(
        gas_service=None, garage_spaces=None, beds=None, baths=None, sqft=None
    )

    assert score is not None
    assert score == 5.0  # Base score


def test_calculate_effective_dom_leverage_score_high_delta() -> None:
    """Test DOM leverage score with high delta."""
    score = calculate_effective_dom_leverage_score(
        effective_dom=150, displayed_dom=30, listing_churn_count=3
    )

    assert score is not None
    assert score >= 8.0


def test_calculate_effective_dom_leverage_score_low_delta() -> None:
    """Test DOM leverage score with low delta."""
    score = calculate_effective_dom_leverage_score(
        effective_dom=35, displayed_dom=30, listing_churn_count=0
    )

    assert score is not None
    assert score <= 4.0


def test_calculate_effective_dom_leverage_score_none() -> None:
    """Test DOM leverage score with None input."""
    score = calculate_effective_dom_leverage_score(
        effective_dom=None, displayed_dom=30, listing_churn_count=0
    )

    assert score is None


def test_calculate_data_confidence_score_complete() -> None:
    """Test data confidence score with complete data."""
    candidate = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="http://example.com",
        redfin_url="http://redfin.com/property/1",
        address="123 Main St",
        city="Temecula",
        zip="92592",
        quiet_score=8.5,
        vibrancy_score=2.0,
        displayed_dom=30,
        garage_spaces=2,
        gas_service=True,
        beds=3,
        baths=2.0,
        sqft=1800,
        price=750000.0,
    )

    score = calculate_data_confidence_score(candidate)

    assert score == 10.0  # All fields present


def test_calculate_data_confidence_score_partial() -> None:
    """Test data confidence score with partial data."""
    candidate = CandidateProperty(
        discovery_date=date.today(),
        source_site="redfin",
        source_search_url="http://example.com",
        redfin_url="http://redfin.com/property/1",
        address="123 Main St",
        city="Temecula",
        zip="92592",
        quiet_score=8.5,
        # Missing most other fields
    )

    score = calculate_data_confidence_score(candidate)

    assert score < 10.0
    assert score >= 0.0
