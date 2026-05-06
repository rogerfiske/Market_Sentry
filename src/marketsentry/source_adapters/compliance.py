"""Compliance guardrails for live retrieval.

Provides compliance checking, rate limit configuration, and audit logging
for all source adapter retrieval operations. Live retrieval is disabled
by default and requires explicit opt-in via environment variables.

No network calls are performed by this module.
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from marketsentry.logging_config import logger


# ---------------------------------------------------------------------------
# Compliance models
# ---------------------------------------------------------------------------


class RateLimitConfig(BaseModel):
    """Rate limit configuration for retrieval."""

    max_requests_per_minute: int = 6
    min_delay_seconds: float = 10.0


class RobotsCheckResult(BaseModel):
    """Result of a robots.txt compliance check.

    Note: Actual robots.txt network fetching is not implemented in this
    milestone. This model defines the interface for future use.
    """

    checked: bool = False
    allowed: bool = False
    robots_url: str = ""
    user_agent: str = ""
    notes: str = "robots.txt checking not yet implemented"


class RetrievalComplianceConfig(BaseModel):
    """Global compliance configuration for live retrieval."""

    live_retrieval_enabled: bool = False
    allowed_live_sources: List[str] = Field(default_factory=list)
    live_user_agent: str = ""
    live_contact_email: str = ""
    max_requests_per_minute: int = 6
    require_dry_run_before_live: bool = True
    retrieval_audit_dir: str = "logs/retrieval_audit"

    @classmethod
    def from_env(cls) -> "RetrievalComplianceConfig":
        """Load compliance configuration from environment variables.

        Returns:
            RetrievalComplianceConfig with values from env or defaults.
        """
        raw_enabled = os.getenv("MARKETSENTRY_LIVE_RETRIEVAL_ENABLED", "false")
        live_enabled = raw_enabled.lower() in ("true", "1", "yes")

        raw_sources = os.getenv("MARKETSENTRY_ALLOWED_LIVE_SOURCES", "")
        allowed_sources = [
            s.strip() for s in raw_sources.split(",") if s.strip()
        ]

        return cls(
            live_retrieval_enabled=live_enabled,
            allowed_live_sources=allowed_sources,
            live_user_agent=os.getenv("MARKETSENTRY_LIVE_USER_AGENT", ""),
            live_contact_email=os.getenv("MARKETSENTRY_LIVE_CONTACT_EMAIL", ""),
            max_requests_per_minute=int(
                os.getenv("MARKETSENTRY_MAX_REQUESTS_PER_MINUTE", "6")
            ),
            require_dry_run_before_live=os.getenv(
                "MARKETSENTRY_REQUIRE_DRY_RUN_BEFORE_LIVE", "true"
            ).lower()
            in ("true", "1", "yes"),
            retrieval_audit_dir=os.getenv(
                "MARKETSENTRY_RETRIEVAL_AUDIT_DIR", "logs/retrieval_audit"
            ),
        )


class ComplianceCheckResult(BaseModel):
    """Result of a compliance check for a retrieval request."""

    allowed: bool = False
    blocked: bool = True
    reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    source_name: str = ""
    domain: str = ""
    retrieval_mode: str = ""
    live_retrieval_enabled: bool = False
    source_allowlisted: bool = False
    rate_limit_configured: bool = False
    user_agent_configured: bool = False
    contact_configured: bool = False
    dry_run_required: bool = True


# ---------------------------------------------------------------------------
# Compliance checking
# ---------------------------------------------------------------------------


def check_retrieval_compliance(
    source_name: str,
    domain: str,
    retrieval_mode: str,
    compliance_config: Optional[RetrievalComplianceConfig] = None,
) -> ComplianceCheckResult:
    """Check whether a retrieval request is compliant.

    Evaluates global and source-specific compliance rules. If any
    required condition is not met, the result is blocked=True.

    Args:
        source_name: Name of the source adapter (e.g., "redfin").
        domain: Domain being accessed (e.g., "www.redfin.com").
        retrieval_mode: The requested retrieval mode.
        compliance_config: Compliance config. Loaded from env if None.

    Returns:
        ComplianceCheckResult with allowed/blocked status and reasons.
    """
    cc = compliance_config or RetrievalComplianceConfig.from_env()

    result = ComplianceCheckResult(
        source_name=source_name,
        domain=domain,
        retrieval_mode=retrieval_mode,
        live_retrieval_enabled=cc.live_retrieval_enabled,
        dry_run_required=cc.require_dry_run_before_live,
    )

    # Dry-run and manual_fixture modes are always allowed
    if retrieval_mode in ("dry_run", "manual_fixture", "disabled"):
        result.allowed = True
        result.blocked = False
        result.reasons.append(f"Mode '{retrieval_mode}' is always permitted.")
        return result

    # For live_http or authorized_api, enforce compliance checks
    reasons: List[str] = []

    # 1. Global live retrieval must be enabled
    if not cc.live_retrieval_enabled:
        reasons.append(
            "Live retrieval is globally disabled. "
            "Set MARKETSENTRY_LIVE_RETRIEVAL_ENABLED=true to enable."
        )

    # 2. Source must be allowlisted
    if source_name in cc.allowed_live_sources:
        result.source_allowlisted = True
    else:
        reasons.append(
            f"Source '{source_name}' is not in MARKETSENTRY_ALLOWED_LIVE_SOURCES. "
            f"Allowed: {cc.allowed_live_sources or '(none)'}."
        )

    # 3. Domain must match allowed domains (basic check)
    # For now we check if source is allowlisted; domain validation is
    # handled per-adapter in validate_request.

    # 4. Rate limit must be configured (non-zero)
    if cc.max_requests_per_minute > 0:
        result.rate_limit_configured = True
    else:
        reasons.append(
            "Rate limit is not configured (max_requests_per_minute=0). "
            "Set MARKETSENTRY_MAX_REQUESTS_PER_MINUTE to a positive value."
        )

    # 5. User-Agent must be set for live mode
    if cc.live_user_agent:
        result.user_agent_configured = True
    else:
        reasons.append(
            "User-Agent is not configured. "
            "Set MARKETSENTRY_LIVE_USER_AGENT to identify your client."
        )

    # 6. Contact email should be set (warning, not blocking)
    if cc.live_contact_email:
        result.contact_configured = True
    else:
        result.warnings.append(
            "Contact email is not configured. "
            "Consider setting MARKETSENTRY_LIVE_CONTACT_EMAIL."
        )

    # 7. Dry-run required check (advisory)
    if cc.require_dry_run_before_live:
        result.warnings.append(
            "Dry-run is required before live retrieval. "
            "Run dry-run commands first to preview."
        )

    if reasons:
        result.allowed = False
        result.blocked = True
        result.reasons = reasons
    else:
        result.allowed = True
        result.blocked = False
        result.reasons = ["All compliance checks passed."]

    return result


def get_compliance_status(
    compliance_config: Optional[RetrievalComplianceConfig] = None,
) -> Dict[str, object]:
    """Get a summary of current compliance configuration status.

    Args:
        compliance_config: Compliance config. Loaded from env if None.

    Returns:
        Dict with compliance status fields.
    """
    cc = compliance_config or RetrievalComplianceConfig.from_env()

    warnings: List[str] = []

    if cc.live_retrieval_enabled:
        warnings.append("Live retrieval is ENABLED. Use with caution.")
    if not cc.live_user_agent and cc.live_retrieval_enabled:
        warnings.append("No User-Agent configured for live retrieval.")
    if not cc.live_contact_email and cc.live_retrieval_enabled:
        warnings.append("No contact email configured for live retrieval.")
    if not cc.allowed_live_sources and cc.live_retrieval_enabled:
        warnings.append("No sources are allowlisted for live retrieval.")

    live_blocked = not cc.live_retrieval_enabled
    live_potentially_allowed = (
        cc.live_retrieval_enabled
        and len(cc.allowed_live_sources) > 0
        and bool(cc.live_user_agent)
        and cc.max_requests_per_minute > 0
    )

    return {
        "live_retrieval_globally_enabled": cc.live_retrieval_enabled,
        "allowed_live_sources": cc.allowed_live_sources,
        "user_agent_configured": bool(cc.live_user_agent),
        "user_agent": cc.live_user_agent or "(not set)",
        "contact_email_configured": bool(cc.live_contact_email),
        "contact_email": cc.live_contact_email or "(not set)",
        "max_requests_per_minute": cc.max_requests_per_minute,
        "dry_run_required_before_live": cc.require_dry_run_before_live,
        "warnings": warnings,
        "live_retrieval_blocked": live_blocked,
        "live_retrieval_potentially_allowed": live_potentially_allowed,
        "retrieval_audit_dir": cc.retrieval_audit_dir,
    }


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

AUDIT_FIELDNAMES = [
    "timestamp",
    "source_site",
    "retrieval_mode",
    "url",
    "domain",
    "allowed",
    "blocked",
    "reason",
    "dry_run",
    "network_call_performed",
]


def write_audit_record(
    source_site: str,
    retrieval_mode: str,
    url: str,
    domain: str,
    allowed: bool,
    blocked: bool,
    reason: str,
    dry_run: bool = True,
    network_call_performed: bool = False,
    audit_dir: Optional[str] = None,
) -> str:
    """Write an audit record for a retrieval decision.

    Args:
        source_site: Source adapter name.
        retrieval_mode: Retrieval mode used.
        url: URL being accessed.
        domain: Domain being accessed.
        allowed: Whether the request was allowed.
        blocked: Whether the request was blocked.
        reason: Reason for the decision.
        dry_run: Whether this was a dry-run.
        network_call_performed: Whether a network call was made.
        audit_dir: Audit log directory. Defaults to logs/retrieval_audit.

    Returns:
        Path to the audit log file.
    """
    if audit_dir is None:
        cc = RetrievalComplianceConfig.from_env()
        audit_dir = cc.retrieval_audit_dir

    audit_path = Path(audit_dir)
    audit_path.mkdir(parents=True, exist_ok=True)

    # Use date-based log file
    date_str = datetime.now().strftime("%Y%m%d")
    log_file = audit_path / f"retrieval_audit_{date_str}.csv"

    file_exists = log_file.exists()

    record = {
        "timestamp": datetime.now().isoformat(),
        "source_site": source_site,
        "retrieval_mode": retrieval_mode,
        "url": url,
        "domain": domain,
        "allowed": str(allowed),
        "blocked": str(blocked),
        "reason": reason,
        "dry_run": str(dry_run),
        "network_call_performed": str(network_call_performed),
    }

    with open(log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)

    logger.debug(f"Audit record written to {log_file}: {source_site} {retrieval_mode} {url}")

    return str(log_file)
