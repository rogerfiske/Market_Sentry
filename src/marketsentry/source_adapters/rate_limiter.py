"""Deterministic local rate limiter for Market_Sentry.

Enforces max requests per minute and optional minimum delay between
requests. State is injectable and testable. No sleeping occurs in
tests. Dry-run requests do not consume live retrieval quota.

No network calls are performed by this module.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from marketsentry.source_adapters.compliance import RateLimitConfig


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RateLimitDecision(str, Enum):
    """Result of a rate limit check."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    COOLDOWN = "cooldown"


class SourceRateLimitState(BaseModel):
    """Current rate limit state for a source site.

    Tracks recent request timestamps to enforce rate limits.
    """

    source_site: str = ""
    request_timestamps: List[str] = Field(default_factory=list)
    last_request_at: Optional[str] = None
    total_requests: int = 0

    def add_timestamp(self, ts: datetime) -> None:
        """Record a request timestamp.

        Args:
            ts: Timestamp of the request.
        """
        self.request_timestamps.append(ts.isoformat())
        self.last_request_at = ts.isoformat()
        self.total_requests += 1

    def get_recent_timestamps(self, window: timedelta, now: datetime) -> List[datetime]:
        """Get timestamps within a time window.

        Args:
            window: Time window to check.
            now: Current time reference.

        Returns:
            List of datetime objects within the window.
        """
        cutoff = now - window
        recent = []
        for ts_str in self.request_timestamps:
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts >= cutoff:
                    recent.append(ts)
            except (ValueError, TypeError):
                continue
        return recent

    def prune_old(self, window: timedelta, now: datetime) -> None:
        """Remove timestamps older than the given window.

        Args:
            window: Time window to keep.
            now: Current time reference.
        """
        cutoff = now - window
        self.request_timestamps = [
            ts for ts in self.request_timestamps
            if datetime.fromisoformat(ts) >= cutoff
        ]


class RateLimitCheckResult(BaseModel):
    """Full result of a rate limit check."""

    decision: RateLimitDecision = RateLimitDecision.ALLOWED
    source_site: str = ""
    requests_in_window: int = 0
    max_allowed: int = 6
    seconds_until_allowed: float = 0.0
    message: str = ""


# ---------------------------------------------------------------------------
# Rate limit checking
# ---------------------------------------------------------------------------


def check_rate_limit(
    source_site: str,
    config: Optional[RateLimitConfig] = None,
    state: Optional[SourceRateLimitState] = None,
    now: Optional[datetime] = None,
) -> RateLimitCheckResult:
    """Check if a request is allowed by rate limits.

    Args:
        source_site: Source adapter name.
        config: Rate limit configuration. Uses defaults if None.
        state: Current rate limit state. Creates empty state if None.
        now: Current time. Uses datetime.now() if None.

    Returns:
        RateLimitCheckResult with decision and details.
    """
    cfg = config or RateLimitConfig()
    st = state or SourceRateLimitState(source_site=source_site)
    current_time = now or datetime.now()

    result = RateLimitCheckResult(
        source_site=source_site,
        max_allowed=cfg.max_requests_per_minute,
    )

    # Check requests in the last minute
    window = timedelta(minutes=1)
    recent = st.get_recent_timestamps(window, current_time)
    result.requests_in_window = len(recent)

    # Check max requests per minute
    if result.requests_in_window >= cfg.max_requests_per_minute:
        result.decision = RateLimitDecision.BLOCKED
        # Calculate when next request would be allowed
        if recent:
            oldest_in_window = min(recent)
            next_allowed = oldest_in_window + window
            result.seconds_until_allowed = max(
                0.0, (next_allowed - current_time).total_seconds()
            )
        result.message = (
            f"Rate limit exceeded: {result.requests_in_window}/{cfg.max_requests_per_minute} "
            f"requests in the last minute."
        )
        return result

    # Check minimum delay between requests
    if cfg.min_delay_seconds > 0 and st.last_request_at:
        try:
            last_ts = datetime.fromisoformat(st.last_request_at)
            elapsed = (current_time - last_ts).total_seconds()
            if elapsed < cfg.min_delay_seconds:
                remaining = cfg.min_delay_seconds - elapsed
                result.decision = RateLimitDecision.COOLDOWN
                result.seconds_until_allowed = remaining
                result.message = (
                    f"Minimum delay not met: {elapsed:.1f}s elapsed, "
                    f"{cfg.min_delay_seconds}s required."
                )
                return result
        except (ValueError, TypeError):
            pass

    result.decision = RateLimitDecision.ALLOWED
    result.message = (
        f"Rate limit OK: {result.requests_in_window}/{cfg.max_requests_per_minute} "
        f"requests in the last minute."
    )
    return result


def record_retrieval_attempt(
    state: SourceRateLimitState,
    now: Optional[datetime] = None,
) -> None:
    """Record a retrieval attempt in the rate limit state.

    Args:
        state: Rate limit state to update.
        now: Current time. Uses datetime.now() if None.
    """
    current_time = now or datetime.now()
    state.add_timestamp(current_time)
    # Prune old entries to keep state manageable
    state.prune_old(timedelta(minutes=5), current_time)
