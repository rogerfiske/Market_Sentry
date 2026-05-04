"""Tests for Quiet/Vibrancy scoring functionality."""

import pytest

from marketsentry.quiet_vibrancy import (
    apply_quiet_gatekeeper,
    calculate_location_fit_score,
    evaluate_location_fit,
)


def test_quiet_gatekeeper_pass() -> None:
    """Test quiet gatekeeper passes with good score."""
    result, reason = apply_quiet_gatekeeper(quiet_score=8.0, vibrancy_score=2.0)

    assert result == "pass"
    assert reason is None


def test_quiet_gatekeeper_fail_low_quiet() -> None:
    """Test quiet gatekeeper fails with low quiet score."""
    result, reason = apply_quiet_gatekeeper(quiet_score=6.0, vibrancy_score=1.0)

    assert result == "fail_noise_risk"
    assert reason is not None


def test_quiet_gatekeeper_fail_no_data() -> None:
    """Test quiet gatekeeper fails with no data."""
    result, reason = apply_quiet_gatekeeper(quiet_score=None, vibrancy_score=2.0)

    assert result == "fail_no_data"
    assert reason is not None


def test_quiet_gatekeeper_vibrancy_irrelevant() -> None:
    """Test that low vibrancy doesn't override low quiet score."""
    result, reason = apply_quiet_gatekeeper(quiet_score=5.0, vibrancy_score=0.5)

    assert result == "fail_noise_risk"


def test_evaluate_location_fit_excellent() -> None:
    """Test excellent location fit evaluation."""
    fit_level, score = evaluate_location_fit(quiet_score=9.5, vibrancy_score=1.5)

    assert fit_level == "excellent"
    assert score is not None
    assert score >= 9.0


def test_evaluate_location_fit_target() -> None:
    """Test target location fit evaluation."""
    fit_level, score = evaluate_location_fit(quiet_score=8.5, vibrancy_score=2.0)

    assert fit_level == "target"
    assert score is not None
    assert 7.5 <= score <= 9.0


def test_evaluate_location_fit_acceptable() -> None:
    """Test acceptable location fit evaluation."""
    fit_level, score = evaluate_location_fit(quiet_score=7.5, vibrancy_score=3.0)

    assert fit_level == "acceptable"
    assert score is not None
    assert score >= 5.0


def test_evaluate_location_fit_poor() -> None:
    """Test poor location fit evaluation."""
    fit_level, score = evaluate_location_fit(quiet_score=5.0, vibrancy_score=5.0)

    assert fit_level == "poor"
    assert score == 0.0


def test_evaluate_location_fit_no_data() -> None:
    """Test location fit with no data."""
    fit_level, score = evaluate_location_fit(quiet_score=None, vibrancy_score=None)

    assert fit_level == "no_data"
    assert score is None


def test_calculate_location_fit_score() -> None:
    """Test location fit score calculation."""
    score = calculate_location_fit_score(quiet_score=8.5, vibrancy_score=2.0)

    assert score is not None
    assert 0.0 <= score <= 10.0


def test_calculate_location_fit_score_none() -> None:
    """Test location fit score with None input."""
    score = calculate_location_fit_score(quiet_score=None, vibrancy_score=2.0)

    assert score is None
