"""Portfolio Trend Threshold Alerts and Local Notification Digest.

Converts portfolio trend analysis from Milestone 42 into local,
read-only operational flags. Generates a notification-style Markdown
and CSV digest of threshold alerts without mutating candidate,
watchlist, or alert state.

No outbound notifications are sent. All alerts are local review
prompts only.
"""

import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

logger = logging.getLogger("marketsentry")


# ---------------------------------------------------------------------------
# Config constants
# ---------------------------------------------------------------------------

DEFAULT_RULE_CONFIG_PATH = Path(
    "config/portfolio_trend_alert_rules.json"
)
EXAMPLE_RULE_CONFIG_PATH = Path(
    "config/portfolio_trend_alert_rules.example.json"
)

ALLOWED_MODES = ("merge", "replace")
ALLOWED_SCOPES = ("portfolio", "property")
ALLOWED_COMPARISONS = (
    ">=", ">", "<=", "<", "==", "!=", "delta>=", "delta<="
)
ALLOWED_SEVERITIES = ("info", "warning", "high")

# Metrics that must not be referenced in custom rules
FORBIDDEN_METRIC_PREFIXES = (
    "walkability", "walk_score", "transit_score",
)
FORBIDDEN_METRIC_KEYWORDS = (
    "live_retrieval", "scrape", "playwright", "selenium",
)

EXAMPLE_RULE_CONFIG: Dict = {
    "mode": "merge",
    "rules": [
        {
            "rule_id": "custom_aggregate_burden_high",
            "rule_name": (
                "Custom aggregate burden high threshold"
            ),
            "scope": "portfolio",
            "metric_name": "aggregate_review_burden_score",
            "threshold_value": 75,
            "comparison": ">=",
            "severity": "high",
            "enabled": True,
            "message_template": (
                "Aggregate review burden is "
                "{current_value}, threshold "
                "{threshold_value}"
            ),
            "recommended_local_action": (
                "Review top burden contributors in "
                "the trend digest"
            ),
        },
        {
            "rule_id": "custom_property_health_drop",
            "rule_name": (
                "Custom property health score drop"
            ),
            "scope": "property",
            "metric_name": "lifecycle_health_score_delta",
            "threshold_value": -10,
            "comparison": "delta<=",
            "severity": "warning",
            "enabled": True,
            "message_template": (
                "Health score delta is {current_value}, "
                "threshold {threshold_value}"
            ),
            "recommended_local_action": (
                "Review lifecycle health trend"
            ),
        },
        {
            "rule_id": "custom_disabled_example",
            "rule_name": "Disabled example rule",
            "scope": "portfolio",
            "metric_name": "aggregate_review_burden_score",
            "threshold_value": 90,
            "comparison": ">=",
            "severity": "info",
            "enabled": False,
            "message_template": (
                "Burden is {current_value}"
            ),
            "recommended_local_action": (
                "This rule is disabled by default"
            ),
        },
    ],
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PortfolioTrendAlert(BaseModel):
    """One trend threshold alert."""

    alert_id: str = ""
    alert_scope: str = ""  # portfolio / property
    property_id: str = ""
    candidate_id: str = ""
    address: str = ""
    severity: str = "info"  # info / warning / high
    alert_type: str = ""
    message: str = ""
    metric_name: str = ""
    previous_value: str = ""
    current_value: str = ""
    delta_value: str = ""
    recommended_local_action: str = ""
    source_pack_file: str = ""
    generated_at: str = ""


class PortfolioTrendAlertRule(BaseModel):
    """A threshold rule for generating trend alerts (built-in)."""

    rule_id: str = ""
    alert_scope: str = ""  # portfolio / property
    alert_type: str = ""
    metric_name: str = ""
    threshold: float = 0.0
    severity: str = "info"
    description: str = ""


class ConfigurablePortfolioTrendAlertRule(BaseModel):
    """A configurable threshold rule from JSON config.

    This extends the built-in rule model with fields from the
    JSON config schema: enabled, comparison, message_template,
    recommended_local_action, and rule_name.
    """

    rule_id: str = ""
    rule_name: str = ""
    scope: str = ""  # portfolio / property
    metric_name: str = ""
    threshold_value: float = 0.0
    comparison: str = ">="
    severity: str = "info"
    enabled: bool = True
    message_template: str = ""
    recommended_local_action: str = ""


class PortfolioTrendAlertRuleConfig(BaseModel):
    """Container for a loaded rule config file."""

    mode: str = "merge"
    rules: List[ConfigurablePortfolioTrendAlertRule] = Field(
        default_factory=list
    )
    source_path: str = ""
    is_valid: bool = True
    errors: List[str] = Field(default_factory=list)


class PortfolioTrendAlertSummary(BaseModel):
    """Summary of trend alerts by severity."""

    total_alerts: int = 0
    info_count: int = 0
    warning_count: int = 0
    high_count: int = 0
    pack_count: int = 0
    first_pack_date: str = ""
    latest_pack_date: str = ""


class PortfolioTrendAlertDigest(BaseModel):
    """A complete digest of trend alerts."""

    alerts: List[PortfolioTrendAlert] = Field(default_factory=list)
    summary: PortfolioTrendAlertSummary = Field(
        default_factory=PortfolioTrendAlertSummary
    )
    generated_at: str = ""
    source_pack_files: List[str] = Field(default_factory=list)


class PortfolioTrendAlertRunResult(BaseModel):
    """Result of a trend alert evaluation and export run."""

    export_paths: List[str] = Field(default_factory=list)
    alert_count: int = 0
    summary: Optional[PortfolioTrendAlertSummary] = None
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# CSV field names for alert digest
# ---------------------------------------------------------------------------

ALERT_DIGEST_CSV_FIELDNAMES = [
    "alert_id",
    "alert_scope",
    "property_id",
    "candidate_id",
    "address",
    "severity",
    "alert_type",
    "message",
    "metric_name",
    "previous_value",
    "current_value",
    "delta_value",
    "recommended_local_action",
    "source_pack_file",
    "generated_at",
]


# ---------------------------------------------------------------------------
# Default alert rules
# ---------------------------------------------------------------------------

def get_default_portfolio_trend_alert_rules() -> List[PortfolioTrendAlertRule]:
    """Return the default set of portfolio trend alert rules.

    Returns:
        List of PortfolioTrendAlertRule with default thresholds.
    """
    return [
        # Aggregate burden rules
        PortfolioTrendAlertRule(
            rule_id="burden_high_80",
            alert_scope="portfolio",
            alert_type="aggregate_burden_high",
            metric_name="aggregate_review_burden_score",
            threshold=80.0,
            severity="high",
            description=(
                "Aggregate review burden score >= 80"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="burden_warning_60",
            alert_scope="portfolio",
            alert_type="aggregate_burden_warning",
            metric_name="aggregate_review_burden_score",
            threshold=60.0,
            severity="warning",
            description=(
                "Aggregate review burden score >= 60"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="burden_increase_15",
            alert_scope="portfolio",
            alert_type="aggregate_burden_increase",
            metric_name="aggregate_burden_delta",
            threshold=15.0,
            severity="warning",
            description=(
                "Aggregate burden increased by >= 15"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="burden_label_worsening",
            alert_scope="portfolio",
            alert_type="burden_label_worsening",
            metric_name="aggregate_review_status_label",
            threshold=0.0,
            severity="warning",
            description=(
                "Burden label changed to elevated_burden "
                "or high_burden"
            ),
        ),
        # Backlog rules
        PortfolioTrendAlertRule(
            rule_id="immediate_review_increase",
            alert_scope="portfolio",
            alert_type="backlog_immediate_increase",
            metric_name="immediate_review_count",
            threshold=1.0,
            severity="warning",
            description=(
                "Immediate review count increased"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="high_review_increase_2",
            alert_scope="portfolio",
            alert_type="backlog_high_increase",
            metric_name="high_review_count",
            threshold=2.0,
            severity="warning",
            description=(
                "High review count increased by >= 2"
            ),
        ),
        # Property degradation rules
        PortfolioTrendAlertRule(
            rule_id="property_degraded",
            alert_scope="property",
            alert_type="property_trend_degraded",
            metric_name="trend_direction",
            threshold=0.0,
            severity="warning",
            description="Property trend direction is degraded",
        ),
        PortfolioTrendAlertRule(
            rule_id="health_score_drop_15",
            alert_scope="property",
            alert_type="lifecycle_health_drop",
            metric_name="lifecycle_health_score_delta",
            threshold=-15.0,
            severity="warning",
            description=(
                "Lifecycle health score decreased by >= 15"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="health_label_attention",
            alert_scope="property",
            alert_type="lifecycle_label_worsening",
            metric_name="lifecycle_health_label",
            threshold=0.0,
            severity="high",
            description=(
                "Health label changed to needs_review "
                "or attention_required"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="open_alert_increase_2",
            alert_scope="property",
            alert_type="open_alert_increase",
            metric_name="open_alert_delta",
            threshold=2.0,
            severity="warning",
            description=(
                "Open alert count increased by >= 2"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="confidence_drop_15",
            alert_scope="property",
            alert_type="cross_site_confidence_drop",
            metric_name="cross_site_confidence_delta",
            threshold=-15.0,
            severity="warning",
            description=(
                "Cross-site confidence decreased by >= 15"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="churn_increase_1_5",
            alert_scope="property",
            alert_type="churn_index_increase",
            metric_name="churn_index_delta",
            threshold=1.5,
            severity="warning",
            description=(
                "Churn Index increased by >= 1.5"
            ),
        ),
        PortfolioTrendAlertRule(
            rule_id="dom_v2_increase_30",
            alert_scope="property",
            alert_type="effective_dom_v2_increase",
            metric_name="effective_dom_v2_delta",
            threshold=30.0,
            severity="info",
            description=(
                "Effective DOM v2 increased by >= 30 days"
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Built-in rule IDs (for override detection)
# ---------------------------------------------------------------------------

_BUILTIN_RULE_IDS = {
    r.rule_id for r in get_default_portfolio_trend_alert_rules()
}


# ---------------------------------------------------------------------------
# Rule configuration loader functions (Milestone 44)
# ---------------------------------------------------------------------------

def load_portfolio_trend_alert_rule_config(
    config_path: Optional[Union[Path, str]] = None,
) -> PortfolioTrendAlertRuleConfig:
    """Load a portfolio trend alert rule config from JSON.

    If the config file does not exist, returns an empty config
    with is_valid=True (missing config is not an error).

    Args:
        config_path: Path to JSON config. Defaults to
            config/portfolio_trend_alert_rules.json.

    Returns:
        PortfolioTrendAlertRuleConfig with loaded rules or errors.
    """
    path = (
        Path(config_path) if config_path
        else DEFAULT_RULE_CONFIG_PATH
    )
    config = PortfolioTrendAlertRuleConfig(
        source_path=str(path)
    )

    if not path.exists():
        return config

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        config.is_valid = False
        config.errors.append(f"Invalid JSON in {path}: {e}")
        return config
    except Exception as e:
        config.is_valid = False
        config.errors.append(f"Error reading {path}: {e}")
        return config

    if not isinstance(data, dict):
        config.is_valid = False
        config.errors.append(
            f"Config must be a JSON object: {path}"
        )
        return config

    # Parse mode
    mode = data.get("mode", "merge")
    if mode not in ALLOWED_MODES:
        config.is_valid = False
        config.errors.append(
            f"Invalid mode '{mode}'. "
            f"Allowed: {', '.join(ALLOWED_MODES)}"
        )
        return config
    config.mode = mode

    # Parse rules
    raw_rules = data.get("rules", [])
    if not isinstance(raw_rules, list):
        config.is_valid = False
        config.errors.append("'rules' must be a list.")
        return config

    seen_ids: set = set()
    for idx, raw in enumerate(raw_rules):
        rule, errors = _parse_configurable_rule(
            raw, idx, seen_ids
        )
        if errors:
            config.errors.extend(errors)
            config.is_valid = False
        elif rule is not None:
            seen_ids.add(rule.rule_id)
            config.rules.append(rule)

    return config


def _parse_configurable_rule(
    raw: dict,
    idx: int,
    seen_ids: set,
) -> Tuple[
    Optional[ConfigurablePortfolioTrendAlertRule],
    List[str],
]:
    """Parse and validate a single configurable rule dict.

    Args:
        raw: Raw rule dict from JSON.
        idx: Index in the rules array for error messages.
        seen_ids: Set of already-seen rule IDs.

    Returns:
        Tuple of (rule_or_None, error_list).
    """
    errors: List[str] = []
    prefix = f"Rule index {idx}"

    if not isinstance(raw, dict):
        return None, [f"{prefix}: must be a JSON object."]

    # Required fields
    rule_id = raw.get("rule_id", "")
    if not rule_id:
        errors.append(f"{prefix}: 'rule_id' is required.")
    elif rule_id in seen_ids:
        errors.append(
            f"{prefix}: duplicate rule_id '{rule_id}'."
        )
    elif rule_id in _BUILTIN_RULE_IDS:
        errors.append(
            f"{prefix}: rule_id '{rule_id}' conflicts with "
            f"a built-in rule. User config must not silently "
            f"override built-in rule IDs."
        )

    rule_name = raw.get("rule_name", "")
    if not rule_name:
        errors.append(f"{prefix}: 'rule_name' is required.")

    scope = raw.get("scope", "")
    if not scope:
        errors.append(f"{prefix}: 'scope' is required.")
    elif scope not in ALLOWED_SCOPES:
        errors.append(
            f"{prefix}: invalid scope '{scope}'. "
            f"Allowed: {', '.join(ALLOWED_SCOPES)}"
        )

    metric_name = raw.get("metric_name", "")
    if not metric_name:
        errors.append(
            f"{prefix}: 'metric_name' is required."
        )
    else:
        # Check forbidden metrics
        mn_lower = metric_name.lower()
        for fp in FORBIDDEN_METRIC_PREFIXES:
            if mn_lower.startswith(fp):
                errors.append(
                    f"{prefix}: metric_name '{metric_name}' "
                    f"references forbidden walkability metric."
                )
                break
        for kw in FORBIDDEN_METRIC_KEYWORDS:
            if kw in mn_lower:
                errors.append(
                    f"{prefix}: metric_name '{metric_name}' "
                    f"references forbidden live retrieval "
                    f"metric."
                )
                break

    comparison = raw.get("comparison", "")
    if not comparison:
        errors.append(
            f"{prefix}: 'comparison' is required."
        )
    elif comparison not in ALLOWED_COMPARISONS:
        errors.append(
            f"{prefix}: invalid comparison '{comparison}'. "
            f"Allowed: {', '.join(ALLOWED_COMPARISONS)}"
        )

    severity = raw.get("severity", "")
    if not severity:
        errors.append(
            f"{prefix}: 'severity' is required."
        )
    elif severity not in ALLOWED_SEVERITIES:
        errors.append(
            f"{prefix}: invalid severity '{severity}'. "
            f"Allowed: {', '.join(ALLOWED_SEVERITIES)}"
        )

    # threshold_value: numeric where applicable
    threshold_value = raw.get("threshold_value")
    if threshold_value is not None:
        if not isinstance(threshold_value, (int, float)):
            errors.append(
                f"{prefix}: 'threshold_value' must be numeric."
            )
            threshold_value = 0.0
    else:
        threshold_value = 0.0

    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        errors.append(
            f"{prefix}: 'enabled' must be true or false."
        )
        enabled = True

    if errors:
        return None, errors

    rule = ConfigurablePortfolioTrendAlertRule(
        rule_id=rule_id,
        rule_name=rule_name,
        scope=scope,
        metric_name=metric_name,
        threshold_value=float(threshold_value),
        comparison=comparison,
        severity=severity,
        enabled=enabled,
        message_template=raw.get("message_template", ""),
        recommended_local_action=raw.get(
            "recommended_local_action", ""
        ),
    )
    return rule, []


def validate_portfolio_trend_alert_rule_config(
    config_path: Optional[Union[Path, str]] = None,
) -> Tuple[bool, List[str], int, int]:
    """Validate a portfolio trend alert rule config file.

    Args:
        config_path: Path to the config file.

    Returns:
        Tuple of (is_valid, errors, enabled_count,
        disabled_count).
    """
    config = load_portfolio_trend_alert_rule_config(
        config_path
    )
    enabled = sum(1 for r in config.rules if r.enabled)
    disabled = sum(1 for r in config.rules if not r.enabled)
    return config.is_valid, config.errors, enabled, disabled


def merge_portfolio_trend_alert_rules(
    config_path: Optional[Union[Path, str]] = None,
) -> Tuple[
    List[ConfigurablePortfolioTrendAlertRule], List[str]
]:
    """Merge built-in and user-defined alert rules.

    In 'merge' mode, enabled custom rules are appended after
    built-in rules converted to configurable format.
    In 'replace' mode, only enabled custom rules are used.

    Args:
        config_path: Path to user config file.

    Returns:
        Tuple of (merged_rules, errors).
    """
    builtin_configurable = _builtin_to_configurable()
    config = load_portfolio_trend_alert_rule_config(
        config_path
    )

    if not config.is_valid:
        return builtin_configurable, config.errors

    # If no config file found, just return builtins
    path = (
        Path(config_path) if config_path
        else DEFAULT_RULE_CONFIG_PATH
    )
    if not path.exists():
        return builtin_configurable, []

    enabled_custom = [r for r in config.rules if r.enabled]

    if config.mode == "replace":
        return enabled_custom, config.errors

    # merge mode: builtins + enabled custom
    return builtin_configurable + enabled_custom, config.errors


def write_portfolio_trend_alert_rule_template(
    output_path: Optional[Union[Path, str]] = None,
    overwrite: bool = False,
) -> Tuple[str, bool]:
    """Write an example trend alert rule config file.

    Args:
        output_path: Output path. Defaults to
            config/portfolio_trend_alert_rules.example.json.
        overwrite: Whether to overwrite existing file.

    Returns:
        Tuple of (path_written, was_written).
    """
    path = (
        Path(output_path) if output_path
        else EXAMPLE_RULE_CONFIG_PATH
    )
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and not overwrite:
        return str(path), False

    with open(path, "w", encoding="utf-8") as f:
        json.dump(EXAMPLE_RULE_CONFIG, f, indent=2)
        f.write("\n")

    return str(path), True


def get_active_portfolio_trend_alert_rules(
    config_path: Optional[Union[Path, str]] = None,
) -> Tuple[
    List[ConfigurablePortfolioTrendAlertRule],
    str,
    int,
    int,
    List[str],
]:
    """Get active rules after merging built-in and custom.

    Args:
        config_path: Path to user config file.

    Returns:
        Tuple of (active_rules, mode, enabled_count,
        disabled_count, errors).
    """
    config = load_portfolio_trend_alert_rule_config(
        config_path
    )
    path = (
        Path(config_path) if config_path
        else DEFAULT_RULE_CONFIG_PATH
    )
    has_config = path.exists()

    if not has_config or not config.is_valid:
        builtin = _builtin_to_configurable()
        return (
            builtin,
            "builtin",
            len(builtin),
            0,
            config.errors,
        )

    merged, errors = merge_portfolio_trend_alert_rules(
        config_path
    )

    all_custom = config.rules
    enabled = sum(1 for r in all_custom if r.enabled)
    disabled = sum(1 for r in all_custom if not r.enabled)

    return merged, config.mode, enabled, disabled, errors


def _builtin_to_configurable() -> (
    List[ConfigurablePortfolioTrendAlertRule]
):
    """Convert built-in rules to configurable format.

    Returns:
        List of ConfigurablePortfolioTrendAlertRule.
    """
    builtin = get_default_portfolio_trend_alert_rules()
    result: List[ConfigurablePortfolioTrendAlertRule] = []
    for r in builtin:
        result.append(ConfigurablePortfolioTrendAlertRule(
            rule_id=r.rule_id,
            rule_name=r.description,
            scope=r.alert_scope,
            metric_name=r.metric_name,
            threshold_value=r.threshold,
            comparison=">=",
            severity=r.severity,
            enabled=True,
            message_template="",
            recommended_local_action="",
        ))
    return result


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def evaluate_portfolio_trend_alerts(
    exports_dir: str = "data/exports",
    rule_config: Optional[Union[Path, str]] = None,
) -> PortfolioTrendAlertDigest:
    """Evaluate all portfolio trend alert rules against trend data.

    Loads trend data from existing portfolio review pack CSV exports,
    evaluates aggregate and property-level alert rules, and returns
    a complete digest. When rule_config is provided, custom rules
    are loaded and merged/replaced per the config mode.

    Args:
        exports_dir: Directory with review pack CSV exports.
        rule_config: Optional path to a custom rule config JSON.

    Returns:
        PortfolioTrendAlertDigest with all triggered alerts.
    """
    from marketsentry.portfolio_review_trends import (
        build_portfolio_trend_series,
        build_property_trend_series,
        load_portfolio_review_pack_series,
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    digest = PortfolioTrendAlertDigest(generated_at=now)

    series = load_portfolio_review_pack_series(exports_dir)
    if not series:
        digest.alerts.append(PortfolioTrendAlert(
            alert_id="no_pack_data",
            alert_scope="portfolio",
            severity="info",
            alert_type="no_data",
            message="No portfolio review pack CSV files found.",
            generated_at=now,
        ))
        digest.summary = summarize_portfolio_trend_alerts(
            digest.alerts
        )
        return digest

    digest.source_pack_files = [fp for fp, _, _ in series]

    portfolio_points = build_portfolio_trend_series(series)
    property_points = build_property_trend_series(series)

    # Determine which rules to use
    if rule_config is not None:
        active_rules, _, _, _, config_errors = (
            get_active_portfolio_trend_alert_rules(rule_config)
        )
        if config_errors:
            for err in config_errors:
                digest.alerts.append(PortfolioTrendAlert(
                    alert_id="config_error",
                    alert_scope="portfolio",
                    severity="warning",
                    alert_type="config_validation_error",
                    message=err,
                    generated_at=now,
                ))
        # Use configurable evaluation
        custom_alerts = _evaluate_configurable_rules(
            active_rules, portfolio_points,
            property_points, now,
        )
        digest.alerts.extend(custom_alerts)
    else:
        # Default built-in evaluation (M43 behavior)
        agg_alerts = evaluate_aggregate_burden_alerts(
            portfolio_points, now
        )
        digest.alerts.extend(agg_alerts)

        prop_alerts = evaluate_property_trend_alerts(
            property_points, now
        )
        digest.alerts.extend(prop_alerts)

    # Summarize
    digest.summary = summarize_portfolio_trend_alerts(
        digest.alerts
    )
    if portfolio_points:
        digest.summary.pack_count = len(portfolio_points)
        digest.summary.first_pack_date = (
            portfolio_points[0].captured_at
        )
        digest.summary.latest_pack_date = (
            portfolio_points[-1].captured_at
        )

    return digest


def _evaluate_configurable_rules(
    rules: List[ConfigurablePortfolioTrendAlertRule],
    portfolio_points: list,
    property_points: list,
    generated_at: str,
) -> List[PortfolioTrendAlert]:
    """Evaluate configurable rules against trend data.

    This function applies custom/merged rules using the
    comparison operators from the config schema.

    Args:
        rules: Active configurable rules to evaluate.
        portfolio_points: Portfolio-level trend points.
        property_points: Per-property trend points.
        generated_at: Timestamp for alert generation.

    Returns:
        List of triggered PortfolioTrendAlert instances.
    """
    alerts: List[PortfolioTrendAlert] = []

    if not portfolio_points:
        return alerts

    latest = portfolio_points[-1]
    prev = (
        portfolio_points[-2]
        if len(portfolio_points) >= 2 else None
    )
    source = latest.pack_file

    for rule in rules:
        if not rule.enabled:
            continue

        if rule.scope == "portfolio":
            new_alerts = _eval_portfolio_rule(
                rule, latest, prev, source, generated_at
            )
            alerts.extend(new_alerts)
        elif rule.scope == "property":
            for pt in property_points:
                new_alerts = _eval_property_rule(
                    rule, pt, generated_at
                )
                alerts.extend(new_alerts)

    return alerts


def _eval_portfolio_rule(
    rule: ConfigurablePortfolioTrendAlertRule,
    latest: object,
    prev: object,
    source: str,
    generated_at: str,
) -> List[PortfolioTrendAlert]:
    """Evaluate a single portfolio-scope configurable rule.

    Args:
        rule: The configurable rule.
        latest: Latest portfolio trend point.
        prev: Previous portfolio trend point (may be None).
        source: Source pack file path.
        generated_at: Timestamp.

    Returns:
        List of alerts (0 or 1).
    """
    current_val = _get_portfolio_metric(
        latest, rule.metric_name
    )
    prev_val = (
        _get_portfolio_metric(prev, rule.metric_name)
        if prev else None
    )

    if current_val is None:
        return []

    triggered = _check_comparison(
        rule.comparison, current_val, prev_val,
        rule.threshold_value,
    )
    if not triggered:
        return []

    delta_str = ""
    if prev_val is not None:
        delta_str = str(
            round(current_val - prev_val, 2)
        )

    msg = rule.message_template
    if msg:
        msg = msg.replace(
            "{current_value}", str(current_val)
        ).replace(
            "{threshold_value}", str(rule.threshold_value)
        ).replace(
            "{previous_value}", str(prev_val or "")
        ).replace(
            "{delta_value}", delta_str
        )
    else:
        msg = (
            f"{rule.rule_name}: {rule.metric_name} is "
            f"{current_val} (threshold: "
            f"{rule.threshold_value})"
        )

    return [PortfolioTrendAlert(
        alert_id=rule.rule_id,
        alert_scope="portfolio",
        severity=rule.severity,
        alert_type=rule.rule_id,
        message=msg,
        metric_name=rule.metric_name,
        previous_value=str(prev_val or ""),
        current_value=str(current_val),
        delta_value=delta_str,
        source_pack_file=source,
        generated_at=generated_at,
        recommended_local_action=(
            rule.recommended_local_action
        ),
    )]


def _eval_property_rule(
    rule: ConfigurablePortfolioTrendAlertRule,
    pt: object,
    generated_at: str,
) -> List[PortfolioTrendAlert]:
    """Evaluate a single property-scope configurable rule.

    Args:
        rule: The configurable rule.
        pt: Property trend point.
        generated_at: Timestamp.

    Returns:
        List of alerts (0 or 1).
    """
    current_val = _get_property_metric(
        pt, rule.metric_name
    )
    if current_val is None:
        return []

    # For delta comparisons on property, use the delta
    # fields directly. The comparison is against
    # threshold_value.
    triggered = False
    if rule.comparison in ("delta>=", "delta<="):
        triggered = _check_comparison(
            rule.comparison, current_val, None,
            rule.threshold_value,
        )
    else:
        triggered = _check_comparison(
            rule.comparison, current_val, None,
            rule.threshold_value,
        )

    if not triggered:
        return []

    msg = rule.message_template
    if msg:
        msg = msg.replace(
            "{current_value}", str(current_val)
        ).replace(
            "{threshold_value}", str(rule.threshold_value)
        ).replace(
            "{address}", getattr(pt, "address", "")
        )
    else:
        msg = (
            f"{getattr(pt, 'address', '')}: "
            f"{rule.rule_name} - {rule.metric_name} is "
            f"{current_val}"
        )

    return [PortfolioTrendAlert(
        alert_id=(
            f"prop_{getattr(pt, 'property_id', '')}"
            f"_{rule.rule_id}"
        ),
        alert_scope="property",
        property_id=str(getattr(pt, "property_id", "")),
        candidate_id=str(
            getattr(pt, "candidate_id", "")
        ),
        address=getattr(pt, "address", ""),
        severity=rule.severity,
        alert_type=rule.rule_id,
        message=msg,
        metric_name=rule.metric_name,
        current_value=str(current_val),
        recommended_local_action=(
            rule.recommended_local_action
        ),
        generated_at=generated_at,
    )]


def _get_portfolio_metric(
    point: object,
    metric_name: str,
) -> Optional[float]:
    """Extract a numeric metric from a portfolio point.

    Args:
        point: Portfolio trend point.
        metric_name: Metric attribute name.

    Returns:
        Numeric value or None.
    """
    val = getattr(point, metric_name, None)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _get_property_metric(
    point: object,
    metric_name: str,
) -> Optional[float]:
    """Extract a numeric metric from a property point.

    Maps common metric names to property trend point
    attributes including delta fields.

    Args:
        point: Property trend point.
        metric_name: Metric name from rule config.

    Returns:
        Numeric value or None.
    """
    # Map metric names to property trend point attributes
    attr_map = {
        "lifecycle_health_score_delta": (
            "lifecycle_health_score_delta_first_to_latest"
        ),
        "open_alert_delta": (
            "open_alert_delta_first_to_latest"
        ),
        "cross_site_confidence_delta": (
            "cross_site_confidence_delta_first_to_latest"
        ),
        "churn_index_delta": (
            "churn_index_delta_first_to_latest"
        ),
        "effective_dom_v2_delta": (
            "effective_dom_v2_delta_first_to_latest"
        ),
        "latest_lifecycle_health_score": (
            "latest_lifecycle_health_score"
        ),
        "latest_open_alert_count": (
            "latest_open_alert_count"
        ),
        "latest_cross_site_confidence": (
            "latest_cross_site_confidence"
        ),
        "latest_recent_churn_index": (
            "latest_recent_churn_index"
        ),
        "latest_effective_dom_v2": (
            "latest_effective_dom_v2"
        ),
    }

    attr = attr_map.get(metric_name, metric_name)
    val = getattr(point, attr, None)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _check_comparison(
    comparison: str,
    current: float,
    previous: Optional[float],
    threshold: float,
) -> bool:
    """Check whether a comparison condition is met.

    Args:
        comparison: Comparison operator string.
        current: Current metric value.
        previous: Previous metric value (for delta).
        threshold: Threshold value from rule.

    Returns:
        True if the condition is triggered.
    """
    if comparison == ">=":
        return current >= threshold
    elif comparison == ">":
        return current > threshold
    elif comparison == "<=":
        return current <= threshold
    elif comparison == "<":
        return current < threshold
    elif comparison == "==":
        return current == threshold
    elif comparison == "!=":
        return current != threshold
    elif comparison == "delta>=":
        if previous is not None:
            return (current - previous) >= threshold
        # For property metrics, current IS the delta
        return current >= threshold
    elif comparison == "delta<=":
        if previous is not None:
            return (current - previous) <= threshold
        return current <= threshold
    return False


def evaluate_aggregate_burden_alerts(
    portfolio_points: list,
    generated_at: str,
) -> List[PortfolioTrendAlert]:
    """Evaluate aggregate burden threshold alerts.

    Args:
        portfolio_points: Portfolio-level trend points from M42.
        generated_at: Timestamp for alert generation.

    Returns:
        List of triggered PortfolioTrendAlert instances.
    """
    alerts: List[PortfolioTrendAlert] = []
    if not portfolio_points:
        return alerts

    latest = portfolio_points[-1]
    source = latest.pack_file

    # Absolute burden thresholds
    score = latest.aggregate_review_burden_score
    if score >= 80:
        alerts.append(PortfolioTrendAlert(
            alert_id="burden_high_80",
            alert_scope="portfolio",
            severity="high",
            alert_type="aggregate_burden_high",
            message=(
                f"Aggregate review burden score is {score} "
                f"(high_burden threshold: 80)."
            ),
            metric_name="aggregate_review_burden_score",
            current_value=str(score),
            source_pack_file=source,
            generated_at=generated_at,
            recommended_local_action=(
                "Review portfolio for immediate triage "
                "opportunities."
            ),
        ))
    elif score >= 60:
        alerts.append(PortfolioTrendAlert(
            alert_id="burden_warning_60",
            alert_scope="portfolio",
            severity="warning",
            alert_type="aggregate_burden_warning",
            message=(
                f"Aggregate review burden score is {score} "
                f"(warning threshold: 60)."
            ),
            metric_name="aggregate_review_burden_score",
            current_value=str(score),
            source_pack_file=source,
            generated_at=generated_at,
            recommended_local_action=(
                "Monitor burden trend. Review high-priority "
                "properties."
            ),
        ))

    # Burden increase alert (requires >= 2 packs)
    if len(portfolio_points) >= 2:
        prev = portfolio_points[-2]
        prev_score = prev.aggregate_review_burden_score
        delta = score - prev_score
        if delta >= 15:
            alerts.append(PortfolioTrendAlert(
                alert_id="burden_increase_15",
                alert_scope="portfolio",
                severity="warning",
                alert_type="aggregate_burden_increase",
                message=(
                    f"Aggregate burden increased by {delta} "
                    f"(from {prev_score} to {score})."
                ),
                metric_name="aggregate_burden_delta",
                previous_value=str(prev_score),
                current_value=str(score),
                delta_value=str(delta),
                source_pack_file=source,
                generated_at=generated_at,
                recommended_local_action=(
                    "Investigate properties driving burden "
                    "increase."
                ),
            ))

        # Burden label worsening
        prev_label = prev.aggregate_review_status_label
        curr_label = latest.aggregate_review_status_label
        if curr_label in ("elevated_burden", "high_burden") and (
            curr_label != prev_label
        ):
            sev = (
                "high" if curr_label == "high_burden"
                else "warning"
            )
            alerts.append(PortfolioTrendAlert(
                alert_id="burden_label_worsening",
                alert_scope="portfolio",
                severity=sev,
                alert_type="burden_label_worsening",
                message=(
                    f"Burden label changed from {prev_label} "
                    f"to {curr_label}."
                ),
                metric_name="aggregate_review_status_label",
                previous_value=prev_label,
                current_value=curr_label,
                source_pack_file=source,
                generated_at=generated_at,
                recommended_local_action=(
                    "Review portfolio burden drivers."
                ),
            ))

        # Backlog alerts
        prev_imm = prev.immediate_review_count
        curr_imm = latest.immediate_review_count
        if curr_imm > prev_imm:
            alerts.append(PortfolioTrendAlert(
                alert_id="immediate_review_increase",
                alert_scope="portfolio",
                severity="warning",
                alert_type="backlog_immediate_increase",
                message=(
                    f"Immediate review count increased from "
                    f"{prev_imm} to {curr_imm}."
                ),
                metric_name="immediate_review_count",
                previous_value=str(prev_imm),
                current_value=str(curr_imm),
                delta_value=str(curr_imm - prev_imm),
                source_pack_file=source,
                generated_at=generated_at,
                recommended_local_action=(
                    "Prioritize immediate review backlog."
                ),
            ))

        prev_high = prev.high_review_count
        curr_high = latest.high_review_count
        h_delta = curr_high - prev_high
        if h_delta >= 2:
            alerts.append(PortfolioTrendAlert(
                alert_id="high_review_increase_2",
                alert_scope="portfolio",
                severity="warning",
                alert_type="backlog_high_increase",
                message=(
                    f"High review count increased by {h_delta} "
                    f"(from {prev_high} to {curr_high})."
                ),
                metric_name="high_review_count",
                previous_value=str(prev_high),
                current_value=str(curr_high),
                delta_value=str(h_delta),
                source_pack_file=source,
                generated_at=generated_at,
                recommended_local_action=(
                    "Review growing high-priority backlog."
                ),
            ))

        # Rising high/critical alert burden
        prev_hca = prev.high_critical_alert_total
        curr_hca = latest.high_critical_alert_total
        hca_delta = curr_hca - prev_hca
        if hca_delta >= 1:
            alerts.append(PortfolioTrendAlert(
                alert_id="high_critical_alert_increase",
                alert_scope="portfolio",
                severity="high",
                alert_type="high_critical_alert_increase",
                message=(
                    f"High/critical alert total increased by "
                    f"{hca_delta} (from {prev_hca} to "
                    f"{curr_hca})."
                ),
                metric_name="high_critical_alert_total",
                previous_value=str(prev_hca),
                current_value=str(curr_hca),
                delta_value=str(hca_delta),
                source_pack_file=source,
                generated_at=generated_at,
                recommended_local_action=(
                    "Review properties with new high/critical "
                    "alerts."
                ),
            ))

        # Rising lifecycle attention/needs_review burden
        prev_att = prev.lifecycle_attention_required_count
        curr_att = latest.lifecycle_attention_required_count
        prev_nr = prev.lifecycle_needs_review_count
        curr_nr = latest.lifecycle_needs_review_count
        lc_delta = (curr_att + curr_nr) - (prev_att + prev_nr)
        if lc_delta >= 2:
            alerts.append(PortfolioTrendAlert(
                alert_id="lifecycle_burden_increase",
                alert_scope="portfolio",
                severity="warning",
                alert_type="lifecycle_burden_increase",
                message=(
                    f"Lifecycle attention/needs_review count "
                    f"increased by {lc_delta}."
                ),
                metric_name="lifecycle_burden_count",
                previous_value=str(prev_att + prev_nr),
                current_value=str(curr_att + curr_nr),
                delta_value=str(lc_delta),
                source_pack_file=source,
                generated_at=generated_at,
                recommended_local_action=(
                    "Review properties with worsening "
                    "lifecycle health."
                ),
            ))

        # Worsening cross-site confidence trend
        prev_cs = prev.avg_cross_site_confidence
        curr_cs = latest.avg_cross_site_confidence
        if prev_cs is not None and curr_cs is not None:
            cs_delta = curr_cs - prev_cs
            if cs_delta <= -15:
                alerts.append(PortfolioTrendAlert(
                    alert_id="avg_confidence_drop",
                    alert_scope="portfolio",
                    severity="warning",
                    alert_type="cross_site_confidence_drop",
                    message=(
                        f"Avg cross-site confidence dropped "
                        f"by {abs(cs_delta):.1f} "
                        f"(from {prev_cs:.1f} to "
                        f"{curr_cs:.1f})."
                    ),
                    metric_name="avg_cross_site_confidence",
                    previous_value=f"{prev_cs:.1f}",
                    current_value=f"{curr_cs:.1f}",
                    delta_value=f"{cs_delta:.1f}",
                    source_pack_file=source,
                    generated_at=generated_at,
                    recommended_local_action=(
                        "Investigate cross-site confidence "
                        "decline."
                    ),
                ))

        # High churn trend
        prev_hc = prev.high_churn_count
        curr_hc = latest.high_churn_count
        hc_delta = curr_hc - prev_hc
        if hc_delta >= 2:
            alerts.append(PortfolioTrendAlert(
                alert_id="high_churn_increase",
                alert_scope="portfolio",
                severity="warning",
                alert_type="high_churn_trend",
                message=(
                    f"High churn property count increased by "
                    f"{hc_delta} (from {prev_hc} to "
                    f"{curr_hc})."
                ),
                metric_name="high_churn_count",
                previous_value=str(prev_hc),
                current_value=str(curr_hc),
                delta_value=str(hc_delta),
                source_pack_file=source,
                generated_at=generated_at,
                recommended_local_action=(
                    "Review properties with high churn."
                ),
            ))

    return alerts


def evaluate_property_trend_alerts(
    property_points: list,
    generated_at: str,
) -> List[PortfolioTrendAlert]:
    """Evaluate property-level trend threshold alerts.

    Args:
        property_points: Per-property trend points from M42.
        generated_at: Timestamp for alert generation.

    Returns:
        List of triggered PortfolioTrendAlert instances.
    """
    alerts: List[PortfolioTrendAlert] = []

    for pt in property_points:
        base_id = f"prop_{pt.property_id}"

        # Property trend degraded
        if pt.trend_direction == "degraded":
            alerts.append(PortfolioTrendAlert(
                alert_id=f"{base_id}_degraded",
                alert_scope="property",
                property_id=str(pt.property_id),
                candidate_id=str(pt.candidate_id),
                address=pt.address,
                severity="warning",
                alert_type="property_trend_degraded",
                message=(
                    f"{pt.address}: trend direction is "
                    f"degraded. {pt.trend_summary}"
                ),
                metric_name="trend_direction",
                current_value="degraded",
                recommended_local_action=(
                    pt.recommended_review_action
                    or "Review property trend details."
                ),
                generated_at=generated_at,
            ))

        # Lifecycle health score drop >= 15
        d = pt.lifecycle_health_score_delta_first_to_latest
        if d is not None and d <= -15:
            alerts.append(PortfolioTrendAlert(
                alert_id=f"{base_id}_health_drop",
                alert_scope="property",
                property_id=str(pt.property_id),
                candidate_id=str(pt.candidate_id),
                address=pt.address,
                severity="warning",
                alert_type="lifecycle_health_drop",
                message=(
                    f"{pt.address}: lifecycle health score "
                    f"decreased by {abs(d):.1f}."
                ),
                metric_name="lifecycle_health_score_delta",
                current_value=(
                    str(pt.latest_lifecycle_health_score)
                    if pt.latest_lifecycle_health_score
                    is not None else ""
                ),
                delta_value=f"{d:.1f}",
                recommended_local_action=(
                    "Review lifecycle health factors."
                ),
                generated_at=generated_at,
            ))

        # Lifecycle label worsening
        lbl = pt.latest_lifecycle_health_label
        if (
            lbl in ("needs_review", "attention_required")
            and pt.lifecycle_health_label_changes > 0
        ):
            alerts.append(PortfolioTrendAlert(
                alert_id=f"{base_id}_health_label",
                alert_scope="property",
                property_id=str(pt.property_id),
                candidate_id=str(pt.candidate_id),
                address=pt.address,
                severity="high",
                alert_type="lifecycle_label_worsening",
                message=(
                    f"{pt.address}: lifecycle health label "
                    f"is {lbl} (changed "
                    f"{pt.lifecycle_health_label_changes}x)."
                ),
                metric_name="lifecycle_health_label",
                current_value=lbl,
                recommended_local_action=(
                    "Prioritize lifecycle health review."
                ),
                generated_at=generated_at,
            ))

        # Open alert count increase >= 2
        if pt.open_alert_delta_first_to_latest >= 2:
            alerts.append(PortfolioTrendAlert(
                alert_id=f"{base_id}_alert_increase",
                alert_scope="property",
                property_id=str(pt.property_id),
                candidate_id=str(pt.candidate_id),
                address=pt.address,
                severity="warning",
                alert_type="open_alert_increase",
                message=(
                    f"{pt.address}: open alert count "
                    f"increased by "
                    f"{pt.open_alert_delta_first_to_latest}."
                ),
                metric_name="open_alert_delta",
                current_value=str(pt.latest_open_alert_count),
                delta_value=str(
                    pt.open_alert_delta_first_to_latest
                ),
                recommended_local_action=(
                    "Review new open alerts."
                ),
                generated_at=generated_at,
            ))

        # Cross-site confidence drop >= 15
        cd = pt.cross_site_confidence_delta_first_to_latest
        if cd is not None and cd <= -15:
            alerts.append(PortfolioTrendAlert(
                alert_id=f"{base_id}_confidence_drop",
                alert_scope="property",
                property_id=str(pt.property_id),
                candidate_id=str(pt.candidate_id),
                address=pt.address,
                severity="warning",
                alert_type="cross_site_confidence_drop",
                message=(
                    f"{pt.address}: cross-site confidence "
                    f"decreased by {abs(cd):.1f}."
                ),
                metric_name="cross_site_confidence_delta",
                current_value=(
                    f"{pt.latest_cross_site_confidence:.1f}"
                    if pt.latest_cross_site_confidence
                    is not None else ""
                ),
                delta_value=f"{cd:.1f}",
                recommended_local_action=(
                    "Investigate cross-site confidence "
                    "decline."
                ),
                generated_at=generated_at,
            ))

        # Churn Index increase >= 1.5
        chi = pt.churn_index_delta_first_to_latest
        if chi is not None and chi >= 1.5:
            alerts.append(PortfolioTrendAlert(
                alert_id=f"{base_id}_churn_increase",
                alert_scope="property",
                property_id=str(pt.property_id),
                candidate_id=str(pt.candidate_id),
                address=pt.address,
                severity="warning",
                alert_type="churn_index_increase",
                message=(
                    f"{pt.address}: Churn Index increased "
                    f"by {chi:.2f}."
                ),
                metric_name="churn_index_delta",
                current_value=(
                    f"{pt.latest_recent_churn_index:.2f}"
                    if pt.latest_recent_churn_index
                    is not None else ""
                ),
                delta_value=f"{chi:.2f}",
                recommended_local_action=(
                    "Review listing churn history."
                ),
                generated_at=generated_at,
            ))

        # Effective DOM v2 increase >= 30
        dd = pt.effective_dom_v2_delta_first_to_latest
        if dd is not None and dd >= 30:
            alerts.append(PortfolioTrendAlert(
                alert_id=f"{base_id}_dom_increase",
                alert_scope="property",
                property_id=str(pt.property_id),
                candidate_id=str(pt.candidate_id),
                address=pt.address,
                severity="info",
                alert_type="effective_dom_v2_increase",
                message=(
                    f"{pt.address}: Effective DOM v2 "
                    f"increased by {dd} days."
                ),
                metric_name="effective_dom_v2_delta",
                current_value=(
                    str(pt.latest_effective_dom_v2)
                    if pt.latest_effective_dom_v2
                    is not None else ""
                ),
                delta_value=str(dd),
                recommended_local_action=(
                    "Note extended market exposure."
                ),
                generated_at=generated_at,
            ))

    return alerts


def summarize_portfolio_trend_alerts(
    alerts: List[PortfolioTrendAlert],
) -> PortfolioTrendAlertSummary:
    """Summarize trend alerts by severity.

    Args:
        alerts: List of triggered alerts.

    Returns:
        PortfolioTrendAlertSummary with counts.
    """
    summary = PortfolioTrendAlertSummary(
        total_alerts=len(alerts),
    )
    for a in alerts:
        if a.severity == "info":
            summary.info_count += 1
        elif a.severity == "warning":
            summary.warning_count += 1
        elif a.severity == "high":
            summary.high_count += 1
    return summary


def export_portfolio_trend_alert_digest(
    exports_dir: str = "data/exports",
    output_dir: str = "data/exports",
    fmt: str = "both",
    rule_config: Optional[Union[Path, str]] = None,
) -> PortfolioTrendAlertRunResult:
    """Evaluate trend alerts and export digest.

    Args:
        exports_dir: Directory with review pack CSV exports.
        output_dir: Directory for output digest files.
        fmt: Export format: csv, md, or both.
        rule_config: Optional path to custom rule config JSON.

    Returns:
        PortfolioTrendAlertRunResult with paths and summary.
    """
    result = PortfolioTrendAlertRunResult()

    digest = evaluate_portfolio_trend_alerts(
        exports_dir, rule_config=rule_config,
    )
    result.alert_count = len(digest.alerts)
    result.summary = digest.summary

    if not digest.alerts:
        result.warnings.append("No trend alerts triggered.")
        return result

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if fmt in ("csv", "both"):
        csv_path = os.path.join(
            output_dir,
            f"portfolio_trend_alert_digest_{ts}.csv",
        )
        _write_alert_csv(csv_path, digest)
        result.export_paths.append(csv_path)

    if fmt in ("md", "both"):
        md_path = os.path.join(
            output_dir,
            f"portfolio_trend_alert_digest_{ts}.md",
        )
        _write_alert_md(md_path, digest)
        result.export_paths.append(md_path)

    return result


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

def _write_alert_csv(
    path: str,
    digest: PortfolioTrendAlertDigest,
) -> None:
    """Write alert digest to CSV.

    Args:
        path: Output CSV file path.
        digest: Alert digest to write.
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=ALERT_DIGEST_CSV_FIELDNAMES
        )
        writer.writeheader()
        for a in digest.alerts:
            writer.writerow({
                "alert_id": a.alert_id,
                "alert_scope": a.alert_scope,
                "property_id": a.property_id,
                "candidate_id": a.candidate_id,
                "address": a.address,
                "severity": a.severity,
                "alert_type": a.alert_type,
                "message": a.message,
                "metric_name": a.metric_name,
                "previous_value": a.previous_value,
                "current_value": a.current_value,
                "delta_value": a.delta_value,
                "recommended_local_action":
                    a.recommended_local_action,
                "source_pack_file": a.source_pack_file,
                "generated_at": a.generated_at,
            })


# ---------------------------------------------------------------------------
# Markdown writer
# ---------------------------------------------------------------------------

def _write_alert_md(
    path: str,
    digest: PortfolioTrendAlertDigest,
) -> None:
    """Write alert digest to Markdown.

    Args:
        path: Output Markdown file path.
        digest: Alert digest to write.
    """
    lines: List[str] = []
    s = digest.summary

    lines.append(
        "# Portfolio Trend Alert Digest"
    )
    lines.append("")
    lines.append(f"Generated: {digest.generated_at}")
    lines.append("")

    # Safety note
    lines.append(
        "*This alert digest is a local analytical review aid. "
        "It does not make purchase recommendations, infer seller "
        "intent, or mutate candidate/watchlist/alert state. "
        "No outbound notifications are sent.*"
    )
    lines.append("")

    # Summary
    lines.append("## Alert Summary")
    lines.append("")
    lines.append(f"Total alerts: {s.total_alerts}")
    lines.append(f"High: {s.high_count}")
    lines.append(f"Warning: {s.warning_count}")
    lines.append(f"Info: {s.info_count}")
    if s.pack_count:
        lines.append(
            f"Packs analyzed: {s.pack_count} "
            f"({s.first_pack_date} to {s.latest_pack_date})"
        )
    lines.append("")

    # Aggregate portfolio alerts
    agg_alerts = [
        a for a in digest.alerts if a.alert_scope == "portfolio"
    ]
    if agg_alerts:
        lines.append("## Aggregate Portfolio Trend Alerts")
        lines.append("")
        lines.append(
            "| Severity | Type | Message | Action |"
        )
        lines.append("| --- | --- | --- | --- |")
        for a in agg_alerts:
            lines.append(
                f"| {a.severity}"
                f" | {a.alert_type}"
                f" | {a.message[:80]}"
                f" | {a.recommended_local_action[:60]} |"
            )
        lines.append("")

    # Property-level alerts
    prop_alerts = [
        a for a in digest.alerts if a.alert_scope == "property"
    ]
    if prop_alerts:
        lines.append("## Property-Level Trend Alerts")
        lines.append("")
        lines.append(
            "| Severity | Address | Type | Message | Action |"
        )
        lines.append("| --- | --- | --- | --- | --- |")
        for a in prop_alerts[:30]:
            lines.append(
                f"| {a.severity}"
                f" | {a.address}"
                f" | {a.alert_type}"
                f" | {a.message[:60]}"
                f" | {a.recommended_local_action[:50]} |"
            )
        lines.append("")

    # Recommended local review actions
    actionable = [
        a for a in digest.alerts
        if a.recommended_local_action
        and a.severity in ("warning", "high")
    ]
    if actionable:
        lines.append("## Recommended Local Review Actions")
        lines.append("")
        for a in actionable[:15]:
            prefix = (
                f"{a.address}: " if a.address else "Portfolio: "
            )
            lines.append(
                f"- **{prefix}** [{a.severity}] "
                f"{a.recommended_local_action}"
            )
        lines.append("")

    # Source pack files
    if digest.source_pack_files:
        lines.append("## Source Pack Files Analyzed")
        lines.append("")
        for fp in digest.source_pack_files:
            lines.append(f"- {fp}")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(
        "*No outbound notifications were sent. "
        "This digest is for local review only.*"
    )
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
