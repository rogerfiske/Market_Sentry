"""Tests for Milestone 18: Redfin Pending Capture Batch Retrieval Orchestrator.

Tests cover:
- Pending Redfin capture request filtering
- Dry-run batch performs no network calls
- Retrieve without force-live performs no network calls
- Force-live blocked when compliance/robots/dry-run/rate-limit fail
- Fake-client success saves fixtures
- retrieve_only does not process
- retrieve_and_process calls processing pipeline
- Queue items marked captured only after success
- Blocked items remain pending
- Batch manifest written
- Per-item manifest written
- CLI commands
- No real network calls

No real network calls in any test.
"""

import csv
import json
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# Helpers
# ===========================================================================


def _create_test_db(db_path: str) -> None:
    """Create a minimal test database with fixture capture queue table."""
    from marketsentry.database import init_db
    from marketsentry.fixture_capture_queue import ensure_fixture_capture_table

    init_db(db_path)
    ensure_fixture_capture_table(db_path)


def _add_pending_request(
    db_path: str,
    source_url: str,
    request_type: str = "property_detail",
    source_site: str = "redfin",
) -> int:
    """Insert a pending capture request and return its ID."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    normalized = source_url.lower().rstrip("/")
    cursor.execute(
        """
        INSERT INTO fixture_capture_queue (
            source_site, source_url, normalized_url, request_type,
            suggested_fixture_path, status, priority
        ) VALUES (?, ?, ?, ?, ?, 'pending', 5)
        """,
        (source_site, source_url, normalized, request_type, f"data/raw/{source_site}/"),
    )
    conn.commit()
    capture_id = cursor.lastrowid
    conn.close()
    return capture_id


def _get_request_status(db_path: str, capture_id: int) -> str:
    """Get the status of a capture request."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status FROM fixture_capture_queue WHERE capture_request_id = ?",
        (capture_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return row["status"] if row else ""


def _full_env():
    """Return environment variables for full live retrieval config."""
    return {
        "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "true",
        "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "redfin",
        "MARKETSENTRY_LIVE_USER_AGENT": "MarketSentry/1.0",
        "MARKETSENTRY_LIVE_CONTACT_EMAIL": "test@example.com",
        "MARKETSENTRY_MAX_REQUESTS_PER_MINUTE": "6",
        "MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE": "false",
    }


def _mock_all_checks_pass():
    """Return mock values for all safety checks passing."""
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


def _patch_adapter_for_success(tmpdir):
    """Create a patched RedfinAdapter that saves to tmpdir."""
    from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

    adapter = RedfinAdapter()
    original_save = adapter.save_retrieved_fixture

    def patched_save(html_content="", url="", request_type="", output_dir=None):
        return original_save(
            html_content=html_content,
            url=url,
            request_type=request_type,
            output_dir=tmpdir,
        )

    adapter.save_retrieved_fixture = patched_save
    return adapter


# ===========================================================================
# TestPendingRequestFiltering
# ===========================================================================


class TestPendingRequestFiltering:
    """Test filtering of pending Redfin capture requests."""

    def test_filter_redfin_only(self):
        from marketsentry.redfin_batch_retrieval import (
            get_pending_redfin_capture_requests,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            _add_pending_request(db_path, "https://www.redfin.com/CA/test/home/123", "property_detail")
            _add_pending_request(db_path, "https://www.zillow.com/test", "property_detail", "zillow")

            results = get_pending_redfin_capture_requests(database_path=db_path)
            assert len(results) == 1
            assert results[0]["source_site"] == "redfin"

    def test_filter_by_request_type(self):
        from marketsentry.redfin_batch_retrieval import (
            get_pending_redfin_capture_requests,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            _add_pending_request(db_path, "https://www.redfin.com/city/test", "search")
            _add_pending_request(db_path, "https://www.redfin.com/CA/test/home/123", "property_detail")

            search_only = get_pending_redfin_capture_requests(
                request_type="search", database_path=db_path
            )
            assert len(search_only) == 1
            assert search_only[0]["request_type"] == "search"

            detail_only = get_pending_redfin_capture_requests(
                request_type="property_detail", database_path=db_path
            )
            assert len(detail_only) == 1

    def test_max_items_limit(self):
        from marketsentry.redfin_batch_retrieval import (
            get_pending_redfin_capture_requests,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            for i in range(5):
                _add_pending_request(db_path, f"https://www.redfin.com/CA/test{i}/home/{i}", "property_detail")

            results = get_pending_redfin_capture_requests(max_items=2, database_path=db_path)
            assert len(results) == 2

    def test_empty_queue_returns_empty(self):
        from marketsentry.redfin_batch_retrieval import (
            get_pending_redfin_capture_requests,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            results = get_pending_redfin_capture_requests(database_path=db_path)
            assert len(results) == 0


# ===========================================================================
# TestDryRunBatch
# ===========================================================================


class TestDryRunBatch:
    """Test dry-run batch mode performs no network calls."""

    def test_dry_run_no_network_calls(self):
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            _add_pending_request(db_path, "https://www.redfin.com/CA/test/home/123", "property_detail")

            config = BatchRetrievalConfig(
                mode="dry_run_only",
                database_path=db_path,
            )

            batch_manifest = os.path.join(tmpdir, "batch.csv")
            item_manifest = os.path.join(tmpdir, "items.csv")

            result = retrieve_pending_redfin_capture_batch(
                config=config,
                batch_manifest_path=batch_manifest,
                item_manifest_path=item_manifest,
            )

            assert result.pending_scanned == 1
            assert result.dry_run_only_count == 1
            assert result.attempted_live == 0
            assert result.retrieved == 0
            assert result.fixtures_saved == 0
            # All items should have no network calls
            for item in result.items:
                assert item.network_call_performed is False
                assert item.status == "dry_run"

    def test_dry_run_leaves_items_pending(self):
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            cap_id = _add_pending_request(db_path, "https://www.redfin.com/CA/test/home/123", "property_detail")

            config = BatchRetrievalConfig(mode="dry_run_only", database_path=db_path)

            retrieve_pending_redfin_capture_batch(
                config=config,
                batch_manifest_path=os.path.join(tmpdir, "b.csv"),
                item_manifest_path=os.path.join(tmpdir, "i.csv"),
            )

            assert _get_request_status(db_path, cap_id) == "pending"


# ===========================================================================
# TestRetrieveWithoutForceLive
# ===========================================================================


class TestRetrieveWithoutForceLive:
    """Test that retrieve without force-live performs no network calls."""

    def test_no_force_live_blocks_all(self):
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            _add_pending_request(db_path, "https://www.redfin.com/CA/test/home/123", "property_detail")

            config = BatchRetrievalConfig(
                mode="retrieve_only",
                force_live=False,
                database_path=db_path,
            )

            result = retrieve_pending_redfin_capture_batch(
                config=config,
                batch_manifest_path=os.path.join(tmpdir, "b.csv"),
                item_manifest_path=os.path.join(tmpdir, "i.csv"),
            )

            assert result.pending_scanned == 1
            assert result.retrieved == 0
            assert result.blocked == 1
            for item in result.items:
                assert item.network_call_performed is False
                assert item.status == "blocked"
                assert "force-live" in item.reason.lower()


# ===========================================================================
# TestForceLiveBlocked
# ===========================================================================


class TestForceLiveBlocked:
    """Test force-live blocked when compliance/robots/rate-limit fail."""

    def test_force_live_blocked_when_compliance_fails(self):
        """Force-live with disabled env should block."""
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            _add_pending_request(db_path, "https://www.redfin.com/CA/test/home/123", "property_detail")

            # Compliance fails: retrieval disabled
            disabled_env = {"MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "false"}

            config = BatchRetrievalConfig(
                mode="retrieve_only",
                force_live=True,
                database_path=db_path,
            )

            with patch.dict(os.environ, disabled_env, clear=False):
                result = retrieve_pending_redfin_capture_batch(
                    config=config,
                    batch_manifest_path=os.path.join(tmpdir, "b.csv"),
                    item_manifest_path=os.path.join(tmpdir, "i.csv"),
                )

            assert result.retrieved == 0
            assert result.blocked >= 1 or result.failed >= 1

    def test_force_live_blocked_when_robots_missing(self):
        """Force-live with no local robots policy should block."""
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            _add_pending_request(db_path, "https://www.redfin.com/CA/test/home/123", "property_detail")

            config = BatchRetrievalConfig(
                mode="retrieve_only",
                force_live=True,
                database_path=db_path,
            )

            with patch.dict(os.environ, _full_env(), clear=False):
                # Robots policy loading will fail (no file at default path)
                result = retrieve_pending_redfin_capture_batch(
                    config=config,
                    batch_manifest_path=os.path.join(tmpdir, "b.csv"),
                    item_manifest_path=os.path.join(tmpdir, "i.csv"),
                )

            # Should be blocked due to missing robots
            assert result.retrieved == 0
            total_blocked_or_failed = result.blocked + result.failed
            assert total_blocked_or_failed >= 1

    def test_force_live_blocked_by_rate_limit(self):
        """Force-live with rate limit exceeded should block."""
        from marketsentry.redfin_batch_retrieval import (
            retrieve_pending_redfin_capture_request,
        )
        from marketsentry.source_adapters.rate_limiter import (
            RateLimitCheckResult,
            RateLimitDecision,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            cap_id = _add_pending_request(db_path, "https://www.redfin.com/CA/test/home/123", "property_detail")

            rate_blocked = RateLimitCheckResult(
                decision=RateLimitDecision.BLOCKED,
                message="Rate limit exceeded",
            )

            capture_request = {
                "capture_request_id": cap_id,
                "source_url": "https://www.redfin.com/CA/test/home/123",
                "request_type": "property_detail",
            }

            mocks = _mock_all_checks_pass()

            with patch.dict(os.environ, _full_env(), clear=False):
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
                            return_value=rate_blocked,
                        ):
                            result = retrieve_pending_redfin_capture_request(
                                capture_request=capture_request,
                                force_live=True,
                            )

            assert result.status in ("blocked", "failed")
            assert result.network_call_performed is False


# ===========================================================================
# TestFakeClientSuccess
# ===========================================================================


class TestFakeClientSuccess:
    """Test successful retrieval with fake HTTP client."""

    def test_fake_client_saves_fixture(self):
        from marketsentry.redfin_batch_retrieval import (
            retrieve_pending_redfin_capture_request,
        )
        from marketsentry.source_adapters.http_client import FakeHttpClient

        html_content = "<html><body><h1>Test Property</h1></body></html>"
        client = FakeHttpClient(response_text=html_content)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            cap_id = _add_pending_request(
                db_path, "https://www.redfin.com/CA/Temecula/123-Test-St-92592/home/6574263", "property_detail"
            )

            capture_request = {
                "capture_request_id": cap_id,
                "source_url": "https://www.redfin.com/CA/Temecula/123-Test-St-92592/home/6574263",
                "request_type": "property_detail",
            }

            adapter = _patch_adapter_for_success(tmpdir)
            mocks = _mock_all_checks_pass()

            with patch.dict(os.environ, _full_env(), clear=False):
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
                            result = retrieve_pending_redfin_capture_request(
                                capture_request=capture_request,
                                adapter=adapter,
                                http_client=client,
                                force_live=True,
                            )

            assert result.status == "retrieved"
            assert result.decision == "allowed"
            assert result.network_call_performed is True
            assert result.fixture_path != ""
            assert Path(result.fixture_path).exists()

    def test_fake_client_batch_success(self):
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )
        from marketsentry.source_adapters.http_client import FakeHttpClient

        html_content = "<html><body><h1>Test Property</h1></body></html>"
        client = FakeHttpClient(response_text=html_content)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            cap_id = _add_pending_request(
                db_path, "https://www.redfin.com/CA/Temecula/123-Test-St-92592/home/6574263", "property_detail"
            )

            adapter = _patch_adapter_for_success(tmpdir)
            mocks = _mock_all_checks_pass()

            config = BatchRetrievalConfig(
                mode="retrieve_only",
                force_live=True,
                database_path=db_path,
            )

            batch_manifest = os.path.join(tmpdir, "batch.csv")
            item_manifest = os.path.join(tmpdir, "items.csv")

            with patch.dict(os.environ, _full_env(), clear=False):
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
                            result = retrieve_pending_redfin_capture_batch(
                                config=config,
                                adapter=adapter,
                                http_client=client,
                                batch_manifest_path=batch_manifest,
                                item_manifest_path=item_manifest,
                            )

            assert result.retrieved == 1
            assert result.fixtures_saved == 1
            assert result.blocked == 0
            assert result.failed == 0


# ===========================================================================
# TestRetrieveOnlyDoesNotProcess
# ===========================================================================


class TestRetrieveOnlyDoesNotProcess:
    """Test retrieve_only does not call processing pipeline."""

    def test_retrieve_only_no_processing(self):
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )
        from marketsentry.source_adapters.http_client import FakeHttpClient

        html_content = "<html><body>Test</body></html>"
        client = FakeHttpClient(response_text=html_content)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            _add_pending_request(
                db_path, "https://www.redfin.com/CA/Temecula/123-Test-St-92592/home/6574263", "property_detail"
            )

            adapter = _patch_adapter_for_success(tmpdir)
            mocks = _mock_all_checks_pass()

            config = BatchRetrievalConfig(
                mode="retrieve_only",
                force_live=True,
                database_path=db_path,
            )

            with patch.dict(os.environ, _full_env(), clear=False):
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
                            result = retrieve_pending_redfin_capture_batch(
                                config=config,
                                adapter=adapter,
                                http_client=client,
                                batch_manifest_path=os.path.join(tmpdir, "b.csv"),
                                item_manifest_path=os.path.join(tmpdir, "i.csv"),
                            )

            assert result.retrieved == 1
            assert result.processed_after_retrieval is False


# ===========================================================================
# TestRetrieveAndProcess
# ===========================================================================


class TestRetrieveAndProcess:
    """Test retrieve_and_process calls processing pipeline."""

    def test_retrieve_and_process_calls_pipeline(self):
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )
        from marketsentry.source_adapters.http_client import FakeHttpClient

        html_content = "<html><body>Test</body></html>"
        client = FakeHttpClient(response_text=html_content)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            cap_id = _add_pending_request(
                db_path, "https://www.redfin.com/CA/Temecula/123-Test-St-92592/home/6574263", "property_detail"
            )

            adapter = _patch_adapter_for_success(tmpdir)
            mocks = _mock_all_checks_pass()

            config = BatchRetrievalConfig(
                mode="retrieve_and_process",
                force_live=True,
                database_path=db_path,
                output_dir=tmpdir,
            )

            # Mock the processing pipeline
            from marketsentry.retrieved_fixture_processor import (
                RedfinFixtureProcessingRunResult,
            )

            mock_proc_result = RedfinFixtureProcessingRunResult(
                reports_exported=["report1.csv"],
            )

            with patch.dict(os.environ, _full_env(), clear=False):
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
                            with patch(
                                "marketsentry.retrieved_fixture_processor.process_redfin_retrieved_fixtures",
                                return_value=mock_proc_result,
                            ):
                                result = retrieve_pending_redfin_capture_batch(
                                    config=config,
                                    adapter=adapter,
                                    http_client=client,
                                    batch_manifest_path=os.path.join(tmpdir, "b.csv"),
                                    item_manifest_path=os.path.join(tmpdir, "i.csv"),
                                )

            assert result.retrieved == 1
            assert result.processed_after_retrieval is True
            assert result.reports_exported == ["report1.csv"]


# ===========================================================================
# TestCapturedMarking
# ===========================================================================


class TestCapturedMarking:
    """Test queue items marked captured only after success."""

    def test_captured_after_retrieve_and_process(self):
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )
        from marketsentry.retrieved_fixture_processor import (
            RedfinFixtureProcessingRunResult,
        )
        from marketsentry.source_adapters.http_client import FakeHttpClient

        html_content = "<html><body>Test</body></html>"
        client = FakeHttpClient(response_text=html_content)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            cap_id = _add_pending_request(
                db_path, "https://www.redfin.com/CA/Temecula/123-Test-St-92592/home/6574263", "property_detail"
            )

            adapter = _patch_adapter_for_success(tmpdir)
            mocks = _mock_all_checks_pass()

            config = BatchRetrievalConfig(
                mode="retrieve_and_process",
                force_live=True,
                database_path=db_path,
            )

            mock_proc_result = RedfinFixtureProcessingRunResult(reports_exported=[])

            with patch.dict(os.environ, _full_env(), clear=False):
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
                            with patch(
                                "marketsentry.retrieved_fixture_processor.process_redfin_retrieved_fixtures",
                                return_value=mock_proc_result,
                            ):
                                result = retrieve_pending_redfin_capture_batch(
                                    config=config,
                                    adapter=adapter,
                                    http_client=client,
                                    batch_manifest_path=os.path.join(tmpdir, "b.csv"),
                                    item_manifest_path=os.path.join(tmpdir, "i.csv"),
                                )

            assert result.queue_items_marked_captured == 1
            assert _get_request_status(db_path, cap_id) == "captured"

    def test_blocked_items_remain_pending(self):
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            cap_id = _add_pending_request(
                db_path, "https://www.redfin.com/CA/test/home/123", "property_detail"
            )

            # Compliance fails (retrieval disabled)
            disabled_env = {"MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "false"}

            config = BatchRetrievalConfig(
                mode="retrieve_only",
                force_live=True,
                database_path=db_path,
            )

            with patch.dict(os.environ, disabled_env, clear=False):
                result = retrieve_pending_redfin_capture_batch(
                    config=config,
                    batch_manifest_path=os.path.join(tmpdir, "b.csv"),
                    item_manifest_path=os.path.join(tmpdir, "i.csv"),
                )

            # Item should still be pending
            assert _get_request_status(db_path, cap_id) == "pending"
            assert result.queue_items_marked_captured == 0

    def test_not_captured_when_not_retrieved(self):
        """Items not retrieved should not be marked captured."""
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            cap_id = _add_pending_request(
                db_path, "https://www.redfin.com/CA/test/home/123", "property_detail"
            )

            # No force-live: items are blocked
            config = BatchRetrievalConfig(
                mode="retrieve_only",
                force_live=False,
                database_path=db_path,
            )

            retrieve_pending_redfin_capture_batch(
                config=config,
                batch_manifest_path=os.path.join(tmpdir, "b.csv"),
                item_manifest_path=os.path.join(tmpdir, "i.csv"),
            )

            assert _get_request_status(db_path, cap_id) == "pending"


# ===========================================================================
# TestBatchManifest
# ===========================================================================


class TestBatchManifest:
    """Test batch manifest CSV is written."""

    def test_batch_manifest_written(self):
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            _add_pending_request(db_path, "https://www.redfin.com/CA/test/home/123", "property_detail")

            config = BatchRetrievalConfig(mode="dry_run_only", database_path=db_path)

            batch_manifest = os.path.join(tmpdir, "batch.csv")
            item_manifest = os.path.join(tmpdir, "items.csv")

            retrieve_pending_redfin_capture_batch(
                config=config,
                batch_manifest_path=batch_manifest,
                item_manifest_path=item_manifest,
            )

            assert Path(batch_manifest).exists()
            with open(batch_manifest, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["mode"] == "dry_run_only"
            assert int(rows[0]["pending_scanned"]) == 1


# ===========================================================================
# TestItemManifest
# ===========================================================================


class TestItemManifest:
    """Test per-item manifest CSV is written."""

    def test_item_manifest_written(self):
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            _add_pending_request(db_path, "https://www.redfin.com/CA/test/home/123", "property_detail")
            _add_pending_request(db_path, "https://www.redfin.com/city/test/search", "search")

            config = BatchRetrievalConfig(mode="dry_run_only", database_path=db_path)

            item_manifest = os.path.join(tmpdir, "items.csv")

            retrieve_pending_redfin_capture_batch(
                config=config,
                batch_manifest_path=os.path.join(tmpdir, "b.csv"),
                item_manifest_path=item_manifest,
            )

            assert Path(item_manifest).exists()
            with open(item_manifest, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 2

    def test_item_manifest_has_expected_columns(self):
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            ITEM_MANIFEST_COLUMNS,
            retrieve_pending_redfin_capture_batch,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            _add_pending_request(db_path, "https://www.redfin.com/CA/test/home/123", "property_detail")

            config = BatchRetrievalConfig(mode="dry_run_only", database_path=db_path)

            item_manifest = os.path.join(tmpdir, "items.csv")

            retrieve_pending_redfin_capture_batch(
                config=config,
                batch_manifest_path=os.path.join(tmpdir, "b.csv"),
                item_manifest_path=item_manifest,
            )

            with open(item_manifest, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert set(rows[0].keys()) == set(ITEM_MANIFEST_COLUMNS)


# ===========================================================================
# TestModels
# ===========================================================================


class TestModels:
    """Test model classes."""

    def test_batch_config_defaults(self):
        from marketsentry.redfin_batch_retrieval import BatchRetrievalConfig

        config = BatchRetrievalConfig()
        assert config.mode == "dry_run_only"
        assert config.max_items == 0
        assert config.force_live is False

    def test_item_result_defaults(self):
        from marketsentry.redfin_batch_retrieval import BatchRetrievalItemResult

        item = BatchRetrievalItemResult()
        assert item.network_call_performed is False
        assert item.marked_captured is False
        assert item.status == ""

    def test_run_result_has_run_id(self):
        from marketsentry.redfin_batch_retrieval import BatchRetrievalRunResult

        result = BatchRetrievalRunResult()
        assert result.run_id != ""
        assert len(result.run_id) == 12

    def test_summarize_output(self):
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalRunResult,
            summarize_batch_retrieval_run,
        )

        result = BatchRetrievalRunResult(
            pending_scanned=3,
            dry_run_only_count=3,
            mode="dry_run_only",
        )
        summary = summarize_batch_retrieval_run(result)
        assert "Pending scanned: 3" in summary
        assert "Dry-run only: 3" in summary
        assert "dry_run_only" in summary


# ===========================================================================
# TestNormalizeRequestType
# ===========================================================================


class TestNormalizeRequestType:
    """Test request type normalization."""

    def test_property_variants(self):
        from marketsentry.redfin_batch_retrieval import _normalize_request_type

        assert _normalize_request_type("property") == "property_detail"
        assert _normalize_request_type("property_detail") == "property_detail"
        assert _normalize_request_type("detail") == "property_detail"
        assert _normalize_request_type("PROPERTY_DETAIL") == "property_detail"

    def test_search(self):
        from marketsentry.redfin_batch_retrieval import _normalize_request_type

        assert _normalize_request_type("search") == "search"
        assert _normalize_request_type("SEARCH") == "search"


# ===========================================================================
# TestCLICommands
# ===========================================================================


class TestCLICommands:
    """Test CLI command registration."""

    def test_dry_run_cli_registered(self):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["dry-run-pending-redfin-fixtures", "--help"])
        assert result.exit_code == 0
        assert "Dry-run preview" in result.output or "dry-run" in result.output.lower()

    def test_retrieve_cli_registered(self):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["retrieve-pending-redfin-fixtures", "--help"])
        assert result.exit_code == 0
        assert "force-live" in result.output.lower()

    def test_retrieve_cli_blocked_default(self):
        """Without --force-live, retrieve command exits cleanly with explanation."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["retrieve-pending-redfin-fixtures"])
        assert result.exit_code == 0
        assert "blocked" in result.output.lower() or "force-live" in result.output.lower()

    def test_dry_run_cli_runs(self):
        """Dry-run CLI runs successfully with a temp database."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            runner = CliRunner()
            result = runner.invoke(app, [
                "dry-run-pending-redfin-fixtures",
                "--db", db_path,
            ])
            assert result.exit_code == 0


# ===========================================================================
# TestNoScheduledLiveRetrieval
# ===========================================================================


class TestNoScheduledLiveRetrieval:
    """Verify no scheduled scripts invoke live retrieval."""

    def test_no_scheduled_scripts_invoke_batch_retrieval(self):
        """Check that no batch script invokes batch retrieval commands."""
        scripts_dir = Path("scripts")
        if not scripts_dir.exists():
            return  # No scripts directory, pass

        batch_commands = [
            "retrieve-pending-redfin-fixtures",
            "dry-run-pending-redfin-fixtures",
        ]

        for script_file in scripts_dir.glob("*.bat"):
            content = script_file.read_text(encoding="utf-8", errors="ignore")
            for cmd in batch_commands:
                assert cmd not in content, (
                    f"Scheduled script {script_file.name} invokes {cmd}. "
                    "Scheduled scripts must not invoke live retrieval."
                )

        for script_file in scripts_dir.glob("*.ps1"):
            content = script_file.read_text(encoding="utf-8", errors="ignore")
            for cmd in batch_commands:
                assert cmd not in content, (
                    f"Scheduled script {script_file.name} invokes {cmd}. "
                    "Scheduled scripts must not invoke live retrieval."
                )


# ===========================================================================
# TestEmptyBatch
# ===========================================================================


class TestEmptyBatch:
    """Test batch behavior when no pending items exist."""

    def test_empty_batch_result(self):
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            config = BatchRetrievalConfig(mode="dry_run_only", database_path=db_path)

            result = retrieve_pending_redfin_capture_batch(
                config=config,
                batch_manifest_path=os.path.join(tmpdir, "b.csv"),
                item_manifest_path=os.path.join(tmpdir, "i.csv"),
            )

            assert result.pending_scanned == 0
            assert len(result.items) == 0
            assert "no pending" in result.notes.lower()


# ===========================================================================
# TestRetrieveOnlyMarksCaptured
# ===========================================================================


class TestRetrieveOnlyMarksCaptured:
    """Test retrieve_only mode marks items as captured."""

    def test_retrieve_only_marks_captured(self):
        from marketsentry.redfin_batch_retrieval import (
            BatchRetrievalConfig,
            retrieve_pending_redfin_capture_batch,
        )
        from marketsentry.source_adapters.http_client import FakeHttpClient

        html_content = "<html><body>Test</body></html>"
        client = FakeHttpClient(response_text=html_content)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            cap_id = _add_pending_request(
                db_path, "https://www.redfin.com/CA/Temecula/123-Test-St-92592/home/6574263", "property_detail"
            )

            adapter = _patch_adapter_for_success(tmpdir)
            mocks = _mock_all_checks_pass()

            config = BatchRetrievalConfig(
                mode="retrieve_only",
                force_live=True,
                database_path=db_path,
            )

            with patch.dict(os.environ, _full_env(), clear=False):
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
                            result = retrieve_pending_redfin_capture_batch(
                                config=config,
                                adapter=adapter,
                                http_client=client,
                                batch_manifest_path=os.path.join(tmpdir, "b.csv"),
                                item_manifest_path=os.path.join(tmpdir, "i.csv"),
                            )

            assert result.queue_items_marked_captured == 1
            assert _get_request_status(db_path, cap_id) == "captured"
