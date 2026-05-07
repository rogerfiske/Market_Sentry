"""Tests for Milestone 14: Live Retrieval Strategy and Compliance Adapters.

Tests source adapter architecture, compliance guardrails, dry-run previews,
audit logging, and CLI commands. No network calls are performed.
"""

import csv
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from marketsentry.source_adapters.base import (
    RetrievalMode,
    RetrievalRequest,
    RetrievalResult,
    SourceAdapterConfig,
)
from marketsentry.source_adapters.compliance import (
    ComplianceCheckResult,
    RateLimitConfig,
    RetrievalComplianceConfig,
    RobotsCheckResult,
    check_retrieval_compliance,
    get_compliance_status,
    write_audit_record,
)
from marketsentry.source_adapters.registry import SourceAdapterRegistry, get_registry
from marketsentry.source_adapters.redfin_adapter import (
    RedfinAdapter,
    is_redfin_property_url,
    is_redfin_search_url,
)


# ---------------------------------------------------------------------------
# Test: RetrievalMode enum
# ---------------------------------------------------------------------------


class TestRetrievalMode:
    """Test RetrievalMode enum values."""

    def test_disabled_value(self):
        """disabled mode exists."""
        assert RetrievalMode.DISABLED == "disabled"

    def test_dry_run_value(self):
        """dry_run mode exists."""
        assert RetrievalMode.DRY_RUN == "dry_run"

    def test_manual_fixture_value(self):
        """manual_fixture mode exists."""
        assert RetrievalMode.MANUAL_FIXTURE == "manual_fixture"

    def test_authorized_api_value(self):
        """authorized_api mode exists."""
        assert RetrievalMode.AUTHORIZED_API == "authorized_api"

    def test_live_http_value(self):
        """live_http mode exists."""
        assert RetrievalMode.LIVE_HTTP == "live_http"

    def test_all_modes_present(self):
        """All expected modes are present."""
        names = [m.value for m in RetrievalMode]
        assert "disabled" in names
        assert "dry_run" in names
        assert "manual_fixture" in names
        assert "authorized_api" in names
        assert "live_http" in names


# ---------------------------------------------------------------------------
# Test: Config defaults
# ---------------------------------------------------------------------------


class TestConfigDefaults:
    """Test that live retrieval is disabled by default in config."""

    def test_compliance_config_defaults_disabled(self):
        """RetrievalComplianceConfig defaults to live retrieval disabled."""
        cc = RetrievalComplianceConfig()
        assert cc.live_retrieval_enabled is False

    def test_compliance_config_no_allowed_sources(self):
        """Default config has no allowed live sources."""
        cc = RetrievalComplianceConfig()
        assert cc.allowed_live_sources == []

    def test_compliance_config_no_user_agent(self):
        """Default config has no User-Agent."""
        cc = RetrievalComplianceConfig()
        assert cc.live_user_agent == ""

    def test_compliance_config_no_contact_email(self):
        """Default config has no contact email."""
        cc = RetrievalComplianceConfig()
        assert cc.live_contact_email == ""

    def test_compliance_config_conservative_rate_limit(self):
        """Default rate limit is conservative (6 req/min)."""
        cc = RetrievalComplianceConfig()
        assert cc.max_requests_per_minute == 6

    def test_compliance_config_dry_run_required(self):
        """Default config requires dry-run before live."""
        cc = RetrievalComplianceConfig()
        assert cc.require_dry_run_before_live is True

    def test_from_env_defaults(self):
        """from_env with no env vars returns disabled defaults."""
        # Clear any test env vars
        env_vars = {
            "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "",
            "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "",
            "MARKETSENTRY_LIVE_USER_AGENT": "",
            "MARKETSENTRY_LIVE_CONTACT_EMAIL": "",
            "MARKETSENTRY_MAX_REQUESTS_PER_MINUTE": "6",
            "MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE": "true",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            cc = RetrievalComplianceConfig.from_env()
            assert cc.live_retrieval_enabled is False

    def test_from_env_enabled(self):
        """from_env parses enabled=true correctly."""
        env_vars = {
            "MARKETSENTRY_LIVE_RETRIEVAL_ENABLED": "true",
            "MARKETSENTRY_ALLOWED_LIVE_SOURCES": "redfin,zillow",
            "MARKETSENTRY_LIVE_USER_AGENT": "TestBot/1.0",
            "MARKETSENTRY_LIVE_CONTACT_EMAIL": "test@example.com",
            "MARKETSENTRY_MAX_REQUESTS_PER_MINUTE": "3",
            "MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE": "false",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            cc = RetrievalComplianceConfig.from_env()
            assert cc.live_retrieval_enabled is True
            assert "redfin" in cc.allowed_live_sources
            assert "zillow" in cc.allowed_live_sources
            assert cc.live_user_agent == "TestBot/1.0"
            assert cc.live_contact_email == "test@example.com"
            assert cc.max_requests_per_minute == 3
            assert cc.require_dry_run_before_live is False


# ---------------------------------------------------------------------------
# Test: Compliance blocks
# ---------------------------------------------------------------------------


class TestComplianceBlocks:
    """Test that compliance blocks live retrieval by default."""

    def test_blocks_live_by_default(self):
        """Live retrieval is blocked with default config."""
        cc = RetrievalComplianceConfig()  # All defaults
        result = check_retrieval_compliance(
            source_name="redfin",
            domain="www.redfin.com",
            retrieval_mode="live_http",
            compliance_config=cc,
        )
        assert result.blocked is True
        assert result.allowed is False

    def test_allows_dry_run(self):
        """Dry-run mode is always allowed."""
        cc = RetrievalComplianceConfig()
        result = check_retrieval_compliance(
            source_name="redfin",
            domain="www.redfin.com",
            retrieval_mode="dry_run",
            compliance_config=cc,
        )
        assert result.allowed is True
        assert result.blocked is False

    def test_allows_manual_fixture(self):
        """Manual fixture mode is always allowed."""
        cc = RetrievalComplianceConfig()
        result = check_retrieval_compliance(
            source_name="redfin",
            domain="www.redfin.com",
            retrieval_mode="manual_fixture",
            compliance_config=cc,
        )
        assert result.allowed is True
        assert result.blocked is False

    def test_blocks_unallowlisted_source(self):
        """Blocks live retrieval for source not in allowlist."""
        cc = RetrievalComplianceConfig(
            live_retrieval_enabled=True,
            allowed_live_sources=["zillow"],
            live_user_agent="TestBot/1.0",
            max_requests_per_minute=6,
        )
        result = check_retrieval_compliance(
            source_name="redfin",
            domain="www.redfin.com",
            retrieval_mode="live_http",
            compliance_config=cc,
        )
        assert result.blocked is True
        assert result.source_allowlisted is False

    def test_blocks_missing_rate_limit(self):
        """Blocks live retrieval when rate limit is zero."""
        cc = RetrievalComplianceConfig(
            live_retrieval_enabled=True,
            allowed_live_sources=["redfin"],
            live_user_agent="TestBot/1.0",
            max_requests_per_minute=0,
        )
        result = check_retrieval_compliance(
            source_name="redfin",
            domain="www.redfin.com",
            retrieval_mode="live_http",
            compliance_config=cc,
        )
        assert result.blocked is True
        assert result.rate_limit_configured is False

    def test_blocks_missing_user_agent(self):
        """Blocks live retrieval when User-Agent is missing."""
        cc = RetrievalComplianceConfig(
            live_retrieval_enabled=True,
            allowed_live_sources=["redfin"],
            live_user_agent="",
            max_requests_per_minute=6,
        )
        result = check_retrieval_compliance(
            source_name="redfin",
            domain="www.redfin.com",
            retrieval_mode="live_http",
            compliance_config=cc,
        )
        assert result.blocked is True
        assert result.user_agent_configured is False

    def test_warns_missing_contact(self):
        """Warns (but doesn't block) when contact email is missing."""
        cc = RetrievalComplianceConfig(
            live_retrieval_enabled=True,
            allowed_live_sources=["redfin"],
            live_user_agent="TestBot/1.0",
            live_contact_email="",
            max_requests_per_minute=6,
        )
        result = check_retrieval_compliance(
            source_name="redfin",
            domain="www.redfin.com",
            retrieval_mode="live_http",
            compliance_config=cc,
        )
        # Should be allowed (contact is a warning, not blocker)
        assert result.allowed is True
        assert result.contact_configured is False
        assert len(result.warnings) > 0

    def test_allows_fully_configured(self):
        """Allows live retrieval when fully configured."""
        cc = RetrievalComplianceConfig(
            live_retrieval_enabled=True,
            allowed_live_sources=["redfin"],
            live_user_agent="TestBot/1.0",
            live_contact_email="test@example.com",
            max_requests_per_minute=6,
        )
        result = check_retrieval_compliance(
            source_name="redfin",
            domain="www.redfin.com",
            retrieval_mode="live_http",
            compliance_config=cc,
        )
        assert result.allowed is True
        assert result.blocked is False


# ---------------------------------------------------------------------------
# Test: Dry-run no network calls
# ---------------------------------------------------------------------------


class TestDryRunNoNetwork:
    """Test that dry-run performs no network calls."""

    def test_redfin_search_dry_run_no_network(self):
        """Redfin search dry-run has network_call_performed=False."""
        adapter = RedfinAdapter()
        result = adapter.dry_run_search(
            "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house"
        )
        assert result.network_call_performed is False
        assert result.dry_run is True

    def test_redfin_property_dry_run_no_network(self):
        """Redfin property dry-run has network_call_performed=False."""
        adapter = RedfinAdapter()
        result = adapter.dry_run_property_detail(
            "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
        )
        assert result.network_call_performed is False
        assert result.dry_run is True


# ---------------------------------------------------------------------------
# Test: Redfin URL validation
# ---------------------------------------------------------------------------


class TestRedfinURLValidation:
    """Test Redfin URL validation helpers."""

    def test_valid_search_url(self):
        """Recognizes valid Redfin search URL."""
        url = "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house"
        assert is_redfin_search_url(url) is True

    def test_invalid_search_url_no_filter(self):
        """Rejects search URL without filter."""
        url = "https://www.redfin.com/city/19701/CA/Temecula"
        assert is_redfin_search_url(url) is False

    def test_valid_property_url(self):
        """Recognizes valid Redfin property URL."""
        url = "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
        assert is_redfin_property_url(url) is True

    def test_invalid_property_url(self):
        """Rejects non-Redfin URL."""
        url = "https://www.zillow.com/homedetails/123"
        assert is_redfin_property_url(url) is False

    def test_empty_url(self):
        """Empty URL returns False for both."""
        assert is_redfin_search_url("") is False
        assert is_redfin_property_url("") is False


# ---------------------------------------------------------------------------
# Test: Redfin adapter dry-run preview
# ---------------------------------------------------------------------------


class TestRedfinDryRunPreview:
    """Test Redfin adapter dry-run preview output."""

    def test_search_preview_has_content(self):
        """Search dry-run preview contains expected information."""
        adapter = RedfinAdapter()
        result = adapter.dry_run_search(
            "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house"
        )
        assert result.success is True
        assert "DRY-RUN" in result.dry_run_preview
        assert "search" in result.dry_run_preview.lower()
        assert "www.redfin.com" in result.dry_run_preview

    def test_property_preview_has_content(self):
        """Property dry-run preview contains expected information."""
        adapter = RedfinAdapter()
        result = adapter.dry_run_property_detail(
            "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
        )
        assert result.success is True
        assert "DRY-RUN" in result.dry_run_preview
        assert "property_detail" in result.dry_run_preview.lower()

    def test_search_preview_shows_compliance(self):
        """Search preview includes compliance status."""
        adapter = RedfinAdapter()
        result = adapter.dry_run_search(
            "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house"
        )
        assert "Live Mode Compliance" in result.dry_run_preview

    def test_invalid_url_blocked(self):
        """Invalid URL is blocked in dry-run."""
        adapter = RedfinAdapter()
        result = adapter.dry_run_search("https://www.zillow.com/search")
        assert result.blocked is True

    def test_empty_url_blocked(self):
        """Empty URL is blocked."""
        adapter = RedfinAdapter()
        request = RetrievalRequest(
            source_name="redfin", url="", request_type="search"
        )
        result = adapter.validate_request(request)
        assert result.blocked is True


# ---------------------------------------------------------------------------
# Test: Redfin retrieve is blocked
# ---------------------------------------------------------------------------


class TestRedfinRetrieveBlocked:
    """Test that Redfin live retrieve is blocked."""

    def test_search_retrieve_blocked(self):
        """Search retrieve is blocked by default."""
        adapter = RedfinAdapter()
        result = adapter.retrieve_search(
            "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house"
        )
        assert result.blocked is True
        assert result.network_call_performed is False

    def test_property_retrieve_blocked(self):
        """Property retrieve is blocked by default."""
        adapter = RedfinAdapter()
        result = adapter.retrieve_property_detail(
            "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263"
        )
        assert result.blocked is True
        assert result.network_call_performed is False

    def test_retrieve_blocked_when_no_robots_policy(self):
        """Live retrieve is blocked when no local robots policy is available."""
        cc = RetrievalComplianceConfig(
            live_retrieval_enabled=True,
            allowed_live_sources=["redfin"],
            live_user_agent="TestBot/1.0",
            live_contact_email="test@example.com",
            max_requests_per_minute=6,
        )
        with patch(
            "marketsentry.source_adapters.redfin_adapter.check_retrieval_compliance"
        ) as mock_check:
            mock_check.return_value = ComplianceCheckResult(
                allowed=True,
                blocked=False,
                source_name="redfin",
                reasons=["All compliance checks passed."],
            )
            adapter = RedfinAdapter()
            result = adapter.retrieve_search(
                "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house"
            )
            # Blocked because no local robots policy (M16 goes further than M14)
            assert result.blocked is True
            assert result.network_call_performed is False
            assert "robots" in result.block_reason.lower()


# ---------------------------------------------------------------------------
# Test: Source adapter registry
# ---------------------------------------------------------------------------


class TestSourceAdapterRegistry:
    """Test source adapter registry."""

    def test_registry_has_all_adapters(self):
        """Registry includes all expected adapters."""
        registry = get_registry()
        expected = ["redfin", "zillow", "realtor", "homes", "compass", "county"]
        for name in expected:
            assert registry.has(name), f"Adapter '{name}' not in registry"

    def test_registry_get_redfin(self):
        """Can get Redfin adapter from registry."""
        registry = get_registry()
        adapter = registry.get("redfin")
        assert adapter is not None
        assert adapter.source_name == "redfin"

    def test_registry_list_names(self):
        """list_names returns all registered names."""
        registry = get_registry()
        names = registry.list_names()
        assert len(names) == 6
        assert "redfin" in names

    def test_registry_list_adapters(self):
        """list_adapters returns all adapters."""
        registry = get_registry()
        adapters = registry.list_adapters()
        assert len(adapters) == 6

    def test_registry_get_nonexistent(self):
        """Getting a nonexistent adapter returns None."""
        registry = get_registry()
        assert registry.get("nonexistent") is None

    def test_empty_registry(self):
        """Empty registry has no adapters."""
        registry = SourceAdapterRegistry()
        assert registry.list_names() == []
        assert registry.has("redfin") is False


# ---------------------------------------------------------------------------
# Test: Audit record writing
# ---------------------------------------------------------------------------


class TestAuditRecords:
    """Test retrieval audit record writing."""

    def test_write_audit_record_creates_file(self):
        """write_audit_record creates a CSV audit file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_audit_record(
                source_site="redfin",
                retrieval_mode="dry_run",
                url="https://www.redfin.com/test",
                domain="www.redfin.com",
                allowed=True,
                blocked=False,
                reason="Dry-run preview.",
                dry_run=True,
                network_call_performed=False,
                audit_dir=tmpdir,
            )
            assert Path(path).exists()

    def test_audit_record_has_network_call_false(self):
        """Audit record has network_call_performed=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_audit_record(
                source_site="redfin",
                retrieval_mode="dry_run",
                url="https://www.redfin.com/test",
                domain="www.redfin.com",
                allowed=True,
                blocked=False,
                reason="Test.",
                dry_run=True,
                network_call_performed=False,
                audit_dir=tmpdir,
            )
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 1
                assert rows[0]["network_call_performed"] == "False"
                assert rows[0]["dry_run"] == "True"

    def test_audit_record_has_expected_fields(self):
        """Audit record contains all expected fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_audit_record(
                source_site="redfin",
                retrieval_mode="dry_run",
                url="https://www.redfin.com/test",
                domain="www.redfin.com",
                allowed=True,
                blocked=False,
                reason="Test record.",
                dry_run=True,
                network_call_performed=False,
                audit_dir=tmpdir,
            )
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                row = rows[0]
                assert "timestamp" in row
                assert "source_site" in row
                assert "retrieval_mode" in row
                assert "url" in row
                assert "domain" in row
                assert "allowed" in row
                assert "blocked" in row
                assert "reason" in row
                assert "dry_run" in row
                assert "network_call_performed" in row

    def test_audit_record_appends(self):
        """Multiple audit records append to same file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            write_audit_record(
                source_site="redfin",
                retrieval_mode="dry_run",
                url="https://www.redfin.com/1",
                domain="www.redfin.com",
                allowed=True,
                blocked=False,
                reason="First.",
                audit_dir=tmpdir,
            )
            path = write_audit_record(
                source_site="redfin",
                retrieval_mode="dry_run",
                url="https://www.redfin.com/2",
                domain="www.redfin.com",
                allowed=True,
                blocked=False,
                reason="Second.",
                audit_dir=tmpdir,
            )
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 2


# ---------------------------------------------------------------------------
# Test: CLI commands
# ---------------------------------------------------------------------------


class TestCLICommands:
    """Test CLI commands for source adapters and retrieval."""

    def test_source_adapters_command_exists(self):
        """source-adapters command is registered."""
        from marketsentry.cli import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "source-adapters" in command_names

    def test_retrieval_compliance_status_command_exists(self):
        """retrieval-compliance-status command is registered."""
        from marketsentry.cli import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "retrieval-compliance-status" in command_names

    def test_dry_run_redfin_search_command_exists(self):
        """dry-run-redfin-search command is registered."""
        from marketsentry.cli import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "dry-run-redfin-search" in command_names

    def test_dry_run_redfin_property_command_exists(self):
        """dry-run-redfin-property command is registered."""
        from marketsentry.cli import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "dry-run-redfin-property" in command_names

    def test_source_adapters_runs(self):
        """source-adapters command runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["source-adapters"])
        assert result.exit_code == 0
        assert "Source Adapters" in result.output

    def test_compliance_status_runs(self):
        """retrieval-compliance-status command runs without error."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["retrieval-compliance-status"])
        assert result.exit_code == 0
        assert "Compliance" in result.output

    def test_dry_run_search_runs(self):
        """dry-run-redfin-search command runs with valid URL."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "dry-run-redfin-search",
                "--url",
                "https://www.redfin.com/city/19701/CA/Temecula/filter/property-type=house",
            ],
        )
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output

    def test_dry_run_property_runs(self):
        """dry-run-redfin-property command runs with valid URL."""
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "dry-run-redfin-property",
                "--url",
                "https://www.redfin.com/CA/Temecula/46197-Via-La-Tranquila-92592/home/6574263",
            ],
        )
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output


# ---------------------------------------------------------------------------
# Test: Compliance status helper
# ---------------------------------------------------------------------------


class TestComplianceStatus:
    """Test get_compliance_status helper."""

    def test_status_blocked_by_default(self):
        """Default compliance status shows blocked."""
        cc = RetrievalComplianceConfig()
        status = get_compliance_status(cc)
        assert status["live_retrieval_blocked"] is True
        assert status["live_retrieval_globally_enabled"] is False

    def test_status_shows_audit_dir(self):
        """Compliance status includes audit directory."""
        cc = RetrievalComplianceConfig()
        status = get_compliance_status(cc)
        assert "retrieval_audit_dir" in status


# ---------------------------------------------------------------------------
# Test: Models
# ---------------------------------------------------------------------------


class TestModels:
    """Test Pydantic models for source adapters."""

    def test_retrieval_request_defaults(self):
        """RetrievalRequest has sensible defaults."""
        req = RetrievalRequest()
        assert req.retrieval_mode == RetrievalMode.DRY_RUN
        assert req.source_name == ""
        assert req.url == ""

    def test_retrieval_result_defaults(self):
        """RetrievalResult has sensible defaults."""
        res = RetrievalResult()
        assert res.dry_run is True
        assert res.network_call_performed is False
        assert res.blocked is False

    def test_source_adapter_config_defaults(self):
        """SourceAdapterConfig has disabled default mode."""
        cfg = SourceAdapterConfig()
        assert cfg.default_mode == RetrievalMode.DISABLED
        assert cfg.current_mode == RetrievalMode.DISABLED

    def test_rate_limit_config(self):
        """RateLimitConfig has conservative defaults."""
        rl = RateLimitConfig()
        assert rl.max_requests_per_minute == 6
        assert rl.min_delay_seconds == 10.0

    def test_robots_check_result(self):
        """RobotsCheckResult defaults to not checked."""
        r = RobotsCheckResult()
        assert r.checked is False
        assert r.allowed is False

    def test_compliance_check_result(self):
        """ComplianceCheckResult defaults to blocked."""
        c = ComplianceCheckResult()
        assert c.blocked is True
        assert c.allowed is False


# ---------------------------------------------------------------------------
# Test: No network calls
# ---------------------------------------------------------------------------


class TestNoNetworkCalls:
    """Verify source adapter modules do not import network libraries."""

    def test_base_no_requests(self):
        """base.py does not import network libraries."""
        import marketsentry.source_adapters.base as mod

        source = Path(mod.__file__).read_text()
        assert "import requests" not in source
        assert "import httpx" not in source
        assert "import urllib.request" not in source

    def test_compliance_no_requests(self):
        """compliance.py does not import network libraries."""
        import marketsentry.source_adapters.compliance as mod

        source = Path(mod.__file__).read_text()
        assert "import requests" not in source
        assert "import httpx" not in source

    def test_redfin_adapter_no_requests(self):
        """redfin_adapter.py does not import network libraries."""
        import marketsentry.source_adapters.redfin_adapter as mod

        source = Path(mod.__file__).read_text()
        assert "import requests" not in source
        assert "import httpx" not in source

    def test_no_selenium(self):
        """No adapter imports selenium."""
        import marketsentry.source_adapters as pkg

        pkg_dir = Path(pkg.__file__).parent
        for py_file in pkg_dir.glob("*.py"):
            source = py_file.read_text()
            assert "import selenium" not in source, f"{py_file.name} imports selenium"
            assert "from selenium" not in source, f"{py_file.name} imports selenium"

    def test_no_playwright(self):
        """No adapter imports playwright."""
        import marketsentry.source_adapters as pkg

        pkg_dir = Path(pkg.__file__).parent
        for py_file in pkg_dir.glob("*.py"):
            source = py_file.read_text()
            assert "import playwright" not in source, f"{py_file.name} imports playwright"
            assert "from playwright" not in source, f"{py_file.name} imports playwright"


# ---------------------------------------------------------------------------
# Test: Stub adapters
# ---------------------------------------------------------------------------


class TestStubAdapters:
    """Test stub adapter implementations."""

    def test_zillow_dry_run(self):
        """Zillow dry-run returns stub preview."""
        from marketsentry.source_adapters.zillow_adapter import ZillowAdapter

        adapter = ZillowAdapter()
        result = adapter.dry_run(RetrievalRequest(url="https://www.zillow.com/test"))
        assert result.dry_run is True
        assert result.network_call_performed is False

    def test_realtor_dry_run(self):
        """Realtor dry-run returns stub preview."""
        from marketsentry.source_adapters.realtor_adapter import RealtorAdapter

        adapter = RealtorAdapter()
        result = adapter.dry_run(RetrievalRequest(url="https://www.realtor.com/test"))
        assert result.dry_run is True
        assert result.network_call_performed is False

    def test_homes_dry_run(self):
        """Homes.com dry-run returns stub preview."""
        from marketsentry.source_adapters.homes_adapter import HomesAdapter

        adapter = HomesAdapter()
        result = adapter.dry_run(RetrievalRequest(url="https://www.homes.com/test"))
        assert result.dry_run is True
        assert result.network_call_performed is False

    def test_compass_dry_run(self):
        """Compass dry-run returns stub preview."""
        from marketsentry.source_adapters.compass_adapter import CompassAdapter

        adapter = CompassAdapter()
        result = adapter.dry_run(RetrievalRequest(url="https://www.compass.com/test"))
        assert result.dry_run is True
        assert result.network_call_performed is False

    def test_county_dry_run(self):
        """County dry-run returns stub preview."""
        from marketsentry.source_adapters.county_adapter import CountyAdapter

        adapter = CountyAdapter()
        result = adapter.dry_run(RetrievalRequest(url=""))
        assert result.dry_run is True
        assert result.network_call_performed is False

    def test_stub_retrieve_blocked(self):
        """Stub adapter retrieve methods return blocked."""
        from marketsentry.source_adapters.zillow_adapter import ZillowAdapter

        adapter = ZillowAdapter()
        result = adapter.retrieve(RetrievalRequest(url="https://www.zillow.com/test"))
        assert result.blocked is True
        assert result.network_call_performed is False
