"""Profile comparison and last-used profile persistence.

Compares built-in and user-defined alert expiration profiles
side-by-side, showing candidate/action counts per profile.
Stores a local preference for the last-used profile as a
convenience default only. No actions are applied automatically.

This module does not change watchlist status, overwrite Redfin
source-of-truth fields, modify Quiet Score gatekeeper results,
or infer seller intent. Reports are operational review aids,
not purchase recommendations.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from marketsentry.logging_config import logger
from marketsentry.models import (
    CrossSiteAlertExpirationProfileComparisonResult,
    CrossSiteAlertExpirationProfileComparisonRow,
    CrossSiteAlertExpirationProfileDiff,
    CrossSiteAlertExpirationProfilePreference,
    CrossSiteAlertExpirationProfilePreferenceResult,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PREFERENCE_PATH = Path(
    "config/alert_expiration_profile_preference.json"
)

COMPARISON_CSV_FIELDNAMES = [
    "profile_name",
    "profile_source",
    "total_candidates",
    "proposed_archive_count",
    "proposed_review_count",
    "proposed_keep_count",
    "high_critical_review_count",
    "no_archive_excluded_count",
    "affected_property_count",
    "oldest_candidate_age_days",
    "youngest_candidate_age_days",
    "rule_count",
    "validation_status",
    "notes",
]


# ---------------------------------------------------------------------------
# Profile comparison
# ---------------------------------------------------------------------------


def compare_alert_expiration_profiles(
    database_path: Optional[str] = None,
    config_path: Optional[Union[Path, str]] = None,
    profile_names: Optional[List[str]] = None,
) -> CrossSiteAlertExpirationProfileComparisonResult:
    """Compare multiple expiration profiles side-by-side.

    Runs preview logic for each profile without mutations.

    Args:
        database_path: Optional database path.
        config_path: Optional path to user profile config.
        profile_names: Optional list of profile names to compare.
            If None, all available profiles are compared.

    Returns:
        Comparison result with one row per profile.
    """
    from marketsentry.cross_site_alert_expiration_policy import (
        _BUILTIN_PROFILE_NAMES,
        merge_builtin_and_user_profiles,
        preview_alert_expiration_policy,
    )

    result = CrossSiteAlertExpirationProfileComparisonResult()

    merged, errors = merge_builtin_and_user_profiles(config_path)
    result.errors.extend(errors)

    # Filter to requested profiles if specified
    if profile_names:
        name_set = set(profile_names)
        merged = [p for p in merged if p.profile_name in name_set]
        missing = name_set - {p.profile_name for p in merged}
        for m in missing:
            result.errors.append(f"Profile '{m}' not found")

    result.profiles_compared = len(merged)

    for profile in merged:
        preview = preview_alert_expiration_policy(
            database_path=database_path,
            profile_name=profile.profile_name,
            config_path=config_path,
        )

        row = _build_comparison_row(profile, preview)
        row.profile_source = (
            "built_in"
            if profile.profile_name in _BUILTIN_PROFILE_NAMES
            else "user_config"
        )
        result.rows.append(row)

    return result


def compare_two_alert_expiration_profiles(
    profile_a: str,
    profile_b: str,
    database_path: Optional[str] = None,
    config_path: Optional[Union[Path, str]] = None,
) -> CrossSiteAlertExpirationProfileDiff:
    """Compare two profiles and compute deltas.

    Args:
        profile_a: First profile name.
        profile_b: Second profile name.
        database_path: Optional database path.
        config_path: Optional path to user profile config.

    Returns:
        Profile diff with count deltas and overlap analysis.
    """
    from marketsentry.cross_site_alert_expiration_policy import (
        preview_alert_expiration_policy,
    )

    diff = CrossSiteAlertExpirationProfileDiff(
        profile_a=profile_a,
        profile_b=profile_b,
    )

    preview_a = preview_alert_expiration_policy(
        database_path=database_path,
        profile_name=profile_a,
        config_path=config_path,
    )
    preview_b = preview_alert_expiration_policy(
        database_path=database_path,
        profile_name=profile_b,
        config_path=config_path,
    )

    diff.candidate_count_delta = (
        preview_b.total_candidates - preview_a.total_candidates
    )
    diff.archive_count_delta = (
        preview_b.proposed_archive - preview_a.proposed_archive
    )
    diff.review_count_delta = (
        preview_b.proposed_review - preview_a.proposed_review
    )
    diff.keep_count_delta = (
        preview_b.proposed_keep - preview_a.proposed_keep
    )

    # Compute alert-level overlap
    alerts_a: Dict[int, str] = {
        c.alert_id: c.proposed_action for c in preview_a.candidates
    }
    alerts_b: Dict[int, str] = {
        c.alert_id: c.proposed_action for c in preview_b.candidates
    }

    ids_a = set(alerts_a.keys())
    ids_b = set(alerts_b.keys())

    diff.alerts_only_in_a = len(ids_a - ids_b)
    diff.alerts_only_in_b = len(ids_b - ids_a)

    common = ids_a & ids_b
    diff.common_alerts_with_different_actions = sum(
        1 for aid in common if alerts_a[aid] != alerts_b[aid]
    )

    # Compute property-level overlap
    props_a: Set[int] = {c.property_id for c in preview_a.candidates}
    props_b: Set[int] = {c.property_id for c in preview_b.candidates}

    diff.properties_only_in_a = len(props_a - props_b)
    diff.properties_only_in_b = len(props_b - props_a)

    # Build summary text
    parts: List[str] = []
    parts.append(
        f"{profile_a}: {preview_a.total_candidates} candidates "
        f"({preview_a.proposed_archive} archive, "
        f"{preview_a.proposed_review} review)"
    )
    parts.append(
        f"{profile_b}: {preview_b.total_candidates} candidates "
        f"({preview_b.proposed_archive} archive, "
        f"{preview_b.proposed_review} review)"
    )
    if diff.candidate_count_delta != 0:
        direction = "more" if diff.candidate_count_delta > 0 else "fewer"
        parts.append(
            f"{profile_b} has {abs(diff.candidate_count_delta)} "
            f"{direction} candidates than {profile_a}"
        )
    if diff.common_alerts_with_different_actions > 0:
        parts.append(
            f"{diff.common_alerts_with_different_actions} common alerts "
            f"have different proposed actions"
        )
    diff.summary_text = ". ".join(parts)

    return diff


def export_alert_expiration_profile_comparison(
    database_path: Optional[str] = None,
    config_path: Optional[Union[Path, str]] = None,
    profile_names: Optional[List[str]] = None,
    output_path: Optional[str] = None,
    exports_dir: Optional[str] = None,
) -> Dict:
    """Export profile comparison to CSV.

    Args:
        database_path: Optional database path.
        config_path: Optional path to user profile config.
        profile_names: Optional list of profile names.
        output_path: Optional explicit output path.
        exports_dir: Optional exports directory.

    Returns:
        Dict with output_path and row_count.
    """
    comparison = compare_alert_expiration_profiles(
        database_path=database_path,
        config_path=config_path,
        profile_names=profile_names,
    )

    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path(exports_dir) if exports_dir else Path("data/exports")
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(
            out_dir
            / f"cross_site_alert_expiration_profile_comparison_{ts}.csv"
        )

    _write_comparison_csv(comparison.rows, output_path)

    return {
        "output_path": output_path,
        "row_count": len(comparison.rows),
        "profiles_compared": comparison.profiles_compared,
    }


def get_profile_candidate_counts(
    database_path: Optional[str] = None,
    config_path: Optional[Union[Path, str]] = None,
    profile_name: Optional[str] = None,
) -> Dict:
    """Get candidate counts for a profile.

    Args:
        database_path: Optional database path.
        config_path: Optional path to user profile config.
        profile_name: Profile name. Defaults to standard.

    Returns:
        Dict with count fields.
    """
    from marketsentry.cross_site_alert_expiration_policy import (
        preview_alert_expiration_policy,
    )

    name = profile_name or "standard"
    preview = preview_alert_expiration_policy(
        database_path=database_path,
        profile_name=name,
        config_path=config_path,
    )

    return {
        "profile_name": name,
        "total_candidates": preview.total_candidates,
        "proposed_archive": preview.proposed_archive,
        "proposed_review": preview.proposed_review,
        "proposed_keep": preview.proposed_keep,
    }


def summarize_profile_differences(
    profile_a: str,
    profile_b: str,
    database_path: Optional[str] = None,
    config_path: Optional[Union[Path, str]] = None,
) -> str:
    """Return a human-readable summary of differences between two profiles.

    Args:
        profile_a: First profile name.
        profile_b: Second profile name.
        database_path: Optional database path.
        config_path: Optional path to user profile config.

    Returns:
        Summary text string.
    """
    diff = compare_two_alert_expiration_profiles(
        profile_a, profile_b,
        database_path=database_path,
        config_path=config_path,
    )
    return diff.summary_text


# ---------------------------------------------------------------------------
# Last-used profile persistence
# ---------------------------------------------------------------------------


def load_last_used_expiration_profile(
    preference_path: Optional[Union[Path, str]] = None,
    config_path: Optional[Union[Path, str]] = None,
) -> CrossSiteAlertExpirationProfilePreferenceResult:
    """Load the last-used profile preference.

    If the preference file is missing or invalid, falls back to
    the built-in 'standard' profile with a warning.

    Args:
        preference_path: Path to the preference JSON file.
        config_path: Optional path to user profile config for validation.

    Returns:
        Preference result with profile name and validation status.
    """
    path = Path(preference_path) if preference_path else DEFAULT_PREFERENCE_PATH
    result = CrossSiteAlertExpirationProfilePreferenceResult()

    if not path.exists():
        result.was_fallback = True
        return result

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        result.warnings.append(f"Invalid preference file {path}: {e}")
        result.was_fallback = True
        return result

    if not isinstance(data, dict):
        result.warnings.append(f"Preference file {path} must be an object")
        result.was_fallback = True
        return result

    profile_name = data.get("last_used_profile", "").strip()
    if not profile_name:
        result.warnings.append("No last_used_profile in preference file")
        result.was_fallback = True
        return result

    # Validate profile exists
    from marketsentry.cross_site_alert_expiration_policy import (
        get_expiration_profile_by_name,
    )

    effective_config = data.get("profile_config_path") or config_path
    profile = get_expiration_profile_by_name(
        profile_name, config_path=effective_config,
    )

    if profile is None:
        result.warnings.append(
            f"Last-used profile '{profile_name}' not found; "
            f"falling back to standard"
        )
        result.was_fallback = True
        return result

    result.profile_name = profile_name
    result.profile_config_path = (
        str(effective_config) if effective_config else None
    )
    result.is_valid = True
    result.was_fallback = False
    return result


def save_last_used_expiration_profile(
    profile_name: str,
    preference_path: Optional[Union[Path, str]] = None,
    config_path: Optional[Union[Path, str]] = None,
) -> Tuple[bool, str]:
    """Save the last-used profile preference.

    Validates the profile exists before saving.

    Args:
        profile_name: Profile name to save.
        preference_path: Path to the preference JSON file.
        config_path: Optional path to user profile config.

    Returns:
        Tuple of (success, message).
    """
    from marketsentry.cross_site_alert_expiration_policy import (
        get_expiration_profile_by_name,
    )

    profile = get_expiration_profile_by_name(profile_name, config_path)
    if profile is None:
        return False, f"Profile '{profile_name}' not found"

    path = Path(preference_path) if preference_path else DEFAULT_PREFERENCE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    pref = CrossSiteAlertExpirationProfilePreference(
        last_used_profile=profile_name,
        profile_config_path=str(config_path) if config_path else None,
        saved_at=datetime.now().isoformat(),
    )

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pref.model_dump(), f, indent=2)
            f.write("\n")
        return True, f"Saved preference: {profile_name} -> {path}"
    except Exception as e:
        return False, f"Error saving preference: {e}"


def clear_last_used_expiration_profile(
    preference_path: Optional[Union[Path, str]] = None,
) -> Tuple[bool, str]:
    """Clear the last-used profile preference.

    Removes the preference file if it exists.

    Args:
        preference_path: Path to the preference JSON file.

    Returns:
        Tuple of (success, message).
    """
    path = Path(preference_path) if preference_path else DEFAULT_PREFERENCE_PATH

    if not path.exists():
        return True, "No preference file to clear"

    try:
        path.unlink()
        return True, f"Cleared preference: {path}"
    except Exception as e:
        return False, f"Error clearing preference: {e}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_comparison_row(
    profile: "CrossSiteAlertExpirationProfile",  # noqa: F821
    preview: "CrossSiteAlertExpirationPreviewResult",  # noqa: F821
) -> CrossSiteAlertExpirationProfileComparisonRow:
    """Build a comparison row from a profile and preview result.

    Args:
        profile: The expiration profile.
        preview: The preview result for that profile.

    Returns:
        A comparison row with computed fields.
    """
    row = CrossSiteAlertExpirationProfileComparisonRow(
        profile_name=profile.profile_name,
        total_candidates=preview.total_candidates,
        proposed_archive_count=preview.proposed_archive,
        proposed_review_count=preview.proposed_review,
        proposed_keep_count=preview.proposed_keep,
        rule_count=len(profile.rules),
    )

    # Compute detailed metrics from candidates
    properties: set = set()
    ages: List[int] = []
    high_crit = 0
    no_archive = 0

    for c in preview.candidates:
        properties.add(c.property_id)
        if c.alert_age_days is not None:
            ages.append(c.alert_age_days)
        if c.severity in ("high", "critical"):
            high_crit += 1
        if c.current_notes and "[no_archive]" in c.current_notes:
            no_archive += 1

    row.affected_property_count = len(properties)
    row.high_critical_review_count = high_crit
    row.no_archive_excluded_count = no_archive

    if ages:
        row.oldest_candidate_age_days = max(ages)
        row.youngest_candidate_age_days = min(ages)

    return row


def _write_comparison_csv(
    rows: List[CrossSiteAlertExpirationProfileComparisonRow],
    path: str,
) -> None:
    """Write comparison rows to CSV.

    Args:
        rows: List of comparison rows.
        path: Output file path.
    """
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COMPARISON_CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "profile_name": row.profile_name,
                "profile_source": row.profile_source,
                "total_candidates": row.total_candidates,
                "proposed_archive_count": row.proposed_archive_count,
                "proposed_review_count": row.proposed_review_count,
                "proposed_keep_count": row.proposed_keep_count,
                "high_critical_review_count": row.high_critical_review_count,
                "no_archive_excluded_count": row.no_archive_excluded_count,
                "affected_property_count": row.affected_property_count,
                "oldest_candidate_age_days": (
                    row.oldest_candidate_age_days
                    if row.oldest_candidate_age_days is not None
                    else ""
                ),
                "youngest_candidate_age_days": (
                    row.youngest_candidate_age_days
                    if row.youngest_candidate_age_days is not None
                    else ""
                ),
                "rule_count": row.rule_count,
                "validation_status": row.validation_status,
                "notes": row.notes or "",
            })
