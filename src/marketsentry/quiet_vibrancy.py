"""Quiet and Vibrancy scoring utilities."""

from typing import Optional, Tuple

from marketsentry.config import config


def apply_quiet_gatekeeper(
    quiet_score: Optional[float], vibrancy_score: Optional[float]
) -> Tuple[str, Optional[str]]:
    """
    Apply Quiet score gatekeeper rule.

    Critical domain rule: Quiet Score is the gatekeeper.
    Reject or heavily downgrade if Quiet Score is below threshold,
    even when Vibrancy is low.

    Args:
        quiet_score: Quiet score (higher is better, scale typically 0-10)
        vibrancy_score: Vibrancy score (lower is better, scale typically 0-10)

    Returns:
        Tuple of (gatekeeper_result: str, reason: Optional[str])
        Results: "pass", "fail_noise_risk", "fail_no_data"
    """
    # No data case
    if quiet_score is None:
        return "fail_no_data", "Quiet score not available"

    # Fail if quiet score below minimum threshold
    if quiet_score < config.quiet_score_minimum:
        return (
            "fail_noise_risk",
            f"Quiet score {quiet_score} below minimum threshold {config.quiet_score_minimum}",
        )

    # Pass the gatekeeper
    return "pass", None


def evaluate_location_fit(
    quiet_score: Optional[float], vibrancy_score: Optional[float]
) -> Tuple[str, Optional[float]]:
    """
    Evaluate location fit based on Quiet and Vibrancy scores.

    Target: Very high Quiet AND very low Vibrancy.
    Low Vibrancy alone is not sufficient.

    Args:
        quiet_score: Quiet score (higher is better)
        vibrancy_score: Vibrancy score (lower is better)

    Returns:
        Tuple of (fit_level: str, location_fit_score: Optional[float])
        Fit levels: "excellent", "target", "acceptable", "poor", "no_data"
    """
    # Check if data is available
    if quiet_score is None or vibrancy_score is None:
        return "no_data", None

    # Excellent location fit
    if (
        quiet_score >= config.quiet_score_excellent
        and vibrancy_score <= config.vibrancy_score_excellent_max
    ):
        # Score from 9.0-10.0 range
        location_score = 9.0 + min(1.0, (quiet_score - config.quiet_score_excellent))
        return "excellent", location_score

    # Target location fit
    if (
        quiet_score >= config.quiet_score_target
        and vibrancy_score <= config.vibrancy_score_target_max
    ):
        # Score from 7.5-9.0 range
        quiet_factor = (quiet_score - config.quiet_score_target) / (
            config.quiet_score_excellent - config.quiet_score_target
        )
        vibrancy_factor = 1.0 - (vibrancy_score / config.vibrancy_score_target_max)
        location_score = 7.5 + (1.5 * (quiet_factor + vibrancy_factor) / 2)
        return "target", location_score

    # Acceptable (passed gatekeeper but not target)
    if quiet_score >= config.quiet_score_minimum:
        # Score from 5.0-7.5 range
        quiet_factor = (quiet_score - config.quiet_score_minimum) / (
            config.quiet_score_target - config.quiet_score_minimum
        )
        location_score = 5.0 + (2.5 * quiet_factor)
        return "acceptable", location_score

    # Poor (failed gatekeeper)
    return "poor", 0.0


def calculate_location_fit_score(
    quiet_score: Optional[float], vibrancy_score: Optional[float]
) -> Optional[float]:
    """
    Calculate numeric location fit score.

    Args:
        quiet_score: Quiet score
        vibrancy_score: Vibrancy score

    Returns:
        Location fit score (0-10 scale) or None if no data
    """
    _, score = evaluate_location_fit(quiet_score, vibrancy_score)
    return score
