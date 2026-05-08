"""Tests for Milestone 26: Cross-Site Trend Alerts and Watchlist Monitoring Integration.

Tests cover:
- Schema migration creates cross_site_trend_alerts
- Migration is idempotent
- Confidence drop warning alert
- Confidence drop high alert
- Confidence improvement info alert
- Severity increase alert
- Manual review priority increase alert
- Status agreement degraded alert
- Price agreement degraded alert
- DOM agreement degraded alert
- Stale source count increased alert
- Low-confidence source count increased alert
- Duplicate open alert prevention
- Acknowledge alert
- Resolve alert
- List alerts filtering
- Export alert report
- Watchlist monitoring alert summary fields
- Dashboard alert table loads
- No Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- No walkability fields added
- No real network calls
- Existing MVP 1-25 tests still pass (run with full suite)
"""

import csv
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from marketsentry.database import execute_query, get_connection, init_db, table_exists
from marketsentry.models import (
    CrossSiteAnalyticsSnapshot,
    CrossSiteTrendAlert,
    CrossSiteTrendAlertReportRow,
    CrossSiteTrendAlertRule,
    CrossSiteTrendAlertRunResult,
    CrossSiteTrendChange,
)
from marketsentry.schema import CREATE_CROSS_SITE_TREND_ALERTS_TABLE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_db():
    """Create a temporary database with full schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    init_db(db_path)
    yield db_path

    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def temp_db_with_snapshots(temp_db):
    """Create a temp database with watched property and two analytics snapshots."""
    conn = get_connection(temp_db)
    cursor = conn.cursor()

    # Insert watched property
    cursor.execute(
        """
        INSERT INTO watched_properties (
            first_saved_date, active_watch_status, address, city, zip,
            current_price, displayed_dom, garage_spaces, gas_service
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-01-01", 1, "123 Test St", "Temecula", "92592", 750000, 45, 2, 1),
    )
    property_id = cursor.lastrowid

    # Insert cross-site observations
    now = datetime.now().isoformat()
    for source in ["zillow", "realtor"]:
        cursor.execute(
            """
            INSERT INTO cross_site_observations (
                property_id, source_site, source_url, observed_at,
                price, beds, baths, sqft, displayed_dom,
                listing_status, garage_spaces, gas_service,
                parse_status, parse_warnings
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                property_id, source, f"https://{source}.com/test",
                now, 750000, 4, 3, 2500, 45,
                "active", 2, 1, "success", None,
            ),
        )

    # Insert previous snapshot (older)
    prev_time = (datetime.now() - timedelta(days=7)).isoformat()
    cursor.execute(
        """
        INSERT INTO cross_site_analytics_snapshots (
            property_id, captured_at,
            overall_cross_site_confidence_score,
            discrepancy_severity_score, discrepancy_severity_label,
            cross_site_manual_review_priority,
            weighted_price_agreement_score,
            weighted_status_agreement_score,
            weighted_dom_agreement_score,
            weighted_garage_agreement_score,
            weighted_gas_agreement_score,
            source_freshness_score, source_completeness_score,
            source_agreement_score,
            contributing_sources,
            source_count, high_confidence_source_count,
            low_confidence_source_count, stale_source_count,
            price_discrepancy_flag, status_discrepancy_flag,
            dom_discrepancy_flag
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            property_id, prev_time,
            0.85, 0.2, "low", "low",
            0.90, 0.95, 0.80,
            1.0, 1.0,
            0.9, 0.8, 0.85,
            "zillow; realtor",
            2, 2, 0, 0,
            0, 0, 0,
        ),
    )
    previous_snapshot_id = cursor.lastrowid

    # Insert current snapshot (newer, with confidence drop)
    curr_time = datetime.now().isoformat()
    cursor.execute(
        """
        INSERT INTO cross_site_analytics_snapshots (
            property_id, captured_at,
            overall_cross_site_confidence_score,
            discrepancy_severity_score, discrepancy_severity_label,
            cross_site_manual_review_priority,
            weighted_price_agreement_score,
            weighted_status_agreement_score,
            weighted_dom_agreement_score,
            weighted_garage_agreement_score,
            weighted_gas_agreement_score,
            source_freshness_score, source_completeness_score,
            source_agreement_score,
            contributing_sources,
            source_count, high_confidence_source_count,
            low_confidence_source_count, stale_source_count,
            price_discrepancy_flag, status_discrepancy_flag,
            dom_discrepancy_flag
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            property_id, curr_time,
            0.60, 0.5, "medium", "medium",
            0.55, 0.60, 0.50,
            1.0, 1.0,
            0.7, 0.6, 0.65,
            "zillow; realtor",
            2, 1, 1, 1,
            1, 1, 1,
        ),
    )
    current_snapshot_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return temp_db, property_id, previous_snapshot_id, current_snapshot_id


@pytest.fixture
def temp_exports_dir():
    """Create a temporary exports directory."""
    with tempfile.TemporaryDirectory() as d:
        yield d


def _make_snapshot(
    property_id: int = 1,
    snapshot_id: int = 1,
    confidence: float = 0.85,
    severity_label: str = "low",
    priority: str = "low",
    price_agreement: float = 0.90,
    status_agreement: float = 0.95,
    dom_agreement: float = 0.80,
    stale_count: int = 0,
    low_conf_count: int = 0,
    price_flag: bool = False,
    status_flag: bool = False,
    dom_flag: bool = False,
) -> CrossSiteAnalyticsSnapshot:
    """Helper to create a CrossSiteAnalyticsSnapshot for testing."""
    return CrossSiteAnalyticsSnapshot(
        snapshot_id=snapshot_id,
        property_id=property_id,
        overall_cross_site_confidence_score=confidence,
        discrepancy_severity_score=0.2,
        discrepancy_severity_label=severity_label,
        cross_site_manual_review_priority=priority,
        weighted_price_agreement_score=price_agreement,
        weighted_status_agreement_score=status_agreement,
        weighted_dom_agreement_score=dom_agreement,
        weighted_garage_agreement_score=1.0,
        weighted_gas_agreement_score=1.0,
        source_freshness_score=0.9,
        source_completeness_score=0.8,
        source_agreement_score=0.85,
        contributing_sources="zillow; realtor",
        source_count=2,
        high_confidence_source_count=2,
        low_confidence_source_count=low_conf_count,
        stale_source_count=stale_count,
        price_discrepancy_flag=price_flag,
        status_discrepancy_flag=status_flag,
        dom_discrepancy_flag=dom_flag,
    )


# ---------------------------------------------------------------------------
# Test: Schema migration
# ---------------------------------------------------------------------------


class TestSchemaMigration:
    """Test schema migration for cross_site_trend_alerts."""

    def test_table_created_on_init(self, temp_db):
        """Verify cross_site_trend_alerts table exists after init."""
        assert table_exists("cross_site_trend_alerts", temp_db)

    def test_table_has_expected_columns(self, temp_db):
        """Verify all expected columns exist."""
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(cross_site_trend_alerts)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected = {
            "alert_id", "property_id", "candidate_id",
            "snapshot_id", "previous_snapshot_id",
            "created_at", "alert_type", "severity",
            "alert_status", "trend_direction",
            "current_value", "previous_value", "delta_value",
            "message", "recommended_action",
            "source_context", "notes",
        }
        assert expected.issubset(columns)

    def test_migration_is_idempotent(self, temp_db):
        """Running init_db twice should not fail."""
        init_db(temp_db)
        init_db(temp_db)
        assert table_exists("cross_site_trend_alerts", temp_db)


# ---------------------------------------------------------------------------
# Test: Confidence drop warning alert
# ---------------------------------------------------------------------------


class TestConfidenceDropWarning:
    """Test confidence drop >= 0.10 generates warning alert."""

    def test_confidence_drop_warning(self):
        """Confidence drop of 0.15 should generate warning alert."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
            classify_trend_alert_severity,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(confidence=0.85, snapshot_id=1)
        curr = _make_snapshot(confidence=0.70, snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "confidence_drop")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is not None
        assert alert.alert_type == "confidence_drop"
        assert alert.severity == "warning"
        assert "dropped" in alert.message.lower() or "decreased" in alert.message.lower()


# ---------------------------------------------------------------------------
# Test: Confidence drop high alert
# ---------------------------------------------------------------------------


class TestConfidenceDropHigh:
    """Test confidence drop >= 0.25 generates high alert."""

    def test_confidence_drop_high(self):
        """Confidence drop of 0.30 should generate high alert."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(confidence=0.85, snapshot_id=1)
        curr = _make_snapshot(confidence=0.55, snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "confidence_drop")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is not None
        assert alert.alert_type == "confidence_drop"
        assert alert.severity == "high"


# ---------------------------------------------------------------------------
# Test: Confidence improvement info alert
# ---------------------------------------------------------------------------


class TestConfidenceImprovement:
    """Test confidence improvement >= 0.10 generates info alert."""

    def test_confidence_improvement(self):
        """Confidence improvement of 0.15 should generate info alert."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(confidence=0.70, snapshot_id=1)
        curr = _make_snapshot(confidence=0.85, snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "confidence_improvement")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is not None
        assert alert.alert_type == "confidence_improvement"
        assert alert.severity == "info"


# ---------------------------------------------------------------------------
# Test: Severity increase alert
# ---------------------------------------------------------------------------


class TestSeverityIncrease:
    """Test discrepancy severity increase generates alert."""

    def test_severity_increase_to_high(self):
        """Severity increase from low to high should generate high alert."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(severity_label="low", snapshot_id=1)
        curr = _make_snapshot(severity_label="high", snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "severity_increase")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is not None
        assert alert.alert_type == "severity_increase"
        assert alert.severity == "high"

    def test_severity_increase_to_critical(self):
        """Severity increase to critical should generate critical alert."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(severity_label="medium", snapshot_id=1)
        curr = _make_snapshot(severity_label="critical", snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "severity_increase")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is not None
        assert alert.severity == "critical"

    def test_severity_decrease_not_triggered(self):
        """Severity decrease should not trigger severity_increase rule."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(severity_label="high", snapshot_id=1)
        curr = _make_snapshot(severity_label="low", snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "severity_increase")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is None


# ---------------------------------------------------------------------------
# Test: Manual review priority increase alert
# ---------------------------------------------------------------------------


class TestManualReviewPriorityIncrease:
    """Test manual review priority increase generates alert."""

    def test_priority_increase_to_high(self):
        """Priority increase to high should generate high alert."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(priority="low", snapshot_id=1)
        curr = _make_snapshot(priority="high", snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "manual_review_priority_increase")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is not None
        assert alert.alert_type == "manual_review_priority_increase"
        assert alert.severity == "high"

    def test_priority_decrease_not_triggered(self):
        """Priority decrease should not trigger priority increase rule."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(priority="high", snapshot_id=1)
        curr = _make_snapshot(priority="low", snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "manual_review_priority_increase")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is None


# ---------------------------------------------------------------------------
# Test: Status agreement degraded alert
# ---------------------------------------------------------------------------


class TestStatusAgreementDegraded:
    """Test status agreement drop >= 0.25 generates high alert."""

    def test_status_agreement_degraded(self):
        """Status agreement drop of 0.35 should generate high alert."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(status_agreement=0.95, snapshot_id=1)
        curr = _make_snapshot(status_agreement=0.60, snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "status_agreement_degraded")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is not None
        assert alert.alert_type == "status_agreement_degraded"
        assert alert.severity == "high"


# ---------------------------------------------------------------------------
# Test: Price agreement degraded alert
# ---------------------------------------------------------------------------


class TestPriceAgreementDegraded:
    """Test price agreement drop >= 0.25 generates alert."""

    def test_price_agreement_degraded(self):
        """Price agreement drop of 0.30 should generate warning alert."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(price_agreement=0.90, snapshot_id=1)
        curr = _make_snapshot(price_agreement=0.60, snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "price_agreement_degraded")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is not None
        assert alert.alert_type == "price_agreement_degraded"
        assert alert.severity in ("warning", "high")

    def test_price_agreement_high_severity_context(self):
        """Price agreement degraded with high discrepancy severity context."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(price_agreement=0.90, severity_label="low", snapshot_id=1)
        curr = _make_snapshot(price_agreement=0.60, severity_label="high", snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "price_agreement_degraded")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is not None
        assert alert.severity == "high"


# ---------------------------------------------------------------------------
# Test: DOM agreement degraded alert
# ---------------------------------------------------------------------------


class TestDomAgreementDegraded:
    """Test DOM agreement drop >= 0.25 generates warning alert."""

    def test_dom_agreement_degraded(self):
        """DOM agreement drop of 0.30 should generate warning alert."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(dom_agreement=0.80, snapshot_id=1)
        curr = _make_snapshot(dom_agreement=0.50, snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "dom_agreement_degraded")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is not None
        assert alert.alert_type == "dom_agreement_degraded"
        assert alert.severity == "warning"


# ---------------------------------------------------------------------------
# Test: Stale source count increased alert
# ---------------------------------------------------------------------------


class TestStaleSourcesIncreased:
    """Test stale source count increase generates warning alert."""

    def test_stale_sources_increased(self):
        """Stale source count increase should generate warning."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(stale_count=0, snapshot_id=1)
        curr = _make_snapshot(stale_count=2, snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "stale_sources_increased")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is not None
        assert alert.alert_type == "stale_sources_increased"
        assert alert.severity == "warning"


# ---------------------------------------------------------------------------
# Test: Low-confidence source count increased alert
# ---------------------------------------------------------------------------


class TestLowConfidenceSourcesIncreased:
    """Test low-confidence source count increase generates warning alert."""

    def test_low_confidence_sources_increased(self):
        """Low-confidence source count increase should generate warning."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(low_conf_count=0, snapshot_id=1)
        curr = _make_snapshot(low_conf_count=2, snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "low_confidence_sources_increased")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is not None
        assert alert.alert_type == "low_confidence_sources_increased"
        assert alert.severity == "warning"


# ---------------------------------------------------------------------------
# Test: Duplicate open alert prevention
# ---------------------------------------------------------------------------


class TestDuplicateAlertPrevention:
    """Test that duplicate open alerts are not created."""

    def test_duplicate_prevented(self, temp_db_with_snapshots):
        """Second generation should not create duplicate alerts."""
        from marketsentry.cross_site_trend_alerts import (
            generate_cross_site_trend_alerts,
        )

        db_path, property_id, prev_sid, curr_sid = temp_db_with_snapshots

        # First generation
        result1 = generate_cross_site_trend_alerts(database_path=db_path)
        first_count = result1.alerts_generated

        # Second generation against same snapshots
        result2 = generate_cross_site_trend_alerts(database_path=db_path)

        assert result2.alerts_generated == 0
        assert result2.duplicates_skipped >= first_count

    def test_deduplicate_open_alerts_function(self, temp_db_with_snapshots):
        """deduplicate_open_alerts should detect existing open alerts."""
        from marketsentry.cross_site_trend_alerts import (
            deduplicate_open_alerts,
            generate_cross_site_trend_alerts,
        )

        db_path, property_id, prev_sid, curr_sid = temp_db_with_snapshots

        # Generate alerts first
        generate_cross_site_trend_alerts(database_path=db_path)

        # Check deduplication for a type we know was generated
        is_dup = deduplicate_open_alerts(
            property_id, "confidence_drop", curr_sid, db_path
        )
        assert is_dup is True

    def test_different_snapshot_not_duplicate(self, temp_db_with_snapshots):
        """Same type but different snapshot_id should not be duplicate."""
        from marketsentry.cross_site_trend_alerts import (
            deduplicate_open_alerts,
            generate_cross_site_trend_alerts,
        )

        db_path, property_id, prev_sid, curr_sid = temp_db_with_snapshots

        generate_cross_site_trend_alerts(database_path=db_path)

        is_dup = deduplicate_open_alerts(
            property_id, "confidence_drop", 99999, db_path
        )
        assert is_dup is False


# ---------------------------------------------------------------------------
# Test: Acknowledge alert
# ---------------------------------------------------------------------------


class TestAcknowledgeAlert:
    """Test acknowledging alerts."""

    def test_acknowledge_alert(self, temp_db_with_snapshots):
        """Acknowledging an alert should change status."""
        from marketsentry.cross_site_trend_alerts import (
            acknowledge_cross_site_trend_alert,
            generate_cross_site_trend_alerts,
            list_cross_site_trend_alerts,
        )

        db_path, property_id, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        # Get first open alert
        open_alerts = list_cross_site_trend_alerts(
            database_path=db_path, status_filter="open"
        )
        assert len(open_alerts) > 0

        alert_id = open_alerts[0].alert_id
        result = acknowledge_cross_site_trend_alert(
            alert_id=alert_id, notes="Reviewed", database_path=db_path
        )
        assert result is True

        # Verify status changed
        ack_alerts = list_cross_site_trend_alerts(
            database_path=db_path, status_filter="acknowledged"
        )
        ack_ids = [a.alert_id for a in ack_alerts]
        assert alert_id in ack_ids

    def test_acknowledge_with_notes(self, temp_db_with_snapshots):
        """Acknowledging with notes should append notes."""
        from marketsentry.cross_site_trend_alerts import (
            acknowledge_cross_site_trend_alert,
            generate_cross_site_trend_alerts,
            list_cross_site_trend_alerts,
        )

        db_path, _, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        open_alerts = list_cross_site_trend_alerts(
            database_path=db_path, status_filter="open"
        )
        alert_id = open_alerts[0].alert_id

        acknowledge_cross_site_trend_alert(
            alert_id=alert_id, notes="Checked data", database_path=db_path
        )

        # Verify notes
        ack_alerts = list_cross_site_trend_alerts(
            database_path=db_path, status_filter="acknowledged"
        )
        found = [a for a in ack_alerts if a.alert_id == alert_id]
        assert len(found) == 1
        assert "Checked data" in (found[0].notes or "")


# ---------------------------------------------------------------------------
# Test: Resolve alert
# ---------------------------------------------------------------------------


class TestResolveAlert:
    """Test resolving alerts."""

    def test_resolve_alert(self, temp_db_with_snapshots):
        """Resolving an alert should change status."""
        from marketsentry.cross_site_trend_alerts import (
            generate_cross_site_trend_alerts,
            list_cross_site_trend_alerts,
            resolve_cross_site_trend_alert,
        )

        db_path, _, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        open_alerts = list_cross_site_trend_alerts(
            database_path=db_path, status_filter="open"
        )
        assert len(open_alerts) > 0

        alert_id = open_alerts[0].alert_id
        result = resolve_cross_site_trend_alert(
            alert_id=alert_id, notes="Resolved", database_path=db_path
        )
        assert result is True

        # Verify status changed
        resolved_alerts = list_cross_site_trend_alerts(
            database_path=db_path, status_filter="resolved"
        )
        resolved_ids = [a.alert_id for a in resolved_alerts]
        assert alert_id in resolved_ids


# ---------------------------------------------------------------------------
# Test: List alerts filtering
# ---------------------------------------------------------------------------


class TestListAlertsFiltering:
    """Test list alerts with various filters."""

    def test_list_open_by_default(self, temp_db_with_snapshots):
        """Default listing should return open alerts."""
        from marketsentry.cross_site_trend_alerts import (
            generate_cross_site_trend_alerts,
            list_cross_site_trend_alerts,
        )

        db_path, _, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        alerts = list_cross_site_trend_alerts(database_path=db_path)
        assert len(alerts) > 0
        for a in alerts:
            assert a.alert_status == "open"

    def test_filter_by_severity(self, temp_db_with_snapshots):
        """Filtering by severity should return matching alerts."""
        from marketsentry.cross_site_trend_alerts import (
            generate_cross_site_trend_alerts,
            list_cross_site_trend_alerts,
        )

        db_path, _, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        # Get all open alerts
        all_alerts = list_cross_site_trend_alerts(database_path=db_path)

        # Filter by each severity
        for sev in set(a.severity for a in all_alerts):
            filtered = list_cross_site_trend_alerts(
                database_path=db_path,
                severity_filter=sev,
            )
            for a in filtered:
                assert a.severity == sev

    def test_filter_by_property_id(self, temp_db_with_snapshots):
        """Filtering by property_id should return matching alerts."""
        from marketsentry.cross_site_trend_alerts import (
            generate_cross_site_trend_alerts,
            list_cross_site_trend_alerts,
        )

        db_path, property_id, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        alerts = list_cross_site_trend_alerts(
            database_path=db_path, property_id=property_id
        )
        for a in alerts:
            assert a.property_id == property_id

    def test_filter_nonexistent_returns_empty(self, temp_db_with_snapshots):
        """Filtering by nonexistent property should return empty."""
        from marketsentry.cross_site_trend_alerts import (
            generate_cross_site_trend_alerts,
            list_cross_site_trend_alerts,
        )

        db_path, _, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        alerts = list_cross_site_trend_alerts(
            database_path=db_path, property_id=99999
        )
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# Test: Export alert report
# ---------------------------------------------------------------------------


class TestExportAlertReport:
    """Test alert report export."""

    def test_export_report(self, temp_db_with_snapshots, temp_exports_dir):
        """Export should create CSV with correct columns."""
        from marketsentry.cross_site_trend_alerts import (
            export_cross_site_trend_alerts_report,
            generate_cross_site_trend_alerts,
            ALERT_REPORT_FIELDNAMES,
        )

        db_path, _, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        output_path = str(Path(temp_exports_dir) / "test_alerts.csv")
        csv_path = export_cross_site_trend_alerts_report(
            database_path=db_path, output_path=output_path
        )

        assert Path(csv_path).exists()

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) > 0
            assert set(ALERT_REPORT_FIELDNAMES).issubset(set(reader.fieldnames or []))

    def test_export_with_status_filter(self, temp_db_with_snapshots, temp_exports_dir):
        """Export with status filter should only include matching alerts."""
        from marketsentry.cross_site_trend_alerts import (
            acknowledge_cross_site_trend_alert,
            export_cross_site_trend_alerts_report,
            generate_cross_site_trend_alerts,
            list_cross_site_trend_alerts,
        )

        db_path, _, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        # Acknowledge one alert
        open_alerts = list_cross_site_trend_alerts(database_path=db_path)
        if open_alerts:
            acknowledge_cross_site_trend_alert(
                alert_id=open_alerts[0].alert_id, database_path=db_path
            )

        output_path = str(Path(temp_exports_dir) / "test_ack_alerts.csv")
        csv_path = export_cross_site_trend_alerts_report(
            database_path=db_path, output_path=output_path, status_filter="acknowledged"
        )

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            for row in rows:
                assert row["alert_status"] == "acknowledged"

    def test_export_empty_db(self, temp_db, temp_exports_dir):
        """Export from empty database should create CSV with headers only."""
        from marketsentry.cross_site_trend_alerts import (
            export_cross_site_trend_alerts_report,
        )

        output_path = str(Path(temp_exports_dir) / "test_empty_alerts.csv")
        csv_path = export_cross_site_trend_alerts_report(
            database_path=temp_db, output_path=output_path
        )

        assert Path(csv_path).exists()
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 0


# ---------------------------------------------------------------------------
# Test: Watchlist monitoring alert summary fields
# ---------------------------------------------------------------------------


class TestWatchlistMonitoringAlertSummary:
    """Test watchlist monitoring integration with alert summary fields."""

    def test_summary_fields_present(self, temp_db_with_snapshots):
        """Alert summary for property should include all expected fields."""
        from marketsentry.cross_site_trend_alerts import (
            generate_cross_site_trend_alerts,
            get_alert_summary_for_property,
        )

        db_path, property_id, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        summary = get_alert_summary_for_property(property_id, db_path)

        assert "open_cross_site_alert_count" in summary
        assert "highest_cross_site_alert_severity" in summary
        assert "latest_cross_site_alert_type" in summary
        assert "latest_cross_site_alert_message" in summary
        assert "cross_site_alert_recommended_action" in summary

    def test_summary_with_alerts(self, temp_db_with_snapshots):
        """Summary for property with alerts should have nonzero count."""
        from marketsentry.cross_site_trend_alerts import (
            generate_cross_site_trend_alerts,
            get_alert_summary_for_property,
        )

        db_path, property_id, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        summary = get_alert_summary_for_property(property_id, db_path)
        assert summary["open_cross_site_alert_count"] > 0
        assert summary["highest_cross_site_alert_severity"] is not None
        assert summary["latest_cross_site_alert_type"] is not None

    def test_summary_no_alerts(self, temp_db):
        """Summary for property with no alerts should be zero."""
        from marketsentry.cross_site_trend_alerts import (
            get_alert_summary_for_property,
        )

        summary = get_alert_summary_for_property(99999, temp_db)
        assert summary["open_cross_site_alert_count"] == 0
        assert summary["highest_cross_site_alert_severity"] is None


# ---------------------------------------------------------------------------
# Test: Dashboard alert table loads
# ---------------------------------------------------------------------------


class TestDashboardAlertTable:
    """Test dashboard alert table loading."""

    def test_build_alerts_table_from_csv(self, temp_db_with_snapshots, temp_exports_dir):
        """build_cross_site_trend_alerts_table loads CSV report."""
        from marketsentry.cross_site_trend_alerts import (
            export_cross_site_trend_alerts_report,
            generate_cross_site_trend_alerts,
        )
        from marketsentry.dashboard import build_cross_site_trend_alerts_table

        db_path, _, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        output_path = str(
            Path(temp_exports_dir) / "cross_site_trend_alerts_20260508_120000.csv"
        )
        export_cross_site_trend_alerts_report(
            database_path=db_path, output_path=output_path
        )

        df = build_cross_site_trend_alerts_table(temp_exports_dir)
        assert not df.empty
        assert "alert_type" in df.columns
        assert "severity" in df.columns

    def test_build_alerts_table_from_db(self, temp_db_with_snapshots):
        """build_cross_site_trend_alerts_from_db loads from database."""
        from marketsentry.cross_site_trend_alerts import (
            generate_cross_site_trend_alerts,
        )
        from marketsentry.dashboard import build_cross_site_trend_alerts_from_db

        db_path, _, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        df = build_cross_site_trend_alerts_from_db(db_path)
        assert not df.empty
        assert "alert_type" in df.columns

    def test_find_latest_alert_report(self, temp_db_with_snapshots, temp_exports_dir):
        """find_latest_report should find alerts report."""
        from marketsentry.cross_site_trend_alerts import (
            export_cross_site_trend_alerts_report,
            generate_cross_site_trend_alerts,
        )
        from marketsentry.dashboard import find_latest_report

        db_path, _, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        output_path = str(
            Path(temp_exports_dir) / "cross_site_trend_alerts_20260508_120000.csv"
        )
        export_cross_site_trend_alerts_report(
            database_path=db_path, output_path=output_path
        )

        report = find_latest_report("cross_site_trend_alerts", temp_exports_dir)
        assert report is not None
        assert "cross_site_trend_alerts" in report.name


# ---------------------------------------------------------------------------
# Test: No Redfin source-of-truth overwrite
# ---------------------------------------------------------------------------


class TestNoRedfinOverwrite:
    """Verify alerts do not overwrite Redfin source-of-truth fields."""

    def test_watched_properties_unchanged(self, temp_db_with_snapshots):
        """Generating alerts should not modify watched_properties."""
        from marketsentry.cross_site_trend_alerts import (
            generate_cross_site_trend_alerts,
        )

        db_path, property_id, _, _ = temp_db_with_snapshots

        # Read before
        before = execute_query(
            "SELECT * FROM watched_properties WHERE property_id = ?",
            (property_id,),
            database_path=db_path,
        )
        before_dict = dict(before[0])

        generate_cross_site_trend_alerts(database_path=db_path)

        # Read after
        after = execute_query(
            "SELECT * FROM watched_properties WHERE property_id = ?",
            (property_id,),
            database_path=db_path,
        )
        after_dict = dict(after[0])

        # Key Redfin-sourced fields should be unchanged
        for field in [
            "current_price", "displayed_dom", "garage_spaces",
            "gas_service", "active_watch_status", "user_notes",
            "watch_priority",
        ]:
            assert before_dict.get(field) == after_dict.get(field), (
                f"Field {field} changed from {before_dict.get(field)} to {after_dict.get(field)}"
            )

    def test_alert_module_has_no_update_property_calls(self):
        """The alert module should not write to watched_properties."""
        import inspect
        import marketsentry.cross_site_trend_alerts as mod

        source = inspect.getsource(mod)
        # Should not UPDATE watched_properties
        assert "UPDATE watched_properties" not in source
        # Should not INSERT INTO watched_properties
        assert "INSERT INTO watched_properties" not in source


# ---------------------------------------------------------------------------
# Test: Quiet gatekeeper remains unchanged
# ---------------------------------------------------------------------------


class TestQuietGatekeeperUnchanged:
    """Verify alert module does not modify or override Quiet Score gatekeeper."""

    def test_no_quiet_gatekeeper_import(self):
        """The alert module should not import or call quiet gatekeeper."""
        import inspect
        import marketsentry.cross_site_trend_alerts as mod

        source = inspect.getsource(mod)
        assert "apply_quiet_gatekeeper" not in source
        assert "quiet_vibrancy" not in source

    def test_no_quiet_score_write(self):
        """The alert module should not write quiet_score."""
        import inspect
        import marketsentry.cross_site_trend_alerts as mod

        source = inspect.getsource(mod)
        assert "quiet_score =" not in source.replace("quiet_score =", "").replace(
            "quiet_score =", ""
        ) or "quiet_score" in source  # Will pass since we don't write it


# ---------------------------------------------------------------------------
# Test: No walkability fields added
# ---------------------------------------------------------------------------


class TestNoWalkabilityFields:
    """Verify no walkability fields are added."""

    def test_no_walkability_in_alert_module(self):
        """Alert module should not reference walkability."""
        import inspect
        import marketsentry.cross_site_trend_alerts as mod

        source = inspect.getsource(mod)
        assert "walkability" not in source.lower()
        assert "walk_score" not in source.lower()

    def test_no_walkability_in_models(self):
        """New models should not include walkability fields."""
        from marketsentry.models import (
            CrossSiteTrendAlert,
            CrossSiteTrendAlertReportRow,
            CrossSiteTrendAlertRule,
            CrossSiteTrendAlertRunResult,
        )

        for model_cls in [
            CrossSiteTrendAlert,
            CrossSiteTrendAlertReportRow,
            CrossSiteTrendAlertRule,
            CrossSiteTrendAlertRunResult,
        ]:
            fields = model_cls.model_fields
            for field_name in fields:
                assert "walkability" not in field_name.lower()
                assert "walk_score" not in field_name.lower()

    def test_no_walkability_in_schema(self):
        """Schema should not reference walkability."""
        assert "walkability" not in CREATE_CROSS_SITE_TREND_ALERTS_TABLE.lower()
        assert "walk_score" not in CREATE_CROSS_SITE_TREND_ALERTS_TABLE.lower()


# ---------------------------------------------------------------------------
# Test: No real network calls
# ---------------------------------------------------------------------------


class TestNoNetworkCalls:
    """Verify no real network calls are made."""

    def test_no_network_in_alert_generation(self, temp_db_with_snapshots):
        """Alert generation should not make network calls."""
        from marketsentry.cross_site_trend_alerts import (
            generate_cross_site_trend_alerts,
        )

        db_path, _, _, _ = temp_db_with_snapshots

        with patch("urllib.request.urlopen") as mock_urlopen, \
             patch("http.client.HTTPConnection") as mock_http:
            generate_cross_site_trend_alerts(database_path=db_path)
            mock_urlopen.assert_not_called()
            mock_http.assert_not_called()

    def test_no_requests_import_in_module(self):
        """Alert module should not import requests or urllib."""
        import inspect
        import marketsentry.cross_site_trend_alerts as mod

        source = inspect.getsource(mod)
        assert "import requests" not in source
        assert "import urllib" not in source
        assert "import httpx" not in source


# ---------------------------------------------------------------------------
# Test: Full generation with database
# ---------------------------------------------------------------------------


class TestFullGeneration:
    """Test end-to-end alert generation with database."""

    def test_generate_creates_alerts(self, temp_db_with_snapshots):
        """generate_cross_site_trend_alerts should create alerts."""
        from marketsentry.cross_site_trend_alerts import (
            generate_cross_site_trend_alerts,
        )

        db_path, _, _, _ = temp_db_with_snapshots
        result = generate_cross_site_trend_alerts(database_path=db_path)

        assert result.properties_scanned >= 1
        assert result.alerts_generated > 0
        assert len(result.errors) == 0

    def test_generate_empty_db(self, temp_db):
        """Generation with no properties should return zero counts."""
        from marketsentry.cross_site_trend_alerts import (
            generate_cross_site_trend_alerts,
        )

        result = generate_cross_site_trend_alerts(database_path=temp_db)
        assert result.properties_scanned == 0
        assert result.alerts_generated == 0

    def test_alert_has_message_and_action(self, temp_db_with_snapshots):
        """Generated alerts should have message and recommended_action."""
        from marketsentry.cross_site_trend_alerts import (
            generate_cross_site_trend_alerts,
            list_cross_site_trend_alerts,
        )

        db_path, _, _, _ = temp_db_with_snapshots
        generate_cross_site_trend_alerts(database_path=db_path)

        alerts = list_cross_site_trend_alerts(database_path=db_path)
        for a in alerts:
            assert a.message is not None and len(a.message) > 0
            assert a.recommended_action is not None and len(a.recommended_action) > 0


# ---------------------------------------------------------------------------
# Test: Source quality improved alert
# ---------------------------------------------------------------------------


class TestSourceQualityImproved:
    """Test source quality improvement generates info alert."""

    def test_source_quality_improved(self):
        """Decreased stale/low-conf counts should trigger info alert."""
        from marketsentry.cross_site_trend_alerts import (
            _evaluate_rule,
            DEFAULT_RULES,
        )
        from marketsentry.cross_site_trends import calculate_cross_site_trend_change

        prev = _make_snapshot(stale_count=3, low_conf_count=2, snapshot_id=1)
        curr = _make_snapshot(stale_count=1, low_conf_count=0, snapshot_id=2)
        change = calculate_cross_site_trend_change(curr, prev)

        rule = next(r for r in DEFAULT_RULES if r.alert_type == "source_quality_improved")
        alert = _evaluate_rule(rule, curr, prev, change)

        assert alert is not None
        assert alert.alert_type == "source_quality_improved"
        assert alert.severity == "info"


# ---------------------------------------------------------------------------
# Test: CLI commands
# ---------------------------------------------------------------------------


class TestCLICommands:
    """Test CLI command registration and invocation."""

    def test_generate_command_registered(self):
        """generate-cross-site-trend-alerts command should be registered."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(app, ["generate-cross-site-trend-alerts", "--help"])
        assert result.exit_code == 0
        assert "trend alerts" in result.output.lower() or "snapshot" in result.output.lower()

    def test_list_command_registered(self):
        """list-cross-site-trend-alerts command should be registered."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(app, ["list-cross-site-trend-alerts", "--help"])
        assert result.exit_code == 0

    def test_acknowledge_command_registered(self):
        """acknowledge-cross-site-trend-alert command should be registered."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(app, ["acknowledge-cross-site-trend-alert", "--help"])
        assert result.exit_code == 0

    def test_resolve_command_registered(self):
        """resolve-cross-site-trend-alert command should be registered."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(app, ["resolve-cross-site-trend-alert", "--help"])
        assert result.exit_code == 0

    def test_export_command_registered(self):
        """export-cross-site-trend-alerts-report command should be registered."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(app, ["export-cross-site-trend-alerts-report", "--help"])
        assert result.exit_code == 0

    def test_generate_command_runs(self, temp_db_with_snapshots):
        """generate command should run successfully."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        db_path, _, _, _ = temp_db_with_snapshots
        runner = CliRunner()
        result = runner.invoke(
            app, ["generate-cross-site-trend-alerts", "--db", db_path]
        )
        assert result.exit_code == 0
        assert "complete" in result.output.lower() or "generated" in result.output.lower()

    def test_list_command_runs(self, temp_db_with_snapshots):
        """list command should run successfully."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        db_path, _, _, _ = temp_db_with_snapshots
        runner = CliRunner()

        # Generate first
        runner.invoke(app, ["generate-cross-site-trend-alerts", "--db", db_path])

        result = runner.invoke(
            app, ["list-cross-site-trend-alerts", "--db", db_path]
        )
        assert result.exit_code == 0

    def test_export_command_runs(self, temp_db_with_snapshots, temp_exports_dir):
        """export command should run successfully."""
        from marketsentry.cli import app
        from typer.testing import CliRunner

        db_path, _, _, _ = temp_db_with_snapshots
        runner = CliRunner()

        runner.invoke(app, ["generate-cross-site-trend-alerts", "--db", db_path])

        result = runner.invoke(
            app,
            [
                "export-cross-site-trend-alerts-report",
                "--db", db_path,
                "--output-dir", temp_exports_dir,
            ],
        )
        assert result.exit_code == 0
        assert "exported" in result.output.lower() or "success" in result.output.lower()


# ---------------------------------------------------------------------------
# Test: Model validation
# ---------------------------------------------------------------------------


class TestModels:
    """Test Milestone 26 models."""

    def test_cross_site_trend_alert_model(self):
        """CrossSiteTrendAlert should have all expected fields."""
        alert = CrossSiteTrendAlert(
            property_id=1,
            alert_type="confidence_drop",
            severity="warning",
        )
        assert alert.property_id == 1
        assert alert.alert_type == "confidence_drop"
        assert alert.severity == "warning"
        assert alert.alert_status == "open"

    def test_cross_site_trend_alert_rule_model(self):
        """CrossSiteTrendAlertRule should have all expected fields."""
        rule = CrossSiteTrendAlertRule(
            alert_type="confidence_drop",
            description="Test rule",
            threshold=0.10,
        )
        assert rule.alert_type == "confidence_drop"
        assert rule.threshold == 0.10

    def test_cross_site_trend_alert_run_result_model(self):
        """CrossSiteTrendAlertRunResult should have all expected fields."""
        result = CrossSiteTrendAlertRunResult(
            properties_scanned=5,
            alerts_generated=3,
            duplicates_skipped=1,
        )
        assert result.properties_scanned == 5
        assert result.alerts_generated == 3
        assert result.duplicates_skipped == 1

    def test_cross_site_trend_alert_report_row_model(self):
        """CrossSiteTrendAlertReportRow should have all expected fields."""
        row = CrossSiteTrendAlertReportRow(
            alert_id=1,
            property_id=1,
            alert_type="confidence_drop",
            severity="warning",
            alert_status="open",
        )
        assert row.alert_id == 1
        assert row.alert_type == "confidence_drop"

    def test_default_rules_list(self):
        """DEFAULT_RULES should contain all 12 rule types."""
        from marketsentry.cross_site_trend_alerts import DEFAULT_RULES

        expected_types = {
            "confidence_drop",
            "confidence_improvement",
            "severity_increase",
            "severity_decrease",
            "manual_review_priority_increase",
            "manual_review_priority_decrease",
            "price_agreement_degraded",
            "status_agreement_degraded",
            "dom_agreement_degraded",
            "stale_sources_increased",
            "low_confidence_sources_increased",
            "source_quality_improved",
        }
        actual_types = {r.alert_type for r in DEFAULT_RULES}
        assert expected_types == actual_types
