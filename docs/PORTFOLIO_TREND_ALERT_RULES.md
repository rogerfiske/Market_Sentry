# Portfolio Trend Alert Rules

This document describes the configurable portfolio trend alert rule system introduced in Milestone 44.

## Overview

Portfolio trend alert rules define threshold conditions that flag significant changes in portfolio and property trend metrics. Rules can be built-in (always available) or user-defined via a JSON config file.

## Built-In Rules

The following rules are always available and active unless replaced by a custom config in `replace` mode:

### Aggregate Portfolio Rules

| Rule ID | Metric | Threshold | Severity | Description |
|---------|--------|-----------|----------|-------------|
| burden_high_80 | aggregate_review_burden_score | >= 80 | high | Aggregate burden score high |
| burden_warning_60 | aggregate_review_burden_score | >= 60 | warning | Aggregate burden score warning |
| burden_increase_15 | aggregate_burden_delta | >= 15 | warning | Burden increased significantly |
| burden_label_worsening | aggregate_review_status_label | label change | warning/high | Burden label worsened |
| immediate_review_increase | immediate_review_count | increased | warning | Immediate review backlog grew |
| high_review_increase_2 | high_review_count | >= 2 increase | warning | High review backlog grew |

### Property Rules

| Rule ID | Metric | Threshold | Severity | Description |
|---------|--------|-----------|----------|-------------|
| property_degraded | trend_direction | degraded | warning | Property trend direction degraded |
| health_score_drop_15 | lifecycle_health_score_delta | <= -15 | warning | Health score dropped significantly |
| health_label_attention | lifecycle_health_label | needs_review/attention_required | high | Health label worsened |
| open_alert_increase_2 | open_alert_delta | >= 2 | warning | Open alert count increased |
| confidence_drop_15 | cross_site_confidence_delta | <= -15 | warning | Cross-site confidence dropped |
| churn_increase_1_5 | churn_index_delta | >= 1.5 | warning | Churn Index increased |
| dom_v2_increase_30 | effective_dom_v2_delta | >= 30 | info | Effective DOM v2 increased |

## Config File Path

The default config file path is:

```
config/portfolio_trend_alert_rules.json
```

This file is optional. If absent, only built-in rules are used.

## Config Schema

```json
{
  "mode": "merge",
  "rules": [
    {
      "rule_id": "custom_rule_id",
      "rule_name": "Human-readable rule name",
      "scope": "portfolio",
      "metric_name": "aggregate_review_burden_score",
      "threshold_value": 75,
      "comparison": ">=",
      "severity": "high",
      "enabled": true,
      "message_template": "Burden is {current_value}, threshold {threshold_value}",
      "recommended_local_action": "Review burden contributors"
    }
  ]
}
```

### Mode

| Value | Behavior |
|-------|----------|
| merge | Custom rules are appended after built-in rules |
| replace | Only custom rules are used (built-ins excluded) |

Default: `merge`

### Rule Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| rule_id | Yes | string | Unique identifier. Must not match a built-in rule ID. |
| rule_name | Yes | string | Human-readable name |
| scope | Yes | string | `portfolio` or `property` |
| metric_name | Yes | string | Metric to evaluate |
| threshold_value | No | number | Numeric threshold (default 0.0) |
| comparison | Yes | string | Comparison operator |
| severity | Yes | string | `info`, `warning`, or `high` |
| enabled | No | boolean | Whether to evaluate (default true) |
| message_template | No | string | Template with {current_value}, {threshold_value}, {previous_value}, {delta_value} |
| recommended_local_action | No | string | Suggested action text |

### Comparison Operators

| Operator | Description |
|----------|-------------|
| >= | Current value >= threshold |
| > | Current value > threshold |
| <= | Current value <= threshold |
| < | Current value < threshold |
| == | Current value equals threshold |
| != | Current value does not equal threshold |
| delta>= | Delta (current - previous) >= threshold |
| delta<= | Delta (current - previous) <= threshold |

## Validation Rules

- `rule_id` must be present and unique within the config
- `rule_id` must not match any built-in rule ID
- `rule_name` must be present
- `scope` must be `portfolio` or `property`
- `comparison` must be one of the allowed operators
- `severity` must be `info`, `warning`, or `high`
- `threshold_value` must be numeric when present
- `enabled` must be true or false when present
- Metric names must not reference walkability (walkability, walk_score, transit_score)
- Metric names must not reference live retrieval (live_retrieval, scrape, playwright, selenium)
- Invalid configs fail with clear error messages
- Disabled rules are valid but not evaluated

## CLI Examples

### Generate a template

```bash
marketsentry write-portfolio-trend-alert-rule-template
marketsentry write-portfolio-trend-alert-rule-template --output config/my_rules.json
marketsentry write-portfolio-trend-alert-rule-template --overwrite
```

### Validate a config

```bash
marketsentry validate-portfolio-trend-alert-rules --rule-config config/portfolio_trend_alert_rules.json
```

### List active rules

```bash
marketsentry list-portfolio-trend-alert-rules
marketsentry list-portfolio-trend-alert-rules --rule-config config/portfolio_trend_alert_rules.json
```

### Use custom rules

```bash
marketsentry portfolio-trend-alerts --rule-config config/portfolio_trend_alert_rules.json
marketsentry export-portfolio-trend-alert-digest --rule-config config/portfolio_trend_alert_rules.json --format both
```

## Safety Limitations

- Configurable rules are local review prompts only
- Rules do not mutate candidate, watchlist, or alert state
- Rules do not trigger outbound notifications (email, SMS, webhook)
- Rules do not overwrite Redfin source-of-truth fields
- Rules do not modify the Quiet Score gatekeeper
- Walkability and live retrieval metrics are rejected
- Built-in rule IDs cannot be overridden by user config
- Invalid configs do not break default commands unless explicitly supplied

## Alert History (Milestone 45)

Evaluated alerts can be persisted locally as append-only history using:

```bash
marketsentry persist-portfolio-trend-alerts
```

This creates one run row and one history row per alert. History enables comparison of current vs. previous runs to identify new, persistent, disappeared, worsened, and improved alerts. History is append-only and does not mutate candidate, watchlist, or alert state.
