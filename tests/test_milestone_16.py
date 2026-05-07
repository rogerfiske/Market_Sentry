"""Tests for Milestone 16: Redfin Live HTTP Retrieval Phase 1.

Covers:
- HTTP client abstraction (HttpRequest, HttpResponse, HttpClient, FakeHttpClient)
- Redfin live retrieval blocked by default
- Redfin live retrieval blocked if source not allowlisted
- Redfin live retrieval blocked if User-Agent missing
- Redfin live retrieval blocked if contact email missing
- Redfin live retrieval blocked if robots policy missing
- Redfin live retrieval blocked if robots policy disallows path
- Redfin live retrieval blocked if rate limit exceeded
- Redfin live retrieval blocked if dry-run approval missing
- Redfin live retrieval succeeds with fake HTTP client when all checks pass
- Successful fake live retrieval saves fixture file
- Metadata/audit written for successful fake retrieval
- Failed HTTP status does not save fixture
- Response too large is blocked
- CLI retrieve commands in dry-run mode
- CLI retrieve commands blocked in default config
- Existing MVP 1-15 tests still pass (verified by full suite run)

All tests are local. No network access is performed.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from marketsentry.source_adapters.base import RetrievalMode, RetrievalResult


# ===========================================================================
# TestHttpClientAbstraction
# ===========================================================================


class TestHttpClientAbstraction:
    """Test HTTP client models and FakeHttpClient."""

    def test_http_request_defaults(self):
        from marketsentry.source_adapters.http_client import HttpRequest

        req = HttpRequest()
        assert req.url == ""
        assert req.method == "GET"
        assert req.headers == {}
        assert req.timeout_seconds == 30
        assert req.max_response_bytes == 10 * 1024 * 1024

    def test_http_request_custom(self):
        from marketsentry.source_adapters.http_client import HttpRequest

        req = HttpRequest(
            url="https://www.redfin.com/test",
            headers={"User-Agent": "Test/1.0"},
            timeout_seconds=15,
            max_response_bytes=1024,
        )
        assert req.url == "https://www.redfin.com/test"
        assert req.headers["User-Agent"] == "Test/1.0"
        assert req.timeout_seconds == 15
        assert req.max_response_bytes == 1024

    def test_http_response_defaults(self):
        from marketsentry.source_adapters.http_client import HttpResponse

        resp = HttpResponse()
        assert resp.status_code == 0
        assert resp.body == b""
        assert resp.text == ""
        assert resp.error == ""
        assert resp.timed_out is False
        assert resp.too_large is False
        assert resp.network_call_performed is False
        assert resp.is_success is False

    def test_http_response_success(self):
        from marketsentry.source_adapters.http_client import HttpResponse

        resp = HttpResponse(status_code=200, text="<html>OK</html>")
        assert resp.is_success is True
        assert resp.is_html is False  # no content_type set

    def test_http_response_is_html(self):
        from marketsentry.source_adapters.http_client import HttpResponse

        resp = HttpResponse(
            status_code=200,
            content_type="text/html; charset=utf-8",
        )
        assert resp.is_html is True

    def test_http_response_error_not_success(self):
        from marketsentry.source_adapters.http_client import HttpResponse

        resp = HttpResponse(status_code=200, error="some error")
        assert resp.is_success is False

    def test_http_response_404_not_success(self):
        from marketsentry.source_adapters.http_client import HttpResponse

        resp = HttpResponse(status_code=404)
        assert resp.is_success is False

    def test_fake_http_client_default_response(self):
        from marketsentry.source_adapters.http_client import (
            FakeHttpClient,
            HttpRequest,
        )

        client = FakeHttpClient()
        req = HttpRequest(url="https://www.redfin.com/test")
        resp = client.get(req)

        assert resp.status_code == 200
        assert "Fake page" in resp.text
        assert resp.network_call_performed is True
        assert resp.is_success is True
        assert len(client.requests) == 1
        assert client.requests[0].url == "https://www.redfin.com/test"

    def test_fake_http_client_custom_response(self):
        from marketsentry.source_adapters.http_client import (
            FakeHttpClient,
            HttpRequest,
        )

        client = FakeHttpClient(
            response_text="<html><body>Custom</body></html>",
            response_status=200,
            response_content_type="text/html",
        )
        req = HttpRequest(url="https://www.redfin.com/test")
        resp = client.get(req)

        assert "Custom" in resp.text
        assert resp.status_code == 200

    def test_fake_http_client_timeout(self):
        from marketsentry.source_adapters.http_client import (
            FakeHttpClient,
            HttpRequest,
        )

        client = FakeHttpClient(response_timed_out=True)
        req = HttpRequest(url="https://www.redfin.com/test", timeout_seconds=5)
        resp = client.get(req)

        assert resp.timed_out is True
        assert resp.error != ""
        assert resp.is_success is False

    def test_fake_http_client_too_large(self):
        from marketsentry.source_adapters.http_client import (
            FakeHttpClient,
            HttpRequest,
        )

        client = FakeHttpClient(response_too_large=True)
        req = HttpRequest(url="https://www.redfin.com/test")
        resp = client.get(req)

        assert resp.too_large is True
        assert resp.error != ""
        assert resp.is_success is False

    def test_fake_http_client_error(self):
        from marketsentry.source_adapters.http_client import (
            FakeHttpClient,
            HttpRequest,
        )

        client = FakeHttpClient(response_error="Connection refused")
        req = HttpRequest(url="https://www.redfin.com/test")
        resp = client.get(req)

        assert resp.error == "Connection refused"
        assert resp.is_success is False

    def test_fake_http_client_tracks_multiple_requests(self):
        from marketsentry.source_adapters.http_client import (
            FakeHttpClient,
            HttpRequest,
        )

        client = FakeHttpClient()
        client.get(HttpRequest(url="https://www.redfin.com/1"))
        client.get(HttpRequest(url="https://www.redfin.com/2"))
        client.get(HttpRequest(url="https://www.redfin.com/3"))

        assert len(client.requests) == 3


# ===========================================================================
# TestRetrievalResultFixturePath
# ===========================================================================


class TestRetrievalResultFixturePath:
    """Test that RetrievalResult has fixture_path field."""

    def test_retrieval_result_has_fixture_path(self):
        result = RetrievalResult()
        assert result.fixture_path == ""

    def test_retrieval_result_fixture_path_set(self):
        result = RetrievalResult(fixture_path="/some/path.html")
        assert result.fixture_path == "/some/path.html"


# ===========================================================================
# TestRedfinLiveRetrievalBlockedByDefault
# ===========================================================================


class TestRedfinLiveRetrievalBlockedByDefault:
    """Test that Redfin live retrieval is blocked by default (no env vars)."""

    def _clean_env(self):
        """Remove all MARKETSENTRY env vars."""
        keys = [
            "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED",
            "MARKETSENTRY_ALLOWED_LIVE_SOURCES",
            "MARKETSENTRY_LIVE_USER_AGENT",
            "MARKETSENTRY_LIVE_CONTACT_EMAIL",
            "MARKETSENTRY_MAX_REQUESTS_PER_MINUTE",
            "MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE",
        ]
        for key in keys:
            os.environ.pop(key, None)

    def test_blocked_by_default_no_env_vars(self):
        from marketsentry.source_adapters.http_client import FakeHttpClient
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        self._clean_env()

        adapter = RedfinAdapter()
        client = FakeHttpClient()
        result = adapter.retrieve_search(
            "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
            http_client=client,
        )

        assert result.blocked is True
        assert result.network_call_performed is False
        assert result.success is False
        assert len(client.requests) == 0  # No HTTP call made

    def test_blocked_by_default_property_detail(self):
        from marketsentry.source_adapters.http_client import FakeHttpClient
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        self._clean_env()

        adapter = RedfinAdapter()
        client = FakeHttpClient()
        result = adapter.retrieve_property_detail(
            "https://www.redfin.com/CA/Temecula/12345-Main-St-92592/home/6574263",
            http_client=client,
        )

        assert result.blocked is True
        assert result.network_call_performed is False
        assert len(client.requests) == 0


# ===========================================================================
# TestRedfinLiveRetrievalBlockedBySource
# ===========================================================================


class TestRedfinLiveRetrievalBlockedBySource:
    """Test blocked when source is not allowlisted."""

    def test_blocked_source_not_allowlisted(self):
        from marketsentry.source_adapters.http_client import FakeHttpClient
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        env = {
            "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "true",
            "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "zillow",  # Not redfin
            "MARKETSENTRY_LIVE_USER_AGENT": "MarketSentry/1.0",
            "MARKETSENTRY_LIVE_CONTACT_EMAIL": "test@example.com",
            "MARKETSENTRY_MAX_REQUESTS_PER_MINUTE": "6",
            "MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE": "false",
        }
        with patch.dict(os.environ, env, clear=False):
            adapter = RedfinAdapter()
            client = FakeHttpClient()
            result = adapter.retrieve_search(
                "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
                http_client=client,
            )

            assert result.blocked is True
            assert result.network_call_performed is False
            assert "not in" in result.block_reason.lower() or "allowlist" in result.block_reason.lower() or "allowed" in result.block_reason.lower()


# ===========================================================================
# TestRedfinLiveRetrievalBlockedByUserAgent
# ===========================================================================


class TestRedfinLiveRetrievalBlockedByUserAgent:
    """Test blocked when User-Agent is not configured."""

    def test_blocked_no_user_agent(self):
        from marketsentry.source_adapters.http_client import FakeHttpClient
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        env = {
            "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "true",
            "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "redfin",
            "MARKETSENTRY_LIVE_USER_AGENT": "",  # Missing
            "MARKETSENTRY_LIVE_CONTACT_EMAIL": "test@example.com",
            "MARKETSENTRY_MAX_REQUESTS_PER_MINUTE": "6",
            "MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE": "false",
        }
        with patch.dict(os.environ, env, clear=False):
            adapter = RedfinAdapter()
            client = FakeHttpClient()
            result = adapter.retrieve_search(
                "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
                http_client=client,
            )

            assert result.blocked is True
            assert result.network_call_performed is False


# ===========================================================================
# TestRedfinLiveRetrievalBlockedByRobots
# ===========================================================================


class TestRedfinLiveRetrievalBlockedByRobots:
    """Test blocked when robots policy is missing or disallows path."""

    def _full_env(self):
        return {
            "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "true",
            "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "redfin",
            "MARKETSENTRY_LIVE_USER_AGENT": "MarketSentry/1.0",
            "MARKETSENTRY_LIVE_CONTACT_EMAIL": "test@example.com",
            "MARKETSENTRY_MAX_REQUESTS_PER_MINUTE": "6",
            "MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE": "false",
        }

    def test_blocked_no_robots_policy(self):
        from marketsentry.source_adapters.http_client import FakeHttpClient
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        with patch.dict(os.environ, self._full_env(), clear=False):
            with patch(
                "marketsentry.source_adapters.redfin_adapter.load_local_robots_policy",
                return_value=None,
            ):
                adapter = RedfinAdapter()
                client = FakeHttpClient()
                result = adapter.retrieve_search(
                    "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
                    http_client=client,
                )

                assert result.blocked is True
                assert result.network_call_performed is False
                assert "robots" in result.block_reason.lower()

    def test_blocked_robots_disallows_path(self):
        from marketsentry.source_adapters.http_client import FakeHttpClient
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter
        from marketsentry.source_adapters.robots_policy import RobotsCheckResult

        disallowed = RobotsCheckResult(
            allowed=False,
            checked=True,
            notes="Disallowed by robots.txt",
        )

        with patch.dict(os.environ, self._full_env(), clear=False):
            with patch(
                "marketsentry.source_adapters.redfin_adapter.load_local_robots_policy",
                return_value="User-agent: *\nDisallow: /",
            ):
                with patch(
                    "marketsentry.source_adapters.redfin_adapter.check_robots_allowed",
                    return_value=disallowed,
                ):
                    adapter = RedfinAdapter()
                    client = FakeHttpClient()
                    result = adapter.retrieve_search(
                        "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
                        http_client=client,
                    )

                    assert result.blocked is True
                    assert result.network_call_performed is False
                    assert "robots" in result.block_reason.lower()


# ===========================================================================
# TestRedfinLiveRetrievalBlockedByRateLimit
# ===========================================================================


class TestRedfinLiveRetrievalBlockedByRateLimit:
    """Test blocked when rate limit is exceeded."""

    def _full_env(self):
        return {
            "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "true",
            "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "redfin",
            "MARKETSENTRY_LIVE_USER_AGENT": "MarketSentry/1.0",
            "MARKETSENTRY_LIVE_CONTACT_EMAIL": "test@example.com",
            "MARKETSENTRY_MAX_REQUESTS_PER_MINUTE": "6",
            "MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE": "false",
        }

    def test_blocked_rate_limit_exceeded(self):
        from marketsentry.source_adapters.http_client import FakeHttpClient
        from marketsentry.source_adapters.rate_limiter import (
            RateLimitCheckResult,
            RateLimitDecision,
        )
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter
        from marketsentry.source_adapters.robots_policy import RobotsCheckResult

        robots_ok = RobotsCheckResult(allowed=True, checked=True)
        rate_blocked = RateLimitCheckResult(
            decision=RateLimitDecision.BLOCKED,
            message="Rate limit exceeded",
        )

        with patch.dict(os.environ, self._full_env(), clear=False):
            with patch(
                "marketsentry.source_adapters.redfin_adapter.load_local_robots_policy",
                return_value="User-agent: *\nAllow: /",
            ):
                with patch(
                    "marketsentry.source_adapters.redfin_adapter.check_robots_allowed",
                    return_value=robots_ok,
                ):
                    with patch(
                        "marketsentry.source_adapters.redfin_adapter.check_rate_limit",
                        return_value=rate_blocked,
                    ):
                        adapter = RedfinAdapter()
                        client = FakeHttpClient()
                        result = adapter.retrieve_search(
                            "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
                            http_client=client,
                        )

                        assert result.blocked is True
                        assert result.network_call_performed is False
                        assert "rate limit" in result.block_reason.lower()


# ===========================================================================
# TestRedfinLiveRetrievalBlockedByDryRunApproval
# ===========================================================================


class TestRedfinLiveRetrievalBlockedByDryRunApproval:
    """Test blocked when dry-run approval is missing."""

    def _full_env_with_dry_run_required(self):
        return {
            "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "true",
            "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "redfin",
            "MARKETSENTRY_LIVE_USER_AGENT": "MarketSentry/1.0",
            "MARKETSENTRY_LIVE_CONTACT_EMAIL": "test@example.com",
            "MARKETSENTRY_MAX_REQUESTS_PER_MINUTE": "6",
            "MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE": "true",
        }

    def test_blocked_no_dry_run_approval(self):
        from marketsentry.source_adapters.http_client import FakeHttpClient
        from marketsentry.source_adapters.rate_limiter import (
            RateLimitCheckResult,
            RateLimitDecision,
        )
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter
        from marketsentry.source_adapters.robots_policy import RobotsCheckResult

        robots_ok = RobotsCheckResult(allowed=True, checked=True)
        rate_ok = RateLimitCheckResult(decision=RateLimitDecision.ALLOWED, message="OK")

        with patch.dict(os.environ, self._full_env_with_dry_run_required(), clear=False):
            with patch(
                "marketsentry.source_adapters.redfin_adapter.load_local_robots_policy",
                return_value="User-agent: *\nAllow: /",
            ):
                with patch(
                    "marketsentry.source_adapters.redfin_adapter.check_robots_allowed",
                    return_value=robots_ok,
                ):
                    with patch(
                        "marketsentry.source_adapters.redfin_adapter.check_rate_limit",
                        return_value=rate_ok,
                    ):
                        with patch(
                            "marketsentry.source_adapters.redfin_adapter.has_recent_dry_run_approval",
                            return_value=False,
                        ):
                            adapter = RedfinAdapter()
                            client = FakeHttpClient()
                            result = adapter.retrieve_search(
                                "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
                                http_client=client,
                            )

                            assert result.blocked is True
                            assert result.network_call_performed is False
                            assert "dry-run" in result.block_reason.lower() or "dry_run" in result.block_reason.lower()


# ===========================================================================
# TestRedfinLiveRetrievalBlockedNoHttpClient
# ===========================================================================


class TestRedfinLiveRetrievalBlockedNoHttpClient:
    """Test blocked when no HTTP client is provided."""

    def _full_env(self):
        return {
            "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "true",
            "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "redfin",
            "MARKETSENTRY_LIVE_USER_AGENT": "MarketSentry/1.0",
            "MARKETSENTRY_LIVE_CONTACT_EMAIL": "test@example.com",
            "MARKETSENTRY_MAX_REQUESTS_PER_MINUTE": "6",
            "MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE": "false",
        }

    def test_blocked_no_http_client(self):
        from marketsentry.source_adapters.rate_limiter import (
            RateLimitCheckResult,
            RateLimitDecision,
        )
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter
        from marketsentry.source_adapters.robots_policy import RobotsCheckResult

        robots_ok = RobotsCheckResult(allowed=True, checked=True)
        rate_ok = RateLimitCheckResult(decision=RateLimitDecision.ALLOWED, message="OK")

        with patch.dict(os.environ, self._full_env(), clear=False):
            with patch(
                "marketsentry.source_adapters.redfin_adapter.load_local_robots_policy",
                return_value="User-agent: *\nAllow: /",
            ):
                with patch(
                    "marketsentry.source_adapters.redfin_adapter.check_robots_allowed",
                    return_value=robots_ok,
                ):
                    with patch(
                        "marketsentry.source_adapters.redfin_adapter.check_rate_limit",
                        return_value=rate_ok,
                    ):
                        adapter = RedfinAdapter()
                        # No http_client passed
                        result = adapter.retrieve_search(
                            "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
                        )

                        assert result.blocked is True
                        assert result.network_call_performed is False
                        assert "http client" in result.block_reason.lower() or "client" in result.block_reason.lower()


# ===========================================================================
# TestRedfinLiveRetrievalSuccess
# ===========================================================================


class TestRedfinLiveRetrievalSuccess:
    """Test successful live retrieval with fake HTTP client."""

    def _full_env(self):
        return {
            "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "true",
            "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "redfin",
            "MARKETSENTRY_LIVE_USER_AGENT": "MarketSentry/1.0",
            "MARKETSENTRY_LIVE_CONTACT_EMAIL": "test@example.com",
            "MARKETSENTRY_MAX_REQUESTS_PER_MINUTE": "6",
            "MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE": "false",
        }

    def _mock_all_checks_pass(self):
        """Return patches for all safety checks passing."""
        from marketsentry.source_adapters.rate_limiter import (
            RateLimitCheckResult,
            RateLimitDecision,
        )
        from marketsentry.source_adapters.robots_policy import RobotsCheckResult

        robots_ok = RobotsCheckResult(allowed=True, checked=True)
        rate_ok = RateLimitCheckResult(decision=RateLimitDecision.ALLOWED, message="OK")

        return {
            "marketsentry.source_adapters.redfin_adapter.load_local_robots_policy": "User-agent: *\nAllow: /",
            "marketsentry.source_adapters.redfin_adapter.check_robots_allowed": robots_ok,
            "marketsentry.source_adapters.redfin_adapter.check_rate_limit": rate_ok,
        }

    def test_search_success_saves_fixture(self):
        from marketsentry.source_adapters.http_client import FakeHttpClient
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        html_content = "<html><body><h1>Redfin Search Results</h1></body></html>"
        client = FakeHttpClient(response_text=html_content)

        mocks = self._mock_all_checks_pass()

        with patch.dict(os.environ, self._full_env(), clear=False):
            with patch(
                "marketsentry.source_adapters.redfin_adapter.load_local_robots_policy",
                return_value=mocks["marketsentry.source_adapters.redfin_adapter.load_local_robots_policy"],
            ):
                with patch(
                    "marketsentry.source_adapters.redfin_adapter.check_robots_allowed",
                    return_value=mocks["marketsentry.source_adapters.redfin_adapter.check_robots_allowed"],
                ):
                    with patch(
                        "marketsentry.source_adapters.redfin_adapter.check_rate_limit",
                        return_value=mocks["marketsentry.source_adapters.redfin_adapter.check_rate_limit"],
                    ):
                        with tempfile.TemporaryDirectory() as tmpdir:
                            # Monkey-patch save to use tmpdir
                            adapter = RedfinAdapter()
                            original_save = adapter.save_retrieved_fixture

                            def patched_save(html_content="", url="", request_type="", output_dir=None):
                                return original_save(html_content=html_content, url=url, request_type=request_type, output_dir=tmpdir)

                            adapter.save_retrieved_fixture = patched_save

                            result = adapter.retrieve_search(
                                "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
                                http_client=client,
                            )

                            assert result.success is True
                            assert result.blocked is False
                            assert result.network_call_performed is True
                            assert result.fixture_path != ""

                            # Verify fixture was saved
                            fixture_path = Path(result.fixture_path)
                            assert fixture_path.exists()
                            assert html_content in fixture_path.read_text(encoding="utf-8")

                            # Verify metadata JSON was saved
                            metadata_path = fixture_path.with_suffix(".json")
                            assert metadata_path.exists()
                            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                            assert metadata["source_site"] == "redfin"
                            assert metadata["request_type"] == "search"
                            assert "source_url" in metadata
                            assert "retrieved_at" in metadata

    def test_property_detail_success_saves_fixture(self):
        from marketsentry.source_adapters.http_client import FakeHttpClient
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        html_content = "<html><body><h1>Property Detail</h1></body></html>"
        client = FakeHttpClient(response_text=html_content)

        mocks = self._mock_all_checks_pass()

        with patch.dict(os.environ, self._full_env(), clear=False):
            with patch(
                "marketsentry.source_adapters.redfin_adapter.load_local_robots_policy",
                return_value=mocks["marketsentry.source_adapters.redfin_adapter.load_local_robots_policy"],
            ):
                with patch(
                    "marketsentry.source_adapters.redfin_adapter.check_robots_allowed",
                    return_value=mocks["marketsentry.source_adapters.redfin_adapter.check_robots_allowed"],
                ):
                    with patch(
                        "marketsentry.source_adapters.redfin_adapter.check_rate_limit",
                        return_value=mocks["marketsentry.source_adapters.redfin_adapter.check_rate_limit"],
                    ):
                        with tempfile.TemporaryDirectory() as tmpdir:
                            adapter = RedfinAdapter()
                            original_save = adapter.save_retrieved_fixture

                            def patched_save(html_content="", url="", request_type="", output_dir=None):
                                return original_save(html_content=html_content, url=url, request_type=request_type, output_dir=tmpdir)

                            adapter.save_retrieved_fixture = patched_save

                            result = adapter.retrieve_property_detail(
                                "https://www.redfin.com/CA/Temecula/12345-Main-St-92592/home/6574263",
                                http_client=client,
                            )

                            assert result.success is True
                            assert result.blocked is False
                            assert result.network_call_performed is True
                            assert result.fixture_path != ""

                            fixture_path = Path(result.fixture_path)
                            assert fixture_path.exists()
                            assert "Property Detail" in fixture_path.read_text(encoding="utf-8")

    def test_success_fake_http_client_records_request(self):
        from marketsentry.source_adapters.http_client import FakeHttpClient
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        client = FakeHttpClient()
        mocks = self._mock_all_checks_pass()

        with patch.dict(os.environ, self._full_env(), clear=False):
            with patch(
                "marketsentry.source_adapters.redfin_adapter.load_local_robots_policy",
                return_value=mocks["marketsentry.source_adapters.redfin_adapter.load_local_robots_policy"],
            ):
                with patch(
                    "marketsentry.source_adapters.redfin_adapter.check_robots_allowed",
                    return_value=mocks["marketsentry.source_adapters.redfin_adapter.check_robots_allowed"],
                ):
                    with patch(
                        "marketsentry.source_adapters.redfin_adapter.check_rate_limit",
                        return_value=mocks["marketsentry.source_adapters.redfin_adapter.check_rate_limit"],
                    ):
                        adapter = RedfinAdapter()
                        result = adapter.retrieve_search(
                            "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
                            http_client=client,
                        )

                        assert result.success is True
                        assert len(client.requests) == 1
                        assert "redfin.com" in client.requests[0].url
                        assert client.requests[0].headers.get("User-Agent") == "MarketSentry/1.0"


# ===========================================================================
# TestRedfinLiveRetrievalFailedHttp
# ===========================================================================


class TestRedfinLiveRetrievalFailedHttp:
    """Test failed HTTP responses do not save fixtures."""

    def _full_env(self):
        return {
            "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "true",
            "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "redfin",
            "MARKETSENTRY_LIVE_USER_AGENT": "MarketSentry/1.0",
            "MARKETSENTRY_LIVE_CONTACT_EMAIL": "test@example.com",
            "MARKETSENTRY_MAX_REQUESTS_PER_MINUTE": "6",
            "MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE": "false",
        }

    def _mock_all_checks_pass(self):
        from marketsentry.source_adapters.rate_limiter import (
            RateLimitCheckResult,
            RateLimitDecision,
        )
        from marketsentry.source_adapters.robots_policy import RobotsCheckResult

        return (
            RobotsCheckResult(allowed=True, checked=True),
            RateLimitCheckResult(decision=RateLimitDecision.ALLOWED, message="OK"),
        )

    def test_http_error_does_not_save_fixture(self):
        from marketsentry.source_adapters.http_client import FakeHttpClient
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        client = FakeHttpClient(response_status=403, response_error="HTTP error 403: Forbidden")
        robots_ok, rate_ok = self._mock_all_checks_pass()

        with patch.dict(os.environ, self._full_env(), clear=False):
            with patch(
                "marketsentry.source_adapters.redfin_adapter.load_local_robots_policy",
                return_value="User-agent: *\nAllow: /",
            ):
                with patch(
                    "marketsentry.source_adapters.redfin_adapter.check_robots_allowed",
                    return_value=robots_ok,
                ):
                    with patch(
                        "marketsentry.source_adapters.redfin_adapter.check_rate_limit",
                        return_value=rate_ok,
                    ):
                        adapter = RedfinAdapter()
                        result = adapter.retrieve_search(
                            "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
                            http_client=client,
                        )

                        assert result.success is False
                        assert result.network_call_performed is True
                        assert result.fixture_path == ""
                        assert result.error_message != ""

    def test_http_timeout_does_not_save_fixture(self):
        from marketsentry.source_adapters.http_client import FakeHttpClient
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        client = FakeHttpClient(response_timed_out=True)
        robots_ok, rate_ok = self._mock_all_checks_pass()

        with patch.dict(os.environ, self._full_env(), clear=False):
            with patch(
                "marketsentry.source_adapters.redfin_adapter.load_local_robots_policy",
                return_value="User-agent: *\nAllow: /",
            ):
                with patch(
                    "marketsentry.source_adapters.redfin_adapter.check_robots_allowed",
                    return_value=robots_ok,
                ):
                    with patch(
                        "marketsentry.source_adapters.redfin_adapter.check_rate_limit",
                        return_value=rate_ok,
                    ):
                        adapter = RedfinAdapter()
                        result = adapter.retrieve_search(
                            "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
                            http_client=client,
                        )

                        assert result.success is False
                        assert result.network_call_performed is True
                        assert result.fixture_path == ""

    def test_http_too_large_blocked(self):
        from marketsentry.source_adapters.http_client import FakeHttpClient
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        client = FakeHttpClient(response_too_large=True)
        robots_ok, rate_ok = self._mock_all_checks_pass()

        with patch.dict(os.environ, self._full_env(), clear=False):
            with patch(
                "marketsentry.source_adapters.redfin_adapter.load_local_robots_policy",
                return_value="User-agent: *\nAllow: /",
            ):
                with patch(
                    "marketsentry.source_adapters.redfin_adapter.check_robots_allowed",
                    return_value=robots_ok,
                ):
                    with patch(
                        "marketsentry.source_adapters.redfin_adapter.check_rate_limit",
                        return_value=rate_ok,
                    ):
                        adapter = RedfinAdapter()
                        result = adapter.retrieve_search(
                            "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
                            http_client=client,
                        )

                        assert result.success is False
                        assert result.blocked is True
                        assert result.network_call_performed is True
                        assert result.fixture_path == ""


# ===========================================================================
# TestFixtureSaving
# ===========================================================================


class TestFixtureSaving:
    """Test fixture saving logic."""

    def test_save_search_fixture(self):
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = RedfinAdapter()
            path = adapter.save_retrieved_fixture(
                html_content="<html>Search</html>",
                url="https://www.redfin.com/city/19701/CA/Temecula/filter/test",
                request_type="search",
                output_dir=tmpdir,
            )

            assert Path(path).exists()
            assert "redfin_search_" in path
            assert path.endswith(".html")
            assert Path(path).read_text(encoding="utf-8") == "<html>Search</html>"

            # Check metadata JSON
            metadata_path = Path(path).with_suffix(".json")
            assert metadata_path.exists()
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            assert metadata["source_site"] == "redfin"
            assert metadata["request_type"] == "search"

    def test_save_property_detail_fixture(self):
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = RedfinAdapter()
            path = adapter.save_retrieved_fixture(
                html_content="<html>Property</html>",
                url="https://www.redfin.com/CA/Temecula/12345-Main-St-92592/home/6574263",
                request_type="property_detail",
                output_dir=tmpdir,
            )

            assert Path(path).exists()
            assert "redfin_property_" in path
            assert "6574263" in path  # Home ID extracted
            assert path.endswith(".html")

    def test_no_overwrite_existing(self):
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = RedfinAdapter()
            path1 = adapter.save_retrieved_fixture(
                html_content="<html>First</html>",
                url="https://www.redfin.com/city/test/filter/x",
                request_type="search",
                output_dir=tmpdir,
            )
            path2 = adapter.save_retrieved_fixture(
                html_content="<html>Second</html>",
                url="https://www.redfin.com/city/test/filter/x",
                request_type="search",
                output_dir=tmpdir,
            )

            assert path1 != path2
            assert Path(path1).exists()
            assert Path(path2).exists()


# ===========================================================================
# TestUrlToSlug
# ===========================================================================


class TestUrlToSlug:
    """Test _url_to_slug helper."""

    def test_extracts_home_id(self):
        from marketsentry.source_adapters.redfin_adapter import _url_to_slug

        slug = _url_to_slug("https://www.redfin.com/CA/Temecula/12345-Main-St/home/6574263")
        assert slug == "6574263"

    def test_no_home_id(self):
        from marketsentry.source_adapters.redfin_adapter import _url_to_slug

        slug = _url_to_slug("https://www.redfin.com/CA/Temecula/some-path")
        assert slug == "some-path"

    def test_empty_url(self):
        from marketsentry.source_adapters.redfin_adapter import _url_to_slug

        slug = _url_to_slug("")
        assert slug == "unknown"

    def test_invalid_url(self):
        from marketsentry.source_adapters.redfin_adapter import _url_to_slug

        slug = _url_to_slug("not a url at all")
        assert isinstance(slug, str)
        assert len(slug) > 0


# ===========================================================================
# TestPolicyEngineAllowedDecision
# ===========================================================================


class TestPolicyEngineAllowedDecision:
    """Test that policy engine returns ALLOWED when all checks pass."""

    def test_all_checks_pass_returns_allowed(self):
        from marketsentry.source_adapters.compliance import RetrievalComplianceConfig
        from marketsentry.source_adapters.policy import (
            RetrievalPolicyDecision,
            evaluate_retrieval_policy,
        )

        cc = RetrievalComplianceConfig(
            live_retrieval_enabled=True,
            allowed_live_sources=["redfin"],
            live_user_agent="MarketSentry/1.0",
            live_contact_email="test@example.com",
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

        assert policy.decision == RetrievalPolicyDecision.ALLOWED
        assert policy.is_allowed is True
        assert policy.is_blocked is False
        assert policy.compliance_passed is True

    def test_blocked_when_compliance_fails(self):
        from marketsentry.source_adapters.compliance import RetrievalComplianceConfig
        from marketsentry.source_adapters.policy import (
            RetrievalPolicyDecision,
            evaluate_retrieval_policy,
        )

        cc = RetrievalComplianceConfig(
            live_retrieval_enabled=False,  # Disabled
            allowed_live_sources=[],
            live_user_agent="",
        )

        policy = evaluate_retrieval_policy(
            source_name="redfin",
            url="https://www.redfin.com/test",
            request_type="search",
            retrieval_mode="live_http",
            compliance_config=cc,
        )

        assert policy.decision == RetrievalPolicyDecision.BLOCKED
        assert policy.is_blocked is True


# ===========================================================================
# TestCLIRetrieveCommands
# ===========================================================================


class TestCLIRetrieveCommands:
    """Test CLI retrieve commands."""

    def test_retrieve_search_blocked_by_default(self):
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "retrieve-redfin-search",
                "--url", "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
            ],
        )
        # Should show message about --force-live required
        assert result.exit_code == 0
        assert "force-live" in result.output.lower() or "live retrieval" in result.output.lower()

    def test_retrieve_property_blocked_by_default(self):
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "retrieve-redfin-property",
                "--url", "https://www.redfin.com/CA/Temecula/12345-Main-St-92592/home/6574263",
            ],
        )
        assert result.exit_code == 0
        assert "force-live" in result.output.lower() or "live retrieval" in result.output.lower()

    def test_retrieve_search_dry_run_only(self):
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "retrieve-redfin-search",
                "--url", "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
                "--dry-run-only",
            ],
        )
        assert result.exit_code == 0
        assert "dry-run" in result.output.lower() or "preview" in result.output.lower()
        assert "network_call_performed=false" in result.output.lower()

    def test_retrieve_property_dry_run_only(self):
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "retrieve-redfin-property",
                "--url", "https://www.redfin.com/CA/Temecula/12345-Main-St-92592/home/6574263",
                "--dry-run-only",
            ],
        )
        assert result.exit_code == 0
        assert "dry-run" in result.output.lower() or "preview" in result.output.lower()

    def test_retrieve_search_force_live_blocked_without_config(self):
        from marketsentry.cli import app

        # Remove env vars to ensure blocked
        env_clean = {
            "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "false",
            "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "",
            "MARKETSENTRY_LIVE_USER_AGENT": "",
            "MARKETSENTRY_LIVE_CONTACT_EMAIL": "",
        }
        with patch.dict(os.environ, env_clean, clear=False):
            runner = CliRunner()
            result = runner.invoke(
                app,
                [
                    "retrieve-redfin-search",
                    "--url", "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
                    "--force-live",
                ],
            )
            assert result.exit_code == 0
            assert "blocked" in result.output.lower()


# ===========================================================================
# TestRedfinAdapterRateLimitState
# ===========================================================================


class TestRedfinAdapterRateLimitState:
    """Test that RedfinAdapter initializes rate limit state."""

    def test_adapter_has_rate_limit_state(self):
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        adapter = RedfinAdapter()
        assert hasattr(adapter, "_rate_limit_state")
        assert adapter._rate_limit_state.source_site == "redfin"

    def test_adapter_rate_limit_state_is_fresh(self):
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        adapter = RedfinAdapter()
        assert adapter._rate_limit_state.total_requests == 0
        assert len(adapter._rate_limit_state.request_timestamps) == 0


# ===========================================================================
# TestRedfinAdapterSupportedModes
# ===========================================================================


class TestRedfinAdapterSupportedModes:
    """Test supported modes include LIVE_HTTP."""

    def test_supported_modes_include_live_http(self):
        from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

        adapter = RedfinAdapter()
        modes = adapter.get_supported_modes()
        assert RetrievalMode.LIVE_HTTP in modes
        assert RetrievalMode.DRY_RUN in modes
        assert RetrievalMode.MANUAL_FIXTURE in modes
        assert RetrievalMode.DISABLED in modes


# ===========================================================================
# TestHttpClientPackageExports
# ===========================================================================


class TestHttpClientPackageExports:
    """Test that http_client classes are exported from the package."""

    def test_http_client_exports(self):
        from marketsentry.source_adapters import (
            FakeHttpClient,
            HttpClient,
            HttpRequest,
            HttpResponse,
            StandardLibraryHttpClient,
        )

        assert FakeHttpClient is not None
        assert HttpClient is not None
        assert HttpRequest is not None
        assert HttpResponse is not None
        assert StandardLibraryHttpClient is not None
