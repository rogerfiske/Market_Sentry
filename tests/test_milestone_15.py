"""Tests for Milestone 15: Retrieval Safety Enforcement and Fixture Capture Queue.

Covers:
- Retrieval policy engine
- Offline robots policy parsing
- Deterministic rate limiter
- Dry-run approval/history gate
- Fixture capture queue (SQLite-backed)
- 5 CLI commands
- Redfin adapter integration with policy engine
- Retrieval audit report
- No network calls

All tests are local. No network access is performed.
"""

import csv
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from marketsentry.source_adapters.base import RetrievalMode


# ===========================================================================
# TestRetrievalPolicy
# ===========================================================================


class TestRetrievalPolicyDecision:
    """Test RetrievalPolicyDecision enum and RetrievalPolicy model."""

    def test_policy_decision_values(self):
        from marketsentry.source_adapters.policy import RetrievalPolicyDecision

        assert RetrievalPolicyDecision.ALLOWED == "allowed"
        assert RetrievalPolicyDecision.BLOCKED == "blocked"
        assert RetrievalPolicyDecision.REQUIRES_MANUAL_FIXTURE == "requires_manual_fixture"
        assert RetrievalPolicyDecision.REQUIRES_DRY_RUN == "requires_dry_run"
        assert RetrievalPolicyDecision.REQUIRES_AUTHORIZED_ACCESS == "requires_authorized_access"
        assert RetrievalPolicyDecision.NOT_IMPLEMENTED == "not_implemented"

    def test_policy_model_defaults(self):
        from marketsentry.source_adapters.policy import RetrievalPolicy

        p = RetrievalPolicy()
        assert p.decision.value == "blocked"
        assert p.is_blocked is True
        assert p.is_allowed is False
        assert p.network_call_performed is False
        assert p.compliance_passed is False
        assert p.robots_passed is False
        assert p.robots_unknown is True
        assert p.rate_limit_passed is False
        assert p.dry_run_approved is False
        assert p.fixture_capture_recommended is False

    def test_policy_allowed_property(self):
        from marketsentry.source_adapters.policy import (
            RetrievalPolicy,
            RetrievalPolicyDecision,
        )

        p = RetrievalPolicy(decision=RetrievalPolicyDecision.ALLOWED)
        assert p.is_allowed is True
        assert p.is_blocked is False

    def test_policy_reason_messages(self):
        from marketsentry.source_adapters.policy import (
            RetrievalPolicy,
            RetrievalPolicyReason,
        )

        p = RetrievalPolicy(
            reasons=[
                RetrievalPolicyReason(message="Reason 1"),
                RetrievalPolicyReason(message="Reason 2"),
            ]
        )
        assert p.reason_messages == ["Reason 1", "Reason 2"]


class TestEvaluateRetrievalPolicy:
    """Test evaluate_retrieval_policy function."""

    def test_disabled_mode_is_blocked(self):
        from marketsentry.source_adapters.policy import evaluate_retrieval_policy

        policy = evaluate_retrieval_policy(
            source_name="redfin",
            url="https://www.redfin.com/CA/Temecula/test",
            request_type="search",
            retrieval_mode="disabled",
        )
        assert policy.is_blocked is True
        assert "disabled" in policy.reason_messages[0].lower()

    def test_dry_run_mode_is_allowed(self):
        from marketsentry.source_adapters.policy import evaluate_retrieval_policy

        policy = evaluate_retrieval_policy(
            source_name="redfin",
            url="https://www.redfin.com/CA/Temecula/test",
            request_type="search",
            retrieval_mode="dry_run",
        )
        assert policy.is_allowed is True
        assert policy.network_call_performed is False

    def test_manual_fixture_mode_is_allowed(self):
        from marketsentry.source_adapters.policy import evaluate_retrieval_policy

        policy = evaluate_retrieval_policy(
            source_name="redfin",
            url="https://www.redfin.com/CA/Temecula/test",
            request_type="search",
            retrieval_mode="manual_fixture",
        )
        assert policy.is_allowed is True

    def test_authorized_api_mode_recommends_fixture(self):
        from marketsentry.source_adapters.policy import evaluate_retrieval_policy

        policy = evaluate_retrieval_policy(
            source_name="redfin",
            url="https://www.redfin.com/CA/Temecula/test",
            request_type="search",
            retrieval_mode="authorized_api",
        )
        assert policy.decision.value == "requires_authorized_access"
        assert policy.fixture_capture_recommended is True

    def test_live_http_blocked_by_default(self):
        from marketsentry.source_adapters.compliance import RetrievalComplianceConfig
        from marketsentry.source_adapters.policy import evaluate_retrieval_policy

        cc = RetrievalComplianceConfig(live_retrieval_enabled=False)
        policy = evaluate_retrieval_policy(
            source_name="redfin",
            url="https://www.redfin.com/city/19701/CA/Temecula/filter/test",
            request_type="search",
            retrieval_mode="live_http",
            compliance_config=cc,
        )
        assert policy.is_blocked is True
        assert policy.fixture_capture_recommended is True

    def test_live_http_blocked_by_robots_unknown(self):
        from marketsentry.source_adapters.compliance import RetrievalComplianceConfig
        from marketsentry.source_adapters.policy import evaluate_retrieval_policy

        cc = RetrievalComplianceConfig(
            live_retrieval_enabled=True,
            allowed_live_sources=["redfin"],
            live_user_agent="MarketSentry/1.0",
            max_requests_per_minute=6,
        )
        policy = evaluate_retrieval_policy(
            source_name="redfin",
            url="https://www.redfin.com/city/19701/CA/Temecula/filter/test",
            request_type="search",
            retrieval_mode="live_http",
            compliance_config=cc,
            robots_unknown=True,
        )
        assert policy.robots_unknown is True
        assert policy.is_blocked is True

    def test_live_http_blocked_by_rate_limit(self):
        from marketsentry.source_adapters.compliance import RetrievalComplianceConfig
        from marketsentry.source_adapters.policy import evaluate_retrieval_policy

        cc = RetrievalComplianceConfig(
            live_retrieval_enabled=True,
            allowed_live_sources=["redfin"],
            live_user_agent="MarketSentry/1.0",
            max_requests_per_minute=6,
        )
        policy = evaluate_retrieval_policy(
            source_name="redfin",
            url="https://www.redfin.com/city/19701/CA/Temecula/filter/test",
            request_type="search",
            retrieval_mode="live_http",
            compliance_config=cc,
            robots_allowed=True,
            robots_unknown=False,
            rate_limit_ok=False,
        )
        assert policy.rate_limit_passed is False

    def test_live_http_blocked_by_dry_run_required(self):
        from marketsentry.source_adapters.compliance import RetrievalComplianceConfig
        from marketsentry.source_adapters.policy import evaluate_retrieval_policy

        cc = RetrievalComplianceConfig(
            live_retrieval_enabled=True,
            allowed_live_sources=["redfin"],
            live_user_agent="MarketSentry/1.0",
            max_requests_per_minute=6,
            require_dry_run_before_live=True,
        )
        policy = evaluate_retrieval_policy(
            source_name="redfin",
            url="https://www.redfin.com/city/19701/CA/Temecula/filter/test",
            request_type="search",
            retrieval_mode="live_http",
            compliance_config=cc,
            robots_allowed=True,
            robots_unknown=False,
            rate_limit_ok=True,
            has_recent_dry_run=False,
        )
        assert policy.dry_run_approved is False

    def test_all_checks_pass_still_not_implemented(self):
        from marketsentry.source_adapters.compliance import RetrievalComplianceConfig
        from marketsentry.source_adapters.policy import evaluate_retrieval_policy

        cc = RetrievalComplianceConfig(
            live_retrieval_enabled=True,
            allowed_live_sources=["redfin"],
            live_user_agent="MarketSentry/1.0",
            max_requests_per_minute=6,
            require_dry_run_before_live=False,
        )
        policy = evaluate_retrieval_policy(
            source_name="redfin",
            url="https://www.redfin.com/city/19701/CA/Temecula/filter/test",
            request_type="search",
            retrieval_mode="live_http",
            compliance_config=cc,
            robots_allowed=True,
            robots_unknown=False,
            rate_limit_ok=True,
            has_recent_dry_run=True,
        )
        assert policy.decision.value == "not_implemented"
        assert policy.fixture_capture_recommended is True

    def test_fixture_path_suggestion(self):
        from marketsentry.source_adapters.policy import suggest_fixture_path

        assert suggest_fixture_path("redfin", "search") == "data/raw/redfin/search"
        assert suggest_fixture_path("redfin", "property_detail") == "data/raw/redfin/details"
        assert suggest_fixture_path("zillow", "property_detail") == "data/raw/cross_site/zillow"
        assert suggest_fixture_path("county", "assessor") == "data/raw/county/assessor"
        assert suggest_fixture_path("county", "recorder") == "data/raw/county/recorder"
        # Unknown fallback
        assert suggest_fixture_path("unknown_source", "unknown_type") == "data/raw/unknown_source"


# ===========================================================================
# TestRobotsPolicy
# ===========================================================================


class TestRobotsPolicyParsing:
    """Test offline robots.txt parsing."""

    def test_parse_empty_robots(self):
        from marketsentry.source_adapters.robots_policy import parse_robots_text

        policy = parse_robots_text("")
        assert policy.parsed is True
        assert len(policy.user_agent_rules) == 0

    def test_parse_redfin_robots_fixture(self):
        from marketsentry.source_adapters.robots_policy import parse_robots_text

        fixture_path = Path(__file__).parent / "fixtures" / "robots" / "redfin_robots.txt"
        text = fixture_path.read_text()
        policy = parse_robots_text(text, source_site="redfin")
        assert policy.parsed is True
        assert policy.source_site == "redfin"
        assert "*" in policy.user_agent_rules
        assert "marketsentry" in policy.user_agent_rules

    def test_parse_block_all_robots(self):
        from marketsentry.source_adapters.robots_policy import parse_robots_text

        fixture_path = Path(__file__).parent / "fixtures" / "robots" / "block_all_robots.txt"
        text = fixture_path.read_text()
        policy = parse_robots_text(text, source_site="test")
        assert policy.parsed is True
        assert "*" in policy.user_agent_rules
        rules = policy.user_agent_rules["*"]
        assert any(r.path == "/" and r.rule_type == "disallow" for r in rules)

    def test_parse_zillow_robots_fixture(self):
        from marketsentry.source_adapters.robots_policy import parse_robots_text

        fixture_path = Path(__file__).parent / "fixtures" / "robots" / "zillow_robots.txt"
        text = fixture_path.read_text()
        policy = parse_robots_text(text, source_site="zillow")
        assert policy.parsed is True
        assert "*" in policy.user_agent_rules
        assert "badbot" in policy.user_agent_rules


class TestRobotsPolicyChecking:
    """Test robots policy allowed/blocked decisions."""

    def test_allowed_by_default_no_rules(self):
        from marketsentry.source_adapters.robots_policy import (
            check_robots_allowed,
            parse_robots_text,
        )

        policy = parse_robots_text("")
        result = check_robots_allowed(policy, "TestBot", "/some/path")
        assert result.allowed is True

    def test_block_all_disallows_everything(self):
        from marketsentry.source_adapters.robots_policy import (
            check_robots_allowed,
            parse_robots_text,
        )

        fixture_path = Path(__file__).parent / "fixtures" / "robots" / "block_all_robots.txt"
        text = fixture_path.read_text()
        policy = parse_robots_text(text)
        result = check_robots_allowed(policy, "AnyBot", "/any/path")
        assert result.allowed is False

    def test_redfin_marketsentry_allows_city(self):
        from marketsentry.source_adapters.robots_policy import (
            check_robots_allowed,
            parse_robots_text,
        )

        fixture_path = Path(__file__).parent / "fixtures" / "robots" / "redfin_robots.txt"
        text = fixture_path.read_text()
        policy = parse_robots_text(text)
        result = check_robots_allowed(policy, "MarketSentry", "/city/19701/CA/Temecula")
        assert result.allowed is True

    def test_redfin_marketsentry_blocks_account(self):
        from marketsentry.source_adapters.robots_policy import (
            check_robots_allowed,
            parse_robots_text,
        )

        fixture_path = Path(__file__).parent / "fixtures" / "robots" / "redfin_robots.txt"
        text = fixture_path.read_text()
        policy = parse_robots_text(text)
        result = check_robots_allowed(policy, "MarketSentry", "/account/settings")
        assert result.allowed is False

    def test_wildcard_blocks_api(self):
        from marketsentry.source_adapters.robots_policy import (
            check_robots_allowed,
            parse_robots_text,
        )

        fixture_path = Path(__file__).parent / "fixtures" / "robots" / "redfin_robots.txt"
        text = fixture_path.read_text()
        policy = parse_robots_text(text)
        result = check_robots_allowed(policy, "SomeOtherBot", "/api/v2/test")
        assert result.allowed is False

    def test_zillow_badbot_blocked(self):
        from marketsentry.source_adapters.robots_policy import (
            check_robots_allowed,
            parse_robots_text,
        )

        fixture_path = Path(__file__).parent / "fixtures" / "robots" / "zillow_robots.txt"
        text = fixture_path.read_text()
        policy = parse_robots_text(text)
        result = check_robots_allowed(policy, "BadBot", "/homedetails/test")
        assert result.allowed is False

    def test_zillow_generic_allows_homedetails(self):
        from marketsentry.source_adapters.robots_policy import (
            check_robots_allowed,
            parse_robots_text,
        )

        fixture_path = Path(__file__).parent / "fixtures" / "robots" / "zillow_robots.txt"
        text = fixture_path.read_text()
        policy = parse_robots_text(text)
        result = check_robots_allowed(policy, "GenericBot", "/homedetails/12345")
        assert result.allowed is True


class TestRobotsPolicyLocalLoading:
    """Test loading robots policy from local files."""

    def test_load_missing_file_returns_none(self):
        from marketsentry.source_adapters.robots_policy import load_local_robots_policy

        result = load_local_robots_policy("nonexistent_source", "/tmp/no_such_dir")
        assert result is None

    def test_load_existing_fixture(self):
        from marketsentry.source_adapters.robots_policy import load_local_robots_policy

        fixture_dir = str(Path(__file__).parent / "fixtures" / "robots")
        result = load_local_robots_policy("redfin", fixture_dir)
        assert result is not None
        assert result.parsed is True
        assert result.source_site == "redfin"


# ===========================================================================
# TestRateLimiter
# ===========================================================================


class TestRateLimiter:
    """Test deterministic rate limiter."""

    def test_allowed_when_empty(self):
        from marketsentry.source_adapters.rate_limiter import check_rate_limit

        result = check_rate_limit("redfin")
        assert result.decision.value == "allowed"
        assert result.requests_in_window == 0

    def test_blocked_at_limit(self):
        from marketsentry.source_adapters.compliance import RateLimitConfig
        from marketsentry.source_adapters.rate_limiter import (
            SourceRateLimitState,
            check_rate_limit,
        )

        now = datetime.now()
        state = SourceRateLimitState(source_site="redfin")

        # Fill up to limit
        for i in range(6):
            state.add_timestamp(now - timedelta(seconds=i * 5))

        config = RateLimitConfig(max_requests_per_minute=6)
        result = check_rate_limit("redfin", config=config, state=state, now=now)
        assert result.decision.value == "blocked"
        assert result.requests_in_window >= 6

    def test_allowed_after_window_expires(self):
        from marketsentry.source_adapters.compliance import RateLimitConfig
        from marketsentry.source_adapters.rate_limiter import (
            SourceRateLimitState,
            check_rate_limit,
        )

        now = datetime.now()
        state = SourceRateLimitState(source_site="redfin")

        # Add old timestamps (>1 minute ago)
        for i in range(6):
            state.add_timestamp(now - timedelta(seconds=120 + i))

        config = RateLimitConfig(max_requests_per_minute=6)
        result = check_rate_limit("redfin", config=config, state=state, now=now)
        assert result.decision.value == "allowed"

    def test_cooldown_min_delay(self):
        from marketsentry.source_adapters.compliance import RateLimitConfig
        from marketsentry.source_adapters.rate_limiter import (
            SourceRateLimitState,
            check_rate_limit,
        )

        now = datetime.now()
        state = SourceRateLimitState(source_site="redfin")
        state.add_timestamp(now - timedelta(seconds=3))

        config = RateLimitConfig(max_requests_per_minute=60, min_delay_seconds=10)
        result = check_rate_limit("redfin", config=config, state=state, now=now)
        assert result.decision.value == "cooldown"
        assert result.seconds_until_allowed > 0

    def test_record_retrieval_attempt(self):
        from marketsentry.source_adapters.rate_limiter import (
            SourceRateLimitState,
            record_retrieval_attempt,
        )

        state = SourceRateLimitState(source_site="redfin")
        assert state.total_requests == 0

        record_retrieval_attempt(state)
        assert state.total_requests == 1
        assert len(state.request_timestamps) == 1

    def test_prune_old_timestamps(self):
        from marketsentry.source_adapters.rate_limiter import SourceRateLimitState

        now = datetime.now()
        state = SourceRateLimitState(source_site="redfin")
        state.add_timestamp(now - timedelta(minutes=10))
        state.add_timestamp(now - timedelta(seconds=30))
        state.add_timestamp(now)

        state.prune_old(timedelta(minutes=5), now)
        assert len(state.request_timestamps) == 2


# ===========================================================================
# TestDryRunApproval
# ===========================================================================


class TestDryRunApproval:
    """Test dry-run approval recording and lookup."""

    def test_record_and_lookup_approval(self):
        from marketsentry.source_adapters.dry_run_approval import (
            has_recent_dry_run_approval,
            record_dry_run_approval,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            record_dry_run_approval(
                source_site="redfin",
                url="https://www.redfin.com/CA/Temecula/test/home/123",
                request_type="property_detail",
                compliance_status="blocked",
                allowed=True,
                blocked=True,
                reasons=["Live retrieval disabled"],
                approval_dir=tmpdir,
            )

            found = has_recent_dry_run_approval(
                source_site="redfin",
                url="https://www.redfin.com/CA/Temecula/test/home/123",
                approval_dir=tmpdir,
            )
            assert found is True

    def test_no_approval_for_different_url(self):
        from marketsentry.source_adapters.dry_run_approval import (
            has_recent_dry_run_approval,
            record_dry_run_approval,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            record_dry_run_approval(
                source_site="redfin",
                url="https://www.redfin.com/CA/Temecula/test/home/123",
                request_type="property_detail",
                compliance_status="blocked",
                allowed=True,
                blocked=True,
                approval_dir=tmpdir,
            )

            found = has_recent_dry_run_approval(
                source_site="redfin",
                url="https://www.redfin.com/CA/Temecula/different/home/456",
                approval_dir=tmpdir,
            )
            assert found is False

    def test_no_approval_for_different_source(self):
        from marketsentry.source_adapters.dry_run_approval import (
            has_recent_dry_run_approval,
            record_dry_run_approval,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            record_dry_run_approval(
                source_site="redfin",
                url="https://www.redfin.com/CA/Temecula/test/home/123",
                request_type="property_detail",
                compliance_status="blocked",
                allowed=True,
                blocked=True,
                approval_dir=tmpdir,
            )

            found = has_recent_dry_run_approval(
                source_site="zillow",
                url="https://www.redfin.com/CA/Temecula/test/home/123",
                approval_dir=tmpdir,
            )
            assert found is False

    def test_no_approval_from_empty_dir(self):
        from marketsentry.source_adapters.dry_run_approval import has_recent_dry_run_approval

        with tempfile.TemporaryDirectory() as tmpdir:
            found = has_recent_dry_run_approval(
                source_site="redfin",
                url="https://www.redfin.com/CA/Temecula/test",
                approval_dir=tmpdir,
            )
            assert found is False

    def test_get_dry_run_approvals(self):
        from marketsentry.source_adapters.dry_run_approval import (
            get_dry_run_approvals,
            record_dry_run_approval,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            record_dry_run_approval(
                source_site="redfin",
                url="https://www.redfin.com/CA/test1",
                request_type="search",
                compliance_status="blocked",
                allowed=True,
                blocked=True,
                approval_dir=tmpdir,
            )
            record_dry_run_approval(
                source_site="redfin",
                url="https://www.redfin.com/CA/test2",
                request_type="property_detail",
                compliance_status="blocked",
                allowed=True,
                blocked=True,
                approval_dir=tmpdir,
            )

            approvals = get_dry_run_approvals(approval_dir=tmpdir)
            assert len(approvals) == 2

    def test_url_normalization(self):
        from marketsentry.source_adapters.dry_run_approval import normalize_url

        assert normalize_url("https://www.redfin.com/CA/test/") == "https://www.redfin.com/CA/test"
        assert normalize_url("HTTPS://WWW.REDFIN.COM/ca/test") == "https://www.redfin.com/ca/test"
        assert normalize_url("https://example.com/path#fragment") == "https://example.com/path"

    def test_require_recent_dry_run_before_live(self):
        from marketsentry.source_adapters.dry_run_approval import (
            record_dry_run_approval,
            require_recent_dry_run_before_live,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            has, reason = require_recent_dry_run_before_live(
                "redfin", "https://www.redfin.com/test", approval_dir=tmpdir
            )
            assert has is False
            assert reason is not None

            record_dry_run_approval(
                source_site="redfin",
                url="https://www.redfin.com/test",
                request_type="search",
                compliance_status="ok",
                allowed=True,
                blocked=False,
                approval_dir=tmpdir,
            )

            has, reason = require_recent_dry_run_before_live(
                "redfin", "https://www.redfin.com/test", approval_dir=tmpdir
            )
            assert has is True
            assert reason is None


# ===========================================================================
# TestFixtureCaptureQueue
# ===========================================================================


class TestFixtureCaptureQueue:
    """Test fixture capture queue operations."""

    def test_add_capture_request(self):
        from marketsentry.fixture_capture_queue import add_capture_request
        from marketsentry.source_adapters.policy import FixtureCaptureRequest

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            request = FixtureCaptureRequest(
                source_site="redfin",
                source_url="https://www.redfin.com/CA/Temecula/test/home/123",
                request_type="property_detail",
                reason="Live retrieval blocked",
            )
            result = add_capture_request(request, database_path=db_path)
            assert result.added is True
            assert result.duplicate is False
            assert result.capture_request_id is not None
        finally:
            os.unlink(db_path)

    def test_duplicate_detection(self):
        from marketsentry.fixture_capture_queue import add_capture_request
        from marketsentry.source_adapters.policy import FixtureCaptureRequest

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            request = FixtureCaptureRequest(
                source_site="redfin",
                source_url="https://www.redfin.com/CA/Temecula/test/home/123",
                request_type="property_detail",
            )
            result1 = add_capture_request(request, database_path=db_path)
            result2 = add_capture_request(request, database_path=db_path)
            assert result1.added is True
            assert result2.added is False
            assert result2.duplicate is True
        finally:
            os.unlink(db_path)

    def test_list_pending_requests(self):
        from marketsentry.fixture_capture_queue import (
            add_capture_request,
            list_pending_capture_requests,
        )
        from marketsentry.source_adapters.policy import FixtureCaptureRequest

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            add_capture_request(
                FixtureCaptureRequest(
                    source_site="redfin",
                    source_url="https://www.redfin.com/test1",
                    request_type="search",
                ),
                database_path=db_path,
            )
            add_capture_request(
                FixtureCaptureRequest(
                    source_site="zillow",
                    source_url="https://www.zillow.com/test2",
                    request_type="property_detail",
                ),
                database_path=db_path,
            )

            all_pending = list_pending_capture_requests(database_path=db_path)
            assert len(all_pending) == 2

            redfin_only = list_pending_capture_requests(
                source_site="redfin", database_path=db_path
            )
            assert len(redfin_only) == 1
        finally:
            os.unlink(db_path)

    def test_mark_captured(self):
        from marketsentry.fixture_capture_queue import (
            add_capture_request,
            list_pending_capture_requests,
            mark_fixture_captured,
        )
        from marketsentry.source_adapters.policy import FixtureCaptureRequest

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            result = add_capture_request(
                FixtureCaptureRequest(
                    source_site="redfin",
                    source_url="https://www.redfin.com/test",
                    request_type="search",
                ),
                database_path=db_path,
            )
            cid = result.capture_request_id
            assert mark_fixture_captured(cid, "data/raw/redfin/search/test.html", db_path) is True

            pending = list_pending_capture_requests(database_path=db_path)
            assert len(pending) == 0
        finally:
            os.unlink(db_path)

    def test_mark_skipped(self):
        from marketsentry.fixture_capture_queue import (
            add_capture_request,
            list_pending_capture_requests,
            mark_fixture_skipped,
        )
        from marketsentry.source_adapters.policy import FixtureCaptureRequest

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            result = add_capture_request(
                FixtureCaptureRequest(
                    source_site="redfin",
                    source_url="https://www.redfin.com/test",
                    request_type="search",
                ),
                database_path=db_path,
            )
            mark_fixture_skipped(result.capture_request_id, "Not needed", db_path)

            pending = list_pending_capture_requests(database_path=db_path)
            assert len(pending) == 0
        finally:
            os.unlink(db_path)

    def test_get_capture_request_count(self):
        from marketsentry.fixture_capture_queue import (
            add_capture_request,
            get_capture_request_count,
        )
        from marketsentry.source_adapters.policy import FixtureCaptureRequest

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            add_capture_request(
                FixtureCaptureRequest(
                    source_site="redfin",
                    source_url="https://www.redfin.com/test1",
                    request_type="search",
                ),
                database_path=db_path,
            )
            add_capture_request(
                FixtureCaptureRequest(
                    source_site="redfin",
                    source_url="https://www.redfin.com/test2",
                    request_type="property_detail",
                ),
                database_path=db_path,
            )

            assert get_capture_request_count(database_path=db_path) == 2
            assert get_capture_request_count(status="pending", database_path=db_path) == 2
        finally:
            os.unlink(db_path)

    def test_export_capture_queue_csv(self):
        from marketsentry.fixture_capture_queue import (
            add_capture_request,
            export_capture_queue_csv,
        )
        from marketsentry.source_adapters.policy import FixtureCaptureRequest

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                add_capture_request(
                    FixtureCaptureRequest(
                        source_site="redfin",
                        source_url="https://www.redfin.com/test",
                        request_type="search",
                    ),
                    database_path=db_path,
                )

                output = export_capture_queue_csv(
                    output_dir=tmpdir, database_path=db_path
                )
                assert Path(output).exists()

                with open(output, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                assert len(rows) == 1
                assert rows[0]["source_site"] == "redfin"
            finally:
                os.unlink(db_path)


# ===========================================================================
# TestAuditReport
# ===========================================================================


class TestAuditReport:
    """Test retrieval audit report generation."""

    def test_empty_audit_dir(self):
        from marketsentry.source_adapters.audit_report import generate_audit_report

        with tempfile.TemporaryDirectory() as tmpdir:
            report = generate_audit_report(audit_dir=tmpdir)
            assert report["total_decisions"] == 0
            assert report["files_scanned"] == 0

    def test_report_from_audit_files(self):
        from marketsentry.source_adapters.audit_report import generate_audit_report

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a sample audit file
            audit_file = Path(tmpdir) / "retrieval_audit_20260506.csv"
            with open(audit_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "timestamp", "source_site", "retrieval_mode", "url",
                    "domain", "allowed", "blocked", "reason",
                    "dry_run", "network_call_performed",
                ])
                writer.writeheader()
                writer.writerow({
                    "timestamp": "2026-05-06T10:00:00",
                    "source_site": "redfin",
                    "retrieval_mode": "dry_run",
                    "url": "https://www.redfin.com/test",
                    "domain": "www.redfin.com",
                    "allowed": "True",
                    "blocked": "False",
                    "reason": "Dry-run OK",
                    "dry_run": "True",
                    "network_call_performed": "False",
                })
                writer.writerow({
                    "timestamp": "2026-05-06T10:01:00",
                    "source_site": "redfin",
                    "retrieval_mode": "live_http",
                    "url": "https://www.redfin.com/test2",
                    "domain": "www.redfin.com",
                    "allowed": "False",
                    "blocked": "True",
                    "reason": "Live retrieval disabled",
                    "dry_run": "False",
                    "network_call_performed": "False",
                })

            report = generate_audit_report(audit_dir=tmpdir)
            assert report["total_decisions"] == 2
            assert report["allowed_count"] == 1
            assert report["blocked_count"] == 1
            assert report["dry_run_count"] == 1
            assert report["live_attempt_count"] == 1
            assert report["network_call_false_count"] == 2
            assert report["network_call_true_count"] == 0
            assert report["sources"]["redfin"] == 2

    def test_nonexistent_audit_dir(self):
        from marketsentry.source_adapters.audit_report import generate_audit_report

        report = generate_audit_report(audit_dir="/tmp/nonexistent_audit_dir_12345")
        assert report["total_decisions"] == 0


# ===========================================================================
# TestCLICommands
# ===========================================================================


class TestCLICommands:
    """Test Milestone 15 CLI commands."""

    def test_retrieval_policy_check_cli(self):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "retrieval-policy-check",
            "--source", "redfin",
            "--url", "https://www.redfin.com/city/19701/CA/Temecula/filter/test",
            "--request-type", "search",
            "--mode", "live_http",
        ])
        assert result.exit_code == 0
        assert "Policy Decision" in result.output
        assert "network_call_performed=False" in result.output

    def test_retrieval_policy_check_dry_run_mode(self):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "retrieval-policy-check",
            "--source", "redfin",
            "--url", "https://www.redfin.com/test",
            "--mode", "dry_run",
        ])
        assert result.exit_code == 0
        assert "allowed" in result.output.lower()

    def test_list_fixture_capture_queue_cli_empty(self):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["list-fixture-capture-queue"])
        assert result.exit_code == 0
        assert "Fixture Capture Queue" in result.output

    def test_export_fixture_capture_queue_cli(self):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmpdir:
            runner = CliRunner()
            result = runner.invoke(app, [
                "export-fixture-capture-queue",
                "--output-dir", tmpdir,
            ])
            assert result.exit_code == 0
            assert "exported" in result.output.lower()

    def test_mark_fixture_captured_cli_not_found(self):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "mark-fixture-captured",
            "--capture-request-id", "99999",
        ])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_retrieval_audit_report_cli(self):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmpdir:
            runner = CliRunner()
            result = runner.invoke(app, [
                "retrieval-audit-report",
                "--audit-dir", tmpdir,
            ])
            assert result.exit_code == 0
            assert "Audit Summary" in result.output


# ===========================================================================
# TestRedfinAdapterIntegration
# ===========================================================================


class TestRedfinAdapterIntegration:
    """Test Redfin adapter integration with policy engine."""

    def test_dry_run_records_approval(self):
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        with tempfile.TemporaryDirectory() as tmpdir:
            approval_dir = os.path.join(tmpdir, "audit")
            os.makedirs(approval_dir, exist_ok=True)

            # Patch the approval dir
            with patch(
                "marketsentry.source_adapters.dry_run_approval.DEFAULT_APPROVAL_DIR",
                approval_dir,
            ):
                adapter = RedfinAdapter()
                result = adapter.dry_run_search(
                    "https://www.redfin.com/city/19701/CA/Temecula/filter/test"
                )
                assert result.success is True
                assert result.network_call_performed is False

                # Verify approval file was created
                approval_files = list(Path(approval_dir).glob("dry_run_approvals_*.csv"))
                assert len(approval_files) >= 1

    def test_dry_run_no_network_call(self):
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        adapter = RedfinAdapter()
        result = adapter.dry_run_property_detail(
            "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
        )
        assert result.network_call_performed is False
        assert result.dry_run is True

    def test_retrieve_blocked_creates_fixture_request(self):
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with patch(
                "marketsentry.fixture_capture_queue.get_connection"
            ) as mock_conn:
                # The retrieve method should attempt to add to fixture queue
                adapter = RedfinAdapter()
                result = adapter.retrieve_search(
                    "https://www.redfin.com/city/19701/CA/Temecula/filter/test"
                )
                assert result.blocked is True
                assert result.network_call_performed is False
        finally:
            os.unlink(db_path)


# ===========================================================================
# TestNoNetworkCalls
# ===========================================================================


class TestNoNetworkCalls:
    """Verify no network calls are performed."""

    def test_policy_engine_no_network(self):
        from marketsentry.source_adapters.policy import evaluate_retrieval_policy

        policy = evaluate_retrieval_policy(
            source_name="redfin",
            url="https://www.redfin.com/test",
            request_type="search",
            retrieval_mode="live_http",
        )
        assert policy.network_call_performed is False

    def test_robots_parser_no_network(self):
        from marketsentry.source_adapters.robots_policy import parse_robots_text

        policy = parse_robots_text("User-agent: *\nDisallow: /")
        assert policy.parsed is True
        # No network call - parsing is purely string manipulation

    def test_rate_limiter_no_network(self):
        from marketsentry.source_adapters.rate_limiter import check_rate_limit

        result = check_rate_limit("redfin")
        # Rate limiting is purely local state management
        assert result.decision.value in ("allowed", "blocked", "cooldown")

    def test_fixture_capture_queue_no_network(self):
        from marketsentry.fixture_capture_queue import add_capture_request
        from marketsentry.source_adapters.policy import FixtureCaptureRequest

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            result = add_capture_request(
                FixtureCaptureRequest(
                    source_site="redfin",
                    source_url="https://www.redfin.com/test",
                    request_type="search",
                ),
                database_path=db_path,
            )
            assert result.added is True
        finally:
            os.unlink(db_path)

    def test_audit_report_no_network(self):
        from marketsentry.source_adapters.audit_report import generate_audit_report

        with tempfile.TemporaryDirectory() as tmpdir:
            report = generate_audit_report(audit_dir=tmpdir)
            assert report["network_call_true_count"] == 0


# ===========================================================================
# TestFixtureCaptureQueueSchema
# ===========================================================================


class TestFixtureCaptureQueueSchema:
    """Test fixture_capture_queue table schema."""

    def test_table_creation(self):
        from marketsentry.fixture_capture_queue import ensure_fixture_capture_table

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            ensure_fixture_capture_table(db_path)

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='fixture_capture_queue'"
            )
            assert cursor.fetchone() is not None

            # Check columns
            cursor.execute("PRAGMA table_info(fixture_capture_queue)")
            columns = [row[1] for row in cursor.fetchall()]
            expected = [
                "capture_request_id", "created_at", "source_site",
                "source_url", "normalized_url", "request_type",
                "suggested_fixture_path", "status", "priority",
                "reason", "candidate_id", "property_id", "notes",
                "captured_at", "fixture_path",
            ]
            for col in expected:
                assert col in columns, f"Missing column: {col}"
            conn.close()
        finally:
            os.unlink(db_path)

    def test_indexes_created(self):
        from marketsentry.fixture_capture_queue import ensure_fixture_capture_table

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            ensure_fixture_capture_table(db_path)

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='fixture_capture_queue'"
            )
            indexes = [row[0] for row in cursor.fetchall()]
            assert "idx_fcq_status" in indexes
            assert "idx_fcq_source" in indexes
            assert "idx_fcq_normalized_url" in indexes
            conn.close()
        finally:
            os.unlink(db_path)


# ===========================================================================
# TestModels
# ===========================================================================


class TestModels:
    """Test Milestone 15 model imports and defaults."""

    def test_fixture_capture_request_defaults(self):
        from marketsentry.source_adapters.policy import FixtureCaptureRequest

        req = FixtureCaptureRequest()
        assert req.priority == 5
        assert req.source_site == ""
        assert req.source_url == ""
        assert req.candidate_id is None
        assert req.property_id is None

    def test_fixture_capture_queue_result_defaults(self):
        from marketsentry.source_adapters.policy import FixtureCaptureQueueResult

        res = FixtureCaptureQueueResult()
        assert res.added is False
        assert res.duplicate is False
        assert res.capture_request_id is None
        assert res.message == ""

    def test_dry_run_approval_record_defaults(self):
        from marketsentry.source_adapters.policy import DryRunApprovalRecord

        rec = DryRunApprovalRecord()
        assert rec.network_call_performed is False
        assert rec.allowed is False
        assert rec.source_site == ""

    def test_rate_limit_state_model(self):
        from marketsentry.source_adapters.rate_limiter import SourceRateLimitState

        state = SourceRateLimitState(source_site="test")
        assert state.total_requests == 0
        assert state.last_request_at is None
        assert len(state.request_timestamps) == 0

    def test_rate_limit_check_result_model(self):
        from marketsentry.source_adapters.rate_limiter import RateLimitCheckResult

        result = RateLimitCheckResult()
        assert result.decision.value == "allowed"
        assert result.max_allowed == 6

    def test_source_robots_policy_model(self):
        from marketsentry.source_adapters.robots_policy import SourceRobotsPolicy

        policy = SourceRobotsPolicy()
        assert policy.parsed is False
        assert policy.source_site == ""
        assert len(policy.user_agent_rules) == 0


# ===========================================================================
# TestExistingTests
# ===========================================================================


class TestExistingTestsNotBroken:
    """Verify Milestone 15 imports don't break existing modules."""

    def test_import_source_adapters_package(self):
        import marketsentry.source_adapters
        assert hasattr(marketsentry.source_adapters, "RetrievalPolicy")
        assert hasattr(marketsentry.source_adapters, "RetrievalPolicyDecision")
        assert hasattr(marketsentry.source_adapters, "FixtureCaptureRequest")
        assert hasattr(marketsentry.source_adapters, "DryRunApprovalRecord")

    def test_import_fixture_capture_queue(self):
        import marketsentry.fixture_capture_queue
        assert hasattr(marketsentry.fixture_capture_queue, "add_capture_request")
        assert hasattr(marketsentry.fixture_capture_queue, "list_pending_capture_requests")
        assert hasattr(marketsentry.fixture_capture_queue, "mark_fixture_captured")
        assert hasattr(marketsentry.fixture_capture_queue, "export_capture_queue_csv")

    def test_import_policy_engine(self):
        from marketsentry.source_adapters.policy import evaluate_retrieval_policy
        assert callable(evaluate_retrieval_policy)

    def test_import_robots_policy(self):
        from marketsentry.source_adapters.robots_policy import (
            parse_robots_text,
            check_robots_allowed,
            load_local_robots_policy,
        )
        assert callable(parse_robots_text)
        assert callable(check_robots_allowed)
        assert callable(load_local_robots_policy)

    def test_import_rate_limiter(self):
        from marketsentry.source_adapters.rate_limiter import (
            check_rate_limit,
            record_retrieval_attempt,
        )
        assert callable(check_rate_limit)
        assert callable(record_retrieval_attempt)

    def test_import_dry_run_approval(self):
        from marketsentry.source_adapters.dry_run_approval import (
            record_dry_run_approval,
            has_recent_dry_run_approval,
        )
        assert callable(record_dry_run_approval)
        assert callable(has_recent_dry_run_approval)

    def test_import_audit_report(self):
        from marketsentry.source_adapters.audit_report import generate_audit_report
        assert callable(generate_audit_report)
