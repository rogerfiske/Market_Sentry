# Portfolio Alert Focus Preferences

This document describes the local alert highlight preferences and dashboard focus views introduced in Milestone 46.

## Overview

Portfolio alert focus preferences let operators configure which alert categories should be emphasized in reports and dashboard views. Preferences are local display settings only and do not change alert evaluation, history, candidate/watchlist/alert state, or trigger outbound notifications.

## Config File Path

The default config file path is:

```
config/portfolio_alert_highlight_preferences.json
```

This file is optional. If absent, safe default preferences are used.

An example template is available at:

```
config/portfolio_alert_highlight_preferences.example.json
```

## Config Schema

```json
{
  "profile_name": "default_focus",
  "description": "Local display preferences for portfolio trend alert focus views.",
  "include_severities": ["high", "warning"],
  "exclude_severities": ["info"],
  "include_alert_types": [
    "aggregate_burden_high",
    "aggregate_burden_increase",
    "property_degraded",
    "lifecycle_health_drop",
    "cross_site_confidence_drop",
    "churn_increase"
  ],
  "exclude_alert_types": [],
  "minimum_persistence_count": 1,
  "include_persistent_only": false,
  "include_property_alerts": true,
  "include_portfolio_alerts": true,
  "max_items": 25,
  "sort_order": "severity_then_persistence",
  "notes": "Local display preferences only. No notifications are sent."
}
```

## Fields and Validation

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| profile_name | Yes | string | Name for this focus profile |
| description | No | string | Human-readable description |
| include_severities | No | list of string | Only include alerts with these severities |
| exclude_severities | No | list of string | Exclude alerts with these severities |
| include_alert_types | No | list of string | Only include these alert types (empty = all) |
| exclude_alert_types | No | list of string | Exclude these alert types |
| minimum_persistence_count | No | integer >= 0 | Minimum persistence count for history items |
| include_persistent_only | No | boolean | Only include alerts seen in 2+ runs |
| include_property_alerts | No | boolean | Include property-scope alerts |
| include_portfolio_alerts | No | boolean | Include portfolio-scope alerts |
| max_items | No | integer >= 1 | Maximum focus items to return |
| sort_order | No | string | Sort order for results |
| notes | No | string | Free-text notes |

### Allowed Severities

- info
- warning
- high

### Allowed Sort Orders

| Value | Behavior |
|-------|----------|
| severity_then_persistence | Sort by severity (high first), then by persistence count |
| persistence_then_severity | Sort by persistence count (most persistent first), then severity |
| newest_first | Sort by latest_seen_at descending |
| property_then_severity | Sort by address, then severity |

### Validation Rules

- `profile_name` is required and must be non-empty
- `include_severities` and `exclude_severities` values must be valid severity strings
- `include_alert_types` and `exclude_alert_types` values must be strings
- `max_items` must be a positive integer
- `minimum_persistence_count` must be a non-negative integer
- `sort_order` must be one of the allowed sort orders
- Config must not contain forbidden keys (live_retrieval, scrape, playwright, selenium, captcha, notification, email, sms, webhook, walkability, walk_score, transit_score)
- Invalid configs fail safely with clear error messages

## CLI Examples

### Generate a template

```bash
marketsentry write-portfolio-alert-focus-template
marketsentry write-portfolio-alert-focus-template --output config/my_focus.json
marketsentry write-portfolio-alert-focus-template --overwrite
```

### Validate a config

```bash
marketsentry validate-portfolio-alert-focus-config --preference-config config/portfolio_alert_highlight_preferences.json
```

### View focused alerts

```bash
marketsentry portfolio-alert-focus
marketsentry portfolio-alert-focus --preference-config config/portfolio_alert_highlight_preferences.json --limit 10
marketsentry portfolio-alert-focus --db data/market_sentry.db --exports-dir data/exports
```

### Export focus digest

```bash
marketsentry export-portfolio-alert-focus-digest --format both
marketsentry export-portfolio-alert-focus-digest --preference-config config/portfolio_alert_highlight_preferences.json --format csv
marketsentry export-portfolio-alert-focus-digest --output-dir data/exports --format md
```

## Dashboard Behavior

The Streamlit dashboard includes a **Portfolio Alert Focus View** subsection that shows:

- Active focus profile name
- Config validation status
- Focus item count
- Severity counts (high, warning, info)
- Scope counts (portfolio, property)
- Focus item table with severity, address, type, persistence, trend, reason, and source
- Latest focus digest report link

The dashboard remains read-only.

## Input Sources

Focus items are built from:

1. **Alert history database** (Milestone 45): If a database with persisted alert history is available, focus items include persistence counts, trend states, and run counts.
2. **Trend alert digest CSV** (Milestone 43): If no history is available, focus items are loaded from the latest `portfolio_trend_alert_digest_*.csv` file.

## Safety Limitations

- Focus preferences are local display preferences only
- Preferences do not change alert evaluation or history
- Preferences do not mutate candidate, watchlist, or alert state
- No outbound notifications are sent (email, SMS, webhook)
- No database writes are performed
- No live retrieval is performed
- No Redfin source-of-truth fields are overwritten
- No Quiet Score gatekeeper modifications
- No walkability fields are referenced
- No browser automation is used
- Invalid configs do not break default commands unless explicitly supplied
