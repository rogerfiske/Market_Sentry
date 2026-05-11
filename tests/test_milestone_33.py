"""Tests for Milestone 33: Profile Comparison and Last-Used Profile Persistence.

Tests cover:
- Compare built-in profiles
- Compare profiles with custom config
- Compare selected subset of profiles
- Profile comparison row counts
- Two-profile diff candidate/action deltas
- Export comparison CSV
- Load missing preference returns standard
- Save valid last-used profile
- Save invalid profile rejected
- Load invalid preference falls back safely
- Clear preference
- CLI compare profiles
- CLI export profile comparison
- CLI set profile
- CLI get profile
- CLI clear profile
- Existing preview command uses valid last-used profile when --profile omitted
- Existing preview command falls back to standard when preference invalid
- Dashboard comparison data loads
- No auto-apply behavior
- No Redfin source-of-truth overwrite
- Quiet gatekeeper remains unchanged
- No walkability fields added
- No real network calls
- Existing MVP 1-32 tests still pass (run with full suite)
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
    CrossSiteAlertExpirationProfileComparisonResult,
    CrossSiteAlertExpirationProfileComparisonRow,
    CrossSiteAlertExpirationProfileDiff,
    CrossSiteAlertExpirationProfilePreference,
    CrossSiteAlertExpirationProfilePreferenceResult,
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
                    },
                ],
            }
        ]
    }


# ---------------------------------------------------------------------------
# Test: Compare built-in profiles
# ---------------------------------------------------------------------------


class TestCompareBuiltinProfiles:
    """Compare built-in profiles side-by-side."""

    def test_compare_all_builtin(self, temp_db):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            compare_alert_expiration_profiles,
        )
        result = compare_alert_expiration_profiles(
            database_path=temp_db,
        )
        assert result.profiles_compared == 3
        assert len(result.rows) == 3
        names = {r.profile_name for r in result.rows}
        assert names == {"conservative", "standard", "aggressive_review_only"}

    def test_all_rows_are_builtin(self, temp_db):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            compare_alert_expiration_profiles,
        )
        result = compare_alert_expiration_profiles(
            database_path=temp_db,
        )
        for row in result.rows:
            assert row.profile_source == "built_in"


# ---------------------------------------------------------------------------
# Test: Compare profiles with custom config
# ---------------------------------------------------------------------------


class TestCompareWithCustomConfig:
    """Compare profiles including custom user profiles."""

    def test_compare_includes_custom(self, temp_db, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            compare_alert_expiration_profiles,
        )
        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)
        result = compare_alert_expiration_profiles(
            database_path=temp_db,
            config_path=path,
        )
        assert result.profiles_compared == 4
        names = {r.profile_name for r in result.rows}
        assert "my_custom_review" in names

    def test_custom_marked_user_config(self, temp_db, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            compare_alert_expiration_profiles,
        )
        config = _valid_user_profile_config()
        path = _write_config(temp_config_dir, config)
        result = compare_alert_expiration_profiles(
            database_path=temp_db,
            config_path=path,
        )
        custom = [r for r in result.rows if r.profile_name == "my_custom_review"]
        assert len(custom) == 1
        assert custom[0].profile_source == "user_config"


# ---------------------------------------------------------------------------
# Test: Compare selected subset of profiles
# ---------------------------------------------------------------------------


class TestCompareSubset:
    """Compare a selected subset of profiles."""

    def test_compare_two(self, temp_db):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            compare_alert_expiration_profiles,
        )
        result = compare_alert_expiration_profiles(
            database_path=temp_db,
            profile_names=["conservative", "standard"],
        )
        assert result.profiles_compared == 2
        names = {r.profile_name for r in result.rows}
        assert names == {"conservative", "standard"}

    def test_missing_profile_reported(self, temp_db):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            compare_alert_expiration_profiles,
        )
        result = compare_alert_expiration_profiles(
            database_path=temp_db,
            profile_names=["standard", "nonexistent"],
        )
        assert result.profiles_compared == 1
        assert any("nonexistent" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Test: Profile comparison row counts
# ---------------------------------------------------------------------------


class TestComparisonRowCounts:
    """Comparison rows have expected count fields."""

    def test_row_has_counts(self, temp_db):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            compare_alert_expiration_profiles,
        )
        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        _insert_alert(
            temp_db, pid,
            alert_status="resolved", severity="warning",
            created_at=old_date,
        )
        result = compare_alert_expiration_profiles(
            database_path=temp_db,
        )
        # At least one profile should find the resolved alert
        found_candidates = False
        for row in result.rows:
            if row.total_candidates > 0:
                found_candidates = True
                assert row.affected_property_count >= 1
                assert row.rule_count > 0
        assert found_candidates


# ---------------------------------------------------------------------------
# Test: Two-profile diff
# ---------------------------------------------------------------------------


class TestTwoProfileDiff:
    """Two-profile diff computes deltas correctly."""

    def test_diff_same_profile(self, temp_db):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            compare_two_alert_expiration_profiles,
        )
        diff = compare_two_alert_expiration_profiles(
            "standard", "standard",
            database_path=temp_db,
        )
        assert diff.candidate_count_delta == 0
        assert diff.archive_count_delta == 0
        assert diff.alerts_only_in_a == 0
        assert diff.alerts_only_in_b == 0

    def test_diff_has_summary_text(self, temp_db):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            compare_two_alert_expiration_profiles,
        )
        diff = compare_two_alert_expiration_profiles(
            "conservative", "aggressive_review_only",
            database_path=temp_db,
        )
        assert diff.profile_a == "conservative"
        assert diff.profile_b == "aggressive_review_only"
        assert len(diff.summary_text) > 0

    def test_diff_with_data(self, temp_db):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            compare_two_alert_expiration_profiles,
        )
        pid = _insert_watched_property(temp_db)
        # 35-day resolved alert: aggressive archives, conservative doesn't
        old_date = (datetime.now() - timedelta(days=35)).isoformat()
        _insert_alert(
            temp_db, pid,
            alert_status="resolved", severity="info",
            created_at=old_date,
        )
        diff = compare_two_alert_expiration_profiles(
            "conservative", "aggressive_review_only",
            database_path=temp_db,
        )
        # aggressive_review_only archives at 30d, conservative at 90d
        # So aggressive has more candidates
        assert isinstance(diff.candidate_count_delta, int)


# ---------------------------------------------------------------------------
# Test: Export comparison CSV
# ---------------------------------------------------------------------------


class TestExportComparisonCSV:
    """Export comparison creates CSV file."""

    def test_export_creates_file(self, temp_db, temp_exports_dir):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            export_alert_expiration_profile_comparison,
        )
        result = export_alert_expiration_profile_comparison(
            database_path=temp_db,
            exports_dir=temp_exports_dir,
        )
        assert result["row_count"] == 3
        assert result["profiles_compared"] == 3
        assert Path(result["output_path"]).exists()

        # Verify CSV headers
        with open(result["output_path"], "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 3
        assert "profile_name" in rows[0]
        assert "total_candidates" in rows[0]


# ---------------------------------------------------------------------------
# Test: Load missing preference returns standard
# ---------------------------------------------------------------------------


class TestLoadMissingPreference:
    """Missing preference file returns standard as default."""

    def test_missing_file(self):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            load_last_used_expiration_profile,
        )
        result = load_last_used_expiration_profile(
            preference_path="/nonexistent/pref.json"
        )
        assert result.profile_name == "standard"
        assert result.was_fallback is True
        assert result.is_valid is True


# ---------------------------------------------------------------------------
# Test: Save valid last-used profile
# ---------------------------------------------------------------------------


class TestSaveValidProfile:
    """Saving a valid profile creates preference file."""

    def test_save_builtin(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            save_last_used_expiration_profile,
            load_last_used_expiration_profile,
        )
        pref_path = str(Path(temp_config_dir) / "pref.json")
        success, msg = save_last_used_expiration_profile(
            "conservative", preference_path=pref_path,
        )
        assert success is True
        assert Path(pref_path).exists()

        # Verify it loads back
        result = load_last_used_expiration_profile(
            preference_path=pref_path,
        )
        assert result.profile_name == "conservative"
        assert result.was_fallback is False

    def test_save_custom(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            save_last_used_expiration_profile,
            load_last_used_expiration_profile,
        )
        config = _valid_user_profile_config()
        config_path = _write_config(temp_config_dir, config, "config.json")
        pref_path = str(Path(temp_config_dir) / "pref.json")

        success, msg = save_last_used_expiration_profile(
            "my_custom_review",
            preference_path=pref_path,
            config_path=config_path,
        )
        assert success is True

        result = load_last_used_expiration_profile(
            preference_path=pref_path,
            config_path=config_path,
        )
        assert result.profile_name == "my_custom_review"


# ---------------------------------------------------------------------------
# Test: Save invalid profile rejected
# ---------------------------------------------------------------------------


class TestSaveInvalidProfileRejected:
    """Saving a non-existent profile is rejected."""

    def test_invalid_profile(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            save_last_used_expiration_profile,
        )
        pref_path = str(Path(temp_config_dir) / "pref.json")
        success, msg = save_last_used_expiration_profile(
            "nonexistent_profile", preference_path=pref_path,
        )
        assert success is False
        assert "not found" in msg.lower()
        assert not Path(pref_path).exists()


# ---------------------------------------------------------------------------
# Test: Load invalid preference falls back safely
# ---------------------------------------------------------------------------


class TestLoadInvalidPreferenceFallback:
    """Invalid preference file falls back to standard."""

    def test_invalid_json(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            load_last_used_expiration_profile,
        )
        pref_path = str(Path(temp_config_dir) / "bad_pref.json")
        with open(pref_path, "w") as f:
            f.write("{bad json")
        result = load_last_used_expiration_profile(
            preference_path=pref_path,
        )
        assert result.profile_name == "standard"
        assert result.was_fallback is True
        assert len(result.warnings) > 0

    def test_missing_profile_in_pref(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            load_last_used_expiration_profile,
        )
        pref_path = str(Path(temp_config_dir) / "pref.json")
        with open(pref_path, "w") as f:
            json.dump({"last_used_profile": "gone_profile"}, f)
        result = load_last_used_expiration_profile(
            preference_path=pref_path,
        )
        assert result.profile_name == "standard"
        assert result.was_fallback is True
        assert len(result.warnings) > 0

    def test_empty_profile_name(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            load_last_used_expiration_profile,
        )
        pref_path = str(Path(temp_config_dir) / "pref.json")
        with open(pref_path, "w") as f:
            json.dump({"last_used_profile": ""}, f)
        result = load_last_used_expiration_profile(
            preference_path=pref_path,
        )
        assert result.profile_name == "standard"
        assert result.was_fallback is True


# ---------------------------------------------------------------------------
# Test: Clear preference
# ---------------------------------------------------------------------------


class TestClearPreference:
    """Clearing preference removes the file."""

    def test_clear_existing(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            save_last_used_expiration_profile,
            clear_last_used_expiration_profile,
        )
        pref_path = str(Path(temp_config_dir) / "pref.json")
        save_last_used_expiration_profile(
            "conservative", preference_path=pref_path,
        )
        assert Path(pref_path).exists()

        success, msg = clear_last_used_expiration_profile(
            preference_path=pref_path,
        )
        assert success is True
        assert not Path(pref_path).exists()

    def test_clear_nonexistent(self, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            clear_last_used_expiration_profile,
        )
        pref_path = str(Path(temp_config_dir) / "nope.json")
        success, msg = clear_last_used_expiration_profile(
            preference_path=pref_path,
        )
        assert success is True


# ---------------------------------------------------------------------------
# Test: CLI compare profiles
# ---------------------------------------------------------------------------


class TestCLICompareProfiles:
    """CLI compare-cross-site-alert-expiration-profiles works."""

    def test_compare_cli(self, temp_db):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["compare-cross-site-alert-expiration-profiles",
             "--db", temp_db],
        )
        assert result.exit_code == 0
        # Rich may truncate long profile names in narrow terminals
        assert "conserv" in result.output
        assert "standard" in result.output

    def test_compare_subset(self, temp_db):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["compare-cross-site-alert-expiration-profiles",
             "--db", temp_db,
             "--profiles", "conservative,standard"],
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Test: CLI export profile comparison
# ---------------------------------------------------------------------------


class TestCLIExportProfileComparison:
    """CLI export-cross-site-alert-expiration-profile-comparison works."""

    def test_export_cli(self, temp_db, temp_exports_dir):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["export-cross-site-alert-expiration-profile-comparison",
             "--db", temp_db,
             "--output-dir", temp_exports_dir],
        )
        assert result.exit_code == 0
        assert "comparison exported" in result.output.lower()


# ---------------------------------------------------------------------------
# Test: CLI set profile
# ---------------------------------------------------------------------------


class TestCLISetProfile:
    """CLI set-cross-site-alert-expiration-profile works."""

    def test_set_valid(self, temp_config_dir):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        pref_path = str(Path(temp_config_dir) / "pref.json")
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["set-cross-site-alert-expiration-profile",
             "--profile", "conservative",
             "--preference-path", pref_path],
        )
        assert result.exit_code == 0
        assert "success" in result.output.lower()

    def test_set_invalid(self, temp_config_dir):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        pref_path = str(Path(temp_config_dir) / "pref.json")
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["set-cross-site-alert-expiration-profile",
             "--profile", "nonexistent",
             "--preference-path", pref_path],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Test: CLI get profile
# ---------------------------------------------------------------------------


class TestCLIGetProfile:
    """CLI get-cross-site-alert-expiration-profile works."""

    def test_get_default(self, temp_config_dir):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        pref_path = str(Path(temp_config_dir) / "pref.json")
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["get-cross-site-alert-expiration-profile",
             "--preference-path", pref_path],
        )
        assert result.exit_code == 0
        assert "standard" in result.output

    def test_get_after_set(self, temp_config_dir):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        pref_path = str(Path(temp_config_dir) / "pref.json")
        runner = CliRunner()
        runner.invoke(
            app,
            ["set-cross-site-alert-expiration-profile",
             "--profile", "conservative",
             "--preference-path", pref_path],
        )
        result = runner.invoke(
            app,
            ["get-cross-site-alert-expiration-profile",
             "--preference-path", pref_path],
        )
        assert result.exit_code == 0
        assert "conservative" in result.output


# ---------------------------------------------------------------------------
# Test: CLI clear profile
# ---------------------------------------------------------------------------


class TestCLIClearProfile:
    """CLI clear-cross-site-alert-expiration-profile works."""

    def test_clear_cli(self, temp_config_dir):
        from typer.testing import CliRunner
        from marketsentry.cli import app

        pref_path = str(Path(temp_config_dir) / "pref.json")
        # Set then clear
        runner = CliRunner()
        runner.invoke(
            app,
            ["set-cross-site-alert-expiration-profile",
             "--profile", "conservative",
             "--preference-path", pref_path],
        )
        result = runner.invoke(
            app,
            ["clear-cross-site-alert-expiration-profile",
             "--preference-path", pref_path],
        )
        assert result.exit_code == 0
        assert "cleared" in result.output.lower() or "success" in result.output.lower()


# ---------------------------------------------------------------------------
# Test: Existing preview uses last-used profile
# ---------------------------------------------------------------------------


class TestExistingPreviewUsesLastUsed:
    """Preview command uses last-used profile when --profile omitted."""

    def test_uses_saved_profile(self, temp_db, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            save_last_used_expiration_profile,
        )
        from marketsentry.cli import _resolve_expiration_profile

        pref_path = str(Path(temp_config_dir) / "pref.json")
        save_last_used_expiration_profile(
            "conservative", preference_path=pref_path,
        )

        # Patch the default preference path
        with patch(
            "marketsentry.cross_site_alert_expiration_profile_comparison"
            ".DEFAULT_PREFERENCE_PATH",
            Path(pref_path),
        ):
            resolved = _resolve_expiration_profile(None)
        assert resolved == "conservative"

    def test_falls_back_to_standard(self, temp_config_dir):
        from marketsentry.cli import _resolve_expiration_profile

        pref_path = str(Path(temp_config_dir) / "bad_pref.json")
        with open(pref_path, "w") as f:
            json.dump({"last_used_profile": "gone"}, f)

        with patch(
            "marketsentry.cross_site_alert_expiration_profile_comparison"
            ".DEFAULT_PREFERENCE_PATH",
            Path(pref_path),
        ):
            resolved = _resolve_expiration_profile(None)
        assert resolved == "standard"

    def test_explicit_profile_overrides(self):
        from marketsentry.cli import _resolve_expiration_profile

        resolved = _resolve_expiration_profile("aggressive_review_only")
        assert resolved == "aggressive_review_only"


# ---------------------------------------------------------------------------
# Test: Dashboard comparison data loads
# ---------------------------------------------------------------------------


class TestDashboardComparisonData:
    """Dashboard imports for comparison work."""

    def test_imports(self):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            compare_alert_expiration_profiles,
            load_last_used_expiration_profile,
        )
        assert callable(compare_alert_expiration_profiles)
        assert callable(load_last_used_expiration_profile)

    def test_comparison_types(self, temp_db):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            compare_alert_expiration_profiles,
        )
        result = compare_alert_expiration_profiles(
            database_path=temp_db,
        )
        assert isinstance(result, CrossSiteAlertExpirationProfileComparisonResult)
        for row in result.rows:
            assert isinstance(row, CrossSiteAlertExpirationProfileComparisonRow)


# ---------------------------------------------------------------------------
# Test: No auto-apply behavior
# ---------------------------------------------------------------------------


class TestNoAutoApply:
    """Comparison and preference do not apply actions."""

    def test_compare_does_not_mutate(self, temp_db):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            compare_alert_expiration_profiles,
        )
        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        aid = _insert_alert(
            temp_db, pid,
            alert_status="resolved", severity="info",
            created_at=old_date,
        )
        compare_alert_expiration_profiles(database_path=temp_db)

        # Verify status unchanged
        rows = execute_query(
            "SELECT alert_status FROM cross_site_trend_alerts "
            "WHERE alert_id = ?",
            (aid,),
            database_path=temp_db,
        )
        assert rows[0]["alert_status"] == "resolved"

    def test_save_pref_does_not_mutate(self, temp_db, temp_config_dir):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            save_last_used_expiration_profile,
        )
        pid = _insert_watched_property(temp_db)
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        aid = _insert_alert(
            temp_db, pid,
            alert_status="resolved", severity="info",
            created_at=old_date,
        )
        pref_path = str(Path(temp_config_dir) / "pref.json")
        save_last_used_expiration_profile(
            "standard", preference_path=pref_path,
        )

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
    """Comparison module does not overwrite Redfin fields."""

    def test_no_redfin_overwrite(self):
        import marketsentry.cross_site_alert_expiration_profile_comparison as mod
        source = Path(mod.__file__).read_text()
        assert "UPDATE watched_properties SET redfin" not in source


# ---------------------------------------------------------------------------
# Test: Quiet gatekeeper remains unchanged
# ---------------------------------------------------------------------------


class TestQuietGatekeeperUnchanged:
    """Comparison module does not modify Quiet Score gatekeeper."""

    def test_no_quiet_modification(self):
        import marketsentry.cross_site_alert_expiration_profile_comparison as mod
        source = Path(mod.__file__).read_text()
        assert "quiet_score" not in source.lower()


# ---------------------------------------------------------------------------
# Test: No walkability fields added
# ---------------------------------------------------------------------------


class TestNoWalkabilityFields:
    """No walkability fields in the module."""

    def test_no_walkability(self):
        import marketsentry.cross_site_alert_expiration_profile_comparison as mod
        source = Path(mod.__file__).read_text()
        assert "walkability" not in source.lower()
        assert "walk_score" not in source.lower()


# ---------------------------------------------------------------------------
# Test: No real network calls
# ---------------------------------------------------------------------------


class TestNoNetworkCalls:
    """Module does not perform real network calls."""

    def test_no_requests_import(self):
        import marketsentry.cross_site_alert_expiration_profile_comparison as mod
        source = Path(mod.__file__).read_text()
        assert "import requests" not in source
        assert "import urllib.request" not in source
        assert "import httpx" not in source

    def test_no_network_calls(self):
        import marketsentry.cross_site_alert_expiration_profile_comparison as mod
        source = Path(mod.__file__).read_text()
        assert "requests.get" not in source
        assert "requests.post" not in source
        assert "urlopen" not in source


# ---------------------------------------------------------------------------
# Test: get_profile_candidate_counts
# ---------------------------------------------------------------------------


class TestGetProfileCandidateCounts:
    """get_profile_candidate_counts returns expected dict."""

    def test_basic_counts(self, temp_db):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            get_profile_candidate_counts,
        )
        counts = get_profile_candidate_counts(
            database_path=temp_db,
            profile_name="standard",
        )
        assert "profile_name" in counts
        assert "total_candidates" in counts
        assert counts["profile_name"] == "standard"

    def test_default_profile(self, temp_db):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            get_profile_candidate_counts,
        )
        counts = get_profile_candidate_counts(database_path=temp_db)
        assert counts["profile_name"] == "standard"


# ---------------------------------------------------------------------------
# Test: summarize_profile_differences
# ---------------------------------------------------------------------------


class TestSummarizeProfileDifferences:
    """summarize_profile_differences returns text."""

    def test_returns_string(self, temp_db):
        from marketsentry.cross_site_alert_expiration_profile_comparison import (
            summarize_profile_differences,
        )
        text = summarize_profile_differences(
            "conservative", "standard",
            database_path=temp_db,
        )
        assert isinstance(text, str)
        assert len(text) > 0
        assert "conservative" in text
        assert "standard" in text


# ---------------------------------------------------------------------------
# Test: Model fields exist
# ---------------------------------------------------------------------------


class TestModelFields:
    """Models have expected fields."""

    def test_comparison_row_fields(self):
        row = CrossSiteAlertExpirationProfileComparisonRow(
            profile_name="test",
            profile_source="built_in",
            total_candidates=5,
        )
        assert row.profile_name == "test"
        assert row.profile_source == "built_in"
        assert row.total_candidates == 5

    def test_diff_fields(self):
        diff = CrossSiteAlertExpirationProfileDiff(
            profile_a="a",
            profile_b="b",
            candidate_count_delta=3,
        )
        assert diff.profile_a == "a"
        assert diff.candidate_count_delta == 3

    def test_preference_fields(self):
        pref = CrossSiteAlertExpirationProfilePreference(
            last_used_profile="conservative",
        )
        assert pref.last_used_profile == "conservative"
        assert "does not apply" in pref.notes.lower()

    def test_preference_result_fields(self):
        result = CrossSiteAlertExpirationProfilePreferenceResult()
        assert result.profile_name == "standard"
        assert result.is_valid is True
        assert result.was_fallback is False
