"""Redfin source adapter with dry-run preview support.

Provides structured preview of what Redfin search and property detail
retrievals would do, without performing any network calls. Live retrieval
is blocked unless explicitly enabled and compliance checks pass.

No active scraping, browser automation, or bypass mechanisms are implemented.
"""

from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

from marketsentry.source_adapters.base import (
    RetrievalMode,
    RetrievalRequest,
    RetrievalResult,
    SourceAdapter,
    SourceAdapterConfig,
)
from marketsentry.source_adapters.compliance import (
    check_retrieval_compliance,
    write_audit_record,
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

        return result

    def retrieve_search(self, url: str) -> RetrievalResult:
        """Retrieve a Redfin search page. Blocked in this milestone.

        Args:
            url: Redfin search URL.

        Returns:
            RetrievalResult with blocked status.
        """
        return self.retrieve(
            RetrievalRequest(
                source_name="redfin",
                url=url,
                request_type="search",
                retrieval_mode=RetrievalMode.LIVE_HTTP,
            )
        )

    def retrieve_property_detail(self, url: str) -> RetrievalResult:
        """Retrieve a Redfin property detail page. Blocked in this milestone.

        Args:
            url: Redfin property detail URL.

        Returns:
            RetrievalResult with blocked status.
        """
        return self.retrieve(
            RetrievalRequest(
                source_name="redfin",
                url=url,
                request_type="property_detail",
                retrieval_mode=RetrievalMode.LIVE_HTTP,
            )
        )

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Attempt retrieval. Blocked unless compliance checks pass.

        Even when compliance checks pass, live retrieval is not implemented
        in this milestone and returns a not-implemented result.

        Args:
            request: The retrieval request.

        Returns:
            RetrievalResult with blocked or not-implemented status.
        """
        domain = extract_redfin_domain(request.url)

        compliance = check_retrieval_compliance(
            source_name="redfin",
            domain=domain,
            retrieval_mode=str(request.retrieval_mode.value),
        )

        if compliance.blocked:
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
                compliance_warnings=compliance.warnings,
            )

        # Compliance passed but live retrieval is not implemented yet
        not_impl_reason = (
            "Live HTTP retrieval is not implemented in this milestone. "
            "Use dry-run commands to preview or manual fixtures for data."
        )

        write_audit_record(
            source_site="redfin",
            retrieval_mode=str(request.retrieval_mode.value),
            url=request.url,
            domain=domain,
            allowed=False,
            blocked=True,
            reason=not_impl_reason,
            dry_run=False,
            network_call_performed=False,
        )

        return RetrievalResult(
            source_name="redfin",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=request.retrieval_mode,
            success=False,
            blocked=True,
            block_reason=not_impl_reason,
            dry_run=False,
            network_call_performed=False,
            compliance_warnings=compliance.warnings,
            error_message=not_impl_reason,
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
