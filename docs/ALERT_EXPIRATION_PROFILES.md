# Alert Expiration Profiles

This document describes built-in and user-defined alert expiration profiles for the Market Sentry cross-site alert lifecycle.

## Overview

Expiration profiles define age-based rules that identify alerts eligible for archive, review, or keep actions. Profiles generate preview candidates only; all mutations require explicit operator approval via CSV import.

## Built-In Profiles

Three built-in profiles are always available:

### conservative

Long thresholds. Archive resolved after 90 days.

| Rule | Status | Severity | Age (days) | Action |
|------|--------|----------|------------|--------|
| resolved_archive_90d | resolved | any | 90 | archive |
| acknowledged_review_45d | acknowledged | any | 45 | review |
| open_info_warning_review_30d | open | info,warning | 30 | review |
| open_high_critical_review_only | open | high,critical | 0 | review |

### standard

Balanced thresholds. Archive resolved after 60 days.

| Rule | Status | Severity | Age (days) | Action |
|------|--------|----------|------------|--------|
| resolved_archive_60d | resolved | any | 60 | archive |
| acknowledged_review_30d | acknowledged | any | 30 | review |
| open_info_warning_review_21d | open | info,warning | 21 | review |
| open_high_critical_review_only | open | high,critical | 0 | review |

### aggressive_review_only

Short thresholds. Archive resolved after 30 days.

| Rule | Status | Severity | Age (days) | Action |
|------|--------|----------|------------|--------|
| resolved_archive_30d | resolved | any | 30 | archive |
| acknowledged_review_14d | acknowledged | any | 14 | review |
| open_info_warning_review_14d | open | info,warning | 14 | review |
| open_high_critical_review_only | open | high,critical | 0 | review |

## Custom Config Format

Custom profiles are defined in a JSON config file. The default path is:

```
config/alert_expiration_profiles.json
```

This file is optional. If absent, only built-in profiles are available.

### Example Config

```json
{
  "profiles": [
    {
      "profile_name": "my_custom_review",
      "description": "Custom local review profile",
      "rules": [
        {
          "rule_name": "resolved_archive_75d",
          "current_status": "resolved",
          "severity": ["info", "warning", "high", "critical"],
          "min_age_days": 75,
          "proposed_action": "archive",
          "exclude_no_archive": true
        },
        {
          "rule_name": "acknowledged_review_21d",
          "current_status": "acknowledged",
          "severity": ["info", "warning", "high", "critical"],
          "min_age_days": 21,
          "proposed_action": "review",
          "exclude_no_archive": false
        }
      ]
    }
  ]
}
```

### Profile Fields

| Field | Required | Description |
|-------|----------|-------------|
| profile_name | Yes | Unique name (lowercase/snake_case recommended) |
| description | No | Human-readable description |
| rules | Yes | List of rule objects |

### Rule Fields

| Field | Required | Description |
|-------|----------|-------------|
| rule_name | Yes | Unique within profile |
| current_status | Yes | open, acknowledged, resolved, or archived |
| severity | No | String or list: info, warning, high, critical, any |
| min_age_days | Yes | Integer >= 0 |
| proposed_action | Yes | archive, review, keep, or reopen_review |
| exclude_no_archive | No | Boolean (informational) |

## Validation Rules

- `profile_name` is required and must be unique
- `rule_name` is required and must be unique within its profile
- `min_age_days` must be an integer >= 0
- High/critical open alerts may only propose `review` or `keep`
- Archived alerts may only propose `keep` or `review`
- No rules may propose deleting anything
- No rule may change watchlist status
- User profiles cannot silently override built-in profile names
- Invalid configs are rejected with clear error messages
- Invalid configs do not break built-in profiles

## CLI Commands

### List all profiles (built-in and custom)

```bash
marketsentry list-cross-site-alert-expiration-profiles
marketsentry list-cross-site-alert-expiration-profiles --profile-config config/alert_expiration_profiles.json
```

### Write example config template

```bash
marketsentry write-alert-expiration-profile-template
marketsentry write-alert-expiration-profile-template --output config/my_profiles.json
marketsentry write-alert-expiration-profile-template --overwrite
```

### Preview policy using custom profile

```bash
marketsentry preview-cross-site-alert-expiration-policy --profile my_custom_review --profile-config config/alert_expiration_profiles.json
```

### Export approval CSV using custom profile

```bash
marketsentry export-cross-site-alert-expiration-approval --profile my_custom_review --profile-config config/alert_expiration_profiles.json
```

### Summary using custom profile

```bash
marketsentry cross-site-alert-expiration-summary --profile my_custom_review --profile-config config/alert_expiration_profiles.json
```

### Import approval CSV (unchanged)

```bash
marketsentry import-cross-site-alert-expiration-approval --file data/exports/cross_site_alert_expiration_approval_YYYYMMDD_HHMMSS.csv
```

## Safety Limits

- Custom profiles generate candidates only; no actions are applied automatically
- All mutations require explicit operator approval via CSV import
- High/critical open alerts are always review-only across all profiles
- `[no_archive]` marked alerts are excluded from archive proposals at runtime
- User profiles cannot silently override built-in profiles
- Invalid configs fail safely without breaking built-in profiles
- Expiration policy does not change watchlist status
- Expiration policy does not overwrite Redfin source-of-truth fields
- Quiet Score gatekeeper is unchanged
- No live retrieval is triggered

## No Auto-Apply Behavior

No scheduled task, background process, or automated workflow applies expiration decisions from custom profiles. The import command is the only way to apply decisions, and it requires an explicit file path and operator-edited approval CSV.
