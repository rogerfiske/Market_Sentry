"""Realtor.com source adapter with dry-run parity and manual fixture support.

Provides URL validation, request type inference, dry-run preview with
fixture capture queue integration, and audit logging. Live HTTP retrieval
is not implemented for Realtor.com. No network calls are performed.
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

REALTOR_DOMAINS = ["www.realtor.com", "realtor.com"]


def _default_realtor_config() -> SourceAdapterConfig:
    """Create default Realtor.com adapter configuration."""
    return SourceAdapterConfig(
        source_name="realtor",
        display_name="Realtor.com",
        allowed_domains=REALTOR_DOMAINS,
        default_mode=RetrievalMode.MANUAL_FIXTURE,
        current_mode=RetrievalMode.MANUAL_FIXTURE,
        fixture_directory="data/raw/realtor/details",
        supports_search=False,
        supports_property_detail=True,
        supports_listing_history=False,
        notes="Cross-site validation source. Manual fixture parsing only.",
    )


def is_realtor_property_url(url: str) -> bool:
    """Check if a URL is a Realtor.com property detail URL.

    Args:
        url: URL to check.

    Returns:
        True if URL matches Realtor.com property pattern.
    """
    try:
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        if domain not in REALTOR_DOMAINS:
            return False
        path = parsed.path.lower()
        return "/realestateandhomes-detail/" in path or "/property-detail/" in path
    except Exception:
        return False


def is_realtor_search_url(url: str) -> bool:
    """Check if a URL is a Realtor.com search URL.

    Args:
        url: URL to check.

    Returns:
        True if URL matches Realtor.com search pattern.
    """
    try:
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        if domain not in REALTOR_DOMAINS:
            return False
        path = parsed.path.lower()
        return "/realestateandhomes-search/" in path
    except Exception:
        return False


def is_realtor_domain(url: str) -> bool:
    """Check if URL belongs to Realtor.com domain.

    Args:
        url: URL to check.

    Returns:
        True if URL is on a Realtor.com domain.
    """
    try:
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        return domain in REALTOR_DOMAINS
    except Exception:
        return False


def infer_realtor_request_type(url: str) -> str:
    """Infer the request type from a Realtor.com URL.

    Args:
        url: Realtor.com URL.

    Returns:
        'property_detail', 'search', or 'unknown'.
    """
    if is_realtor_property_url(url):
        return "property_detail"
    if is_realtor_search_url(url):
        return "search"
    return "unknown"


class RealtorAdapter(SourceAdapter):
    """Realtor.com source adapter with dry-run and manual fixture support."""

    def __init__(self, config: Optional[SourceAdapterConfig] = None) -> None:
        """Initialize the Realtor.com adapter."""
        super().__init__(config or _default_realtor_config())

    def validate_request(self, request: RetrievalRequest) -> RetrievalResult:
        """Validate a Realtor.com retrieval request.

        Args:
            request: Retrieval request to validate.

        Returns:
            RetrievalResult with validation status.
        """
        if not request.url:
            return RetrievalResult(
                source_name="realtor", url=request.url,
                request_type=request.request_type,
                retrieval_mode=request.retrieval_mode,
                success=False, blocked=True,
                block_reason="No URL provided.",
                dry_run=True, network_call_performed=False,
            )

        if not is_realtor_domain(request.url):
            return RetrievalResult(
                source_name="realtor", url=request.url,
                request_type=request.request_type,
                retrieval_mode=request.retrieval_mode,
                success=False, blocked=True,
                block_reason=(
                    f"URL domain is not a recognized Realtor.com domain. "
                    f"Expected: {', '.join(REALTOR_DOMAINS)}"
                ),
                dry_run=True, network_call_performed=False,
            )

        req_type = request.request_type or infer_realtor_request_type(request.url)

        return RetrievalResult(
            source_name="realtor", url=request.url,
            request_type=req_type,
            retrieval_mode=request.retrieval_mode,
            success=True, blocked=False,
            dry_run=True, network_call_performed=False,
        )

    def dry_run(self, request: RetrievalRequest) -> RetrievalResult:
        """Dry-run preview for Realtor.com.

        Args:
            request: Retrieval request for dry-run.

        Returns:
            RetrievalResult with dry-run preview.
        """
        validation = self.validate_request(request)
        if validation.blocked:
            return validation

        req_type = request.request_type or infer_realtor_request_type(request.url)
        parsed = urlparse(request.url)
        domain = parsed.hostname or ""

        lines = [
            "DRY-RUN: Realtor.com Property Detail Preview",
            f"URL: {request.url}",
            f"Domain: {domain}",
            f"Request Type: {req_type}",
        ]

        if req_type == "property_detail":
            lines.append("Action: Would parse saved Realtor.com property detail HTML fixture")
            lines.append("Parser: realtor_parser.parse_realtor_detail_html")
            lines.append("Output: Property facts, cross-site observation")
        elif req_type == "search":
            lines.append("Action: Search fixture parsing is not yet supported for Realtor.com.")
            lines.append("Note: Save property detail pages manually for cross-site enrichment.")
        else:
            lines.append("Action: Could not determine request type from URL pattern.")
            lines.append("Note: Save the page manually and provide as a detail fixture.")

        lines.append("")
        lines.append("Live retrieval is NOT implemented for Realtor.com.")
        lines.append("Save the page manually as an HTML fixture.")

        capture_info = self._create_capture_request(request.url, req_type)
        if capture_info:
            lines.append(f"Fixture capture request: {capture_info}")
        else:
            lines.append("Fixture capture request: created or already pending")

        self._write_audit(request.url, domain, req_type)

        return RetrievalResult(
            source_name="realtor", url=request.url,
            request_type=req_type,
            retrieval_mode=RetrievalMode.DRY_RUN,
            success=True, blocked=False, dry_run=True,
            dry_run_preview="\n".join(lines),
            network_call_performed=False,
        )

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Retrieve from Realtor.com. Not implemented.

        Args:
            request: Retrieval request.

        Returns:
            RetrievalResult with blocked status.
        """
        req_type = request.request_type or infer_realtor_request_type(request.url)
        parsed = urlparse(request.url) if request.url else None
        domain = (parsed.hostname or "") if parsed else ""

        self._write_audit(
            request.url, domain, req_type,
            allowed=False, blocked=True,
            reason="Realtor.com live retrieval is not implemented.",
        )
        self._create_capture_request(request.url, req_type)

        return RetrievalResult(
            source_name="realtor", url=request.url,
            request_type=req_type,
            retrieval_mode=request.retrieval_mode,
            success=False, blocked=True,
            block_reason="Realtor.com live retrieval is not implemented. Save page manually as HTML fixture.",
            dry_run=False, network_call_performed=False,
        )

    def get_supported_modes(self) -> List[RetrievalMode]:
        """Return supported modes."""
        return [RetrievalMode.DISABLED, RetrievalMode.DRY_RUN, RetrievalMode.MANUAL_FIXTURE]

    def _create_capture_request(self, url: str, request_type: str) -> str:
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
                source_site="realtor",
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
        self, url: str, domain: str, request_type: str,
        allowed: bool = True, blocked: bool = False,
        reason: str = "Dry-run preview (no live retrieval for Realtor.com)",
    ) -> None:
        """Write an audit record.

        Args:
            url: Source URL.
            domain: Domain name.
            request_type: Request type.
            allowed: Whether allowed.
            blocked: Whether blocked.
            reason: Reason string.
        """
        try:
            from marketsentry.source_adapters.compliance import write_audit_record

            write_audit_record(
                source_site="realtor",
                retrieval_mode="dry_run",
                url=url, domain=domain,
                allowed=allowed, blocked=blocked,
                reason=reason,
                dry_run=True, network_call_performed=False,
            )
        except Exception as e:
            logger.debug(f"Could not write audit record: {e}")
