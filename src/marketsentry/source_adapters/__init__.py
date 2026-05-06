"""Source adapter package for Market_Sentry live retrieval strategy.

Provides compliance-aware source adapters for data retrieval from
real estate sites. Live retrieval is disabled by default. All adapters
support dry-run preview mode that performs no network calls.

No active live scraping, browser automation, Playwright, Selenium,
or bypass mechanisms are implemented.
"""

from marketsentry.source_adapters.base import (
    RetrievalMode,
    RetrievalRequest,
    RetrievalResult,
    SourceAdapter,
    SourceAdapterConfig,
)
from marketsentry.source_adapters.compliance import (
    ComplianceCheckResult,
    RateLimitConfig,
    RetrievalComplianceConfig,
    RobotsCheckResult,
    check_retrieval_compliance,
    get_compliance_status,
)
from marketsentry.source_adapters.policy import (
    DryRunApprovalRecord,
    FixtureCaptureQueueResult,
    FixtureCaptureRequest,
    RetrievalPolicy,
    RetrievalPolicyDecision,
    RetrievalPolicyReason,
)
from marketsentry.source_adapters.registry import SourceAdapterRegistry, get_registry

__all__ = [
    "ComplianceCheckResult",
    "DryRunApprovalRecord",
    "FixtureCaptureQueueResult",
    "FixtureCaptureRequest",
    "RateLimitConfig",
    "RetrievalComplianceConfig",
    "RetrievalMode",
    "RetrievalPolicy",
    "RetrievalPolicyDecision",
    "RetrievalPolicyReason",
    "RetrievalRequest",
    "RetrievalResult",
    "RobotsCheckResult",
    "SourceAdapter",
    "SourceAdapterConfig",
    "SourceAdapterRegistry",
    "check_retrieval_compliance",
    "get_compliance_status",
    "get_registry",
]
