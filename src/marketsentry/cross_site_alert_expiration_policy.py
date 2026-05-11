"""Configurable alert expiration rules and operator approval gates.

Defines local expiration profiles with age-based rules that identify
alerts eligible for archive, review, or keep actions. All mutations
require explicit operator approval via CSV import. No actions are
applied automatically.

This module does not change watchlist status, overwrite Redfin
source-of-truth fields, modify Quiet Score gatekeeper results,
or infer seller intent. Reports are operational review aids,
not purchase recommendations.
"""

import csv
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from marketsentry.database import execute_query, get_connection, table_exists
from marketsentry.logging_config import logger
from marketsentry.models import (
    CrossSiteAlertExpirationApplyResult,
    CrossSiteAlertExpirationApprovalRow,
    CrossSiteAlertExpirationCandidate,
    CrossSiteAlertExpirationPreviewResult,
    CrossSiteAlertExpirationProfile,
    CrossSiteAlertExpirationRule,
    CrossSiteAlertExpirationSummary,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPIRATION_CSV_FIELDNAMES = [
    "expiration_export_id",
    "profile_name",
    "rule_name",
    "alert_id",
    "property_id",
    "candidate_id",
    "address",
    "city",
    "zip",
    "alert_type",
    "severity",
    "current_status",
    "alert_age_days",
    "proposed_action",
    "proposed_reason",
    "current_notes",
    "approval_decision",
    "approval_notes",
]

ALLOWED_APPROVAL_DECISIONS = frozenset({
    "approve_action",
    "keep_current",
    "mark_no_archive",
    "reopen",
    "acknowledge",
    "resolve",
    "archive",
})

_STATUS_CHANGING_DECISIONS = {
    "reopen": "open",
    "acknowledge": "acknowledged",
    "resolve": "resolved",
    "archive": "archived",
}

_PROPOSED_ACTION_TO_STATUS = {
    "archive": "archived",
    "reopen_review": "open",
}

ALLOWED_STATUSES = frozenset({"open", "acknowledged", "resolved", "archived"})
ALLOWED_SEVERITIES = frozenset({
    "info", "warning", "high", "critical", "any",
})
ALLOWED_PROPOSED_ACTIONS = frozenset({
    "archive", "review", "keep", "reopen_review",
})

DEFAULT_CONFIG_PATH = Path("config/alert_expiration_profiles.json")
EXAMPLE_CONFIG_PATH = Path("config/alert_expiration_profiles.example.json")

_BUILTIN_PROFILE_NAMES = frozenset({
    "conservative", "standard", "aggressive_review_only",
})

EXAMPLE_PROFILE_CONFIG = {
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
                    "exclude_no_archive": True,
                },
                {
                    "rule_name": "acknowledged_review_21d",
                    "current_status": "acknowledged",
                    "severity": ["info", "warning", "high", "critical"],
                    "min_age_days": 21,
                    "proposed_action": "review",
                    "exclude_no_archive": False,
                },
            ],
        }
    ]
}


# ---------------------------------------------------------------------------
# User-defined profile loading (Milestone 32)
# ---------------------------------------------------------------------------


def load_user_expiration_profiles(
    config_path: Optional[Union[Path, str]] = None,
) -> Tuple[List[CrossSiteAlertExpirationProfile], List[str]]:
    """Load user-defined expiration profiles from a JSON config file.

    If the config file does not exist, returns empty lists.
    If the config is invalid, returns empty profiles and error messages.

    Args:
        config_path: Path to the JSON config. Defaults to
            config/alert_expiration_profiles.json.

    Returns:
        Tuple of (profiles, errors). Errors are empty on success.
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        return [], []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [], [f"Invalid JSON in {path}: {e}"]
    except Exception as e:
        return [], [f"Error reading {path}: {e}"]

    if not isinstance(data, dict) or "profiles" not in data:
        return [], [f"Config must have a 'profiles' key: {path}"]

    raw_profiles = data["profiles"]
    if not isinstance(raw_profiles, list):
        return [], [f"'profiles' must be a list: {path}"]

    profiles: List[CrossSiteAlertExpirationProfile] = []
    errors: List[str] = []
    seen_names: set = set()

    for idx, raw in enumerate(raw_profiles):
        profile, profile_errors = _parse_profile(raw, idx, seen_names)
        if profile_errors:
            errors.extend(profile_errors)
        elif profile is not None:
            seen_names.add(profile.profile_name)
            profiles.append(profile)

    return profiles, errors


def validate_expiration_profile_config(
    config_path: Optional[Union[Path, str]] = None,
) -> Tuple[bool, List[str]]:
    """Validate a user-defined profile config file.

    Args:
        config_path: Path to the config file.

    Returns:
        Tuple of (is_valid, error_messages).
    """
    profiles, errors = load_user_expiration_profiles(config_path)
    if errors:
        return False, errors

    # Check for builtin name conflicts
    for p in profiles:
        if p.profile_name in _BUILTIN_PROFILE_NAMES:
            errors.append(
                f"Profile '{p.profile_name}' conflicts with built-in profile"
            )

    return len(errors) == 0, errors


def merge_builtin_and_user_profiles(
    config_path: Optional[Union[Path, str]] = None,
) -> Tuple[List[CrossSiteAlertExpirationProfile], List[str]]:
    """Merge built-in and user-defined profiles.

    Built-in profiles are always included. User profiles are added
    if the config file exists and is valid. User profiles that conflict
    with built-in names are rejected.

    Args:
        config_path: Path to the user config file.

    Returns:
        Tuple of (merged_profiles, errors).
    """
    builtin = get_default_expiration_profiles()
    user_profiles, errors = load_user_expiration_profiles(config_path)

    # Reject user profiles that conflict with built-in names
    valid_user: List[CrossSiteAlertExpirationProfile] = []
    for p in user_profiles:
        if p.profile_name in _BUILTIN_PROFILE_NAMES:
            errors.append(
                f"User profile '{p.profile_name}' conflicts with "
                f"built-in profile; skipped"
            )
        else:
            valid_user.append(p)

    return builtin + valid_user, errors


def get_expiration_profile_by_name(
    profile_name: str,
    config_path: Optional[Union[Path, str]] = None,
) -> Optional[CrossSiteAlertExpirationProfile]:
    """Get a profile by name from built-in and user-defined profiles.

    Args:
        profile_name: Name of the profile to find.
        config_path: Optional path to user config.

    Returns:
        The profile if found, or None.
    """
    merged, _ = merge_builtin_and_user_profiles(config_path)
    for p in merged:
        if p.profile_name == profile_name:
            return p
    return None


def write_example_expiration_profile_config(
    output_path: Optional[Union[Path, str]] = None,
    overwrite: bool = False,
) -> Tuple[str, bool]:
    """Write an example expiration profile config file.

    Args:
        output_path: Output path. Defaults to
            config/alert_expiration_profiles.example.json.
        overwrite: Whether to overwrite existing file.

    Returns:
        Tuple of (path_written, was_written).
    """
    path = Path(output_path) if output_path else EXAMPLE_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and not overwrite:
        return str(path), False

    with open(path, "w", encoding="utf-8") as f:
        json.dump(EXAMPLE_PROFILE_CONFIG, f, indent=2)
        f.write("\n")

    return str(path), True


def _parse_profile(
    raw: dict,
    idx: int,
    seen_names: set,
) -> Tuple[Optional[CrossSiteAlertExpirationProfile], List[str]]:
    """Parse and validate a single profile from JSON config.

    Args:
        raw: Raw dict from JSON.
        idx: Profile index for error messages.
        seen_names: Set of already-seen profile names.

    Returns:
        Tuple of (profile_or_none, errors).
    """
    errors: List[str] = []

    if not isinstance(raw, dict):
        return None, [f"Profile [{idx}]: must be an object"]

    profile_name = raw.get("profile_name", "").strip()
    if not profile_name:
        return None, [f"Profile [{idx}]: missing profile_name"]

    if profile_name in seen_names:
        return None, [
            f"Profile '{profile_name}': duplicate profile_name"
        ]

    description = raw.get("description", "")
    raw_rules = raw.get("rules", [])
    if not isinstance(raw_rules, list):
        return None, [f"Profile '{profile_name}': rules must be a list"]

    rules: List[CrossSiteAlertExpirationRule] = []
    seen_rule_names: set = set()

    for ridx, raw_rule in enumerate(raw_rules):
        rule, rule_errors = _parse_rule(
            raw_rule, ridx, profile_name, seen_rule_names,
        )
        if rule_errors:
            errors.extend(rule_errors)
        elif rule is not None:
            seen_rule_names.add(rule.rule_name)
            rules.append(rule)

    if errors:
        return None, errors

    return CrossSiteAlertExpirationProfile(
        profile_name=profile_name,
        description=description,
        rules=rules,
    ), []


def _parse_rule(
    raw: dict,
    idx: int,
    profile_name: str,
    seen_names: set,
) -> Tuple[Optional[CrossSiteAlertExpirationRule], List[str]]:
    """Parse and validate a single rule from JSON config.

    Args:
        raw: Raw dict from JSON.
        idx: Rule index for error messages.
        profile_name: Parent profile name for error messages.
        seen_names: Set of already-seen rule names in this profile.

    Returns:
        Tuple of (rule_or_none, errors).
    """
    prefix = f"Profile '{profile_name}' rule [{idx}]"
    errors: List[str] = []

    if not isinstance(raw, dict):
        return None, [f"{prefix}: must be an object"]

    rule_name = raw.get("rule_name", "").strip()
    if not rule_name:
        return None, [f"{prefix}: missing rule_name"]

    if rule_name in seen_names:
        return None, [f"{prefix}: duplicate rule_name '{rule_name}'"]

    current_status = raw.get("current_status", "").strip()
    if current_status not in ALLOWED_STATUSES:
        errors.append(
            f"{prefix} '{rule_name}': invalid current_status "
            f"'{current_status}'"
        )

    # Parse severity
    raw_severity = raw.get("severity", "any")
    if isinstance(raw_severity, list):
        for s in raw_severity:
            if s not in ALLOWED_SEVERITIES:
                errors.append(
                    f"{prefix} '{rule_name}': invalid severity '{s}'"
                )
        if "any" in raw_severity:
            severity_str = None
        else:
            severity_str = ",".join(raw_severity)
    elif isinstance(raw_severity, str):
        if raw_severity == "any":
            severity_str = None
        elif raw_severity in ALLOWED_SEVERITIES:
            severity_str = raw_severity
        else:
            errors.append(
                f"{prefix} '{rule_name}': invalid severity "
                f"'{raw_severity}'"
            )
            severity_str = None
    else:
        errors.append(
            f"{prefix} '{rule_name}': severity must be string or list"
        )
        severity_str = None

    # Parse min_age_days
    min_age = raw.get("min_age_days", 0)
    if not isinstance(min_age, int) or min_age < 0:
        errors.append(
            f"{prefix} '{rule_name}': min_age_days must be integer >= 0"
        )
        min_age = 0

    # Parse proposed_action
    proposed_action = raw.get("proposed_action", "review").strip()
    if proposed_action not in ALLOWED_PROPOSED_ACTIONS:
        errors.append(
            f"{prefix} '{rule_name}': invalid proposed_action "
            f"'{proposed_action}'"
        )

    # Safety: high/critical open alerts may only propose review or keep
    if (
        current_status == "open"
        and severity_str
        and any(
            s in ("high", "critical")
            for s in severity_str.split(",")
        )
        and proposed_action not in ("review", "keep")
    ):
        errors.append(
            f"{prefix} '{rule_name}': high/critical open alerts "
            f"may only propose review or keep, not '{proposed_action}'"
        )

    # Safety: archived alerts may only propose keep or review
    if (
        current_status == "archived"
        and proposed_action not in ("keep", "review")
    ):
        errors.append(
            f"{prefix} '{rule_name}': archived alerts may only "
            f"propose keep or review, not '{proposed_action}'"
        )

    if errors:
        return None, errors

    description = raw.get("description", "")
    if not description:
        description = (
            f"{current_status} alerts aged >={min_age}d -> {proposed_action}"
        )

    return CrossSiteAlertExpirationRule(
        rule_name=rule_name,
        target_status=current_status,
        target_severity=severity_str,
        age_threshold_days=min_age,
        proposed_action=proposed_action,
        description=description,
    ), []


# ---------------------------------------------------------------------------
# Default profiles
# ---------------------------------------------------------------------------


def get_default_expiration_profiles() -> List[CrossSiteAlertExpirationProfile]:
    """Return the built-in expiration rule profiles.

    Three profiles are provided: conservative, standard, and
    aggressive_review_only. Profiles only generate preview/approval
    rows. They never apply actions automatically.

    Returns:
        List of default expiration profiles.
    """
    conservative = CrossSiteAlertExpirationProfile(
        profile_name="conservative",
        description="Long thresholds. Archive resolved after 90 days.",
        rules=[
            CrossSiteAlertExpirationRule(
                rule_name="resolved_archive_90d",
                target_status="resolved",
                age_threshold_days=90,
                proposed_action="archive",
                description="Resolved alerts older than 90 days -> archive candidate",
            ),
            CrossSiteAlertExpirationRule(
                rule_name="acknowledged_review_45d",
                target_status="acknowledged",
                age_threshold_days=45,
                proposed_action="review",
                description="Acknowledged alerts older than 45 days -> review",
            ),
            CrossSiteAlertExpirationRule(
                rule_name="open_info_warning_review_30d",
                target_status="open",
                target_severity="info,warning",
                age_threshold_days=30,
                proposed_action="review",
                description=(
                    "Open info/warning alerts older than 30 days -> review"
                ),
            ),
            CrossSiteAlertExpirationRule(
                rule_name="open_high_critical_review_only",
                target_status="open",
                target_severity="high,critical",
                age_threshold_days=0,
                proposed_action="review",
                description=(
                    "High/critical open alerts -> review only (never archive)"
                ),
            ),
        ],
    )

    standard = CrossSiteAlertExpirationProfile(
        profile_name="standard",
        description="Balanced thresholds. Archive resolved after 60 days.",
        rules=[
            CrossSiteAlertExpirationRule(
                rule_name="resolved_archive_60d",
                target_status="resolved",
                age_threshold_days=60,
                proposed_action="archive",
                description="Resolved alerts older than 60 days -> archive candidate",
            ),
            CrossSiteAlertExpirationRule(
                rule_name="acknowledged_review_30d",
                target_status="acknowledged",
                age_threshold_days=30,
                proposed_action="review",
                description="Acknowledged alerts older than 30 days -> review",
            ),
            CrossSiteAlertExpirationRule(
                rule_name="open_info_warning_review_21d",
                target_status="open",
                target_severity="info,warning",
                age_threshold_days=21,
                proposed_action="review",
                description=(
                    "Open info/warning alerts older than 21 days -> review"
                ),
            ),
            CrossSiteAlertExpirationRule(
                rule_name="open_high_critical_review_only",
                target_status="open",
                target_severity="high,critical",
                age_threshold_days=0,
                proposed_action="review",
                description=(
                    "High/critical open alerts -> review only (never archive)"
                ),
            ),
        ],
    )

    aggressive = CrossSiteAlertExpirationProfile(
        profile_name="aggressive_review_only",
        description="Short thresholds. Archive resolved after 30 days.",
        rules=[
            CrossSiteAlertExpirationRule(
                rule_name="resolved_archive_30d",
                target_status="resolved",
                age_threshold_days=30,
                proposed_action="archive",
                description="Resolved alerts older than 30 days -> archive candidate",
            ),
            CrossSiteAlertExpirationRule(
                rule_name="acknowledged_review_14d",
                target_status="acknowledged",
                age_threshold_days=14,
                proposed_action="review",
                description="Acknowledged alerts older than 14 days -> review",
            ),
            CrossSiteAlertExpirationRule(
                rule_name="open_info_warning_review_14d",
                target_status="open",
                target_severity="info,warning",
                age_threshold_days=14,
                proposed_action="review",
                description=(
                    "Open info/warning alerts older than 14 days -> review"
                ),
            ),
            CrossSiteAlertExpirationRule(
                rule_name="open_high_critical_review_only",
                target_status="open",
                target_severity="high,critical",
                age_threshold_days=0,
                proposed_action="review",
                description=(
                    "High/critical open alerts -> review only (never archive)"
                ),
            ),
        ],
    )

    return [conservative, standard, aggressive]


def load_expiration_profile(
    profile_name: str = "standard",
    config_path: Optional[Union[Path, str]] = None,
) -> Optional[CrossSiteAlertExpirationProfile]:
    """Load an expiration profile by name.

    Searches built-in profiles first, then user-defined profiles
    from the config file if provided.

    Args:
        profile_name: Name of the profile to load.
        config_path: Optional path to user config file.

    Returns:
        The profile if found, or None.
    """
    return get_expiration_profile_by_name(profile_name, config_path)


# ---------------------------------------------------------------------------
# Preview expiration policy
# ---------------------------------------------------------------------------


def preview_alert_expiration_policy(
    database_path: Optional[str] = None,
    profile_name: str = "standard",
    property_id: Optional[int] = None,
    severity: Optional[str] = None,
    config_path: Optional[Union[Path, str]] = None,
) -> CrossSiteAlertExpirationPreviewResult:
    """Preview which alerts would be affected by an expiration profile.

    No mutations are performed. This is a read-only preview.

    Args:
        database_path: Optional database path.
        profile_name: Expiration profile name.
        property_id: Optional property ID filter.
        severity: Optional severity filter.
        config_path: Optional path to user profile config file.

    Returns:
        Preview result with candidate counts.
    """
    result = CrossSiteAlertExpirationPreviewResult(
        profile_name=profile_name,
    )

    profile = load_expiration_profile(profile_name, config_path=config_path)
    if profile is None:
        return result

    if not table_exists("cross_site_trend_alerts", database_path):
        return result

    alerts = _fetch_alerts(database_path, property_id, severity)
    candidates = _evaluate_rules(alerts, profile)

    result.candidates = candidates
    result.total_candidates = len(candidates)
    for c in candidates:
        if c.proposed_action == "archive":
            result.proposed_archive += 1
        elif c.proposed_action == "review":
            result.proposed_review += 1
        elif c.proposed_action == "keep":
            result.proposed_keep += 1
        elif c.proposed_action == "reopen_review":
            result.proposed_reopen_review += 1

    return result


# ---------------------------------------------------------------------------
# Export approval CSV
# ---------------------------------------------------------------------------


def export_alert_expiration_approval_csv(
    database_path: Optional[str] = None,
    profile_name: str = "standard",
    output_path: Optional[str] = None,
    exports_dir: Optional[str] = None,
    property_id: Optional[int] = None,
    severity: Optional[str] = None,
    config_path: Optional[Union[Path, str]] = None,
) -> Dict:
    """Export expiration approval CSV for operator review.

    Args:
        database_path: Optional database path.
        profile_name: Expiration profile name.
        output_path: Optional explicit output path.
        exports_dir: Optional exports directory.
        property_id: Optional property ID filter.
        severity: Optional severity filter.
        config_path: Optional path to user profile config file.

    Returns:
        Dict with expiration_export_id, output_path, row_count.
    """
    expiration_export_id = f"expiration_{uuid.uuid4().hex[:12]}"

    preview = preview_alert_expiration_policy(
        database_path=database_path,
        profile_name=profile_name,
        property_id=property_id,
        severity=severity,
        config_path=config_path,
    )

    # Stamp export ID on candidates
    for c in preview.candidates:
        c.expiration_export_id = expiration_export_id

    # Determine output path
    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path(exports_dir) if exports_dir else Path("data/exports")
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(
            out_dir / f"cross_site_alert_expiration_approval_{ts}.csv"
        )

    _write_approval_csv(preview.candidates, output_path)

    return {
        "expiration_export_id": expiration_export_id,
        "output_path": output_path,
        "row_count": len(preview.candidates),
        "profile_name": profile_name,
    }


# ---------------------------------------------------------------------------
# Load approval CSV
# ---------------------------------------------------------------------------


def load_alert_expiration_approval_csv(file_path: str) -> List[Dict]:
    """Load expiration approval CSV rows.

    Args:
        file_path: Path to the approval CSV.

    Returns:
        List of row dictionaries.
    """
    rows: List[Dict] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
    except Exception as e:
        logger.error(f"Error loading expiration CSV {file_path}: {e}")
    return rows


# ---------------------------------------------------------------------------
# Validate approvals
# ---------------------------------------------------------------------------


def validate_alert_expiration_approvals(
    rows: List[Dict],
    database_path: Optional[str] = None,
    force_status_mismatch: bool = False,
) -> List[CrossSiteAlertExpirationApprovalRow]:
    """Validate approval decisions from CSV rows.

    Args:
        rows: List of row dicts from approval CSV.
        database_path: Optional database path.
        force_status_mismatch: Allow apply even if status changed.

    Returns:
        List of validated approval rows.
    """
    valid: List[CrossSiteAlertExpirationApprovalRow] = []

    if not table_exists("cross_site_trend_alerts", database_path):
        return valid

    alert_status_map = _get_alert_status_map(database_path)

    for row in rows:
        alert_id_str = row.get("alert_id", "")
        approval_decision = row.get("approval_decision", "").strip()
        expiration_export_id = row.get("expiration_export_id", "").strip()
        profile_name = row.get("profile_name", "").strip()
        expected_status = row.get("current_status", "").strip()
        approval_notes = row.get("approval_notes", "").strip() or None

        # Validate alert_id is numeric
        try:
            alert_id = int(alert_id_str)
        except (ValueError, TypeError):
            continue

        # Validate alert exists
        if alert_id not in alert_status_map:
            continue

        # Validate approval_decision
        if approval_decision not in ALLOWED_APPROVAL_DECISIONS:
            continue

        # Validate expiration_export_id present
        if not expiration_export_id:
            continue

        # Validate profile_name present
        if not profile_name:
            continue

        # Check status mismatch
        actual_status = alert_status_map[alert_id]
        if expected_status and expected_status != actual_status:
            if not force_status_mismatch:
                continue

        valid.append(CrossSiteAlertExpirationApprovalRow(
            alert_id=alert_id,
            expiration_export_id=expiration_export_id,
            profile_name=profile_name,
            expected_status=expected_status,
            approval_decision=approval_decision,
            approval_notes=approval_notes,
        ))

    return valid


# ---------------------------------------------------------------------------
# Apply approvals
# ---------------------------------------------------------------------------


def apply_alert_expiration_approvals(
    file_path: str,
    database_path: Optional[str] = None,
    force_status_mismatch: bool = False,
) -> CrossSiteAlertExpirationApplyResult:
    """Import approval CSV and apply operator-approved decisions.

    Only approved decisions mutate alert status or notes. No automatic
    actions are applied.

    Args:
        file_path: Path to the approval CSV.
        database_path: Optional database path.
        force_status_mismatch: Allow apply even if status changed.

    Returns:
        CrossSiteAlertExpirationApplyResult with counts.
    """
    result = CrossSiteAlertExpirationApplyResult()

    rows = load_alert_expiration_approval_csv(file_path)
    result.rows_read = len(rows)

    if not rows:
        return result

    if not table_exists("cross_site_trend_alerts", database_path):
        result.errors.append("cross_site_trend_alerts table not found")
        return result

    alert_status_map = _get_alert_status_map(database_path)

    for row in rows:
        alert_id_str = row.get("alert_id", "")
        approval_decision = row.get("approval_decision", "").strip()
        expiration_export_id = row.get("expiration_export_id", "").strip()
        profile_name = row.get("profile_name", "").strip()
        expected_status = row.get("current_status", "").strip()
        proposed_action = row.get("proposed_action", "").strip()
        approval_notes = row.get("approval_notes", "").strip() or None

        # Validate alert_id
        try:
            alert_id = int(alert_id_str)
        except (ValueError, TypeError):
            result.invalid_rows += 1
            continue

        # Validate alert exists
        if alert_id not in alert_status_map:
            result.invalid_rows += 1
            result.errors.append(f"Alert {alert_id} not found")
            continue

        # Validate approval_decision
        if approval_decision not in ALLOWED_APPROVAL_DECISIONS:
            result.invalid_rows += 1
            result.errors.append(
                f"Alert {alert_id}: invalid decision '{approval_decision}'"
            )
            continue

        # Validate expiration_export_id
        if not expiration_export_id:
            result.invalid_rows += 1
            result.errors.append(
                f"Alert {alert_id}: missing expiration_export_id"
            )
            continue

        # Validate profile_name
        if not profile_name:
            result.invalid_rows += 1
            result.errors.append(f"Alert {alert_id}: missing profile_name")
            continue

        # Check status mismatch
        actual_status = alert_status_map[alert_id]
        if expected_status and expected_status != actual_status:
            if not force_status_mismatch:
                result.skipped_status_mismatch += 1
                continue

        result.valid_decisions += 1

        # Apply the decision
        if approval_decision == "approve_action":
            # Apply the proposed action
            if proposed_action in _PROPOSED_ACTION_TO_STATUS:
                new_status = _PROPOSED_ACTION_TO_STATUS[proposed_action]
                _apply_status_change(
                    alert_id, actual_status, new_status, database_path,
                )
                _record_expiration_action(
                    expiration_export_id, alert_id, actual_status,
                    f"approve_{proposed_action}", new_status,
                    approval_notes, database_path,
                )
                if proposed_action == "archive":
                    result.archived += 1
                    result.approved_actions += 1
                elif proposed_action == "reopen_review":
                    result.reopened += 1
                    result.approved_actions += 1
            else:
                # review or keep -> notes only
                if approval_notes:
                    _append_notes(alert_id, approval_notes, database_path)
                _record_expiration_action(
                    expiration_export_id, alert_id, actual_status,
                    f"approve_{proposed_action}", actual_status,
                    approval_notes, database_path,
                )
                result.approved_actions += 1
                result.kept_current += 1

        elif approval_decision == "keep_current":
            if approval_notes:
                _append_notes(alert_id, approval_notes, database_path)
            _record_expiration_action(
                expiration_export_id, alert_id, actual_status,
                "keep_current", actual_status,
                approval_notes, database_path,
            )
            result.kept_current += 1

        elif approval_decision == "mark_no_archive":
            note_text = "[no_archive]"
            if approval_notes:
                note_text = f"[no_archive] {approval_notes}"
            _append_notes(alert_id, note_text, database_path)
            _record_expiration_action(
                expiration_export_id, alert_id, actual_status,
                "mark_no_archive", actual_status,
                approval_notes, database_path,
            )
            result.marked_no_archive += 1

        elif approval_decision in _STATUS_CHANGING_DECISIONS:
            new_status = _STATUS_CHANGING_DECISIONS[approval_decision]
            _apply_status_change(
                alert_id, actual_status, new_status, database_path,
            )
            if approval_notes:
                _append_notes(alert_id, approval_notes, database_path)
            _record_expiration_action(
                expiration_export_id, alert_id, actual_status,
                approval_decision, new_status,
                approval_notes, database_path,
            )
            if approval_decision == "archive":
                result.archived += 1
            elif approval_decision == "reopen":
                result.reopened += 1
            elif approval_decision == "acknowledge":
                result.acknowledged += 1
            elif approval_decision == "resolve":
                result.resolved += 1

    return result


# ---------------------------------------------------------------------------
# Expiration policy summary
# ---------------------------------------------------------------------------


def summarize_alert_expiration_policy(
    database_path: Optional[str] = None,
    profile_name: str = "standard",
    config_path: Optional[Union[Path, str]] = None,
) -> CrossSiteAlertExpirationSummary:
    """Summarize current expiration policy state.

    Args:
        database_path: Optional database path.
        profile_name: Expiration profile to use.
        config_path: Optional path to user profile config file.

    Returns:
        CrossSiteAlertExpirationSummary with counts and actions.
    """
    summary = CrossSiteAlertExpirationSummary(profile_name=profile_name)

    if not table_exists("cross_site_trend_alerts", database_path):
        return summary

    try:
        preview = preview_alert_expiration_policy(
            database_path=database_path,
            profile_name=profile_name,
            config_path=config_path,
        )
        summary.total_candidates = preview.total_candidates
        summary.proposed_archive = preview.proposed_archive
        summary.proposed_review = preview.proposed_review
        summary.proposed_keep = preview.proposed_keep

        # Count archived
        archived_rows = execute_query(
            """
            SELECT COUNT(*) as cnt
            FROM cross_site_trend_alerts
            WHERE alert_status = 'archived'
            """,
            database_path=database_path,
        )
        if archived_rows:
            summary.already_archived = archived_rows[0]["cnt"]

        # Count no_archive
        no_archive_rows = execute_query(
            """
            SELECT COUNT(*) as cnt
            FROM cross_site_trend_alerts
            WHERE notes LIKE '%[no_archive]%'
            """,
            database_path=database_path,
        )
        if no_archive_rows:
            summary.no_archive_marked = no_archive_rows[0]["cnt"]

    except Exception as e:
        logger.error(f"Error summarizing expiration policy: {e}")

    summary.next_actions = _generate_expiration_next_actions(summary)
    return summary


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _age_days(created_at_str: Optional[str]) -> Optional[int]:
    """Calculate age in days from a timestamp string."""
    if not created_at_str:
        return None
    try:
        created = datetime.fromisoformat(str(created_at_str))
        delta = datetime.now() - created
        return max(0, delta.days)
    except (ValueError, TypeError):
        return None


def _get_alert_status_map(
    database_path: Optional[str] = None,
) -> Dict[int, str]:
    """Build a map of alert_id -> current alert_status."""
    result: Dict[int, str] = {}
    try:
        rows = execute_query(
            "SELECT alert_id, alert_status FROM cross_site_trend_alerts",
            database_path=database_path,
        )
        for row in rows:
            result[row["alert_id"]] = row["alert_status"]
    except Exception:
        pass
    return result


def _fetch_alerts(
    database_path: Optional[str] = None,
    property_id: Optional[int] = None,
    severity: Optional[str] = None,
) -> List[Dict]:
    """Fetch alerts for rule evaluation."""
    conditions = ["a.alert_status NOT IN ('archived')"]
    params: list = []

    if property_id is not None:
        conditions.append("a.property_id = ?")
        params.append(property_id)

    if severity:
        conditions.append("a.severity = ?")
        params.append(severity)

    where = " AND ".join(conditions)
    query = f"""
    SELECT a.alert_id, a.property_id, a.candidate_id,
           a.alert_type, a.severity, a.alert_status,
           a.created_at, a.message, a.recommended_action,
           a.source_context, a.notes,
           wp.address, wp.city, wp.zip
    FROM cross_site_trend_alerts a
    LEFT JOIN watched_properties wp ON a.property_id = wp.property_id
    WHERE {where}
    ORDER BY a.created_at ASC
    """

    try:
        return execute_query(query, tuple(params), database_path=database_path)
    except Exception as e:
        logger.error(f"Error fetching alerts for expiration: {e}")
        return []


def _evaluate_rules(
    alerts: List[Dict],
    profile: CrossSiteAlertExpirationProfile,
) -> List[CrossSiteAlertExpirationCandidate]:
    """Evaluate profile rules against alerts."""
    candidates: List[CrossSiteAlertExpirationCandidate] = []
    seen_alert_ids: set = set()

    for rule in profile.rules:
        target_severities = None
        if rule.target_severity:
            target_severities = {
                s.strip() for s in rule.target_severity.split(",")
            }

        for alert in alerts:
            alert_id = alert["alert_id"]
            if alert_id in seen_alert_ids:
                continue

            status = alert["alert_status"]
            sev = alert["severity"]
            notes = alert["notes"] or ""

            # Match status
            if status != rule.target_status:
                continue

            # Match severity if specified
            if target_severities and sev not in target_severities:
                continue

            # Check age threshold
            age = _age_days(alert["created_at"])
            if age is None:
                continue
            if rule.age_threshold_days > 0 and age < rule.age_threshold_days:
                continue

            # Determine proposed action
            proposed = rule.proposed_action

            # no_archive alerts -> keep or review only (never archive)
            if "[no_archive]" in notes and proposed == "archive":
                proposed = "keep"

            # high/critical open alerts -> review only (never archive)
            if (
                status == "open"
                and sev in ("high", "critical")
                and proposed == "archive"
            ):
                proposed = "review"

            # Build reason
            reason = rule.description
            if not reason:
                reason = (
                    f"{status} {sev} alert aged {age}d "
                    f"(threshold: {rule.age_threshold_days}d)"
                )

            candidates.append(CrossSiteAlertExpirationCandidate(
                profile_name=profile.profile_name,
                rule_name=rule.rule_name,
                alert_id=alert_id,
                property_id=alert["property_id"],
                candidate_id=alert["candidate_id"],
                address=alert["address"],
                city=alert["city"],
                zip=alert["zip"],
                alert_type=alert["alert_type"],
                severity=sev,
                current_status=status,
                alert_age_days=age,
                proposed_action=proposed,
                proposed_reason=reason,
                current_notes=notes if notes else None,
                approval_decision="keep_current",
            ))
            seen_alert_ids.add(alert_id)

    return candidates


def _apply_status_change(
    alert_id: int,
    previous_status: str,
    new_status: str,
    database_path: Optional[str] = None,
) -> None:
    """Update alert status in the database."""
    conn = get_connection(database_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE cross_site_trend_alerts SET alert_status = ? "
            "WHERE alert_id = ?",
            (new_status, alert_id),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error changing alert {alert_id} status: {e}")
    finally:
        conn.close()


def _append_notes(
    alert_id: int,
    note_text: str,
    database_path: Optional[str] = None,
) -> None:
    """Append text to an alert's notes field."""
    conn = get_connection(database_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE cross_site_trend_alerts
            SET notes = CASE
                WHEN notes IS NULL OR notes = '' THEN ?
                ELSE notes || '; ' || ?
            END
            WHERE alert_id = ?
            """,
            (note_text, note_text, alert_id),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error appending notes for alert {alert_id}: {e}")
    finally:
        conn.close()


def _record_expiration_action(
    expiration_export_id: str,
    alert_id: int,
    previous_status: str,
    action: str,
    new_status: str,
    notes: Optional[str],
    database_path: Optional[str] = None,
) -> None:
    """Record an expiration action in the triage_actions table."""
    if not table_exists("cross_site_alert_triage_actions", database_path):
        return

    property_id = None
    try:
        rows = execute_query(
            "SELECT property_id FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (alert_id,),
            database_path=database_path,
        )
        if rows:
            property_id = rows[0]["property_id"]
    except Exception:
        pass

    conn = get_connection(database_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO cross_site_alert_triage_actions
            (triage_export_id, alert_id, property_id, action,
             previous_status, new_status, triage_notes, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                expiration_export_id, alert_id, property_id, action,
                previous_status, new_status, notes or "",
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error recording expiration action: {e}")
    finally:
        conn.close()


def _write_approval_csv(
    candidates: List[CrossSiteAlertExpirationCandidate],
    path: str,
) -> None:
    """Write expiration approval candidates to CSV."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPIRATION_CSV_FIELDNAMES)
        writer.writeheader()
        for c in candidates:
            writer.writerow({
                "expiration_export_id": c.expiration_export_id,
                "profile_name": c.profile_name,
                "rule_name": c.rule_name,
                "alert_id": c.alert_id,
                "property_id": c.property_id,
                "candidate_id": c.candidate_id or "",
                "address": c.address or "",
                "city": c.city or "",
                "zip": c.zip or "",
                "alert_type": c.alert_type,
                "severity": c.severity,
                "current_status": c.current_status,
                "alert_age_days": (
                    c.alert_age_days if c.alert_age_days is not None else ""
                ),
                "proposed_action": c.proposed_action,
                "proposed_reason": c.proposed_reason,
                "current_notes": c.current_notes or "",
                "approval_decision": c.approval_decision,
                "approval_notes": c.approval_notes or "",
            })


def _generate_expiration_next_actions(
    summary: CrossSiteAlertExpirationSummary,
) -> List[str]:
    """Generate recommended next actions from expiration summary."""
    actions: List[str] = []

    if summary.total_candidates > 0:
        actions.append(
            f"Export {summary.total_candidates} expiration candidate(s): "
            f"marketsentry export-cross-site-alert-expiration-approval "
            f"--profile {summary.profile_name}"
        )

    if summary.proposed_archive > 0:
        actions.append(
            f"{summary.proposed_archive} alert(s) proposed for archive"
        )

    if summary.proposed_review > 0:
        actions.append(
            f"{summary.proposed_review} alert(s) proposed for review"
        )

    if summary.already_archived > 0:
        actions.append(
            f"{summary.already_archived} alert(s) already archived"
        )

    if summary.no_archive_marked > 0:
        actions.append(
            f"{summary.no_archive_marked} alert(s) marked no_archive"
        )

    if not actions:
        actions.append(
            "No alerts match expiration rules at current thresholds."
        )

    return actions
