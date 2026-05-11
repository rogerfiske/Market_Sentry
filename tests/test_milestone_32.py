"""Tests for Milestone 32: User-Defined Alert Expiration Profiles.

Tests cover:
- Built-in profiles still load without config
- Missing config does not error
- Example config writer creates file
- Example config writer refuses overwrite by default
- Valid user profile loads
- Multiple user profiles load
- Duplicate user profile names rejected
- User profile cannot override built-in profile
- Invalid JSON handled clearly
- Missing profile_name rejected
- Missing rule_name rejected
- Invalid status rejected
- Invalid severity rejected
- Invalid proposed_action rejected
- Negative min_age_days rejected
- High/critical open archive rule rejected
- Archived alert mutation rule rejected
- Merge builtin and user profiles
- get_expiration_profile_by_name built-in
- get_expiration_profile_by_name custom
- Preview policy with custom profile
- Export approval CSV with custom profile
- CLI list profiles with config
- CLI write template
- CLI preview custom profile
- CLI export custom profile
- Dashboard custom profile validation data loads
- No auto-apply behavior
- No Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- No walkability fields added
- No real network calls
- Existing MVP 1-31 tests still pass (run with full suite)
"""

import csv
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from marketsentry.database import (
    execute_query,
    get_connection,
    init_db,
    table_exists,
)
from marketsentry.models import (
    CrossSiteAlertExpirationProfile,
    CrossSiteAlertExpirationRule,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_db():
    """Create a temporary database with full schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    init_db(db_path)
    yield db_path

    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def temp_exports_dir():
    """Create a temporary exports directory."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for config files."""
    with tempfile.TemporaryDirectory() as d:
        yield d


def _insert_watched_property(
    db_path: str, address: str = "123 Test St",
) -> int:
    """Insert a watched property and return its ID."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO watched_properties (
            first_saved_date, active_watch_status, address, city, zip,
            current_price, displayed_dom, garage_spaces, gas_service
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-01-01", 1, address, "Temecula", "92592", 750000, 45, 2, 1),
    )
    pid = cursor.lastrowid
    conn.commit()
    conn.close()
    return pid


def _insert_alert(
    db_path: str,
    property_id: int,
    alert_type: str = "confidence_drop",
    severity: str = "warning",
    alert_status: str = "open",
    snapshot_id: int = 1,
    created_at: str = "",
    notes: str = "",
) -> int:
    """Insert a trend alert and return its ID."""
    if not created_at:
        created_at = datetime.now().isoformat()

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO cross_site_trend_alerts (
            property_id, alert_type, severity, alert_status,
            snapshot_id, created_at, message, recommended_action, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            property_id, alert_type, severity, alert_status,
            snapshot_id, created_at,
            f"Test {alert_type} alert",
            "Review cross-site data",
            notes,
        ),
    )
    aid = cursor.lastrowid
    conn.commit()
    conn.close()
    return aid


def _write_config(config_dir: str, data: dict, name: str = "profiles.json") -> str:
    """Write a JSON config file and return the path."""
    path = str(Path(config_dir) / name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def _valid_user_profile_config() -> dict:
    """Return a valid user profile config dict."""
    return {
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
# Test: Built-in profiles still load without config
# ---------------------------------------------------------------------------


class TestBuiltinProfilesWithoutConfig:
    """Built-in profiles work regardless of user config."""

    def test_builtin_profiles_load(self):
        from marketsentry.cross_site_alert_expiration_policy import (
            get_default_expiration_profiles,
        )
        profiles = get_default_expiration_profiles()
        assert len(profiles) == 3
        names = {p.profile_name for p in profiles}
        assert names == {"conservative", "standard", "aggressive_review_only"}

    def test_merge_with_no_config(self):
        from marketsentry.cross_site_alert_expiration_policy import (
            merge_builtin_and_user_profiles,
        )
        profiles, errors = merge_builtin_and_user_profiles(
            config_path="/nonexistent/path.json"
        )
        assert len(profiles) == 3
        assert errors == []

    def test_load_profile_standard_no_config(self):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_expiration_profile,
        )
        profile = load_expiration_profile(
            "standard", config_path="/nonexistent/path.json"
        )
        assert profile is not None
        assert profile.profile_name == "standard"


# ---------------------------------------------------------------------------
# Test: Missing config does not error
# ---------------------------------------------------------------------------


class TestMissingConfigNoError:
    """Missing config file returns empty profiles without error."""

    def test_load_user_profiles_missing_file(self):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        profiles, errors = load_user_expiration_profiles(
            "/nonexistent/profiles.json"
        )
        assert profiles == []
        assert errors == []

    def test_validate_missing_file(self):
        from marketsentry.cross_site_alert_expiration_policy import (
            validate_expiration_profile_config,
        )
        is_valid, errors = validate_expiration_profile_config(
            "/nonexistent/profiles.json"
        )
        assert is_valid is True
        assert errors == []


# ---------------------------------------------------------------------------
# Test: Example config writer
# ---------------------------------------------------------------------------


class TestExampleConfigWriter:
    """Example config writer creates file and respects overwrite flag."""

    def test_creates_file(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            write_example_expiration_profile_config,
        )
        output = str(Path(temp_config_dir) / "example.json")
        path, was_written = write_example_expiration_profile_config(
            output_path=output
        )
        assert was_written is True
        assert Path(path).exists()

        # Verify contents are valid JSON
        with open(path, "r") as f:
            data = json.load(f)
        assert "profiles" in data
        assert len(data["profiles"]) > 0

    def test_refuses_overwrite_by_default(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            write_example_expiration_profile_config,
        )
        output = str(Path(temp_config_dir) / "example.json")
        # Create file first
        write_example_expiration_profile_config(output_path=output)
        # Try again without overwrite
        path, was_written = write_example_expiration_profile_config(
            output_path=output
        )
        assert was_written is False

    def test_overwrite_when_requested(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            write_example_expiration_profile_config,
        )
        output = str(Path(temp_config_dir) / "example.json")
        write_example_expiration_profile_config(output_path=output)
        path, was_written = write_example_expiration_profile_config(
            output_path=output, overwrite=True,
        )
        assert was_written is True


# ---------------------------------------------------------------------------
# Test: Valid user profile loads
# ---------------------------------------------------------------------------


class TestValidUserProfileLoads:
    """Valid user profiles load correctly."""

    def test_single_profile(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(profiles) == 1
        assert errors == []
        assert profiles[0].profile_name == "my_custom_review"
        assert len(profiles[0].rules) == 2

    def test_multiple_profiles(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "profile_a",
                    "description": "Profile A",
                    "rules": [
                        {
                            "rule_name": "rule_1",
                            "current_status": "resolved",
                            "severity": "any",
                            "min_age_days": 30,
                            "proposed_action": "archive",
                        }
                    ],
                },
                {
                    "profile_name": "profile_b",
                    "description": "Profile B",
                    "rules": [
                        {
                            "rule_name": "rule_1",
                            "current_status": "acknowledged",
                            "severity": "any",
                            "min_age_days": 14,
                            "proposed_action": "review",
                        }
                    ],
                },
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(profiles) == 2
        assert errors == []
        assert profiles[0].profile_name == "profile_a"
        assert profiles[1].profile_name == "profile_b"


# ---------------------------------------------------------------------------
# Test: Duplicate user profile names rejected
# ---------------------------------------------------------------------------


class TestDuplicateProfileNamesRejected:
    """Duplicate profile names within user config are rejected."""

    def test_duplicate_names(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "same_name",
                    "rules": [{
                        "rule_name": "r1",
                        "current_status": "resolved",
                        "min_age_days": 30,
                        "proposed_action": "archive",
                    }],
                },
                {
                    "profile_name": "same_name",
                    "rules": [{
                        "rule_name": "r2",
                        "current_status": "resolved",
                        "min_age_days": 60,
                        "proposed_action": "review",
                    }],
                },
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(errors) > 0
        assert any("duplicate" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Test: User profile cannot override built-in profile
# ---------------------------------------------------------------------------


class TestCannotOverrideBuiltin:
    """User profiles with built-in names are rejected on merge."""

    def test_builtin_name_rejected(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            merge_builtin_and_user_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "standard",
                    "description": "Override attempt",
                    "rules": [{
                        "rule_name": "r1",
                        "current_status": "resolved",
                        "min_age_days": 10,
                        "proposed_action": "archive",
                    }],
                },
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = merge_builtin_and_user_profiles(path)
        # Built-in profiles preserved
        assert len(profiles) == 3
        # Error reported
        assert len(errors) > 0
        assert any("conflicts" in e.lower() for e in errors)

    def test_validate_rejects_builtin_name(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            validate_expiration_profile_config,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "conservative",
                    "rules": [{
                        "rule_name": "r1",
                        "current_status": "resolved",
                        "min_age_days": 10,
                        "proposed_action": "archive",
                    }],
                },
            ]
        }
        path = _write_config(temp_config_dir, config)
        is_valid, errors = validate_expiration_profile_config(path)
        assert is_valid is False
        assert any("conflicts" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Test: Invalid JSON handled clearly
# ---------------------------------------------------------------------------


class TestInvalidJsonHandled:
    """Invalid JSON in config file produces clear errors."""

    def test_invalid_json(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        path = str(Path(temp_config_dir) / "bad.json")
        with open(path, "w") as f:
            f.write("{invalid json content")
        profiles, errors = load_user_expiration_profiles(path)
        assert profiles == []
        assert len(errors) > 0
        assert any("invalid json" in e.lower() for e in errors)

    def test_missing_profiles_key(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        path = _write_config(temp_config_dir, {"rules": []})
        profiles, errors = load_user_expiration_profiles(path)
        assert profiles == []
        assert len(errors) > 0
        assert any("profiles" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Test: Missing profile_name rejected
# ---------------------------------------------------------------------------


class TestMissingProfileNameRejected:
    """Profiles without profile_name are rejected."""

    def test_no_profile_name(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "description": "Missing name",
                    "rules": [],
                }
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(errors) > 0
        assert any("profile_name" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Test: Missing rule_name rejected
# ---------------------------------------------------------------------------


class TestMissingRuleNameRejected:
    """Rules without rule_name are rejected."""

    def test_no_rule_name(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "test_profile",
                    "rules": [
                        {
                            "current_status": "resolved",
                            "min_age_days": 30,
                            "proposed_action": "archive",
                        }
                    ],
                }
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(errors) > 0
        assert any("rule_name" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Test: Invalid status rejected
# ---------------------------------------------------------------------------


class TestInvalidStatusRejected:
    """Invalid current_status values are rejected."""

    def test_invalid_status(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "test_profile",
                    "rules": [
                        {
                            "rule_name": "bad_rule",
                            "current_status": "invalid_status",
                            "min_age_days": 30,
                            "proposed_action": "archive",
                        }
                    ],
                }
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(errors) > 0
        assert any("current_status" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Test: Invalid severity rejected
# ---------------------------------------------------------------------------


class TestInvalidSeverityRejected:
    """Invalid severity values are rejected."""

    def test_invalid_severity_string(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "test_profile",
                    "rules": [
                        {
                            "rule_name": "bad_rule",
                            "current_status": "resolved",
                            "severity": "extreme",
                            "min_age_days": 30,
                            "proposed_action": "archive",
                        }
                    ],
                }
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(errors) > 0
        assert any("severity" in e.lower() for e in errors)

    def test_invalid_severity_in_list(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "test_profile",
                    "rules": [
                        {
                            "rule_name": "bad_rule",
                            "current_status": "resolved",
                            "severity": ["info", "extreme"],
                            "min_age_days": 30,
                            "proposed_action": "archive",
                        }
                    ],
                }
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(errors) > 0
        assert any("severity" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Test: Invalid proposed_action rejected
# ---------------------------------------------------------------------------


class TestInvalidProposedActionRejected:
    """Invalid proposed_action values are rejected."""

    def test_invalid_action(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "test_profile",
                    "rules": [
                        {
                            "rule_name": "bad_rule",
                            "current_status": "resolved",
                            "min_age_days": 30,
                            "proposed_action": "delete",
                        }
                    ],
                }
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(errors) > 0
        assert any("proposed_action" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Test: Negative min_age_days rejected
# ---------------------------------------------------------------------------


class TestNegativeMinAgeDaysRejected:
    """Negative min_age_days values are rejected."""

    def test_negative_age(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "test_profile",
                    "rules": [
                        {
                            "rule_name": "bad_rule",
                            "current_status": "resolved",
                            "min_age_days": -5,
                            "proposed_action": "archive",
                        }
                    ],
                }
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(errors) > 0
        assert any("min_age_days" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Test: High/critical open archive rule rejected
# ---------------------------------------------------------------------------


class TestHighCriticalOpenArchiveRejected:
    """Archive rules for high/critical open alerts are rejected."""

    def test_high_open_archive_rejected(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "test_profile",
                    "rules": [
                        {
                            "rule_name": "bad_rule",
                            "current_status": "open",
                            "severity": ["high"],
                            "min_age_days": 30,
                            "proposed_action": "archive",
                        }
                    ],
                }
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(errors) > 0
        assert any("high/critical" in e.lower() for e in errors)

    def test_critical_open_archive_rejected(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "test_profile",
                    "rules": [
                        {
                            "rule_name": "bad_rule",
                            "current_status": "open",
                            "severity": ["critical"],
                            "min_age_days": 30,
                            "proposed_action": "archive",
                        }
                    ],
                }
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(errors) > 0
        assert any("high/critical" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Test: Archived alert mutation rule rejected
# ---------------------------------------------------------------------------


class TestArchivedAlertMutationRejected:
    """Archived alerts may only propose keep or review."""

    def test_archived_archive_rejected(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "test_profile",
                    "rules": [
                        {
                            "rule_name": "bad_rule",
                            "current_status": "archived",
                            "min_age_days": 30,
                            "proposed_action": "archive",
                        }
                    ],
                }
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(errors) > 0
        assert any("archived" in e.lower() for e in errors)

    def test_archived_reopen_review_rejected(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "test_profile",
                    "rules": [
                        {
                            "rule_name": "bad_rule",
                            "current_status": "archived",
                            "min_age_days": 30,
                            "proposed_action": "reopen_review",
                        }
                    ],
                }
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(errors) > 0
        assert any("archived" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Test: Merge builtin and user profiles
# ---------------------------------------------------------------------------


class TestMergeBuiltinAndUserProfiles:
    """Merging built-in and user profiles works correctly."""

    def test_merge_with_valid_user(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            merge_builtin_and_user_profiles,
        )
        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)
        profiles, errors = merge_builtin_and_user_profiles(path)
        assert len(profiles) == 4  # 3 built-in + 1 custom
        assert errors == []
        names = {p.profile_name for p in profiles}
        assert "my_custom_review" in names

    def test_merge_skips_builtin_conflict(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            merge_builtin_and_user_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "standard",
                    "rules": [{
                        "rule_name": "r1",
                        "current_status": "resolved",
                        "min_age_days": 10,
                        "proposed_action": "archive",
                    }],
                },
                {
                    "profile_name": "valid_custom",
                    "rules": [{
                        "rule_name": "r1",
                        "current_status": "resolved",
                        "min_age_days": 10,
                        "proposed_action": "review",
                    }],
                },
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = merge_builtin_and_user_profiles(path)
        # 3 built-in + 1 valid custom (standard conflict skipped)
        assert len(profiles) == 4
        assert any("conflicts" in e.lower() for e in errors)
        names = {p.profile_name for p in profiles}
        assert "valid_custom" in names


# ---------------------------------------------------------------------------
# Test: get_expiration_profile_by_name
# ---------------------------------------------------------------------------


class TestGetProfileByName:
    """Profile retrieval by name works for both built-in and custom."""

    def test_get_builtin_profile(self):
        from marketsentry.cross_site_alert_expiration_policy import (
            get_expiration_profile_by_name,
        )
        profile = get_expiration_profile_by_name("conservative")
        assert profile is not None
        assert profile.profile_name == "conservative"

    def test_get_custom_profile(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            get_expiration_profile_by_name,
        )
        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)
        profile = get_expiration_profile_by_name(
            "my_custom_review", config_path=path,
        )
        assert profile is not None
        assert profile.profile_name == "my_custom_review"

    def test_get_nonexistent_profile(self):
        from marketsentry.cross_site_alert_expiration_policy import (
            get_expiration_profile_by_name,
        )
        profile = get_expiration_profile_by_name("nonexistent")
        assert profile is None


# ---------------------------------------------------------------------------
# Test: Preview policy with custom profile
# ---------------------------------------------------------------------------


class TestPreviewWithCustomProfile:
    """Preview works with user-defined custom profiles."""

    def test_preview_custom_profile(self, temp_db, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            preview_alert_expiration_policy,
        )
        pid = _insert_watched_property(temp_db)
        # Insert a resolved alert older than 75 days
        old_date = (datetime.now() - timedelta(days=80)).isoformat()
        _insert_alert(
            temp_db, pid,
            alert_status="resolved",
            severity="warning",
            created_at=old_date,
        )
        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)

        result = preview_alert_expiration_policy(
            database_path=temp_db,
            profile_name="my_custom_review",
            config_path=path,
        )
        assert result.total_candidates >= 1
        assert result.proposed_archive >= 1

    def test_preview_unknown_profile_returns_empty(self, temp_db):
        from marketsentry.cross_site_alert_expiration_policy import (
            preview_alert_expiration_policy,
        )
        result = preview_alert_expiration_policy(
            database_path=temp_db,
            profile_name="nonexistent",
        )
        assert result.total_candidates == 0


# ---------------------------------------------------------------------------
# Test: Export approval CSV with custom profile
# ---------------------------------------------------------------------------


class TestExportWithCustomProfile:
    """Export works with user-defined custom profiles."""

    def test_export_custom_profile(
        self, temp_db, temp_exports_dir, temp_config_dir,
    ):
        from marketsentry.cross_site_alert_expiration_policy import (
            export_alert_expiration_approval_csv,
        )
        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=80)).isoformat()
        _insert_alert(
            temp_db, pid,
            alert_status="resolved",
            severity="info",
            created_at=old_date,
        )
        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)

        result = export_alert_expiration_approval_csv(
            database_path=temp_db,
            profile_name="my_custom_review",
            exports_dir=temp_exports_dir,
            config_path=path,
        )
        assert result["row_count"] >= 1
        assert result["profile_name"] == "my_custom_review"
        assert Path(result["output_path"]).exists()

        # Verify CSV contents
        with open(result["output_path"], "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) >= 1
        assert rows[0]["profile_name"] == "my_custom_review"


# ---------------------------------------------------------------------------
# Test: CLI list profiles with config
# ---------------------------------------------------------------------------


class TestCLIListProfilesWithConfig:
    """CLI list profiles shows both built-in and custom profiles."""

    def test_list_with_config(self, temp_config_dir):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["list-cross-site-alert-expiration-profiles",
             "--profile-config", path],
        )
        assert result.exit_code == 0
        assert "my_custom_review" in result.output
        assert "standard" in result.output
        assert "conservative" in result.output

    def test_list_without_config(self):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["list-cross-site-alert-expiration-profiles"],
        )
        assert result.exit_code == 0
        assert "standard" in result.output


# ---------------------------------------------------------------------------
# Test: CLI write template
# ---------------------------------------------------------------------------


class TestCLIWriteTemplate:
    """CLI write-alert-expiration-profile-template works."""

    def test_write_template(self, temp_config_dir):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        output = str(Path(temp_config_dir) / "template.json")
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["write-alert-expiration-profile-template",
             "--output", output],
        )
        assert result.exit_code == 0
        assert Path(output).exists()

        # Verify file is valid JSON with profiles
        with open(output, "r") as f:
            data = json.load(f)
        assert "profiles" in data

    def test_write_template_no_overwrite(self, temp_config_dir):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        output = str(Path(temp_config_dir) / "template.json")
        runner = CliRunner()
        # First write
        runner.invoke(
            app,
            ["write-alert-expiration-profile-template",
             "--output", output],
        )
        # Second write without --overwrite
        result = runner.invoke(
            app,
            ["write-alert-expiration-profile-template",
             "--output", output],
        )
        assert result.exit_code == 0
        assert "already exists" in result.output.lower()


# ---------------------------------------------------------------------------
# Test: CLI preview custom profile
# ---------------------------------------------------------------------------


class TestCLIPreviewCustomProfile:
    """CLI preview works with custom profile."""

    def test_preview_with_config(self, temp_db, temp_config_dir):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["preview-cross-site-alert-expiration-policy",
             "--profile", "my_custom_review",
             "--profile-config", path,
             "--db", temp_db],
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Test: CLI export custom profile
# ---------------------------------------------------------------------------


class TestCLIExportCustomProfile:
    """CLI export works with custom profile."""

    def test_export_with_config(
        self, temp_db, temp_exports_dir, temp_config_dir,
    ):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["export-cross-site-alert-expiration-approval",
             "--profile", "my_custom_review",
             "--profile-config", path,
             "--db", temp_db,
             "--output-dir", temp_exports_dir],
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Test: Dashboard custom profile validation data loads
# ---------------------------------------------------------------------------


class TestDashboardCustomProfileValidation:
    """Dashboard imports for custom profile validation work."""

    def test_dashboard_imports(self):
        """Verify dashboard can import custom profile functions."""
        from marketsentry.cross_site_alert_expiration_policy import (
            merge_builtin_and_user_profiles,
            validate_expiration_profile_config,
            DEFAULT_CONFIG_PATH,
        )
        # Verify functions are callable
        assert callable(merge_builtin_and_user_profiles)
        assert callable(validate_expiration_profile_config)
        assert DEFAULT_CONFIG_PATH is not None

    def test_merge_returns_correct_types(self, temp_config_dir):
        """Verify merge returns expected types for dashboard."""
        from marketsentry.cross_site_alert_expiration_policy import (
            merge_builtin_and_user_profiles,
        )
        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)
        profiles, errors = merge_builtin_and_user_profiles(path)
        assert isinstance(profiles, list)
        assert isinstance(errors, list)
        for p in profiles:
            assert isinstance(p, CrossSiteAlertExpirationProfile)


# ---------------------------------------------------------------------------
# Test: No auto-apply behavior
# ---------------------------------------------------------------------------


class TestNoAutoApply:
    """Custom profiles do not auto-apply actions."""

    def test_preview_does_not_mutate(self, temp_db, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            preview_alert_expiration_policy,
        )
        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=80)).isoformat()
        aid = _insert_alert(
            temp_db, pid,
            alert_status="resolved",
            severity="warning",
            created_at=old_date,
        )
        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)

        preview_alert_expiration_policy(
            database_path=temp_db,
            profile_name="my_custom_review",
            config_path=path,
        )

        # Verify status unchanged
        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,),
            database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "resolved"

    def test_export_does_not_mutate(
        self, temp_db, temp_exports_dir, temp_config_dir,
    ):
        from marketsentry.cross_site_alert_expiration_policy import (
            export_alert_expiration_approval_csv,
        )
        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=80)).isoformat()
        aid = _insert_alert(
            temp_db, pid,
            alert_status="resolved",
            severity="warning",
            created_at=old_date,
        )
        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)

        export_alert_expiration_approval_csv(
            database_path=temp_db,
            profile_name="my_custom_review",
            exports_dir=temp_exports_dir,
            config_path=path,
        )

        # Verify status unchanged
        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,),
            database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "resolved"


# ---------------------------------------------------------------------------
# Test: No Redfin source-of-truth overwrite
# ---------------------------------------------------------------------------


class TestNoRedfin:
    """Custom profiles do not overwrite Redfin source-of-truth fields."""

    def test_no_redfin_overwrite(self):
        import marketsentry.cross_site_alert_expiration_policy as mod
        source = Path(mod.__file__).read_text()
        # Should not write to redfin source columns
        assert "redfin_url" not in source or "redfin_url" in source.split(
            "source_context"
        )[0]
        # More direct: no UPDATE to watched_properties Redfin fields
        assert "UPDATE watched_properties SET redfin" not in source


# ---------------------------------------------------------------------------
# Test: Quiet gatekeeper remains unchanged
# ---------------------------------------------------------------------------


class TestQuietGatekeeperUnchanged:
    """Custom profiles do not modify Quiet Score gatekeeper."""

    def test_no_quiet_modification(self):
        import marketsentry.cross_site_alert_expiration_policy as mod
        source = Path(mod.__file__).read_text()
        assert "quiet_score" not in source.lower() or \
            "quiet" in "gatekeeper unchanged"
        # No UPDATE to quiet_score
        assert "UPDATE" not in source or "quiet_score" not in source


# ---------------------------------------------------------------------------
# Test: No walkability fields added
# ---------------------------------------------------------------------------


class TestNoWalkabilityFields:
    """No walkability fields are present in the module."""

    def test_no_walkability(self):
        import marketsentry.cross_site_alert_expiration_policy as mod
        source = Path(mod.__file__).read_text()
        assert "walkability" not in source.lower()
        assert "walk_score" not in source.lower()


# ---------------------------------------------------------------------------
# Test: No real network calls
# ---------------------------------------------------------------------------


class TestNoNetworkCalls:
    """Module does not perform real network calls."""

    def test_no_requests_import_in_module(self):
        import marketsentry.cross_site_alert_expiration_policy as mod
        source = Path(mod.__file__).read_text()
        assert "import requests" not in source
        assert "import urllib.request" not in source
        assert "import httpx" not in source

    def test_no_network_in_module(self):
        import marketsentry.cross_site_alert_expiration_policy as mod
        source = Path(mod.__file__).read_text()
        assert "requests.get" not in source
        assert "requests.post" not in source
        assert "urlopen" not in source


# ---------------------------------------------------------------------------
# Test: Duplicate rule names within profile rejected
# ---------------------------------------------------------------------------


class TestDuplicateRuleNames:
    """Duplicate rule names within a single profile are rejected."""

    def test_duplicate_rule_names(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "test_profile",
                    "rules": [
                        {
                            "rule_name": "same_rule",
                            "current_status": "resolved",
                            "min_age_days": 30,
                            "proposed_action": "archive",
                        },
                        {
                            "rule_name": "same_rule",
                            "current_status": "acknowledged",
                            "min_age_days": 14,
                            "proposed_action": "review",
                        },
                    ],
                }
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(errors) > 0
        assert any("duplicate" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Test: Summary with custom profile
# ---------------------------------------------------------------------------


class TestSummaryWithCustomProfile:
    """Summary works with user-defined custom profiles."""

    def test_summary_custom(self, temp_db, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            summarize_alert_expiration_policy,
        )
        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=80)).isoformat()
        _insert_alert(
            temp_db, pid,
            alert_status="resolved",
            severity="warning",
            created_at=old_date,
        )
        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)

        summary = summarize_alert_expiration_policy(
            database_path=temp_db,
            profile_name="my_custom_review",
            config_path=path,
        )
        assert summary.profile_name == "my_custom_review"
        assert summary.total_candidates >= 1


# ---------------------------------------------------------------------------
# Test: CLI summary with custom profile
# ---------------------------------------------------------------------------


class TestCLISummaryCustomProfile:
    """CLI summary command works with custom profile."""

    def test_summary_with_config(self, temp_db, temp_config_dir):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["cross-site-alert-expiration-summary",
             "--profile", "my_custom_review",
             "--profile-config", path,
             "--db", temp_db],
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Test: Profiles list not array handled
# ---------------------------------------------------------------------------


class TestProfilesNotArray:
    """Non-array profiles value produces clear error."""

    def test_profiles_not_list(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {"profiles": "not_a_list"}
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert profiles == []
        assert len(errors) > 0
        assert any("list" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Test: Profile entry not dict handled
# ---------------------------------------------------------------------------


class TestProfileNotDict:
    """Non-dict profile entry produces clear error."""

    def test_profile_not_dict(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {"profiles": ["not_a_dict"]}
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert profiles == []
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# Test: Rule entry not dict handled
# ---------------------------------------------------------------------------


class TestRuleNotDict:
    """Non-dict rule entry produces clear error."""

    def test_rule_not_dict(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_policy import (
            load_user_expiration_profiles,
        )
        config = {
            "profiles": [
                {
                    "profile_name": "test_profile",
                    "rules": ["not_a_dict"],
                }
            ]
        }
        path = _write_config(temp_config_dir, config)
        profiles, errors = load_user_expiration_profiles(path)
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# Test: Constants are correct
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify module constants match expected values."""

    def test_allowed_statuses(self):
        from marketsentry.cross_site_alert_expiration_policy import (
            ALLOWED_STATUSES,
        )
        assert ALLOWED_STATUSES == frozenset({
            "open", "acknowledged", "resolved", "archived",
        })

    def test_allowed_severities(self):
        from marketsentry.cross_site_alert_expiration_policy import (
            ALLOWED_SEVERITIES,
        )
        assert ALLOWED_SEVERITIES == frozenset({
            "info", "warning", "high", "critical", "any",
        })

    def test_allowed_proposed_actions(self):
        from marketsentry.cross_site_alert_expiration_policy import (
            ALLOWED_PROPOSED_ACTIONS,
        )
        assert ALLOWED_PROPOSED_ACTIONS == frozenset({
            "archive", "review", "keep", "reopen_review",
        })

    def test_builtin_profile_names(self):
        from marketsentry.cross_site_alert_expiration_policy import (
            _BUILTIN_PROFILE_NAMES,
        )
        assert _BUILTIN_PROFILE_NAMES == frozenset({
            "conservative", "standard", "aggressive_review_only",
        })
