"""Tests for Milestone 22: Cross-Site Adapter Parity and Manual Fixture Workflow.

All tests use local data only (SQLite, temp files, mocks).
No real network calls are performed.
"""

import csv
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest


# ===========================================================================
# Test helpers
# ===========================================================================


def _create_test_db(db_path: str) -> None:
    """Create a minimal test database with required tables."""
    from marketsentry.database import init_db
    from marketsentry.fixture_capture_queue import ensure_fixture_capture_table

    init_db(db_path)
    ensure_fixture_capture_table(db_path)


def _add_capture_request(
    db_path: str,
    source_url: str,
    request_type: str = "property_detail",
    source_site: str = "redfin",
    status: str = "pending",
    created_at: str = "",
) -> int:
    """Insert a capture request with optional created_at override."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    normalized = source_url.lower().rstrip("/")
    if created_at:
        cursor.execute(
            """
            INSERT INTO fixture_capture_queue (
                source_site, source_url, normalized_url, request_type,
                suggested_fixture_path, status, priority, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 5, ?)
            """,
            (source_site, source_url, normalized, request_type,
             f"data/raw/{source_site}/", status, created_at),
        )
    else:
        cursor.execute(
            """
            INSERT INTO fixture_capture_queue (
                source_site, source_url, normalized_url, request_type,
                suggested_fixture_path, status, priority
            ) VALUES (?, ?, ?, ?, ?, ?, 5)
            """,
            (source_site, source_url, normalized, request_type,
             f"data/raw/{source_site}/", status),
        )
    conn.commit()
    cap_id = cursor.lastrowid
    conn.close()
    return cap_id


def _write_csv(path: str, fieldnames: list, rows: list) -> None:
    """Write a CSV file with given fieldnames and rows."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _create_html_fixture(dir_path: Path, filename: str, content: str = "") -> Path:
    """Create an HTML fixture file in a directory."""
    dir_path.mkdir(parents=True, exist_ok=True)
    fixture_path = dir_path / filename
    html_content = content or (
        "<html><head><title>Test Property</title></head>"
        "<body><h1>123 Main St</h1></body></html>"
    )
    fixture_path.write_text(html_content, encoding="utf-8")
    return fixture_path


# ===========================================================================
# Zillow Adapter Tests
# ===========================================================================


class TestZillowAdapterDryRun:
    """Tests for Zillow adapter dry-run parity."""

    def test_zillow_property_url_validates(self):
        """Zillow property URL is correctly validated."""
        from marketsentry.source_adapters.zillow_adapter import (
            is_zillow_property_url,
            is_zillow_domain,
        )

        assert is_zillow_domain("https://www.zillow.com/homedetails/123/456_zpid/")
        assert is_zillow_property_url(
            "https://www.zillow.com/homedetails/123-Main-St/12345678_zpid/"
        )
        assert not is_zillow_property_url("https://www.redfin.com/CA/Temecula/")

    def test_zillow_search_url_detected(self):
        """Zillow search URL pattern is detected."""
        from marketsentry.source_adapters.zillow_adapter import is_zillow_search_url

        assert is_zillow_search_url(
            "https://www.zillow.com/homes/Temecula_rb/"
        )

    def test_zillow_dry_run_creates_capture_request(self):
        """Zillow dry-run creates a fixture capture queue request."""
        from marketsentry.source_adapters.zillow_adapter import ZillowAdapter
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter = ZillowAdapter()

        with patch(
            "marketsentry.fixture_capture_queue.add_capture_request"
        ) as mock_add, patch(
            "marketsentry.source_adapters.compliance.write_audit_record"
        ):
            mock_add.return_value = type("R", (), {
                "duplicate": False, "capture_request_id": 1
            })()

            request = RetrievalRequest(
                url="https://www.zillow.com/homedetails/123-Main-St/12345678_zpid/",
                source_name="zillow",
                request_type="property_detail",
            )
            result = adapter.dry_run(request)

            assert result.success is True
            assert result.dry_run is True
            assert result.network_call_performed is False
            assert "DRY-RUN" in result.dry_run_preview
            assert "Zillow" in result.dry_run_preview

    def test_zillow_invalid_domain_blocked(self):
        """Zillow adapter blocks URLs from invalid domains."""
        from marketsentry.source_adapters.zillow_adapter import ZillowAdapter
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter = ZillowAdapter()
        request = RetrievalRequest(
            url="https://www.redfin.com/CA/Temecula/",
            source_name="zillow",
        )
        result = adapter.validate_request(request)
        assert result.blocked is True
        assert result.success is False
        assert "not a recognized Zillow domain" in result.block_reason

    def test_zillow_live_retrieval_blocked(self):
        """Zillow live retrieval returns blocked/not_implemented."""
        from marketsentry.source_adapters.zillow_adapter import ZillowAdapter
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter = ZillowAdapter()
        request = RetrievalRequest(
            url="https://www.zillow.com/homedetails/123/456_zpid/",
            source_name="zillow",
        )

        # Adapter methods use try/except for audit/capture calls,
        # so they handle failures gracefully without mocking.
        result = adapter.retrieve(request)

        assert result.blocked is True
        assert result.success is False
        assert result.network_call_performed is False
        assert "not implemented" in result.block_reason.lower()


# ===========================================================================
# Realtor Adapter Tests
# ===========================================================================


class TestRealtorAdapterDryRun:
    """Tests for Realtor.com adapter dry-run parity."""

    def test_realtor_property_url_validates(self):
        """Realtor property URL is correctly validated."""
        from marketsentry.source_adapters.realtor_adapter import (
            is_realtor_property_url,
            is_realtor_domain,
        )

        assert is_realtor_domain(
            "https://www.realtor.com/realestateandhomes-detail/123-Main-St"
        )
        assert is_realtor_property_url(
            "https://www.realtor.com/realestateandhomes-detail/123-Main-St_Temecula_CA"
        )
        assert not is_realtor_property_url("https://www.zillow.com/homedetails/")

    def test_realtor_dry_run_creates_capture_request(self):
        """Realtor dry-run creates a fixture capture queue request."""
        from marketsentry.source_adapters.realtor_adapter import RealtorAdapter
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter = RealtorAdapter()

        with patch(
            "marketsentry.fixture_capture_queue.add_capture_request"
        ) as mock_add, patch(
            "marketsentry.source_adapters.compliance.write_audit_record"
        ):
            mock_add.return_value = type("R", (), {
                "duplicate": False, "capture_request_id": 2
            })()

            request = RetrievalRequest(
                url="https://www.realtor.com/realestateandhomes-detail/123-Main-St",
                source_name="realtor",
            )
            result = adapter.dry_run(request)

            assert result.success is True
            assert result.dry_run is True
            assert result.network_call_performed is False
            assert "DRY-RUN" in result.dry_run_preview

    def test_realtor_invalid_domain_blocked(self):
        """Realtor adapter blocks URLs from invalid domains."""
        from marketsentry.source_adapters.realtor_adapter import RealtorAdapter
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter = RealtorAdapter()
        request = RetrievalRequest(
            url="https://www.homes.com/property/123",
            source_name="realtor",
        )
        result = adapter.validate_request(request)
        assert result.blocked is True
        assert "not a recognized Realtor" in result.block_reason

    def test_realtor_live_retrieval_blocked(self):
        """Realtor live retrieval returns blocked/not_implemented."""
        from marketsentry.source_adapters.realtor_adapter import RealtorAdapter
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter = RealtorAdapter()
        request = RetrievalRequest(
            url="https://www.realtor.com/realestateandhomes-detail/123",
            source_name="realtor",
        )
        result = adapter.retrieve(request)

        assert result.blocked is True
        assert result.network_call_performed is False


# ===========================================================================
# Homes Adapter Tests
# ===========================================================================


class TestHomesAdapterDryRun:
    """Tests for Homes.com adapter dry-run parity."""

    def test_homes_property_url_validates(self):
        """Homes.com property URL is correctly validated."""
        from marketsentry.source_adapters.homes_adapter import (
            is_homes_property_url,
            is_homes_domain,
        )

        assert is_homes_domain("https://www.homes.com/property/123-main-st/")
        assert is_homes_property_url(
            "https://www.homes.com/property/123-main-st-temecula-ca/12345/"
        )
        assert not is_homes_property_url("https://www.compass.com/listing/123")

    def test_homes_dry_run_creates_capture_request(self):
        """Homes dry-run creates a fixture capture queue request."""
        from marketsentry.source_adapters.homes_adapter import HomesAdapter
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter = HomesAdapter()

        with patch(
            "marketsentry.fixture_capture_queue.add_capture_request"
        ) as mock_add, patch(
            "marketsentry.source_adapters.compliance.write_audit_record"
        ):
            mock_add.return_value = type("R", (), {
                "duplicate": False, "capture_request_id": 3
            })()

            request = RetrievalRequest(
                url="https://www.homes.com/property/123-main-st/12345/",
                source_name="homes",
            )
            result = adapter.dry_run(request)

            assert result.success is True
            assert result.dry_run is True
            assert result.network_call_performed is False
            assert "DRY-RUN" in result.dry_run_preview

    def test_homes_invalid_domain_blocked(self):
        """Homes adapter blocks URLs from invalid domains."""
        from marketsentry.source_adapters.homes_adapter import HomesAdapter
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter = HomesAdapter()
        request = RetrievalRequest(
            url="https://www.zillow.com/homedetails/123",
            source_name="homes",
        )
        result = adapter.validate_request(request)
        assert result.blocked is True
        assert "not a recognized Homes.com domain" in result.block_reason

    def test_homes_live_retrieval_blocked(self):
        """Homes live retrieval returns blocked/not_implemented."""
        from marketsentry.source_adapters.homes_adapter import HomesAdapter
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter = HomesAdapter()
        request = RetrievalRequest(
            url="https://www.homes.com/property/123-main-st/",
            source_name="homes",
        )
        result = adapter.retrieve(request)

        assert result.blocked is True
        assert result.network_call_performed is False


# ===========================================================================
# Compass Adapter Tests
# ===========================================================================


class TestCompassAdapterDryRun:
    """Tests for Compass adapter dry-run parity."""

    def test_compass_property_url_validates(self):
        """Compass property URL is correctly validated."""
        from marketsentry.source_adapters.compass_adapter import (
            is_compass_property_url,
            is_compass_domain,
        )

        assert is_compass_domain("https://www.compass.com/listing/123-main-st/")
        assert is_compass_property_url(
            "https://www.compass.com/listing/123-main-st/12345/"
        )
        assert not is_compass_property_url("https://www.homes.com/property/123")

    def test_compass_dry_run_creates_capture_request(self):
        """Compass dry-run creates a fixture capture queue request."""
        from marketsentry.source_adapters.compass_adapter import CompassAdapter
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter = CompassAdapter()

        with patch(
            "marketsentry.fixture_capture_queue.add_capture_request"
        ) as mock_add, patch(
            "marketsentry.source_adapters.compliance.write_audit_record"
        ):
            mock_add.return_value = type("R", (), {
                "duplicate": False, "capture_request_id": 4
            })()

            request = RetrievalRequest(
                url="https://www.compass.com/listing/123-main-st/12345/",
                source_name="compass",
            )
            result = adapter.dry_run(request)

            assert result.success is True
            assert result.dry_run is True
            assert result.network_call_performed is False
            assert "DRY-RUN" in result.dry_run_preview

    def test_compass_invalid_domain_blocked(self):
        """Compass adapter blocks URLs from invalid domains."""
        from marketsentry.source_adapters.compass_adapter import CompassAdapter
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter = CompassAdapter()
        request = RetrievalRequest(
            url="https://www.redfin.com/CA/Temecula/",
            source_name="compass",
        )
        result = adapter.validate_request(request)
        assert result.blocked is True
        assert "not a recognized Compass domain" in result.block_reason

    def test_compass_live_retrieval_blocked(self):
        """Compass live retrieval returns blocked/not_implemented."""
        from marketsentry.source_adapters.compass_adapter import CompassAdapter
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter = CompassAdapter()
        request = RetrievalRequest(
            url="https://www.compass.com/listing/123/",
            source_name="compass",
        )
        result = adapter.retrieve(request)

        assert result.blocked is True
        assert result.network_call_performed is False


# ===========================================================================
# Common adapter behavior tests
# ===========================================================================


class TestAdapterCommonBehavior:
    """Tests for common adapter behavior across all non-Redfin sources."""

    @pytest.mark.parametrize("source,adapter_cls,url", [
        ("zillow", "ZillowAdapter",
         "https://www.zillow.com/homedetails/123/456_zpid/"),
        ("realtor", "RealtorAdapter",
         "https://www.realtor.com/realestateandhomes-detail/123"),
        ("homes", "HomesAdapter",
         "https://www.homes.com/property/123-main-st/"),
        ("compass", "CompassAdapter",
         "https://www.compass.com/listing/123-main-st/"),
    ])
    def test_dry_run_no_network_call(self, source, adapter_cls, url):
        """Dry-run performs no network call for any source."""
        import importlib

        mod = importlib.import_module(
            f"marketsentry.source_adapters.{source}_adapter"
        )
        cls = getattr(mod, adapter_cls)
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter = cls()
        request = RetrievalRequest(url=url, source_name=source)

        with patch(
            "marketsentry.fixture_capture_queue.add_capture_request",
            return_value=type("R", (), {
                "duplicate": False, "capture_request_id": 1
            })(),
        ), patch(
            "marketsentry.source_adapters.compliance.write_audit_record"
        ):
            result = adapter.dry_run(request)

        assert result.network_call_performed is False
        assert result.dry_run is True

    @pytest.mark.parametrize("source,adapter_cls", [
        ("zillow", "ZillowAdapter"),
        ("realtor", "RealtorAdapter"),
        ("homes", "HomesAdapter"),
        ("compass", "CompassAdapter"),
    ])
    def test_no_url_blocked(self, source, adapter_cls):
        """Empty URL is blocked for all sources."""
        import importlib

        mod = importlib.import_module(
            f"marketsentry.source_adapters.{source}_adapter"
        )
        cls = getattr(mod, adapter_cls)
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter = cls()
        request = RetrievalRequest(url="", source_name=source)
        result = adapter.validate_request(request)
        assert result.blocked is True
        assert "No URL" in result.block_reason


# ===========================================================================
# Cross-Site Fixture Processor Tests
# ===========================================================================


class TestCrossSiteFixtureScan:
    """Tests for cross-site fixture scanning."""

    def test_scan_finds_fixtures(self):
        """scan_cross_site_fixtures finds HTML files in source directories."""
        from marketsentry.cross_site_fixture_processor import (
            scan_cross_site_fixtures,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            details_dir = Path(tmpdir) / "zillow" / "details"
            _create_html_fixture(details_dir, "prop1.html")
            _create_html_fixture(details_dir, "prop2.html")

            records = scan_cross_site_fixtures(
                root_dir=tmpdir, source_site="zillow",
            )
            assert len(records) == 2
            assert all(r.source_site == "zillow" for r in records)
            assert all(r.content_hash for r in records)

    def test_scan_empty_directory(self):
        """scan_cross_site_fixtures returns empty for missing directories."""
        from marketsentry.cross_site_fixture_processor import (
            scan_cross_site_fixtures,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            records = scan_cross_site_fixtures(
                root_dir=tmpdir, source_site="compass",
            )
            assert len(records) == 0

    def test_scan_specific_directory(self):
        """scan_cross_site_fixtures scans a specific directory."""
        from marketsentry.cross_site_fixture_processor import (
            scan_cross_site_fixtures,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_dir = Path(tmpdir) / "custom"
            _create_html_fixture(fixture_dir, "test.html")

            records = scan_cross_site_fixtures(
                fixture_dir=str(fixture_dir), source_site="homes",
            )
            assert len(records) == 1
            assert records[0].source_site == "homes"


class TestCrossSiteFixtureProcessing:
    """Tests for cross-site fixture processing."""

    def test_processing_inserts_observations(self):
        """Processing a fixture calls the parser and inserts observations."""
        from marketsentry.cross_site_fixture_processor import (
            _process_single_fixture,
            CrossSiteFixtureRecord,
        )
        from marketsentry.models import CrossSiteParseResult

        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path = _create_html_fixture(
                Path(tmpdir), "test.html",
            )

            record = CrossSiteFixtureRecord(
                fixture_path=str(fixture_path),
                source_site="zillow",
                content_hash="abc123",
            )

            mock_parse_result = CrossSiteParseResult(
                source_site="zillow",
                source_url="https://www.zillow.com/homedetails/123/456_zpid/",
                parse_status="success",
                property_facts={"price": "500000", "beds": "3"},
            )

            def mock_parser(path):
                return mock_parse_result

            with patch(
                "marketsentry.cross_site_enrichment."
                "_find_watched_property_for_observation",
                return_value=None,
            ), patch(
                "marketsentry.cross_site_enrichment."
                "insert_cross_site_observation",
                return_value=True,
            ):
                result = _process_single_fixture(
                    record, mock_parser, None,
                )

            assert result.status == "processed"
            assert result.source_url == mock_parse_result.source_url

    def test_processing_deduplicates_unchanged(self):
        """Processing skips unchanged fixtures using content hash."""
        from marketsentry.cross_site_fixture_processor import (
            process_cross_site_source_fixtures,
            MANIFEST_FIELDNAMES,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fixture
            details_dir = Path(tmpdir) / "raw" / "zillow" / "details"
            fixture = _create_html_fixture(details_dir, "prop.html")

            # Compute hash
            import hashlib
            content = fixture.read_text(encoding="utf-8")
            content_hash = hashlib.sha256(
                content.encode("utf-8")
            ).hexdigest()

            # Create manifest with this hash already processed
            processed_dir = Path(tmpdir) / "processed"
            processed_dir.mkdir(parents=True, exist_ok=True)
            _write_csv(
                str(processed_dir / "cross_site_fixture_processing_manifest.csv"),
                MANIFEST_FIELDNAMES,
                [{
                    "processed_at": datetime.now().isoformat(),
                    "source_site": "zillow",
                    "fixture_path": str(fixture),
                    "source_url": "",
                    "fixture_type": "property_detail",
                    "status": "processed",
                    "observations_inserted": "0",
                    "candidates_matched": "0",
                    "watched_properties_matched": "0",
                    "warnings": "",
                    "errors": "",
                    "content_hash": content_hash,
                }],
            )

            result = process_cross_site_source_fixtures(
                source_site="zillow",
                root_dir=str(Path(tmpdir) / "raw"),
                output_dir=str(processed_dir),
            )

            assert result.files_scanned == 1
            assert result.duplicates_skipped == 1
            assert result.files_processed == 0

    def test_force_reprocess(self):
        """Force reprocess processes even when hash matches."""
        from marketsentry.cross_site_fixture_processor import (
            process_cross_site_source_fixtures,
            MANIFEST_FIELDNAMES,
        )
        from marketsentry.models import CrossSiteParseResult

        with tempfile.TemporaryDirectory() as tmpdir:
            details_dir = Path(tmpdir) / "raw" / "zillow" / "details"
            fixture = _create_html_fixture(details_dir, "prop.html")

            import hashlib
            content = fixture.read_text(encoding="utf-8")
            content_hash = hashlib.sha256(
                content.encode("utf-8")
            ).hexdigest()

            processed_dir = Path(tmpdir) / "processed"
            processed_dir.mkdir(parents=True, exist_ok=True)
            _write_csv(
                str(processed_dir / "cross_site_fixture_processing_manifest.csv"),
                MANIFEST_FIELDNAMES,
                [{
                    "processed_at": datetime.now().isoformat(),
                    "source_site": "zillow",
                    "fixture_path": str(fixture),
                    "source_url": "",
                    "fixture_type": "property_detail",
                    "status": "processed",
                    "observations_inserted": "0",
                    "candidates_matched": "0",
                    "watched_properties_matched": "0",
                    "warnings": "",
                    "errors": "",
                    "content_hash": content_hash,
                }],
            )

            mock_parse_result = CrossSiteParseResult(
                source_site="zillow",
                parse_status="success",
                property_facts={"price": "500000"},
            )

            with patch(
                "marketsentry.cross_site_fixture_processor._get_parser",
                return_value=lambda p: mock_parse_result,
            ), patch(
                "marketsentry.cross_site_enrichment."
                "_find_watched_property_for_observation",
                return_value=None,
            ), patch(
                "marketsentry.cross_site_enrichment."
                "insert_cross_site_observation",
                return_value=True,
            ), patch(
                "marketsentry.cross_site_fixture_processor."
                "_mark_capture_queue_item",
                return_value=False,
            ):
                result = process_cross_site_source_fixtures(
                    source_site="zillow",
                    root_dir=str(Path(tmpdir) / "raw"),
                    output_dir=str(processed_dir),
                    force_reprocess=True,
                )

            assert result.files_scanned == 1
            assert result.duplicates_skipped == 0
            assert result.files_processed == 1


class TestCrossSiteManifest:
    """Tests for cross-site processing manifest."""

    def test_manifest_written(self):
        """Manifest CSV is written with correct columns."""
        from marketsentry.cross_site_fixture_processor import (
            write_cross_site_processing_manifest,
            CrossSiteFixtureProcessingResult,
            MANIFEST_FIELDNAMES,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            results = [
                CrossSiteFixtureProcessingResult(
                    fixture_path="/tmp/test.html",
                    source_site="zillow",
                    fixture_type="property_detail",
                    status="processed",
                    observations_inserted=1,
                    content_hash="abc123",
                ),
            ]

            path = write_cross_site_processing_manifest(
                results, output_dir=tmpdir,
            )

            assert Path(path).exists()

            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            assert rows[0]["source_site"] == "zillow"
            assert rows[0]["status"] == "processed"
            assert rows[0]["content_hash"] == "abc123"

            # Verify all expected columns present
            for field in MANIFEST_FIELDNAMES:
                assert field in rows[0]

    def test_manifest_append_only(self):
        """Manifest appends to existing file."""
        from marketsentry.cross_site_fixture_processor import (
            write_cross_site_processing_manifest,
            CrossSiteFixtureProcessingResult,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            results1 = [
                CrossSiteFixtureProcessingResult(
                    fixture_path="/tmp/test1.html",
                    source_site="zillow",
                    status="processed",
                    content_hash="hash1",
                ),
            ]
            write_cross_site_processing_manifest(results1, output_dir=tmpdir)

            results2 = [
                CrossSiteFixtureProcessingResult(
                    fixture_path="/tmp/test2.html",
                    source_site="realtor",
                    status="processed",
                    content_hash="hash2",
                ),
            ]
            write_cross_site_processing_manifest(results2, output_dir=tmpdir)

            manifest_path = (
                Path(tmpdir)
                / "cross_site_fixture_processing_manifest.csv"
            )
            with open(manifest_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]["source_site"] == "zillow"
            assert rows[1]["source_site"] == "realtor"


class TestCaptureQueueMarking:
    """Tests for capture queue marking after processing."""

    def test_queue_item_marked_captured_after_success(self):
        """Queue item is marked captured only after successful processing."""
        from marketsentry.cross_site_fixture_processor import (
            _mark_capture_queue_item,
        )

        with patch(
            "marketsentry.fixture_capture_queue.list_pending_capture_requests",
            return_value=[{"capture_request_id": 42}],
        ), patch(
            "marketsentry.fixture_capture_queue.mark_fixture_captured",
        ) as mock_mark:
            result = _mark_capture_queue_item(
                "/tmp/test.html", "zillow", None,
            )

            assert result is True
            mock_mark.assert_called_once()


# ===========================================================================
# Health Check Tests
# ===========================================================================


class TestCrossSiteHealthChecks:
    """Tests for cross-site health check integration."""

    def test_health_check_detects_unprocessed_cross_site_fixture(self):
        """Health check flags unprocessed cross-site fixtures."""
        from marketsentry.retrieval_health import (
            check_cross_site_fixture_processing_gaps,
            RetrievalHealthCheckConfig,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            zillow_dir = raw_dir / "zillow" / "details"
            fixture = _create_html_fixture(zillow_dir, "old_prop.html")

            # Set file mtime to 48 hours ago
            import time
            old_time = time.time() - (48 * 3600)
            os.utime(str(fixture), (old_time, old_time))

            config = RetrievalHealthCheckConfig(
                retrieved_fixture_unprocessed_hours=24.0,
            )

            issues = check_cross_site_fixture_processing_gaps(
                processed_dir=str(Path(tmpdir) / "processed"),
                raw_dir=str(raw_dir),
                config=config,
                now=datetime.now(),
            )

            assert len(issues) >= 1
            assert any(
                i.category == "unprocessed_cross_site_fixture"
                for i in issues
            )

    def test_health_check_no_false_positive_for_processed(self):
        """Health check does not flag already-processed fixtures."""
        from marketsentry.retrieval_health import (
            check_cross_site_fixture_processing_gaps,
            RetrievalHealthCheckConfig,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            zillow_dir = raw_dir / "zillow" / "details"
            fixture = _create_html_fixture(zillow_dir, "prop.html")

            # Set file mtime to 48 hours ago
            import time
            old_time = time.time() - (48 * 3600)
            os.utime(str(fixture), (old_time, old_time))

            # Compute content hash
            import hashlib
            content = fixture.read_text(encoding="utf-8")
            content_hash = hashlib.sha256(
                content.encode("utf-8")
            ).hexdigest()

            # Write manifest with this hash
            processed_dir = Path(tmpdir) / "processed"
            processed_dir.mkdir(parents=True, exist_ok=True)
            _write_csv(
                str(processed_dir / "cross_site_fixture_processing_manifest.csv"),
                ["processed_at", "source_site", "fixture_path", "source_url",
                 "fixture_type", "status", "observations_inserted",
                 "candidates_matched", "watched_properties_matched",
                 "warnings", "errors", "content_hash"],
                [{
                    "processed_at": datetime.now().isoformat(),
                    "source_site": "zillow",
                    "fixture_path": str(fixture),
                    "source_url": "",
                    "fixture_type": "property_detail",
                    "status": "processed",
                    "observations_inserted": "0",
                    "candidates_matched": "0",
                    "watched_properties_matched": "0",
                    "warnings": "",
                    "errors": "",
                    "content_hash": content_hash,
                }],
            )

            config = RetrievalHealthCheckConfig(
                retrieved_fixture_unprocessed_hours=24.0,
            )

            issues = check_cross_site_fixture_processing_gaps(
                processed_dir=str(processed_dir),
                raw_dir=str(raw_dir),
                config=config,
                now=datetime.now(),
            )

            assert len(issues) == 0

    def test_health_summary_includes_cross_site_counts(self):
        """Health summary includes cross-site-specific counts."""
        from marketsentry.retrieval_health import (
            run_retrieval_health_checks,
            RetrievalHealthCheckConfig,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            config = RetrievalHealthCheckConfig()

            summary = run_retrieval_health_checks(
                database_path=db_path,
                audit_dir=os.path.join(tmpdir, "audit"),
                processed_dir=os.path.join(tmpdir, "processed"),
                raw_dir=os.path.join(tmpdir, "raw"),
                config=config,
            )

            # These fields should exist even if zero
            assert hasattr(summary, "unprocessed_cross_site_fixture_count")
            assert hasattr(summary, "stale_cross_site_capture_request_count")
            assert hasattr(summary, "missing_parser_count")

    def test_parser_availability_check(self):
        """Parser availability check does not flag when no pending requests."""
        from marketsentry.retrieval_health import (
            check_cross_site_parser_availability,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            _create_test_db(db_path)

            issues = check_cross_site_parser_availability(
                database_path=db_path,
            )
            assert len(issues) == 0


# ===========================================================================
# Dashboard Tests
# ===========================================================================


class TestDashboardCrossSite:
    """Tests for dashboard cross-site integration."""

    def test_dashboard_has_cross_site_fixtures_tab(self):
        """Retrieval Operations includes Cross-Site Fixtures tab."""
        from marketsentry.dashboard_app import (
            _render_cross_site_fixture_processing,
        )

        # Verify the function exists and is callable
        assert callable(_render_cross_site_fixture_processing)

    def test_dashboard_includes_cross_site_processing_manifest(self):
        """Dashboard render function can handle manifest data."""
        # This is a smoke test that the function signature is correct
        from marketsentry.dashboard_app import (
            _render_cross_site_fixture_processing,
        )
        import inspect

        sig = inspect.signature(_render_cross_site_fixture_processing)
        params = list(sig.parameters.keys())
        assert "db_path" in params
        assert "exports_dir" in params


# ===========================================================================
# CLI Tests
# ===========================================================================


class TestCLIDryRunCrossSiteProperty:
    """Tests for CLI dry-run-cross-site-property command."""

    def test_cli_has_dry_run_command(self):
        """CLI has dry-run-cross-site-property command registered."""
        from marketsentry.cli import app

        # Typer may store command names with underscores or hyphens
        commands = []
        for cmd in app.registered_commands:
            name = cmd.name or cmd.callback.__name__
            commands.append(name.replace("_", "-"))
        assert "dry-run-cross-site-property" in commands

    def test_cli_dry_run_cross_site_property(self):
        """CLI dry-run-cross-site-property runs successfully."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "dry-run-cross-site-property",
            "--source", "zillow",
            "--url", "https://www.zillow.com/homedetails/123/456_zpid/",
        ])
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output or "dry-run" in result.output.lower()


class TestCLIProcessCrossSiteFixtures:
    """Tests for CLI process-cross-site-fixtures command."""

    def test_cli_has_process_command(self):
        """CLI has process-cross-site-fixtures command registered."""
        from marketsentry.cli import app

        commands = []
        for cmd in app.registered_commands:
            name = cmd.name or cmd.callback.__name__
            commands.append(name.replace("_", "-"))
        assert "process-cross-site-fixtures" in commands

    def test_cli_process_cross_site_fixtures(self):
        """CLI process-cross-site-fixtures runs successfully."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmpdir:
            runner = CliRunner()
            result = runner.invoke(app, [
                "process-cross-site-fixtures",
                "--root-dir", tmpdir,
            ])
            assert result.exit_code == 0


class TestCLIProcessCrossSiteSourceFixtures:
    """Tests for CLI process-cross-site-source-fixtures command."""

    def test_cli_has_process_source_command(self):
        """CLI has process-cross-site-source-fixtures command registered."""
        from marketsentry.cli import app

        commands = []
        for cmd in app.registered_commands:
            name = cmd.name or cmd.callback.__name__
            commands.append(name.replace("_", "-"))
        assert "process-cross-site-source-fixtures" in commands

    def test_cli_process_cross_site_source_fixtures(self):
        """CLI process-cross-site-source-fixtures runs successfully."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        with tempfile.TemporaryDirectory() as tmpdir:
            runner = CliRunner()
            result = runner.invoke(app, [
                "process-cross-site-source-fixtures",
                "--source", "zillow",
                "--dir", tmpdir,
            ])
            assert result.exit_code == 0


# ===========================================================================
# No Network Calls Test
# ===========================================================================


class TestNoNetworkCalls:
    """Tests that no real network calls are performed."""

    @pytest.mark.parametrize("source", ["zillow", "realtor", "homes", "compass"])
    def test_adapter_dry_run_no_network(self, source):
        """Adapter dry-run does not perform network calls."""
        import importlib
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter_names = {
            "zillow": "ZillowAdapter",
            "realtor": "RealtorAdapter",
            "homes": "HomesAdapter",
            "compass": "CompassAdapter",
        }
        test_urls = {
            "zillow": "https://www.zillow.com/homedetails/123/456_zpid/",
            "realtor": "https://www.realtor.com/realestateandhomes-detail/123",
            "homes": "https://www.homes.com/property/123-main-st/",
            "compass": "https://www.compass.com/listing/123-main-st/",
        }

        mod = importlib.import_module(
            f"marketsentry.source_adapters.{source}_adapter"
        )
        cls = getattr(mod, adapter_names[source])
        adapter = cls()

        request = RetrievalRequest(
            url=test_urls[source], source_name=source,
        )

        # Patch network modules and the actual import targets
        with patch("urllib.request.urlopen") as mock_urlopen, patch(
            "marketsentry.fixture_capture_queue.add_capture_request",
            return_value=type("R", (), {
                "duplicate": False, "capture_request_id": 1
            })(),
        ), patch(
            "marketsentry.source_adapters.compliance.write_audit_record"
        ):
            result = adapter.dry_run(request)
            mock_urlopen.assert_not_called()

        assert result.network_call_performed is False

    @pytest.mark.parametrize("source", ["zillow", "realtor", "homes", "compass"])
    def test_adapter_retrieve_no_network(self, source):
        """Adapter retrieve does not perform network calls."""
        import importlib
        from marketsentry.source_adapters.base import RetrievalRequest

        adapter_names = {
            "zillow": "ZillowAdapter",
            "realtor": "RealtorAdapter",
            "homes": "HomesAdapter",
            "compass": "CompassAdapter",
        }
        test_urls = {
            "zillow": "https://www.zillow.com/homedetails/123/456_zpid/",
            "realtor": "https://www.realtor.com/realestateandhomes-detail/123",
            "homes": "https://www.homes.com/property/123-main-st/",
            "compass": "https://www.compass.com/listing/123-main-st/",
        }

        mod = importlib.import_module(
            f"marketsentry.source_adapters.{source}_adapter"
        )
        cls = getattr(mod, adapter_names[source])
        adapter = cls()

        request = RetrievalRequest(
            url=test_urls[source], source_name=source,
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            result = adapter.retrieve(request)
            mock_urlopen.assert_not_called()

        assert result.network_call_performed is False
        assert result.blocked is True


# ===========================================================================
# Metadata and Model Tests
# ===========================================================================


class TestCrossSiteFixtureMetadata:
    """Tests for fixture metadata loading."""

    def test_load_metadata(self):
        """load_cross_site_fixture_metadata computes content hash."""
        from marketsentry.cross_site_fixture_processor import (
            load_cross_site_fixture_metadata,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            fixture = _create_html_fixture(Path(tmpdir), "test.html")

            meta = load_cross_site_fixture_metadata(
                str(fixture), "zillow",
            )

            assert meta.source_site == "zillow"
            assert meta.content_hash
            assert meta.content_length > 0
            assert meta.fixture_path == str(fixture)


class TestFormatting:
    """Tests for formatting functions."""

    def test_format_processing_summary(self):
        """format_cross_site_processing_summary produces readable output."""
        from marketsentry.cross_site_fixture_processor import (
            format_cross_site_processing_summary,
            CrossSiteFixtureProcessingRunResult,
        )

        run = CrossSiteFixtureProcessingRunResult(
            files_scanned=10,
            files_processed=8,
            files_skipped=1,
            files_failed=1,
            observations_inserted=6,
            sources_processed=["zillow", "realtor"],
        )

        output = format_cross_site_processing_summary(run)
        assert "Files scanned" in output
        assert "10" in output
        assert "zillow" in output

    def test_format_health_summary_includes_cross_site(self):
        """format_retrieval_health_summary includes cross-site categories."""
        from marketsentry.retrieval_health import (
            format_retrieval_health_summary,
            RetrievalHealthSummary,
        )

        summary = RetrievalHealthSummary(
            checked_at=datetime.now().isoformat(),
            unprocessed_cross_site_fixture_count=3,
            stale_cross_site_capture_request_count=1,
            missing_parser_count=0,
        )

        output = format_retrieval_health_summary(summary)
        assert "Unprocessed cross-site" in output
        assert "Stale cross-site" in output
        assert "Missing parsers" in output
