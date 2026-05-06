"""Base abstractions for source adapters.

Defines the core interfaces and models for compliance-aware data retrieval.
Live retrieval is disabled by default. All adapters must support dry-run
preview mode that performs no network calls.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RetrievalMode(str, Enum):
    """Supported retrieval modes for source adapters.

    - disabled: All retrieval blocked.
    - dry_run: Preview what would be retrieved; no network calls.
    - manual_fixture: Read from locally saved HTML fixtures.
    - authorized_api: Use an authorized API or data feed (future).
    - live_http: Direct HTTP retrieval (requires explicit opt-in).
    """

    DISABLED = "disabled"
    DRY_RUN = "dry_run"
    MANUAL_FIXTURE = "manual_fixture"
    AUTHORIZED_API = "authorized_api"
    LIVE_HTTP = "live_http"


class SourceAdapterConfig(BaseModel):
    """Configuration for a single source adapter."""

    source_name: str = ""
    display_name: str = ""
    allowed_domains: List[str] = Field(default_factory=list)
    default_mode: RetrievalMode = RetrievalMode.DISABLED
    current_mode: RetrievalMode = RetrievalMode.DISABLED
    fixture_directory: str = ""
    supports_search: bool = False
    supports_property_detail: bool = False
    supports_listing_history: bool = False
    notes: str = ""


class RetrievalRequest(BaseModel):
    """A request to retrieve data from a source."""

    source_name: str = ""
    url: str = ""
    request_type: str = ""  # e.g. "search", "property_detail"
    retrieval_mode: RetrievalMode = RetrievalMode.DRY_RUN
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    """Result from a retrieval attempt."""

    source_name: str = ""
    url: str = ""
    request_type: str = ""
    retrieval_mode: RetrievalMode = RetrievalMode.DRY_RUN
    success: bool = False
    blocked: bool = False
    block_reason: str = ""
    dry_run: bool = True
    dry_run_preview: str = ""
    data: Optional[Any] = None
    content: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    network_call_performed: bool = False
    compliance_warnings: List[str] = Field(default_factory=list)
    error_message: str = ""


class SourceAdapter(ABC):
    """Abstract base class for source adapters.

    All source adapters must implement these methods. Live retrieval
    must be blocked unless explicitly enabled and compliance checks pass.
    Dry-run methods must never perform network calls.
    """

    def __init__(self, config: SourceAdapterConfig) -> None:
        """Initialize the adapter with configuration.

        Args:
            config: Adapter-specific configuration.
        """
        self.config = config

    @property
    def source_name(self) -> str:
        """Return the source name for this adapter."""
        return self.config.source_name

    @property
    def display_name(self) -> str:
        """Return the display name for this adapter."""
        return self.config.display_name

    @property
    def current_mode(self) -> RetrievalMode:
        """Return the current retrieval mode."""
        return self.config.current_mode

    @abstractmethod
    def validate_request(self, request: RetrievalRequest) -> RetrievalResult:
        """Validate a retrieval request without performing it.

        Args:
            request: The retrieval request to validate.

        Returns:
            RetrievalResult indicating whether the request is valid.
        """
        ...

    @abstractmethod
    def dry_run(self, request: RetrievalRequest) -> RetrievalResult:
        """Preview what a retrieval would do without network calls.

        Args:
            request: The retrieval request to preview.

        Returns:
            RetrievalResult with dry_run=True and preview details.
        """
        ...

    @abstractmethod
    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Perform a retrieval. Must check compliance before proceeding.

        Live retrieval is blocked unless explicitly enabled. Even when
        enabled, this method may return a not-implemented result until
        a later milestone.

        Args:
            request: The retrieval request to perform.

        Returns:
            RetrievalResult with the outcome.
        """
        ...

    def get_supported_modes(self) -> List[RetrievalMode]:
        """Return the retrieval modes this adapter supports.

        Returns:
            List of supported RetrievalMode values.
        """
        return [RetrievalMode.DISABLED, RetrievalMode.DRY_RUN, RetrievalMode.MANUAL_FIXTURE]
