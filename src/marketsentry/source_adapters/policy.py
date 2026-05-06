"""Retrieval policy engine for Market_Sentry.

Evaluates whether a retrieval request is allowed, blocked, or requires
manual action. Combines compliance checks, robots policy, rate limiting,
and dry-run approval requirements into a single policy decision.

No network calls are performed by this module.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from marketsentry.source_adapters.compliance import (
    RetrievalComplianceConfig,
    check_retrieval_compliance,
)


# ---------------------------------------------------------------------------
# Policy decision models
# ---------------------------------------------------------------------------


class RetrievalPolicyDecision(str, Enum):
    """Possible outcomes from a retrieval policy evaluation.

    - allowed: Request may proceed.
    - blocked: Request is blocked by policy.
    - requires_manual_fixture: User should save HTML fixture manually.
    - requires_dry_run: A dry-run must be performed first.
    - requires_authorized_access: Authorized API access is needed.
    - not_implemented: Live retrieval is not implemented yet.
    """

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REQUIRES_MANUAL_FIXTURE = "requires_manual_fixture"
    REQUIRES_DRY_RUN = "requires_dry_run"
    REQUIRES_AUTHORIZED_ACCESS = "requires_authorized_access"
    NOT_IMPLEMENTED = "not_implemented"


class RetrievalPolicyReason(BaseModel):
    """A single reason contributing to a policy decision."""

    code: str = ""
    message: str = ""
    severity: str = "info"  # info, warning, error


class RetrievalPolicy(BaseModel):
    """Result of a retrieval policy evaluation."""

    decision: RetrievalPolicyDecision = RetrievalPolicyDecision.BLOCKED
    reasons: List[RetrievalPolicyReason] = Field(default_factory=list)
    source_name: str = ""
    url: str = ""
    request_type: str = ""
    retrieval_mode: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    compliance_passed: bool = False
    robots_passed: bool = False
    robots_unknown: bool = True
    rate_limit_passed: bool = False
    dry_run_approved: bool = False
    fixture_capture_recommended: bool = False
    suggested_fixture_path: str = ""
    network_call_performed: bool = False

    @property
    def is_allowed(self) -> bool:
        """Whether the request is allowed to proceed."""
        return self.decision == RetrievalPolicyDecision.ALLOWED

    @property
    def is_blocked(self) -> bool:
        """Whether the request is blocked."""
        return self.decision in (
            RetrievalPolicyDecision.BLOCKED,
            RetrievalPolicyDecision.NOT_IMPLEMENTED,
        )

    @property
    def reason_messages(self) -> List[str]:
        """Return flat list of reason messages."""
        return [r.message for r in self.reasons]


class DryRunApprovalRecord(BaseModel):
    """Record of a completed dry-run for a specific URL."""

    source_site: str = ""
    url: str = ""
    normalized_url: str = ""
    request_type: str = ""
    dry_run_timestamp: str = ""
    compliance_status: str = ""
    allowed: bool = False
    blocked: bool = False
    reasons: List[str] = Field(default_factory=list)
    network_call_performed: bool = False


class FixtureCaptureRequest(BaseModel):
    """A request to manually capture a fixture file."""

    source_site: str = ""
    source_url: str = ""
    normalized_url: str = ""
    request_type: str = ""
    suggested_fixture_path: str = ""
    reason: str = ""
    candidate_id: Optional[int] = None
    property_id: Optional[int] = None
    priority: int = 5
    notes: str = ""


class FixtureCaptureQueueResult(BaseModel):
    """Result of adding an item to the fixture capture queue."""

    added: bool = False
    duplicate: bool = False
    capture_request_id: Optional[int] = None
    message: str = ""


# ---------------------------------------------------------------------------
# Fixture path suggestions
# ---------------------------------------------------------------------------

FIXTURE_PATH_MAP = {
    ("redfin", "search"): "data/raw/redfin/search",
    ("redfin", "property_detail"): "data/raw/redfin/details",
    ("zillow", "property_detail"): "data/raw/cross_site/zillow",
    ("realtor", "property_detail"): "data/raw/cross_site/realtor",
    ("homes", "property_detail"): "data/raw/cross_site/homes",
    ("compass", "property_detail"): "data/raw/cross_site/compass",
    ("county", "assessor"): "data/raw/county/assessor",
    ("county", "recorder"): "data/raw/county/recorder",
}


def suggest_fixture_path(source_name: str, request_type: str, url: str = "") -> str:
    """Suggest a fixture save path for a given source and request type.

    Args:
        source_name: Source adapter name (e.g., "redfin").
        request_type: Request type (e.g., "search", "property_detail").
        url: Source URL for filename hints.

    Returns:
        Suggested fixture directory path.
    """
    key = (source_name, request_type)
    base_path = FIXTURE_PATH_MAP.get(key, f"data/raw/{source_name}")
    return base_path


# ---------------------------------------------------------------------------
# Policy evaluation
# ---------------------------------------------------------------------------


def evaluate_retrieval_policy(
    source_name: str,
    url: str,
    request_type: str,
    retrieval_mode: str,
    compliance_config: Optional[RetrievalComplianceConfig] = None,
    robots_allowed: Optional[bool] = None,
    robots_unknown: bool = True,
    rate_limit_ok: bool = True,
    has_recent_dry_run: bool = False,
) -> RetrievalPolicy:
    """Evaluate the full retrieval policy for a request.

    Combines compliance checks, robots policy, rate limiting, and dry-run
    approval into a single policy decision. No network calls are performed.

    Args:
        source_name: Source adapter name.
        url: URL being requested.
        request_type: Type of request (search, property_detail, etc.).
        retrieval_mode: Requested retrieval mode.
        compliance_config: Compliance config. Loaded from env if None.
        robots_allowed: Whether robots policy allows access. None = unknown.
        robots_unknown: Whether robots policy is unknown/not loaded.
        rate_limit_ok: Whether rate limit allows the request.
        has_recent_dry_run: Whether a recent dry-run exists for this URL.

    Returns:
        RetrievalPolicy with decision, reasons, and recommendations.
    """
    from urllib.parse import urlparse

    cc = compliance_config or RetrievalComplianceConfig.from_env()

    domain = ""
    try:
        parsed = urlparse(url)
        domain = parsed.hostname or ""
    except Exception:
        pass

    policy = RetrievalPolicy(
        source_name=source_name,
        url=url,
        request_type=request_type,
        retrieval_mode=retrieval_mode,
        network_call_performed=False,
    )

    # Mode: disabled
    if retrieval_mode == "disabled":
        policy.decision = RetrievalPolicyDecision.BLOCKED
        policy.reasons.append(RetrievalPolicyReason(
            code="mode_disabled",
            message="Retrieval mode is disabled.",
            severity="info",
        ))
        return policy

    # Mode: dry_run - always allowed, no network call
    if retrieval_mode == "dry_run":
        policy.decision = RetrievalPolicyDecision.ALLOWED
        policy.compliance_passed = True
        policy.reasons.append(RetrievalPolicyReason(
            code="dry_run_allowed",
            message="Dry-run mode is always allowed. No network call performed.",
            severity="info",
        ))
        return policy

    # Mode: manual_fixture - always allowed, no network call
    if retrieval_mode == "manual_fixture":
        policy.decision = RetrievalPolicyDecision.ALLOWED
        policy.compliance_passed = True
        policy.reasons.append(RetrievalPolicyReason(
            code="manual_fixture_allowed",
            message="Manual fixture mode is always allowed. No network call.",
            severity="info",
        ))
        return policy

    # Mode: authorized_api - not implemented
    if retrieval_mode == "authorized_api":
        policy.decision = RetrievalPolicyDecision.REQUIRES_AUTHORIZED_ACCESS
        policy.fixture_capture_recommended = True
        policy.suggested_fixture_path = suggest_fixture_path(source_name, request_type, url)
        policy.reasons.append(RetrievalPolicyReason(
            code="authorized_api_not_available",
            message="Authorized API access is not available. Use manual fixture capture.",
            severity="warning",
        ))
        return policy

    # Mode: live_http - full policy evaluation
    reasons: List[RetrievalPolicyReason] = []

    # 1. Compliance check
    compliance = check_retrieval_compliance(
        source_name=source_name,
        domain=domain,
        retrieval_mode=retrieval_mode,
        compliance_config=cc,
    )

    if compliance.allowed:
        policy.compliance_passed = True
    else:
        for r in compliance.reasons:
            reasons.append(RetrievalPolicyReason(
                code="compliance_block",
                message=r,
                severity="error",
            ))

    # 2. Robots check
    if robots_unknown:
        policy.robots_unknown = True
        policy.robots_passed = False
        reasons.append(RetrievalPolicyReason(
            code="robots_unknown",
            message=(
                f"Robots policy for '{source_name}' is unknown. "
                "Save a local robots.txt to data/policies/robots/ before live retrieval."
            ),
            severity="error",
        ))
    elif robots_allowed is False:
        policy.robots_passed = False
        policy.robots_unknown = False
        reasons.append(RetrievalPolicyReason(
            code="robots_disallowed",
            message=f"Robots policy for '{source_name}' disallows access to this path.",
            severity="error",
        ))
    elif robots_allowed is True:
        policy.robots_passed = True
        policy.robots_unknown = False

    # 3. Rate limit check
    if rate_limit_ok:
        policy.rate_limit_passed = True
    else:
        reasons.append(RetrievalPolicyReason(
            code="rate_limit_exceeded",
            message="Rate limit exceeded. Wait before making more requests.",
            severity="error",
        ))

    # 4. Dry-run approval check
    if cc.require_dry_run_before_live and not has_recent_dry_run:
        policy.dry_run_approved = False
        reasons.append(RetrievalPolicyReason(
            code="dry_run_required",
            message="A dry-run preview is required before live retrieval. Run a dry-run first.",
            severity="error",
        ))
    elif has_recent_dry_run:
        policy.dry_run_approved = True

    # Determine final decision
    error_reasons = [r for r in reasons if r.severity == "error"]

    if error_reasons:
        # Check if it's specifically a not-implemented scenario
        if policy.compliance_passed and policy.robots_passed and policy.rate_limit_passed:
            policy.decision = RetrievalPolicyDecision.NOT_IMPLEMENTED
        elif not policy.compliance_passed:
            policy.decision = RetrievalPolicyDecision.BLOCKED
        else:
            policy.decision = RetrievalPolicyDecision.BLOCKED

        # Recommend fixture capture as fallback
        policy.fixture_capture_recommended = True
        policy.suggested_fixture_path = suggest_fixture_path(source_name, request_type, url)
    else:
        # All checks passed - but live_http is still not implemented
        policy.decision = RetrievalPolicyDecision.NOT_IMPLEMENTED
        reasons.append(RetrievalPolicyReason(
            code="live_not_implemented",
            message="Live HTTP retrieval is not implemented in this milestone.",
            severity="info",
        ))
        policy.fixture_capture_recommended = True
        policy.suggested_fixture_path = suggest_fixture_path(source_name, request_type, url)

    policy.reasons = reasons
    return policy
