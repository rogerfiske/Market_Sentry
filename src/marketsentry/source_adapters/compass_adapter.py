"""Compass source adapter stub.

Skeleton adapter for future Compass data retrieval. Currently supports
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


def _default_compass_config() -> SourceAdapterConfig:
    """Create default Compass adapter configuration."""
    return SourceAdapterConfig(
        source_name="compass",
        display_name="Compass",
        allowed_domains=["www.compass.com", "compass.com"],
        default_mode=RetrievalMode.MANUAL_FIXTURE,
        current_mode=RetrievalMode.MANUAL_FIXTURE,
        fixture_directory="data/raw/cross_site/compass",
        supports_search=False,
        supports_property_detail=True,
        supports_listing_history=False,
        notes="Cross-site validation source. Fixture parsing only.",
    )


class CompassAdapter(SourceAdapter):
    """Compass source adapter stub."""

    def __init__(self, config: Optional[SourceAdapterConfig] = None) -> None:
        """Initialize the Compass adapter."""
        super().__init__(config or _default_compass_config())

    def validate_request(self, request: RetrievalRequest) -> RetrievalResult:
        """Validate a Compass retrieval request."""
        return RetrievalResult(
            source_name="compass",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=request.retrieval_mode,
            success=True,
            blocked=False,
            dry_run=True,
            network_call_performed=False,
        )

    def dry_run(self, request: RetrievalRequest) -> RetrievalResult:
        """Dry-run preview for Compass. Stub implementation."""
        return RetrievalResult(
            source_name="compass",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=RetrievalMode.DRY_RUN,
            success=True,
            blocked=False,
            dry_run=True,
            dry_run_preview="DRY-RUN: Compass adapter stub. Not yet implemented.",
            network_call_performed=False,
        )

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Retrieve from Compass. Not implemented."""
        return RetrievalResult(
            source_name="compass",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=request.retrieval_mode,
            success=False,
            blocked=True,
            block_reason="Compass live retrieval is not implemented.",
            dry_run=False,
            network_call_performed=False,
        )

    def get_supported_modes(self) -> List[RetrievalMode]:
        """Return supported modes."""
        return [RetrievalMode.DISABLED, RetrievalMode.DRY_RUN, RetrievalMode.MANUAL_FIXTURE]
