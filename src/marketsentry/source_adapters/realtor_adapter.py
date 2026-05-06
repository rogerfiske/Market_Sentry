"""Realtor.com source adapter stub.

Skeleton adapter for future Realtor.com data retrieval. Currently supports
only disabled, dry-run, and manual fixture modes. No network calls.
"""

from typing import List, Optional

from marketsentry.source_adapters.base import (
    RetrievalMode,
    RetrievalRequest,
    RetrievalResult,
    SourceAdapter,
    SourceAdapterConfig,
)


def _default_realtor_config() -> SourceAdapterConfig:
    """Create default Realtor.com adapter configuration."""
    return SourceAdapterConfig(
        source_name="realtor",
        display_name="Realtor.com",
        allowed_domains=["www.realtor.com", "realtor.com"],
        default_mode=RetrievalMode.MANUAL_FIXTURE,
        current_mode=RetrievalMode.MANUAL_FIXTURE,
        fixture_directory="data/raw/cross_site/realtor",
        supports_search=False,
        supports_property_detail=True,
        supports_listing_history=False,
        notes="Cross-site validation source. Fixture parsing only.",
    )


class RealtorAdapter(SourceAdapter):
    """Realtor.com source adapter stub."""

    def __init__(self, config: Optional[SourceAdapterConfig] = None) -> None:
        """Initialize the Realtor.com adapter."""
        super().__init__(config or _default_realtor_config())

    def validate_request(self, request: RetrievalRequest) -> RetrievalResult:
        """Validate a Realtor.com retrieval request."""
        return RetrievalResult(
            source_name="realtor",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=request.retrieval_mode,
            success=True,
            blocked=False,
            dry_run=True,
            network_call_performed=False,
        )

    def dry_run(self, request: RetrievalRequest) -> RetrievalResult:
        """Dry-run preview for Realtor.com. Stub implementation."""
        return RetrievalResult(
            source_name="realtor",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=RetrievalMode.DRY_RUN,
            success=True,
            blocked=False,
            dry_run=True,
            dry_run_preview="DRY-RUN: Realtor.com adapter stub. Not yet implemented.",
            network_call_performed=False,
        )

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Retrieve from Realtor.com. Not implemented."""
        return RetrievalResult(
            source_name="realtor",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=request.retrieval_mode,
            success=False,
            blocked=True,
            block_reason="Realtor.com live retrieval is not implemented.",
            dry_run=False,
            network_call_performed=False,
        )

    def get_supported_modes(self) -> List[RetrievalMode]:
        """Return supported modes."""
        return [RetrievalMode.DISABLED, RetrievalMode.DRY_RUN, RetrievalMode.MANUAL_FIXTURE]
