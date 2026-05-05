"""Tests for candidate scoring v1."""

import pytest

from marketsentry.models import CandidateProperty
from marketsentry.scoring import (
    calculate_data_confidence_score_v1,
    calculate_effective_dom_leverage_score_v1,
    calculate_property_fit_score,
    score_candidate,
)


class TestQuietGatekeeperScoring:
    """Tests for Quiet gatekeeper behavior in scoring."""

    def test_fail_noise_risk_low_quiet(self):
        """Test that low Quiet score fails gatekeeper."""
        candidate = CandidateProperty(
            candidate_id=1,
            quiet_score=6.0,  # Below 7.0 threshold
            vibrancy_score=1.0,  # Low vibrancy doesn't help
        )

        score = score_candidate(candidate)

        assert score.quiet_gatekeeper_result == "fail_noise_risk"
        assert score.location_fit_label == "fail_noise_risk"
        assert score.review_recommendation == "reject_location_noise"

    def test_low_vibrancy_cannot_override_poor_quiet(self):
        """Test critical rule: Low Vibrancy alone is not sufficient."""
        candidate = CandidateProperty(
            candidate_id=1,
            quiet_score=6.5,  # Below threshold
            vibrancy_score=0.5,  # Very low vibrancy
        )

        score = score_candidate(candidate)

        # Must still fail despite very low vibrancy
        assert score.quiet_gatekeeper_result == "fail_noise_risk"
        assert score.review_recommendation == "reject_location_noise"

    def test_target_location_fit(self):
        """Test target location fit criteria."""
        candidate = CandidateProperty(
            candidate_id=1,
            quiet_score=8.5,  # >= 8.0
            vibrancy_score=2.0,  # <= 2.5
        )

        score = score_candidate(candidate)

        assert score.location_fit_label == "target_location_fit"
        assert score.location_fit_score == 85.0

    def test_excellent_location_fit(self):
        """Test excellent location fit criteria."""
        candidate = CandidateProperty(
            candidate_id=1,
            quiet_score=9.5,  # >= 9.0
            vibrancy_score=1.0,  # <= 2.0
        )

        score = score_candidate(candidate)

        assert score.location_fit_label == "excellent_location_fit"
        assert score.location_fit_score == 100.0

    def test_needs_manual_location_review(self):
        """Test missing Quiet score triggers manual review need."""
        candidate = CandidateProperty(
            candidate_id=1,
            quiet_score=None,
            vibrancy_score=None,
        )

        score = score_candidate(candidate)

        assert score.location_fit_label == "needs_manual_location_review"
        assert score.location_fit_score == 40.0


class TestPropertyFitScoring:
    """Tests for property fit score calculation."""

    def test_gas_service_positive(self):
        """Test that gas service increases score significantly."""
        score_with_gas = calculate_property_fit_score(
            gas_service=True,
            garage_spaces=2,
            price=750000,
            beds=3,
            baths=2.5,
            sqft=2100,
        )

        score_without_gas = calculate_property_fit_score(
            gas_service=False,
            garage_spaces=2,
            price=750000,
            beds=3,
            baths=2.5,
            sqft=2100,
        )

        assert score_with_gas > score_without_gas
        # Gas service adds 20 points, no gas removes 10
        assert score_with_gas - score_without_gas == 30.0

    def test_garage_spaces_positive(self):
        """Test that 2+ garage spaces is positive."""
        score_two_garage = calculate_property_fit_score(
            gas_service=None,
            garage_spaces=2,
            price=750000,
            beds=3,
            baths=2.5,
            sqft=2100,
        )

        score_three_garage = calculate_property_fit_score(
            gas_service=None,
            garage_spaces=3,
            price=750000,
            beds=3,
            baths=2.5,
            sqft=2100,
        )

        assert score_two_garage is not None
        assert score_three_garage > score_two_garage

    def test_price_within_range_positive(self):
        """Test that price within $550k-$990k is positive."""
        score_in_range = calculate_property_fit_score(
            gas_service=None,
            garage_spaces=None,
            price=750000,  # Within range
            beds=None,
            baths=None,
            sqft=None,
        )

        score_below_range = calculate_property_fit_score(
            gas_service=None,
            garage_spaces=None,
            price=500000,  # Below range
            beds=None,
            baths=None,
            sqft=None,
        )

        assert score_in_range > score_below_range

    def test_missing_fields_reduce_score(self):
        """Test that missing fields don't crash but affect score."""
        score = calculate_property_fit_score(
            gas_service=None,
            garage_spaces=None,
            price=None,
            beds=None,
            baths=None,
            sqft=None,
        )

        # Should still return a score (base score)
        assert score is not None
        assert score == 50.0  # Base score when nothing is set


class TestEffectiveDOMLeverageScoring:
    """Tests for Effective DOM leverage score calculation."""

    def test_high_dom_delta_positive(self):
        """Test that effective_dom_delta >= 90 is a positive signal."""
        score_high_delta = calculate_effective_dom_leverage_score_v1(
            effective_dom=135,
            displayed_dom=45,  # Delta = 90
            listing_churn_count=0,
            dom_reset_count=0,
            sale_rent_alternation_count=0,
            price_change_count=0,
        )

        score_low_delta = calculate_effective_dom_leverage_score_v1(
            effective_dom=60,
            displayed_dom=45,  # Delta = 15
            listing_churn_count=0,
            dom_reset_count=0,
            sale_rent_alternation_count=0,
            price_change_count=0,
        )

        assert score_high_delta > score_low_delta

    def test_dom_reset_count_positive(self):
        """Test that dom_reset_count >= 1 is a positive signal."""
        score_with_resets = calculate_effective_dom_leverage_score_v1(
            effective_dom=100,
            displayed_dom=45,
            listing_churn_count=0,
            dom_reset_count=2,  # Has resets
            sale_rent_alternation_count=0,
            price_change_count=0,
        )

        score_no_resets = calculate_effective_dom_leverage_score_v1(
            effective_dom=100,
            displayed_dom=45,
            listing_churn_count=0,
            dom_reset_count=0,
            sale_rent_alternation_count=0,
            price_change_count=0,
        )

        assert score_with_resets > score_no_resets

    def test_listing_churn_count_positive(self):
        """Test that listing_churn_count >= 3 is a positive signal."""
        score_high_churn = calculate_effective_dom_leverage_score_v1(
            effective_dom=100,
            displayed_dom=45,
            listing_churn_count=5,  # High churn
            dom_reset_count=0,
            sale_rent_alternation_count=0,
            price_change_count=0,
        )

        score_low_churn = calculate_effective_dom_leverage_score_v1(
            effective_dom=100,
            displayed_dom=45,
            listing_churn_count=2,  # Below threshold
            dom_reset_count=0,
            sale_rent_alternation_count=0,
            price_change_count=0,
        )

        assert score_high_churn > score_low_churn

    def test_sale_rent_alternation_positive(self):
        """Test that sale_rent_alternation_count >= 1 is a positive signal."""
        score_with_alternation = calculate_effective_dom_leverage_score_v1(
            effective_dom=100,
            displayed_dom=45,
            listing_churn_count=0,
            dom_reset_count=0,
            sale_rent_alternation_count=1,
            price_change_count=0,
        )

        score_no_alternation = calculate_effective_dom_leverage_score_v1(
            effective_dom=100,
            displayed_dom=45,
            listing_churn_count=0,
            dom_reset_count=0,
            sale_rent_alternation_count=0,
            price_change_count=0,
        )

        assert score_with_alternation > score_no_alternation

    def test_price_change_count_positive(self):
        """Test that price_change_count >= 1 is a positive signal."""
        score_with_changes = calculate_effective_dom_leverage_score_v1(
            effective_dom=100,
            displayed_dom=45,
            listing_churn_count=0,
            dom_reset_count=0,
            sale_rent_alternation_count=0,
            price_change_count=2,
        )

        score_no_changes = calculate_effective_dom_leverage_score_v1(
            effective_dom=100,
            displayed_dom=45,
            listing_churn_count=0,
            dom_reset_count=0,
            sale_rent_alternation_count=0,
            price_change_count=0,
        )

        assert score_with_changes > score_no_changes

    def test_returns_none_without_dom_data(self):
        """Test that None is returned when DOM data is missing."""
        score = calculate_effective_dom_leverage_score_v1(
            effective_dom=None,
            displayed_dom=45,
            listing_churn_count=5,
            dom_reset_count=2,
            sale_rent_alternation_count=1,
            price_change_count=2,
        )

        assert score is None


class TestDataConfidenceScoring:
    """Tests for data confidence score calculation."""

    def test_all_fields_present_high_confidence(self):
        """Test that complete data yields high confidence."""
        candidate = CandidateProperty(
            candidate_id=1,
            redfin_url="https://www.redfin.com/test",
            address="123 Main St",
            price=750000.0,
            quiet_score=8.5,
            vibrancy_score=2.0,
            garage_spaces=2,
            gas_service=True,
            listing_churn_count=3,
            effective_dom_estimate=120,
        )

        score = calculate_data_confidence_score_v1(candidate)

        assert score >= 90.0  # Should be high with complete data

    def test_minimal_fields_low_confidence(self):
        """Test that minimal data yields low confidence."""
        candidate = CandidateProperty(
            candidate_id=1,
            # Only candidate_id set
        )

        score = calculate_data_confidence_score_v1(candidate)

        assert score < 50.0  # Should be low with minimal data


class TestCandidateScoringWarningFlags:
    """Tests for warning flag collection."""

    def test_warning_flag_low_quiet(self):
        """Test that low Quiet score generates warning flag."""
        candidate = CandidateProperty(
            candidate_id=1,
            quiet_score=6.0,
            vibrancy_score=2.0,
        )

        score = score_candidate(candidate)

        assert "low_quiet_score" in score.warning_flags
        assert "fail_quiet_gatekeeper" in score.warning_flags

    def test_warning_flag_no_gas(self):
        """Test that no gas service generates warning flag."""
        candidate = CandidateProperty(
            candidate_id=1,
            gas_service=False,
            quiet_score=8.5,
            vibrancy_score=2.0,
        )

        score = score_candidate(candidate)

        assert "no_gas_service" in score.warning_flags

    def test_warning_flag_missing_quiet(self):
        """Test that missing Quiet score generates warning flag."""
        candidate = CandidateProperty(
            candidate_id=1,
            quiet_score=None,
        )

        score = score_candidate(candidate)

        assert "missing_quiet_score" in score.warning_flags


class TestCandidateScoringPositiveFlags:
    """Tests for positive flag collection."""

    def test_positive_flag_excellent_location(self):
        """Test that excellent location generates positive flag."""
        candidate = CandidateProperty(
            candidate_id=1,
            quiet_score=9.5,
            vibrancy_score=1.0,
        )

        score = score_candidate(candidate)

        assert "excellent_location" in score.positive_flags

    def test_positive_flag_has_gas(self):
        """Test that gas service generates positive flag."""
        candidate = CandidateProperty(
            candidate_id=1,
            gas_service=True,
            quiet_score=8.5,
            vibrancy_score=2.0,
        )

        score = score_candidate(candidate)

        assert "has_gas_service" in score.positive_flags

    def test_positive_flag_high_dom_delta(self):
        """Test that high DOM delta generates positive flag."""
        candidate = CandidateProperty(
            candidate_id=1,
            displayed_dom=45,
            effective_dom_estimate=150,  # Delta = 105 (>= 90)
            quiet_score=8.5,
            vibrancy_score=2.0,
        )

        score = score_candidate(candidate)

        assert "high_dom_delta" in score.positive_flags

    def test_positive_flag_dom_resets(self):
        """Test that DOM resets generate positive flag."""
        candidate = CandidateProperty(
            candidate_id=1,
            dom_reset_count=2,
            quiet_score=8.5,
            vibrancy_score=2.0,
        )

        score = score_candidate(candidate)

        assert "has_dom_resets" in score.positive_flags

    def test_positive_flag_sale_rent_alternation(self):
        """Test that sale/rent alternation generates positive flag."""
        candidate = CandidateProperty(
            candidate_id=1,
            sale_rent_alternation_count=1,
            quiet_score=8.5,
            vibrancy_score=2.0,
        )

        score = score_candidate(candidate)

        assert "sale_rent_alternation" in score.positive_flags


class TestReviewRecommendation:
    """Tests for review recommendation determination."""

    def test_strong_review_high_score(self):
        """Test that high overall score yields strong_review."""
        candidate = CandidateProperty(
            candidate_id=1,
            quiet_score=9.5,
            vibrancy_score=1.0,
            gas_service=True,
            garage_spaces=3,
            price=750000.0,
            beds=3,
            baths=2.5,
            sqft=2200,
            effective_dom_estimate=150,
            displayed_dom=45,
            listing_churn_count=5,
            dom_reset_count=2,
        )

        score = score_candidate(candidate)

        assert score.review_recommendation == "strong_review"
        assert score.overall_review_score >= 80.0

    def test_review_good_score(self):
        """Test that good overall score yields review."""
        candidate = CandidateProperty(
            candidate_id=1,
            quiet_score=8.5,
            vibrancy_score=2.0,
            gas_service=True,
            garage_spaces=2,
            price=750000.0,
        )

        score = score_candidate(candidate)

        # Should be at least 'review' or 'strong_review'
        assert score.review_recommendation in ["review", "strong_review"]

    def test_reject_location_noise(self):
        """Test that failed gatekeeper yields reject_location_noise."""
        candidate = CandidateProperty(
            candidate_id=1,
            quiet_score=6.0,  # Fails gatekeeper
            vibrancy_score=2.0,
            gas_service=True,
            garage_spaces=3,
        )

        score = score_candidate(candidate)

        assert score.review_recommendation == "reject_location_noise"

    def test_needs_more_data_low_confidence(self):
        """Test that low data confidence yields needs_more_data."""
        candidate = CandidateProperty(
            candidate_id=1,
            # Minimal data
            address="123 Main St",
        )

        score = score_candidate(candidate)

        assert score.review_recommendation == "needs_more_data"


class TestScoringExplanation:
    """Tests for scoring explanation generation."""

    def test_explanation_includes_location(self):
        """Test that explanation includes location assessment."""
        candidate = CandidateProperty(
            candidate_id=1,
            quiet_score=8.5,
            vibrancy_score=2.0,
        )

        score = score_candidate(candidate)

        assert "target" in score.explanation.lower() or "location" in score.explanation.lower()

    def test_explanation_includes_recommendation(self):
        """Test that explanation includes recommendation."""
        candidate = CandidateProperty(
            candidate_id=1,
            quiet_score=9.5,
            vibrancy_score=1.0,
            gas_service=True,
        )

        score = score_candidate(candidate)

        assert "recommendation" in score.explanation.lower()
