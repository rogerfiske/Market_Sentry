"""Offline robots policy interface for Market_Sentry.

Parses locally saved robots.txt files to check retrieval compliance.
Does NOT fetch robots.txt from the internet. All checks use local
fixtures or saved policy files only.

Local policies directory: data/policies/robots/
Test fixtures: tests/fixtures/robots/
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from marketsentry.source_adapters.compliance import RobotsCheckResult


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass
class RobotsRule:
    """A single robots.txt rule (Disallow or Allow)."""

    path: str = ""
    rule_type: str = "disallow"  # "disallow" or "allow"


@dataclass
class SourceRobotsPolicy:
    """Parsed robots.txt policy for a source site.

    Contains user-agent blocks with their associated rules.
    """

    source_site: str = ""
    raw_text: str = ""
    user_agent_rules: dict = field(default_factory=dict)
    # user_agent_rules maps user-agent string -> list of RobotsRule
    parsed: bool = False
    notes: str = ""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_robots_text(robots_text: str, source_site: str = "") -> SourceRobotsPolicy:
    """Parse a robots.txt string into a SourceRobotsPolicy.

    Supports simple User-agent and Disallow/Allow rules. Handles
    wildcard user-agent '*'. Does not support pattern matching
    with wildcards in paths (e.g., '/foo*bar').

    Args:
        robots_text: Raw robots.txt content.
        source_site: Name of the source site.

    Returns:
        SourceRobotsPolicy with parsed rules.
    """
    policy = SourceRobotsPolicy(
        source_site=source_site,
        raw_text=robots_text,
    )

    if not robots_text or not robots_text.strip():
        policy.parsed = True
        policy.notes = "Empty robots.txt - no rules defined."
        return policy

    current_agents: List[str] = []
    rules_map: dict = {}

    for raw_line in robots_text.splitlines():
        line = raw_line.strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            if not line and current_agents:
                # Empty line ends a block - reset for next block
                current_agents = []
            continue

        # Remove inline comments
        if "#" in line:
            line = line[:line.index("#")].strip()

        if not line:
            continue

        # Parse directive
        if ":" not in line:
            continue

        directive, _, value = line.partition(":")
        directive = directive.strip().lower()
        value = value.strip()

        if directive == "user-agent":
            # Start or continue a user-agent block
            agent = value.lower()
            if agent not in current_agents:
                current_agents.append(agent)
            if agent not in rules_map:
                rules_map[agent] = []

        elif directive in ("disallow", "allow") and current_agents:
            rule = RobotsRule(
                path=value,
                rule_type=directive,
            )
            for agent in current_agents:
                if agent not in rules_map:
                    rules_map[agent] = []
                rules_map[agent].append(rule)

    policy.user_agent_rules = rules_map
    policy.parsed = True
    return policy


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------


def _get_rules_for_agent(
    policy: SourceRobotsPolicy, user_agent: str
) -> List[RobotsRule]:
    """Get the rules that apply to a specific user-agent.

    Tries exact match first, then falls back to wildcard '*'.

    Args:
        policy: Parsed robots policy.
        user_agent: User-agent string to check.

    Returns:
        List of applicable rules.
    """
    agent_lower = user_agent.lower()

    # Try exact match first
    if agent_lower in policy.user_agent_rules:
        return policy.user_agent_rules[agent_lower]

    # Try wildcard
    if "*" in policy.user_agent_rules:
        return policy.user_agent_rules["*"]

    return []


def _path_matches(rule_path: str, request_path: str) -> bool:
    """Check if a rule path matches a request path.

    Uses simple prefix matching as per standard robots.txt.

    Args:
        rule_path: Path from robots.txt rule.
        request_path: Path being requested.

    Returns:
        True if the rule matches the request path.
    """
    if not rule_path:
        return False
    return request_path.startswith(rule_path)


def check_robots_allowed(
    policy: SourceRobotsPolicy,
    user_agent: str,
    path: str,
) -> RobotsCheckResult:
    """Check if a path is allowed by the robots policy for a user-agent.

    Args:
        policy: Parsed robots policy.
        user_agent: User-agent string to check.
        path: URL path to check (e.g., "/city/19701/CA/Temecula").

    Returns:
        RobotsCheckResult with allowed/blocked status.
    """
    result = RobotsCheckResult(
        checked=True,
        user_agent=user_agent,
        robots_url=f"(local policy for {policy.source_site})",
    )

    if not policy.parsed:
        result.checked = False
        result.allowed = False
        result.notes = "Robots policy not parsed."
        return result

    rules = _get_rules_for_agent(policy, user_agent)

    if not rules:
        # No rules for this agent - allowed by default
        result.allowed = True
        result.notes = f"No rules found for user-agent '{user_agent}'. Allowed by default."
        return result

    # Find the most specific matching rule (longest path match)
    best_match: Optional[Tuple[int, RobotsRule]] = None

    for rule in rules:
        if _path_matches(rule.path, path):
            path_len = len(rule.path)
            if best_match is None or path_len > best_match[0]:
                best_match = (path_len, rule)

    if best_match is None:
        # No matching rules - allowed
        result.allowed = True
        result.notes = f"No matching rules for path '{path}'. Allowed by default."
        return result

    matched_rule = best_match[1]
    if matched_rule.rule_type == "allow":
        result.allowed = True
        result.notes = f"Explicitly allowed by rule: Allow: {matched_rule.path}"
    else:
        result.allowed = False
        result.notes = f"Blocked by rule: Disallow: {matched_rule.path}"

    return result


# ---------------------------------------------------------------------------
# Local policy loading
# ---------------------------------------------------------------------------

DEFAULT_POLICIES_DIR = "data/policies/robots"


def load_local_robots_policy(
    source_site: str,
    policies_dir: Optional[str] = None,
) -> Optional[SourceRobotsPolicy]:
    """Load a local robots.txt policy file for a source site.

    Looks for a file named '{source_site}_robots.txt' in the policies
    directory. Does NOT fetch from the internet.

    Args:
        source_site: Source site name (e.g., "redfin").
        policies_dir: Directory containing local robots.txt files.
            Defaults to data/policies/robots/.

    Returns:
        SourceRobotsPolicy if found and parsed, None if file not found.
    """
    dir_path = Path(policies_dir) if policies_dir else Path(DEFAULT_POLICIES_DIR)
    policy_file = dir_path / f"{source_site}_robots.txt"

    if not policy_file.exists():
        return None

    robots_text = policy_file.read_text(encoding="utf-8")
    return parse_robots_text(robots_text, source_site=source_site)
