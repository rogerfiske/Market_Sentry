"""Tests for Milestone 24: Confidence-Weighted Cross-Site Analytics."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from marketsentry.cross_site_analytics import (
    _determine_review_priority,
    _normalize_status_for_agreement,
    analyze_property_cross_site_metrics,
    calculate_cross_site_confidence_metrics,
    calculate_discrepancy_severity,
    calculate_dom_agreement,
    calculate_field_agreement,
    calculate_garage_agreement,
    calculate_gas_agreement,
    calculate_price_agreement,
    calculate_source_weight,
    calculate_status_agreement,
    completeness_to_weight,
    confidence_to_weight,
    freshness_to_weight,
)
from marketsentry.models import (
    CrossSiteAnalyticsReportRow,
    CrossSiteAnalyticsResult,
    CrossSiteConfidenceMetrics,
    CrossSiteDiscrepancySeverity,
    CrossSiteFieldAgreement,
    CrossSiteSourceWeight,
)


# ---------------------------------------------------------------------------
# Weight calculation tests
# ---------------------------------------------------------------------------


class TestConfidenceToWeight:
    """Tests for confidence_to_weight function."""

    def test_high_confidence(self):
        assert confidence_to_weight("high") == 1.0

    def test_medium_confidence(self):
        assert confidence_to_weight("medium") == 0.7

    def test_low_confidence(self):
        assert confidence_to_weight("low") == 0.4

    def test_none_confidence(self):
        assert confidence_to_weight(None) == 0.4

    def test_unknown_string(self):
        assert confidence_to_weight("unknown") == 0.4

    def test_case_insensitive(self):
        assert confidence_to_weight("HIGH") == 1.0
        assert confidence_to_weight("Medium") == 0.7


class TestFreshnessToWeight:
    """Tests for freshness_to_weight function."""

    def test_recent_observation(self):
        now = datetime.now()
        observed = now - timedelta(days=3)
        assert freshness_to_weight(observed, now) == 1.0

    def test_week_old(self):
        now = datetime.now()
        observed = now - timedelta(days=7)
        assert freshness_to_weight(observed, now) == 1.0

    def test_two_weeks_old(self):
        now = datetime.now()
        observed = now - timedelta(days=14)
        assert freshness_to_weight(observed, now) == 0.8

    def test_month_old(self):
        now = datetime.now()
        observed = now - timedelta(days=30)
        assert freshness_to_weight(observed, now) == 0.8

    def test_two_months_old(self):
        now = datetime.now()
        observed = now - timedelta(days=60)
        assert freshness_to_weight(observed, now) == 0.5

    def test_very_old(self):
        now = datetime.now()
        observed = now - timedelta(days=120)
        assert freshness_to_weight(observed, now) == 0.2

    def test_none_observed_at(self):
        assert freshness_to_weight(None) == 0.2

    def test_string_timestamp(self):
        now = datetime.now()
        observed_str = (now - timedelta(days=3)).isoformat()
        assert freshness_to_weight(observed_str, now) == 1.0

    def test_invalid_string_timestamp(self):
        assert freshness_to_weight("not-a-date") == 0.2


class TestCompletenessToWeight:
    """Tests for completeness_to_weight function."""

    def test_all_fields_present(self):
        obs = {"price": 500000, "listing_status": "active", "beds": 3, "baths": 2, "sqft": 1800}
        assert completeness_to_weight(obs) == 1.0

    def test_some_fields_missing(self):
        obs = {"price": 500000, "listing_status": "active", "beds": 3}
        assert completeness_to_weight(obs) == 0.6

    def test_no_fields(self):
        obs = {}
        assert completeness_to_weight(obs) == 0.0

    def test_one_field(self):
        obs = {"price": 500000}
        assert completeness_to_weight(obs) == 0.2

    def test_none_values_not_counted(self):
        obs = {"price": None, "listing_status": "active", "beds": 3, "baths": None, "sqft": None}
        assert completeness_to_weight(obs) == 0.4


class TestCalculateSourceWeight:
    """Tests for calculate_source_weight function."""

    def test_high_confidence_recent_complete(self):
        now = datetime.now()
        obs = {
            "source_site": "zillow",
            "price": 500000,
            "listing_status": "active",
            "beds": 3,
            "baths": 2,
            "sqft": 1800,
        }
        sw = calculate_source_weight("high", "success", now - timedelta(days=1), obs, now)
        assert sw.confidence_weight == 1.0
        assert sw.freshness_weight == 1.0
        assert sw.completeness_weight == 1.0
        assert sw.combined_weight == 1.0
        assert not sw.is_stale
        assert not sw.is_low_confidence

    def test_failed_parse_zero_weight(self):
        now = datetime.now()
        obs = {"source_site": "zillow", "price": 500000}
        sw = calculate_source_weight("high", "failed", now, obs, now)
        assert sw.combined_weight == 0.0
        assert sw.is_stale
        assert sw.is_low_confidence

    def test_low_confidence_stale(self):
        now = datetime.now()
        obs = {
            "source_site": "realtor",
            "price": 500000,
            "listing_status": "active",
        }
        sw = calculate_source_weight("low", "partial", now - timedelta(days=60), obs, now)
        assert sw.confidence_weight == 0.4
        assert sw.freshness_weight == 0.5
        assert sw.is_stale
        assert sw.is_low_confidence

    def test_parse_warnings_tracked(self):
        now = datetime.now()
        obs = {"source_site": "homes", "price": 500000, "parse_warnings": "missing sqft"}
        sw = calculate_source_weight("medium", "success", now, obs, now)
        assert sw.has_parse_warnings


# ---------------------------------------------------------------------------
# Field agreement tests
# ---------------------------------------------------------------------------


class TestCalculateFieldAgreement:
    """Tests for field agreement calculation."""

    def test_all_agree(self):
        fa = calculate_field_agreement(
            "price", 500000,
            {"zillow": 505000, "realtor": 498000},
            {"zillow": 1.0, "realtor": 1.0},
            tolerance=10000,
        )
        assert fa.agreement_score == 1.0
        assert fa.contributing_sources == 2
        assert fa.agreeing_sources == 2

    def test_one_disagrees(self):
        fa = calculate_field_agreement(
            "price", 500000,
            {"zillow": 505000, "realtor": 600000},
            {"zillow": 1.0, "realtor": 1.0},
            tolerance=10000,
        )
        assert fa.agreement_score == 0.5
        assert fa.agreeing_sources == 1

    def test_no_redfin_baseline(self):
        fa = calculate_field_agreement(
            "price", None,
            {"zillow": 505000},
            {"zillow": 1.0},
            tolerance=10000,
        )
        assert fa.agreement_score == 0.0
        assert fa.contributing_sources == 1

    def test_empty_sources(self):
        fa = calculate_field_agreement(
            "price", 500000, {}, {}, tolerance=10000,
        )
        assert fa.agreement_score == 0.0
        assert fa.contributing_sources == 0

    def test_zero_weight_excluded(self):
        fa = calculate_field_agreement(
            "price", 500000,
            {"zillow": 505000, "realtor": 498000},
            {"zillow": 1.0, "realtor": 0.0},
            tolerance=10000,
        )
        assert fa.contributing_sources == 1


class TestCalculatePriceAgreement:
    """Tests for price agreement calculation."""

    def test_high_confidence_sources_agree(self):
        fa = calculate_price_agreement(
            750000,
            {"zillow": 755000, "realtor": 748000, "homes": 750000},
            {"zillow": 1.0, "realtor": 1.0, "homes": 1.0},
        )
        assert fa.agreement_score == 1.0
        assert fa.contributing_sources == 3

    def test_low_confidence_source_downweighted(self):
        fa = calculate_price_agreement(
            750000,
            {"zillow": 755000, "realtor": 820000},
            {"zillow": 1.0, "realtor": 0.4},
        )
        # zillow agrees (within 10k), realtor disagrees
        # agreeing_weight = 1.0, total_weight = 1.4
        expected = round(1.0 / 1.4, 4)
        assert fa.agreement_score == expected
        assert fa.agreeing_sources == 1


class TestCalculateStatusAgreement:
    """Tests for status agreement calculation."""

    def test_all_active(self):
        fa = calculate_status_agreement(
            "active",
            {"zillow": "for_sale", "realtor": "Active"},
            {"zillow": 1.0, "realtor": 1.0},
        )
        assert fa.agreement_score == 1.0

    def test_status_conflict(self):
        fa = calculate_status_agreement(
            "active",
            {"zillow": "active", "realtor": "sold"},
            {"zillow": 1.0, "realtor": 1.0},
        )
        assert fa.agreement_score == 0.5


class TestCalculateDomAgreement:
    """Tests for DOM agreement calculation."""

    def test_close_doms_agree(self):
        fa = calculate_dom_agreement(
            45,
            {"zillow": 42, "realtor": 48},
            {"zillow": 1.0, "realtor": 1.0},
        )
        assert fa.agreement_score == 1.0

    def test_large_dom_difference(self):
        fa = calculate_dom_agreement(
            45,
            {"zillow": 42, "realtor": 120},
            {"zillow": 1.0, "realtor": 1.0},
        )
        assert fa.agreement_score == 0.5


class TestCalculateGarageAgreement:
    """Tests for garage agreement calculation."""

    def test_matching_garages(self):
        fa = calculate_garage_agreement(
            2, {"zillow": 2, "realtor": 2}, {"zillow": 1.0, "realtor": 1.0},
        )
        assert fa.agreement_score == 1.0

    def test_different_garages(self):
        fa = calculate_garage_agreement(
            2, {"zillow": 3}, {"zillow": 1.0},
        )
        assert fa.agreement_score == 0.0


class TestCalculateGasAgreement:
    """Tests for gas agreement calculation."""

    def test_matching_gas(self):
        fa = calculate_gas_agreement(
            True, {"zillow": True, "realtor": True}, {"zillow": 1.0, "realtor": 1.0},
        )
        assert fa.agreement_score == 1.0

    def test_gas_disagreement(self):
        fa = calculate_gas_agreement(
            True, {"zillow": True, "realtor": False}, {"zillow": 1.0, "realtor": 1.0},
        )
        assert fa.agreement_score == 0.5


# ---------------------------------------------------------------------------
# Confidence metrics tests
# ---------------------------------------------------------------------------


class TestCalculateCrossSiteConfidenceMetrics:
    """Tests for aggregated confidence metrics."""

    def test_high_confidence_metrics(self):
        weights = [
            CrossSiteSourceWeight(
                source_site="zillow", confidence_weight=1.0,
                freshness_weight=1.0, completeness_weight=1.0, combined_weight=1.0,
            ),
            CrossSiteSourceWeight(
                source_site="realtor", confidence_weight=1.0,
                freshness_weight=1.0, completeness_weight=1.0, combined_weight=1.0,
            ),
        ]
        agreements = [
            CrossSiteFieldAgreement(
                field_name="price", agreement_score=1.0, contributing_sources=2,
            ),
            CrossSiteFieldAgreement(
                field_name="status", agreement_score=1.0, contributing_sources=2,
            ),
        ]
        cm = calculate_cross_site_confidence_metrics(weights, agreements)
        assert cm.source_freshness_score == 1.0
        assert cm.source_completeness_score == 1.0
        assert cm.source_agreement_score == 1.0
        assert cm.overall_cross_site_confidence_score == 1.0
        assert len(cm.contributing_sources) == 2

    def test_mixed_confidence_metrics(self):
        weights = [
            CrossSiteSourceWeight(
                source_site="zillow", confidence_weight=1.0,
                freshness_weight=1.0, completeness_weight=1.0, combined_weight=1.0,
            ),
            CrossSiteSourceWeight(
                source_site="realtor", confidence_weight=0.4,
                freshness_weight=0.5, completeness_weight=0.4, combined_weight=0.08,
                is_low_confidence=True, is_stale=True,
            ),
        ]
        agreements = [
            CrossSiteFieldAgreement(
                field_name="price", agreement_score=0.5, contributing_sources=2,
            ),
        ]
        cm = calculate_cross_site_confidence_metrics(weights, agreements)
        assert cm.overall_cross_site_confidence_score < 1.0
        assert "realtor" in cm.low_confidence_sources
        assert "realtor" in cm.stale_sources

    def test_no_contributing_sources(self):
        weights = [
            CrossSiteSourceWeight(
                source_site="zillow", combined_weight=0.0,
            ),
        ]
        cm = calculate_cross_site_confidence_metrics(weights, [])
        assert cm.source_freshness_score == 0.0
        assert cm.overall_cross_site_confidence_score == 0.0

    def test_overall_score_formula(self):
        """Verify the 25/25/50 weighting formula."""
        weights = [
            CrossSiteSourceWeight(
                source_site="zillow", confidence_weight=1.0,
                freshness_weight=0.8, completeness_weight=0.6, combined_weight=0.48,
            ),
        ]
        agreements = [
            CrossSiteFieldAgreement(
                field_name="price", agreement_score=0.5, contributing_sources=1,
            ),
        ]
        cm = calculate_cross_site_confidence_metrics(weights, agreements)
        expected = round(0.8 * 0.25 + 0.6 * 0.25 + 0.5 * 0.50, 4)
        assert cm.overall_cross_site_confidence_score == expected


# ---------------------------------------------------------------------------
# Discrepancy severity tests
# ---------------------------------------------------------------------------


class TestCalculateDiscrepancySeverity:
    """Tests for discrepancy severity scoring."""

    def test_no_discrepancy(self):
        sev = calculate_discrepancy_severity(
            redfin_price=500000, redfin_status="active", redfin_dom=30,
            redfin_garage=2, redfin_gas=True,
            source_data={
                "zillow": {"price": 505000, "listing_status": "active",
                           "displayed_dom": 28, "garage_spaces": 2, "gas_service": True},
            },
            source_weights={"zillow": 1.0},
        )
        assert sev.severity_label == "none"
        assert sev.severity_score == 0.0

    def test_price_discrepancy_low(self):
        sev = calculate_discrepancy_severity(
            redfin_price=500000, redfin_status=None, redfin_dom=None,
            redfin_garage=None, redfin_gas=None,
            source_data={"zillow": {"price": 515000}},
            source_weights={"zillow": 1.0},
        )
        assert sev.price_severity == "low"
        assert "price_discrepancy" in sev.flags

    def test_price_discrepancy_medium(self):
        sev = calculate_discrepancy_severity(
            redfin_price=500000, redfin_status=None, redfin_dom=None,
            redfin_garage=None, redfin_gas=None,
            source_data={"zillow": {"price": 530000}},
            source_weights={"zillow": 1.0},
        )
        assert sev.price_severity == "medium"

    def test_price_discrepancy_high(self):
        sev = calculate_discrepancy_severity(
            redfin_price=500000, redfin_status=None, redfin_dom=None,
            redfin_garage=None, redfin_gas=None,
            source_data={"zillow": {"price": 560000}},
            source_weights={"zillow": 1.0},
        )
        assert sev.price_severity == "high"

    def test_status_conflict_severity(self):
        sev = calculate_discrepancy_severity(
            redfin_price=None, redfin_status="active", redfin_dom=None,
            redfin_garage=None, redfin_gas=None,
            source_data={"zillow": {"listing_status": "sold"}},
            source_weights={"zillow": 1.0},
        )
        assert sev.status_severity == "high"
        assert "status_discrepancy" in sev.flags

    def test_dom_discrepancy_severity(self):
        sev = calculate_discrepancy_severity(
            redfin_price=None, redfin_status=None, redfin_dom=30,
            redfin_garage=None, redfin_gas=None,
            source_data={"zillow": {"displayed_dom": 130}},
            source_weights={"zillow": 1.0},
        )
        assert sev.dom_severity == "high"
        assert "dom_discrepancy" in sev.flags

    def test_gas_disagreement(self):
        sev = calculate_discrepancy_severity(
            redfin_price=None, redfin_status=None, redfin_dom=None,
            redfin_garage=None, redfin_gas=True,
            source_data={"zillow": {"gas_service": False}},
            source_weights={"zillow": 1.0},
        )
        assert sev.gas_severity == "low"
        assert "gas_disagreement" in sev.flags

    def test_garage_disagreement(self):
        sev = calculate_discrepancy_severity(
            redfin_price=None, redfin_status=None, redfin_dom=None,
            redfin_garage=2, redfin_gas=None,
            source_data={"zillow": {"garage_spaces": 3}},
            source_weights={"zillow": 1.0},
        )
        assert sev.garage_severity == "low"
        assert "garage_disagreement" in sev.flags

    def test_low_confidence_reduces_severity(self):
        """Low-confidence source should reduce severity, not exaggerate it."""
        sev_high = calculate_discrepancy_severity(
            redfin_price=500000, redfin_status=None, redfin_dom=None,
            redfin_garage=None, redfin_gas=None,
            source_data={"zillow": {"price": 560000}},
            source_weights={"zillow": 1.0},
        )
        sev_low = calculate_discrepancy_severity(
            redfin_price=500000, redfin_status=None, redfin_dom=None,
            redfin_garage=None, redfin_gas=None,
            source_data={"zillow": {"price": 560000}},
            source_weights={"zillow": 0.2},
        )
        sev_rank = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        assert sev_rank[sev_low.price_severity] <= sev_rank[sev_high.price_severity]

    def test_low_confidence_source_flag(self):
        sev = calculate_discrepancy_severity(
            redfin_price=None, redfin_status=None, redfin_dom=None,
            redfin_garage=None, redfin_gas=None,
            source_data={"zillow": {}},
            source_weights={"zillow": 0.3},
        )
        assert "low_confidence_source" in sev.flags

    def test_failed_parse_excluded(self):
        sev = calculate_discrepancy_severity(
            redfin_price=500000, redfin_status=None, redfin_dom=None,
            redfin_garage=None, redfin_gas=None,
            source_data={"zillow": {"price": 999999}},
            source_weights={"zillow": 0.0},
        )
        assert sev.price_severity == "none"


# ---------------------------------------------------------------------------
# Manual review priority tests
# ---------------------------------------------------------------------------


class TestManualReviewPriority:
    """Tests for manual review priority determination."""

    def test_no_discrepancy_no_issues(self):
        sev = CrossSiteDiscrepancySeverity(severity_label="none")
        cm = CrossSiteConfidenceMetrics()
        assert _determine_review_priority(sev, cm) == "none"

    def test_high_severity_high_priority(self):
        sev = CrossSiteDiscrepancySeverity(severity_label="high")
        cm = CrossSiteConfidenceMetrics()
        assert _determine_review_priority(sev, cm) == "high"

    def test_medium_severity_medium_priority(self):
        sev = CrossSiteDiscrepancySeverity(severity_label="medium")
        cm = CrossSiteConfidenceMetrics()
        assert _determine_review_priority(sev, cm) == "medium"

    def test_low_severity_low_priority(self):
        sev = CrossSiteDiscrepancySeverity(severity_label="low")
        cm = CrossSiteConfidenceMetrics()
        assert _determine_review_priority(sev, cm) == "low"

    def test_low_severity_with_low_confidence_becomes_medium(self):
        sev = CrossSiteDiscrepancySeverity(severity_label="low")
        cm = CrossSiteConfidenceMetrics(low_confidence_sources=["zillow"])
        assert _determine_review_priority(sev, cm) == "medium"

    def test_no_discrepancy_stale_sources_low_priority(self):
        sev = CrossSiteDiscrepancySeverity(severity_label="none")
        cm = CrossSiteConfidenceMetrics(stale_sources=["zillow"])
        assert _determine_review_priority(sev, cm) == "low"


# ---------------------------------------------------------------------------
# Full analytics pipeline tests
# ---------------------------------------------------------------------------


class TestAnalyzePropertyCrossSiteMetrics:
    """Tests for the full analytics pipeline."""

    def test_full_pipeline_high_confidence(self):
        now = datetime.now()
        redfin = {
            "current_price": 750000,
            "displayed_dom": 30,
            "listing_status": "active",
            "garage_spaces": 2,
            "gas_service": True,
        }
        observations = {
            "zillow": {
                "price": 755000, "displayed_dom": 28, "listing_status": "for_sale",
                "garage_spaces": 2, "gas_service": True,
                "beds": 4, "baths": 3, "sqft": 2200,
                "parse_confidence": "high", "parse_status": "success",
                "observed_at": (now - timedelta(days=2)).isoformat(),
            },
            "realtor": {
                "price": 749000, "displayed_dom": 32, "listing_status": "active",
                "garage_spaces": 2, "gas_service": True,
                "beds": 4, "baths": 3, "sqft": 2200,
                "parse_confidence": "high", "parse_status": "success",
                "observed_at": (now - timedelta(days=1)).isoformat(),
            },
        }
        result = analyze_property_cross_site_metrics(1, redfin, observations, now)

        assert result.property_id == 1
        assert len(result.source_weights) == 2
        assert result.price_agreement is not None
        assert result.price_agreement.agreement_score == 1.0
        assert result.confidence_metrics is not None
        assert result.confidence_metrics.overall_cross_site_confidence_score > 0.5
        assert result.discrepancy_severity is not None
        assert result.discrepancy_severity.severity_label == "none"
        assert result.cross_site_manual_review_priority == "none"

    def test_pipeline_with_stale_low_confidence(self):
        now = datetime.now()
        redfin = {"current_price": 600000, "displayed_dom": 45}
        observations = {
            "zillow": {
                "price": 600000, "displayed_dom": 43,
                "listing_status": "active",
                "beds": 3, "baths": 2, "sqft": 1500,
                "parse_confidence": "low", "parse_status": "partial",
                "observed_at": (now - timedelta(days=100)).isoformat(),
            },
        }
        result = analyze_property_cross_site_metrics(1, redfin, observations, now)

        assert len(result.source_weights) == 1
        sw = result.source_weights[0]
        assert sw.is_stale
        assert sw.is_low_confidence
        assert sw.combined_weight < 0.5
        assert result.confidence_metrics.low_confidence_sources == ["zillow"]
        assert result.confidence_metrics.stale_sources == ["zillow"]

    def test_pipeline_with_no_observations(self):
        result = analyze_property_cross_site_metrics(1, {}, {})
        assert result.property_id == 1
        assert len(result.source_weights) == 0

    def test_pipeline_discrepancy_severity_propagated(self):
        now = datetime.now()
        redfin = {"current_price": 500000, "listing_status": "active"}
        observations = {
            "zillow": {
                "price": 600000, "listing_status": "sold",
                "beds": 3, "baths": 2, "sqft": 1500,
                "parse_confidence": "high", "parse_status": "success",
                "observed_at": now.isoformat(),
            },
        }
        result = analyze_property_cross_site_metrics(1, redfin, observations, now)
        assert result.discrepancy_severity.severity_label in ("high", "critical")
        assert result.cross_site_manual_review_priority == "high"


# ---------------------------------------------------------------------------
# Report and model tests
# ---------------------------------------------------------------------------


class TestCrossSiteAnalyticsModels:
    """Tests for analytics model fields."""

    def test_source_weight_defaults(self):
        sw = CrossSiteSourceWeight(source_site="test")
        assert sw.combined_weight == 1.0
        assert not sw.is_stale
        assert not sw.is_low_confidence

    def test_field_agreement_defaults(self):
        fa = CrossSiteFieldAgreement(field_name="test")
        assert fa.agreement_score == 0.0
        assert fa.contributing_sources == 0

    def test_confidence_metrics_defaults(self):
        cm = CrossSiteConfidenceMetrics()
        assert cm.overall_cross_site_confidence_score == 0.0
        assert cm.contributing_sources == []

    def test_discrepancy_severity_defaults(self):
        ds = CrossSiteDiscrepancySeverity()
        assert ds.severity_label == "none"
        assert ds.severity_score == 0.0

    def test_analytics_result_defaults(self):
        ar = CrossSiteAnalyticsResult(property_id=1)
        assert ar.cross_site_manual_review_priority == "none"

    def test_report_row_defaults(self):
        row = CrossSiteAnalyticsReportRow()
        assert row.property_id is None


class TestCrossSiteAnalyticsReport:
    """Tests for analytics report generation."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        from marketsentry.database import init_db
        init_db(db_path)

        yield db_path

        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def sample_property(self, temp_db):
        """Create a sample watched property with cross-site observations."""
        from marketsentry.database import execute_insert

        # Create watched property
        query = """
        INSERT INTO watched_properties (
            first_saved_date, normalized_address, address, city, zip,
            current_price, displayed_dom, active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = ("2026-05-01", "12345 TEST ST", "12345 Test St", "Temecula", "92592",
                  500000, 30, 1)
        execute_insert(query, params, database_path=temp_db)

        from marketsentry.database import execute_query
        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE normalized_address = ?",
            ("12345 TEST ST",), database_path=temp_db,
        )
        prop_id = result[0]["property_id"]

        # Create cross-site observations
        obs_query = """
        INSERT INTO cross_site_observations (
            property_id, source_site, source_url, price, beds, baths, sqft,
            listing_status, displayed_dom, garage_spaces, gas_service,
            parse_status, observed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        execute_insert(obs_query, (
            prop_id, "zillow", "https://zillow.com/test", 505000, 3, 2, 1800,
            "for_sale", 28, 2, True, "success", datetime.now().isoformat(),
        ), database_path=temp_db)
        execute_insert(obs_query, (
            prop_id, "realtor", "https://realtor.com/test", 498000, 3, 2, 1800,
            "active", 32, 2, True, "success", datetime.now().isoformat(),
        ), database_path=temp_db)

        return prop_id

    def test_report_generation(self, temp_db, sample_property):
        """Test that analytics report generates CSV."""
        from marketsentry.cross_site_analytics_report import (
            export_cross_site_analytics_report,
        )
        import csv

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            output_path = f.name

        try:
            result_path = export_cross_site_analytics_report(
                database_path=temp_db, output_path=output_path,
            )
            assert Path(result_path).exists()

            with open(result_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) >= 1
            row = rows[0]
            assert row["property_id"] == str(sample_property)
            assert row["address"] == "12345 Test St"
            assert row["overall_cross_site_confidence_score"] is not None
            assert row["discrepancy_severity_label"] is not None
            assert row["cross_site_manual_review_priority"] is not None
            # At least one contributing source should be present
            contributing = row["contributing_sources"] or ""
            assert len(contributing) > 0

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_report_empty_db(self, temp_db):
        """Test report with no properties."""
        from marketsentry.cross_site_analytics_report import (
            export_cross_site_analytics_report,
        )
        import csv

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            output_path = f.name

        try:
            result_path = export_cross_site_analytics_report(
                database_path=temp_db, output_path=output_path,
            )
            assert Path(result_path).exists()

            with open(result_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 0

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_dashboard_table_includes_analytics_fields(self, temp_db, sample_property):
        """Test that dashboard analytics table has expected columns."""
        from marketsentry.cross_site_analytics_report import (
            export_cross_site_analytics_report,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "cross_site_analytics_test.csv")
            export_cross_site_analytics_report(
                database_path=temp_db, output_path=output_path,
            )

            from marketsentry.dashboard import build_cross_site_analytics_table
            df = build_cross_site_analytics_table(tmpdir)

            assert not df.empty
            # Check that analytics columns are present
            expected_cols = [
                "overall_cross_site_confidence_score",
                "discrepancy_severity_label",
                "cross_site_manual_review_priority",
            ]
            for col in expected_cols:
                assert col in df.columns


# ---------------------------------------------------------------------------
# Database integration tests
# ---------------------------------------------------------------------------


class TestAnalyzeCrossSiteObservations:
    """Tests for database-backed analysis."""

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        from marketsentry.database import init_db
        init_db(db_path)
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def prop_with_obs(self, temp_db):
        from marketsentry.database import execute_insert, execute_query
        query = """
        INSERT INTO watched_properties (
            first_saved_date, normalized_address, address, city, zip,
            current_price, displayed_dom, garage_spaces, gas_service,
            active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        execute_insert(query, (
            "2026-05-01", "99999 ANALYTICS DR", "99999 Analytics Dr",
            "Temecula", "92592", 700000, 45, 3, True, 1,
        ), database_path=temp_db)

        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE normalized_address = ?",
            ("99999 ANALYTICS DR",), database_path=temp_db,
        )
        prop_id = result[0]["property_id"]

        obs_query = """
        INSERT INTO cross_site_observations (
            property_id, source_site, source_url, price, beds, baths, sqft,
            listing_status, displayed_dom, garage_spaces, gas_service,
            parse_status, observed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        now = datetime.now()
        execute_insert(obs_query, (
            prop_id, "zillow", "https://zillow.com/x", 705000, 4, 3, 2200,
            "for_sale", 43, 3, True, "success", now.isoformat(),
        ), database_path=temp_db)
        execute_insert(obs_query, (
            prop_id, "homes", "https://homes.com/x", 695000, 4, 3, 2200,
            "active", 47, 3, True, "success", now.isoformat(),
        ), database_path=temp_db)

        return prop_id

    def test_analyze_from_database(self, temp_db, prop_with_obs):
        from marketsentry.cross_site_analytics import analyze_cross_site_observations
        result = analyze_cross_site_observations(prop_with_obs, temp_db)

        assert result.property_id == prop_with_obs
        assert result.address == "99999 Analytics Dr"
        assert len(result.source_weights) == 2
        assert result.confidence_metrics is not None
        assert result.discrepancy_severity is not None

    def test_analyze_no_observations(self, temp_db):
        from marketsentry.database import execute_insert, execute_query
        query = """
        INSERT INTO watched_properties (
            first_saved_date, normalized_address, address, city, zip,
            active_watch_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        execute_insert(query, (
            "2026-05-01", "00000 EMPTY ST", "00000 Empty St",
            "Temecula", "92592", 1,
        ), database_path=temp_db)
        result = execute_query(
            "SELECT property_id FROM watched_properties WHERE normalized_address = ?",
            ("00000 EMPTY ST",), database_path=temp_db,
        )
        prop_id = result[0]["property_id"]

        from marketsentry.cross_site_analytics import analyze_cross_site_observations
        analytics = analyze_cross_site_observations(prop_id, temp_db)
        assert analytics.property_id == prop_id
        assert len(analytics.source_weights) == 0


# ---------------------------------------------------------------------------
# Invariant tests
# ---------------------------------------------------------------------------


class TestNoRedfinOverwrite:
    """Confirm cross-site analytics does not overwrite Redfin fields."""

    def test_analytics_does_not_modify_database(self):
        """Analytics module has no INSERT/UPDATE/DELETE operations."""
        import inspect
        from marketsentry import cross_site_analytics

        source = inspect.getsource(cross_site_analytics)
        # Should only have SELECT queries, no writes
        assert "INSERT" not in source.upper().split("SELECT")[0]
        assert "UPDATE" not in source
        assert "DELETE" not in source

    def test_redfin_data_read_only(self):
        """The Redfin query is a SELECT only."""
        import inspect
        from marketsentry.cross_site_analytics import _get_redfin_property_data

        source = inspect.getsource(_get_redfin_property_data)
        assert "SELECT" in source
        assert "INSERT" not in source
        assert "UPDATE" not in source


class TestQuietGatekeeperUnchanged:
    """Confirm Quiet Score gatekeeper is not modified."""

    def test_scoring_module_unchanged(self):
        """Scoring module should not import cross_site_analytics."""
        import inspect
        from marketsentry import scoring

        source = inspect.getsource(scoring)
        assert "cross_site_analytics" not in source

    def test_quiet_gatekeeper_logic_intact(self):
        """Quiet gatekeeper thresholds remain unchanged."""
        from marketsentry.quiet_vibrancy import apply_quiet_gatekeeper

        # Quiet score < 7.0 should fail
        result, _ = apply_quiet_gatekeeper(6.5, 2.0)
        assert result == "fail_noise_risk"

        # Quiet score >= 7.0 should pass
        result, _ = apply_quiet_gatekeeper(8.0, 2.0)
        assert result == "pass"


class TestNoWalkabilityFields:
    """Confirm no walkability fields were added."""

    def test_no_walkability_in_analytics_models(self):
        fields = set(CrossSiteAnalyticsResult.model_fields.keys())
        walkability_terms = {"walk_score", "transit_score", "bike_score", "walkability"}
        assert not fields & walkability_terms

    def test_no_walkability_in_report_row(self):
        fields = set(CrossSiteAnalyticsReportRow.model_fields.keys())
        walkability_terms = {"walk_score", "transit_score", "bike_score", "walkability"}
        assert not fields & walkability_terms


class TestNoNetworkCalls:
    """Confirm no real network calls in the analytics module."""

    def test_no_network_imports(self):
        import inspect
        from marketsentry import cross_site_analytics

        source = inspect.getsource(cross_site_analytics)
        assert "requests" not in source
        assert "httpx" not in source
        assert "urllib.request" not in source
        assert "playwright" not in source.lower()
        assert "selenium" not in source.lower()


class TestStatusNormalization:
    """Tests for status normalization in analytics."""

    def test_active_variants(self):
        assert _normalize_status_for_agreement("active") == "active"
        assert _normalize_status_for_agreement("for_sale") == "active"
        assert _normalize_status_for_agreement("Active") == "active"
        assert _normalize_status_for_agreement("For Sale") == "active"

    def test_sold_variants(self):
        assert _normalize_status_for_agreement("sold") == "sold"
        assert _normalize_status_for_agreement("Sold") == "sold"

    def test_pending_variants(self):
        assert _normalize_status_for_agreement("pending") == "pending"
        assert _normalize_status_for_agreement("contingent") == "pending"

    def test_off_market(self):
        assert _normalize_status_for_agreement("off_market") == "off_market"
        assert _normalize_status_for_agreement("Off Market") == "off_market"

    def test_none_returns_none(self):
        assert _normalize_status_for_agreement(None) is None
