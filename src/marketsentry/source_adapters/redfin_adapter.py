"""Redfin source adapter with dry-run preview and live HTTP retrieval.

Provides structured preview of what Redfin search and property detail
retrievals would do, and (when all safety checks pass) performs actual
HTTP retrieval saving pages as local fixtures.

Live retrieval is disabled by default and requires explicit opt-in via
environment variables, local robots policy, dry-run approval, rate limit
compliance, and policy checks. No browser automation or bypass mechanisms.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from marketsentry.logging_config import logger
from marketsentry.source_adapters.base import (
    RetrievalMode,
    RetrievalRequest,
    RetrievalResult,
    SourceAdapter,
    SourceAdapterConfig,
)
from marketsentry.source_adapters.compliance import (
    RetrievalComplianceConfig,
    check_retrieval_compliance,
    write_audit_record,
)
from marketsentry.source_adapters.dry_run_approval import (
    has_recent_dry_run_approval,
    record_dry_run_approval,
)
from marketsentry.source_adapters.http_client import (
    FakeHttpClient,
    HttpClient,
    HttpRequest,
    HttpResponse,
)
from marketsentry.source_adapters.policy import (
    FixtureCaptureRequest,
    evaluate_retrieval_policy,
    suggest_fixture_path,
)
from marketsentry.source_adapters.rate_limiter import (
    SourceRateLimitState,
    check_rate_limit,
    record_retrieval_attempt,
)
from marketsentry.source_adapters.robots_policy import (
    check_robots_allowed,
    load_local_robots_policy,
)


# ---------------------------------------------------------------------------
# Redfin URL validation helpers
# ---------------------------------------------------------------------------

REDFIN_DOMAINS = ["www.redfin.com", "redfin.com"]


def is_redfin_search_url(url: str) -> bool:
    """Check if a URL is a Redfin search URL.

    Args:
        url: URL to check.

    Returns:
        True if the URL looks like a Redfin search page.
    """
    try:
        parsed = urlparse(url)
        return (
            parsed.hostname in REDFIN_DOMAINS
            and "/city/" in parsed.path
            and "filter" in (parsed.path + "?" + (parsed.query or ""))
        )
    except Exception:
        return False


def is_redfin_property_url(url: str) -> bool:
    """Check if a URL is a Redfin property detail URL.

    Args:
        url: URL to check.

    Returns:
        True if the URL looks like a Redfin property detail page.
    """
    try:
        parsed = urlparse(url)
        return (
            parsed.hostname in REDFIN_DOMAINS
            and "/home/" in parsed.path
        )
    except Exception:
        return False


def extract_redfin_domain(url: str) -> str:
    """Extract domain from a Redfin URL.

    Args:
        url: URL to parse.

    Returns:
        Domain string.
    """
    try:
        parsed = urlparse(url)
        return parsed.hostname or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Redfin adapter
# ---------------------------------------------------------------------------


def _default_redfin_config() -> SourceAdapterConfig:
    """Create default Redfin adapter configuration."""
    return SourceAdapterConfig(
        source_name="redfin",
        display_name="Redfin",
        allowed_domains=REDFIN_DOMAINS,
        default_mode=RetrievalMode.MANUAL_FIXTURE,
        current_mode=RetrievalMode.MANUAL_FIXTURE,
        fixture_directory="data/raw/redfin",
        supports_search=True,
        supports_property_detail=True,
        supports_listing_history=True,
        notes="Primary source. Search and detail page parsing from saved fixtures.",
    )


class RedfinAdapter(SourceAdapter):
    """Redfin source adapter with dry-run preview support.

    Supports search page and property detail page retrieval previews.
    Live retrieval is blocked unless explicitly enabled. No network
    calls are performed in dry-run mode.
    """

    def __init__(self, config: Optional[SourceAdapterConfig] = None) -> None:
        """Initialize the Redfin adapter.

        Args:
            config: Adapter configuration. Uses defaults if None.
        """
        super().__init__(config or _default_redfin_config())
        self._rate_limit_state = SourceRateLimitState(source_site="redfin")

    def validate_request(self, request: RetrievalRequest) -> RetrievalResult:
        """Validate a Redfin retrieval request.

        Args:
            request: The retrieval request to validate.

        Returns:
            RetrievalResult indicating validity.
        """
        result = RetrievalResult(
            source_name="redfin",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=request.retrieval_mode,
            dry_run=True,
            network_call_performed=False,
        )

        if not request.url:
            result.blocked = True
            result.block_reason = "URL is required."
            return result

        domain = extract_redfin_domain(request.url)
        if domain not in REDFIN_DOMAINS:
            result.blocked = True
            result.block_reason = f"Domain '{domain}' is not a Redfin domain."
            return result

        if request.request_type == "search":
            if not is_redfin_search_url(request.url):
                result.blocked = True
                result.block_reason = "URL does not match Redfin search URL pattern."
                return result
        elif request.request_type == "property_detail":
            if not is_redfin_property_url(request.url):
                result.blocked = True
                result.block_reason = "URL does not match Redfin property URL pattern."
                return result

        result.success = True
        result.blocked = False
        return result

    def build_search_request_preview(self, url: str) -> RetrievalResult:
        """Build a preview of what a search retrieval would do.

        Args:
            url: Redfin search URL.

        Returns:
            RetrievalResult with dry-run preview details.
        """
        return self.dry_run(
            RetrievalRequest(
                source_name="redfin",
                url=url,
                request_type="search",
                retrieval_mode=RetrievalMode.DRY_RUN,
            )
        )

    def build_property_request_preview(self, url: str) -> RetrievalResult:
        """Build a preview of what a property detail retrieval would do.

        Args:
            url: Redfin property detail URL.

        Returns:
            RetrievalResult with dry-run preview details.
        """
        return self.dry_run(
            RetrievalRequest(
                source_name="redfin",
                url=url,
                request_type="property_detail",
                retrieval_mode=RetrievalMode.DRY_RUN,
            )
        )

    def dry_run_search(self, url: str) -> RetrievalResult:
        """Dry-run preview for a Redfin search page retrieval.

        Args:
            url: Redfin search URL.

        Returns:
            RetrievalResult with preview and compliance information.
        """
        return self.build_search_request_preview(url)

    def dry_run_property_detail(self, url: str) -> RetrievalResult:
        """Dry-run preview for a Redfin property detail retrieval.

        Args:
            url: Redfin property detail URL.

        Returns:
            RetrievalResult with preview and compliance information.
        """
        return self.build_property_request_preview(url)

    def dry_run(self, request: RetrievalRequest) -> RetrievalResult:
        """Preview what a Redfin retrieval would do without network calls.

        Args:
            request: The retrieval request to preview.

        Returns:
            RetrievalResult with dry_run=True and preview details.
        """
        # Validate first
        validation = self.validate_request(request)
        if validation.blocked:
            write_audit_record(
                source_site="redfin",
                retrieval_mode="dry_run",
                url=request.url,
                domain=extract_redfin_domain(request.url),
                allowed=False,
                blocked=True,
                reason=validation.block_reason,
                dry_run=True,
                network_call_performed=False,
            )
            return validation

        domain = extract_redfin_domain(request.url)

        # Check compliance for live mode
        compliance = check_retrieval_compliance(
            source_name="redfin",
            domain=domain,
            retrieval_mode="live_http",
        )

        # Build preview
        if request.request_type == "search":
            preview_lines = [
                "DRY-RUN: Redfin Search Page Retrieval Preview",
                f"URL: {request.url}",
                f"Domain: {domain}",
                f"Request Type: search",
                f"Action: Would fetch search results page via HTTP GET",
                f"Parser: redfin_fixture_parser.parse_redfin_search_page",
                f"Output: Candidate URLs extracted from search results",
                "",
                "Live Mode Compliance:",
                f"  Live retrieval globally enabled: {compliance.live_retrieval_enabled}",
                f"  Source allowlisted: {compliance.source_allowlisted}",
                f"  Rate limit configured: {compliance.rate_limit_configured}",
                f"  User-Agent configured: {compliance.user_agent_configured}",
                f"  Would be blocked in live mode: {compliance.blocked}",
            ]
            if compliance.reasons:
                preview_lines.append(f"  Reasons: {'; '.join(compliance.reasons)}")
        else:
            preview_lines = [
                "DRY-RUN: Redfin Property Detail Retrieval Preview",
                f"URL: {request.url}",
                f"Domain: {domain}",
                f"Request Type: property_detail",
                f"Action: Would fetch property detail page via HTTP GET",
                f"Parser: redfin_detail_parser.parse_redfin_detail_page",
                f"Output: Property facts, listing history, scores extracted",
                "",
                "Live Mode Compliance:",
                f"  Live retrieval globally enabled: {compliance.live_retrieval_enabled}",
                f"  Source allowlisted: {compliance.source_allowlisted}",
                f"  Rate limit configured: {compliance.rate_limit_configured}",
                f"  User-Agent configured: {compliance.user_agent_configured}",
                f"  Would be blocked in live mode: {compliance.blocked}",
            ]
            if compliance.reasons:
                preview_lines.append(f"  Reasons: {'; '.join(compliance.reasons)}")

        preview = "\n".join(preview_lines)

        result = RetrievalResult(
            source_name="redfin",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=RetrievalMode.DRY_RUN,
            success=True,
            blocked=False,
            dry_run=True,
            dry_run_preview=preview,
            network_call_performed=False,
            compliance_warnings=compliance.warnings,
        )

        write_audit_record(
            source_site="redfin",
            retrieval_mode="dry_run",
            url=request.url,
            domain=domain,
            allowed=True,
            blocked=False,
            reason="Dry-run preview generated successfully.",
            dry_run=True,
            network_call_performed=False,
        )

        # Record dry-run approval for future live retrieval gate
        compliance_summary = "blocked" if compliance.blocked else "would_be_allowed"
        record_dry_run_approval(
            source_site="redfin",
            url=request.url,
            request_type=request.request_type,
            compliance_status=compliance_summary,
            allowed=True,
            blocked=compliance.blocked,
            reasons=compliance.reasons,
        )

        # Add fixture capture request if live retrieval would be blocked
        if compliance.blocked:
            try:
                from marketsentry.fixture_capture_queue import add_capture_request

                add_capture_request(
                    FixtureCaptureRequest(
                        source_site="redfin",
                        source_url=request.url,
                        request_type=request.request_type,
                        reason="Live retrieval blocked; manual fixture capture recommended.",
                    )
                )
            except Exception:
                pass  # Queue add is best-effort; don't block dry-run

        return result

    def retrieve_search(self, url: str, http_client: Optional[HttpClient] = None) -> RetrievalResult:
        """Retrieve a Redfin search page via HTTP if all checks pass.

        Args:
            url: Redfin search URL.
            http_client: HTTP client (inject FakeHttpClient for tests).

        Returns:
            RetrievalResult with retrieval outcome.
        """
        return self.retrieve(
            RetrievalRequest(
                source_name="redfin",
                url=url,
                request_type="search",
                retrieval_mode=RetrievalMode.LIVE_HTTP,
            ),
            http_client=http_client,
        )

    def retrieve_property_detail(self, url: str, http_client: Optional[HttpClient] = None) -> RetrievalResult:
        """Retrieve a Redfin property detail page via HTTP if all checks pass.

        Args:
            url: Redfin property detail URL.
            http_client: HTTP client (inject FakeHttpClient for tests).

        Returns:
            RetrievalResult with retrieval outcome.
        """
        return self.retrieve(
            RetrievalRequest(
                source_name="redfin",
                url=url,
                request_type="property_detail",
                retrieval_mode=RetrievalMode.LIVE_HTTP,
            ),
            http_client=http_client,
        )

    def retrieve(
        self,
        request: RetrievalRequest,
        http_client: Optional[HttpClient] = None,
    ) -> RetrievalResult:
        """Attempt live HTTP retrieval with full policy enforcement.

        Runs all safety checks: compliance, robots policy, rate limiting,
        dry-run approval. If any check fails, the request is blocked and
        a fixture capture request is created as fallback.

        When all checks pass and an HTTP client is provided, performs one
        GET request and saves the response as a local fixture.

        Args:
            request: The retrieval request.
            http_client: HTTP client to use. None = no live retrieval possible.

        Returns:
            RetrievalResult with outcome, fixture path, and audit info.
        """
        domain = extract_redfin_domain(request.url)
        cc = RetrievalComplianceConfig.from_env()

        # -- Step 1: Basic compliance check --
        compliance = check_retrieval_compliance(
            source_name="redfin",
            domain=domain,
            retrieval_mode=str(request.retrieval_mode.value),
            compliance_config=cc,
        )

        if compliance.blocked:
            return self._block_retrieval(request, domain, compliance)

        # -- Step 2: Robots policy check --
        robots_policy = load_local_robots_policy("redfin")
        if robots_policy is None:
            reason = (
                "No local robots policy found for Redfin. "
                "Save robots.txt to data/policies/robots/redfin_robots.txt before live retrieval."
            )
            return self._block_retrieval_reason(request, domain, reason)

        parsed_url = urlparse(request.url)
        user_agent = cc.live_user_agent or "MarketSentry"
        robots_check = check_robots_allowed(robots_policy, user_agent, parsed_url.path)
        if not robots_check.allowed:
            reason = f"Robots policy blocks this path: {robots_check.notes}"
            return self._block_retrieval_reason(request, domain, reason)

        # -- Step 3: Rate limit check --
        rate_check = check_rate_limit(
            "redfin",
            state=self._rate_limit_state,
        )
        if rate_check.decision.value != "allowed":
            reason = f"Rate limit: {rate_check.message}"
            return self._block_retrieval_reason(request, domain, reason)

        # -- Step 4: Dry-run approval check --
        if cc.require_dry_run_before_live:
            has_approval = has_recent_dry_run_approval(
                source_site="redfin",
                url=request.url,
            )
            if not has_approval:
                reason = (
                    "No recent dry-run approval found. Run dry-run-redfin-search or "
                    "dry-run-redfin-property first."
                )
                return self._block_retrieval_reason(request, domain, reason)

        # -- Step 5: HTTP client check --
        if http_client is None:
            reason = (
                "No HTTP client provided. Live retrieval requires an HTTP client. "
                "Use --force-live with CLI commands."
            )
            return self._block_retrieval_reason(request, domain, reason)

        # -- Step 6: Perform HTTP GET --
        headers = {
            "User-Agent": cc.live_user_agent,
            "Accept": "text/html,application/xhtml+xml",
        }
        if cc.live_contact_email:
            headers["From"] = cc.live_contact_email

        http_request = HttpRequest(
            url=request.url,
            headers=headers,
            timeout_seconds=30,
            max_response_bytes=10 * 1024 * 1024,
        )

        http_response = http_client.get(http_request)

        # Record rate limit attempt (even for failed requests)
        record_retrieval_attempt(self._rate_limit_state)

        # -- Step 7: Handle HTTP errors --
        if http_response.timed_out:
            write_audit_record(
                source_site="redfin",
                retrieval_mode="live_http",
                url=request.url,
                domain=domain,
                allowed=True,
                blocked=False,
                reason=f"HTTP timeout: {http_response.error}",
                dry_run=False,
                network_call_performed=True,
            )
            return RetrievalResult(
                source_name="redfin", url=request.url,
                request_type=request.request_type,
                retrieval_mode=request.retrieval_mode,
                success=False, blocked=False, dry_run=False,
                network_call_performed=True,
                error_message=http_response.error,
            )

        if http_response.too_large:
            write_audit_record(
                source_site="redfin",
                retrieval_mode="live_http",
                url=request.url,
                domain=domain,
                allowed=True,
                blocked=True,
                reason=f"Response too large: {http_response.error}",
                dry_run=False,
                network_call_performed=True,
            )
            return RetrievalResult(
                source_name="redfin", url=request.url,
                request_type=request.request_type,
                retrieval_mode=request.retrieval_mode,
                success=False, blocked=True, dry_run=False,
                network_call_performed=True,
                error_message=http_response.error,
            )

        if not http_response.is_success:
            write_audit_record(
                source_site="redfin",
                retrieval_mode="live_http",
                url=request.url,
                domain=domain,
                allowed=True,
                blocked=False,
                reason=f"HTTP error: {http_response.error or http_response.status_code}",
                dry_run=False,
                network_call_performed=True,
            )
            return RetrievalResult(
                source_name="redfin", url=request.url,
                request_type=request.request_type,
                retrieval_mode=request.retrieval_mode,
                success=False, blocked=False, dry_run=False,
                network_call_performed=True,
                error_message=http_response.error or f"HTTP {http_response.status_code}",
            )

        # -- Step 8: Save fixture --
        fixture_path = self.save_retrieved_fixture(
            html_content=http_response.text,
            url=request.url,
            request_type=request.request_type,
        )

        # -- Step 9: Audit success --
        write_audit_record(
            source_site="redfin",
            retrieval_mode="live_http",
            url=request.url,
            domain=domain,
            allowed=True,
            blocked=False,
            reason=f"Live retrieval successful. Fixture saved to {fixture_path}.",
            dry_run=False,
            network_call_performed=True,
        )

        return RetrievalResult(
            source_name="redfin",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=request.retrieval_mode,
            success=True,
            blocked=False,
            dry_run=False,
            network_call_performed=True,
            fixture_path=fixture_path,
        )

    # -- Fixture saving --

    def save_retrieved_fixture(
        self,
        html_content: str,
        url: str,
        request_type: str,
        output_dir: Optional[str] = None,
    ) -> str:
        """Save retrieved HTML as a local fixture file.

        Creates directories if missing, generates timestamped filenames,
        and writes a sidecar metadata JSON file.

        Args:
            html_content: Raw HTML content to save.
            url: Source URL.
            request_type: Request type (search, property_detail).
            output_dir: Override output directory.

        Returns:
            Path to the saved fixture file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if request_type == "search":
            base_dir = Path(output_dir or "data/raw/redfin/search")
            filename = f"redfin_search_{timestamp}.html"
        else:
            slug = _url_to_slug(url)
            base_dir = Path(output_dir or "data/raw/redfin/details")
            filename = f"redfin_property_{slug}_{timestamp}.html"

        base_dir.mkdir(parents=True, exist_ok=True)

        fixture_path = base_dir / filename

        # Don't overwrite existing fixtures
        counter = 1
        while fixture_path.exists():
            stem = fixture_path.stem
            fixture_path = base_dir / f"{stem}_{counter}.html"
            counter += 1

        fixture_path.write_text(html_content, encoding="utf-8")

        # Write sidecar metadata
        metadata = {
            "source_url": url,
            "source_site": "redfin",
            "request_type": request_type,
            "retrieved_at": datetime.now().isoformat(),
            "fixture_path": str(fixture_path),
            "content_length": len(html_content),
        }
        metadata_path = fixture_path.with_suffix(".json")
        metadata_path.write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )

        logger.info(f"Saved Redfin fixture: {fixture_path}")
        return str(fixture_path)

    def retrieve_and_save_search_fixture(
        self, url: str, http_client: Optional[HttpClient] = None, output_dir: Optional[str] = None,
    ) -> RetrievalResult:
        """Retrieve a Redfin search page and save as fixture.

        Convenience method combining retrieve + save.

        Args:
            url: Redfin search URL.
            http_client: HTTP client.
            output_dir: Override output directory.

        Returns:
            RetrievalResult with fixture path if successful.
        """
        return self.retrieve_search(url, http_client=http_client)

    def retrieve_and_save_property_fixture(
        self, url: str, http_client: Optional[HttpClient] = None, output_dir: Optional[str] = None,
    ) -> RetrievalResult:
        """Retrieve a Redfin property page and save as fixture.

        Convenience method combining retrieve + save.

        Args:
            url: Redfin property detail URL.
            http_client: HTTP client.
            output_dir: Override output directory.

        Returns:
            RetrievalResult with fixture path if successful.
        """
        return self.retrieve_property_detail(url, http_client=http_client)

    # -- Helper methods --

    def _block_retrieval(
        self, request: RetrievalRequest, domain: str, compliance: object,
    ) -> RetrievalResult:
        """Block a retrieval and create a fixture capture request.

        Args:
            request: The retrieval request.
            domain: Domain being accessed.
            compliance: ComplianceCheckResult with reasons.

        Returns:
            Blocked RetrievalResult.
        """
        reason = "; ".join(compliance.reasons)
        write_audit_record(
            source_site="redfin",
            retrieval_mode=str(request.retrieval_mode.value),
            url=request.url,
            domain=domain,
            allowed=False,
            blocked=True,
            reason=reason,
            dry_run=False,
            network_call_performed=False,
        )

        try:
            from marketsentry.fixture_capture_queue import add_capture_request

            add_capture_request(
                FixtureCaptureRequest(
                    source_site="redfin",
                    source_url=request.url,
                    request_type=request.request_type,
                    reason=f"Live retrieval blocked: {reason}",
                )
            )
        except Exception:
            pass

        return RetrievalResult(
            source_name="redfin",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=request.retrieval_mode,
            success=False,
            blocked=True,
            block_reason=reason,
            dry_run=False,
            network_call_performed=False,
            compliance_warnings=getattr(compliance, "warnings", []),
        )

    def _block_retrieval_reason(
        self, request: RetrievalRequest, domain: str, reason: str,
    ) -> RetrievalResult:
        """Block a retrieval with a specific reason string.

        Args:
            request: The retrieval request.
            domain: Domain being accessed.
            reason: Block reason message.

        Returns:
            Blocked RetrievalResult.
        """
        write_audit_record(
            source_site="redfin",
            retrieval_mode=str(request.retrieval_mode.value),
            url=request.url,
            domain=domain,
            allowed=False,
            blocked=True,
            reason=reason,
            dry_run=False,
            network_call_performed=False,
        )

        try:
            from marketsentry.fixture_capture_queue import add_capture_request

            add_capture_request(
                FixtureCaptureRequest(
                    source_site="redfin",
                    source_url=request.url,
                    request_type=request.request_type,
                    reason=f"Live retrieval blocked: {reason}",
                )
            )
        except Exception:
            pass

        return RetrievalResult(
            source_name="redfin",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=request.retrieval_mode,
            success=False,
            blocked=True,
            block_reason=reason,
            dry_run=False,
            network_call_performed=False,
        )

    def get_supported_modes(self) -> List[RetrievalMode]:
        """Return supported retrieval modes for Redfin.

        Returns:
            List of supported modes.
        """
        return [
            RetrievalMode.DISABLED,
            RetrievalMode.DRY_RUN,
            RetrievalMode.MANUAL_FIXTURE,
            RetrievalMode.LIVE_HTTP,
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _url_to_slug(url: str) -> str:
    """Convert a URL to a filesystem-safe slug for fixture filenames.

    Args:
        url: URL to convert.

    Returns:
        Sanitized slug string.
    """
    try:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        # Extract home ID if present
        match = re.search(r"/home/(\d+)", parsed.path)
        if match:
            return match.group(1)
        # Use last path component
        parts = path.split("/")
        slug = parts[-1] if parts else "unknown"
        # Sanitize
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", slug)
        return slug[:80] or "unknown"
    except Exception:
        return "unknown"
