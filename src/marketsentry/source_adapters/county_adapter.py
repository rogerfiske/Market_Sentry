"""County recorder/assessor source adapter stub.

Skeleton adapter for future county data retrieval. Currently supports
only disabled, dry-run, and manual fixture modes. No live county
recorder or assessor access is implemented. No network calls.
"""

from typing import List, Optional

from marketsentry.source_adapters.base import (
    RetrievalMode,
    RetrievalRequest,
    RetrievalResult,
    SourceAdapter,
    SourceAdapterConfig,
)


def _default_county_config() -> SourceAdapterConfig:
    """Create default county adapter configuration."""
    return SourceAdapterConfig(
        source_name="county",
        display_name="County Recorder/Assessor",
        allowed_domains=[],
        default_mode=RetrievalMode.MANUAL_FIXTURE,
        current_mode=RetrievalMode.MANUAL_FIXTURE,
        fixture_directory="data/raw/county",
        supports_search=False,
        supports_property_detail=True,
        supports_listing_history=False,
        notes="County records via manual CSV import or saved HTML fixtures only.",
    )


class CountyAdapter(SourceAdapter):
    """County recorder/assessor source adapter stub."""

    def __init__(self, config: Optional[SourceAdapterConfig] = None) -> None:
        """Initialize the county adapter."""
        super().__init__(config or _default_county_config())

    def validate_request(self, request: RetrievalRequest) -> RetrievalResult:
        """Validate a county retrieval request."""
        return RetrievalResult(
            source_name="county",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=request.retrieval_mode,
            success=True,
            blocked=False,
            dry_run=True,
            network_call_performed=False,
        )

    def dry_run(self, request: RetrievalRequest) -> RetrievalResult:
        """Dry-run preview for county. Stub implementation."""
        return RetrievalResult(
            source_name="county",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=RetrievalMode.DRY_RUN,
            success=True,
            blocked=False,
            dry_run=True,
            dry_run_preview="DRY-RUN: County adapter stub. Not yet implemented.",
            network_call_performed=False,
        )

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Retrieve from county sources. Not implemented."""
        return RetrievalResult(
            source_name="county",
            url=request.url,
            request_type=request.request_type,
            retrieval_mode=request.retrieval_mode,
            success=False,
            blocked=True,
            block_reason="County live retrieval is not implemented.",
            dry_run=False,
            network_call_performed=False,
        )

    def get_supported_modes(self) -> List[RetrievalMode]:
        """Return supported modes."""
        return [RetrievalMode.DISABLED, RetrievalMode.DRY_RUN, RetrievalMode.MANUAL_FIXTURE]
