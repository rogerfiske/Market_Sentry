"""Zillow source adapter with dry-run parity and manual fixture support.

Provides URL validation, request type inference, dry-run preview with
fixture capture queue integration, and audit logging. Live HTTP retrieval
is not implemented for Zillow. No network calls are performed.
"""

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

ZILLOW_DOMAINS = ["www.zillow.com", "zillow.com"]


def _default_zillow_config() -> SourceAdapterConfig:
    """Create default Zillow adapter configuration."""
    return SourceAdapterConfig(
        source_name="zillow",
        display_name="Zillow",
        allowed_domains=ZILLOW_DOMAINS,
        default_mode=RetrievalMode.MANUAL_FIXTURE,
        current_mode=RetrievalMode.MANUAL_FIXTURE,
        fixture_directory="data/raw/zillow/details",
        supports_search=False,
        supports_property_detail=True,
        supports_listing_history=False,
        notes="Cross-site validation source. Manual fixture parsing only.",
    )


def is_zillow_property_url(url: str) -> bool:
    """Check if a URL is a Zillow property detail URL.

    Args:
        url: URL to check.

    Returns:
        True if URL matches Zillow property pattern.
    """
    try:
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        if domain not in ZILLOW_DOMAINS:
            return False
        path = parsed.path.lower()
        return "/homedetails/" in path or "/homes/" in path
    except Exception:
        return False


def is_zillow_search_url(url: str) -> bool:
    """Check if a URL is a Zillow search URL.

    Args:
        url: URL to check.

    Returns:
        True if URL matches Zillow search pattern.
    """
    try:
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        if domain not in ZILLOW_DOMAINS:
            return False
        path = parsed.path.lower()
        return ("/homes/" in path and "filter" in url.lower()) or path.endswith("_rb/")
    except Exception:
        return False


def is_zillow_domain(url: str) -> bool:
    """Check if URL belongs to Zillow domain.

    Args:
        url: URL to check.

    Returns:
        True if URL is on a Zillow domain.
    """
    try:
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        return domain in ZILLOW_DOMAINS
    except Exception:
        return False


def infer_zillow_request_type(url: str) -> str:
    """Infer the request type from a Zillow URL.

    Args:
        url: Zillow URL.

    Returns:
        'property_detail', 'search', or 'unknown'.
    """
    if is_zillow_property_url(url):
        return "property_detail"
    if is_zillow_search_url(url):
        return "search"
    return "unknown"


class ZillowAdapter(SourceAdapter):
    """Zillow source adapter with dry-run and manual fixture support."""

    def __init__(self, config: Optional[SourceAdapterConfig] = None) -> None:
        """Initialize the Zillow adapter."""
        super().__init__(config or _default_zillow_config())

    def validate_request(self, request: RetrievalRequest) -> RetrievalResult:
        """Validate a Zillow retrieval request.

        Checks URL is provided, domain is valid, and request type is
        recognized.

        Args:
            request: Retrieval request to validate.

        Returns:
            RetrievalResult with validation status.
        """
        if not request.url:
            return RetrievalResult(
                source_name="zillow",
                url=request.url,
                request_type=request.request_type,
                retrieval_mode=request.retrieval_mode,
                success=False,
                blocked=True,
                block_reason="No URL provided.",
                dry_run=True,
                network_call_performed=False,
            )

        if not is_zillow_domain(request.url):
            return RetrievalResult(
                source_name="zillow",
                url=request.url,
                request_type=request.request_type,
                retrieval_mode=request.retrieval_mode,
                success=False,
                blocked=True,
                block_reason=(
                    f"URL domain is not a recognized Zillow domain. "
                    f"Expected: {', '.join(ZILLOW_DOMAINS)}"
                ),
                dry_run=True,
                network_call_performed=False,
            )

        req_type = request.request_type or infer_zillow_request_type(request.url)

        return RetrievalResult(
            source_name="zillow",
            url=request.url,
            request_type=req_type,
            retrieval_mode=request.retrieval_mode,
            success=True,
            blocked=False,
            dry_run=True,
            network_call_performed=False,
        )

    def dry_run(self, request: RetrievalRequest) -> RetrievalResult:
        """Dry-run preview for Zillow.

        Validates the URL, infers request type, creates a fixture capture
        queue request, writes an audit record, and returns a detailed preview.

        Args:
            request: Retrieval request for dry-run.

        Returns:
            RetrievalResult with dry-run preview.
        """
        validation = self.validate_request(request)
        if validation.blocked:
            return validation

        req_type = request.request_type or infer_zillow_request_type(request.url)
        parsed = urlparse(request.url)
        domain = parsed.hostname or ""

        # Build preview
        lines = [
            "DRY-RUN: Zillow Property Detail Preview",
            f"URL: {request.url}",
            f"Domain: {domain}",
            f"Request Type: {req_type}",
        ]

        if req_type == "property_detail":
            lines.append("Action: Would parse saved Zillow property detail HTML fixture")
            lines.append("Parser: zillow_parser.parse_zillow_detail_html")
            lines.append("Output: Property facts, cross-site observation")
        elif req_type == "search":
            lines.append("Action: Search fixture parsing is not yet supported for Zillow.")
            lines.append("Note: Save property detail pages manually for cross-site enrichment.")
        else:
            lines.append("Action: Could not determine request type from URL pattern.")
            lines.append("Note: Save the page manually and provide as a detail fixture.")

        lines.append("")
        lines.append("Live retrieval is NOT implemented for Zillow.")
        lines.append("Save the page manually as an HTML fixture.")

        # Create capture queue request
        capture_info = self._create_capture_request(request.url, req_type)
        if capture_info:
            lines.append(f"Fixture capture request: {capture_info}")
        else:
            lines.append("Fixture capture request: created or already pending")

        # Write audit record
        self._write_audit(request.url, domain, req_type)

        return RetrievalResult(
            source_name="zillow",
            url=request.url,
            request_type=req_type,
            retrieval_mode=RetrievalMode.DRY_RUN,
            success=True,
            blocked=False,
            dry_run=True,
            dry_run_preview="\n".join(lines),
            network_call_performed=False,
        )

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Retrieve from Zillow. Not implemented.

        Args:
            request: Retrieval request.

        Returns:
            RetrievalResult with blocked status.
        """
        req_type = request.request_type or infer_zillow_request_type(request.url)
        parsed = urlparse(request.url) if request.url else None
        domain = (parsed.hostname or "") if parsed else ""

        # Write audit record
        self._write_audit(
            request.url, domain, req_type,
            allowed=False, blocked=True,
            reason="Zillow live retrieval is not implemented.",
        )

        # Create capture request as fallback
        self._create_capture_request(request.url, req_type)

        return RetrievalResult(
            source_name="zillow",
            url=request.url,
            request_type=req_type,
            retrieval_mode=request.retrieval_mode,
            success=False,
            blocked=True,
            block_reason="Zillow live retrieval is not implemented. Save page manually as HTML fixture.",
            dry_run=False,
            network_call_performed=False,
        )

    def get_supported_modes(self) -> List[RetrievalMode]:
        """Return supported modes."""
        return [RetrievalMode.DISABLED, RetrievalMode.DRY_RUN, RetrievalMode.MANUAL_FIXTURE]

    def _create_capture_request(
        self, url: str, request_type: str,
    ) -> str:
        """Create a fixture capture queue request.

        Args:
            url: Source URL.
            request_type: Request type.

        Returns:
            Status string.
        """
        try:
            from marketsentry.fixture_capture_queue import add_capture_request
            from marketsentry.source_adapters.policy import FixtureCaptureRequest

            req = FixtureCaptureRequest(
                source_site="zillow",
                source_url=url,
                request_type=request_type,
                reason="Live retrieval not implemented. Manual fixture capture recommended.",
            )
            result = add_capture_request(req)
            if result.duplicate:
                return "already pending"
            return f"added (id={result.capture_request_id})"
        except Exception as e:
            logger.debug(f"Could not create capture request: {e}")
            return ""

    def _write_audit(
        self,
        url: str,
        domain: str,
        request_type: str,
        allowed: bool = True,
        blocked: bool = False,
        reason: str = "Dry-run preview (no live retrieval for Zillow)",
    ) -> None:
        """Write an audit record for this retrieval attempt.

        Args:
            url: Source URL.
            domain: Domain name.
            request_type: Request type.
            allowed: Whether the action was allowed.
            blocked: Whether the action was blocked.
            reason: Reason string.
        """
        try:
            from marketsentry.source_adapters.compliance import write_audit_record

            write_audit_record(
                source_site="zillow",
                retrieval_mode="dry_run",
                url=url,
                domain=domain,
                allowed=allowed,
                blocked=blocked,
                reason=reason,
                dry_run=True,
                network_call_performed=False,
            )
        except Exception as e:
            logger.debug(f"Could not write audit record: {e}")
